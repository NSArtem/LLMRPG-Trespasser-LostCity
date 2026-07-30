# Plan to improve the module representation

## Purpose

This plan turns the findings in [review-by-codex.md](review-by-codex.md) into
an incremental implementation roadmap.

The goal is to make `module/` the primary, selectively loadable representation
of an adventure for the LLM game master invoked through the repository's
prompts.

The target combines:

- the current extractor's bounded evidence and deterministic generation;
- compact Markdown cards suitable for LLM context;
- the older `feature/module-extractor` branch's richer operational semantics;
- explicit runtime integration through `MANIFEST.md`, `CURRENT.md`, and the
  Project instructions.

## Desired outcome

At the end of the work, the system must be able to:

1. resolve the current campaign location to one canonical module place;
2. load a bounded scene context without loading the complete module or PDF;
3. identify the actors, situations, procedures, knowledge, and exits relevant
   to that scene;
4. distinguish player-safe, discoverable, and GM-only information;
5. apply campaign overrides and topology changes over an immutable module
   baseline;
6. trace operational facts to source pages without loading extraction audit
   data during normal play;
7. detect duplicate concepts instead of releasing them under different IDs;
8. use the PDF only for missing details, conflicts, repair, or audit.

## Non-goals

This plan does not:

- restore the old `feature/module-extractor` ingestion workflow;
- require all old schemas or generated diagrams;
- reproduce the PDF as Markdown;
- place mutable campaign state inside `module/`;
- make every relation a graph;
- make every module card fully self-contained through duplicated content;
- automatically apply hypothetical module outcomes to campaign state;
- migrate, convert, or preserve the currently produced `module/`,
  `module-input/`, `_exchange/`, `.module-extractor-cache/`, or equivalent
  module-workspace artifacts;
- preserve the current prototype output format indefinitely.

## Clean-rerun policy

The existing Winter's Daughter extraction is disposable output, not migration
input.

It may be inspected read-only to understand the defects described in
[review-by-codex.md](review-by-codex.md), but implementation must not:

- copy current cards into the new layout;
- transform current `module/module.json` into the new contract;
- reuse current `module-input/` responses or review decisions;
- carry current generated IDs forward merely for compatibility;
- preserve current aliases, topology reconciliation, coverage, or audit state;
- seed tests with the current produced data as an expected result.

After implementation and synthetic validation are complete, the whole
extraction pipeline must be run again from the original source PDF. Routing,
focused extraction, response ingestion, semantic review, reconciliation, and
assembly must all use artifacts created by that new run.

The only durable inputs reused across the rerun are:

- the original source PDF;
- extractor implementation, schemas, prompts, tests, and documentation;
- deliberate human decisions made during the new run from newly inspected
  source evidence.

## Design principles

### One concept, one canonical ID

Every place, actor, situation, procedure, knowledge item, rule, item, effect,
topology node, and topology edge must have one canonical ID.

Alternative source labels and source-specific IDs encountered during a run
become aliases. They must not survive as independent records unless they
represent genuinely different concepts. IDs from the discarded produced
workspace are not imported as compatibility aliases.

### One relation, one canonical owner

Topology owns reachability and baseline passage state. Situation cards own
situation activation and outcomes. Knowledge cards own truth and discovery
semantics.

Other files may include generated summaries, but must not redefine the
canonical relation.

### The place is the scene-loading entry point

A place card contains all immediately useful room or area information and
exact references to additional scene context.

It is not required to copy the full contents of referenced actors,
procedures, situations, or knowledge.

### Separate baseline from campaign state

`module/` remains an immutable representation of the source adventure before
play.

Campaign changes belong in:

- current campaign entity files;
- checkpoints;
- `gm/module-overrides.md`;
- the campaign topology overlay.

### Separate runtime data from audit data

Runtime cards and indexes should contain only what helps run the adventure.
Observation histories, response packs, confidence provenance, coverage, and
review ledgers remain available for validation and repair, but are excluded
from normal gameplay loading.

### Secrets require explicit structure

The model must not infer whether a paragraph is safe to narrate. Cards must
distinguish immediate player-facing information, discoverable information, and
GM-only information.

## Target layout

```text
module/
  MODULE.md
  index.md
  index.json
  cards/
    places/
    actors/
    situations/
    knowledge/
    procedures/
    reference/
  topology.yaml
  audit/
    module.json
    coverage.md
    conflicts-and-gaps.md
    review.md
  GENERATED_OUTPUT.json
```

### `MODULE.md`

A short LLM-facing entry point containing:

- module identity and title;
- premise;
- supported system and level range when known;
- verification state;
- major areas or starting points;
- runtime loading instructions;
- precedence and secrecy rules.

### `index.md`

A compact human- and LLM-readable directory grouped by:

- places;
- actors;
- active or available situations;
- procedures;
- knowledge;
- reference material.

It should identify direct card paths but contain no audit provenance.

### `index.json`

A deterministic machine-readable routing index. Each entry should contain
only fields required to locate and load runtime context:

```json
{
  "id": "place.winters-daughter.area-13",
  "type": "place",
  "title": "The Knight's Tomb",
  "path": "cards/places/area-13.md",
  "topology_node": "area-13",
  "refs": [
    "actor.winters-daughter.sir-chyde",
    "situation.winters-daughter.sir-chyde-plea"
  ]
}
```

### Runtime cards

Each card uses structured front matter for identity and relations and Markdown
sections for operational prose.

### `topology.yaml`

The canonical module navigation baseline:

- nodes;
- edges;
- direction;
- passage kind;
- baseline state;
- requirements;
- barriers;
- hazards;
- dynamic mechanisms when present.

Place-card exit sections are generated from this graph.

### `audit/`

Extraction-only data:

- canonical full JSON;
- raw observations;
- confidence and pack provenance;
- coverage;
- conflicts and uncertainties;
- review decisions.

The runtime prompts must explicitly exclude this directory.

## Phase 0: establish measurable requirements

### Tasks

1. Add a read-only analysis command or test helper that reports:
   - record count by type;
   - duplicate title groups;
   - unresolved aliases;
   - place-to-topology mappings;
   - dangling references;
   - runtime index size;
   - card size distribution.
2. Create small synthetic fixtures for known failure classes:
   - duplicate concepts under different ID styles;
   - complementary observations for one concept;
   - two distinct concepts with the same display title;
   - a place and topology node requiring an explicit join;
   - a hidden or conditional passage;
   - mixed player-safe and GM-only information.
3. Select representative synthetic end-to-end scenes:
   - a normal keyed room;
   - an encounter room;
   - a room with a hidden exit;
   - a cross-map or conditional passage;
   - an NPC-driven knowledge scene.
4. For each scene, record the files and approximate bytes currently required
   to answer:
   - what the players see;
   - who is present;
   - what can happen;
   - where the party can go;
   - what must remain secret.

### Acceptance criteria

- The requirements report is deterministic.
- Synthetic tests reproduce duplicate, secrecy, and topology-link failure
  classes without consuming the current produced module.
- At least five representative scene fixtures exist.
- Later phases can compare runtime context size and completeness against the
  synthetic requirements.

## Phase 1: connect the new module contract to the runtime prompts

The prompt and manifest changes are implemented against the target contract.
They do not establish the current produced module as a supported intermediate
runtime format.

### Tasks

1. Add `module/` to the loading rules in `MANIFEST.md`.
2. Update the Project instructions to define the verified module as the
   adventure baseline.
3. Define source precedence:

   ```text
   current campaign state
   → gm/module-overrides.md
   → relevant module cards
   → adventure PDF for missing detail, conflict, or audit
   ```

4. Add explicit instructions not to load:
   - `module/audit/module.json`;
   - module audit reports;
   - unrelated cards;
   - the complete adventure PDF by default.
5. Describe how to use the target `MODULE.md`, `index.json`, place cards, and
   topology slices.
6. Require verified new-contract output before treating `module/` as a runtime
   source. If it is absent or incomplete, report that state instead of falling
   back to old generated output.
7. Document all of `module/` as GM-only until player-safe sections are
   introduced.

### Affected files

- `MANIFEST.md`
- `chatgpt-project/SETUP_AND_PROMPTS.md`
- `README.md`
- corresponding templates under `templates/`

### Acceptance criteria

- The normal play prompt names `module/` as the source adventure baseline.
- The prompt never defaults to the PDF when a verified module card contains
  the needed information.
- The prompt explicitly applies campaign state and overrides before module
  baseline facts.
- Runtime instructions prohibit loading audit documents during normal play.
- Runtime instructions do not describe or support the current prototype output
  as a compatibility format.
- Template copies remain synchronized with root files.

## Phase 2: define the runtime card contracts

### Tasks

1. Replace the generic minimum-field model with type-specific operational
   contracts.
2. Define common front matter:

   ```yaml
   id:
   type:
   title:
   aliases: []
   source_pages: []
   verification:
   references: []
   ```

3. Define place fields:
   - `topology_node`;
   - `load_with`;
   - first impression;
   - contents;
   - discoverable information;
   - hidden information;
   - triggers;
   - hazards;
   - resources.
4. Define actor fields:
   - appearance;
   - role;
   - goals;
   - behavior and reactions;
   - capabilities and mechanics;
   - knowledge;
   - hidden information.
5. Define situation fields:
   - location references;
   - activation;
   - participants;
   - pressure;
   - likely approaches or decisions;
   - outcomes;
   - completion conditions;
   - repeat behavior.
6. Define procedure fields:
   - trigger;
   - ordered steps;
   - transitions;
   - stop and reset conditions;
   - applicable locations or actors.
7. Define knowledge fields:
   - kind;
   - statement;
   - truth status;
   - available from;
   - discoverable at;
   - acquisition;
   - reveals, corroborates, and contradicts.
8. Keep reference cards for rules, tables, items, spells, classes, and effects,
   but give them stable type-specific headings where useful.
9. Specify which fields are mandatory, optional, nullable, or omitted when not
   supported by the source.
10. Avoid mandatory `unknown` placeholders unless the distinction between
    unknown and absent materially affects play.

### Acceptance criteria

- Every supported record type has a documented runtime purpose.
- A place contract can answer sight, contents, occupants, exits, secrets, and
  triggers.
- An actor contract separates observable behavior from hidden motivation.
- A situation contract can be run without consulting a second situation
  identity.
- A knowledge contract separates truth from player acquisition.
- Validation rejects missing operationally essential fields.
- Validation permits source-inapplicable optional fields to remain absent.

## Phase 3: canonicalize identities and aliases

### Tasks

1. Select one ID convention, for example:

   ```text
   place.<module>.<slug>
   actor.<module>.<slug>
   situation.<module>.<slug>
   knowledge.<module>.<slug>
   procedure.<module>.<slug>
   item.<module>.<slug>
   ```

2. Add an entity-resolution stage before reconciliation:
   - normalize titles;
   - compare type and source context;
   - compare references;
   - compare area numbers and topology labels;
   - propose alias candidates;
   - distinguish same-name entities from duplicate observations.
3. Require human or review-overlay confirmation for uncertain merges.
4. Merge complementary field observations from the new run under the selected
   canonical ID.
5. Store source labels and alternate IDs encountered within the new run as
   aliases.
6. Detect duplicate concepts that survive under different IDs.
7. Change the release gate so unresolved high-confidence duplicate candidates
   block release.
8. Extend `conflicts-and-gaps.md` with:
   - duplicate candidates;
   - selected canonical IDs;
   - aliases;
   - rejected merge candidates and rationale.

### Fresh-run target

During the clean Winter's Daughter rerun, the new reconciliation must resolve
duplicate observations from introductory summaries, keyed areas, maps, and
reference sections without consulting the old generated records or their
review overlay.

### Acceptance criteria

- One canonical ID represents each real concept.
- Source-specific alternate IDs from the new extraction resolve through
  aliases when needed.
- Complementary observations are merged instead of emitted as parallel cards.
- The release gate no longer reports clean when duplicate candidates remain
  unresolved.
- Regeneration does not depend on response-pack order.
- All references resolve after alias application.

## Phase 4: link places and topology

### Tasks

1. Add `topology_node` to place observations or canonical review decisions.
2. Match numbered place titles to corresponding topology nodes
   deterministically where evidence supports the match.
3. Require explicit review for ambiguous, repeated, or unnumbered locations.
4. Validate:
   - every mapped place references an existing node;
   - every operational map node is mapped to a place or explicitly classified
     as a waypoint, boundary, mechanism, or unmapped region;
   - every edge endpoint exists;
   - traversal direction and conditions are internally consistent.
5. Render a derived `## Exits` section in every mapped place card.
6. Include:
   - destination place or node;
   - passage kind;
   - direction;
   - baseline state;
   - barriers;
   - conditions;
   - hazards.
7. Mark the exit section as generated from `topology.yaml`.
8. Add a topology-slice helper that returns one node and its immediate
   neighbors without loading the complete graph.

### Acceptance criteria

- A place card never relies on title inference to find its topology node.
- Every mapped place presents its immediate exits.
- Exit data has exactly one canonical owner.
- Hidden and conditional passages retain their discovery or traversal
  requirements.
- Runtime prompts can load the current topology slice without loading the
  complete topology file.

## Phase 5: add scene-oriented loading

### Tasks

1. Add `load_with` metadata to place cards:

   ```yaml
   load_with:
     actors: []
     situations: []
     procedures: []
     knowledge: []
   ```

2. Make references explicit and typed rather than relying on one undifferenced
   `references` list.
3. Generate `index.md` grouped by area and operational type.
4. Reduce `index.json` to:
   - canonical ID;
   - type;
   - title;
   - path;
   - aliases;
   - area or topology node;
   - typed references.
5. Add a deterministic scene-resolution command or library function:

   ```text
   current place ID
   → place card
   → active or available situations
   → required actors
   → referenced procedures
   → relevant knowledge
   → current topology slice
   ```

6. Enforce a maximum or reported context size for a scene bundle.
7. Detect accidental inclusion of audit files or unrelated cards.

### Acceptance criteria

- Each representative scene resolves to an exact file list.
- No scene requires loading the complete index, complete topology, or
  `module.json`.
- Scene bundles include all required immediate operational information.
- Scene bundles exclude unrelated secrets and entities.
- Bundle generation is deterministic.
- Bundle sizes are materially smaller than loading the PDF or complete module.

## Phase 6: model knowledge, situations, and effects safely

### Knowledge tasks

1. Introduce stable knowledge IDs.
2. Distinguish:
   - confirmed fact;
   - secret;
   - clue;
   - claim;
   - rumor;
   - false or mixed claim;
   - solution.
3. Record truth separately from availability.
4. Record acquisition conditions and reveal relationships.
5. Make module knowledge IDs valid checkpoint `knowledge_ref` targets.
6. Do not mark a module fact as player-known merely because it is true.

### Situation tasks

1. Give every situation one file and one canonical ID.
2. Store structured activation and outcomes in front matter.
3. Store presentation, pressure, approaches, reactions, and consequences in
   the Markdown body.
4. Represent outcomes as possible effects.
5. Align effect shapes with checkpoint changes where practical.
6. Require an actual gameplay `source_event` before a possible effect becomes
   mutable campaign state.

### Procedure tasks

1. Model repeated or scheduled behavior separately from one-shot situations.
2. Support transitions, stop conditions, and reset conditions only when the
   source requires them.
3. Keep simple procedures simple.

### Acceptance criteria

- The GM can determine what is true without treating it as player-known.
- The GM can determine how a clue may be acquired.
- A situation exposes meaningful choices and possible consequences.
- Hypothetical outcomes never alter campaign state automatically.
- Applied effects are traceable to a checkpoint event.
- No situation requires a separate flow ID and card ID.

## Phase 7: make overrides and topology overlays deterministic

### Tasks

1. Require every override row to have a canonical target ID.
2. Define target types:
   - module record;
   - topology node;
   - topology edge;
   - campaign-created entity.
3. Validate target resolution.
4. Preserve a human-readable title column only as display metadata.
5. Define effective state evaluation:

   ```text
   module baseline
   + prior checkpoints
   + module overrides
   + topology overlay
   = current effective state
   ```

6. Update checkpoint and continuity-audit prompts to verify module target IDs.
7. Add tests for:
   - dead or moved actors;
   - looted rooms;
   - opened or destroyed passages;
   - disabled traps;
   - consumed or transferred module items;
   - situations that have already completed.

### Acceptance criteria

- Every module override resolves deterministically.
- The model can answer whether an entity remains in its baseline state.
- Topology changes never mutate the module baseline.
- Continuity validation catches stale scene assumptions.
- Duplicate override targets and contradictory effective states are reported.

## Phase 8: separate runtime and audit output

### Tasks

1. Move or render the full canonical extraction document as
   `module/audit/module.json`.
2. Move reports under `module/audit/`.
3. Keep runtime card source pages, but move observation IDs, response pack IDs,
   confidence histories, and review internals to audit data.
4. Generate `MODULE.md`, `index.md`, `index.json`, cards, and topology as the
   runtime product.
5. Add generated-output markers and hashes for both:
   - runtime representation;
   - audit representation.
6. Teach overwrite safety checks about the new layout.
7. Ensure repair workflows can still trace every runtime claim to audit
   evidence.

### Acceptance criteria

- Runtime loading never requires audit files.
- Audit files retain full source traceability.
- A runtime card can be traced to its source observations through stable IDs.
- Generated-output replacement remains atomic and marker-gated.
- The runtime index is substantially smaller than the current 104 KB index.

## Phase 9: run the complete Winter's Daughter pipeline from scratch

This phase must not migrate, convert, or selectively retain any existing
produced result.

### Tasks

1. Finish implementation, synthetic tests, schemas, prompts, and documentation
   before starting the adventure extraction.
2. Confirm the exact produced workspace paths for the existing run:
   - `module/`;
   - `module-input/`;
   - `_exchange/`;
   - `.module-extractor-cache/`;
   - any other extractor-produced module workspace.
3. Remove or isolate those produced artifacts through the extractor's safe
   cleanup workflow. Do not feed them into any new preparation, import,
   reconciliation, or review command.
4. Prepare the original Winter's Daughter PDF as a new extraction.
5. Perform routing again with the new routing contract.
6. Generate all focused packs again.
7. Obtain new focused responses for every pack.
8. Ingest and validate only those new responses.
9. Perform semantic review from newly prepared source text and map evidence.
10. Complete new-run entity resolution and aliases.
11. Resolve place-to-topology links from new-run evidence.
12. Review player-safe, discoverable, and hidden sections.
13. Review active and available situations by area.
14. Review knowledge truth and acquisition.
15. Review possible effects and ensure none are treated as already applied.
16. Assemble fresh runtime and audit trees.
17. Run the representative scene-loading tests against the fresh output.
18. Conduct a human GM review of at least:
    - initial approach;
    - tomb entry;
    - one hidden passage;
    - Sir Chyde's request;
    - one Fairy location;
    - a return visit after an override.

### Acceptance criteria

- Every input and intermediate artifact belongs to the new pipeline run.
- No file, record, alias, review choice, response, topology decision, or
  generated card from the previous run is migrated into the fresh output.
- The new output can be reproduced after another clean preparation using the
  same source and newly supplied responses.
- No unresolved duplicate concepts remain.
- All new-run aliases resolve.
- Every keyed area has one canonical place card.
- Every mapped place has a valid topology node and derived exits.
- Every playable situation has sufficient GM-facing material.
- Secrets are structurally separated from immediate narration.
- Overrides use canonical target IDs.
- All representative scenes resolve bounded, complete context bundles.
- The PDF is unnecessary for ordinary play through the reviewed scenes.

## Phase 10: update documentation and templates

### Tasks

1. Update user documentation to describe:
   - the immutable module baseline;
   - runtime versus audit files;
   - selective loading;
   - aliases and canonical IDs;
   - override and topology-overlay behavior.
2. Update developer documentation with:
   - card contracts;
   - canonical ownership rules;
   - scene resolution;
   - release gates;
   - clean-rerun and workspace-replacement behavior.
3. Update campaign templates to include:
   - `module_ref` or `module_refs`;
   - canonical override targets;
   - topology overlay references;
   - current situation references when applicable.
4. Update Project prompts and checkpoint prompts.
5. Add examples for:
   - starting a module;
   - entering an area;
   - discovering a secret;
   - applying an override;
   - recording a topology change;
   - resolving a module effect through a checkpoint.
6. Decide and document language policy:
   - preserve source-language extraction by default;
   - translate during narration;
   - retain exact wording when mechanically or narratively significant.

### Acceptance criteria

- Root files and templates carry the same contracts.
- A new campaign can select a starting module place without manual path
  invention.
- The prompt tells the LLM exactly which module files to load and in which
  order.
- Documentation never suggests loading the complete PDF or audit tree by
  default.

## Validation strategy

### Unit tests

Cover:

- type-specific card validation;
- canonical ID normalization;
- alias resolution;
- duplicate candidate detection;
- place-to-topology linkage;
- derived exit rendering;
- knowledge truth and acquisition;
- situation effect validation;
- override target resolution;
- runtime index generation.

### Integration tests

Build synthetic modules containing:

- duplicated observations under different IDs;
- two entities with the same display name but different identities;
- hidden and conditional passages;
- a clue known by an actor and discoverable at a place;
- a situation that changes topology if resolved;
- a campaign override that supersedes module baseline state.

### Clean-pipeline end-to-end verification

After implementation, run the complete Winter's Daughter pipeline from the
source PDF and verify:

1. current place ID resolves to one place card;
2. the place card resolves the correct actors and situations;
3. exits match topology;
4. hidden information is not in the immediate narration section;
5. knowledge is not treated as acquired before its condition;
6. an applied override supersedes baseline state;
7. an unplayed possible effect remains hypothetical;
8. no runtime load includes `audit/` or the complete PDF.
9. no previous `module/`, `module-input/`, exchange, cache, response, or review
   artifact contributed to the new result.

### Repository validation

Run:

```bash
python3 -m unittest discover -s module-extractor/tests -v
python3 scripts/validate_repo.py
git diff --check
```

Add a dedicated runtime-module validation command if the existing validator
cannot express scene bundles and canonical target resolution.

## Rollout order

The phases should be implemented in this order:

1. measurable synthetic requirements;
2. prompt integration;
3. runtime card contracts;
4. identity and alias reconciliation;
5. topology linkage;
6. scene-oriented loading;
7. typed knowledge and situations;
8. deterministic overrides;
9. runtime/audit separation;
10. clean full Winter's Daughter pipeline rerun;
11. final documentation and prompt audit.

Prompt integration is designed early but becomes operational only with fresh
new-contract output. Identity reconciliation precedes topology joins and scene
bundles because later stages require stable canonical IDs.

## Step-by-step execution documents

The implementation is divided into independently releasable vertical slices:

1. [plan-by-codex-0.md](plan-by-codex-0.md) — establish the new runtime output
   boundary and keep the complete pipeline working;
2. [plan-by-codex-1.md](plan-by-codex-1.md) — canonical identity, aliases, and
   duplicate review;
3. [plan-by-codex-2.md](plan-by-codex-2.md) — operational places, topology
   linkage, and bounded scene loading;
4. [plan-by-codex-3.md](plan-by-codex-3.md) — operational actors and
   situations;
5. [plan-by-codex-4.md](plan-by-codex-4.md) — typed knowledge, procedures, and
   reference material;
6. [plan-by-codex-5.md](plan-by-codex-5.md) — campaign overrides, topology
   overlays, and runtime prompt integration;
7. [plan-by-codex-6.md](plan-by-codex-6.md) — hardening and a complete clean
   real-source pipeline qualification.

Each document assumes a fresh extractor workspace. None uses, migrates, reads
for compatibility, or validates against a previously produced `module/`,
`module-input/`, exchange directory, cache, response, or review overlay.

## Risks and mitigations

### Risk: overengineering the replacement

Mitigation:

- require fields only when operationally necessary;
- keep simple cards simple;
- avoid restoring separate flow identities and generated diagrams;
- validate usefulness through representative scene bundles.

### Risk: incorrect automatic entity merges

Mitigation:

- distinguish candidate detection from canonical merge;
- require review for ambiguous candidates;
- preserve source-specific alternate IDs from the new run as aliases;
- record merge rationale and source pages.

### Risk: duplicated topology state

Mitigation:

- keep `topology.yaml` canonical;
- mark card exits as generated;
- apply campaign changes only through overlays and checkpoints.

### Risk: secrets leak into narration

Mitigation:

- use stable immediate, discoverable, and hidden sections;
- validate required visibility structure;
- add prompt tests for player-facing responses.

### Risk: scene bundles become too large

Mitigation:

- make references typed;
- load only active situations and related knowledge;
- report bundle sizes;
- prohibit transitive loading without an explicit rule.

### Risk: module effects mutate state prematurely

Mitigation:

- label module effects as possible effects;
- require checkpoint `source_event`;
- validate effective state only after applied campaign changes.

## Definition of done

The module-representation improvement is complete when:

- `MANIFEST.md` and the Project prompt use `module/` during normal play;
- one canonical ID represents each concept;
- aliases resolve source-specific alternate IDs encountered during the fresh
  run;
- duplicate candidates block release until reviewed;
- every keyed place has a complete operational card;
- every mapped place links to topology and presents derived exits;
- player-safe, discoverable, and hidden information are structurally distinct;
- situations, actors, procedures, and knowledge have operational type-specific
  contracts;
- a current place resolves a bounded deterministic scene bundle;
- overrides and topology changes target canonical IDs;
- hypothetical module outcomes do not become state without a gameplay event;
- runtime and audit data are separated;
- a fresh Winter's Daughter module produced by a complete new pipeline run
  passes validation and human scene review;
- no prior produced module workspace or result is migrated or reused;
- ordinary play through reviewed scenes does not require loading the PDF.
