# Implementation report: architecture-new-plan

This report records work performed against
[architecture-new-plan.md](architecture-new-plan.md), in task order. It
distinguishes implementation evidence from the plan's human-review gates.

## Status at handoff

T0.1–T0.4 have committed prototype implementations and automated tests. T0.5
has generated all four in-scope review tables, but its boundary review is still
pending. T1.1 is implemented below. T1.2 is a required manual model exchange;
the work stops there until a response is supplied.

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

### T0.4 — Unit assembly

Implemented in `module-extractor/scratch/units.py`. It assembles Contract A
units, joins page continuations, absorbs subordinate keyed headings, preserves
unkeyed sibling sections, folds table-row runs into their host unit, and keeps
Cyrillic IDs distinct. `test_units.py` covers these boundaries and the page
citation invariant.

### T0.5 — Generalize and report

The requested review tables exist at
`module-extractor/scratch/unit-tables/` for all five source files named by the
original Phase 0 task. The current real-input run produces 237, 128, 68, 72,
and 281 units respectively for Lair, Winter's Daughter, Falkrest, Doom, and
Шпиль Кетцаль. Their keyed-unit counts are 51, 42, 34, 23, and 82 under the
prototype's strict key signal; numeric/lettered keyed ranges have no reported
gaps.

Status: implementation artifact complete; **human boundary review pending**.
The tables still surface suspiciously small and large units, so this report
does not claim the review gate passed.

## Phase 1 — CSV contract

### T1.1 — Hand-assemble one pack

Implemented `module-extractor/scratch/phase1_pack.py`. It selects six real
Lair units covering a keyed room, an adventure/stat-block entry, a monster stat
block, a random encounter table, a rules section, and a spell. The builder emits
`README.md`, `prompt.md`, draft `schema.md`, `units.csv`, and verbatim unit files
inside a deterministic `pack-001.zip`.

Build and determinism check:

```text
python3 module-extractor/scratch/phase1_pack.py --output /tmp/pack-001-a.zip
python3 module-extractor/scratch/phase1_pack.py --output /tmp/pack-001-b.zip
cmp /tmp/pack-001-a.zip /tmp/pack-001-b.zip
```

The pack is also emitted to `_exchange/pack-001.zip` by default. The schema is
explicitly marked draft; T1.3/T1.4 must measure and decide before it becomes
the production contract.

### T1.2 — Exchange

Blocked at the required H-1 manual handoff. The pack must be supplied to a chat
model and the returned CSV saved as `_exchange/pack-001.csv`. No model response
has been invented or substituted.

## Verification

Before this report was updated:

- `python3 -m unittest discover -s module-extractor/tests` — 115 tests, 1
  skipped, green.
- `python3 scripts/validate_repo.py` — 0 errors, 0 warnings.

The next action is to complete H-1 with at least the required model response;
then T1.3 can measure compliance and the implementation can continue in order.
