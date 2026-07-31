# What happens to adventure text

This is a data-lineage walkthrough: one piece of *Lair of the Lamb* prose is
followed from the PDF to the final runtime artifacts.

The important distinction is:

```text
source text
  → chunks of source text
  → semantic observations
  → canonically identified observations
  → reconciled and reviewed records
  → rendered cards and runtime index
  → bounded scene context
```

The text is not repeatedly summarized. Each transformation gives the same
source material more structure.

## Step 1: extract text from the PDF

Input:

```text
Module - Lair of the Lamb.pdf
```

`module_extractor.preparation` shells out to poppler (`pdfinfo`, `pdftotext
-layout`, `pdftoppm`) and produces:

```text
.module-extractor-cache/
  source.pdf
  source.json
  prepared.json
  text/
    layout.txt
    pages/
      page-0001.txt
      ...
      page-0031.txt
      ...
      page-0054.txt
  thumbnails/
    page-0001.png
    ...
```

`layout.txt` is the whole document in one file; the per-page files are split
from it on form feeds, and the split is checked against the `pdfinfo` page
count. There is no OCR path in the current implementation: a scanned PDF passes
the page-count check and yields empty page text rather than triggering image
recognition. OCR appears below only as a recommendation.

The page files contain text, not semantic JSON. A representative portion of
`page-0031.txt` would look roughly like this:

```text
24 CRUSH HALLWAY

A 90' hallway. Thick splinters and wood shards are spread around the east
side. Any touch greater than a feather triggers the ceiling. It takes 10
seconds to fall 10', rests for 10 seconds, then resets.

Three perfectly disguised trap doors are driven by hinges and strong springs.
They drop victims 40' into the water below. A human can sprint across before
the ceiling crushes them, but must jump the trap doors unless they have been
disabled.

Other possibilities include jamming the ceiling with an uncrushable object or
climbing along the wall with spikes and ropes.
```

This is a **reconstruction** from the checked-in extracted evidence, not a
verbatim transcription: the disposable page-text cache is no longer present in
this checkout.

At this stage the program knows:

- these characters came from physical PDF page 31;
- their order and approximate layout;
- the source PDF hash.

It does **not** yet know that this text describes a place, a trap situation,
several effects, and a traversal procedure.

Durable source identity is stored as:

```json
{
  "filename": "Module - Lair of the Lamb.pdf",
  "pdf_pages": 54,
  "sha256": "3b30ac4e2937da1f827f66f28c7a47d4c6ed6784e36a6363b042ac8575621bda",
  "slug": "module-lair-of-the-lamb"
}
```

## Step 2: classify the page

The routing pass does not extract adventure facts. It only decides which
later extractors should see the page.

In the current implementation routing is itself a model task, not deterministic
code: `prepare` writes `_exchange/routing.zip`, that ZIP is uploaded to
ChatGPT, and the reply is saved back as `_exchange/routing.json` and ingested
into `module-input/routing.json` (`module-routing/v1`). The recommendation
below — deterministic rules first, model only for ambiguous pages — is not what
is built today.

For page 31, the actual routing record is:

```json
{
  "confidence": "high",
  "exclusion_reason": null,
  "notes": "Room 24 and side areas with flooded hazards and fungal wall art.",
  "pdf_page": 31,
  "tasks": [
    "adventure",
    "maps",
    "effects",
    "illustrations"
  ]
}
```

The text pipeline keeps the `adventure` and `effects` assignments. The map and
illustration assignments go to other pipelines.

Data transformation:

```text
page 31 text
  +
["adventure", "effects"]
```

No source text has been rewritten or discarded yet.

## Step 3: split the page stream into extraction chunks

The current implementation groups contiguous routed pages into content packs.
Page 31 is part of the actual pack:

```json
{
  "pack_id": "content.007",
  "physical_pages": [28, 29, 30, 31, 32, 33, 34, 35],
  "tasks": ["adventure", "effects", "items", "tables"],
  "page_tasks": [
    {"pdf_page": 30, "tasks": ["adventure", "effects"]},
    {"pdf_page": 31, "tasks": ["adventure", "effects"]},
    {"pdf_page": 32, "tasks": ["adventure", "effects", "items"]}
  ]
}
```

The omitted rows follow the same shape; each real `page_tasks` row also carries
a `context_reason` (`null` unless the page was pulled in only for context). The
stored pack additionally records `pack_sha256`, `text_bytes`,
`archive_path` (`../_exchange/content.007.zip`), `response_path`, and — once
ingested — `ingested_response_sha256`.

The disposable model handoff is exactly:

```text
_exchange/content.007.zip
  README.md
  prompt.md
  response-template.json
  pack.json
  pages/
    page-0028.txt
    ...
    page-0031.txt
    ...
    page-0035.txt
  thumbnails/
    ...
```

This pack is only a transport container. It does not become part of the final
module. Today the whole ZIP is handed to one ChatGPT conversation, and the
whole reply is saved as `_exchange/content.007.json` — the pack is the unit of
the model call.

For automated extraction, this pack should be internally divided into smaller
**model-call shards**. For example:

```json
{
  "parent_pack": "content.007",
  "shard_id": "content.007.page-0031.adventure",
  "pdf_pages": [31],
  "task": "adventure",
  "text": "24 CRUSH HALLWAY ...",
  "context": [
    "last heading or continuation from page 30",
    "first heading or continuation from page 32"
  ]
}
```

and:

```json
{
  "parent_pack": "content.007",
  "shard_id": "content.007.page-0031.effects",
  "pdf_pages": [31],
  "task": "effects",
  "text": "24 CRUSH HALLWAY ..."
}
```

These shards do not exist as a durable contract in the current implementation;
they are the recommended unit for local 8B or cheap API calls. Several shard
results are merged back into one valid `content.007.json`.

What splitting changes:

- it copies the same page text into one or more task-specific requests;
- it narrows what each request is allowed to produce;
- it preserves the physical page citation and parent pack identity.

What splitting must not do:

- cut a keyed room halfway through;
- remove a continuation needed to understand a sentence;
- decide semantic facts before the semantic extractor runs.

## Step 4: run semantic extraction

The semantic model receives page text and a schema (today: the whole pack, one
call; under the sharding recommendation: one page/task shard per call). It
converts prose into typed **observations**.

For page 31 under the `adventure` task, it identifies that the prose contains at
least three different operational concepts:

```text
location:  24 CRUSH HALLWAY
situation: the hallway trap activating
procedure: ways to cross the hallway
```

Under the `effects` task, it identifies:

```text
effect: the ceiling cycle
effect: the trapdoor fall
```

The actual checked-in location observation is:

```json
{
  "id": "location.24-crush-hallway",
  "record_type": "location",
  "fields": {
    "title": "24 CRUSH HALLWAY",
    "keyed_area": "24 CRUSH HALLWAY",
    "first_impression": "A 90' hallway has thick splinters and wood shards spread around its east side.",
    "contents": [
      "Crushed furniture debris on the east side."
    ],
    "discoverable": [
      {
        "information": "Three perfectly disguised trap doors sound hollow.",
        "condition": "Tap the floor to listen for hollow sections."
      }
    ],
    "hidden": [
      "Any contact heavier than a feather triggers the descending ceiling.",
      "Each disguised trap door is driven by a hinge and strong spring."
    ],
    "triggers": [
      "Entering the hallway or applying more than feather-light contact starts the ceiling's lowering cycle."
    ],
    "hazards": [
      "The ceiling falls 10' in 10 seconds, rests for 10 seconds, then resets.",
      "Three disguised spring trap doors drop victims 40' to water below."
    ],
    "situation_references": [
      "situation.crush-hallway-trap"
    ],
    "procedure_references": [
      "procedure.cross-crush-hallway",
      "procedure.disarm-crush-hallway-trapdoors"
    ]
  },
  "source_pages": [31],
  "confidence": "high",
  "references": [
    "situation.crush-hallway-trap",
    "procedure.cross-crush-hallway",
    "procedure.disarm-crush-hallway-trapdoors",
    "effect.crush-hallway-ceiling",
    "effect.crush-hallway-trapdoor-fall"
  ],
  "uncertainties": []
}
```

The same prose also becomes a separate situation:

```json
{
  "id": "situation.crush-hallway-trap",
  "record_type": "situation",
  "fields": {
    "title": "24 CRUSH HALLWAY Trap",
    "perceived": "After someone enters the 90' hall, the ceiling begins descending toward the floor; hidden floor panels can spring open beneath runners.",
    "activation": {
      "type": "triggered",
      "condition": "Any touch greater than a feather in the hallway triggers the ceiling; stepping on a trap door triggers that floor panel."
    },
    "repeat": {
      "mode": "repeatable",
      "condition": "The ceiling falls, rests, and resets; trap doors remain active unless their remote switches are held."
    },
    "location_references": [
      "location.24-crush-hallway"
    ],
    "procedure_references": [
      "procedure.cross-crush-hallway",
      "procedure.disarm-crush-hallway-trapdoors"
    ],
    "stakes": [
      "Entrants can be crushed by the ceiling.",
      "Runners can fall 40' through one of three disguised trap doors into the water chambers."
    ],
    "outcomes": [
      "A human can sprint the length without a Movement check for the ceiling.",
      "Movement checks are needed to jump the three trap doors unless disabled.",
      "The ceiling takes 10 seconds to fall 10', rests for 10 seconds, then resets."
    ]
  },
  "source_pages": [31],
  "confidence": "high",
  "references": [
    "location.24-crush-hallway",
    "procedure.cross-crush-hallway",
    "procedure.disarm-crush-hallway-trapdoors",
    "effect.crush-hallway-ceiling",
    "effect.crush-hallway-trapdoor-fall"
  ],
  "uncertainties": []
}
```

The crossing instructions become a procedure:

```json
{
  "id": "procedure.cross-crush-hallway",
  "record_type": "procedure",
  "fields": {
    "title": "Cross 24 CRUSH HALLWAY",
    "trigger": "The party attempts to traverse the 90' crushing hallway.",
    "steps": [
      "A human can sprint across before the ceiling crushes without a Movement check, but Movement checks are required to jump the three disguised trap doors unless those doors are disabled.",
      "Alternatively, throw an uncrushable object such as the metal cage, ballista, or a combination of sturdy objects into the hallway; those objects are not recoverable.",
      "Alternatively, climb along the wall with iron spikes and ropes; this takes about an hour and causes a couple of encounter checks.",
      "Alternatively, disable the trap doors from 22 MUSHROOM and then sprint across."
    ]
  },
  "source_pages": [31],
  "confidence": "high",
  "references": [
    "location.24-crush-hallway",
    "procedure.disarm-crush-hallway-trapdoors"
  ],
  "uncertainties": []
}
```

The mechanical statements become two effect records:

```json
[
  {
    "id": "effect.crush-hallway-ceiling",
    "record_type": "effect",
    "fields": {
      "title": "Crush Hallway Ceiling Cycle",
      "text": "Any touch greater than a feather triggers the ceiling in 24 CRUSH HALLWAY. It takes 10 seconds to fall 10', rests for 10 seconds, then resets."
    },
    "source_pages": [31],
    "confidence": "high",
    "references": [
      "location.24-crush-hallway",
      "situation.crush-hallway-trap"
    ],
    "uncertainties": []
  },
  {
    "id": "effect.crush-hallway-trapdoor-fall",
    "record_type": "effect",
    "fields": {
      "title": "Crush Hallway Trap-Door Fall",
      "text": "Each of the three disguised spring trap doors in 24 CRUSH HALLWAY drops a victim 40' to the water below."
    },
    "source_pages": [31],
    "confidence": "high",
    "references": [
      "location.24-crush-hallway",
      "situation.crush-hallway-trap"
    ],
    "uncertainties": []
  }
]
```

The model has not created final cards. It has created source-cited claims about
what page 31 says.

## Step 5: ingest and validate the pack response

The saved reply — one file per pack, whether it came from one call or several
merged shard calls — is ingested as:

```text
module-input/responses/content.007.json
```

The outer object identifies the source and parent pack:

```json
{
  "schema": "module-content-evidence/v3",
  "source_sha256": "3b30ac4e2937da1f827f66f28c7a47d4c6ed6784e36a6363b042ac8575621bda",
  "pack_id": "content.007",
  "task": "content",
  "records": [
    "...records from pages 28–35..."
  ],
  "task_coverage": [
    {
      "pdf_page": 31,
      "task": "adventure",
      "status": "extracted",
      "record_ids": [
        "location.24-crush-hallway",
        "situation.crush-hallway-trap",
        "procedure.cross-crush-hallway"
      ]
    },
    {
      "pdf_page": 31,
      "task": "effects",
      "status": "extracted",
      "record_ids": [
        "effect.crush-hallway-ceiling",
        "effect.crush-hallway-trapdoor-fall"
      ]
    }
  ]
}
```

The real response contains more records and the complete coverage lists — each
coverage row also carries a `notes` string, and page 31's `adventure` row also
claims `location.24a`, `location.24b`, `location.24c`, while its `effects` row
also claims `effect.oil-layer-burning`. The example is reduced to the hallway.

At this boundary, local validation checks that:

- every expected page/task pair has a coverage row;
- listed records exist and cite the relevant page;
- records have the required fields for their type;
- IDs and references are structurally valid;
- the model did not insert forbidden campaign state.

If valid, the exact response hash is recorded as `ingested_response_sha256` in
`module-input/packs.json`. Once that hash exists the ZIP may be missing on
later runs, so the ZIP and any temporary model-call shards can be discarded —
this checkout has already done so. From then on the ingested response file is
pinned: editing `responses/content.007.json` without re-ingesting fails with
`response changed after ingest`.

The durable data is now:

```text
module-input/
  source.json
  routing.json
  packs.json
  review.json
  responses/
    content.001.json … content.011.json
    map.v2.001.json
```

## Step 6: convert provisional identities into canonical identities

Identity runs **before** grouping, not after: `evaluate()` calls
`apply_identity_review` on the ingested observations and only then hands the
rewritten observations to `reconcile_records`. Grouping therefore keys on
canonical IDs, never on the raw extracted ones.

The extracted IDs are scoped only by type and source wording:

```text
location.24-crush-hallway
situation.crush-hallway-trap
procedure.cross-crush-hallway
```

These become module-scoped canonical IDs:

```text
location.24-crush-hallway
  → place.module-lair-of-the-lamb.24-crush-hallway

situation.crush-hallway-trap
  → situation.module-lair-of-the-lamb.24-crush-hallway-trap

procedure.cross-crush-hallway
  → procedure.module-lair-of-the-lamb.cross-24-crush-hallway
```

None of those three mappings is written down anywhere. They are **derived
deterministically** by `identity._default_base`: alias-connected observations
are unioned into a component, and the canonical ID is
`<prefix>.<module-slug>.<slug of the alphabetically first normalized title>`.
`Cross 24 CRUSH HALLWAY` is why the procedure gains the `24` its extracted ID
lacked. Collisions between two unrelated components are broken with a
`-area-<n>` or hash suffix. Only the six types in `CANONICAL_PREFIXES`
(`location`→`place`, `actor`, `situation`, `knowledge`, `procedure`, `item`)
are rewritten — which is why the effects keep bare IDs like
`effect.crush-hallway-ceiling` all the way to their cards.

`module-input/review.json` (`module-review-overlay/v3`) holds only the
**exceptions** to that policy, and for this module it is very small: one
`canonical_ids` entry and one `aliases` entry, both about `actor.the-lamb`
being the same creature across pages 16–41. The hallway needs neither. What the
review file does say about the hallway is that two procedures must *not* be
merged:

```json
{
  "left_id": "procedure.cross-crush-hallway",
  "right_id": "procedure.disarm-crush-hallway-trapdoors",
  "source_pages": [30, 31],
  "rationale": "Crossing the 90-foot crush hallway and disarming its three spring trapdoors are distinct procedures with different approaches and outcomes."
}
```

## Step 7: reconcile repeated observations and resolve conflicting values

Page 31 is not the only place that mentions this trap.

For example, page 30 describes switches in `22 MUSHROOM` that disable the three
trapdoors. Another section describes the water chambers underneath. Those
pages produce their own records and references.

`reconcile_records` groups observations by canonical `concept_id` and, for each
field, keeps every observation's value alongside the merged record:

```json
{
  "id": "procedure.module-lair-of-the-lamb.disarm-the-trap-doors-in-24-crush-hallway",
  "record_type": "procedure",
  "fields": {
    "trigger": "A character uses the three wall holes in 22 MUSHROOM."
  },
  "field_observations": {
    "trigger": [
      {
        "value": "A character uses the three wall holes in 22 MUSHROOM.",
        "source_pages": [30],
        "confidence": "high",
        "pack_id": "content.007",
        "observation_id": "observation.content.007.procedure.disarm-crush-hallway-trapdoors"
      }
    ]
  },
  "source_pages": [30],
  "observation_ids": [
    "observation.content.007.procedure.disarm-crush-hallway-trapdoors"
  ],
  "extracted_ids": ["procedure.disarm-crush-hallway-trapdoors"],
  "references": [
    "place.module-lair-of-the-lamb.22-mushroom",
    "place.module-lair-of-the-lamb.24-crush-hallway"
  ]
}
```

The `steps` and `title` fields are omitted here; they carry the same shape.
Note that `references` have already been rewritten to canonical IDs, because
identity ran first.

A field collapses into `fields` only when every non-null observation of it
agrees. If two packs disagree, no value is chosen: both are emitted as a
separate conflict object with `"blocking": true`, which stops the release gate
until a human settles it. Reconciliation does not use last-write-wins.

This module raises 45 such conflicts, all of them currently resolved. They are
settled by `values` entries in `review.json` — the largest section of that
file, 63 entries — which `apply_review` overlays onto the reconciled records.
That is also where a decision like the hallway's topology identity is recorded:

```json
{
  "object_id": "place.module-lair-of-the-lamb.24-crush-hallway",
  "field": "topology_node",
  "value": null,
  "source_pages": [15, 28, 31],
  "rationale": "The map classifies 24 CRUSH HALLWAY as a waypoint feeding several trapdoors and the coffer; the keyed hallway card is not a separate place node."
}
```

`null` does not mean that the place disappeared. It means that text produced a
useful place card, while review decided it should not own a distinct canonical
map node.

## Step 8: build the canonical module object

The program combines:

```text
source identity
+ routing
+ pack hashes
+ all content observations
+ map observations
+ reconciliation results
+ review decisions
+ coverage
```

into:

```text
module/audit/module.json
```

built under a `profile` of `draft` or `release`; this checkout holds a
`release` build of `operational-module/v3` whose `release_gate` passed with no
errors. The object pins itself and its inputs by hash: `review_sha256` over the
review overlay and `module_sha256` over everything else. Three Markdown audit
reports are written beside it (`coverage.md`, `conflicts-and-gaps.md`,
`review.md`).

For the hallway, the canonical object now contains:

- the reviewed place record;
- the reviewed situation;
- the crossing and disarming procedures;
- the two effects;
- aliases back to extracted IDs;
- source-page citations;
- the explicit `topology_node: null` decision;
- raw observations and review provenance.

This file is the authoritative final data artifact. The Markdown cards below
are projections of it.

## Step 9: render separate runtime cards

The canonical place becomes:

```text
module/cards/places/
  place.module-lair-of-the-lamb.24-crush-hallway.md
```

Its data is reorganized for use at the table. This is the actual file, in full:

```markdown
---
id: "place.module-lair-of-the-lamb.24-crush-hallway"
type: "place"
title: "24 CRUSH HALLWAY"
aliases: ["location.24-crush-hallway"]
source_pages: [31]
verification: verified
references: ["effect.crush-hallway-ceiling", "effect.crush-hallway-trapdoor-fall", "procedure.module-lair-of-the-lamb.cross-24-crush-hallway", "procedure.module-lair-of-the-lamb.disarm-the-trap-doors-in-24-crush-hallway", "situation.module-lair-of-the-lamb.24-crush-hallway-trap"]
topology_node: null
load_with:
  actors: []
  situations: ["cards/situations/situation.module-lair-of-the-lamb.24-crush-hallway-trap.md"]
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.cross-24-crush-hallway.md", "cards/procedures/procedure.module-lair-of-the-lamb.disarm-the-trap-doors-in-24-crush-hallway.md"]
  knowledge: []
---

# 24 CRUSH HALLWAY

## First impression

A 90' hallway has thick splinters and wood shards spread around its east side.

## Contents

- Crushed furniture debris on the east side.

## Discoverable

- **Tap the floor to listen for hollow sections.** — Three perfectly disguised trap doors sound hollow.

## Hidden

- Any contact heavier than a feather triggers the descending ceiling.
- Each disguised trap door is driven by a hinge and strong spring.

## Triggers

- Entering the hallway or applying more than feather-light contact starts the ceiling's lowering cycle.

## Hazards

- The ceiling falls 10' in 10 seconds, rests for 10 seconds, then resets.
- Three disguised spring trap doors drop victims 40' to water below.

## Resources


## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->
```

Note that the section headings are fixed by the template: `Resources` is
rendered empty rather than dropped, and `Exits` is deliberately left to
`topology.yaml` instead of being duplicated into the card.

The event data becomes a different file:

```text
module/cards/situations/
  situation.module-lair-of-the-lamb.24-crush-hallway-trap.md
```

The choices for crossing become:

```text
module/cards/procedures/
  procedure.module-lair-of-the-lamb.cross-24-crush-hallway.md
  procedure.module-lair-of-the-lamb.disarm-the-trap-doors-in-24-crush-hallway.md
```

The reusable mechanics become:

```text
module/cards/reference/
  effect.crush-hallway-ceiling.md
  effect.crush-hallway-trapdoor-fall.md
```

Thus one prose section fans out into five kinds of data:

```text
page-0031.txt
  ├─ place card
  ├─ situation card
  ├─ crossing procedure
  ├─ ceiling effect
  └─ trapdoor effect
```

No LLM is involved in rendering these Markdown files. They are deterministic
views of the canonical JSON.

## Step 10: create index and load relationships

Beside the cards, the renderer also writes:

```text
module/MODULE.md            how to use the module at the table
module/index.md             human-readable card listing
module/index.json           machine-readable runtime index
module/topology.yaml        canonical map nodes and passages
module/GENERATED_OUTPUT.json  manifest: play_contract, module_sha256, file list
```

`GENERATED_OUTPUT.json` is what makes the whole directory replaceable: the
renderer refuses to overwrite a `module/` it did not generate, and verifies on
rewrite that every file still matches the canonical module.

`index.json` does not duplicate all prose. It records how to locate and load
the records:

```json
{
  "id": "place.module-lair-of-the-lamb.24-crush-hallway",
  "path": "cards/places/place.module-lair-of-the-lamb.24-crush-hallway.md",
  "topology_node": null,
  "load_with": {
    "situations": [
      "cards/situations/situation.module-lair-of-the-lamb.24-crush-hallway-trap.md"
    ],
    "procedures": [
      "cards/procedures/procedure.module-lair-of-the-lamb.cross-24-crush-hallway.md",
      "cards/procedures/procedure.module-lair-of-the-lamb.disarm-the-trap-doors-in-24-crush-hallway.md"
    ]
  }
}
```

The real record additionally carries `type`, `title`, `aliases`, and
`references`; the index as a whole is `{"schema": ..., "records": [...]}`.

## Step 11: resolve a bounded scene at runtime

When the GM or runtime asks for:

```text
python3 module-extractor/cli.py status \
  --scene place.module-lair-of-the-lamb.24-crush-hallway
```

`resolve_scene` first refuses to serve a module that is not play-ready: it
requires `GENERATED_OUTPUT.json` to declare `play_contract: module-play/v1` and
`verification: verified`. It then follows the index and returns:

```text
place card
+ available situation metadata (id, title, path, activation, repeat)
+ explicitly linked procedures, actors, and knowledge
+ topology node and adjacent passages, if any
+ a file list with byte sizes
```

Selecting the active situation is a separate, explicit runtime decision: with
no `--situation`, `active_situation` stays `null` and the bundle remains at
place level. Passing `--situation` adds that situation's own dependencies plus
its `possible_effects`, flagged `"applied": false` — the bundle names what could
happen without asserting that it has. For the hallway the resolved bundle is
four files: the place card, the trap situation, and the two procedures. Effect
cards under `cards/reference/` are not pulled in.

The runtime receives neither the entire PDF nor the
entire `module/audit/module.json`.

So the final transformation is:

```text
hundreds of source pages
  → one selected place
  + one selected situation
  + only their operational dependencies
```

## Which steps actually require an LLM?

The answer depends on what “require” means:

- Some steps require no semantic judgment and should always be ordinary code.
- Some steps require semantic judgment, but a human could perform it.
- Only one bulk step benefits enough from an LLM to make automated extraction
  practical: converting prose into typed observations.

The `Today` column is what the code does now; the last column is the
recommendation.

| Step | Operation | LLM required? | Today | Correct implementation |
| --- | --- | --- | --- | --- |
| 1 | PDF text extraction | No | poppler, no LLM | PDF parser; OCR only for scanned text |
| 2 | Page routing | Usually no | ChatGPT via `routing.zip` | Deterministic rules first; optional cheap classifier for ambiguous pages |
| 3 | Pack creation | No | deterministic code | Deterministic code using page boundaries, headings, byte/token budgets |
| 4 | Prose → semantic records | Yes for practical automation | ChatGPT, one call per pack | Local or API LLM with a strict schema and bounded source |
| 5 | Ingest and validate responses | No | deterministic code | Deterministic schema, coverage, citation, and reference checks |
| 6 | Canonical identity | Sometimes | deterministic policy + human `review.json` exceptions | Deterministic easy cases; human or strong LLM for genuine ambiguity |
| 7 | Group observations, resolve values | No for grouping; sometimes for conflicts | deterministic grouping + human `review.json` values | Deterministic grouping and conflict detection; defer meaning-changing decisions |
| 8 | Build canonical audit object | No | deterministic code | Deterministic assembly |
| 9 | Render cards | No | deterministic code | Deterministic templates |
| 10 | Build index and load relationships | No | deterministic code | Deterministic reference resolution |
| 11 | Resolve a runtime scene bundle | No | deterministic code | Deterministic graph/index traversal |

### Step 1 does not need an LLM

Born-digital PDFs already contain text objects. A PDF parser can recover them
more faithfully and cheaply than a language model.

For scanned pages, OCR is needed, but OCR is not an LLM in this architecture.
OCR answers “which characters are visible?” It does not decide what those
characters mean operationally.

An LLM may repair a rare damaged heading or column-order ambiguity, but that is
an exception queue. It should not sit in the normal text-extraction path.

### Step 2 usually does not need an LLM

Routing asks a limited classification question:

```text
Does this page contain keyed adventure material, rules, tables, items,
spells, classes, effects, maps, or illustrations?
```

Much of this can be routed from deterministic signals:

- headings such as `24 CRUSH HALLWAY`;
- repeated stat-block or table formatting;
- known chapter headings;
- the presence of large raster/vector images;
- blank-page and cover detection;
- continuation from the preceding routed page.

A small classifier—possibly a conventional text classifier rather than a
generative model—can handle the uncertain remainder. An LLM is convenient
while developing the router, but it is not intrinsically required.

The safe design is:

```text
deterministic routing
  → confidence check
  → optional cheap-model classification for ambiguous pages
  → human review only for unresolved pages
```

Routing errors are costly because a false negative can hide source material.
Therefore uncertain pages should be routed too broadly, not excluded.

### Step 3 does not need an LLM

Once routing is known, code can create packs and shards from:

- physical page boundaries;
- headings and paragraph boundaries;
- continuation markers;
- task labels;
- byte, token, and output budgets.

An LLM should not choose arbitrary chunk boundaries. Chunking must be
reproducible: the same PDF, routing, and configuration should produce the same
shards.

The only semantic complication is keeping a logical unit intact across page
boundaries. Most cases can be detected using headings and continuations. If
not, include overlapping context instead of asking another LLM to plan the
split.

### Step 4 is the real bulk LLM task

This transformation cannot be implemented reliably with PDF parsing, OCR,
regular expressions, or embeddings alone:

```text
"Any touch greater than a feather triggers the ceiling..."

  →

location.hidden
situation.activation.condition
situation.repeat
effect.text
procedure constraints
cross-record references
```

The source does not explicitly label those schema fields. The extractor must
interpret meaning, separate player-visible and GM-only information, identify
events and procedures, preserve conditions, and infer which statements refer
to the same concept.

A human could do this, so an LLM is not logically necessary. But for processing
many adventures automatically, this is the step where an LLM is practically
required.

The model should produce **observations**, not final canonical truth. Its work
remains bounded, cited, validated, and replaceable.

This is also the only stage that should generate a large number of model calls:

```text
one page/task shard
  → one semantic extraction call
  → zero or more typed observations
```

For easy prose, a local 8B model or cheap API model may be adequate. Failed
validation, low confidence, or difficult prose can be escalated to a stronger
model.

### Step 5 does not need an LLM

Merging JSON arrays, checking schemas, verifying page citations, ensuring total
coverage, and hashing accepted responses are exact operations.

An LLM must not “fix” structurally invalid JSON after ingestion. Reject the
small shard and retry it. Otherwise the repair step could silently change the
meaning without source accountability.

Limited syntax repair may be used before validation—for example, removing a
Markdown fence around otherwise exact JSON—but it should be deterministic and
must never invent fields or content.

### Step 6 sometimes requires semantic reasoning

Canonical identity includes two kinds of decisions.

Easy decisions are deterministic, and the implementation already handles them
without any review input:

- an exact ID repeated across packs;
- a canonical slug derived from the record's own title;
- references resolved through an already confirmed alias;
- a unique keyed-area number with no conflict.

Ambiguous decisions require source interpretation, and are exactly what
`review.json` records:

- `The Lamb` records that might describe the same creature or different forms;
- `Shawson` versus `Shawson the Ghoul`;
- whether a keyed textual area corresponds to a place node, waypoint, or no
  distinct map node;
- two similarly named procedures that must stay `distinct`.

These decisions require a reasoner, but not necessarily an LLM. The authority
can be:

1. a human reviewing cited passages;
2. a strong model such as Codex proposing a source-cited review operation;
3. a strong model proposal followed by human approval.

The model should receive only the candidate, conflicting values, and cited
source pages—not the whole adventure. The result is an explicit
`review.json` operation with provenance, never a silent rewrite.

For this module that workload really is small: two identity entries and 38
`distinct` assertions against 649 content observations that collapse into 613
canonical records.

### Step 7 is mostly deterministic

Grouping records that resolved to the same canonical ID requires no model:

```text
actor.shawson + actor.shawson → one observation group
```

Comparing field values and detecting that they differ also requires no model:

```text
value A != value B → blocking conflict
```

Similarity search can propose duplicate candidates using normalized names,
keyed-area numbers, reference overlap, or embeddings. Embeddings may come from
a model, but they are only a search optimization; they do not authorize a
merge.

Choosing *which* conflicting value is right is the one part of this step that
needs a reasoner, and it uses the same `review.json` channel as Step 6:
45 conflicts here, settled by cited `values` entries.

Consequently this is a **small exception workload**, not another full
extraction pass.

### Steps 8–11 do not need an LLM

After canonical decisions exist, everything else is data processing:

```text
reviewed records
  → validate references
  → assemble canonical JSON
  → render templates
  → construct index
  → traverse dependencies for a requested scene
```

Putting an LLM in these stages would make identical inputs produce
non-identical outputs and would weaken validation. These operations should be
deterministic and covered by tests.

An LLM may later **consume** the bounded scene bundle to act as the GM. That is
runtime gameplay, not module extraction.

### Minimal model architecture

The leanest reliable design is:

```text
ordinary local code
  Step 1: extract page text
  Step 2: route obvious pages
  Step 3: create deterministic shards

cheap/local LLM
  Step 4: turn each text shard into typed observations

ordinary local code
  Step 5: merge, validate, and retry failures
  Step 6: apply the deterministic canonical ID policy
  Step 7: group observations and generate conflict candidates

strong LLM or human
  Steps 6–7 exceptions only: genuine identity questions and
  blocking value conflicts, written into review.json

ordinary local code
  Steps 8–11: assemble, render, index, and load
```

This gives us one high-volume model boundary and one low-volume escalation
boundary:

```text
HIGH VOLUME                         LOW VOLUME
every semantic text shard           only ambiguous candidates
cheap/local model                    strong model or human
produces observations                produces review decisions
```

There is no reason to run the entire adventure through a frontier model. There
is also no reason to send already structured records to an LLM merely to turn
them into Markdown.

## Complete data lineage

```text
Module - Lair of the Lamb.pdf
  │
  ├─ pdftotext -layout (no OCR path today)
  ▼
.module-extractor-cache/text/pages/page-0031.txt
  │
  ├─ routing adds task labels (model task today)
  ▼
routing.json: page 31 → adventure, effects, maps, illustrations
  │
  ├─ content packer copies relevant text
  ▼
_exchange/content.007.zip: pages 28–35
  │
  ├─ optional API/local-runner sharding (not implemented)
  ▼
page-0031.adventure + page-0031.effects
  │
  ├─ LLM semantic extraction
  ▼
location + situation + procedures + effects
  │
  ├─ ingest, validate, pin response hash
  ▼
module-input/responses/content.007.json
  │
  ├─ canonical identity (deterministic + review exceptions)
  ├─ cross-pack reconciliation and conflict detection
  ├─ review value overlay
  ▼
reviewed operational records
  │
  ├─ deterministic assembly
  ▼
module/audit/module.json
  │
  ├─ deterministic rendering
  ▼
place/situation/procedure/effect cards
+ index.json + topology.yaml + GENERATED_OUTPUT.json
  │
  ├─ indexed dependency resolution
  ▼
bounded runtime scene context
```

In the normal flow, only semantic extraction is a high-volume LLM task.
Routing uses a model today but does not require one. Canonical review needs a
human or strong LLM only when deterministic evidence cannot settle identity or
conflicting meaning. All other transformations are ordinary code.

## Where this document is prescriptive rather than descriptive

Three things described above are recommendations, not implemented behavior:

- **OCR fallback** in Step 1. Preparation is poppler-only.
- **Deterministic routing** in Step 2. Routing is a model task today.
- **Model-call shards** in Step 3. The pack is the unit of the model call; the
  shard JSON shown there has no durable contract anywhere in the code.

Everything else — the file layouts, schemas, IDs, JSON excerpts, the card, and
the resolved scene — is taken from this checkout and matches the code in
`module-extractor/module_extractor/`.
