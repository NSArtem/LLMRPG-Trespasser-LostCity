#!/usr/bin/env python3
"""T0.3 -- find the column gutter, then build lines inside each column.

**This runs before T0.2, not after.** The work order lists tier clustering
second and column separation third; that order cannot work. Lines are the input
to clustering, and a line cannot be formed correctly until the columns are
known: banding words by vertical position across a whole two-column page fuses
the left column with the right one.

On page 31 of *Lair of the Lamb*, grouping before splitting produces

    24 CRUSH HALLWAY Crossing the Hallway

from two headings that are 260 points apart, and drops keyed-area detection
from 58 hits to 24. Poppler makes the same mistake in its own ``<line>``
elements, which is why T0.1 reads words rather than lines.

Gutters are found from occupancy rather than assumed: a run of x positions that
no word covers, wide enough to be deliberate and near enough to the middle to be
a gutter rather than a margin. Single-column pages simply yield none.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bbox import BboxError, SOURCES  # noqa: E402
from pdfhtml import Page, Run, extract_document  # noqa: E402


# (size, family, bold, colour, italic) -- what the typesetter chose.
Style = tuple[float, str, bool, str, bool]


LINE_TOLERANCE = 0.5   # share of line height that still counts as the same line
GUTTER_BAND = (0.30, 0.70)  # a gutter lives in the middle of the page, not the margin
MIN_COLUMN_SHARE = 0.15     # both sides must carry real text to be columns
MIN_RUN_IN_HEADING = 3      # characters; shorter prefixes are dropped capitals
DROP_CAP_RATIO = 2.0        # a single glyph this much taller than body is an initial
RUN_IN_TERMINATORS = ":."   # punctuation a run-in heading closes with
RESUMPTION_WINDOW = 4       # points scanned past a quiet run for the next column
FOLIO_MARGIN = 0.12         # share of page height that is header/footer space
REGION_MIN_ROWS = 4         # consecutive rows that must agree before a boundary is real
REGION_MIN_GAP = 0.012      # share of page width; a smaller hole is word spacing
REGION_CLUSTER = 0.02       # share of page width; nearer midpoints are one boundary


@dataclass(frozen=True)
class Line:
    page: int
    column: int  # 0-based; -1 spans the gutter
    x: float
    y: float
    height: float
    text: str
    size: float = 0.0
    family: str = ""
    bold: bool = False
    color: str = "#000000"
    italic: bool = False
    run_in: bool = False  # a prefix split off a row that continues in body style

    @property
    def style(self) -> tuple[float, str, bool, str, bool]:
        """What the typesetter chose. Discrete, so no clustering is needed.

        **Italic is part of the choice.** Leaving it out made Doom's read-aloud
        text -- bold italic BookAntiqua -- indistinguishable from its bold
        BookAntiqua act titles, so every boxed paragraph following a keyed
        heading was promoted to a heading of its own.
        """
        return (self.size, self.family, self.bold, self.color, self.italic)

    @property
    def is_upper(self) -> bool:
        letters = [c for c in self.text if c.isalpha()]
        return bool(letters) and all(c.isupper() for c in letters)


def find_gutter(page: Page) -> float | None:
    """Return the x of the least-crossed vertical band near the page middle.

    Density, not emptiness. Requiring a *wholly* empty band fails on any page
    carrying one full-width element -- a banner heading, a rule, a wide table --
    because occupancy is projected over the whole page and a single crossing
    line fills the gutter. Counting how many words cross each x and taking the
    minimum survives that: a real gutter is crossed by a handful of headings
    while the text columns either side are crossed by hundreds of lines.

    **The widest quiet run is not the gutter.** A ragged right margin leaves a
    far wider quiet band than the gutter does. Page 21 of *Lair of the Lamb*
    runs quiet from x=320 to x=449 because its left column is short, while the
    real gutter is the ten points from 455 to 464; taking the widest run put the
    boundary at 385, so ``. Each bowl contains 4`` -- which reaches x=453 --
    straddled it, was filed as full-width, and was emitted before the heading
    that owns it. The number of sacrifices simply left the room.

    What distinguishes the gutter is what follows it: the next column starts at
    full density, whereas a ragged margin is followed by more ragged text. So
    candidates are scored by the density immediately to their right.

    **Width is a tie-break, never a filter.** A minimum gutter in points cannot
    be written down: *Lair of the Lamb* is 918 points wide with a 10-point
    gutter, while Шпиль Кетцаль is 722 wide with a **2**-point one. Any
    threshold that admits the second admits word spacing in the first, so the
    density test has to carry the discrimination on its own.
    """
    if len(page.words) < 20:
        return None
    width = int(page.width) or 1
    crossings = [0] * (width + 1)
    for word in page.words:
        for x in range(max(0, int(word.x)), min(width, int(word.right)) + 1):
            crossings[x] += 1

    low, high = int(width * GUTTER_BAND[0]), int(width * GUTTER_BAND[1])
    if high <= low:
        return None
    typical = sorted(c for c in crossings[low:high + 1])[len(range(low, high + 1)) // 2]
    if typical == 0:
        return None

    floor = min(crossings[low:high + 1])
    if floor > typical * 0.25:
        return None  # nothing in the middle is notably clearer than the rest

    runs: list[tuple[int, int]] = []
    run_start: int | None = None
    for x in range(low, high + 2):
        quiet = x <= high and crossings[x] <= floor
        if quiet:
            run_start = x if run_start is None else run_start
        elif run_start is not None:
            runs.append((run_start, x - run_start))
            run_start = None
    if not runs:
        return None

    def resumption(start: int, size: int) -> int:
        """Density at the run's right edge -- where the next column begins.

        The window is deliberately a few points wide. Widen it and it reaches
        across a ragged margin into the real column beyond, which is exactly
        the confusion it exists to resolve.
        """
        after = crossings[start + size:start + size + RESUMPTION_WINDOW]
        return max(after) if after else 0

    # Deterministic: score, then width, then leftmost.
    best_start, best_size = max(
        runs, key=lambda run: (resumption(*run), run[1], -run[0])
    )
    centre = best_start + best_size / 2
    left = sum(1 for w in page.words if w.right <= centre)
    right = sum(1 for w in page.words if w.x >= centre)
    total = len(page.words)
    if min(left, right) < total * MIN_COLUMN_SHARE:
        return None  # a wide gap, but everything is on one side of it
    return centre


def column_of(word: Run, gutter: float | None) -> int:
    if gutter is None:
        return 0
    if word.right <= gutter:
        return 0
    if word.x >= gutter:
        return 1
    return -1  # spans the gutter: a full-width heading or rule


def _detection_rows(page: Page) -> list[list[Run]]:
    """Words banded by vertical position across the whole page width.

    Deliberately cruder than ``_band``: this only has to be right enough to see
    where rows agree on leaving a hole. ``_band`` does the real work afterwards,
    inside each column, where drop caps and run-in headings are handled.
    """
    heights = sorted(word.height for word in page.words)
    typical = heights[len(heights) // 2] if heights else 1.0
    rows: list[list[Run]] = []
    for word in sorted(page.words, key=lambda w: (w.y, w.x)):
        if rows and abs(word.y - min(w.y for w in rows[-1])) <= typical * 0.5:
            rows[-1].append(word)
        else:
            rows.append([word])
    return rows


def _boundary_candidates(page: Page, rows: list[list[Run]]) -> list[float]:
    """Where rows agree on a hole too wide to be word spacing.

    Holes are clustered before they are tested. Untested, one gutter offers a
    slightly different hole from every row that shows it, and each survives
    support on its own -- so a two-column region was cut five or six times and
    arrived shredded.

    **A cluster is reduced by intersection, not by averaging.** Averaging puts
    the boundary at the mean of the holes, which sits left of the true gutter
    wherever a column is ragged. On page 4 of *Doom of the Savage Kings* that
    landed it at 448.6 while one justified line reached 449.0, so that line
    counted as crossing, broke the run of agreeing rows, and left the page's
    first two rows braided. The intersection cannot cross any row that supports
    it, which is the property actually wanted.
    """
    holes: list[tuple[float, float]] = []
    for row in rows:
        ordered = sorted(row, key=lambda word: word.x)
        reach = ordered[0].right
        for word in ordered[1:]:
            if word.x - reach > page.width * REGION_MIN_GAP:
                holes.append((reach, word.x))
            reach = max(reach, word.right)

    clusters: list[list[tuple[float, float]]] = []
    for hole in sorted(holes, key=lambda item: (item[0] + item[1]) / 2):
        centre = (hole[0] + hole[1]) / 2
        if clusters:
            previous = clusters[-1][-1]
            if centre - (previous[0] + previous[1]) / 2 <= page.width * REGION_CLUSTER:
                clusters[-1].append(hole)
                continue
        clusters.append([hole])

    candidates = []
    for cluster in clusters:
        low, high = max(item[0] for item in cluster), min(item[1] for item in cluster)
        if low < high:
            candidates.append((low + high) / 2)
        else:
            centres = sorted((item[0] + item[1]) / 2 for item in cluster)
            candidates.append(centres[len(centres) // 2])
    return candidates


def _supported_rows(rows: list[list[Run]], x: float) -> list[tuple[int, int]]:
    """Maximal row intervals over which ``x`` is a real boundary.

    A row whose word crosses ``x`` ends the interval. A row carrying text on
    both sides votes for it. A row lying wholly on one side does neither: the
    short last line of a paragraph must not end its own column.
    """
    intervals: list[tuple[int, int]] = []
    start: int | None = None
    votes = 0
    for index, row in enumerate(rows):
        if any(word.x < x < word.right for word in row):
            if start is not None and votes >= REGION_MIN_ROWS:
                intervals.append((start, index - 1))
            start, votes = None, 0
            continue
        if start is None:
            start = index
        if (any(word.right <= x for word in row)
                and any(word.x >= x for word in row)):
            votes += 1
    if start is not None and votes >= REGION_MIN_ROWS:
        intervals.append((start, len(rows) - 1))
    return intervals


def region_lines(page: Page, body: Style | None) -> list[Line]:
    """Lines for a page whose columns hold over part of it, not all of it.

    ``find_gutter`` asks one question of the whole page, and a page that stacks
    layouts has no answer to give. Page 65 of Шпиль Кетцаль sets two rooms side
    by side above a full-width table of berry effects; the table crosses the
    middle on twenty-five rows, so the middle is genuinely no clearer than the
    rest and detection correctly declines. Every row was then assembled across
    the full width, and two rooms' prose came out braided line by line:

        ся друг о друга, нарушая тишину обширного  Пол пещеры устилает несметное

    **Text retention cannot see this.** Not one character is lost; they arrive
    interleaved. It took reading the lines to find it.

    So support is counted over a *run of consecutive rows* rather than over the
    page, letting a boundary hold for part of a page and lapse for the rest. One
    run may hold several boundaries at once, which is what the three-column
    rumour table on page 4 of *Doom of the Savage Kings* is -- and what a single
    gutter could never express.
    """
    rows = _detection_rows(page)
    per_row: list[list[float]] = [[] for _ in rows]
    for x in _boundary_candidates(page, rows):
        for first, last in _supported_rows(rows, x):
            for index in range(first, last + 1):
                per_row[index].append(x)
    per_row = [sorted(set(edges)) for edges in per_row]
    if not any(per_row):
        return []

    lines: list[Line] = []
    index = 0
    while index < len(rows):
        edges = per_row[index]
        stop = index
        while stop + 1 < len(rows) and per_row[stop + 1] == edges:
            stop += 1
        words = [word for row in rows[index:stop + 1] for word in row]
        # A region with no boundary is full width, which is what -1 has always
        # meant, so `join_wrapped_headings` keeps matching across such a run.
        cuts = [-float("inf"), *edges, float("inf")]
        for column, (low, high) in enumerate(zip(cuts, cuts[1:])):
            bucket = [w for w in words if low <= (w.x + w.right) / 2 < high]
            if bucket:
                lines.extend(_band(bucket, page.number,
                                   -1 if not edges else column, body))
        index = stop + 1
    return lines


def is_drop_cap(run: Run, body: Style | None) -> bool:
    """One oversized glyph opening a paragraph.

    Its height describes the glyph, not the row it sits in. Doom of the Savage
    Kings opens each section with a 72pt initial 85pt tall, across three 18pt
    body lines. Letting that height set the row's vertical tolerance swallowed
    the section heading above it and the first two body lines below it into one
    row, in body style -- so ``Introduction`` and ``The Village of Hirot``
    stopped being headings, no heading was left on either page, and 10,509
    characters fell through ``assemble``'s front-matter branch.
    """
    return (body is not None
            and len(run.text.strip()) <= 1
            and run.height > body[0] * DROP_CAP_RATIO)


def _row_span(row: list[Run], word: Run, body: Style | None) -> float:
    """How far from a row's top ``word`` may sit and still join it.

    Measured over the runs that set type on the row, so an initial cannot widen
    the row's reach and pull in the heading above it.
    """
    ordinary = [run.height for run in row if not is_drop_cap(run, body)]
    if not ordinary:
        # The row *is* a dropped capital. Its height is exactly what attaches
        # the paragraph it opens, so here it is the right measure.
        return max(run.height for run in row)
    if not is_drop_cap(word, body):
        ordinary.append(word.height)
    return max(ordinary)


def _band(words: list[Run], page: int, column: int,
          body: Style | None) -> list[Line]:
    rows: list[list[Run]] = []
    for word in sorted(words, key=lambda w: (w.y, w.x)):
        if rows:
            row = rows[-1]
            top = min(w.y for w in row)
            span = _row_span(row, word, body)
            if abs(word.y - top) <= span * LINE_TOLERANCE:
                row.append(word)
                continue
        rows.append([word])

    lines = []
    for row in rows:
        ordered = sorted(row, key=lambda w: w.x)
        parts = _split_run_in_heading(ordered, body)
        for index, part in enumerate(parts):
            # Only the prefix of a split row is a run-in candidate; the tail is
            # ordinary body text that happens to share the row.
            lines.append(_line(part, page, column,
                               run_in=len(parts) > 1 and index == 0))
    return lines


def run_style(run: Run) -> Style:
    # Italic last: `tiers` and Contract A read this tuple positionally.
    return (run.size, run.font.family, run.bold, run.color, run.italic)


def _line(runs: list[Run], page: int, column: int, run_in: bool = False) -> Line:
    # A line's style is its dominant run's, weighted by how much text that run
    # carries -- a dropped capital must not redefine the line it opens.
    weight: Counter = Counter()
    for run in runs:
        weight[run_style(run)] += len(run.text)
    size, family, bold, color, italic = weight.most_common(1)[0][0]
    heights = Counter(round(run.height, 1) for run in runs)
    return Line(
        page=page,
        column=column,
        x=min(run.x for run in runs),
        y=min(run.y for run in runs),
        height=heights.most_common(1)[0][0],
        text=" ".join(run.text for run in runs).strip(),
        size=size,
        family=family,
        bold=bold,
        color=color,
        italic=italic,
        run_in=run_in,
    )


def _split_run_in_heading(
    ordered: list[Run], body: Style | None
) -> list[list[Run]]:
    """Split a row where a **run-in heading** is followed by body text.

    Doom of the Savage Kings and The Lost City set headings inline:

        Area A-4 - Chapel of Justicia: The chapel is a low, vaulted...
        |--- CooperBlack bold ------||------- BookAntiqua body -----|

    That is one typographic row, so a line carrying a single dominant style
    takes the body's -- the heading is outvoted by the prose beside it, and
    reads as an eleven-word line that no length test will accept. Both
    documents collapsed to a handful of units because of it.

    The signal is positional rather than metric: a row that *opens* in a
    non-body style and *switches out of it* has a heading prefix. Splitting
    there lets a unit boundary fall mid-row, which is what these layouts need.

    **The switch is out of the heading's style, not always into the document's
    body style.** Doom sets the read-aloud text after a keyed heading in bold
    italic, so requiring the tail to match body exactly left three areas -- C-7,
    C-10 and D-1, the last of them the adventure's climax -- glued to their
    prose and rejected as eleven-word headings, then absorbed into the area
    above.

    A switch into a style that is not body is only a heading boundary when the
    prefix *closes* like a run-in heading. Шпиль Кетцаль sets its stat lines
    entirely in non-body styles -- ``Телосложение 3, ловкость 2 НАВЫКИ:
    скрытность 2`` changes style mid-row with no heading anywhere in sight --
    and cutting on the style change alone promoted fifteen attribute lines to
    units.
    """
    if body is None or len(ordered) < 2:
        return [ordered]
    opening = run_style(ordered[0])
    if opening == body:
        return [ordered]
    cut = next(
        (index for index, run in enumerate(ordered) if run_style(run) != opening), None
    )
    if cut is None or cut == 0:
        return [ordered]
    if run_style(ordered[cut]) != body:
        closer = "".join(run.text for run in ordered[:cut]).strip()[-1:]
        if closer not in RUN_IN_TERMINATORS:
            return [ordered]
    prefix = "".join(run.text for run in ordered[:cut]).strip()
    if len(prefix) < MIN_RUN_IN_HEADING:
        # A **dropped capital** matches this shape exactly -- one oversized
        # glyph in its own style, opening a paragraph of body text. Splitting
        # there would make the capital a heading and orphan the paragraph.
        return [ordered]
    return [ordered[:cut], ordered[cut:]]


def body_run_style(pages: Sequence[Page]) -> Style | None:
    """The style carrying the most characters across the document."""
    weight: Counter = Counter()
    for page in pages:
        for run in page.words:
            weight[run_style(run)] += len(run.text)
    return weight.most_common(1)[0][0] if weight else None


def is_folio(line: Line, height: float) -> bool:
    """A bare page number in the header or footer band.

    ``furniture`` in ``units`` cannot catch these: it keys on repeated text and
    every folio is different. Left alone they are appended as body to whichever
    unit happens to be open, which is how ``the Ghouls`` ended up with a body of
    ``27\\n28``.

    Both conditions are required. Digits alone would eat a table row keyed only
    by its die number; the margin band alone would eat a real heading that
    starts high on the page.
    """
    if not height:
        return False
    text = line.text.strip()
    if not text or not text.isdigit():
        return False
    return line.y < height * FOLIO_MARGIN or line.y > height * (1 - FOLIO_MARGIN)


def page_lines(
    page: Page, body: Style | None = None
) -> list[Line]:
    """Lines in reading order: spanning content, then each column top to bottom.

    A page-wide gutter is tried first and always wins where it is found. The
    real gutters are narrow -- Шпиль Кетцаль's median is four points on a
    698-point page -- and ``find_gutter`` reads them from the crossing profile,
    far below the hole width ``region_lines`` needs to see a boundary at all. So
    the region model is a fallback for pages the page-wide question cannot
    answer, never a replacement: on the 151 pages where a gutter is found, this
    function behaves exactly as it did before.
    """
    if not page.words:
        return []
    if body is None:
        body = body_run_style([page])
    gutter = find_gutter(page)
    if gutter is None:
        regional = region_lines(page, body)
        if regional:
            return [line for line in regional
                    if not is_folio(line, page.height)]
    buckets: dict[int, list[Run]] = {}
    for word in page.words:
        buckets.setdefault(column_of(word, gutter), []).append(word)

    lines: list[Line] = []
    for column in sorted(buckets, key=lambda c: (c != -1, c)):
        lines.extend(_band(buckets[column], page.number, column, body))
    lines = [line for line in lines if not is_folio(line, page.height)]

    # A full-width line divides the page; it does not precede all of it. Emitting
    # every spanning line first put both of Winter's Daughter p13's centred
    # headings ahead of the columns, so `3. Tomb Entrance` came out empty and its
    # granite slab was filed under `4. Worm Hole`. Each spanning line opens a
    # section, and the columns under it belong to that section.
    spanning = sorted(line.y for line in lines if line.column == -1)
    return sorted(lines, key=lambda line: (
        sum(1 for y in spanning if y <= line.y), line.column, line.y))


def document_lines(pdf: Path) -> list[Line]:
    document = extract_document(pdf)
    # Body style is a whole-document fact: a single page may be all heading.
    body = body_run_style(document.pages)
    return [line for page in document.pages for line in page_lines(page, body)]


def report(pdf: Path) -> None:
    document = extract_document(pdf)
    gutters = [find_gutter(page) for page in document.pages if page.words]
    two = sum(1 for g in gutters if g is not None)
    values = [round(g) for g in gutters if g is not None]
    common = Counter(values).most_common(3)
    print(f"{pdf.name[:40]:<40} {two:>3}/{len(gutters):<3} two-column   "
          f"gutter x: {common if common else '-'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", nargs="*", type=Path)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--page", type=int, help="print one page's lines")
    args = parser.parse_args(argv)
    targets = list(SOURCES) if args.all else args.pdf
    if not targets:
        parser.error("give at least one PDF, or --all")

    for pdf in targets:
        try:
            if args.page is not None:
                document = extract_document(pdf)
                page = document.pages[args.page - 1]
                print(f"# {pdf.name} p{args.page}  gutter={find_gutter(page)}")
                for line in page_lines(page):
                    print(f"  c{line.column} x={line.x:6.1f} h={line.height:5.1f}  {line.text[:78]}")
            else:
                report(pdf)
        except BboxError as exc:
            print(f"{pdf.name}: ERROR {exc}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
