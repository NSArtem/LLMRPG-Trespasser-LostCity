# Implementation 3: operational actors and situations

## Outcome

After this implementation, actor and situation cards contain enough
structured and prose information to run encounters. Each situation has one
canonical ID and one canonical file.

## Dependency

[Implementation 2](plan-by-codex-2.md) is complete and green.

## Clean-workspace rule

Update extraction contracts in place and start every validation run with new
packs and responses. Do not accept responses from an earlier contract.

## Work

### 1. Replace the actor evidence contract

Support:

- appearance;
- role;
- goals;
- behavior and reactions;
- relationships;
- capabilities and mechanics;
- knowledge references;
- hidden motivations or constraints;
- applicable locations and situations.

Separate observable material from GM-only material.

### 2. Render actor cards consistently

Use:

```markdown
## Appearance
## Role
## Goals
## Behavior and reactions
## Capabilities and mechanics
## Knowledge
## Hidden
```

Do not place mutable health, current position, attitude, or inventory in the
immutable baseline unless it is explicitly the source starting state and
clearly labeled as such.

### 3. Replace the situation evidence contract

Support:

- location references;
- activation type and condition;
- participants;
- pressure and stakes;
- likely approaches or decisions;
- procedure references;
- knowledge references;
- possible outcomes;
- completion conditions;
- repeat behavior;
- source uncertainty.

### 4. Use one situation identity

Do not create a separate flow object and Markdown-card identity.

Store structured activation and possible effects in front matter. Store
presentation and GM guidance in the body:

```markdown
## What the players perceive
## Pressure and stakes
## Likely approaches
## Actor reactions
## Consequences
## Completion conditions
```

### 5. Model possible effects without applying them

Possible effects may describe:

- activation of another situation;
- a future thread;
- an actor state change;
- a topology state change;
- reveal of knowledge;
- scheduling or stopping a procedure.

They describe source possibilities. They do not mutate campaign state and are
never copied automatically into a checkpoint.

### 6. Improve scene resolution

The scene resolver must:

- include actors required by the selected active situation;
- include situation cards available at the current place;
- avoid loading dormant unrelated situations;
- report possible effects without treating them as current facts.

Selection of which available situation is active remains an explicit runtime
decision.

## Pipeline invariant

The same change must update:

- focused prompts;
- response templates;
- validators;
- reconciliation;
- review queue;
- release gate;
- card rendering;
- indexes;
- scene resolver;
- documentation and tests.

A clean source with no actors or situations remains valid when its place
contract supports that absence.

## Tests

Create fresh scenarios for:

- a guard with public behavior and hidden orders;
- two same-name actors in different roles;
- a negotiation with several approaches;
- a one-shot hazard;
- a repeatable random encounter;
- a situation with a possible topology effect;
- an available but not active situation;
- an actor shared by two places without duplicated actor content.

Verify:

- correct visible/hidden separation;
- one situation file and ID;
- typed participant and location references;
- bounded scene loading;
- no automatic effect application;
- alias rewriting through actor and situation references.

Run the complete clean synthetic pipeline.

## Exit criteria

- Actor cards are sufficient for portrayal and adjudication.
- Situation cards are sufficient to present pressure, choices, and
  consequences.
- Every situation has one identity and canonical owner.
- Possible effects remain hypothetical in module output.
- Place bundles load only required actors and situations.
- No prior packs, responses, or produced output are read.
- The complete clean pipeline and repository validation pass.

## Handoff to implementation 4

Implementation 4 may rely on explicit actor knowledge references, situation
knowledge/procedure references, and event-gated possible effects.
