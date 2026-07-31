---
id: "place.module-lair-of-the-lamb.25g-crypt"
type: "place"
title: "25G CRYPT"
aliases: ["location.25g-crypt"]
source_pages: [32]
verification: verified
references: ["item.module-lair-of-the-lamb.crypt-staves", "item.module-lair-of-the-lamb.purple-moon-patterned-robes", "situation.module-lair-of-the-lamb.gerdith-and-molina-investigate-an-alert"]
topology_node: "place.module-lair-of-the-lamb.area-25g-crypt"
load_with:
  actors: []
  situations: ["cards/situations/situation.module-lair-of-the-lamb.gerdith-and-molina-investigate-an-alert.md"]
  procedures: []
  knowledge: []
---

# 25G CRYPT

## First impression

A new-moon motif marks this crypt, where a stone sarcophagus rests in the center.

## Contents

- A new moon motif.
- A central stone sarcophagus.

## Discoverable

- **Open the stone sarcophagus.** — The sarcophagus contains 5 broken staves, 2 intact staves, and 6 purple robes worth 50s each, embroidered with moonstones and orbital patterns.

## Hidden


## Triggers

- Bringing a light source into the room causes the ghouls in 27 BALLISTA to notice it.

## Hazards


## Resources

- 2 intact staves.
- 6 purple robes worth 50s each.

## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.area-25b-crypt

- Destination: `place.module-lair-of-the-lamb.area-25b-crypt`
- Direction: conditional
- Passage kind: descending passage through a portcullis
- Baseline state: lowered
- Visibility: visible
- Barriers: portcullis currently lowered
- Conditions: Operate the winch 10 feet south of the portcullis.

### place.module-lair-of-the-lamb.area-25f-crypt

- Destination: `place.module-lair-of-the-lamb.area-25f-crypt`
- Direction: both
- Passage kind: corridor
- Baseline state: open
- Visibility: visible

### place.module-lair-of-the-lamb.area-26-secret-crypt

- Destination: `place.module-lair-of-the-lamb.area-26-secret-crypt`
- Direction: both
- Passage kind: corridor
- Baseline state: open
- Visibility: visible
