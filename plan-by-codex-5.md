# Implementation 5: campaign overlays and runtime integration

## Outcome

After this implementation, the LLM runtime deterministically combines the
immutable module baseline with current campaign state, module overrides, and
topology changes.

## Dependency

[Implementation 4](plan-by-codex-4.md) is complete and green.

## Clean-workspace rule

Tests generate a fresh small module through the complete extractor and then
create campaign state against its new canonical IDs. Do not point campaign
fixtures at any previously produced module.

## Work

### 1. Add canonical module references to campaign state

Update relevant campaign contracts and templates with:

- current `module_ref` for the active place;
- optional `module_refs` for active situations or cross-scene context;
- stable references from campaign NPC/location files to module baseline
  entities.

Validate every reference against verified runtime indexes.

### 2. Make module overrides deterministic

Require each override to target:

- a canonical module record;
- a topology node;
- a topology edge; or
- an entity created by a prior checkpoint.

Retain a display title for humans, but use target ID as the join key.

Reject:

- missing targets;
- ambiguous targets;
- duplicate contradictory overrides;
- unsafe paths or free-text-only targets.

### 3. Define topology overlay behavior

Keep module topology immutable.

The campaign overlay records changes such as:

- opened, locked, blocked, or destroyed passages;
- discovered secret routes;
- activated portals;
- changed traversal requirements;
- actor knowledge of a route.

Distinguish physical state from who knows that state.

### 4. Implement effective-state resolution

Resolve:

```text
module baseline
+ prior checkpoints
+ module overrides
+ topology overlay
= effective current state
```

Return provenance for every overridden value.

### 5. Update runtime prompts

The loading sequence becomes:

1. read `CURRENT.md` and required campaign files;
2. resolve the current canonical module place;
3. load its scene bundle;
4. apply entity overrides;
5. apply topology overlay;
6. load active situation, actors, procedures, and acquired/relevant knowledge;
7. consult the PDF only for missing detail, extraction conflict, or audit.

Prompts must never:

- reset campaign state to module baseline;
- reveal hidden module knowledge;
- treat possible effects as already applied;
- load `audit/` during normal play.

### 6. Update checkpoint contracts

- Validate module target IDs in changes.
- Require `source_event` before applying a possible module effect.
- Record knowledge acquisition separately from module truth.
- Update module overrides and topology overlay through checkpoint application,
  not direct module edits.

### 7. Update continuity audit

Audit:

- current place against `module_ref`;
- active situations;
- actor position and status;
- override target validity;
- topology effective state;
- acquired knowledge;
- completed one-shot situations;
- consumed or transferred module resources.

## Pipeline invariant

The extraction pipeline remains independently runnable. Campaign integration
activates only against a verified new-contract module.

Absence of a module is a valid preparation state. Presence of an incompatible
or incomplete module produces a clear validation error, not heuristic
fallback.

## Tests

Generate a fresh synthetic module, then test:

- an actor moved from its baseline location;
- a dead actor not restored by module data;
- a looted room;
- an opened secret door;
- a physically open route unknown to the party;
- a completed one-shot situation;
- knowledge acquired by only some subjects;
- a possible effect applied through a valid checkpoint event;
- a possible effect not applied without an event;
- an invalid free-text override target.

Run:

- clean extraction pipeline;
- campaign initialization against its output;
- checkpoint application;
- continuity audit;
- scene resolution before and after changes.

## Exit criteria

- Campaign state references verified canonical module IDs.
- Overrides resolve deterministically.
- Effective state is reproducible and provenance-aware.
- Module topology remains immutable.
- Knowledge truth and player acquisition remain distinct.
- Possible effects require gameplay events.
- Runtime prompts load a bounded effective scene.
- No incompatible or previously produced module is accepted.
- All tests and repository validation pass.

## Handoff to implementation 6

Implementation 6 may rely on a complete clean pipeline and a complete runtime
state model. It performs qualification and hardening, not migration.
