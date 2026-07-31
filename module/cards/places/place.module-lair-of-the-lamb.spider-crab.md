---
id: "place.module-lair-of-the-lamb.spider-crab"
type: "place"
title: "Spider Crab"
aliases: ["location.43-spider-crab"]
source_pages: [38]
verification: verified
references: ["actor.module-lair-of-the-lamb.spider-crab", "effect.spider-crab-grab", "situation.module-lair-of-the-lamb.spider-crab-in-the-pool"]
topology_node: "place.module-lair-of-the-lamb.area-43-spider-crab"
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.spider-crab.md"]
  situations: ["cards/situations/situation.module-lair-of-the-lamb.spider-crab-in-the-pool.md"]
  procedures: []
  knowledge: []
---

# Spider Crab

## First impression

A pool of unusually murky brown water lies 10 feet deep, with the floor above 40 feet above the water's surface.

## Contents

- Brown water 10 feet deep and much murkier than usual.
- Occupant: A giant undead spider crab, formerly a high priestess of Vandoh.

## Discoverable

- **Notice the eyestalks or otherwise detect the hidden crab.** — A giant spider crab is watching from the water with its eyestalks near the surface.

## Hidden

- A giant undead spider crab hides in the water.
- The crab is all that remains of a high priestess of Vandoh.
- The crab can reach 38 feet out of the water, two feet short of the floor above.
- If a large object is dropped into the pool, the crab eventually uses it as a platform to escape.

## Triggers

- The first time the crab notices that it has been noticed, it hides for a few seconds.
- Anything dropped within its 38-foot reach causes it to lunge.
- Dropping a large object such as a table or ballista into the pool eventually lets the crab stand on it and escape.

## Hazards

- The hidden giant undead spider crab lunges at anything that falls within reach.

## Resources


## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.area-42-sunken-gallery

- Destination: `place.module-lair-of-the-lamb.area-42-sunken-gallery`
- Direction: both
- Passage kind: flooded corridor and doorway
- Visibility: visible
- Barriers: metal door shown on the map

### place.module-lair-of-the-lamb.boundary-east-of-43

- Destination: `place.module-lair-of-the-lamb.boundary-east-of-43`
- Direction: conditional
- Passage kind: flooded corridor and doorway
- Baseline state: closed
- Visibility: visible
- Barriers: locked steel door
- Conditions: The locked steel door must be opened or bypassed; the destination beyond is not identified in this pack.
