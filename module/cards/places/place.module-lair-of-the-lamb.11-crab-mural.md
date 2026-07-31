---
id: "place.module-lair-of-the-lamb.11-crab-mural"
type: "place"
title: "11 CRAB MURAL"
aliases: ["location.11-crab-mural"]
source_pages: [24]
verification: verified
references: ["actor.module-lair-of-the-lamb.friendly-rat"]
topology_node: "place.module-lair-of-the-lamb.area-11-crab-mural"
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.friendly-rat.md"]
  situations: []
  procedures: []
  knowledge: []
---

# 11 CRAB MURAL

## First impression

A mural shows a crab being groomed in a woman’s lap. A friendly rat is present, and a wooden door to the east is locked.

## Contents

- Crab-grooming mural.
- Locked wooden door to the east.
- Occupant: A friendly rat.

## Discoverable


## Hidden


## Triggers


## Hazards


## Resources


## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.area-12-abacus-mural

- Destination: `place.module-lair-of-the-lamb.area-12-abacus-mural`
- Direction: conditional
- Passage kind: corridor
- Baseline state: open
- Visibility: visible
- Conditions: Traversal remains possible only while 12 ABACUS MURAL has not been rendered impassable by collapse.
- Hazards: Ceiling collapse if the support pike is removed.

### place.module-lair-of-the-lamb.area-19-priests

- Destination: `place.module-lair-of-the-lamb.area-19-priests`
- Direction: conditional
- Passage kind: doorway
- Baseline state: closed
- Visibility: visible
- Barriers: locked wooden door
- Conditions: The locked wooden door must be opened or bypassed.

### place.module-lair-of-the-lamb.area-8-pit

- Destination: `place.module-lair-of-the-lamb.area-8-pit`
- Direction: both
- Passage kind: corridor
- Baseline state: open
- Visibility: visible
