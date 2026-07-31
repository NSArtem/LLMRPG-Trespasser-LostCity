---
id: "situation.module-lair-of-the-lamb.little-lambs-emerge-from-the-corpse"
type: "situation"
title: "Little Lambs Emerge from the Corpse"
aliases: ["situation.little-lambs-emerge"]
source_pages: [20]
verification: verified
references: ["actor.module-lair-of-the-lamb.the-lamb", "actor.module-lair-of-the-lamb.the-little-lambs", "effect.little-lamb-emergence"]
activation: {"condition": "The Lamb is killed and its corpse is not utterly destroyed.", "type": "triggered"}
repeat: {"mode": "once"}
locations: []
participants: [{"actor_id": "actor.module-lair-of-the-lamb.the-little-lambs", "role": "New predators emerging from the corpse."}]
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.the-lamb.md", "cards/actors/actor.module-lair-of-the-lamb.the-little-lambs.md"]
  procedures: []
  knowledge: []
# Possible effects are source possibilities. Nothing here is applied or copied into a checkpoint.
possible_effects: []
---

# Little Lambs Emerge from the Corpse

## What the players perceive

After a quiet delay, three Little Lambs chew their way out of the Lamb’s corpse.

## Pressure and stakes

- Three new hostile creatures enter the dungeon.

## Likely approaches


## Actor reactions

- **The Little Lambs** (`actor.module-lair-of-the-lamb.the-little-lambs`) takes part: New predators emerging from the corpse.

## Consequences

- Three Little Lambs become active after waiting quietly inside the corpse.

### Possible effects

<!-- Source possibilities only. The runtime never applies these automatically and never copies them into a checkpoint. -->


## Completion conditions

- All three Little Lambs have emerged, or the corpse is utterly destroyed before they emerge.

### Repeat behavior

- Mode: once
