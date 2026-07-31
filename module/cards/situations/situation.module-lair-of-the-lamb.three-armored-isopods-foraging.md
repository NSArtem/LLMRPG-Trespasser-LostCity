---
id: "situation.module-lair-of-the-lamb.three-armored-isopods-foraging"
type: "situation"
title: "Three Armored Isopods Foraging"
aliases: ["situation.armored-isopod-encounter"]
source_pages: [34]
verification: verified
references: ["actor.module-lair-of-the-lamb.three-armored-isopods", "effect.armored-isopod-defense-curl", "place.module-lair-of-the-lamb.32-isopods"]
activation: {"condition": "The party enters 32 ISOPODS.", "type": "keyed"}
repeat: {"mode": "repeatable"}
locations: ["cards/places/place.module-lair-of-the-lamb.32-isopods.md"]
participants: [{"actor_id": "actor.module-lair-of-the-lamb.three-armored-isopods", "role": "Forage, curl defensively, and retaliate only if harmed."}]
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.three-armored-isopods.md"]
  procedures: []
  knowledge: []
# Possible effects are source possibilities. Nothing here is applied or copied into a checkpoint.
possible_effects: []
---

# Three Armored Isopods Foraging

## What the players perceive

Three armored isopods forage calmly and ignore the party.

## Pressure and stakes

- Provoking the isopods can trigger a fight against creatures protected by Defense Curl.

## Likely approaches


## Actor reactions

- **Three Armored Isopods** (`actor.module-lair-of-the-lamb.three-armored-isopods`) takes part: Forage, curl defensively, and retaliate only if harmed.
- **Three Armored Isopods** (`actor.module-lair-of-the-lamb.three-armored-isopods`) — Ignore the party if left alone, curl if poked, and fight back if damaged.

## Consequences

- Unprovoked isopods continue foraging and ignore the party.
- Poked isopods curl into balls.
- Damaged isopods fight back.

### Possible effects

<!-- Source possibilities only. The runtime never applies these automatically and never copies them into a checkpoint. -->


## Completion conditions


### Repeat behavior

- Mode: repeatable
