# Module Extractor developer reference

The [user guide](USER_GUIDE.md) is the sole authority for the human workflow.
This document describes contracts and implementation boundaries.

## Repository boundary

`module-extractor/` contains reusable source code, tests, and documentation
only. Runtime data is rooted beside it:

```text
_exchange/                 ignored manual handoff files
.module-extractor-cache/   ignored prepared PDF assets
module-input/              durable pipeline inputs
module/                    generated product
```

One Git branch owns one active module. The CLI therefore has no run selector or
source-hash directory. `run PDF` derives a slug from the filename and takes
optional `--slug` and `--title` overrides. A second preparation with the same
slug stages and replaces the active workspace. An existing different slug is
rejected.

The source SHA-256 remains a required identity field in every contract. It
guards against mixing source material without becoming a user-facing path.

## Pipeline

```text
PDF
  -> disposable prepared assets and routing ZIP
  -> durable routing response
  -> disposable focused ZIPs
  -> validated durable evidence responses
  -> reconciliation and review overlay
  -> canonical module and selective views
```

The CLI performs no model calls.

## CLI and state machine

The public parser exposes only:

```text
run [PDF] [--slug SLUG] [--title TITLE]
status [--json] [--scene PLACE_ID [--situation SITUATION_ID]]
clean
advanced
```

`run PDF` prepares the source and stops after creating `routing.zip`. `run`
without a PDF detects and advances these states:

```text
not-started
waiting-for-routing
routing-response-ready
waiting-for-focused-responses
codex-review-required
release-ready
already-released
```

It executes all available deterministic transitions in one invocation:
routing acceptance and focusing, validation and partial ingestion, evidence
evaluation and Codex-task generation, then release assembly when the gate
passes. Waiting is successful workflow state, not an error. A rejected response
names the JSON, validation reason, ZIP to retry, and rerun command.

`status` is read-only and human-readable. `status --json` is the explicit
structured interface. `status --scene` is the read-only runtime interface and
always prints JSON; `--situation` requires it.

Technical commands are intentionally available only below `advanced`:

```text
advanced prepare
advanced focus
advanced ingest
advanced validate
advanced review
advanced assemble
```

They preserve stage-level debugging and testing without forming part of the
normal human workflow.

## Current contracts

| Artifact | Schema |
| --- | --- |
| page routing | `module-routing/v1` |
| content evidence | `module-content-evidence/v3` |
| map evidence | `module-map-evidence/v2` |
| coverage manifest | `module-coverage/v1` |
| review overlay | `module-review-overlay/v3` |
| canonical module | `operational-module/v3` |
| runtime index | `operational-module-index/v4` |
| generated output | `module-extractor-generated-output/v4` |
| scene context | `operational-scene-context/v2` |

Routing is page-total and multi-label. Content records retain stable IDs,
physical-page citations, confidence, references, and targeted uncertainties.
Place evidence separates player-safe first impression, visible contents,
conditioned discoveries, hidden GM information, triggers, hazards, resources,
occupants, and typed card references. Optional fields are omitted when the
source does not support them. `topology_node: null` is reserved for an explicit
source-supported unmapped decision.

Actor evidence separates observable material — appearance, role, goals,
behavior, reactions, capabilities and mechanics, relationships, and applicable
location and situation references — from GM-only `hidden` motivations,
orders, and constraints. Mutable runtime state is rejected outright: health,
hit points, wounds, position, location, attitude, disposition, mood, status,
and inventory belong to the campaign checkpoint. `starting_state` is the only
sanctioned exception and holds a source-stated starting state, clearly labeled
as such on the card.

Situation evidence carries a player-safe `perceived` description, a structured
`activation` (`triggered`, `timed`, `random`, `keyed`, `ongoing`, or `chosen`
with a condition), `repeat` (`once` or `repeatable` with an optional
condition), typed location, participant, procedure, and knowledge references,
stakes, approaches, actor reactions, outcomes, and completion conditions.
A situation may not record that it already ran: `active`, `resolved`,
`completed`, `progress`, and applied-effect fields are rejected.

`possible_effects` are typed source possibilities: `activate-situation`,
`actor-state`, `future-thread`, `reveal-knowledge`, `schedule-procedure`,
`stop-procedure`, and `topology-state`. Every effect except `future-thread`
names a target — a record of the matching canonical type, or, for
`topology-state`, a topology node or passage. The extractor never applies an
effect, never derives current state from one, and never copies one into a
checkpoint.

Topology nodes are classified as `place`, `waypoint`, or `boundary`. Passages
keep kind, medium, elevation, baseline state, visibility, barriers, features,
conditions, hazards, and traversal direction as independent facets. Kind,
medium, and baseline state are open source-faithful strings. Elevation,
visibility, and direction use small controlled vocabularies; unknown scalar
values make no assertion. Hidden and conditional passages require conditions.

## Durable input layout

```text
module-input/
  source.json
  routing.json
  packs.json
  responses/
    <pack-id>.json
  review.json
```

`packs.json` records pack kind, pages, size budget, pack SHA-256, response path,
and—after ingestion—the exact ingested response SHA-256. Content packs also
record the task union and page-by-page task matrix. Ingestion validates the
exchange archive before recording that response hash.

Assembly accepts either:

- a still-present archive whose bytes match `pack_sha256`; or
- an ingested response whose bytes match `ingested_response_sha256`.

This permits `_exchange/` and the preparation cache to be deleted without
making durable inputs impossible to validate or assemble.

## Exchange and cache

`_exchange/` is flat:

```text
routing.zip
routing.json
<pack-id>.zip
<pack-id>.json
codex-task.md
```

Every new archive contains human `README.md`, model `prompt.md`, and
`response-template.json`. Focused archives additionally contain `pack.json`,
page text, and relevant images.

Content packs combine every semantic task on at most eight contiguous pages.
They split near 30 KiB of prepared UTF-8 text once the current chunk contains
at least 15 KiB. Non-operational illustration pages may bridge content; covers,
dividers, and blanks break a run.

Map pages are ordered but need not be physically contiguous. A pack contains
at most 20 pages and 16 MiB of uncompressed PNG renders; one oversized render
is allowed alone. Pack ZIPs are deterministic for identical source assets,
routing, and code.

`advanced focus` generates a complete replacement workspace in staging. It
preserves an exchange or ingested response only when the new pack has the same
ID and exact ZIP hash and the response validates against the current contract.
Any pack-set change resets the review overlay. Generation failure leaves all
three runtime directories untouched.

Content responses include an exact page/task checklist. Each pair either names
compatible, page-citing record IDs or reports `not-found` with an explanation.
Map coverage is derived from node and passage citations.

`.module-extractor-cache/` contains the copied source PDF, layout text,
per-page text, thumbnails, and map renders. Nothing in it is a durable
correction or canonical output.

## Reconciliation and review

Cross-pack records remain source observations. Reconciliation groups them by
conceptual ID while retaining field values, packs, pages, confidence, and
uncertainties.

`module-input/review.json` is the only durable canonicalization layer. It may
declare policy-compliant canonical IDs, alias current-run extracted IDs,
declare duplicate candidates distinct, select or compose canonical values,
explicitly accept source uncertainties, and authorize a source-cited composite
when multiple place cards intentionally map to one topology node. See
[IDENTITY.md](IDENTITY.md).
Duplicate analysis runs on untouched ingested observations before alias
rewriting and reconciliation. Two objects the source keyed as different areas
are never high-confidence duplicates, and a typed operational cross-reference
alone — one situation naming another — is not identity evidence. Both still
surface as reviewable candidates. `_exchange/codex-task.md` is generated and
inert. It includes release-gate errors, coverage gaps, complete conflict
candidates and provenance, uncertainties, neighboring topology, place and
topology decisions, actor and situation decisions, cited source paths, and
exact permitted correction paths and commands.

The stable agent contract is [CODEX_WORKFLOW.md](CODEX_WORKFLOW.md). Codex may
correct an exchange response and re-ingest it, or write a source-cited review
operation. It must inspect cited source evidence before deciding, rerun `run`
until release or a genuine blocker, and never commit or clean. It must not
modify ingested evidence, coverage, or generated output. Local validation and
the release gate remain authoritative, and the human approves the resulting
Git diff.

## Generated output

`module/audit/module.json` is the authoritative extraction and audit object.
Runtime entry points and cards are deterministic selective views:

```text
module/
  MODULE.md
  index.md
  index.json
  topology.yaml
  cards/
    places/
    actors/
    situations/
    knowledge/
    procedures/
    reference/
  audit/
    module.json
    coverage.md
    conflicts-and-gaps.md
    review.md
  GENERATED_OUTPUT.json
```

Runtime cards use a stable YAML front-matter envelope and retain only
operational fields. The compact JSON index contains routing data, aliases,
references, explicit place-to-node links, and typed load paths. Observation,
pack, confidence, review, and coverage histories exist only under `audit/`.
`topology.yaml` is canonical JSON, a deterministic YAML 1.2 subset. Place cards
carry an explicit `topology_node`, typed `load_with`, stable visibility
sections, and an `Exits` section generated from adjacent canonical passages.
Passage state is never owned by a place record.

Actor cards render `Appearance`, `Role`, `Goals`, `Behavior and reactions`,
`Relationships`, `Capabilities and mechanics`, `Starting state`, `Knowledge`,
and `Hidden`. Only `Hidden` is GM-only. Front matter carries the places and
situations the actor appears in, resolved in both directions, so one shared
actor is one record and one card.

Situation cards render `What the players perceive`, `Pressure and stakes`,
`Likely approaches`, `Actor reactions`, `Consequences` with a marked
`Possible effects` subsection, and `Completion conditions` with `Repeat
behavior`. Structured activation, repeat, participants, typed load paths, and
possible effects live in front matter. A situation has exactly one identity and
one canonical file: there is no separate flow object.

A place bundles the situations available there. A situation bundles the actors,
procedures, and knowledge it needs and never another situation, so a possible
`activate-situation` effect cannot pull a dormant situation into context.

`status --scene PLACE_ID` resolves one bounded runtime bundle: the place card,
its explicit `load_with` paths, the situations available there, the current
topology node, and adjacent edges. `--situation SITUATION_ID` additionally
selects one available situation as active and adds only its own load paths.
Choosing the active situation is always an explicit runtime decision. The
active situation reports its possible effects with `applied: false`. The
resolver reports each included path and total bytes and never returns `audit/`,
the PDF, the complete index, or the complete topology.

Release assembly requires total coverage, valid required fields, references,
place decisions, node classifications, topology coverage and endpoints, valid
actor and situation records with resolvable typed references, and no
unresolved conflicts, high-confidence duplicate candidates, invalid aliases,
duplicate keyed-area claims, ambiguous joins, or pending uncertainties.
The v3 marker enumerates and hashes the complete tree. Assembly validates the
whole staged product before an atomic publication. Replacement is permitted
only for a valid v3 marker; prior layouts have no compatibility reader or
migration path.

## Prototype format

Pack and response formats are replaced in place while the extractor remains a
prototype. `advanced focus` regenerates disposable archives and invalidates
responses whose exact pack bytes changed. The production CLI does not carry
legacy-pack options or compatibility branches.

## Verification

```bash
python3 -m unittest discover -s module-extractor/tests -v
python3 scripts/validate_repo.py
git diff --check
```

The historical PoC has its own isolated regression tests.
