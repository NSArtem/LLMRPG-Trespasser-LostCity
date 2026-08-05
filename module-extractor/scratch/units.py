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

# A dot leader points at a page; it never opens one. Falkrest Abbey's contents
# page is set in the same style as its section titles, so thirteen rows like
# ``2 The Frozen Cloister .....13`` were emitted as units -- and being keyed,
# they survived every rule aimed at short ones. Four dots is past any ellipsis.
_LEADER = re.compile(r"\.{4,}")


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
    if _LEADER.search(stripped):
        return False
    return len(stripped.split()) <= MAX_HEADING_WORDS


def _merge(first: Line, second: Line, separator: str = " ") -> Line:
    """One line from two, taking the style that carries the most text."""
    dominant = first if len(first.text) >= len(second.text) else second
    return Line(
        page=first.page,
        column=first.column,
        x=min(first.x, second.x),
        # The *lowest* line, so a heading wrapping onto a third line still
        # measures its gap against the second rather than the first.
        y=max(first.y, second.y),
        height=max(first.height, second.height),
        text=f"{first.text}{separator}{second.text}".strip(),
        size=dominant.size,
        family=dominant.family,
        bold=dominant.bold,
        color=dominant.color,
        italic=dominant.italic,
    )


def rejoin_run_ins(lines: list[Line]) -> list[Line]:
    """Undo a run-in split that no unit boundary will ever use.

    ``columns._split_run_in_heading`` cuts a row where a non-body prefix gives
    way to body text, because Doom sets its keyed areas that way:
    ``Area A-4 - Chapel of Justicia: The chapel is a low...``. The split is
    typographic and indiscriminate, and *Lair of the Lamb* sets emphasis in the
    same shape -- ``Lvl 4 Def leather Slam 1d6``, ``Wooden Table holding 1
    immature Lambfruit``, ``Three enormous stone bowls. Each bowl contains 4``.

    Inside a keyed area those prefixes are absorbed and nothing shows. Outside
    one, every prefix opened a unit, which shredded the stat blocks: the Lantern
    Worm lost both its second stat line and all three of its abilities to units
    named ``Crawl``, ``Eat Light -``, ``Lantern -`` and ``Stonemeld -``.

    A prefix earns a unit boundary only by opening a key. That is precisely
    Doom's case and none of Lair's, so the split is kept where it was needed and
    reversed everywhere else.
    """
    joined: list[Line] = []
    skip = False
    for index, line in enumerate(lines):
        if skip:
            skip = False
            continue
        following = lines[index + 1] if index + 1 < len(lines) else None
        if (line.run_in and key_root(line.text) is None and following is not None
                and following.page == line.page
                and following.column == line.column
                and abs(following.y - line.y) <= max(line.height, 1.0) * 0.5):
            joined.append(_merge(line, following))
            skip = True
            continue
        joined.append(line)
    return joined


# A wrapped heading's continuation sits one line down, not a paragraph away.
WRAP_GAP = 2.0
# A heading that has finished its sentence is not waiting for a second line. A
# colon is *not* on this list: it ends Doom's run-in keys, and those are excluded
# already by carrying ``run_in``, while Lair wraps a part title as
# ``Part 1: / Lair of the Lamb``.
_HEADING_END = ".!?"


def join_wrapped_headings(lines: list[Line], ranks: dict[Style, int]) -> list[Line]:
    """A heading too long for its measure is one heading, not several.

    Page 27 of *Lair of the Lamb* is a divider reading ``Part 2 / Gallery of /
    the Ghouls`` in one 81pt style. Three lines, three units, six to sixteen
    bytes each, and the section title that page exists to announce was never
    attached to anything.

    Only same-style neighbours in the same column join, and only when the
    *second* line opens no key -- otherwise a table whose rows are keyed by die
    number (``1 Athletic``, ``2 Beautiful``) would collapse into a single
    heading.

    **The first line may open one, and usually does.** Requiring both to be
    key-free meant a keyed heading could never wrap, which is how Шпиль Кетцаль
    ended up with ``12. ПОГОСТ ГРОМОВЫХ`` as a 33-byte unit and ``ЯЩЕРИЦ`` --
    the rest of its own name -- as a 7,734-byte one carrying the room. Four of
    its keyed areas were cut this way, and the source's largest unit was named
    for the second half of a heading.
    """
    joined: list[Line] = []
    for line in lines:
        previous = joined[-1] if joined else None
        if (previous is not None
                and not line.run_in and not previous.run_in
                and line.style == previous.style and line.style in ranks
                and line.page == previous.page and line.column == previous.column
                and 0 <= line.y - previous.y <= max(previous.height, 1.0) * WRAP_GAP
                and previous.is_upper == line.is_upper
                and not previous.text.rstrip().endswith(tuple(_HEADING_END))
                and key_root(line.text) is None
                and is_heading_text(previous.text) and is_heading_text(line.text)
                and len(f"{previous.text} {line.text}".split()) <= MAX_HEADING_WORDS):
            joined[-1] = _merge(previous, line)
            continue
        joined.append(line)
    return joined


@dataclass
class Unit:
    unit_id: str
    heading: str
    style: Style
    pages: list[int]
    column: int
    key: str | None
    rank: int = 0
    path: tuple[str, ...] = ()
    lines: list[Line] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    @property
    def bodyless(self) -> bool:
        """Nothing but its own heading -- a section title, not a section."""
        return len(self.lines) <= 1

    def to_contract_a(self) -> dict[str, object]:
        text = self.text
        return {
            "unit_id": self.unit_id,
            "heading": self.heading,
            "heading_path": list(self.path),
            "pages": self.pages,
            "column": self.column,
            "text": text,
            "labels": [],  # T2.4 fills these in
            "text_bytes": len(text.encode("utf-8")),
            "keyed_area": self.key,
            "style": {"size": self.style[0], "family": self.style[1].split("+")[-1],
                      "bold": self.style[2], "color": self.style[3],
                      "italic": self.style[4]},
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


def opens_a_section(line: Line, body_size: float) -> bool:
    """Whether a subordinate heading names a section or labels part of a block.

    *Lair of the Lamb*'s bestiary sets a monster's name at 21pt and then repeats
    it at 16pt over the stat lines, with the traits -- ``Immunity – Acid.``,
    ``Spells - delay, haste, scry`` -- in 16pt too. Body is also 16pt. Three
    monsters became ten units, and ``Immunity – Acid.`` was not a stub but a
    1,065-byte unit holding the trait below it and the Lamb's whole description:
    a unit named for one line of a stat block and containing another creature's
    prose.

    Size settles it. A style no larger than body is a label inside something,
    not a section of its own -- while its rules chapter sets ``Time``, ``Doors``
    and ``Movement`` at 21pt, above body, and those must keep segmenting.

    **A key overrides size.** Doom of the Savage Kings sets its 26 keyed areas
    at body size in a display family, and they are exactly the boundaries the
    pipeline exists to find.
    """
    return line.size > body_size or key_root(line.text) is not None


def assemble(lines: list[Line], ranks: dict[Style, int],
             repeated: set[str] | None = None,
             body_size: float = 0.0) -> list[Unit]:
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
        if rank > here:
            if current.key is not None:
                return False  # subordinate heading within a keyed area
            return opens_a_section(line, body_size)
        if current.key is None:
            return True  # not inside a keyed area, so nothing to absorb into
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
                rank=rank,
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
FURNITURE_SPREAD = 6.0  # points; furniture is nailed to a position, content is not


def furniture(lines: list[Line]) -> set[str]:
    """Heading-shaped text that repeats *at the same place* is running furniture.

    Page headers, footers, running heads and watermarks are set in heading
    styles and are not headings. The Russian module is a personalised copy
    stamped with a purchaser's address on every page, which alone produced 49
    spurious units; its running heads ("глава 2", the module title) produced
    more. Two appearances can be a genuine repeat -- Lair keys 25F CRYPT twice
    -- so the threshold is three distinct pages.

    **Repetition alone is not enough.** *Lair of the Lamb* heads three
    consecutive pages ``Encounter Table (Lamb Alive)``, and counting pages
    deleted that heading while leaving its ``(Lamb Dead)`` twin -- printed
    twice -- standing. The two tables then looked like different kinds of thing
    when they are the same kind of thing.

    What actually separates a running head from a repeated title is that
    furniture is nailed to a vertical position and content is not. So a repeat
    must also be positionally locked before it is discarded.
    """
    seen: dict[str, list[Line]] = {}
    for line in lines:
        text = line.text.strip()
        if text:
            seen.setdefault(text, []).append(line)
    repeated = set()
    for text, members in seen.items():
        if len({line.page for line in members}) < FURNITURE_PAGES:
            continue
        positions = [line.y for line in members]
        if max(positions) - min(positions) <= FURNITURE_SPREAD:
            repeated.add(text)
    return repeated


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


def attach_paths(units: list[Unit]) -> list[Unit]:
    """Give every unit the section titles standing above it.

    A title with nothing under it but more headings cannot become a unit worth
    extracting, and deleting it would lose real information: page 18 of *Lair of
    the Lamb* prints two encounter tables side by side, both broken into
    ``Active`` / ``Passive`` / ``Indirect Encounters`` in one 21pt style. Rank
    cannot nest them -- the title and its subsections are typographically
    identical -- so ``Active Encounters`` reached the model with no way to know
    whether the Lamb was alive or dead.

    Keeping the title as a unit *and* copying it into its children's path costs
    one short unit and keeps every physical page accounted for, which the
    coverage invariant at T4.4 depends on.

    **A same-rank title governs only its own page.** Rank alone cannot say
    whether a 21pt heading is a sibling of the 21pt title above it or a child of
    it, and guessing "child" leaked ``Encounter Table (Lamb Dead)`` onto every
    keyed room for the next three pages. Two tables printed side by side on one
    page is the evidence for nesting, and it does not survive a page turn. A
    genuinely senior title -- a part divider -- keeps its scope either way.
    """
    stack: list[tuple[int, str, int]] = []
    for unit in units:
        while stack and (
            stack[-1][0] > unit.rank
            or (stack[-1][0] == unit.rank
                and (unit.bodyless or unit.pages[0] != stack[-1][2]))
        ):
            stack.pop()
        unit.path = tuple(heading for _, heading, _page in stack)
        if unit.bodyless:
            stack.append((unit.rank, unit.heading, unit.pages[0]))
    return units


def segment(pdf: Path) -> tuple[list[Line], list[Unit]]:
    """The units, and the lines they were built from.

    Returning both is what makes retention measurable: a unit list alone cannot
    say whether anything was dropped on the way in. See ``retention``.
    """
    # **Ranks come from the raw lines, before any joining.** Which styles the
    # typesetter used for headings is a fact about the document; rejoining and
    # wrapping are decisions about it. Ranking the joined lines instead lets a
    # fix rewrite its own evidence: dropping Winter's Daughter's short non-keyed
    # run-ins lifted the median length of the remaining bold lines from 2.5
    # words to 5.0, past the threshold that admits a style as a heading, and all
    # 23 of its keyed rooms were absorbed into two units.
    lines = document_lines(pdf)
    groups = style_table(lines)
    ranks = heading_ranks(groups, lines)
    lines = join_wrapped_headings(rejoin_run_ins(lines), ranks)
    repeated = furniture(lines)
    body = body_style(groups)
    units = attach_paths(merge_table_runs(
        assemble(lines, ranks, repeated, body.size if body else 0.0)))
    return lines, units


def units_for(pdf: Path) -> list[Unit]:
    return segment(pdf)[1]


def retention(lines: list[Line], units: list[Unit]) -> tuple[int, int, dict[int, int]]:
    """Characters in, characters into units, and what was dropped per page.

    A unit count cannot detect loss -- Doom of the Savage Kings segmented into a
    plausible-looking 33 units while two whole pages of prose fell through the
    "before the first heading" branch of ``assemble``, because a 72pt drop cap
    had fused their headings into body lines. Retention sees that; nothing else
    in the digest does.
    """
    held = {id(line) for unit in units for line in unit.lines}
    dropped: dict[int, int] = {}
    total = 0
    for line in lines:
        total += len(line.text)
        if id(line) not in held:
            dropped[line.page] = dropped.get(line.page, 0) + len(line.text)
    return total, total - sum(dropped.values()), dropped


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
