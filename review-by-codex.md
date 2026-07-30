# Review of the module representation

I interpreted `model/` as the existing `module/`, and
`feature/module_extractor` as the branch `feature/module-extractor`.

## Verdict

The current `module/` is a decent extraction/audit product, but a poor runtime
model for the LLM game master. The older `feature/module-extractor` design
models gameplay much better, although it is too elaborate and fragmented to
adopt unchanged.

The best direction is:

> Keep the current branch's simple Markdown-card packaging and deterministic
> index, but adopt the older branch's semantic model and prompt integration.

### Important qualification

`feature/module-extractor` does not contain a completed root `module/`. It
contains the proposed contract, schemas, templates, and representative test
fixtures. Therefore, this compares:

- the real current Winter's Daughter output;
- the intended final structure represented by `feature/module-extractor`.

## Current `module/`

The current output contains:

- 256 Markdown cards;
- 52 locations;
- 42 actors;
- 39 situations;
- 42 procedures;
- 39 knowledge records;
- 19 topology nodes and 22 passages;
- a 104 KB global index;
- a nearly 800 KB canonical `module.json`;
- approximately 2 MB total.

The basic card format is pleasantly lightweight: ID, type, source pages,
references, and operational fields. The renderer is straightforward and
predictable in
[rendering.py](module-extractor/module_extractor/rendering.py#L21).

### What works well

- Individual cards are compact enough to load into an LLM context.
- IDs and references permit graph-like navigation.
- Source pages are retained.
- Rules, items, tables, effects, actors, locations, and adventure content use
  one common mechanism.
- The extraction artifact retains observations, confidence, coverage, and
  review information.
- `module/index.json` provides deterministic ID-to-file lookup.
- Campaign-independent source material is kept separate from mutable campaign
  files.

### Critical weaknesses

#### 1. The GM prompts do not use `module/`

This is the largest problem.

The current manifest tells the model to load campaign NPC/location files and
the PDF, but never tells it to load module cards or the module index. See
[MANIFEST.md](MANIFEST.md#L31).

Likewise, the Project prompt defines the adventure PDF—not `module/`—as the
source baseline and says to consult current entities, overrides, and then the
PDF. See
[SETUP_AND_PROMPTS.md](chatgpt-project/SETUP_AND_PROMPTS.md#L75).

Consequently, the generated module is effectively orphaned. Even a perfect
representation is useless if the runtime prompt never discovers or loads it.

#### 2. The semantic contracts are too shallow

The required fields are minimal:

- location: title and description;
- actor: title and role;
- situation: title and trigger;
- procedure: title, trigger, steps;
- knowledge: title and text.

See
[contracts.py](module-extractor/module_extractor/contracts.py#L62).

These fields preserve summaries, but they do not reliably tell a game master:

- what to present immediately;
- what remains secret;
- what an actor wants or knows;
- how an actor reacts;
- what activates an encounter;
- what choices the players have;
- what consequences change world state;
- whether an event repeats;
- how a clue is acquired;
- whether a statement is true, false, a rumor, or an interpretation;
- which situation is active at a location.

For example, the current Sir Chyde situation contains only a trigger and a
one-sentence outcome:
[Sir Chyde's plea](module/cards/entities/winters-daughter.situation.area-13-sir-chydes-plea.md#L8).
That is evidence, but not enough structure for reliably running the encounter.

#### 3. Duplicate concepts remain separate canonical entities

There are at least 19 groups with identical type and title, including:

- two Sir Chyde actors;
- three Princess Snowfall-at-Dusk actors;
- two Ring of Soul-Binding items;
- duplicated locations for areas 3–14.

For example, area 13 exists as both:

- [the page-29 version](module/cards/entities/winters-daughter.location.area-13-the-knights-tomb.md#L1);
- [the page-19 version](module/cards/entities/location-area-13-knights-tomb.md#L1).

These contain complementary information but are not aliased or merged.
Meanwhile, `index.json` has an empty `aliases` object:
[index.json](module/index.json#L1).

An LLM may load either version and miss relevant facts, or load both and treat
them as separate places.

#### 4. Topology is disconnected from location cards

Topology uses IDs such as `area-13`, while location records use IDs such as:

- `location-area-13-knights-tomb`;
- `winters-daughter.location.area-13-the-knights-tomb`.

None of the 52 location IDs directly matches a topology node ID, and the
location cards have no `topology_node` field.

Thus, the LLM must infer that `area-13` corresponds to those location cards.
That is exactly the kind of implicit join that becomes unreliable under
limited context.

#### 5. The global index is not scene-oriented

The index maps IDs to files, but it does not answer the most important runtime
question:

> Given the current location or situation, what exact bundle of cards should
> the GM load?

It lacks explicit fields such as:

- `topology_node`;
- `active_situations`;
- `load_with`;
- `available_actors`;
- `relevant_procedures`;
- `discoverable_knowledge`;
- `player_visible` or `knowledge_level`.

Loading the complete 104 KB index for every scene is wasteful, while searching
it heuristically is unreliable.

#### 6. Audit and runtime representations are mixed

`module/module.json` includes raw observations, confidence details, coverage,
packs, conflicts, review hashes, and release-gate data. That is valuable for
extraction auditing, but it is not useful GM context.

The runtime representation should not require the model to navigate an 800 KB
audit-oriented document.

## `feature/module-extractor`

The older design is significantly stronger as an operational model.

| Concern | Current representation | Older representation |
| --- | --- | --- |
| Locations | Title and description | Impression, occupants, triggers, hazards, resources, exits |
| Actors | Title and role | Goals, behavior, knowledge, reactions, mechanics |
| Situations | Trigger and sometimes outcome | Activation, location, participants, pressure, decisions, outcomes, completion, repeat |
| Knowledge | Undifferentiated text | Fact/clue/rumor/claim, truth status, acquisition, discoverability, reveals |
| Procedures | Trigger and prose steps | Schedules, transitions, stop/reset conditions, source mechanics |
| Topology | Nodes and passages | Typed edges, state, requirements, hazards, directions, mechanisms |
| Runtime loading | Not integrated | Explicit `module_ref`, topology slice, situation bundle |
| Campaign changes | Overrides only | Immutable baseline plus topology overlay and overrides |

Its most valuable ideas are:

- `module/` is an immutable pre-campaign baseline.
- Campaign changes live in entity files, overrides, checkpoints, and a topology
  overlay.
- Locations point explicitly to topology nodes.
- Knowledge distinguishes truth from availability.
- Situations represent playable decision points, not merely passages of source
  text.
- Effects can change route or entity state.
- The prompt loads the current place, adjacent topology, active situation,
  participants, procedures, and only related knowledge.
- The PDF becomes a cold audit source instead of default runtime context.

Those concepts align closely with what an LLM game master needs.

### Where the older design goes too far

Its final representation is overengineered in several respects:

- Operational data is split among Markdown cards, topology YAML,
  situation-flow YAML, knowledge YAML, procedure YAML, source indexes, and
  audit files.
- A situation has separate identities for its YAML object and Markdown card.
- Finding everything needed to run one encounter can require several joins.
- Mandatory geometry, measurements, schedules, typed links, ownership rules,
  and verification fields impose substantial authoring cost even when
  irrelevant.
- Strict graph schemas make ordinary adventure prose difficult to represent
  without many `unknown` values.
- Generated Mermaid/SVG views add maintenance surface but little runtime value.
- The model must understand which relation is canonical in which file.

That complexity likely contributed to the infeasible extraction workflow, but
it would also hurt runtime loading if retained unchanged.

## Recommended final representation

Use one canonical Markdown card per operational concept, with small structured
front matter. Keep topology separate because reachability and mutable route
state genuinely benefit from a graph.

```text
module/
  manifest.md
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
```

A place card should resemble:

```yaml
---
id: place.winters-daughter.area-13
type: place
title: The Knight's Tomb
topology_node: area-13
source_pages: [19, 29]
knowledge_level: gm-secret
load_with:
  situations:
    - situation.winters-daughter.sir-chyde-plea
  actors:
    - actor.winters-daughter.sir-chyde
  procedures: []
---
```

Its body should contain stable, type-specific headings:

```markdown
## First impression
## Features
## Occupants
## Triggers
## Hazards
## Resources
## Exits
## GM secrets
```

A situation card should directly own both its structured activation metadata
and GM-facing prose:

```yaml
---
id: situation.winters-daughter.sir-chyde-plea
type: situation
location_refs: [place.winters-daughter.area-13]
participants: [actor.winters-daughter.sir-chyde]
activation: encounter
repeat: once
outcomes:
  - id: accept-request
    effects:
      - activate_thread: recover-ring
---
```

Body:

```markdown
## What the players perceive
## Pressure and stakes
## Likely approaches
## Actor reactions
## Consequences
## Completion conditions
```

This avoids the older design's separate flow identity while preserving its
operational semantics.

## Prompt-loading contract

The runtime prompt should restore the older branch's loading logic in
simplified form:

1. Read `CURRENT.md` and the active campaign files.
2. Apply `gm/module-overrides.md`.
3. Follow `module_refs` from the current scene/location.
4. Load the current place card.
5. Load its `load_with` actors and active situations.
6. Load procedures and knowledge referenced by those situations.
7. For movement, load only the current topology node and adjacent edges.
8. Apply the campaign topology overlay.
9. Consult the PDF only for a missing detail, extraction conflict, or audit.
10. Never expose GM-only module text directly to players.

## Final assessment

The current representation is approximately:

- good as extracted evidence;
- acceptable as human-readable cards;
- weak as a canonical adventure model;
- currently unusable as intended by the GM prompts.

The older representation is:

- much better aligned with LLM game-master reasoning;
- stronger about secrets, decisions, state transitions, topology, and
  selective loading;
- too fragmented and strict to use wholesale.

The right architecture is therefore **old semantics + current packaging +
explicit prompt integration**. The highest-priority fixes are:

1. connect `module/` to `MANIFEST.md` and the Project prompt;
2. merge or alias duplicate concepts;
3. link every place to a topology node;
4. enrich actors, situations, knowledge, and procedures with operational
   fields;
5. add scene-oriented `load_with` bundles;
6. keep extraction audit data outside normal runtime context.
