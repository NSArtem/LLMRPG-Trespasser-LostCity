---
id: "situation.module-lair-of-the-lamb.traditional-level-1-lock-in"
type: "situation"
title: "Traditional Level 1 Lock-In"
aliases: ["situation.traditional-level-one-lock-in"]
source_pages: [54]
verification: verified
references: ["actor.module-lair-of-the-lamb.townsfolk", "procedure.module-lair-of-the-lamb.traditional-level-1-entrance"]
activation: {"condition": "The GM uses the more traditional variant for equipped Level 1 characters.", "type": "chosen"}
repeat: {"mode": "once"}
locations: []
participants: [{"actor_id": "actor.module-lair-of-the-lamb.townsfolk", "role": "Lock the entrance to contain the beast and return to reopen it."}]
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.townsfolk.md"]
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.traditional-level-1-entrance.md"]
  knowledge: []
# Possible effects are source possibilities. Nothing here is applied or copied into a checkpoint.
possible_effects: []
---

# Traditional Level 1 Lock-In

## What the players perceive

Equipped Level 1 characters enter the dungeon through the iron door in 5 LANDING and are locked inside until the townsfolk return.

## Pressure and stakes

- The characters are locked in the dungeon until the entrance is reopened.
- The townsfolk are trying to prevent the beast from escaping.

## Likely approaches


## Actor reactions

- **Townsfolk** (`actor.module-lair-of-the-lamb.townsfolk`) takes part: Lock the entrance to contain the beast and return to reopen it.

## Consequences

- The townsfolk return and open the door after exactly 12 hours.

### Possible effects

<!-- Source possibilities only. The runtime never applies these automatically and never copies them into a checkpoint. -->


## Completion conditions

- Exactly 12 hours pass and the townsfolk return to open the iron door.

### Repeat behavior

- Mode: once
