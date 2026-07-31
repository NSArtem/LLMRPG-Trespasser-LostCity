---
id: "place.module-lair-of-the-lamb.4-chests"
type: "place"
title: "4 CHESTS"
aliases: ["location.4-chests"]
source_pages: [21]
verification: verified
references: ["situation.module-lair-of-the-lamb.the-skull-of-davok-escapes"]
topology_node: "place.module-lair-of-the-lamb.area-4-chests"
load_with:
  actors: []
  situations: ["cards/situations/situation.module-lair-of-the-lamb.the-skull-of-davok-escapes.md"]
  procedures: []
  knowledge: []
---

# 4 CHESTS

## First impression

A locked wooden door protects a room containing a wooden table, a wooden chest, and a lead-and-iron chest chained to the floor.

## Contents

- Locked wooden entrance door.
- Wooden table holding 1 immature Lambfruit.
- Wooden chest.
- Lead-and-iron chest bolted to the floor and bound with two linchpinned chains.

## Discoverable

- **Open the wooden chest.** — The wooden chest contains a masterwork helmet, 1 torch, 2 doses of purple lotus powder, and a lotus pipe.
- **Remove both linchpins and open the lead-and-iron chest.** — The lead-and-iron chest contains only the Skull of Davok.

## Hidden


## Triggers

- Opening the lead-and-iron chest allows the Skull of Davok to escape.

## Hazards

- Removing the first linchpin causes headaches.
- Removing the second linchpin causes nosebleeds.

## Resources


## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.waypoint-1c-third-intersection

- Destination: `place.module-lair-of-the-lamb.waypoint-1c-third-intersection`
- Direction: conditional
- Passage kind: doorway
- Baseline state: closed
- Visibility: visible
- Barriers: locked wooden door
- Conditions: The locked wooden door must be opened or bypassed.
