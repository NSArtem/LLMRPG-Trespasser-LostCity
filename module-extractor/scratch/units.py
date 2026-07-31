#!/usr/bin/env python3
"""T0.4 -- assemble source-native units from headings.

A **unit** is what the author wrote as one thing: a keyed area, a stat block, a
table, a rules section. It runs from one heading to the next and carries the
pages it draws from. Units, not pages, are the pipeline's unit of work.

Two decisions worth stating.

**A heading tier is a non-body tier whose lines are short.** Size alone is not
enough: Falkrest Abbey sets its OGL notice at h=8.6, well away from the body
tier, but those lines run seven words each and are plainly not headings. Length
separates them. Height says "different", length says "heading".

**Page-break continuation needs no special case.** Units break only at
headings, and lines arrive in reading order across the whole document, so a unit
whose text runs from the foot of one page to the head of the next simply
accumulates both page numbers. The join is the absence of a rule, not a rule.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bbox import BboxError, SOURCES  # noqa: E402
from columns import Line, document_lines  # noqa: E402
from tiers import Tier, body_tier, tier_table  # noqa: E402


# A heading is short. Body prose, legal boilerplate and table rows are not.
MAX_HEADING_WORDS = 6

# How much taller than body text a heading tier must be. 8% clears the 6% gap
# between Lair of the Lamb's table rows (12.9) and its body (12.2).
HEADING_MARGIN = 1.08

# A tier smaller than body counts as headings only if it is mostly capitalised.
SHOUTING_SHARE = 0.6

# Keyed areas look like "24 CRUSH HALLWAY", "1A FIRST INTERSECTION", "12b".
KEYED_AREA = re.compile(r"^(\d+[A-Za-z]?)\b")

_SLUG = re.compile(r"[^a-z0-9]+")


def slug(text: str, limit: int = 32) -> str:
    value = _SLUG.sub("-", text.lower()).strip("-")
    return value[:limit].rstrip("-") or "unit"


@dataclass
class Unit:
    unit_id: str
    heading: str
    heading_height: float
    pages: list[int]
    column: int
    lines: list[Line] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    @property
    def keyed_area(self) -> str | None:
        match = KEYED_AREA.match(self.heading)
        return match.group(1) if match else None

    def to_contract_a(self) -> dict[str, object]:
        text = self.text
        return {
            "unit_id": self.unit_id,
            "heading": self.heading,
            "pages": self.pages,
            "column": self.column,
            "text": text,
            "labels": [],  # T2.4 fills these in
            "text_bytes": len(text.encode("utf-8")),
            "heading_height": self.heading_height,
        }


def is_heading_text(text: str) -> bool:
    """Headings name something. Page numbers and bullets do not."""
    stripped = text.strip()
    if not stripped or not any(c.isalpha() for c in stripped):
        return False  # "1", "•", "— 12 —"
    return len(stripped.split()) <= MAX_HEADING_WORDS


def heading_heights(lines: list[Line], tiers: list[Tier]) -> set[float]:
    """Heights that behave like headings.

    Three filters, each earning its place against a real document:

    - **Clearly larger than body.** Being merely *different* is not enough.
      Lair of the Lamb sets random-table rows at h=12.9 against body at 12.2 --
      6% apart, above the body tier, short enough to look like headings, and not
      headings at all. The margin removes them.
    - **Or smaller but shouting.** The Lost City sets sections below its body
      size, so a smaller tier still qualifies when its lines are predominantly
      capitalised.
    - **Short, and containing a letter.** Removes page numbers (a whole tier of
      them in Lair, at h=13.3) and bullet glyphs.
    """
    body = body_tier(tiers)
    if body is None:
        return set()
    by_height: dict[float, list[Line]] = {}
    for line in lines:
        by_height.setdefault(line.height, []).append(line)

    heights: set[float] = set()
    for height, members in by_height.items():
        named = [line for line in members if is_heading_text(line.text)]
        if not named or len(named) < len(members) * 0.5:
            continue
        typical = statistics.median(len(line.text.split()) for line in named)
        if typical > MAX_HEADING_WORDS:
            continue
        if height >= body.height * HEADING_MARGIN:
            heights.add(height)
        elif height < body.height:
            shouting = sum(1 for line in named if line.is_upper)
            if shouting >= len(named) * SHOUTING_SHARE:
                heights.add(height)
    return heights


def assemble(lines: list[Line], headings: set[float]) -> list[Unit]:
    """Split the document at heading lines; everything else is unit body."""
    units: list[Unit] = []
    current: Unit | None = None
    seen: dict[str, int] = {}

    for line in lines:
        if line.height in headings and is_heading_text(line.text):
            base = f"p{line.page}.{slug(line.text)}"
            seen[base] = seen.get(base, 0) + 1
            unit_id = base if seen[base] == 1 else f"{base}-{seen[base]}"
            current = Unit(
                unit_id=unit_id,
                heading=line.text.strip(),
                heading_height=line.height,
                pages=[line.page],
                column=line.column,
                lines=[line],
            )
            units.append(current)
            continue
        if current is None:
            continue  # front matter before the first heading
        current.lines.append(line)
        if line.page not in current.pages:
            current.pages.append(line.page)
    return units


def units_for(pdf: Path) -> list[Unit]:
    lines = document_lines(pdf)
    return assemble(lines, heading_heights(lines, tier_table(lines)))


def report(pdf: Path, show: int = 0) -> dict[str, object]:
    units = units_for(pdf)
    keyed = [unit for unit in units if unit.keyed_area]
    spanning = [unit for unit in units if len(unit.pages) > 1]
    sizes = [len(unit.text.encode("utf-8")) for unit in units] or [0]
    row = {
        "name": pdf.name,
        "units": len(units),
        "keyed": len(keyed),
        "spanning_pages": len(spanning),
        "median_bytes": int(statistics.median(sizes)),
        "max_bytes": max(sizes),
        "empty": sum(1 for unit in units if not unit.text.strip()),
    }
    print(f"{pdf.name[:38]:<38} {row['units']:>5} units {row['keyed']:>4} keyed "
          f"{row['spanning_pages']:>4} multi-page  median {row['median_bytes']:>5}B "
          f"max {row['max_bytes']:>6}B")
    for unit in units[:show]:
        print(f"    {unit.unit_id:<44} p{unit.pages} h={unit.heading_height} "
              f"{len(unit.text.encode('utf-8')):>5}B  {unit.heading[:38]}")
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", nargs="*", type=Path)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--show", type=int, default=0, help="print the first N units")
    parser.add_argument("--dump", type=Path, help="write Contract A JSON to a directory")
    args = parser.parse_args(argv)
    targets = list(SOURCES) if args.all else args.pdf
    if not targets:
        parser.error("give at least one PDF, or --all")

    for pdf in targets:
        try:
            report(pdf, show=args.show)
            if args.dump:
                args.dump.mkdir(parents=True, exist_ok=True)
                payload = [unit.to_contract_a() for unit in units_for(pdf)]
                out = args.dump / f"{slug(pdf.stem, 48)}.json"
                out.write_text(
                    json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
        except BboxError as exc:
            print(f"{pdf.name}: ERROR {exc}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
