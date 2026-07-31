---
id: "situation.module-lair-of-the-lamb.father-bastoval-enters-the-dungeon"
type: "situation"
title: "Father Bastoval Enters the Dungeon"
aliases: ["situation.bastoval-enters-after-lamb-death"]
source_pages: [20]
verification: verified
references: ["actor.module-lair-of-the-lamb.bilosh", "actor.module-lair-of-the-lamb.father-bastoval", "actor.module-lair-of-the-lamb.mino", "actor.module-lair-of-the-lamb.the-lamb"]
activation: {"condition": "Two hours after the Lamb is killed.", "type": "timed"}
repeat: {"mode": "once"}
locations: []
participants: [{"actor_id": "actor.module-lair-of-the-lamb.father-bastoval", "role": "Leader checking on the Lamb."}, {"actor_id": "actor.module-lair-of-the-lamb.mino", "role": "Elderly bodyguard."}, {"actor_id": "actor.module-lair-of-the-lamb.bilosh", "role": "Elderly bodyguard."}]
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.bilosh.md", "cards/actors/actor.module-lair-of-the-lamb.father-bastoval.md", "cards/actors/actor.module-lair-of-the-lamb.mino.md", "cards/actors/actor.module-lair-of-the-lamb.the-lamb.md"]
  procedures: []
  knowledge: []
# Possible effects are source possibilities. Nothing here is applied or copied into a checkpoint.
possible_effects: []
---

# Father Bastoval Enters the Dungeon

## What the players perceive

Father Bastoval enters with two elderly bodyguards to check on the Lamb.

## Pressure and stakes

- If the Lamb is dead, Bastoval hunts its killers.

## Likely approaches


## Actor reactions

- **Father Bastoval** (`actor.module-lair-of-the-lamb.father-bastoval`) takes part: Leader checking on the Lamb.
- **Mino** (`actor.module-lair-of-the-lamb.mino`) takes part: Elderly bodyguard.
- **Bilosh** (`actor.module-lair-of-the-lamb.bilosh`) takes part: Elderly bodyguard.

## Consequences

- Bastoval and his bodyguards check on the Lamb.
- If the Lamb is dead, they hunt the Lamb’s murderers.

### Possible effects

<!-- Source possibilities only. The runtime never applies these automatically and never copies them into a checkpoint. -->


## Completion conditions


### Repeat behavior

- Mode: once
