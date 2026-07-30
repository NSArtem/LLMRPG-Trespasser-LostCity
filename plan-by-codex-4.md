# Implementation 4: typed knowledge, procedures, and reference material

## Outcome

After this implementation, the GM can distinguish truth from availability,
determine how information is acquired, run repeatable procedures, and load
mechanical reference cards without collapsing them into generic text blobs.

## Dependency

[Implementation 3](plan-by-codex-3.md) is complete and green.

## Clean-workspace rule

All prompts, packs, and responses are newly generated for this contract.
No earlier knowledge cards, procedure cards, or review decisions are inputs.

## Work

### 1. Replace the knowledge evidence contract

Support kinds:

- fact;
- secret;
- clue;
- claim;
- rumor;
- false or mixed claim;
- solution.

Require:

- statement;
- truth status;
- available-from references;
- discoverable-at references;
- acquisition conditions;
- reveals;
- corroborates;
- contradicts;
- source pages.

Truth and player acquisition are separate dimensions.

### 2. Render knowledge cards

Use structured front matter for kind, truth, availability, and relations.
Use the Markdown body for precise operational explanation and GM guidance.

The runtime index must route a knowledge ID without exposing its statement.
This prevents the index itself from leaking secrets.

### 3. Replace the procedure evidence contract

Support:

- trigger;
- ordered steps;
- transitions;
- stop conditions;
- reset conditions;
- schedule when present;
- applicable actors, situations, and places;
- source mechanics.

Keep optional structures absent when the source describes a simple procedure.

### 4. Render procedure cards

Use:

```markdown
## Trigger
## Steps
## Transitions
## Stop conditions
## Reset conditions
## Source mechanics
```

Do not force schedules or state machines onto one-shot instructions.

### 5. Improve reference cards

Define stable operational formatting for:

- rules;
- tables;
- items;
- spells;
- classes;
- effects.

Preserve exact names, numbers, table entries, and mechanically significant
wording. Separate an item's baseline description from possible effects and
limitations.

### 6. Connect scene references

- Actor cards reference knowledge they can supply.
- Places reference discoverable knowledge.
- Situations reference knowledge they may reveal.
- Situations and actors reference procedures they use.
- The scene resolver loads only knowledge/procedures explicitly needed for the
  active situation or current action.

### 7. Align with checkpoint vocabulary

Make knowledge IDs valid targets for checkpoint knowledge changes.
Make possible effect shapes compatible with checkpoint changes where useful.

Do not apply either automatically. A checkpoint requires an actual gameplay
source event and adjudicated result.

## Pipeline invariant

The new semantic shapes must be reflected in extraction prompts, response
validation, reconciliation, review, rendering, indexes, and scene resolution
in the same implementation.

A module without procedures, spells, classes, or items remains valid.

## Tests

Create fresh synthetic cases for:

- a true secret not yet known by players;
- a false rumor;
- two clues revealing one fact;
- a claim contradicted by a physical clue;
- a recurring patrol;
- a mechanism with a stop condition;
- a simple one-shot procedure;
- an item with a benefit and limitation;
- a table whose entries must remain exact.

Verify:

- truth is distinct from acquisition;
- indexes do not leak secret statements;
- knowledge relations resolve;
- procedure optionality remains compact;
- exact mechanics survive rendering;
- scene bundles include only relevant knowledge and procedures;
- no possible effect becomes campaign state without an event.

Run the complete clean synthetic pipeline.

## Exit criteria

- Knowledge truth, availability, and acquisition are explicit.
- Procedures can be run without reconstructing steps from prose.
- Reference cards preserve exact operational mechanics.
- Scene loading remains bounded and secret-safe.
- Checkpoint compatibility does not imply automatic state mutation.
- No previously produced artifacts are read.
- The complete clean pipeline and repository validation pass.

## Handoff to implementation 5

Implementation 5 may rely on stable module entity IDs, knowledge references,
possible effects, topology IDs, and complete scene bundles.
