---
id: "place.module-lair-of-the-lamb.22-mushroom"
type: "place"
title: "22 MUSHROOM"
aliases: ["location.22-mushroom"]
source_pages: [30]
verification: verified
references: ["effect.favored-by-shendormu", "procedure.module-lair-of-the-lamb.disarm-the-trap-doors-in-24-crush-hallway"]
topology_node: "place.module-lair-of-the-lamb.area-22-mushroom"
load_with:
  actors: []
  situations: []
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.disarm-the-trap-doors-in-24-crush-hallway.md"]
  knowledge: []
---

# 22 MUSHROOM

## First impression

A locked door stands to the north; the south door is carved with “ASSHOLE STORAGE”; a huge cobweb partly blocks the east route; a tiny green mushroom grows in exposed dirt in the southwest corner.

## Contents

- A locked door to the north.
- A defaced south door bearing the words “ASSHOLE STORAGE”.
- A huge cobweb partly blocking the path east to 24 CRUSH HALLWAY.
- A tiny green mushroom growing in exposed dirt.

## Discoverable

- **Dig 10' beneath the mushroom.** — A dagger, a sling, and an empty wineskin are buried beneath the mushroom.
- **Reach 3' into a wall hole and continually depress its switch.** — Each of three wall holes contains a switch 3' deep that disarms one trap door in 24 CRUSH HALLWAY while continuously depressed.

## Hidden

- Eating the mushroom makes the eater Favored by Shendormu.

## Triggers


## Hazards


## Resources

- A tiny green mushroom.
- A buried dagger, sling, and empty wineskin.

## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.area-23-weak-floor

- Destination: `place.module-lair-of-the-lamb.area-23-weak-floor`
- Direction: conditional
- Passage kind: doorway
- Baseline state: closed
- Visibility: visible
- Barriers: locked north door
- Conditions: The locked door must be opened or bypassed.

### place.module-lair-of-the-lamb.area-25a-crypt

- Destination: `place.module-lair-of-the-lamb.area-25a-crypt`
- Direction: both
- Passage kind: south doorway
- Visibility: visible
- Barriers: defaced wooden door shown on the map

### place.module-lair-of-the-lamb.boundary-21-heavy-doors

- Destination: `place.module-lair-of-the-lamb.boundary-21-heavy-doors`
- Direction: conditional
- Passage kind: heavy iron doorway
- Baseline state: closed
- Visibility: visible
- Barriers: 10-foot heavy bar; chains
- Conditions: Two people can pry the bar aside for a narrow opening; heavy tools are needed to remove the chain for full opening.

### place.module-lair-of-the-lamb.waypoint-24-crush-hallway

- Destination: `place.module-lair-of-the-lamb.waypoint-24-crush-hallway`
- Direction: both
- Passage kind: east path
- Baseline state: open
- Visibility: visible
- Barriers: huge cobweb partially blocking the path
