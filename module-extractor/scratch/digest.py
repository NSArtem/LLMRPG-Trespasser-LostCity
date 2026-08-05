#!/usr/bin/env python3
"""T0.5 -- render unit tables as something a person can actually review.

The gate asks whether unit *boundaries* are right, which no test can answer.
Raw Contract A JSON is the wrong artefact for that: it is 150 KB per source and
buries the six things worth looking at. This writes one Markdown file per
source, leading with the checks most likely to expose a bad boundary.

**Suspicions are not failures.** Everything flagged here is a prompt to look,
not a defect. A 12-byte unit may be a genuine cross-reference stub; a 4 KB unit
may be a legitimately long rules section.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bbox import BboxError, SOURCES  # noqa: E402
from units import Unit, retention, segment, slug  # noqa: E402


TINY = 40      # bytes; below this a unit is probably a stub or a stray heading
HUGE = 3000    # bytes; above this a unit is probably two units
STRICT_KEY = re.compile(r"^\d+[A-Za-z]?\s+\S")


def _keyed_coverage(units: list[Unit]) -> tuple[list[int], list[str]]:
    """Which numeric keys are present, and which are missing from the run."""
    numbers = sorted({int(unit.key) for unit in units if unit.key and unit.key.isdigit()})
    if not numbers:
        return [], []
    gaps = [str(n) for n in range(numbers[0], numbers[-1] + 1) if n not in set(numbers)]
    return numbers, gaps


def digest(pdf: Path) -> str:
    lines, units = segment(pdf)
    total, kept, dropped = retention(lines, units)
    sizes = [len(unit.text.encode("utf-8")) for unit in units] or [0]
    keyed = [unit for unit in units if unit.key]
    strict = [unit for unit in units if STRICT_KEY.match(unit.heading)]
    numbers, gaps = _keyed_coverage(units)
    tiny = [unit for unit in units if len(unit.text.encode("utf-8")) < TINY]
    huge = [unit for unit in units if len(unit.text.encode("utf-8")) > HUGE]
    spanning = [unit for unit in units if len(unit.pages) > 1]
    pages = sorted({page for unit in units for page in unit.pages})

    out: list[str] = [
        f"# {pdf.name}", "",
        "| | |", "|---|---|",
        f"| units | {len(units)} |",
        f"| text retained | {100 * kept / total if total else 100:.1f}% "
        f"({total - kept} of {total} characters reached no unit) |",
        f"| pages covered | {len(pages)} |",
        f"| keyed units | {len(keyed)} (strict `N NAME` form: {len(strict)}) |",
        f"| spanning a page break | {len(spanning)} |",
        f"| size | median {int(statistics.median(sizes))}B, "
        f"max {max(sizes)}B, min {min(sizes)}B |",
        "",
    ]

    out += ["## Checks", ""]
    losses = sorted(dropped.items(), key=lambda item: -item[1])[:6]
    heavy = [(page, size) for page, size in losses if size >= TINY * 10]
    out += [f"**Text reaching no unit:** {total - kept} characters"
            + (f", worst pages {', '.join(f'p{p} ({n})' for p, n in losses)}"
               if losses else "")]
    if heavy:
        out += ["", "> A page losing hundreds of characters is not a cover. It "
                "is a page whose heading was never recognised, so every line on "
                "it fell through `assemble`'s front-matter branch. Open it.", ""]
    else:
        out.append("")

    if numbers:
        out += [f"**Keyed range** {numbers[0]}–{numbers[-1]}, {len(numbers)} distinct."]
        out += [f"**Missing keys:** {', '.join(gaps) if gaps else 'none'}", ""]
        if gaps:
            out += ["> A gap usually means a heading was missed, or the source "
                    "genuinely skips that number. Check a few against the PDF.", ""]
    else:
        out += ["**No numeric keys found.** Either the source keys areas by "
                "letter, or keyed-area detection is failing here.", ""]

    out += [f"**Suspiciously small** (< {TINY}B): {len(tiny)}"]
    for unit in tiny[:12]:
        out.append(f"- `{unit.unit_id}` p{unit.pages} — {unit.heading[:60]}")
    if len(tiny) > 12:
        out.append(f"- …and {len(tiny) - 12} more")
    out.append("")

    out += [f"**Suspiciously large** (> {HUGE}B), likely under-segmented: {len(huge)}"]
    for unit in huge[:12]:
        size = len(unit.text.encode("utf-8"))
        out.append(f"- `{unit.unit_id}` p{unit.pages} {size}B — {unit.heading[:60]}")
    out.append("")

    out += ["## Units", "", "| id | pages | bytes | heading |", "|---|---|---:|---|"]
    for unit in units:
        size = len(unit.text.encode("utf-8"))
        span = f"{unit.pages[0]}–{unit.pages[-1]}" if len(unit.pages) > 1 else str(unit.pages[0])
        heading = unit.heading.replace("|", "\\|")[:70]
        out.append(f"| `{unit.unit_id}` | {span} | {size} | {heading} |")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", nargs="*", type=Path)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--out", type=Path,
                        default=Path(__file__).resolve().parent / "unit-tables")
    args = parser.parse_args(argv)
    targets = list(SOURCES) if args.all else args.pdf
    if not targets:
        parser.error("give at least one PDF, or --all")
    args.out.mkdir(parents=True, exist_ok=True)
    for pdf in targets:
        try:
            path = args.out / f"{slug(pdf.stem, 48)}.md"
            path.write_text(digest(pdf), encoding="utf-8")
            print(f"{pdf.name[:44]:<44} -> {path.name}")
        except BboxError as exc:
            print(f"{pdf.name}: ERROR {exc}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
