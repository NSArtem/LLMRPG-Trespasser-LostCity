#!/usr/bin/env python3
"""T0.2 (revised) -- group lines by typographic style.

The first version clustered *glyph heights* with a relative tolerance, because
``pdftotext -bbox-layout`` offered nothing else. With ``pdftohtml`` the
typesetter's own choices are available directly -- point size, family, weight,
colour -- and they are **discrete**. Two lines either share a style or they do
not, so there is no tolerance to tune and no cluster to get wrong.

**Bigger still does not mean heading.** The Lost City sets section headings at
the same 14pt as its body and distinguishes them with bold. So the *body* style
is identified as the one carrying the most text, and every other style is
reported relative to it.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bbox import BboxError, SOURCES  # noqa: E402
from columns import Line, document_lines  # noqa: E402


# Styles holding less than this share of a document's lines are noise.
STYLE_FLOOR = 0.002

Style = tuple[float, str, bool, str, bool]  # size, family, bold, colour, italic


@dataclass(frozen=True)
class StyleGroup:
    style: Style
    lines: int
    words: int
    share: float
    median_words: float
    samples: tuple[str, ...]

    @property
    def size(self) -> float:
        return self.style[0]

    @property
    def family(self) -> str:
        return self.style[1].split("+")[-1]

    @property
    def bold(self) -> bool:
        return self.style[2]

    @property
    def color(self) -> str:
        return self.style[3]

    @property
    def label(self) -> str:
        return f"{self.size:.0f}pt {self.family}{' B' if self.bold else ''} {self.color}"


def style_table(lines: list[Line], floor: float = STYLE_FLOOR) -> list[StyleGroup]:
    """Group lines by exact style, most-used first."""
    if not lines:
        return []
    grouped: dict[Style, list[Line]] = {}
    for line in lines:
        grouped.setdefault(line.style, []).append(line)

    groups = []
    for style, members in grouped.items():
        share = len(members) / len(lines)
        if share < floor:
            continue
        samples = tuple(
            dict.fromkeys(
                line.text.strip()[:48]
                for line in sorted(members, key=lambda item: (item.page, item.y))
                if line.text.strip()
            )
        )[:3]
        groups.append(
            StyleGroup(
                style=style,
                lines=len(members),
                words=sum(len(line.text.split()) for line in members),
                share=share,
                median_words=statistics.median(
                    len(line.text.split()) for line in members
                ),
                samples=samples,
            )
        )
    return sorted(groups, key=lambda group: -group.words)


def body_style(groups: list[StyleGroup]) -> StyleGroup | None:
    """The style carrying the most words -- the document\'s running text."""
    return groups[0] if groups else None


def report(pdf: Path) -> None:
    lines = document_lines(pdf)
    groups = style_table(lines)
    body = body_style(groups)
    print(f"\n=== {pdf.name}  ({len(lines)} lines, {len(groups)} styles) ===")
    print(f"{'style':<38} {'lines':>6} {'words':>7} {'med':>4}  {'role':<5} sample")
    for group in groups[:10]:
        role = "BODY" if group is body else ""
        sample = group.samples[0] if group.samples else ""
        print(f"{group.label:<38} {group.lines:>6} {group.words:>7} "
              f"{group.median_words:>4.0f}  {role:<5} {sample[:40]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", nargs="*", type=Path)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)
    targets = list(SOURCES) if args.all else args.pdf
    if not targets:
        parser.error("give at least one PDF, or --all")
    failures = 0
    for pdf in targets:
        try:
            report(pdf)
        except BboxError as exc:
            print(f"\n=== {pdf.name} === ERROR: {exc}")
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
