---
id: "place.module-lair-of-the-lamb.24c"
type: "place"
title: "24C"
aliases: ["location.24c"]
source_pages: [31]
verification: verified
references: ["effect.oil-layer-burning"]
topology_node: "place.module-lair-of-the-lamb.area-24c"
load_with:
  actors: []
  situations: []
  procedures: []
  knowledge: []
---

# 24C

## First impression

Water 10' deep is covered by a layer of oil.

## Contents

- Water, 10' deep.
- A surface layer of oil.

## Discoverable

- **Search the bottom of the 10'-deep water.** — Two flasks of oil and broken glass lie on the bottom.

## Hidden


## Triggers


## Hazards

- The surface oil burns for 5 minutes if ignited.

## Resources

- Two flasks of oil on the bottom.

## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.waypoint-24-crush-hallway

- Destination: `place.module-lair-of-the-lamb.waypoint-24-crush-hallway`
- Direction: inbound
- Passage kind: disguised spring trapdoor
- Baseline state: armed
- Visibility: hidden
- Barriers: perfectly disguised trapdoor
- Conditions: A touch greater than a feather triggers the hallway; the corresponding switch in 22 MUSHROOM can disarm this trapdoor while held.
- Hazards: 40-foot fall into oil-covered, 10-foot-deep water.; Broken glass on the bottom.
