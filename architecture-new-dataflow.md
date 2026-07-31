# Module extraction dataflow

How an adventure PDF becomes runtime-ready play material.

This describes the target design. It is written as a specification of how the
pipeline should work, not a report on how any current code behaves.

## Scope

**In scope:** turning printed adventure text into validated, source-cited,
deterministically rendered play artifacts, and resolving a bounded slice of
those artifacts at the table.

**Out of scope:** running the game. A model may later consume a resolved scene
to act as GM; that is gameplay, not extraction.

**Named boundary:** map and floorplan interpretation. Topology has two
independent sources — the drawn map and the prose — and this document specifies
the prose side concretely while treating the image side as a boundary with open
questions. See [Topology has two sources](#topology-has-two-sources).

## Design principles

1. **The model extracts facts. Code builds artifacts.** The model is asked what
   the source asserts, never what the output should look like. Ownership,
   identity, references, structure, and prose rendering are all decided by
   ordinary code afterward.

2. **One high-volume model boundary, one low-volume escalation.** Semantic
   extraction is the only bulk model task. Everything else is deterministic
   code, except a small stream of genuine ambiguities escalated to a human.

3. **Everything is cited.** Every fact carries the source unit and physical page
   it came from, all the way to the rendered card.

4. **Failures are loud.** A malformed or incomplete response is rejected and
   retried. Nothing is silently repaired, and no stage guesses at meaning to
   recover from a parse error.

5. **Identical inputs produce identical outputs.** Every stage after extraction
   is deterministic and hashable. The same PDF and the same extraction responses
   always produce the same module.

6. **Extraction is complete before play.** The whole adventure is processed at
   ingest. Global identity and cross-references are fully resolved before
   anything reaches the table, so extraction can never fail mid-session.

## Pipeline overview

```text
PDF
 │  1  text extraction              deterministic
 ▼
page text + page images
 │  2  unit segmentation            deterministic
 ▼
source-native units (rooms, stat blocks, tables, rules)
 │  3  unit classification          deterministic
 ▼
classified units
 │  4  exchange pack assembly       deterministic
 ▼
packs (many units per pack)
 │  5  semantic extraction          MODEL  ← the only bulk model stage
 ▼
CSV fact rows
 │  6  ingest and validation        deterministic
 ▼
durable fact store
 │  7  canonical identity           deterministic + review exceptions
 ▼
identified entities and facts
 │  8  reconciliation               deterministic
 ▼
merged facts + blocking conflicts
 │  9  review escalation            HUMAN  ← low volume, only ambiguity
 ▼
settled fact set
 │ 10  compilation                  deterministic
 ▼
canonical records (places, situations, procedures, actors, effects…)
 │ 11  rendering                    deterministic
 ▼
cards + runtime index + topology
 │ 12  scene resolution             deterministic
 ▼
bounded scene context
```

---

## Stage 1 — Text extraction

**Input:** the source PDF.
**Output:** per-page text, page images, and a source identity record.

A PDF text layer is extracted directly. Page images are rendered separately for
units that need visual context (stat blocks with sidebars, tables, maps).

The source identity record pins the work to a specific file:

```json
{
  "filename": "Module - Lair of the Lamb.pdf",
  "sha256": "3b30ac4e…",
  "pdf_pages": 54,
  "slug": "module-lair-of-the-lamb"
}
```

Every downstream artifact carries this hash. Changing the PDF invalidates
everything derived from it.

**Scanned sources.** A PDF without a usable text layer must fail this stage
explicitly rather than proceed with empty pages. OCR, if added later, sits here
as a preprocessing step and produces the same page text contract. OCR answers
"which characters are visible", never "what do they mean".

**No model is involved.** A parser recovers text objects more faithfully and
more cheaply than a language model can.

---

## Stage 2 — Unit segmentation

**Input:** page text.
**Output:** source-native units with page citations.

The pipeline's unit of work is a **source-native unit** — the thing the author
wrote as one thing:

- a keyed room or area
- an actor entry or stat block
- a rule section
- a random table
- a spell or item entry
- a titled sidebar

Not a page, and not an output type. Pages are an artifact of layout: a single
page routinely carries several keyed areas, and a single area sometimes spans a
page break. Splitting on pages cuts units in half and forces the same text to be
read more than once.

Segmentation is deterministic, driven by typographic and structural signals:

- keyed-area headings (`24 CRUSH HALLWAY`, `12a`, `Area 7`)
- heading case, weight, and size changes
- stat-block and table layout patterns
- list and column structure
- continuation detection across page breaks
- blank pages, covers, credits, and back matter

Each unit records the pages it draws from, so a unit spanning pages 31–32 cites
both.

**Units must not be cut mid-concept.** Where a boundary is uncertain, include
overlapping context rather than guessing. An over-large unit is a cost problem;
a truncated unit is a correctness problem.

**Segmentation is reproducible.** The same PDF and configuration always produce
the same units with the same identifiers. Unit IDs are derived from position and
heading, for example `p31.area24`.

---

## Stage 3 — Unit classification

**Input:** segmented units.
**Output:** each unit labelled with the extraction concerns that apply.

Classification asks a narrow question: *what kind of material is this?* Labels
include `adventure`, `actors`, `items`, `rules`, `tables`, `spells`, `classes`,
`maps`, `illustrations`.

**This stage is deterministic, and segmentation is what makes it so.** Once a
unit has been isolated, the heading that defines it usually classifies it too. A
unit beginning `24 CRUSH HALLWAY` is keyed adventure content. A unit shaped like
a 2d6 table is a table. A unit matching the stat-block template is an actor.
Classifying an entire mixed page is hard; classifying an already-segmented unit
is mostly pattern matching.

Signals used:

- heading grammar and numbering
- stat-block and table templates
- known section titles from the front matter or table of contents
- presence and size of embedded images
- density of dice notation, measurements, and rules vocabulary
- the classification of the preceding unit, for continuations

**Uncertain units are labelled broadly, never excluded.** A false positive costs
some extraction budget. A false negative silently loses source material, and
nothing downstream can detect the loss. When signals conflict, apply every
plausible label.

**Unresolvable units go to a human queue,** not to a model. This queue should be
small; if it is not, segmentation needs fixing rather than the classifier.

---

## Stage 4 — Exchange pack assembly

**Input:** classified units.
**Output:** packs — batches of units prepared for one model interaction.

A pack is a transport container. It bundles units up to a token budget, together
with everything the model needs and nothing else:

```text
pack-007/
  README.md               how to respond
  prompt.md               the extraction instruction
  schema.md               the CSV contract and predicate vocabulary
  units.csv               unit manifest: id, name, pages, labels
  units/
    p28.area21.txt
    p31.area24.txt
    …
  images/
    p31.png               only where a unit needs visual context
```

Pack assembly is deterministic: the same units and budget always produce the
same packs with the same hash.

**Why packs still exist when the unit is the semantic boundary.** The model
reads and answers about one unit at a time, but many units travel together. This
keeps the number of round trips manageable — which matters a great deal when the
transport is manual. Batching is a transport decision; it does not change the
extraction contract, because CSV rows from many units concatenate into one file
without any nesting.

**The pack is disposable.** Once its response is validated and hashed, the pack
can be deleted. It is never part of the module.

---

## Stage 5 — Semantic extraction

**Input:** a pack.
**Output:** CSV fact rows, one block per unit.

This is the only bulk model stage. The model is asked one question:

> What does this unit assert?

It does not decide which card a fact belongs to, does not mint global IDs, does
not build cross-references, and does not write player-facing prose. It reports
what the text says, in rows.

### The CSV contract

**Every row has exactly four fields. Parse by splitting on the first three
commas only.**

```python
col1, col2, col3, col4 = line.split(",", 3)
```

That single rule removes the entire quoting and escaping problem. The fourth
field absorbs everything after the third comma, so prose commas, semicolons,
quotation marks, and embedded JSON all pass through untouched. No escaping is
required, and none should be requested — a model that never has to apply a
quoting rule can never apply it wrongly.

The first three fields are always short controlled-vocabulary tokens: entity
IDs, predicate names, and enumerated values. **They must never contain a comma**,
which ingest verifies against the known vocabulary.

#### Row types

Rows beginning with `#` are structural. All others are facts.

| Row | Shape |
|---|---|
| Unit marker | `#unit,<unit-id>,pages,<page-list>` |
| Entity declaration | `#entity,<local-id>,<kind>,<name>` |
| Option | `#option,<local-id>,<slot>,<text>` |
| Uncertainty | `#uncertain,<local-id>,<about>,<note>` |
| Fact | `<subject>,<predicate>,<visibility>,<value>` |

`visibility` is one of `public`, `hidden`, `discoverable`, or empty. It is the
field that later decides which section of which card a fact reaches.

Local IDs are short and scoped to the unit — `a24`, `ceil`, `trap`. Code expands
them into globally safe identifiers on ingest, so the model never spends tokens
on long names.

#### Example

```text
#unit,p31.area24,pages,31
#entity,a24,place,24 CRUSH HALLWAY
#entity,ceil,mechanism,descending ceiling
#entity,trap,mechanism,disguised trap doors (x3)
#entity,m22,place,22 MUSHROOM
a24,dimensions,,90 ft hallway
a24,visible,public,Thick splinters and wood shards spread around the east side.
a24,contents,public,Crushed furniture debris on the east side.
a24,exit,,{"to":"m22","via":"corridor"}
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

Note what this does *not* contain: no source hashes, no pack IDs, no per-fact
page citations, no global IDs, no schema boilerplate, and no repeated field
names. The runner attaches all of that on receipt, because it already knows it.

#### Values that are genuinely structured

Where a value has parts worth computing with — distances, durations, counts,
exits — the fourth field carries JSON:

```text
ceil,cycle,,{"fall_ft":10,"fall_s":10,"rest_s":10,"then":"reset"}
```

This works precisely because the fourth field is unsplit. Code later renders
such values into prose deterministically: *"The ceiling falls 10 feet in 10
seconds, rests for 10 seconds, then resets."* There is no reason to pay a model
to write that sentence, and no reason to let it write three slightly different
versions.

#### Rules with exactly one free-text field

A row may carry **one** free-text field, and it must be last. Where a concept
needs two pieces of prose, it becomes two rows:

```text
#option,sprint,action,Sprint across
#option,sprint,result,No Movement check for the ceiling; trap doors must be jumped or disabled.
```

This is slightly more verbose and worth it: every row in every response has the
same shape, so validation is a single rule applied uniformly.

### Why rows rather than JSON objects

Measured over a realistic fact table drawn from a full adventure, delimited rows
cost about a third less than the equivalent minified JSON, because column names
stop repeating. Against the same content expressed as pretty-printed JSON
records, the saving is far larger.

Rows also give resumability for free: a response is a sequence of independent
lines, so one bad unit invalidates one block rather than a whole document, and a
retry replaces those lines in place.

The trade is that a row format cannot express nesting. That is affordable here
only because the extraction schema is deliberately flat — subject, predicate,
value — with JSON reserved for the small minority of values that genuinely have
internal structure.

### Transport paths

The extraction contract is identical on every path. Only who calls the model,
and how the response arrives, differs.

**Manual exchange — the default during proof of concept.** The pack is zipped
and handed to a chat model; the reply is saved beside it as
`<pack-id>.csv` and ingested. No API key, no local inference, no marginal cost.
This is why packs batch many units: manual round trips are expensive in human
time, so each one should carry as much work as fits.

**Local model.** A local 8B-class model called per unit by the runner, with
automatic validation and retry. Removes the human from the loop and makes
per-unit calls practical, at the cost of setting up inference and of unproven
quality on this material. The compact CSV contract exists partly to make this
path viable: short outputs with a uniform shape are what small models handle
best.

**Cloud API.** A cheap API model called per unit, with automatic retry and
escalation to a stronger model when a unit repeatedly fails validation. Highest
reliability, at a per-token cost.

**Hybrid.** Automated calls as the default path, with the manual exchange
retained as an escape hatch for units that fail validation repeatedly.

The pipeline should treat the transport as a pluggable runner. Because the pack,
the prompt, the CSV contract, and the validator are all shared, moving between
paths changes no durable data and no downstream stage.

---

## Stage 6 — Ingest and validation

**Input:** a pack response.
**Output:** durable, hash-pinned facts, or a rejection.

Validation is exact and unforgiving. A response is accepted only if:

- every row splits into exactly four fields;
- the first three fields of every row are in the known vocabulary;
- every expected unit appears exactly once, marked by a `#unit` row — the runner
  knows which units it packed, so a missing or duplicated block is detected
  without asking the model to count anything;
- every fact's subject refers to an entity declared in the same unit, or to a
  unit-qualified entity elsewhere;
- every JSON value in a fourth field parses;
- no fact carries mutable campaign or runtime state, which belongs to a
  campaign, never to the immutable module.

On success the runner attaches what the model was not asked to repeat — source
hash, pack ID, unit ID, page citations — expands local IDs, and writes the facts
to durable storage in a rich, self-describing form. **The compact CSV is a wire
format only.** What is stored is verbose, explicit, and easy to audit; only what
crosses the model boundary is compressed.

The accepted response is hashed and pinned. From that point the response file
cannot change without re-ingestion, and the pack itself can be discarded.

**Rejection is per unit.** A failed unit is re-requested on its own; valid units
in the same response are kept. Nothing is repaired automatically. Deterministic
cleanup of transport artifacts — a stray markdown fence, a trailing blank line —
is permitted before parsing, but nothing may invent, alter, or drop content.

---

## Stage 7 — Canonical identity

**Input:** validated facts with unit-local entities.
**Output:** entities resolved to module-scoped canonical identities.

Identity is resolved **before** facts are merged, so that merging keys on
canonical identities rather than on whatever the model happened to call things.

The default policy is deterministic. A canonical ID is built from the entity's
kind, the module slug, and a normalized form of its name:

```text
p31.area24 / a24  "24 CRUSH HALLWAY"
  → place.module-lair-of-the-lamb.24-crush-hallway
```

Entities are grouped by exact name match, by keyed-area number, and through
explicitly confirmed aliases. Collisions between genuinely different entities
that normalize alike are broken by keyed area, or failing that by a content
hash.

**A review overlay records only the exceptions**, each with cited pages and a
written rationale:

- two differently-named entities that are the same thing (`The Lamb` in the
  opening and in the cistern);
- two similarly-named entities that must stay distinct;
- an entity whose keyed area does not correspond to a distinct map node.

Everything the policy handles on its own is left alone. The overlay should stay
small; if it grows large, the policy is wrong and should be fixed rather than
overridden case by case.

---

## Stage 8 — Reconciliation

**Input:** canonically identified facts from every unit.
**Output:** merged facts, plus blocking conflicts.

Facts about the same entity and predicate are grouped. Where every observation
agrees, the fact is settled. Where two units assert different values for the same
entity and predicate, **no value is chosen** — both are preserved as a blocking
conflict.

Last-write-wins is never used. A conflict is evidence that the source is
ambiguous or that the model misread something, and both cases deserve attention
rather than an arbitrary pick.

All observations are retained alongside the merged result, each with its unit,
pages, and originating pack, so any settled value can be traced back to the
sentences that produced it.

Grouping and difference detection require no model. Similarity search may
propose that two differently-named entities are the same, using normalized
names, keyed-area numbers, or reference overlap — but a proposal is not
authority. Merging differently-named entities is an identity decision, and
identity decisions are made in Stage 7 or escalated.

---

## Stage 9 — Review escalation

**Input:** blocking conflicts and identity ambiguities.
**Output:** explicit, cited decisions.

This is the second and much smaller model-or-human boundary. It receives only
the candidate, the conflicting values, and the cited source pages — never the
whole adventure.

Decisions are recorded as explicit operations with provenance:

```json
{
  "object_id": "place.module-lair-of-the-lamb.24-crush-hallway",
  "field": "topology_node",
  "value": null,
  "source_pages": [15, 28, 31],
  "rationale": "The map treats 24 CRUSH HALLWAY as a waypoint feeding several trapdoors and the coffer; the keyed hallway is not a separate place node."
}
```

Never a silent rewrite. The authority may be a human reading the cited passages,
a strong model proposing a cited operation, or a model proposal followed by
human approval — the record looks the same either way.

**Unresolved blocking conflicts prevent release.** A module with open conflicts
can be built as a draft for inspection, but cannot be marked play-ready.

---

## Stage 10 — Compilation

**Input:** the settled fact set.
**Output:** canonical records.

This stage is new in kind: it does the work the model used to do implicitly, and
it does it in code.

A compiler maps facts onto record fields. Facts are **shared, not copied** —
several records project the same fact rather than carrying their own paraphrase
of it:

```text
place 24-crush-hallway
  first_impression  ← a24.dimensions + a24.visible
  contents          ← a24.contents
  discoverable      ← facts with visibility=discoverable
  hidden            ← facts with visibility=hidden
  hazards           ← ceil.cycle + trap.consequence

situation crush-hallway-trap
  activation        ← ceil.activation
  repeat            ← ceil.cycle
  stakes            ← ceil.cycle + trap.consequence

procedure cross-crush-hallway
  steps             ← options sprint, jam, climb, switch
```

Because both the place and the situation project `ceil.activation`, they cannot
disagree about it. Consistency stops being something to verify and becomes
something the structure guarantees.

Every compiled field records which facts produced it, so provenance survives to
the rendered card.

### Reusable records are earned, not assumed

A mechanic becomes its own reusable record only when it is genuinely shared:

- referenced by more than one place or situation, **or**
- part of a named rules vocabulary (`Dying`, `Haste`), **or**
- applied independently by the campaign runtime.

Otherwise it stays a fact inside its unit and is projected directly into the
cards that need it. Promoting every local mechanic to a global record inflates
the module with reference cards that are each used once.

---

## Stage 11 — Rendering

**Input:** canonical records.
**Output:** the runtime module.

```text
module/
  MODULE.md              how to use this module
  index.md               human-readable listing
  index.json             machine-readable runtime index
  topology.yaml          canonical nodes and passages
  GENERATED_OUTPUT.json  manifest: contract version, module hash, file list
  cards/
    places/  situations/  procedures/  actors/  knowledge/  reference/
  audit/
    module.json          the full canonical object
    coverage.md          what was extracted, and what was not
    conflicts-and-gaps.md
    review.md            every escalated decision and its rationale
```

`audit/module.json` is the authoritative artifact. Everything else is a
projection of it, and the whole directory is reproducible from it.

Rendering is templated and involves no model. Structured values become prose
through fixed rules. Cards carry their source pages, their aliases, and the
list of related cards to load with them.

The manifest makes the directory safely replaceable: rendering refuses to
overwrite output it did not generate, and verifies on rewrite that every file
still matches the canonical object.

**Prose polish is an optional, separate pass.** If mechanically rendered text
reads badly in specific places, a stronger model may rewrite those passages —
operating on already-extracted facts, with the original text retained. This is
editing, not extraction, and it never introduces new facts.

---

## Stage 12 — Scene resolution

**Input:** the runtime module and a place identifier.
**Output:** a bounded context bundle.

At the table, the runtime asks for one place. It receives:

```text
the place card
+ metadata for each situation available there
+ explicitly linked procedures, actors, and knowledge
+ the topology node and its adjacent passages
```

Selecting which available situation is *active* is a separate, explicit
decision. Without it the bundle stays at place level. With it, that situation's
own dependencies are added, along with the effects it could apply — flagged as
possible, not applied, because the module describes what can happen and the
campaign records what did.

Resolution refuses to serve a module that is not marked play-ready.

The point of the whole pipeline is this reduction:

```text
fifty-plus source pages
  → one place
  + one situation
  + only their operational dependencies
```

---

## Topology has two sources

Topology — which spaces exist and how they connect — is asserted twice, by two
different media, and the pipeline must treat both as evidence.

**The drawn map.** Floorplans state adjacency, scale, doors, and elevation
directly. Extracting this is image interpretation, not text extraction. It does
not fit the CSV row contract and needs its own path.

**The prose.** Text routinely asserts topology in passing:

> In the room there is a door to the hallway with a bridge.

That sentence establishes a space, a connection, a portal type, and a feature of
the destination. It is an ordinary fact and travels the ordinary path:

```text
a24,exit,,{"to":"hall-b","via":"door"}
hall-b,feature,public,A bridge crosses the hallway.
```

Prose topology is frequently *richer* than the map — it carries door state,
one-way passages, conditions on traversal, and connections a floorplan omits or
draws ambiguously. It is also frequently in tension with the map.

The two sources therefore converge in Stage 8, where a text-asserted passage and
a map-asserted passage about the same pair of nodes are reconciled like any
other pair of observations, and disagreements become blocking conflicts for
Stage 9.

**Open questions on this boundary:**

- Should map extraction produce facts in the same vocabulary as prose topology,
  so both are simply observations, or should it stay a separate typed pipeline
  that reconciliation joins?
- When prose and map disagree, is there a default authority, or is every
  disagreement escalated?
- Prose often names spaces the map does not label, and vice versa. What
  establishes that a prose-named space and a map node are the same node?
- Can useful topology be recovered from prose alone for adventures whose maps
  are unusable, and is a text-only topology worth shipping?
- Should a keyed area that text describes but the map treats as a waypoint own a
  topology node? The answer affects navigation and needs a stated rule rather
  than a per-case decision.

---

## Where models are used

| Stage | Work | Model? |
|---|---|---|
| 1 | Text extraction | No — parser |
| 2 | Unit segmentation | No — typographic rules |
| 3 | Unit classification | No — pattern matching, human queue for the rest |
| 4 | Pack assembly | No |
| 5 | **Facts from prose** | **Yes — the only bulk model stage** |
| 6 | Ingest and validation | No |
| 7 | Canonical identity | No, except recorded exceptions |
| 8 | Reconciliation | No |
| 9 | Conflict and identity decisions | Human, optionally model-assisted — low volume |
| 10 | Compilation | No |
| 11 | Rendering | No, except optional prose polish |
| 12 | Scene resolution | No |

```text
HIGH VOLUME                        LOW VOLUME
every source unit                  only genuine ambiguity
cheap or local model               human, optionally model-assisted
produces facts                     produces cited decisions
```

There is no reason to send an entire adventure through a frontier model, and no
reason to send already-structured facts to a model merely to format them.

---

## Failure handling

| Failure | Response |
|---|---|
| PDF has no text layer | Fail Stage 1 explicitly |
| Unit boundary uncertain | Include overlapping context |
| Unit classification uncertain | Apply every plausible label |
| Unit classification impossible | Human queue |
| Malformed CSV row | Reject that unit, retry it alone |
| Unit block missing from response | Detected against the known pack manifest, retried |
| Unparseable JSON in a value | Reject that unit |
| Model asserts campaign state | Reject — modules are immutable |
| Two units disagree | Blocking conflict, escalated |
| Conflicts unresolved | Draft build permitted, release blocked |
| Rendering mismatch | Refuse to write, report the discrepancy |

Retry granularity is the unit throughout. A single bad room never costs a whole
pack, and never costs the run.

---

## Open questions

**Extraction contract**

- Is the predicate vocabulary closed, or may the model coin predicates that
  ingest then reconciles? A closed vocabulary is verifiable; an open one adapts
  to unfamiliar rulesets.
- How reliably do models follow the "four fields, free text last, never escape
  anything" rule in practice? The rule is verifiable on data; model compliance
  with it is not yet known and should be measured on a prototype before the
  format is committed to.
- Which values deserve structured JSON rather than prose, and who decides —
  the schema, or the model?

**Compilation**

- Is one fact-to-field mapping enough across rulesets, or is the mapping
  per-system?
- Do compiled cards read acceptably? Deriving several fields from one shared
  fact risks making a card repetitive where hand-written variants read better.
  This is the load-bearing assumption of the whole design and needs a
  side-by-side prototype on a handful of rooms.

**Segmentation**

- How well do typographic rules segment adventures with unconventional layout —
  multi-column, boxed text, marginalia, poetry?
- What is the fallback when segmentation clearly fails on a document: manual
  unit boundaries, or per-page units as a degraded mode?

**Topology** — see [Topology has two sources](#topology-has-two-sources).
