# Review of the module representation

## Scope

There is no `model/` directory, so this review treats `module/` as the subject.
The branch named in the request as `feature/module_extractor` is interpreted as
`feature/module-extractor`.

The comparison is not perfectly symmetrical:

- the current branch contains a real generated module for *Winter's Daughter*;
- `feature/module-extractor` contains the proposed canonical contract,
  templates, schemas, and representative fixtures, but not a completed root
  `module/`.

The evaluation therefore compares the current real output with the older
branch's intended final representation. It deliberately does not evaluate the
feasibility of the older extraction workflow.

## Executive conclusion

The current `module/` is useful as extracted, source-cited evidence, but it is
not yet a good runtime representation for an LLM game master. The older branch
models gameplay much more effectively, but its final representation is too
fragmented and strict to adopt unchanged.

The recommended direction is:

> Keep the current extractor's bounded evidence, deterministic assembly, and
> compact Markdown output. Adopt the older design's operational semantics,
> typed relationships, secrecy model, topology linkage, immutable baseline,
> and prompt-loading rules. Do not restore its multiple files and identities
> for a single playable concept.

In short: **old semantics, current packaging, explicit runtime integration**.

## What the current representation contains

The current generated module contains:

- 256 Markdown cards;
- 214 entity cards and 42 reference cards;
- 52 locations;
- 42 actors;
- 39 situations;
- 42 procedures;
- 39 knowledge records;
- 19 topology nodes and 22 passages;
- a 104 KB `index.json`;
- a 75 KB `topology.json`;
- a nearly 800 KB `module.json`;
- approximately 2 MB in total.

The renderer is intentionally generic. It emits the record's ID, type, source
pages, references, and one heading per field:
[rendering.py](module-extractor/module_extractor/rendering.py#L21).

The minimum semantic contract is correspondingly shallow:

- location: `title`, `description`;
- actor: `title`, `role`;
- situation: `title`, `trigger`;
- procedure: `title`, `trigger`, `steps`;
- knowledge: `title`, `text`.

See [contracts.py](module-extractor/module_extractor/contracts.py#L62).

## What the current representation gets right

### Compact, selectively loadable Markdown

Individual cards are small, readable, and cheap to place in an LLM context.
They are substantially better runtime material than loading a complete PDF or
the 800 KB canonical JSON document.

### One common extraction mechanism

Locations, actors, situations, procedures, knowledge, rules, tables, items,
spells, classes, and effects all pass through a common evidence and review
pipeline. This reduces implementation surface and makes deterministic assembly
possible.

### Source traceability and review data

The extraction retains:

- physical source pages;
- observations and confidence;
- response-pack identity;
- coverage;
- conflicts and uncertainties;
- review decisions.

These are valuable for audit and repair.

### Useful topology evidence

The topology contains real operational facets such as passage kind, medium,
elevation, barriers, traversal conditions, and direction. Much of this data is
already suitable for running movement once it is connected to the relevant
place cards.

### Immutable source material

Generated module content is separate from mutable campaign state. That is the
correct conceptual boundary: the module describes the adventure baseline,
while play changes campaign files, checkpoints, overrides, and topology state.

## Critical problems in the current representation

### 1. The runtime prompts do not load `module/`

This is the largest problem.

The current [MANIFEST.md](MANIFEST.md#L31) tells the model to load relevant
campaign NPC/location files and, when needed, the attached adventure PDF. It
does not tell the model to inspect module cards, follow module references, or
load a topology slice.

The Project instructions similarly define the PDF as the adventure baseline
and say to consult current entities and `gm/module-overrides.md` before the
PDF:
[SETUP_AND_PROMPTS.md](chatgpt-project/SETUP_AND_PROMPTS.md#L75).

As a result, the generated module is effectively orphaned from gameplay. Its
shape is largely moot until the runtime loading contract references it.

The required precedence should become:

```text
current campaign state
→ module overrides and topology overlay
→ relevant verified module fragment
→ PDF for missing details, conflicts, or audit
→ general model knowledge
```

### 2. The cards are summaries, not operational GM units

A location card currently provides little more than a title, references, and
one description paragraph. At the moment the party enters an area, an LLM game
master needs at least:

- what can be presented immediately;
- what and who are present;
- available exits;
- hidden or discoverable information;
- triggers, hazards, and reactions;
- resources and interactable features.

The current location contract reliably supplies only the first approximation
of one of these.

Actors similarly combine role, history, behavior, capabilities, and secrets
into a prose blob. Situations reliably require only a trigger; only 9 of 39
current situations have an `outcome` field. For example,
[Sir Chyde's plea](module/cards/entities/winters-daughter.situation.area-13-sir-chydes-plea.md#L8)
contains a trigger and one-sentence outcome, but no pressure, choices,
reactions, completion conditions, or state changes.

### 3. Player-safe and GM-only information are mixed

The campaign prompt requires the GM to respect knowledge boundaries. Current
module cards have neither typed front matter nor stable player-safe and
GM-only sections.

A single actor card may contain:

- immediately visible appearance;
- behavior players can observe;
- private motivation;
- unknown mechanics;
- a hidden relationship or vulnerability.

A single file-level `knowledge_level` is therefore not enough. The
representation needs section- or field-level semantics such as:

```markdown
## First impression
Player-safe information that may be narrated immediately.

## Discoverable
Information paired with the action or condition that reveals it.

## Hidden
GM-only information that must not be narrated without activation.
```

Structured knowledge records must separately model who can know a fact, where
it can be discovered, how it is acquired, and whether it is true.

### 4. Topology is not joined to places

Topology nodes use IDs such as `area-13`. Location cards use unrelated IDs such
as:

- `location-area-13-knights-tomb`;
- `winters-daughter.location.area-13-the-knights-tomb`.

None of the 52 location record IDs equals a topology node ID, no location card
has a `topology_node` field, and no card reference points to a topology node.

An LLM can sometimes infer that a titled Area 13 card corresponds to
`area-13`, but this is a heuristic join. It will become unreliable with
unnumbered locations, subareas, multiple maps, wilderness regions, portals, or
repeated names.

The topology does contain exits, but they are absent from location cards. A GM
must load or search the complete topology and infer the node mapping before it
can answer where the party can go.

The fix does not require re-extracting topology. It requires:

1. reconciling each place with a topology node;
2. making that relation canonical;
3. rendering the current node and adjacent passages into the place's runtime
   card.

The topology graph should remain the canonical owner. Exit lists embedded in
place cards should be explicitly derived views so the same passage cannot
acquire two conflicting canonical states.

### 5. Duplicate concepts survive as separate canonical records

The current module uses three broad ID styles:

- 127 records use hyphen IDs such as `actor-sir-chyde`;
- 75 use dot IDs such as `item.ring-of-soul-binding`;
- 54 use namespaced IDs such as
  `winters-daughter.actor.area-13-sir-chyde`.

These namespaces overlap semantically. There are at least 19 groups with the
same type and title, including:

- two Sir Chyde actors;
- three Princess Snowfall-at-Dusk actors;
- two Ring of Soul-Binding items;
- duplicate locations for areas 3 through 14.

For example, area 13 exists as both:

- [the page-29 record](module/cards/entities/winters-daughter.location.area-13-the-knights-tomb.md#L1);
- [the page-19 record](module/cards/entities/location-area-13-knights-tomb.md#L1).

They contain complementary evidence but are neither merged nor aliased.
Meanwhile, [index.json](module/index.json#L1) has an empty `aliases` object.

The conflict report still reports no blocking conflicts because reconciliation
compares observations only after they already share a conceptual ID. It does
not detect that two different IDs describe the same entity.

This makes the release gate structurally meaningful but semantically
misleading. It verifies consistency within IDs, not canonical identity across
IDs.

### 6. The campaign override join is under-specified

The current `gm/module-overrides.md` table already includes an `ID` column, so
it has room for a deterministic key. However, neither its documentation nor
validation requires that ID to resolve to a canonical module record, topology
edge, or campaign-created entity.

Without that contract, the GM cannot reliably answer:

> Is this area, actor, object, or passage still in its original module state?

Overrides should use stable targets:

```text
override.target_id must resolve to:
- a canonical module entity;
- a canonical module topology node or edge; or
- an entity created by an earlier campaign checkpoint.
```

The display-name column can remain for humans, but it must not be the join key.

### 7. The loading granularity is wrong

The gameplay prompt loads context by scene. The generated module is organized
by individual records.

Running one room currently requires some combination of:

- the location card;
- several referenced actor, situation, procedure, or knowledge cards;
- the global index;
- topology data;
- campaign overrides.

Yet there is no direct scene bundle or `load_with` contract. The global
`index.json` answers ID-to-path lookup but not:

> Given the current place or situation, which exact files are needed now?

A place should be the primary loading entry point. It should contain all
immediate room-operational information and exact references to any additional
cards needed for the scene.

It should not duplicate the complete contents of actors, reusable procedures,
or cross-location knowledge. Making every place fully self-contained would
create stale copies and unclear canonical ownership. Instead, it should act as
a deterministic scene bundle.

### 8. Runtime and audit data are mixed

`module/module.json` includes raw observations, confidence, response packs,
coverage, conflicts, uncertainties, review hashes, and release-gate details.
This is useful extraction evidence, but poor gameplay context.

`index.json` does not contain raw topology observations, but it is still 104 KB
because it routes 256 records and their references. Neither it nor the 800 KB
`module.json` should be loaded by default during play.

Audit material may remain under `module/audit/` as long as:

- runtime prompts explicitly exclude it;
- runtime indexes do not link to it;
- gameplay tools do not glob it into context;
- a small LLM-facing module guide identifies the correct entry points.

## What `feature/module-extractor` got right

### Typed operational cards

The older design gives cards structured front matter containing stable IDs,
types, source references, verification state, visibility, and explicit
topology linkage.

This is substantially more useful than relying on filename conventions and
untyped prose.

### Places designed for play

Its place cards distinguish:

- purpose;
- first impression;
- inhabitants;
- triggers and reactions;
- hazards;
- resources;
- exits;
- source uncertainty.

These headings correspond to decisions the GM must make while running an area.

### Explicit topology ownership

Places link to topology nodes and list edge IDs, while topology owns
reachability and passage state. This eliminates the current implicit join.

### Situations as decision points

The older design treats a situation as a playable structure with:

- activation;
- location;
- participants;
- pressure;
- available decisions;
- possible outcomes;
- completion conditions;
- repeat behavior.

That is a much better model than `title + trigger`.

### Knowledge as a typed graph

The older knowledge representation distinguishes:

- facts;
- secrets;
- clues;
- claims;
- rumors;
- false or mixed claims;
- solutions.

It also records:

- truth status;
- who can provide the knowledge;
- where it is discoverable;
- how it is acquired;
- what it reveals, corroborates, or contradicts.

This aligns well with the existing checkpoint vocabulary for facts and
knowledge changes. Stable module knowledge IDs can be referenced from campaign
state without copying their contents.

### Typed state effects

Situation outcomes can express effects such as changing a topology edge from
closed to open. These shapes can be made compatible with checkpoint changes.

Compatibility must not mean automatic application. A module effect describes
a possible consequence; it becomes campaign state only after an actual
gameplay action and adjudicated outcome produce a checkpoint `source_event`.

### Immutable baseline plus campaign overlay

The older branch correctly defines:

- `module/` as the source adventure before play;
- current entity files and checkpoints as played state;
- `gm/module-overrides.md` as source-state differences;
- a topology overlay as mutable reachability state;
- the PDF as a cold source for audit and missing details.

This is the right state model for a persistent LLM-run campaign.

### Prompt integration

The older runtime prompt explicitly instructs the model to:

- follow `module_ref` and `module_refs`;
- load only relevant module fragments;
- add the current topology slice during navigation;
- load active situations, actors, procedures, and related knowledge;
- apply campaign overlays;
- use the PDF only for missing details, conflict resolution, or audit.

These instructions are as important as the module format itself.

## What `feature/module-extractor` got wrong

### One situation represented twice

The older design gives a situation:

- a Markdown card ID;
- a separate YAML situation ID;
- a `situation_ref` join between them.

That is two files and two identities for one concept. The LLM must load both to
understand presentation and state.

A situation should have one canonical ID and preferably one canonical file
containing structured metadata plus GM-facing prose.

### Too many canonical files for one scene

Running one room can require traversing places, actors, knowledge, procedures,
topology, flow, and situation directories. The semantic decomposition is
useful, but the runtime packaging is too fragmented.

The place card should be the deterministic scene entry point and list exact
additional files.

### Excessively strict schemas

Mandatory geometry, measurements, schedules, typed links, ownership rules, and
verification fields impose cost even when the source does not contain or need
them.

Strict schemas can turn normal adventure prose into a large number of
`unknown` placeholders. Fields should be mandatory only when their absence
would make gameplay unsafe or ambiguous.

### Generated and audit artifacts are too prominent

Mermaid, SVG, source inventories, extraction ledgers, and ambiguity reports
are useful for humans and repair workflows. They should not appear to be
runtime entry points.

They may remain under an explicitly excluded `audit/` or `generated/`
directory, but the LLM-facing guide and index must route around them.

### Too many canonical owners

Splitting prose, activation, flow, effects, topology, and source references
across several file types makes it difficult for both humans and models to know
which file owns a relation.

The useful rule from the older design should be retained:

> Every identity and relation has exactly one canonical owner; other views are
> derived.

The number of owners should be reduced, not multiplied.

## Recommended final representation

```text
module/
  MODULE.md
  index.json
  areas/
  actors/
  situations/
  knowledge/
  procedures/
  reference/
  topology.yaml
  audit/
```

### `MODULE.md`

A small, approximately 2 KB LLM-facing guide containing:

- module ID and title;
- system and supported level range;
- premise and starting situation;
- area list;
- source language;
- verification status;
- runtime loading rules;
- precedence and secrecy rules.

This is the only module file that may be loaded when opening the adventure
without knowing the current area.

### `index.json`

A compact routing index:

```json
{
  "id": "place.winters-daughter.area-13",
  "type": "place",
  "title": "The Knight's Tomb",
  "path": "areas/area-13.md",
  "topology_node": "area-13",
  "refs": [
    "actor.winters-daughter.sir-chyde",
    "situation.winters-daughter.sir-chyde-plea"
  ]
}
```

Do not inline observations, pack IDs, confidence histories, or full provenance
in the runtime index.

### Area cards

An area is the primary scene-loading entry point, but not the canonical owner
of every connected actor or situation.

```markdown
---
id: place.winters-daughter.area-13
type: module-place
title: The Knight's Tomb
topology_node: area-13
source_refs: [source.winters-daughter.page-19, source.winters-daughter.page-29]
verification: verified
load_with:
  actors:
    - actor.winters-daughter.sir-chyde
  situations:
    - situation.winters-daughter.sir-chyde-plea
  procedures: []
  knowledge:
    - knowledge.winters-daughter.sir-chyde-request
---

## First impression

Player-safe information that may be narrated when the party enters.

## Contents

Operationally relevant visible features and interactable objects.

## Discoverable

- **Portrait:** revealed by examining the dust-covered portrait.
- **Coffer contents:** revealed only after opening the coffer.

## Hidden

GM-only information, including motives, unrevealed relationships, and dormant
effects.

## Triggers

- Encountering the ghost activates
  `situation.winters-daughter.sir-chyde-plea`.

## Exits

Generated from canonical `topology.yaml`; do not edit independently.
```

### Actor cards

Actor cards should distinguish:

```markdown
## Appearance
## Role
## Goals
## Behavior and reactions
## Capabilities and mechanics
## Knowledge
## Hidden
```

Current campaign position, health, attitude, and inventory do not belong in
the immutable module card. They belong in campaign entity state or overrides.

### Situation cards

One file and one identity should own structured activation and GM-facing prose:

```markdown
---
id: situation.winters-daughter.sir-chyde-plea
type: module-situation
location_refs:
  - place.winters-daughter.area-13
participants:
  - actor.winters-daughter.sir-chyde
activation:
  type: encounter
  condition: The party can perceive Sir Chyde's ghost.
repeat: once
outcomes:
  - id: accept-request
    possible_effects:
      - kind: activate_thread
        target: thread.recover-sir-chydes-ring
---

## What the players perceive
## Pressure and stakes
## Likely approaches
## Actor reactions
## Consequences
## Completion conditions
```

`possible_effects` are baseline possibilities, not applied campaign changes.
They enter a checkpoint only after play establishes the outcome.

### Knowledge cards

Knowledge should retain typed truth and acquisition semantics:

```yaml
id: knowledge.winters-daughter.ring-binds-souls
type: fact
truth_status: confirmed
statement: The ring binds the souls of its paired bearers.
available_from:
  - actor.winters-daughter.sir-chyde
discoverable_at:
  - place.winters-daughter.area-13
acquisition:
  - Sir Chyde explains the ring after the party agrees to hear his request.
reveals: []
contradicts: []
```

A fact being true in the module does not make it player-known. Campaign
knowledge changes require a gameplay source event.

### Topology

`topology.yaml` remains the canonical baseline for:

- nodes;
- edges;
- directions;
- passage type;
- baseline state;
- requirements;
- barriers and hazards;
- dynamic mechanisms.

Area-card exits are generated slices. Campaign changes apply through a
topology overlay or checkpoint changes, never by editing the immutable
baseline during play.

### Audit data

Move or render extraction-only material under `module/audit/`:

- source page mappings;
- observation and pack IDs;
- confidence histories;
- coverage reports;
- conflict and uncertainty reports;
- review decisions.

Runtime prompts must explicitly exclude this directory.

## Runtime prompt contract

The Project instructions and `MANIFEST.md` should implement the following
loading sequence:

1. Read `CURRENT.md` and the active campaign files.
2. Identify the current place and its canonical `module_ref`.
3. Load that area card.
4. Apply `gm/module-overrides.md` entries keyed by canonical target ID.
5. Load the area's exact `load_with` actors and active situations.
6. Load procedures and knowledge referenced by the active situation.
7. During movement, load only the current topology node and adjacent edges.
8. Apply the campaign topology overlay.
9. Treat module effects as possibilities until play establishes an outcome.
10. Consult the PDF only for a missing detail, a conflict, or an audit.
11. Never expose `Hidden`, GM-only knowledge, audit data, or unacquired facts
    directly to players.

## Language policy

The current cards are primarily English while campaign-side files and prompts
are Russian. The cheapest and safest default is:

- preserve extracted source facts and exact mechanics in the source language;
- use stable structural headings;
- let the GM translate during narration;
- retain exact wording where a password, poem, prophecy, riddle, rule, or
  mechanical phrase depends on it.

If module prose must be narratable verbatim in Russian, translation becomes a
verified extraction-stage transformation, not a renderer concern.

## Implementation priorities

### Priority 1: make the existing module reachable

1. Add `module/` to `MANIFEST.md` and the Project prompt.
2. Define precedence between campaign state, overrides, module baseline, and
   PDF.
3. Add a small `MODULE.md` runtime entry point.

This immediately makes current cards usable even before the schema improves.

### Priority 2: repair identity and topology joins

1. Select one canonical ID convention.
2. Add alias and near-duplicate detection.
3. Merge complementary observations describing the same concept.
4. Require every mapped place to reference a topology node.
5. Render derived exits into area cards.
6. Make override targets resolve against module IDs.

This removes the most dangerous ambiguity in the current release.

### Priority 3: enrich operational semantics

1. Split player-safe, discoverable, and hidden content.
2. Expand place and actor contracts.
3. Give situations activation, pressure, choices, outcomes, completion, and
   repeat semantics.
4. Type knowledge by truth, availability, and acquisition.
5. Make possible effects schema-compatible with checkpoint changes without
   applying them automatically.

### Priority 4: separate runtime and audit views

1. Reduce `index.json` to routing data.
2. Keep raw observations and provenance in `audit/`.
3. Ensure gameplay prompts never load `module.json` or audit reports by
   default.
4. Validate that each scene can resolve an exact bounded context bundle.

## Final assessment

The current module is:

- good as bounded, source-cited extraction evidence;
- readable as individual Markdown summaries;
- structurally validated but not semantically canonical;
- too shallow and disconnected for reliable GM operation;
- currently unused by the runtime prompts.

The older representation is:

- much closer to the information architecture an LLM game master needs;
- especially strong in topology, situations, knowledge, source-state
  immutability, and selective loading;
- too fragmented, strict, and expensive to use wholesale.

The target should preserve:

- current deterministic extraction and Markdown packaging;
- old typed operational semantics;
- one canonical identity per concept;
- one canonical owner per relation;
- area-centered scene loading;
- explicit player-safe, discoverable, and GM-only boundaries;
- canonical module IDs in campaign overrides;
- typed but event-gated campaign effects;
- audit data outside normal play context;
- an explicit prompt path from current scene to relevant module files.
