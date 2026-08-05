# Implementation work order: the unit/fact pipeline

**Status:** work order. This document is written to be executed, one task at a
time, by an implementer who has not been part of the design discussion.

**Three documents, three jobs:**

| Document | Authority over |
|---|---|
| [architecture-new-dataflow.md](architecture-new-dataflow.md) | **What the pipeline must do.** The specification. Never edit it to make an implementation easier. |
| [architecture-new-plan.md](architecture-new-plan.md) | **Why the work is sequenced this way**, what each phase risks, what survives and what is deleted. Read it once before starting. |
| this document | **What to do next**, in what order, and how to know a task is finished. |

Where this document and the dataflow document disagree, the dataflow document
wins and this one is wrong — report it rather than following it.

---

## Operating rules

1. **One task per commit.** Tasks are numbered `T<phase>.<n>`. Do not bundle.
2. **Do not skip a gate.** Phase gates are listed in `architecture-new-plan.md`.
   A failed gate stops the phase; it is not a thing to work around.
3. **Never edit `architecture-new-dataflow.md`.**
4. **Never invent source material.** Every fact in the pipeline traces to a
   physical page of a real PDF. If a task seems to require making something up,
   the task is wrong.
5. **Determinism is not optional.** Any stage after extraction must produce
   byte-identical output for identical input. If you add a dict iteration, a
   `set()`, or a timestamp to an output path, sort it or remove it.
6. **When blocked, stop and report.** Do not stub, do not fake a PDF, do not
   write a placeholder response file and proceed. Blocked tasks are listed under
   [Human handoffs](#human-handoffs); they are expected, not failures.
7. **Report honestly.** If a gate half-passes, say which half.
8. **Cite code by symbol, never by line number.** Write
   `identity._default_base`, not `identity.py:446`. A line number is correct
   until the first edit above it and silently wrong afterwards — a human
   re-finds the code, an implementer following literally edits the wrong line.
   For Markdown and config that have no symbols, quote a greppable string
   (`grep -rn 'module-play/v1'`) rather than a position.

### Gate types

Every task ends in a **Done when** clause of one of two kinds. The distinction is
binding: an implementer may close the first kind on its own and **may never close
the second**.

- `*Done when:*` — **automatic.** A command, an exit code, or a test. Run it; if
  it passes, the task is done.
- `*Done when (review):*` — **human sign-off.** The task produces a named
  artefact at a named path and then **stops**. Judgment about whether the work is
  good is not the implementer's to make. These are enumerated under
  [Human handoffs](#human-handoffs).

Writing a decision into a document is never self-certifying. If a task asks you
to *decide* something, it is a review gate even when the mechanical part
(the file exists, the table is complete) is checkable.

### Verification commands

Automatic gates are expressed in these terms.

```bash
# Extractor unit tests — must be green except where a task says otherwise
python3 -m unittest discover -s module-extractor/tests

# Repository structure and campaign invariants — must stay at zero errors
python3 scripts/validate_repo.py

# Whitespace hygiene
git diff --check
```

---

## Environment

**These paths are stable and may be hardcoded in scripts and tests.**

```text
/mnt/data/RPG/Module - Lair of the Lamb.pdf            54 pages   primary source
/mnt/data/RPG/Module - Winters Daughter.pdf            31 pages
/mnt/data/RPG/Module - Falkrest_Abbey_1.1.pdf          46 pages
/mnt/data/RPG/[M] 66.5 Doom of the Savage Kings.pdf    18 pages
/mnt/data/RPG/Запретные Земли - Шпиль Кетцаль.pdf      74 pages   Russian
/mnt/data/RPG/TSR B4 - The Lost City 1982.pdf          34 pages   DEFERRED, see below
```

**Keep the Russian source in every run.** It is the only one that exercises
non-ASCII text, and it has already caught two defects that the five English
sources could not: an ASCII-only slug pattern that erased every Cyrillic
heading, and an unescaped ampersand in a font name that broke the XML parse.
**Canonical IDs downstream are ASCII-only** -- `util.SAFE_ID` rejects
`place.module-x.авторы` -- so T4.3 must decide between transliteration and
widening the pattern. Do not discover that in Phase 4.

*Lair of the Lamb* is the primary source: it is the one with a recovered
baseline build to compare against, and every gate that names a source without
qualification means this one.

**Four of the five are in scope. *The Lost City* is deferred** -- it has a text
layer, but not a usable one. See [Deferred: scanned sources](#deferred-scanned-sources).
Gates that say "all five sources" mean the four in scope; do not spend effort
making Lost City pass.

The PDFs are **read-only inputs and must never be copied into the repository** —
`/*.pdf` is gitignored. Derived artefacts (extracted text, bounding-box XML, page
renders, thumbnails) are fine to commit; the repository is private.

**Tooling.** Python standard library only, plus the Poppler binaries already used
via `subprocess`: `pdfinfo`, `pdftotext`, `pdftoppm`, and — added at T2.1 —
`pdftohtml`. There is no `requirements.txt` and none is to be added. **Do not
introduce PyMuPDF, pdfplumber, PyPDF2, lxml, PyYAML, or any other third-party
package.**

The capability the pipeline gained is `pdftohtml -xml`, which emits typed text
runs and is parsed with `xml.etree.ElementTree`:

```xml
<fontspec id="0" size="18" family="CIDFont+F10" color="#3333ff"/>
<text top="504" left="65" width="182" height="22" font="0">24 CRUSH HALLWAY</text>
<text top="52"  left="93" width="311" height="23" font="1"><b>roleplAyIng the non-</b></text>
```

A `<text>` element is a **run**: contiguous characters sharing one font. Runs
split mid-line whenever the font changes and never span a column, so they are a
strictly better unit than words.

**An earlier revision of this section named `pdftotext -bbox-layout`.** That
tool gives a box per word and nothing else, leaving glyph height as the only
typographic signal — a lossy proxy for point size, with family, weight and
colour discarded. Lair sets keyed areas and subsection headings at the same
18pt and separates them **by colour**; Doom separates headings by family and
weight, and under glyph height 96.8% of its lines looked identical. Two of the
five in-scope sources could not be segmented from bounding boxes. T0.2 switched
to `pdftohtml` and T2.1 followed; `scratch/bbox.py` survives only as the source
list and error type.

Poppler's XML is **not well-formed** and every consumer must expect that:
unescaped ampersands inside font names (`TURLCX+Brokgauz&Efron`), unbalanced
inline tags inside runs where a link overlaps an emphasis span, and C0 control
characters copied straight out of the PDF. `scratch/pdfhtml.py` carries the
repairs; T2.3 promotes them.

---

## Deferred: scanned sources

**Out of scope. Do not work on them. Revisit deliberately, not by accident.**

Two sources are deferred, and they fail the same way for the same underlying
reason: **they are scans, and the segmenter depends on a sane font table.**

### Curse of Strahd — the clearest case

258 pages, 40 MB, `Producer: EPSON Scan`. It has a text layer -- 779 KB of it,
32,020 runs -- so nothing about it looks broken. It yields **zero units**.

The cause is the OCR font table. It declares **12,151 fonts**: `Times New
Roman-271`, `-272`, one synthetic face per recognised fragment. Colour is
equally poisoned, a slightly different near-black per fragment -- `#1d1a1d`,
`#201d20`, `#151214`, `#1f1c20`. After normalising font names, **9,317 distinct
style keys remain across 32,020 runs**. Every style falls below the noise floor,
none is accepted as a heading, and nothing segments.

Style-based segmentation assumes the typesetter chose a small number of styles
deliberately. An OCR engine chooses one per fragment, accidentally. The
assumption simply does not hold on scans.

### It failed silently, which is the real defect

Zero units, exit 0, no diagnostic. **Stage 1's no-text-layer check (T2.2) is
necessary but not sufficient**: this document has plenty of text. The check must
widen to *text present but structurally unusable*, and the ratio of distinct
style keys to runs is a direct, cheap measure of it -- roughly 1:3 here against
roughly 1:200 on a typeset source. Fail loudly, name the cause, and say the
source needs the image path.

### The Lost City -- the same class, seen earlier

*TSR B4 - The Lost City (1982)*

**Out of scope. Do not work on it. Revisit deliberately, not by accident.**

is a 1982 scan with a bad embedded
text layer. Two causes, both found in T0.3:

**Its styles do not discriminate.** The `14pt Times bold` style carries both
headings and body prose -- `DM's Background` and `9. ABANDONED PRIEST'S
QUARTERS` sit in the same style as `Goblin. Goblins are described in both
editions of the D&D Basic`. No style rule separates those, so the document
yields 4 units for 34 pages.

**Its text layer is pervasively damaged**, in body text and not only headings:

```text
C e ntip e d e , G ia nt. G ia n t c en tip ed es   a re   d es c rib
```

That is the deeper problem. Segmenting the document perfectly would still hand
the model garbled prose, so this is a **Stage 1 text-quality problem, not a
Stage 2 segmentation one**. A bad embedded text layer is worse than none,
because it looks usable.

**No prior run contradicts this.** Lost City was never extracted -- the
`lost-city` branch is a hand-written, module-free campaign with no `module/` or
`module-input/` at all. Only Lair of the Lamb and Winter's Daughter were ever
built.

### Three options, when it is picked up again

1. **OCR at Stage 1.** The dataflow document already reserves the slot: "OCR, if
   added later, sits here as a preprocessing step and produces the same page
   text contract." Most faithful, and the largest piece of work.
2. **Ship the page image with damaged units.** *The old pipeline did this and
   the new design dropped it.* `packs.py` attached `thumbnails/page-NNNN.png` to
   every content pack, so the model always had a second channel and could read
   what the text layer mangled. The new Stage 4 sends images "only where a unit
   needs visual context", and packs are per unit rather than per page, so the
   fallback is no longer automatic. Damage is detectable without a model -- a
   high ratio of one- and two-character tokens is what letter-spacing looks
   like. Cheapest of the three, but it widens Stage 4's contract.
3. **Fail Stage 1 loudly** with a diagnostic naming the damage, and support only
   documents with a clean text layer.

Option 2 is the one to cost first if pre-2000 scans matter long term.

## Glossary

The dataflow document and the existing code use overlapping words for different
things. These meanings are binding.

| Term | Meaning |
|---|---|
| **unit** | A source-native span the author wrote as one thing: a keyed area, a stat block, a table, a rules section. The pipeline's semantic unit of work. Produced by Stage 2. Not a page. |
| **pack** | A transport batch of many units sent to the model in one interaction. Disposable. Has no meaning after its response is ingested. |
| **fact** | One CSV row: subject, predicate, visibility, value. The atom the model produces. |
| **entity** | A thing a unit declares (`#entity,a24,place,24 CRUSH HALLWAY`). Facts attach to entities. Scoped to its unit until Stage 7. |
| **local ID** | An entity's short unit-scoped name (`a24`, `ceil`). Never leaves Stage 6. |
| **concept ID** | An entity's module-scoped identifier after local-ID expansion. What reconciliation groups on. |
| **canonical ID** | The final identifier after Stage 7 (`place.module-lair-of-the-lamb.24-crush-hallway`). |
| **entity observation** | One entity's facts as asserted by one unit, with provenance. The durable fact-store row and **the seam** between the new front end and the preserved back end. Contract C. |
| **value observation** | One `(predicate, value)` assertion inside an entity observation, carrying the unit, pages, and pack it came from. What `reconcile_records` retains as `field_observations`. |
| **record** | A reconciled entity: all value observations merged, conflicts surfaced. Stage 8 output. |
| **card** | A rendered Markdown file under `module/cards/`. Stage 11 output. |
| **concern** | What a classifier says a unit contains (`adventure`, `rules`, `tables`…). Replaces the old page-level *task*. |

**Two collisions to keep straight.**

*Record.* The old code calls the model's JSON output a *record*, and
`reconcile_records` operates on those. Under the new design the model produces
*facts* and code produces *records*; the bare word is reserved for the Stage 8+
meaning. The plan document qualifies its old-schema uses explicitly
("record JSON", "record-shape validators") — read those as historical.

*Observation.* **The dataflow document uses "observation" at the value level**:
*"Where every observation agrees, the fact is settled… All observations are
retained alongside the merged result, each with its unit, pages, and originating
pack."* That is a **value observation** in the table above. Contract C's object
is one level up — an **entity observation** containing many of them. Both are
real and both are stored; when the dataflow document says "observation", it means
the inner one. Use the qualified terms in code and commit messages, never the
bare word.

---

## Contracts

These are the interfaces tasks must implement. Fill in the unspecified parts
during the phase that owns them; do not improvise them earlier.

### Contract A — Unit (Stage 2 output)

Owned by Phase 0/2. One JSON object per unit, stored in document order.

```json
{
  "unit_id": "p21.area01",
  "heading": "1 BOWLS",
  "pages": [21],
  "column": "left",
  "text": "…verbatim unit text, columns un-interleaved…",
  "labels": ["adventure"],
  "text_bytes": 1180,
  "heading_height": 14.5
}
```

- `unit_id` is derived from first page and heading, stable across runs.
- `pages` lists every page the unit draws from, in order.
- `labels` is Stage 3 output and may be empty until Phase 2 T2.3.
- `text` must be the source text with columns separated, not `-layout` output.

### Contract B — CSV wire format (Stage 5)

Fully specified in the dataflow document under *The CSV contract*. Restated as
validation rules, in the order ingest must apply them:

1. Split each line on the **first three commas only**: `line.split(",", 3)`.
2. Exactly four fields, or reject the unit.
3. Lines beginning `#` are structural (`#unit`, `#entity`, `#option`,
   `#uncertain`); all others are facts.
4. Fields 1–3 must match the known vocabulary and **must not contain a comma**.
5. Field 4 is unparsed free text, or JSON when the predicate is declared
   structured in `schema.md`.
6. Every unit packed must appear exactly once, marked by `#unit`.
7. Every fact subject must resolve to an entity declared in the same unit.
8. Reject any fact carrying mutable campaign state.

Deterministic cleanup of transport artefacts — a stray markdown fence, a trailing
blank line — is permitted before parsing. Nothing may be invented, altered, or
dropped.

### Contract C — Entity observation (Stage 6 output) — **the seam**

This is the load-bearing interface: everything downstream of it is preserved
code. Get it wrong and Stages 7–12 stop working.

**One entity observation per (entity, unit).** Not one per fact. This shape is chosen
deliberately so that `reconciliation.reconcile_records` keeps working: it already
groups by `concept_id` and iterates `fields`, so grouping facts into a per-entity
`fields` dict means reconciliation needs a rename, not a rewrite.

```json
{
  "observation_id": "observation.pack-007.p31.area24.a24",
  "concept_id": "p31.area24.a24",
  "entity_kind": "place",
  "entity_name": "24 CRUSH HALLWAY",
  "fields": {
    "dimensions": {"value": "90 ft hallway", "visibility": null},
    "visible": {
      "value": "Thick splinters and wood shards spread around the east side.",
      "visibility": "public"
    },
    "exit": {"value": {"to": "m22", "via": "corridor"}, "visibility": null}
  },
  "unit_id": "p31.area24",
  "source_pages": [31],
  "confidence": "high",
  "references": ["p31.area24.m22"],
  "pack_id": "pack-007"
}
```

**Keys `observation_id`, `concept_id`, `fields`, `source_pages`, `confidence`,
`references`, and `pack_id` are read directly by `reconcile_records` and must
keep these exact names.**

`entity_kind` replaces the old `record_type`. `reconcile_records` reads
`record_type`; renaming it there is a one-line change and is task T4.1.

**Every field value is a `{"value": …, "visibility": …}` wrapper, never a bare
value.** Visibility must travel *inside* the value, not in a parallel map beside
it. `reconcile_records` builds its output records from `fields` alone — a sibling
key is never read, so a parallel visibility map would be silently dropped at
Stage 8 and never reach the Stage 10 compiler, which consumes records rather than
observations. Visibility is the field the dataflow document says "decides which
section of which card a fact reaches", so losing it there would be invisible and
fatal.

Wrapping has three consequences, all wanted:

- `_value_key` hashes values with `canonical_json_bytes`, so dict values compare
  correctly with no change.
- Two units that agree on a value but disagree on its visibility now raise a
  blocking conflict automatically, which is the behaviour Stage 8 specifies.
- The compiler reads `record["fields"][predicate]["visibility"]` to route facts
  into card sections.

`visibility` is `null` for predicates that carried none.

**Three fields exist downstream but have no source in the CSV format.** The wire
format carries no confidence, no references, and no per-fact page citation. The
runner must supply all three, and how it does so is a decision, not an
implementation detail:

- **D-1 `confidence`** — the model no longer reports it. Recommended: the runner
  assigns `high` when a unit validated on first attempt and `medium` after a
  retry. Alternative: drop confidence from the entity observation shape entirely and
  strip it from `reconcile_records`, `review.py`, and `cli.render_codex_task`.
  **Decide in T2.7 and record the decision in this document.**
- **D-2 `references`** — derive deterministically from fact values that resolve
  to another declared entity, including JSON values such as
  `{"to": "m22", …}`. No model involvement.
- **D-3 `source_pages`** — take the unit's pages. Per-fact page precision is not
  available and the dataflow document does not ask for it.

### Contract D — `schema.md` (Phase 1 deliverable)

The frozen extraction contract shipped inside every pack. It must contain, and a
task may not proceed on its absence:

1. **The predicate vocabulary**, and whether it is closed or open (open question
   in the dataflow document; decided in T1.4).
2. **For each predicate: scalar or list-valued**, with both behaviours below
   spelled out per predicate. If a unit may assert the same `(entity, predicate)`
   twice, that predicate is list-valued. **This must be declared, never inferred
   at parse time** — inferring it makes the entity observation shape depend on
   the data.

   *Within one unit* (ingest, T2.8): repeated rows for a list-valued predicate
   collect into a list, in source order. Repeated rows for a **scalar** predicate
   are a validation error and reject the unit. Neither may silently overwrite —
   a dict assignment that drops the earlier row is undetectable downstream, and
   it is the specific failure this declaration exists to prevent.

   *Across units* (Stage 8): differing values are a **blocking conflict**,
   list-valued or not. Dataflow Stage 8 is explicit — *"no value is chosen —
   both are preserved as a blocking conflict"* — with no exemption for lists.

   **Do not add a union-merge path to `reconcile_records`.** `reconcile_topology`
   merges its `SET_FACETS` (`barriers`, `features`, `conditions`, `hazards`) as a
   union and raises no conflict. That asymmetry is deliberate: topology facets
   are independent observations of one physical passage, whereas two units
   disagreeing about an entity's facts is exactly the evidence Stage 8 wants
   escalated. Copying the union path into record reconciliation would silently
   merge contradictions.
3. **For each predicate: free text or structured JSON**, and for structured ones,
   the key set.
4. **The entity kind vocabulary** (`place`, `mechanism`, `actor`, …).
5. **The visibility vocabulary**: `public`, `hidden`, `discoverable`, empty.
6. **The structural row types** and their field meanings.

---

## Test continuity policy

The suite is the safety net for a rewrite that touches `identity.py` and
`coverage.py`. It must not be red for three phases.

Of 6,301 test lines, 5,085 are coupled to the record schema: `test_v1.py`
(2,369), `test_operational_actors.py` (1,379), `test_operational_places.py`
(610), and `test_identity.py` (727). The first three construct synthetic
`module-content-evidence/v3` responses and drive the CLI end to end. Phase 2
deletes the validators they depend on.

**The policy:**

1. **`test_scene_loading.py` and `test_campaign_binding.py` must stay green at
   every commit, without modification.** They reference no content schema. They
   are the proof that the preserved back end really was preserved. If a task
   turns either red, that task is wrong.
2. **Fixtures move with their phase, not to Phase 5.** A task that deletes a
   validator also re-authors or quarantines the tests covering it, in the same
   commit.
3. **Quarantine is allowed exactly once and must be explicit.** A test suite that
   cannot yet be re-authored moves to `module-extractor/tests/legacy/` with a
   module-level skip and a one-line reason. Phase 5 empties that directory. A
   non-empty `tests/legacy/` at the Phase 5 gate is a failure.
4. **New code lands with tests in the same commit.** No task defers its own
   coverage.
5. **`test_identity.py` is split, never quarantined whole.** It is the one suite
   that would otherwise leave `identity.py` uncovered across the exact two phases
   in which it is rewritten. The file has two classes and only one of them is
   schema-coupled:

   | Class | Lines | Schemas used | Fate |
   |---|---:|---|---|
   | `IdentityAnalysisTests` (9 tests) | ~415 | `REVIEW_SCHEMA` only — survives Phase 2 | **Stays green.** Reshape fixtures from old observations to Contract C entity observations at T2.8. |
   | `CleanIdentityPipelineTests` (1 test) | ~210 | `ROUTING_SCHEMA`, `CONTENT_SCHEMA` — both deleted | Quarantine at T2.5, restore at T5.1. |

   The analysis class covers `normalize_identity_text`,
   `detect_duplicate_candidates`, `apply_identity_review`, alias cycles,
   keyed-area distinctness, and release gating. **That is precisely the coverage
   T4.3 needs while rewriting `_default_base`, `_descriptor_table`, and the
   collision-suffix logic.** Quarantining the whole file would rewrite 824 lines
   of identity policy with no safety net.

---

## Human handoffs

Two steps cannot be performed by an automated implementer. They are expected
pauses. Stop, produce the named artefact, and report.

**H-1 — Manual model exchange (T1.2).** A pack ZIP must be handed to a chat model
and its response saved back. The implementer prepares `_exchange/<pack-id>.zip`
and stops. A human returns `_exchange/<pack-id>.csv`. There is no automated
transport path until the local-model or cloud-API runner exists, which is out of
scope for this work order.

**H-2 — Judgment gates.** Eight points require a person to read output and
decide. The implementer produces the artefact and stops.

| Task | Decision | Artefact |
|---|---|---|
| T0.5 | Are the unit boundaries right? | `scratch/unit-tables/` |
| T1.3 | Are format violations occasional or systematic? | `scratch/csv-compliance.md` |
| T1.4 | Closed or open predicate vocabulary; which are list-valued; which carry JSON | decision table in this document (D-4, D-5, D-6) |
| T2.4 | Is the classifier's human queue small enough, or does segmentation need fixing? | `scratch/classification-queue.md` |
| T3.5 | Do compiled cards read acceptably? | `scratch/baseline-diff.md` |
| T4.7 | The three topology questions | `architecture-new-plan.md` (D-8, D-9, D-10) |
| T5.4 | Keep or delete the historical PoC | decision recorded in this document |
| T6.2 | Whole-module comparison against the baseline | `scratch/final-diff.md` |

T2.4 is easy to miss and matters: the dataflow document makes Stage 3's
determinism conditional on that queue staying small, and says that if it does
not, **segmentation** is what needs fixing — a Phase 0 problem surfacing two
phases late.

---

## Tasks

### Phase 0 — Segmentation

Prototype work. Lives under `module-extractor/scratch/`, not in the package.

**T0.1 — Bounding-box extraction.** Wrap `pdftotext -bbox-layout` and parse it
with `xml.etree.ElementTree` into per-page word lists with `x`, `y`, `width`,
`height`, `text`.
*Done when:* running it over all five PDFs produces a word count per page for
each, with no parse errors.

**T0.2 — Line-height clustering.** Cluster line heights per document to find its
structural tiers. **Thresholds must be derived per document, never hardcoded** —
14.5 is a fact about *Lair of the Lamb*, not about PDFs.
*Done when:* each of the five sources yields a tier table, and *Lair of the
Lamb*'s reproduces the known result: 56.1 titles / 20.8 sections / 14.5 keyed
areas / 12.2 body.

**T0.3 — Column separation.** Assign words to columns by `xMin` clustering and
emit un-interleaved text per column.
*Done when:* the text for `1 BOWLS` on page 21 contains its own body prose and
none of the facing column's.

**T0.4 — Unit assembly.** Build Contract A units: heading detection from the
keyed-area tier, body text to the next heading, page-break continuation joining
units that span pages.
*Done when:* all 58 keyed areas of *Lair of the Lamb* appear as exactly one unit
each, and units spanning a page break cite both pages.

**T0.5 — Generalize and report.** Run T0.4 across all five sources. Handle
non-keyed units: stat blocks, tables, sidebars, rules sections.
*Done when (review):* a unit table for all five sources is written to
`module-extractor/scratch/unit-tables/`.

### Phase 1 — CSV contract

**T1.1 — Hand-assemble one pack.** Five to eight units from T0.5 spanning a keyed
room, a stat block, a random table, and a rules section. Build `README.md`,
`prompt.md`, `schema.md` (draft), `units.csv`, `units/*.txt`.
*Done when:* `_exchange/<pack-id>.zip` exists and is deterministic across two
builds.

**T1.2 — Exchange.** **→ H-1 handoff.** Stop here.

**T1.3 — Throwaway parser and compliance measurement.** Parse the returned CSV
per Contract B. Count: rows that split into four fields, first-three-field
vocabulary violations, JSON parse failures, missing or duplicated `#unit`
markers.
*Done when (review):* figures for at least two independent responses to the same
pack are written to `module-extractor/scratch/csv-compliance.md`.

**T1.4 — Decide the vocabulary.** Closed or open; per-predicate scalar/list;
per-predicate text/JSON.
*Done when (review):* the decision and its rationale are written into this
document under Contract D and the D-4/D-5/D-6 rows. **A decision you made
yourself is a proposal until a human accepts it.**

**T1.5 — Freeze `schema.md`.** Produce the real one, meeting all six Contract D
requirements.
*Done when:* `module-extractor/module_extractor/schema.md` exists and T1.3's
parser validates the Phase 1 responses against it.

### Phase 2 — Front end

**T2.1 — `preparation.py`: typed-run assets.** Add `pdftohtml -xml` extraction
beside the existing `-layout` call, writing the runs into the cache. Keep the
source identity record, thumbnails, map renders, and atomic publish untouched.
*Done when:* `advanced prepare` emits the runs file; existing preparation tests
still pass. **Done** — `preparation.PDFTOHTML_ARGUMENTS`, cached at
`text/runs.xml`, with `tests/test_preparation.py`.

**Two deviations from this task as originally written, both deliberate.**

*The tool is `pdftohtml -xml`, not `pdftotext -bbox-layout`.* This task and the
Environment section above were written before T0.2 was revised. `-bbox-layout`
gives a box per word and nothing else, so the only typographic signal is glyph
height — a lossy proxy for point size, with family, weight and colour discarded.
Two of the five in-scope sources could not be segmented from it: Lair sets keyed
areas and subsection headings at the same 18pt and separates them by colour,
Doom separates headings by family and weight. `pdftohtml` ships in the same
Poppler package, needs no new dependency, and is what `scratch/pdfhtml.py`
already uses. `scratch/bbox.py` remains only as the source list and error type.

*One document-level file, not one per page.* Poppler's XML is not well-formed —
bare ampersands inside font names, unbalanced inline tags inside runs — so
splitting it per page requires the same repairs the segmenter performs at T2.3.
The cache should hold what Poppler said rather than a partial reading of it, and
segmentation reads the document whole in any case, because the body style is a
whole-document fact.

**T2.2 — `preparation.py`: unusable-text-layer failure.** Stage 1 requires a PDF
without a *usable* text layer to fail explicitly.

**Empty is not the only unusable.** Curse of Strahd carries 779 KB of OCR text
across 258 pages and still segments to nothing, because its 12,151 synthetic
fonts give 11,964 style keys over 32,020 runs. It failed silently: zero units,
exit 0.

*Done when:* a text-layer-free PDF and an OCR-noise PDF each raise
`ExtractorError` naming which condition failed, with tests. **Done** —
`preparation.check_text_layer`. Measured runs per distinct style:

| Source | Runs | Styles | Runs/style |
|---|---:|---:|---:|
| Lair of the Lamb | 3,486 | 24 | 145.2 |
| Winter's Daughter | 2,691 | 22 | 122.3 |
| Falkrest Abbey | 2,775 | 27 | 102.8 |
| Doom of the Savage Kings | 1,382 | 12 | 115.2 |
| Шпиль Кетцаль | 5,509 | 29 | 190.0 |
| The Lost City | 3,979 | 21 | 189.5 |
| **Curse of Strahd** | **32,020** | **11,964** | **2.7** |

`TEXT_LAYER_MIN_RUNS_PER_STYLE = 20` sits a factor of five below the worst
typeset source and a factor of seven above the scan. The ratio is only applied
above `TEXT_LAYER_MIN_RUNS = 200`, below which it means nothing and the
empty-text condition is the operative one. Font subset tags are stripped before
counting, or one face embedded twice would inflate an ordinary document.

**The check does not catch a damaged text layer, and must not claim to.** The
Lost City scores 189.5 — a perfectly clean font table — while its prose arrives
as `C e ntip e d e , G ia nt`. That is a different defect needing a different
measure (a high ratio of one- and two-character tokens), and it stays deferred.
Preparation now runs it before the page renders, so an unusable 258-page source
fails in under three seconds instead of after rendering every thumbnail.

**T2.3 — `segmentation.py`.** Promote T0.4/T0.5 into the package, emitting
Contract A units.
*Done when:* segmentation is deterministic across two runs on all five sources,
with tests.

**T2.4 — `classification.py`.** Assign concerns per unit from heading grammar,
templates, dice/measurement density, and the preceding unit's labels. Uncertain
units get **every plausible label**; unresolvable ones go to a human queue.
*Done when (review):* every unit carries at least one label or is queued, and
the queue is written to `module-extractor/scratch/classification-queue.md` with
its size. A large queue is evidence against Phase 0, not against the classifier.

**T2.5 — Delete `routing.py`.** Remove the module, `validate_routing`, the
routing round trip, and the routing state from the CLI state machine. Split
`test_identity.py` per test-continuity rule 5: quarantine
`CleanIdentityPipelineTests`, keep `IdentityAnalysisTests` in place.
*Done when:* no reference to `ROUTING_SCHEMA` remains outside `tests/legacy/`,
and `IdentityAnalysisTests` is still green.

**T2.6 — `packs.py`: rekey to units.** Keep `deterministic_zip`, the manifest
with pack hashes, README and template scaffolding. Partition unit lists instead
of page runs. Delete `_content_prompt`.
*Done when:* packs are deterministic for identical units and budget; each pack
carries `units.csv` and `units/*.txt` per Contract A.

**T2.7 — `facts.py`: parse and validate.** Implement Contract B in the order
given. Rejection is per unit. **Resolve decision D-1 here.**
*Done when:* every Contract B rule has a passing negative test.

**T2.8 — `facts.py`: emit entity observations.** Produce Contract C entity
observations, expand local IDs, attach pack ID, unit ID, and pages, derive
`references` per D-2. Apply the Contract D within-unit rule: repeated rows
collect into a list for a list-valued predicate and reject the unit for a scalar
one.
*Done when:* entity observations validate against Contract C;
`reconcile_records` consumes them unmodified except for the T4.1 rename; and a
unit asserting the same scalar predicate twice is rejected rather than silently
losing the first row.

**T2.9 — Strip `contracts.py` and `evidence.py`.** Delete
`_validate_place_fields`, `_validate_actor_fields`, `_validate_situation_fields`,
`_validate_activation`, `_validate_repeat`, `_validate_possible_effects`,
`validate_content_task_coverage`, and their vocabulary constants (~800 of 1,066
lines). Delete `_content_observations` and the content branch of
`ingest_responses`. **Keep `validate_source`, `validate_pages`,
`validate_pack_manifest`, `validate_review`, the schema constants, and
`validate_map_response` — map evidence does not travel the CSV path.**
*Done when:* the package imports cleanly, and the record-shaped suites are
re-authored or quarantined per the test continuity policy.

**Phase 2 gate:** a PDF goes in and validated entity observations land in the durable
store with unit IDs and page citations, with no model call outside Stage 5.

### Phase 3 — Compiler

**T3.1 — Recover the baseline.** Already done; it lives at
`module-extractor/scratch/baseline/` and is **committed**.

```bash
git show baseline/lair-lamb:module/audit/module.json   # 613 records, 3.9 MB
git show baseline/lair-lamb:module/index.json
git show baseline/lair-lamb:module-input/review.json
```

**Cite it by tag, never by hash.** The history before the rebuild was squashed
from 31 commits to 6, which changed every hash in it. `baseline/lair-lamb` and
`base/extractor-v1` are annotated tags precisely so that a rewrite cannot
invalidate the two references this work order depends on — a stale hash fails as
`unknown revision`, with nothing to say it used to resolve.

**It is committed on purpose.** An earlier revision said not to commit it,
reasoning that it is derivable from git history. That was wrong: it is
derivable only from the `lair-lamb` branch, so any checkout that does not
happen to carry that branch — a fresh clone, a different machine, a shallow
fetch — silently loses the one thing Phase 3's gate compares against. Four
megabytes in a private repository is not worth that risk.

**The pipeline must never read it.** That is the real constraint, and it is
about contamination, not storage: if compilation could see the old output it
could copy from it, and the Phase 3 diff would prove nothing. No module under
`module_extractor/` may open a path under `scratch/baseline/`.

*Done when:* 613 records are readable and indexed by ID. **Verified** — 613
records, 613 unique IDs, 59 `(record_type, field)` pairs, 393 title+text-only
against 220 structured, and `place.module-lair-of-the-lamb.1-bowls` present.

**T3.2 — Map the field surface.** Enumerate the `(record_type, field)` pairs the
compiler must fill — 59 in the baseline — and mark which are covered by which
predicate.
*Done when:* every pair is either mapped to predicates or explicitly listed as
unmapped.

**T3.3 — `compilation.py` for places.** Target `operational-module/v3` so
`rendering.py`, `operations.py`, `topology.py`, and `scene.py` need no changes.
Route facts into card sections using the `visibility` carried inside each
Contract C field value.

**Note the integration point.** There is no compiler step in the pipeline today:
`assembly.canonical_module` wires reconciled records straight into the module,
because under the old design the model's records were already card-shaped. This
task inserts compilation between `apply_review` and `canonical_module`. That is
the only change `assembly.py` needs: its own logic is untouched, and only its
input moves one step further down the pipeline.

Reconciled records and compiled records both have a `fields` key and they are
**not the same object**: the reconciled one is keyed by predicate with wrapped
values, the compiled one by card field with bare values. Everything upstream of
the compiler reads the first; `rendering.py` and `operations.py` read the second.
*Done when:* three or four keyed rooms compile into place records that
`validate_rendered_module` accepts.

**T3.4 — Situations and procedures** for the same rooms.
*Done when:* the same rooms produce situation and procedure records.

**T3.5 — Baseline diff.** Field-by-field comparison against T3.1's records.
Report lost mechanics, lost numbers, lost citations, and specifically whether
`location.hidden`, `location.triggers`, and `situation.activation` have collapsed
into identical prose.
*Done when (review):* the comparison is written to
`module-extractor/scratch/baseline-diff.md`. This is the load-bearing bet; if it
fails, Phase 4 does not start.

### Phase 4 — Identity, reconciliation, review

**T4.1 — `reconciliation.py` rename.** `record_type` → `entity_kind`, and nothing
else. Confirm the existing grouping — by `concept_id`, iterating `fields` — is
already what Contract C needs.
*Done when:* reconciliation tests pass against entity observations;
`reconcile_topology` is untouched; and two units asserting different values for
the same list-valued predicate produce a **blocking conflict**, not a merged
list. If that test tempts you to add a union path, re-read Contract D item 2.

**T4.2 — Pin the ID shape.** Write the test *first*: the entity named `1 BOWLS`
canonicalizes to `place.module-lair-of-the-lamb.1-bowls`.
*Done when:* the test exists and fails for the right reason.

**T4.3 — `identity.py` rework.** `_default_base` derives canonical IDs from
record *titles*; facts have entity *names*. Rework `_descriptor_table`,
`_default_base`, and the collision-suffix logic. Keep `normalize_identity_text`,
`identity_slug`, `keyed_area`, `module_slug`, alias resolution, and
duplicate-candidate detection.
*Done when:* T4.2 passes and `IdentityAnalysisTests` — green since T2.5 and
never quarantined — is still green afterwards. It is the safety net for this
task; if it was quarantined, stop and restore it first.

**T4.4 — `coverage.py` rewrite.** Key on `(unit_id, concern)` instead of
`(pdf_page, task)`. **Preserve the page-completeness invariant**: every physical
page must be covered by some unit or explicitly excluded as cover, divider,
blank, or non-operational illustration. Without it a segmentation false negative
is undetectable.
*Done when:* a deliberately dropped unit makes coverage fail.

**T4.5 — `review.py` to fact identities.** Conflicts become per-fact rather than
per-field. Keep `validate_review`, `release_gate`, and `cli.render_codex_task`
structurally intact.
*Done when:* a synthetic two-unit disagreement produces a blocking conflict that
`release_gate` refuses to release.

**T4.6 — CLI state machine.** Rework states for the unit pipeline; the routing
states are gone.
*Done when:* `run` advances from prepare through release on *Lair of the Lamb*
without manual intervention beyond H-1.

**T4.7 — Topology reconciliation review.** Answer the three carried topology
questions against the existing `reconcile_topology` and
`resolve_operational_topology` behaviour before changing either.
*Done when (review):* the answers are recorded in `architecture-new-plan.md`
and in the D-8/D-9/D-10 rows below.

### Phase 5 — Tests

**T5.1 — Empty `tests/legacy/`.** Re-author every quarantined suite against CSV
fact fixtures. The assertions are unchanged; only the input shape moves.
*Done when:* `tests/legacy/` is empty and the full suite is green.

**T5.2 — Fixture builders.** Replace ad-hoc dict construction with helpers that
build fact rows, so future schema changes touch one place.
*Done when:* no test file constructs a Contract C entity observation literal
directly; all go through the builder.

**T5.3 — Determinism test.** Same PDF twice, byte-identical `module/`.
*Done when:* a test builds the module twice into separate directories and
asserts equal `content_tree_hash`.

**T5.4 — Decide on the PoC.** `scripts/poc.py` (1,798 lines) and `test_poc.py`
(715) are historical and isolated. Keep or delete; either is acceptable.
*Done when (review):* the decision is recorded here. If keeping, they must pass;
if deleting, both go in one commit.

### Phase 6 — Rebuild

**T6.1 — Full run** on *Lair of the Lamb*, publishing `module/`.
*Done when:* `run` completes from prepare to release and `module/` is published,
with H-1 the only manual step.

**T6.2 — Gate.** Four automatic checks, then one review.
*Done when:* all four pass —

1. `python3 scripts/validate_repo.py` reports zero errors.
2. `GENERATED_OUTPUT.json` declares `play_contract: module-play/v1` and
   `verification: verified`.
3. `module/index.json` contains `place.module-lair-of-the-lamb.1-bowls`.
4. `status --scene place.module-lair-of-the-lamb.1-bowls` resolves.

*Done when (review):* a whole-module comparison against the recovered baseline —
record counts and card sections, not the handful of rooms from T3.5 — is written
to `module-extractor/scratch/final-diff.md`.

**T6.3 — Documentation.** Update `DEVELOPER.md`, `USER_GUIDE.md`,
`CODEX_WORKFLOW.md`, and `IDENTITY.md`, which all describe the page/record
pipeline throughout. Only after T6.2 passes.
*Done when:* no reference to routing, page/task coverage, or
`module-content-evidence` remains in any of the four.

---

## Dependencies

```text
T0.1 → T0.2 → T0.3 → T0.4 → T0.5 ──┐
                                    ├→ T1.1 → T1.2(H-1) → T1.3 → T1.4 → T1.5
                                    │                                     │
T2.1 → T2.2 ────────────────────────┘                                     │
T2.3 ← T0.5                                                               │
T2.4 ← T2.3                                                               │
T2.5 ← T2.4                                                               │
T2.6 ← T2.3, T1.5 ────────────────────────────────────────────────────────┘
T2.7 ← T1.5      (resolves D-1)
T2.8 ← T2.7
T2.9 ← T2.8

T3.1 (independent — do early, it is one command)
T3.2 ← T3.1, T1.5
T3.3 ← T3.2, T2.8
T3.4 ← T3.3
T3.5 ← T3.4, T3.1

T4.1 ← T2.8       T4.2 → T4.3       T4.4 ← T2.4
T4.5 ← T4.1       T4.6 ← T2.5, T2.6, T4.4
T4.7 ← T4.1

T5.* ← Phase 4 complete
T6.* ← Phase 5 complete
```

`T3.1` has no dependencies and should be done first — it is one `git show`, and
losing the `lair-lamb` branch before it runs destroys the only comparison
baseline.

---

## Decisions recorded here

As tasks resolve open questions, record the answers in this section so later
tasks do not re-litigate them.

| ID | Question | Decided in | Answer |
|---|---|---|---|
| D-1 | Where does `confidence` come from? | T2.7 | *unanswered* |
| D-2 | How are `references` derived? | T2.8 | Deterministically, from fact values resolving to declared entities |
| D-3 | Per-fact page citations? | — | No; entity observations take the unit's pages |
| D-4 | Closed or open predicate vocabulary? | T1.4 | *unanswered* |
| D-5 | Which predicates are list-valued? | T1.4 | *unanswered* — but the behaviour is fixed: collect within a unit, conflict across units, never union |
| D-6 | Which values carry JSON? | T1.4 | *unanswered* |
| D-7 | Segmentation fallback for a failing document? | T0.5 | **Scans are deferred as a class.** See [Deferred: scanned sources](#deferred-scanned-sources) |
| D-8 | Map facts: shared vocabulary or typed pipeline? | T4.7 | *unanswered* |
| D-9 | Prose/map disagreement authority? | T4.7 | *unanswered* |
| D-10 | Waypoint keyed areas: own a topology node? | T4.7 | *unanswered* |
| D-11 | Is one fact-to-field mapping enough across rulesets? | **not in this work order** | *unanswerable here* — see below |

**D-11 is out of scope and must not be closed by guessing.** The dataflow
document raises it under Compilation, but every task here builds one module in
one ruleset. A single-source result says nothing about portability. Answering it
needs a second module from a different system — the other four sources span
several, including a 1982 TSR module against a modern GLOG one. That is a
follow-on effort. Until then the compiler's mapping is assumed per-system, and
a task that finds itself generalizing the mapping should stop and flag it.
