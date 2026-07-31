---
id: "place.module-lair-of-the-lamb.25a-crypt"
type: "place"
title: "25A CRYPT"
aliases: ["location.25a-crypt"]
source_pages: [32]
verification: verified
references: ["item.module-lair-of-the-lamb.parts-of-seven-mummies"]
topology_node: "place.module-lair-of-the-lamb.area-25a-crypt"
load_with:
  actors: []
  situations: []
  procedures: []
  knowledge: []
---

# 25A CRYPT

## First impression

A third-quarter-moon motif marks this crypt, where a stone sarcophagus rests in the center.

## Contents

- A third quarter moon motif.
- A central stone sarcophagus.

## Discoverable

- **Open the stone sarcophagus.** — The sarcophagus contains 7 mummified left arms.
- **Remove or investigate the tiles on the south wall.** — The door to 26 SECRET CRYPT is behind the south-wall tiles.

## Hidden

- A door to 26 SECRET CRYPT is concealed behind the south-wall tiles.

## Triggers


## Hazards


## Resources


## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.area-22-mushroom

- Destination: `place.module-lair-of-the-lamb.area-22-mushroom`
- Direction: both
- Passage kind: south doorway
- Visibility: visible
- Barriers: defaced wooden door shown on the map

### place.module-lair-of-the-lamb.area-25b-crypt

- Destination: `place.module-lair-of-the-lamb.area-25b-crypt`
- Direction: both
- Passage kind: corridor
- Baseline state: open
- Visibility: visible

### place.module-lair-of-the-lamb.area-26-secret-crypt

- Destination: `place.module-lair-of-the-lamb.area-26-secret-crypt`
- Direction: conditional
- Passage kind: secret doorway
- Baseline state: concealed
- Visibility: hidden
- Barriers: door hidden behind the tiles on the south wall
- Conditions: Strip or remove the south-wall tiles to reveal the door.
