---
id: "place.module-lair-of-the-lamb.18-shaft"
type: "place"
title: "18 SHAFT"
aliases: ["location.18-shaft"]
source_pages: [25]
verification: verified
references: []
topology_node: "place.module-lair-of-the-lamb.area-18-shaft"
load_with:
  actors: []
  situations: []
  procedures: []
  knowledge: []
---

# 18 SHAFT

## First impression

A 7-foot-high heap of broken beams and bricks, apparently a shattered gazebo but actually a fallen elevator, sits amid loops of soft rotten rope. A shaft rises 60 feet, with a visible ledge 40 feet up.

## Contents

- Fallen elevator wreckage, 7 feet high.
- Broken beams and loose bricks.
- Loops of soft, rotten rope.
- High shaft terminating 60 feet above.
- Visible ledge 40 feet above.

## Discoverable

- **Search the wreckage.** — A block and tackle is hidden in the wreckage.

## Hidden


## Triggers


## Hazards


## Resources

- Block and tackle.

## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.area-16-mold

- Destination: `place.module-lair-of-the-lamb.area-16-mold`
- Direction: both
- Passage kind: corridor
- Baseline state: open
- Visibility: visible

### place.module-lair-of-the-lamb.waypoint-18a-ledge

- Destination: `place.module-lair-of-the-lamb.waypoint-18a-ledge`
- Direction: conditional
- Passage kind: shaft climb
- Baseline state: open
- Visibility: visible
- Conditions: Reach the ledge by climbing or rigging the block and tackle found in the wreckage.
- Hazards: A fall of up to 40 feet.
