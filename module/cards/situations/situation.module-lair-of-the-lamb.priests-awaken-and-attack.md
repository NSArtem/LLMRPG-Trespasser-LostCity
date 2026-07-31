---
id: "situation.module-lair-of-the-lamb.priests-awaken-and-attack"
type: "situation"
title: "Priests Awaken and Attack"
aliases: ["situation.priests-awaken-and-attack"]
source_pages: [26]
verification: verified
references: ["actor.module-lair-of-the-lamb.priest-of-the-pool", "actor.module-lair-of-the-lamb.vandress", "place.module-lair-of-the-lamb.19-priests", "place.module-lair-of-the-lamb.20-pools"]
activation: {"condition": "Any one of the priests is touched.", "type": "triggered"}
repeat: {"mode": "once"}
locations: ["cards/places/place.module-lair-of-the-lamb.19-priests.md", "cards/places/place.module-lair-of-the-lamb.20-pools.md"]
participants: [{"actor_id": "actor.module-lair-of-the-lamb.priest-of-the-pool", "role": "The touched priest screams; all three Priests of the Pool awaken and attack."}, {"actor_id": "actor.module-lair-of-the-lamb.vandress", "role": "Awakens in area 20 and attacks with the other priests."}]
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.priest-of-the-pool.md", "cards/actors/actor.module-lair-of-the-lamb.vandress.md"]
  procedures: []
  knowledge: []
# Possible effects are source possibilities. Nothing here is applied or copied into a checkpoint.
possible_effects: [{"description": "All three Priests of the Pool awaken and attack.", "effect": "actor-state", "target": "actor.module-lair-of-the-lamb.priest-of-the-pool"}, {"description": "Vandress awakens and attacks.", "effect": "actor-state", "target": "actor.module-lair-of-the-lamb.vandress"}]
---

# Priests Awaken and Attack

## What the players perceive

When any priest is touched, that priest screams aloud and psychically. All four priests, including Vandress in the next area, awaken and attack.

## Pressure and stakes

- The party faces all four priests at once.

## Likely approaches


## Actor reactions

- **Priest of the Pool** (`actor.module-lair-of-the-lamb.priest-of-the-pool`) takes part: The touched priest screams; all three Priests of the Pool awaken and attack.
- **Vandress** (`actor.module-lair-of-the-lamb.vandress`) takes part: Awakens in area 20 and attacks with the other priests.
- **Priest of the Pool** (`actor.module-lair-of-the-lamb.priest-of-the-pool`) — The touched priest screams verbally and psychically, and all three attack once awakened.
- **Vandress** (`actor.module-lair-of-the-lamb.vandress`) — Awakens and attacks.

## Consequences

- All four priests awaken and attack.

### Possible effects

<!-- Source possibilities only. The runtime never applies these automatically and never copies them into a checkpoint. -->

- `actor-state` → **Priest of the Pool** (`actor.module-lair-of-the-lamb.priest-of-the-pool`) — All three Priests of the Pool awaken and attack.
- `actor-state` → **Vandress** (`actor.module-lair-of-the-lamb.vandress`) — Vandress awakens and attacks.

## Completion conditions


### Repeat behavior

- Mode: once
