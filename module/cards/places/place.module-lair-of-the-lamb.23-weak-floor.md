---
id: "place.module-lair-of-the-lamb.23-weak-floor"
type: "place"
title: "23 WEAK FLOOR"
aliases: ["location.23-weak-floor"]
source_pages: [30]
verification: verified
references: ["effect.weak-floor-collapse", "situation.module-lair-of-the-lamb.collapse-of-23-weak-floor"]
topology_node: "place.module-lair-of-the-lamb.area-23-weak-floor"
load_with:
  actors: []
  situations: ["cards/situations/situation.module-lair-of-the-lamb.collapse-of-23-weak-floor.md"]
  procedures: []
  knowledge: []
---

# 23 WEAK FLOOR

## First impression

The brick floor sags about 2' at the center, water drips from the ceiling, and a mummified head with sewn eyes and mouth lies exactly in the middle with something shiny in its teeth.

## Contents

- A mummified head with its eyes and mouth sewn shut.
- A shiny object held in the head's teeth.

## Discoverable

- **Inspect and retrieve the objects from the mummified head's teeth.** — The shiny objects are 10g coins and a note reading “now we're paid up, rat fuck”.

## Hidden

- Small thrown objects cause localized collapses.
- More than 10' from the south door, 40 lbs is enough to collapse every remaining brick floor tile.
- The far door is practically impossible to smash from an unstable climbing position unless first weakened by acid or fire; a ballista bolt opens it instantly.

## Triggers


## Hazards

- The weak brick floor can collapse completely under 40 lbs once more than 10' from the south door.

## Resources


## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.area-22-mushroom

- Destination: `place.module-lair-of-the-lamb.area-22-mushroom`
- Direction: conditional
- Passage kind: doorway
- Baseline state: closed
- Visibility: visible
- Barriers: locked north door
- Conditions: The locked door must be opened or bypassed.

### place.module-lair-of-the-lamb.area-36-table

- Destination: `place.module-lair-of-the-lamb.area-36-table`
- Direction: conditional
- Passage kind: room crossing and far doorway
- Baseline state: closed
- Visibility: visible
- Barriers: far door; unstable brick floor
- Conditions: Cross the unstable floor and open the far door; the door is effectively impossible to smash from the unstable floor unless weakened by acid or fire, while a ballista bolt opens it instantly.
- Hazards: Total floor collapse beneath a load of 40 pounds beyond 10 feet from the south door.
