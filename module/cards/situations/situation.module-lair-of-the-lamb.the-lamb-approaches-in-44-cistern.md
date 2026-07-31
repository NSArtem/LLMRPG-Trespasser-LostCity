---
id: "situation.module-lair-of-the-lamb.the-lamb-approaches-in-44-cistern"
type: "situation"
title: "The Lamb Approaches in 44 CISTERN"
aliases: ["situation.44-cistern-lamb-approach"]
source_pages: [40]
verification: verified
references: ["actor.module-lair-of-the-lamb.the-lamb-25359288", "effect.44-cistern-ammonia-warning", "place.module-lair-of-the-lamb.44-cistern", "procedure.module-lair-of-the-lamb.calculate-human-swim-speed-in-44-cistern", "procedure.module-lair-of-the-lamb.calculate-makeshift-table-boat-speed"]
activation: {"condition": "Someone enters the central 50-foot-by-50-foot area of 44 CISTERN.", "type": "triggered"}
repeat: null
locations: ["cards/places/place.module-lair-of-the-lamb.44-cistern.md"]
participants: [{"actor_id": "actor.module-lair-of-the-lamb.the-lamb-25359288", "role": "Pursues the person who entered the center."}]
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.the-lamb-25359288.md"]
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.calculate-human-swim-speed-in-44-cistern.md", "cards/procedures/procedure.module-lair-of-the-lamb.calculate-makeshift-table-boat-speed.md"]
  knowledge: []
# Possible effects are source possibilities. Nothing here is applied or copied into a checkpoint.
possible_effects: [{"condition": "Two rounds pass after it starts approaching.", "description": "The Lamb changes from submerged approach to surface swimming.", "effect": "actor-state", "target": "actor.module-lair-of-the-lamb.the-lamb-25359288"}]
---

# The Lamb Approaches in 44 CISTERN

## What the players perceive

After someone enters the center of the cistern, the Lamb closes through the water. One round later an ammonia stink fills the air; on the following round the Lamb swims at the surface.

## Pressure and stakes

- Swimmers and passengers have only a short warning before the Lamb reaches surface pursuit.

## Likely approaches

- Swim away while accounting for carried-item penalties.
- Use a makeshift boat and paddles.
- Prepare to fight or lure the Lamb into the noria.

## Actor reactions

- **The Lamb** (`actor.module-lair-of-the-lamb.the-lamb-25359288`) takes part: Pursues the person who entered the center.
- **The Lamb** (`actor.module-lair-of-the-lamb.the-lamb-25359288`) — Starts swimming toward the intruders; after one round urinates in anticipation, then surfaces one round later.

## Consequences

- The Lamb continues its pursuit at 10 feet per round.
- The ammonia stink warns that the Lamb will surface on the next round.

### Possible effects

<!-- Source possibilities only. The runtime never applies these automatically and never copies them into a checkpoint. -->

- `actor-state` → **The Lamb** (`actor.module-lair-of-the-lamb.the-lamb-25359288`) — The Lamb changes from submerged approach to surface swimming. (condition: Two rounds pass after it starts approaching.)

## Completion conditions

- The Lamb begins swimming on the surface.

### Repeat behavior
