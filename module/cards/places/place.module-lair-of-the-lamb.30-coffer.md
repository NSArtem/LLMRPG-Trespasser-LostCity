---
id: "place.module-lair-of-the-lamb.30-coffer"
type: "place"
title: "30 COFFER"
aliases: ["location.30-coffer"]
source_pages: [33]
verification: verified
references: ["effect.favored-by-shendormu", "item.module-lair-of-the-lamb.flasks-of-oil", "item.module-lair-of-the-lamb.invisibility-potion", "item.module-lair-of-the-lamb.tiny-green-mushroom"]
topology_node: "place.module-lair-of-the-lamb.area-30-coffer"
load_with:
  actors: []
  situations: []
  procedures: []
  knowledge: []
---

# 30 COFFER

## First impression

A tiny unlocked coffer sits here with a tiny green mushroom growing from its top; heavy bootsteps and humming are audible from 27 BALLISTA.

## Contents

- An unlocked tiny coffer.
- A tiny green mushroom growing from the coffer.

## Discoverable

- **Open the unlocked coffer.** — The coffer contains an invisibility potion and 2 flasks of oil.

## Hidden

- Eating the mushroom makes the eater Favored by Shendormu.
- None of the ghouls has seen this mushroom before.

## Triggers


## Hazards


## Resources

- An invisibility potion.
- Two flasks of oil.
- A tiny green mushroom.

## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.area-29-stage

- Destination: `place.module-lair-of-the-lamb.area-29-stage`
- Direction: both
- Passage kind: corridor
- Baseline state: open
- Visibility: visible

### place.module-lair-of-the-lamb.waypoint-24-crush-hallway

- Destination: `place.module-lair-of-the-lamb.waypoint-24-crush-hallway`
- Direction: conditional
- Passage kind: 90-foot crushing hallway
- Baseline state: armed
- Visibility: visible
- Barriers: lowering ceiling; three perfectly disguised spring trapdoors
- Conditions: Cross by sprinting and jumping the trapdoors, disarm trapdoors with the three switches in 22 MUSHROOM, climb along the wall with spikes and ropes, or brace the ceiling with an uncrushable object.
- Hazards: Crushing ceiling; Three 40-foot falls through trapdoors.

### place.module-lair-of-the-lamb.waypoint-31-traverse

- Destination: `place.module-lair-of-the-lamb.waypoint-31-traverse`
- Direction: both
- Passage kind: doorway
- Visibility: visible
- Barriers: wooden door shown on the map
