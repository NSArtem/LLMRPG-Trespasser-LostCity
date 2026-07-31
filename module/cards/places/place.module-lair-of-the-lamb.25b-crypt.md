---
id: "place.module-lair-of-the-lamb.25b-crypt"
type: "place"
title: "25B CRYPT"
aliases: ["location.25b-crypt"]
source_pages: [32]
verification: verified
references: ["item.module-lair-of-the-lamb.hook-hand-prosthesis", "item.module-lair-of-the-lamb.parts-of-seven-mummies"]
topology_node: "place.module-lair-of-the-lamb.area-25b-crypt"
load_with:
  actors: []
  situations: []
  procedures: []
  knowledge: []
---

# 25B CRYPT

## First impression

A waning-gibbous-moon motif marks this crypt; a stone sarcophagus rests in the center and the portcullis to the south is lowered.

## Contents

- A waning gibbous moon motif.
- A central stone sarcophagus.
- A lowered portcullis to the south.
- A winch 10' south of the portcullis.

## Discoverable

- **Open the stone sarcophagus.** — The sarcophagus contains 7 mummified right arms, one with a hook-hand prosthesis.

## Hidden


## Triggers


## Hazards


## Resources


## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.area-25a-crypt

- Destination: `place.module-lair-of-the-lamb.area-25a-crypt`
- Direction: both
- Passage kind: corridor
- Baseline state: open
- Visibility: visible

### place.module-lair-of-the-lamb.area-25c-crypt

- Destination: `place.module-lair-of-the-lamb.area-25c-crypt`
- Direction: both
- Passage kind: corridor
- Baseline state: open
- Visibility: visible

### place.module-lair-of-the-lamb.area-25g-crypt

- Destination: `place.module-lair-of-the-lamb.area-25g-crypt`
- Direction: conditional
- Passage kind: descending passage through a portcullis
- Baseline state: lowered
- Visibility: visible
- Barriers: portcullis currently lowered
- Conditions: Operate the winch 10 feet south of the portcullis.
