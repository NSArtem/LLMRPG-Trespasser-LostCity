---
id: "place.module-lair-of-the-lamb.13-city-mural"
type: "place"
title: "13 CITY MURAL"
aliases: ["location.13-city-mural"]
source_pages: [24]
verification: verified
references: []
topology_node: "place.module-lair-of-the-lamb.area-13-city-mural"
load_with:
  actors: []
  situations: []
  procedures: []
  knowledge: []
---

# 13 CITY MURAL

## First impression

A mural depicts a city under the waves. A huge spiderweb-filled crack runs along the south wall with a faint breeze coming through it; a moldy, badly damaged locked door blocks the east passage.

## Contents

- Mural of a city under the waves.
- Huge spiderweb-filled crack along the south wall.
- Moldy, locked, badly damaged eastern door.

## Discoverable

- **Examine or try to manipulate the badly damaged door.** — The damaged eastern door can be quietly wrenched off its hinges.

## Hidden

- The Lamb previously damaged the eastern door by ramming it in a fit of madness.

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

### place.module-lair-of-the-lamb.area-14-sarcophagus

- Destination: `place.module-lair-of-the-lamb.area-14-sarcophagus`
- Direction: both
- Passage kind: corridor
- Baseline state: open
- Visibility: visible

### place.module-lair-of-the-lamb.area-16-mold

- Destination: `place.module-lair-of-the-lamb.area-16-mold`
- Direction: conditional
- Passage kind: doorway
- Baseline state: closed
- Visibility: visible
- Barriers: moldy locked wooden door
- Conditions: The damaged door can be opened by lock bypass or quietly wrenched off its hinges.

### place.module-lair-of-the-lamb.waypoint-15-crack

- Destination: `place.module-lair-of-the-lamb.waypoint-15-crack`
- Direction: conditional
- Passage kind: crack and crawlspace
- Baseline state: open
- Visibility: visible
- Barriers: spiderwebs
- Conditions: A person must squeeze through the narrow crack.
- Hazards: Tiny red spider bites; a second bite causes instant death.
