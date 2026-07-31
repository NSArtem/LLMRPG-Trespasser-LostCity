#!/usr/bin/env python3
"""T0.4 -- assemble source-native units from headings.

A **unit** is what the author wrote as one thing: a keyed area with everything
belonging to it, a stat block, a table, a rules section. Units, not pages, are
the pipeline\'s unit of work.

**Subsections are absorbed into their keyed area** (decision 1). The dataflow
document treats page 31 of *Lair of the Lamb* as one unit ``p31.area24``
containing the room, the ceiling, the trap doors, the flooded sub-areas and the
four ways across. Splitting them truncates concepts: ``Crossing the Hallway``
never names which hallway, and ``24 CRUSH HALLWAY`` never mentions it can be
crossed. Per the dataflow document, "an over-large unit is a cost problem; a
truncated unit is a correctness problem".

Note that separate records do not require separate units. One unit declares many
entities -- the reference build produced nine records from page 31, including
``location.24a`` and ``procedure.cross-crush-hallway`` -- so absorbing costs
nothing in output granularity.

**Rank comes from style, then from the key. Not from colour.** An earlier note
claimed keyed areas were blue and subsections black in Lair. That is wrong:
``24 CRUSH HALLWAY``, ``24A``, ``24B``, ``24C`` and ``Crossing the Hallway`` are
all 18pt F10 #3333ff. Within one style the distinction is textual -- a heading
that opens a new root key starts a unit, a heading that extends the current key
or carries none is absorbed.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bbox import BboxError, SOURCES  # noqa: E402
from columns import Line, document_lines  # noqa: E402
from tiers import Style, StyleGroup, body_style, style_table  # noqa: E402


# Doom keys areas as "Area A-5 - Sign of Three Rats (Flophouse):" -- eight
# words. A limit of six rejected the style outright and lost all 26 of its
# areas. Style membership does the real discriminating; this is only a guard
# against a style that is mostly body prose.
MAX_HEADING_WORDS = 10

# Numeric keys: "24 CRUSH HALLWAY" -> 24, "1A FIRST INTERSECTION" -> 1, "24C" -> 24.
# Lettered keys: "Area A-4 - Chapel of Justicia:" -> A, "Area A" -> A. Doom keys
# its whole village that way, and lettered sub-maps are a common convention.
KEY_ROOT = re.compile(r"^(\d+)")
KEY_LETTER = re.compile(r"^(?:area|room|location)\s+([A-Z](?:-\d+)?)\b", re.IGNORECASE)
# Unicode-aware: an ASCII-only class silently erases Cyrillic, and every
# heading in a Russian module then slugs to the same empty string.
_SLUG = re.compile(r"[\W_]+", re.UNICODE)


def slug(text: str, limit: int = 32) -> str:
    value = _SLUG.sub("-", text.casefold()).strip("-_")
    return value[:limit].rstrip("-_") or "unit"


def key_root(text: str) -> str | None:
    """The key a heading opens, numeric or lettered, or None."""
    stripped = text.strip()
    match = KEY_ROOT.match(stripped)
    if match:
        return match.group(1)
    match = KEY_LETTER.match(stripped)
    return match.group(1).upper() if match else None


def is_heading_text(text: str) -> bool:
    """Headings name something. Page numbers and bullet glyphs do not."""
    stripped = text.strip()
    if not stripped or not any(character.isalpha() for character in stripped):
        return False
    return len(stripped.split()) <= MAX_HEADING_WORDS


@dataclass
class Unit:
    unit_id: str
    heading: str
    style: Style
    pages: list[int]
    column: int
    key: str | None
    lines: list[Line] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

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
            "keyed_area": self.key,
            "style": {"size": self.style[0], "family": self.style[1].split("+")[-1],
                      "bold": self.style[2], "color": self.style[3]},
        }


def heading_ranks(groups: list[StyleGroup], lines: list[Line]) -> dict[Style, int]:
    """Map each heading style to a rank; 0 is the most senior."""
    body = body_style(groups)
    if body is None:
        return {}
    named: dict[Style, list[Line]] = {}
    for line in lines:
        if is_heading_text(line.text):
            named.setdefault(line.style, []).append(line)

    # Shortness is relative to the document, not absolute. Doom's areas run to
    # eight words against an eleven-word body; a fixed limit of six lost all 26
    # of them, and raising it to ten admitted body-like styles in the Russian
    # module and Falkrest. Measuring against body adapts to both.
    limit = max(4.0, body.median_words * 0.8)
    candidates = []
    for group in groups:
        if group.style == body.style or group.median_words > limit:
            continue
        if len(named.get(group.style, [])) < group.lines * 0.5:
            continue  # mostly page numbers or glyphs, not headings
        candidates.append(group)

    # Senior first: larger, then bold, then non-black.
    candidates.sort(key=lambda g: (-g.size, not g.bold, g.color.lower() == "#000000"))
    return {group.style: rank for rank, group in enumerate(candidates)}


def assemble(lines: list[Line], ranks: dict[Style, int],
             repeated: set[str] | None = None) -> list[Unit]:
    units: list[Unit] = []
    current: Unit | None = None
    seen: dict[str, int] = {}

    def starts_new(line: Line, rank: int) -> bool:
        """Absorption happens *inside* a keyed area, and nowhere else.

        An earlier version absorbed every junior heading, which swallowed the
        keyed areas into the part titles above them and left Lair with 16 units
        and no keys at all. Outside a keyed area, a heading of any rank opens a
        unit -- that is what makes rules chapters segment.
        """
        if current is None:
            return True
        here = ranks[current.style]
        if rank < here:
            return True  # more senior: always a new unit
        if current.key is None:
            return True  # not inside a keyed area, so nothing to absorb into
        if rank > here:
            return False  # subordinate heading within a keyed area
        root = key_root(line.text)
        if root is not None:
            return root != current.key
        # No key, same style as the keyed areas around it. Case decides whether
        # it is a sibling section or a subsection: Lair sets FIGHTING THE LAMB
        # -- the climax -- in the same style as its rooms, and absorbing it into
        # 44A WALL buried a major section inside a wall. Crossing the Hallway,
        # a genuine subsection, is title case.
        return line.is_upper

    for line in lines:
        rank = ranks.get(line.style)
        is_furniture = repeated is not None and line.text.strip() in repeated
        if (rank is not None and not is_furniture
                and is_heading_text(line.text) and starts_new(line, rank)):
            base = f"p{line.page}.{slug(line.text)}"
            seen[base] = seen.get(base, 0) + 1
            unit_id = base if seen[base] == 1 else f"{base}-{seen[base]}"
            current = Unit(
                unit_id=unit_id,
                heading=line.text.strip(),
                style=line.style,
                pages=[line.page],
                column=line.column,
                key=key_root(line.text),
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


FURNITURE_PAGES = 3


def furniture(lines: list[Line]) -> set[str]:
    """Heading-shaped text that repeats across pages is running furniture.

    Page headers, footers, running heads and watermarks are set in heading
    styles and are not headings. The Russian module is a personalised copy
    stamped with a purchaser's address on every page, which alone produced 49
    spurious units; its running heads ("глава 2", the module title) produced
    more. Two appearances can be a genuine repeat -- Lair keys 25F CRYPT twice
    -- so the threshold is three distinct pages.
    """
    seen: dict[str, set[int]] = {}
    for line in lines:
        text = line.text.strip()
        if text:
            seen.setdefault(text, set()).add(line.page)
    return {text for text, pages in seen.items() if len(pages) >= FURNITURE_PAGES}


TABLE_RUN = 4      # consecutive tiny headings before it is read as a table
TABLE_ROW_BYTES = 48


def merge_table_runs(units: list[Unit]) -> list[Unit]:
    """Fold a run of table rows back into the unit above them.

    A random table is a unit; its **rows** are not. Lair sets its
    character-generation tables so every row opens with its die number --
    "1 Athletic", "2 Beautiful", "3 Boney" -- which matches the keyed-area
    shape exactly and produced 89 units of about twenty bytes each.

    Nothing is discarded. A wandering-monster table is critical content, so the
    rows are merged into the preceding unit rather than filtered out; the table
    ends up as one unit, which is what the dataflow document asks for.

    The signal is the run: four or more consecutive headings, each with almost
    no body. One tiny unit is a stub, four in a row is a table.
    """
    merged: list[Unit] = []
    run: list[Unit] = []

    def flush() -> None:
        if not run:
            return
        if len(run) >= TABLE_RUN and merged:
            host = merged[-1]
            for unit in run:
                host.lines.extend(unit.lines)
                for page in unit.pages:
                    if page not in host.pages:
                        host.pages.append(page)
        else:
            merged.extend(run)
        run.clear()

    for unit in units:
        tiny = len(unit.text.encode("utf-8")) <= TABLE_ROW_BYTES
        if tiny:
            run.append(unit)
            continue
        flush()
        merged.append(unit)
    flush()
    return merged


def units_for(pdf: Path) -> list[Unit]:
    lines = document_lines(pdf)
    groups = style_table(lines)
    ranks = heading_ranks(groups, lines)
    repeated = furniture(lines)
    return merge_table_runs(assemble(lines, ranks, repeated))


def report(pdf: Path, show: int = 0) -> None:
    import statistics

    units = units_for(pdf)
    keyed = [unit for unit in units if unit.key]
    spanning = [unit for unit in units if len(unit.pages) > 1]
    sizes = [len(unit.text.encode("utf-8")) for unit in units] or [0]
    print(f"{pdf.name[:36]:<36} {len(units):>4} units {len(keyed):>4} keyed "
          f"{len(spanning):>4} multi-page  median {int(statistics.median(sizes)):>5}B "
          f"max {max(sizes):>6}B")
    for unit in units[:show]:
        print(f"    {unit.unit_id:<40} p{unit.pages} "
              f"{len(unit.text.encode('utf-8')):>5}B  {unit.heading[:36]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", nargs="*", type=Path)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--show", type=int, default=0)
    parser.add_argument("--dump", type=Path)
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
                (args.dump / f"{slug(pdf.stem, 48)}.json").write_text(
                    json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
        except BboxError as exc:
            print(f"{pdf.name}: ERROR {exc}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
