# Implementation report: architecture-new-plan

This report records work performed against
[architecture-new-plan.md](architecture-new-plan.md), in task order. It
distinguishes implementation evidence from the plan's human-review gates.

## Status at handoff

T0.1–T0.4 have committed prototype implementations and automated tests. T0.5
has generated all five in-scope review tables, but its boundary review is still
pending. T1.1 is implemented below. T1.2 is a required manual model exchange;
the work stops there until a response is supplied.

Sections marked **corrected after review** record defects found by reading this
work back against the sources, and what was done about them.

## Phase 0 — Segmentation

### T0.1 — Bounding-box extraction

Implemented in `module-extractor/scratch/bbox.py` using Poppler
`pdftotext -bbox-layout` and `xml.etree.ElementTree`. The parser reports
word-level geometry, page counts, empty pages, and removed XML control
characters. `module-extractor/scratch/test_bbox.py` covers malformed XML,
missing coordinates, empty words/pages, and control-character sanitization.

Measured on the five in-scope PDFs:

| Source | Pages | Words | Empty pages | XML controls removed |
| --- | ---: | ---: | --- | ---: |
| Lair of the Lamb | 54 | 19,053 | — | 0 |
| Winter's Daughter | 31 | 8,470 | 2 | 29 |
| Falkrest Abbey | 46 | 9,402 | 2, 4 | 0 |
| Doom of the Savage Kings | 18 | 11,844 | 1, 18 | 0 |
| Запретные Земли — Шпиль Кетцаль | 74 | 22,175 | 1 | 0 |

The deferred Lost City scan was not included in the in-scope run.

### T0.2 — Line-height/style clustering

Implemented first as per-document height tiers, then improved in the existing
scratch prototype to use Poppler's typed runs from `pdftohtml -xml` where the
font table provides a stronger structural signal. `module-extractor/scratch/
tiers.py` reports per-document styles and identifies the body style from text
weight; `test_pdfhtml.py` covers the typed-run parser.

The current prototype confirms that thresholds are document-derived. Lair's
typed-run report includes the expected 16pt body, 18pt keyed-area, 21pt section,
and 30pt title styles; the other sources use different families/sizes.

### T0.3 — Column separation

Implemented in `module-extractor/scratch/columns.py`. It finds a gutter from
word occupancy, assigns words to columns, reconstructs lines, and handles
run-in headings. `test_columns.py` covers single-column pages, gutters,
full-width content, line grouping, and heading-prefix splits.

**Corrected after review.** `find_gutter` took the *widest* quiet band in the
page's middle third, which is a ragged right margin far more often than it is
the gutter. On page 21 of Lair it put the boundary at x=385 while the real
gutter is x≈459, so the run `. Each bowl contains 4` straddled it, was filed as
full-width, and was emitted ahead of the heading that owns it — the number of
sacrifices in room 1 left the room. Candidates are now scored by the density
immediately to their right, because a real gutter is followed by the next
column at full density and a ragged margin is not. Width is a tie-break and
never a filter: Lair is 918pt wide with a 10pt gutter, Шпиль Кетцаль 722pt with
a **2pt** one, and no absolute minimum admits the second without admitting word
spacing in the first.

Page folios are also dropped now. A bare page number in the outer 12% of a page
never repeats, so `furniture` cannot see it, and it was being appended as body
to whichever unit happened to be open.

### T0.4 — Unit assembly

Implemented in `module-extractor/scratch/units.py`. It assembles Contract A
units, joins page continuations, absorbs subordinate keyed headings, preserves
unkeyed sibling sections, folds table-row runs into their host unit, and keeps
Cyrillic IDs distinct. `test_units.py` covers these boundaries and the page
citation invariant.

**Three corrections after review.**

*Run-in prefixes no longer open units unless they open a key.* The T0.3 split
that lets Doom's `Area A-4 - Chapel of Justicia:` start a unit mid-row is
typographic and indiscriminate, and Lair sets emphasis in the same shape. Every
prefix opened a unit, which shredded the stat blocks: the Lantern Worm on page
28 was 47 bytes holding one stat line, having lost its second and all three of
its abilities to units named `Crawl`, `Eat Light -`, `Lantern -` and
`Stonemeld -`. It is now one 656-byte unit matching the source.

*A heading that wraps is one heading.* Page 27 is a divider reading `Part 2 /
Gallery of / the Ghouls` in one 81pt style and produced three units of six to
sixteen bytes. Same-style neighbours in a column now join, unless either opens a
key — otherwise a table keyed by die number would collapse into one heading.

*Units carry a `heading_path`.* Page 18 prints two encounter tables side by
side, each broken into `Active` / `Passive` / `Indirect Encounters` in one 21pt
style, so rank cannot nest them and `Active Encounters` reached the model with
no way to know whether the Lamb was alive or dead. Bodyless section titles now
travel in a new Contract A field. A same-rank title governs only its own page;
an earlier attempt without that limit leaked `Encounter Table (Lamb Dead)` onto
every keyed room for the next three pages.

`furniture` additionally requires a repeat to be positionally locked. Counting
pages alone deleted `Encounter Table (Lamb Alive)`, printed on three pages,
while leaving its `(Lamb Dead)` twin standing.

### T0.5 — Generalize and report

The requested review tables exist at `module-extractor/scratch/unit-tables/` for
all five in-scope sources. After the T0.3/T0.4 corrections above:

| Source | Units | Keyed | Under 40B |
| --- | ---: | ---: | ---: |
| Lair of the Lamb | 237 → **214** | 51 | 21 → **18** |
| Winter's Daughter | 128 → **115** | 42 | 26 → **20** |
| Falkrest Abbey | 68 → **80** | 34 → **35** | 10 → **18** |
| Doom of the Savage Kings | 72 → **33** | 23 | 3 → **2** |
| Шпиль Кетцаль | 281 → **280** | 82 → **77** | 34 → **25** |

No real keyed area was lost. Шпиль Кетцаль's five are d6 attack-table rows
(`1 РАЗРЫВАЮЩАЯ АТАКА`, `2 СМЕРТОНОСНЫЙ РЫВОК`) folding into their table, which
is what should happen to them.

**Falkrest moved the wrong way and the cause is known.** Its map pages label
features `Statue`, `Ghost`, `N`, `P`, `Rowayn` across five to nine pages at
scattered vertical positions. The old page-count furniture rule deleted them
silently; the positional rule keeps them, and page 3 alone now yields 14 short
label units. Keeping them is the safer direction — the dataflow document is
explicit that a false negative loses source material and nothing downstream can
detect it — but the right home for map labels is Stage 3 classification at T2.4,
not another segmentation heuristic.

Status: implementation artifact complete; **human boundary review pending**.
Stat-block internals still fragment on Lair page 20 (`Immunity – Acid.`,
`Spells - delay, haste, scry` become their own units); the text is present and
adjacent, so this is a boundary-quality question for the review gate rather than
a loss.

## Phase 1 — CSV contract

### T1.1 — Hand-assemble one pack

Implemented `module-extractor/scratch/phase1_pack.py`. It selects six real Lair
units and emits `README.md`, `prompt.md`, draft `schema.md`, `units.csv` and
verbatim unit files inside a deterministic `pack-001.zip`, also written to
`_exchange/pack-001.zip`. `test_phase1_pack.py` covers the manifest, the unit
files, the selection, the schema's declarations and the pack itself.

| Unit | Bytes | Covers |
| --- | ---: | --- |
| `p31.24-crush-hallway` | 1631 | keyed room, trap, sub-areas, crossing procedure |
| `p33.27-ballista` | 1361 | keyed room, two actors, embedded stat block |
| `p28.lantern-worm` | 656 | standalone monster stat block |
| `p18.active-encounters-2` | 200 | random encounter table |
| `p8.doors` | 1126 | rules section |
| `p46.haste` | 248 | spell |

**The first selection was rebuilt after review.** It was drawn from unit tables
that predate the T0.3/T0.4 corrections, and three of its six probes were
damaged: `p21.1-bowls` was missing the clause `Each bowl contains 4`,
`p28.lantern-worm` was 47 bytes of a stat block, and `p18.active-encounters-2`
carried no indication which of the page's two identically-headed tables it came
from. T1.3 is supposed to separate a format failure from a compliant answer;
on mutilated units it cannot separate either from a unit with nothing to say.
Every unit above was re-checked line by line against the PDF.

Four further corrections to the pack itself:

- **`units.csv` had its columns transposed.** The header read
  `unit_id,heading,pages,labels,text_bytes`, the rows were written
  `unit_id,heading,labels,pages,text_bytes`, and `labels` is empty until T2.4 —
  so the model was handed an empty `pages` column and each unit's page numbers
  filed under `labels`, in a pack whose prompt requires it to emit
  `#unit,<id>,pages,<page-list>`. The manifest now puts free text last and is
  read with `split(",", 4)`, mirroring the wire contract, so a comma in a
  heading needs no quoting.
- **The prompt now carries a worked example**, on `p24.11-crab-mural` — a real
  unit deliberately *not* in the pack. Shipping the finished answer to one of
  the pack's own units would measure copying rather than compliance.
- **`schema.md` drops `hidden` as a predicate.** Visibility is column three and
  nothing else, so the two can never disagree; `option` and `result` likewise go,
  being `#option` slots rather than predicates. Every predicate now declares
  scalar-or-list and text-or-JSON, and all four structured predicates declare
  their key set, per Contract D items 2 and 3. The draft vocabulary is closed
  **for the prototype only** — an open vocabulary has nothing to violate, and
  T1.3 exists to count violations. D-4/D-5/D-6 stay open for T1.4.
- **Unit files no longer open header lines with `#`**, which is the structural
  row marker of the format being taught, and no longer leak a draft
  classification label that Stage 5 is not asked to agree with. They carry the
  unit's `heading_path` as a `section:` line instead.

### T1.2 — Exchange

Blocked at the required H-1 manual handoff. The pack must be supplied to a chat
model and the returned CSV saved as `_exchange/pack-001.csv`. No model response
has been invented or substituted.

## Verification

- `python3 -m unittest discover -s module-extractor/tests` — 115 tests, 1
  skipped, green.
- `python3 -m unittest discover -s module-extractor/scratch -p 'test_*.py'` —
  104 tests, green (70 before this round).
- `python3 scripts/validate_repo.py` — 0 errors, 0 warnings.
- `git diff --check` — clean.

The next action is to complete H-1 with at least the required model response;
then T1.3 can measure compliance and the implementation can continue in order.
T0.5's boundary review is still open and does not block H-1, but it should be
read before Phase 2 promotes `segmentation.py` into the package.
