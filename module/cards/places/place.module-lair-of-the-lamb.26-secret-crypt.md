---
id: "place.module-lair-of-the-lamb.26-secret-crypt"
type: "place"
title: "26 SECRET CRYPT"
aliases: ["location.26-secret-crypt"]
source_pages: [32]
verification: verified
references: ["item.module-lair-of-the-lamb.crypt-staves", "item.module-lair-of-the-lamb.fine-purple-robe", "item.module-lair-of-the-lamb.whelk-comb"]
topology_node: "place.module-lair-of-the-lamb.area-26-secret-crypt"
load_with:
  actors: []
  situations: []
  procedures: []
  knowledge: []
---

# 26 SECRET CRYPT

## First impression

A waning-crescent-moon motif marks this crypt; a central sarcophagus, a wall winch, and a soldier's corpse in the western passage are visible.

## Contents

- A waning crescent moon motif.
- A central stone sarcophagus.
- A wall winch controlling the portcullis.
- A soldier's corpse in the western passage.

## Discoverable

- **Open the stone sarcophagus.** — The sarcophagus contains a mummy wearing a fine purple robe worth 50s, with a stave and a whelk comb worth 100s.

## Hidden


## Triggers


## Hazards


## Resources

- A fine purple robe worth 50s.
- A stave.
- A comb made from a whelk worth 100s.

## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.area-25a-crypt

- Destination: `place.module-lair-of-the-lamb.area-25a-crypt`
- Direction: conditional
- Passage kind: secret doorway
- Baseline state: concealed
- Visibility: hidden
- Barriers: door hidden behind the tiles on the south wall
- Conditions: Strip or remove the south-wall tiles to reveal the door.

### place.module-lair-of-the-lamb.area-25g-crypt

- Destination: `place.module-lair-of-the-lamb.area-25g-crypt`
- Direction: both
- Passage kind: corridor
- Baseline state: open
- Visibility: visible

### place.module-lair-of-the-lamb.waypoint-18a-ledge

- Destination: `place.module-lair-of-the-lamb.waypoint-18a-ledge`
- Direction: conditional
- Passage kind: passage through a portcullis
- Baseline state: closed
- Visibility: visible
- Barriers: sealed portcullis
- Conditions: The wall winch in 26 SECRET CRYPT controls the portcullis.
