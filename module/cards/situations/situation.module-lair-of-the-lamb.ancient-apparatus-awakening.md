---
id: "situation.module-lair-of-the-lamb.ancient-apparatus-awakening"
type: "situation"
title: "Ancient Apparatus Awakening"
aliases: ["situation.41-apparatus-awakening"]
source_pages: [37]
verification: verified
references: ["actor.module-lair-of-the-lamb.ancient-apparatus-of-anguish", "effect.ancient-apparatus-stone", "effect.ancient-tone", "effect.anguish-pattern", "place.module-lair-of-the-lamb.sunken-shrine"]
activation: {"condition": "Two rounds after someone enters the Sunken Shrine, whether by falling or another route.", "type": "timed"}
repeat: {"mode": "once"}
locations: ["cards/places/place.module-lair-of-the-lamb.sunken-shrine.md"]
participants: [{"actor_id": "actor.module-lair-of-the-lamb.ancient-apparatus-of-anguish", "role": "Attacks intruders and attempts to escape."}]
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.ancient-apparatus-of-anguish.md"]
  procedures: []
  knowledge: []
# Possible effects are source possibilities. Nothing here is applied or copied into a checkpoint.
possible_effects: [{"description": "An escaped ancient apparatus can be added to the wandering monster table.", "effect": "future-thread"}]
---

# Ancient Apparatus Awakening

## What the players perceive

Two rounds after someone enters, the submerged quadrupedal statue begins attacking and tries to climb out of the pit. At half hit points it starts bleeding despite its stone exterior.

## Pressure and stakes

- Intruders face slam and Ancient Tone damage.
- An escaping apparatus may become a wandering monster.

## Likely approaches


## Actor reactions

- **Ancient Apparatus of Anguish** (`actor.module-lair-of-the-lamb.ancient-apparatus-of-anguish`) takes part: Attacks intruders and attempts to escape.
- **Ancient Apparatus of Anguish** (`actor.module-lair-of-the-lamb.ancient-apparatus-of-anguish`) — On losing half its hit points, it begins bleeding and attempts to escape the room.

## Consequences

- If it escapes, it can be added to the wandering monster table.

### Possible effects

<!-- Source possibilities only. The runtime never applies these automatically and never copies them into a checkpoint. -->

- `future-thread` — An escaped ancient apparatus can be added to the wandering monster table.

## Completion conditions


### Repeat behavior

- Mode: once
