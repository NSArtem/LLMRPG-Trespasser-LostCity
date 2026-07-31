# Proposed architecture: shared fact bundles

**Status:** draft. Not implemented.

**Relationship to the current design:** this proposes a replacement for Step 4
of `architecture-current.md`, and a simplification of Steps 6–9 that follows
from it. Steps 1–3 (page text, routing, packing) and Step 11 (scene
resolution) are unaffected in kind.

**A note on this revision.** An earlier version justified the change on token
cost, claiming the model repeatedly paraphrases the same facts. Measured
against the *Lair of the Lamb* build, that specific claim does not hold —
paraphrase accounts for roughly 3% of output, and the largest cheap win
(minified JSON, 30%) needs no architecture change at all.

A token argument for fact bundles does survive, but a different one: a flat
fact schema can be emitted as **CSV rows instead of JSON objects**, which
measures 28–35% cheaper and is structurally impossible for the current nested
records. So the design is worth doing for two reasons — schema coherence and
row encoding — neither of which is the reason originally given.

Measurements are in [Measured baseline](#measured-baseline) and
[Serialization format comparison](#serialization-format-comparison); corrected
priorities are in [Recommended sequencing](#recommended-sequencing).

## Summary

The current pipeline asks the extraction model to produce final-shaped records
— places, situations, procedures, effects — which are partly different views
of the same underlying facts. The model decides record ownership, mints IDs,
builds cross-references, and writes player-facing prose, all while reading the
source for the first time.

The proposal is to split that: the model extracts **facts**, and local code
**compiles** facts into cards.

> Places, situations, procedures, and effects should be read models derived
> from shared semantic facts — not independent LLM-authored copies of those
> facts.

There are two justifications, and neither is the one originally offered.

**Schema coherence.** Today, agreement between a place card and its situation
card is something the model is asked to achieve and later stages are asked to
verify. Under fact bundles agreement becomes structural: both cards project the
same fact, so they cannot disagree.

**Row encoding.** A flat, uniform fact table can be emitted as CSV rows rather
than JSON objects, which measures 28–35% cheaper because column names stop
repeating. Nested heterogeneous records cannot be expressed this way, so this
saving is only reachable through the fact schema.

What is *not* a justification is fact deduplication, which the earlier draft led
with and which measures at about 3%.

## Measured baseline

All figures below are measured from this checkout: the 613 canonical records in
`module/audit/module.json` and the 655 KB response set in
`module-input/responses/`.

### Duplication is real but small

The motivating example is genuine. One sentence about the crush hallway ceiling
appears six times across three record types:

```
effect     Any touch greater than a feather triggers the ceiling in 24 CRUSH HALLWAY. It takes 10 seconds…
location   The ceiling falls 10' in 10 seconds, rests for 10 seconds, then resets.
location   Any contact heavier than a feather triggers the descending ceiling.
location   Entering the hallway or applying more than feather-light contact starts the ceiling's lowering cycle.
situation  Any touch greater than a feather in the hallway triggers the ceiling; stepping on a trap door…
situation  The ceiling takes 10 seconds to fall 10', rests for 10 seconds, then resets.
```

But it is close to the worst case, not the typical case. Comparing every pair
of prose strings from different records citing the same page (4-gram Jaccard
similarity above 0.35):

- 152 of 1,513 prose strings participate in any paraphrase;
- that is **8.8% of prose characters**;
- exact string duplication is 6.5%, and most of it is ID strings, not prose.

Prose is 29% of the payload, so eliminating *all* fact duplication saves about
**3% of output**.

### The payload is mostly encoding, not content

Decomposing the 655 KB response set by what each byte pays for:

| Component | Share |
|---|---:|
| Pretty-print whitespace | 28% |
| Prose values | 29% |
| Repeated JSON keys | 18% |
| Cross-reference ID strings | 9.5% |
| Short values | 8% |
| ID and schema metadata | 4.6% |

This is real generation cost, not a storage artifact:
`evidence.import_exchange_responses` copies the model's bytes verbatim
(`payload = response_path.read_bytes()`) and pins that exact byte sequence by
hash, so the stored files are literally what the model emitted — indentation
included.

The consequence is that **the large token wins are encoding changes, and none
of them require this architecture.**

### Serialization format comparison

All figures are `o200k_base` tokens over the full response set. `cl100k_base`
gives the same ranking within 0.4%.

| Format | Tokens | vs. minified JSON |
|---|---:|---:|
| JSON as emitted (indent 2) | 163,680 | +42% |
| **JSON minified** | **115,203** | — |
| YAML flow style | 116,978 | +2% |
| S-expressions | 124,057 | +8% |
| YAML block style | 130,513 | +13% |
| TOML | 138,419 | +20% |
| XML | 156,137 | +36% |

The 163,680-token figure confirms the "roughly 145k–170k" estimate quoted
elsewhere in this document.

**Nothing beats minified JSON for the current nested record schema.** Every
alternative pays for 3–4 levels of nesting through indentation or repeated tag
names, while JSON's punctuation (`","`, `":"`, `"},{"`) merges into single
tokens because JSON is ubiquitous in training data. TOML additionally has no
null type, and this pipeline uses null meaningfully (`topology_node: null` is a
recorded review decision), so it was measured only after stripping nulls.

Non-ASCII escaping is a non-issue: there are zero `\uXXXX` sequences in the
emitted files, and switching to raw UTF-8 would save 0.4%.

### Locality is high

Two measurements strongly support source-unit sharding:

- only 48 of 613 records (8%) cite more than one page;
- only 42 of 1,342 cross-references (3%) point at a record with no shared
  source page.

Pages carry 2–4 keyed places each (maximum 9), so source-native units are
genuinely finer-grained than pages.

### Effect records

Counting inbound references to each of the 129 effect records:

| Referenced by | Effects |
|---|---:|
| 0 records | 5 |
| 1 record | 67 |
| 2 records | 28 |
| 3 records | 24 |
| 4+ records | 5 |

Applying the inlining rule proposed below, **72 effects (56%) are inlining
candidates and 57 survive as genuinely shared.** That removes 72 of 613
records — about 12% of the module, not the "large fraction" claimed earlier.

## The design

### Facts first, cards later

Step 4 should answer a simpler question:

> What does this source section assert?

It produces one compact semantic bundle per keyed section. Local code compiles
that bundle into places, situations, procedures, and effects.

```text
source section
    ↓
one semantic extraction
    ↓
facts + entities + events + options
    ↓
deterministic compiler
    ├─ place card
    ├─ situation card
    ├─ procedure card
    └─ effects, where actually useful
```

### Example bundle

```json
{
  "unit": "page31.area24",
  "source_pages": [31],
  "entities": [
    {"id": "area.24", "kind": "place", "name": "24 CRUSH HALLWAY"},
    {"id": "mechanism.ceiling", "kind": "mechanism"},
    {"id": "mechanism.trapdoors", "kind": "mechanism", "count": 3}
  ],
  "facts": [
    {
      "id": "f1",
      "subject": "area.24",
      "predicate": "dimensions",
      "value": {"length_ft": 90}
    },
    {
      "id": "f2",
      "subject": "area.24",
      "predicate": "visible-feature",
      "value": "Thick splinters and wood shards lie around the east side.",
      "visibility": "player"
    },
    {
      "id": "f3",
      "subject": "mechanism.ceiling",
      "predicate": "activation",
      "value": "Contact greater than a feather.",
      "visibility": "hidden"
    },
    {
      "id": "f4",
      "subject": "mechanism.ceiling",
      "predicate": "cycle",
      "value": {
        "fall_distance_ft": 10,
        "fall_seconds": 10,
        "rest_seconds": 10,
        "then": "reset"
      }
    },
    {
      "id": "f5",
      "subject": "mechanism.trapdoors",
      "predicate": "concealment",
      "value": "Perfectly disguised but sound hollow when tapped."
    },
    {
      "id": "f6",
      "subject": "mechanism.trapdoors",
      "predicate": "consequence",
      "value": {"fall_distance_ft": 40, "destination": "water below"}
    }
  ],
  "options": [
    {
      "id": "o1",
      "action": "Sprint across",
      "result": "Avoid the ceiling without a Movement check.",
      "condition": "Trapdoors must still be jumped or disabled."
    },
    {
      "id": "o2",
      "action": "Jam the ceiling with an uncrushable object",
      "cost": "The object cannot be recovered."
    },
    {
      "id": "o3",
      "action": "Climb along the wall with spikes and ropes",
      "cost": "About one hour and several encounter checks."
    },
    {
      "id": "o4",
      "action": "Hold the remote switches in 22 MUSHROOM",
      "result": "Disable the three trapdoors."
    }
  ]
}
```

Every source assertion appears approximately once.

### Cards become projections

The compiler declares which facts belong in each artifact:

```text
place 24:
  first_impression = f1 + f2
  discoverable     = f5
  hidden           = f3
  hazards          = f4 + f6

situation hallway-trap:
  activation       = f3
  repeat           = f4
  stakes           = f4 + f6

procedure cross-hallway:
  steps            = o1 + o2 + o3 + o4
```

Provenance becomes field-level:

```json
{"field": "situation.activation", "fact_refs": ["f3"]}
```

The rendered situation still reads *"Any contact heavier than a feather
activates the ceiling"*, but that sentence is generated from `f3` rather than
written by the model into five separate record fields.

### Shard by source unit, not by output type

Instead of:

```text
page 31 × adventure
page 31 × effects
```

use:

```text
source unit: 24 CRUSH HALLWAY
tasks: discover all relevant semantic facts
```

The model sees the section once and emits every entity, fact, event, and
option it finds. This is independently justified by the 3% cross-page reference
rate: units are nearly self-contained.

Task labels stay useful for **coverage accounting** but should not force
separate calls:

```json
{
  "unit": "page31.area24",
  "coverage": {
    "places": true, "situations": true, "procedures": true,
    "effects": true, "actors": false, "items": false
  }
}
```

Some material still deserves its own call — a large class definition, a complex
random table, a spell catalogue, a full-page stat block. The primary boundary
should be a **source-native unit** (room, actor entry, rule section, table),
not an arbitrary semantic task.

### Stop promoting every mechanic to a global effect

Create a separate effect record only when it is:

- referenced by multiple places or situations;
- part of a reusable rules vocabulary;
- independently applied by the campaign runtime;
- important enough to load or track separately.

Otherwise the fact stays in its source bundle.

```text
ceiling cycle  → local fact used by the hallway place and situation
Dying          → reusable global effect record
Haste          → reusable global spell/effect record
```

Both the hallway place and its situation can refer to
`fact.page31.area24.ceiling-cycle` instead of a shared reference card. Measured
effect: 72 records removed (see [Effect records](#effect-records)).

### Separate extraction from writing

The model currently both discovers information and writes polished prose. These
are different tasks:

```text
LLM:
  identify facts, conditions, entities, events, choices, relationships

code:
  assign standard structure
  propagate shared facts
  build references
  render straightforward prose

optional stronger model:
  rewrite only awkward passages that cannot be rendered mechanically
```

Code can safely render:

```json
{"fall_distance_ft": 10, "fall_seconds": 10, "rest_seconds": 10, "then": "reset"}
```

as *"The ceiling falls 10 feet in 10 seconds, rests for 10 seconds, then
resets."* There is no reason to pay an LLM to write that sentence three times.

## Encoding compaction

These techniques are **independent of the fact architecture** and, per the
measurements above, deliver most of the available token savings. They are
listed here because the earlier draft folded them into the fact proposal and
thereby understated them.

### Emit minified JSON

28% of the current payload is pretty-print whitespace, paid for at generation
time. Measured at the token level the saving is **30%** (163,680 → 115,203).
A prompt change alone recovers it, with no schema change.

### Preallocate the source-unit skeleton

Local code identifies the heading and hands the model:

```json
{"unit": "p31.area24", "name": "24 CRUSH HALLWAY", "page": 31}
```

The model does not repeat source hashes, pack IDs, or citations per fact; the
runner attaches them on receipt.

### Use short local IDs

Reference strings are 9.5% of the payload. Within one unit:

```text
a24 = 24 CRUSH HALLWAY    ceil = the ceiling    trap = the trap doors
```

The compiler expands these into globally safe IDs on receipt, so nothing
downstream changes.

### Store provenance at unit level

If every fact came from page 31, say so once. Only facts spanning several pages
need individual page lists.

### Emit facts as delimited rows, not JSON objects

This is the largest single saving available, and **it is only available once
the fact schema exists** — it does not apply to the current nested records.

Repeated JSON keys are 18% of the payload. A fact table is flat and uniform, so
the column names can appear once (or not at all) instead of on every record.
Measured over a realistic 979-fact table built from actual module prose:

| Format | Tokens | vs. minified JSON |
|---|---:|---:|
| **Delimited rows, position = id** | **23,687** | **−35%** |
| Delimited rows with header | 26,350 | −28% |
| JSON minified | 36,379 | — |
| JSONL | 37,356 | +3% |

For scale: the prose content alone is 16,330 tokens. That is the floor. Rows
land at 31% overhead above it; minified JSON at 55%. There is little left to win
after this change.

Note that JSONL is *more* expensive than a single minified array, because the
outer structure repeats per line. Delimited rows deliver the same
per-unit resumability at a third less cost, so the resumability argument and
the compaction argument point at the same format.

#### Use CSV, with the free-text column last

The separator barely matters — quoted CSV 24,202, unquoted CSV 24,130, tabs
23,687, a 2% spread. **The parsing rule matters much more than the delimiter.**

Adopt one constraint: every row has fixed controlled-vocabulary columns first
and **exactly one free-text column, last**. Parsing then splits on only the
first N−1 delimiters:

```python
subject, predicate, value = line.split(",", 2)
```

No quoting or escaping is required at all, because commas inside the prose fall
after the parser has stopped splitting. Verified against the 979-fact table:
**all 979 rows round-trip exactly with zero quoting.**

```text
akina,capabilities,Carries the Ruby Ring of Wisdom, worth 1000s.
                   └──────────── all of this is the value ─────┘
```

CSV is preferred over tab-separated output because the delimiter is visible
(responses can be read and debugged), there is no invisible-whitespace
ambiguity, and models have seen far more CSV. That last point is a structural
argument, not a measurement — relative model reliability across delimiters has
not been tested here.

**Failure is loud, which matches the rest of the pipeline.** 27% of fact values
contain a comma, so if a model ignores the instruction and quotes values
RFC-style, or mangles a row, a strict column-count check flags roughly a
quarter of the file rather than silently accepting wrong data. Ingest should
still strip surrounding quotes defensively, since models may quote some rows
out of habit.

Two costs of the rule:

- **Rows needing two free-text fields must be split into two rows.** An option
  with an action and a result becomes:

  ```text
  #option,sprint,action,Sprint across
  #option,sprint,result,No Movement check for the ceiling; trap doors must be jumped or disabled.
  ```

  Slightly more verbose, but every row in the file then has the same shape.

- **Controlled-vocabulary columns must never contain a comma.** These are
  generated slugs and known predicate names, so ingest can validate them
  against the known vocabulary — which is worth doing regardless.

Values that are genuinely structured can carry JSON inside the final cell; see
the worked example below.

### Worked example: one room, three encodings

Page 31's `24 CRUSH HALLWAY` currently produces six records — the place, the
situation, two procedures, two effects — costing **1,525 tokens as emitted**
and 1,141 minified. The same content as one fact bundle:

```text
#unit,p31.area24,pages,31
#entity,a24,place,24 CRUSH HALLWAY
#entity,ceil,mechanism,descending ceiling
#entity,trap,mechanism,disguised trap doors (x3)
#entity,m22,place,22 MUSHROOM
a24,dimensions,,90 ft hallway
a24,visible,,Thick splinters and wood shards spread around the east side.
a24,contents,,Crushed furniture debris on the east side.
ceil,activation,hidden,Any contact heavier than a feather triggers the descending ceiling.
ceil,cycle,,{"fall_ft":10,"fall_s":10,"rest_s":10,"then":"reset"}
trap,concealment,discoverable,Perfectly disguised; sound hollow when the floor is tapped.
trap,mechanism,hidden,Each trap door is driven by a hinge and strong spring.
trap,consequence,,{"fall_ft":40,"destination":"water below"}
trap,disarm-from,,m22
#option,sprint,action,Sprint across
#option,sprint,result,No Movement check for the ceiling; trap doors must be jumped or disabled.
#option,jam,action,Jam the ceiling with an uncrushable object
#option,jam,cost,The object cannot be recovered.
#option,climb,action,Climb the wall with spikes and ropes
#option,climb,cost,About an hour; a couple of encounter checks.
#option,switch,action,Hold the three wall switches in 22 MUSHROOM
#option,switch,result,Reach 3 ft into each hole; disables the trap doors while held.
```

Roughly 350 tokens against 1,525 — about a fifth. Points worth noting:

- The ceiling activation sentence appears **once**. Today it appears six times
  across the six records; the compiler copies it into `location.hidden`,
  `situation.activation`, and the effect text.
- Rows beginning `#` are structural (unit, entity, option); plain rows are
  facts. Several row shapes coexist in one file without separate formats.
- Column 3 is visibility (`hidden`, `discoverable`, empty for public). This is
  what routes a fact to the right card section.
- Genuinely structured values carry JSON in the final cell (`cycle`,
  `consequence`). Code renders those into prose deterministically.
- `trap,disarm-from,,m22` is a one-line cross-reference that currently costs
  two `procedure_references` arrays plus an entire separate procedure record.

**Caveat:** this bundle was written by hand from the existing records. It shows
what the format can express, not what a model actually produced. The 30%
minification saving is measured on real output and is firm; this bundle figure
is a design estimate until a prototype runs.

## Alternative: lazy semantic extraction

Rather than extracting the whole adventure upfront, initial ingestion could
produce only source units, headings, page citations, a lightweight entity
index, and map topology. Each room's bundle is extracted and cached when the GM
first approaches it.

Drawbacks: latency before a new area is ready; extraction failures during play;
incomplete global identity resolution; module-wide consistency is harder to
guarantee.

A workable compromise: extract the main keyed locations upfront, lazily extract
appendices, optional encounters, spells, and secondary rules.

## Recommended pipeline

```text
1. Deterministically divide text into source-native units
2. Send each unit once to the semantic model
3. Receive a compact semantic bundle
4. Validate every fact and preserve unit/page provenance
5. Reconcile entities and relations across bundles
6. Compile facts into runtime projections
7. Render cards deterministically
```

Steps 4, 5, and 7 map onto existing machinery. **Step 6 is genuinely new** — a
fact compiler sits where the current pipeline has nothing, because today the
model performs that role implicitly.

## Feasibility risks

These are the parts most likely to cost more than expected.

**Compilation fidelity is the load-bearing assumption, and it is untested.**
The compiler must fill 59 distinct `(record_type, field)` pairs. The hallway
shows the difficulty: `location.hidden`, `location.triggers`, and
`situation.activation` are currently worded *differently because they serve
different roles* — what players cannot see, what starts the trap, what the
activation condition is. Compiling all three from one fact makes them read
identically. That may be acceptable or may flatten the cards; nobody has tried
it. Mitigating factor: 393 of 613 records are only `text` + `title`, so the
compiler's hard surface is the 220 structured records.

**The canonical identity policy does not survive unchanged.**
`identity._default_base` derives canonical IDs from record *titles*. Facts have
no titles; entities have `name`. `_default_base`, `_descriptor_table`, and the
collision-suffix logic in `identity.py` (824 lines) all need rework.

**The existing review overlay does not migrate.** All 63 `values` entries in
`review.json` are field-scoped (`text` ×25, `topology_node` ×17, `title` ×9).
Under a fact model, conflicts become per-fact, so those hand-authored decisions
and the 45 resolved conflicts need re-authoring against new object identities.
This is human work, not code, and is probably the largest hidden cost.

**Coverage validation is page×task by construction.**
`coverage.build_coverage` walks `routing.json` rows and looks up
`task_results[(pdf_page, task)]`, raising if two packs cover the same pair. The
release gate depends on it. Unit-based extraction breaks that contract.

**Unit detection cannot currently be tested.** `.module-extractor-cache/` has
been cleaned and the source PDF is not in the repo, so heading segmentation
cannot be validated against real page text without re-running `prepare`. The
packer is page-based today.

**Migration surface:** `contracts.py` (1,066 lines), `rendering.py` (1,251),
`identity.py` (824), plus a new compiler — against roughly 5,800 lines of
record-shaped tests, of which `test_v1.py` alone is 2,369.

## Revised token expectations

Current Step 4 output measures **163,680 tokens**. The changes fall into two
groups.

**Available without the fact architecture:**

| Change | Saving | Confidence |
|---|---:|---|
| Minified JSON output | 30% | measured |
| Short IDs, unit-level provenance, skeleton | ~7% | estimated |
| **Subtotal** | **~35%** → ~106k tokens | |

**Available only with the fact architecture:**

| Change | Saving | Confidence |
|---|---:|---|
| CSV rows instead of JSON objects | ~28–35% of what remains | measured on a synthetic fact table |
| Fact deduplication | ~3% | measured |
| Merging `adventure` + `effects` calls | not separately quantified | — |

Applying the row-encoding saving on top of the first group lands roughly in the
**65–75k token** range. That is close to the earlier draft's 45–80k band for
fact bundles — but the credit belongs mostly to **CSV row encoding**, which the
earlier draft never considered, rather than to fact deduplication, which it
credited and which is worth 3%.

The important structural point: **CSV row encoding is unavailable to the
current schema.** Nested, heterogeneous records cannot be expressed as flat
rows. That makes the token argument for fact bundles real after all — but it
runs through the format, not through deduplication.

The "lightweight index plus lazy extraction" figure of 15–35k remains
plausible, because it avoids the work rather than compressing it.

## Recommended sequencing

Ordered by measured yield against implementation cost:

1. **Minified JSON output.** 30%, a prompt change, no architectural risk. Worth
   doing regardless of everything else here.
2. **Compact extraction schema** — short local IDs, unit-level provenance,
   preallocated skeleton. ~7% more, and the canonical schema is untouched
   because the runner expands on receipt.
3. **Merge `adventure` and `effects` into one call per unit.** Removes an
   entire duplicate pass over the same text.
4. **Effect inlining rule.** Bounded and testable against existing data: 72
   records.
5. **Fact bundles, CSV row encoding, and the compiler.** Only after 1–4, and
   only after a prototype on two or three keyed rooms is compared field-by-field
   against the current cards. Adopt the CSV rules together with the fact
   schema — they are one change, since flat rows require a flat schema.

Steps 1–3 capture roughly 35% without touching identity, review, or coverage.
Step 5 carries nearly all the cost and roughly half the remaining benefit.

Its justification is now twofold: **schema coherence** — a single source of
truth per fact, and cards that cannot contradict each other — and **CSV row
encoding**, which is worth another 28–35% but is structurally unavailable to
the nested record schema. Fact deduplication, the original stated justification,
is worth 3% and should not be the reason anyone signs off on this.

## Open questions

- What is the fact predicate vocabulary, and is it closed or open?
- How does entity reconciliation relate to the existing canonical-identity
  policy in `identity.py`?
- What does a conflict look like when two bundles assert contradictory facts
  about the same entity — still a blocking conflict resolved through
  `review.json`?
- How are source-native units detected deterministically, given a page-based
  packer?
- Does the compiler's fact-to-field mapping need to be per-system, or is one
  mapping enough across rulesets?
- Do compiled cards read acceptably, or does deriving several fields from one
  fact make them repetitive?
- How reliably do models actually emit delimited rows under the "free text
  last, no quoting" rule? The rule is verified against data; model compliance
  with it is not. This needs a prototype before the format is committed to.
- Can every fact value be expressed as a single trailing cell, or do enough
  cases need embedded JSON that the row format loses its advantage?
