---
id: "situation.module-lair-of-the-lamb.24-crush-hallway-trap"
type: "situation"
title: "24 CRUSH HALLWAY Trap"
aliases: ["situation.crush-hallway-trap"]
source_pages: [31]
verification: verified
references: ["effect.crush-hallway-ceiling", "effect.crush-hallway-trapdoor-fall", "place.module-lair-of-the-lamb.24-crush-hallway", "procedure.module-lair-of-the-lamb.cross-24-crush-hallway", "procedure.module-lair-of-the-lamb.disarm-the-trap-doors-in-24-crush-hallway"]
activation: {"condition": "Any touch greater than a feather in the hallway triggers the ceiling; stepping on a trap door triggers that floor panel.", "type": "triggered"}
repeat: {"condition": "The ceiling falls, rests, and resets; trap doors remain active unless their remote switches are held.", "mode": "repeatable"}
locations: ["cards/places/place.module-lair-of-the-lamb.24-crush-hallway.md"]
participants: []
load_with:
  actors: []
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.cross-24-crush-hallway.md", "cards/procedures/procedure.module-lair-of-the-lamb.disarm-the-trap-doors-in-24-crush-hallway.md"]
  knowledge: []
# Possible effects are source possibilities. Nothing here is applied or copied into a checkpoint.
possible_effects: []
---

# 24 CRUSH HALLWAY Trap

## What the players perceive

After someone enters the 90' hall, the ceiling begins descending toward the floor; hidden floor panels can spring open beneath runners.

## Pressure and stakes

- Entrants can be crushed by the ceiling.
- Runners can fall 40' through one of three disguised trap doors into the water chambers.

## Likely approaches


## Actor reactions


## Consequences

- A human can sprint the length without a Movement check for the ceiling.
- Movement checks are needed to jump the three trap doors unless disabled.
- The ceiling takes 10 seconds to fall 10', rests for 10 seconds, then resets.

### Possible effects

<!-- Source possibilities only. The runtime never applies these automatically and never copies them into a checkpoint. -->


## Completion conditions


### Repeat behavior

- Mode: repeatable
- Condition: The ceiling falls, rests, and resets; trap doors remain active unless their remote switches are held.
