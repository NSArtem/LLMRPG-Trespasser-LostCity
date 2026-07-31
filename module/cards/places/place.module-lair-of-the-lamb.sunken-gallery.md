---
id: "place.module-lair-of-the-lamb.sunken-gallery"
type: "place"
title: "Sunken Gallery"
aliases: ["location.42-sunken-gallery"]
source_pages: [38]
verification: verified
references: ["effect.sunken-gallery-poison", "item.module-lair-of-the-lamb.bottle-of-liquid-boat", "item.module-lair-of-the-lamb.hand-mirror-of-lies", "item.module-lair-of-the-lamb.pouch-of-50-golden-gorbels", "knowledge.module-lair-of-the-lamb.the-scribes-scroll", "procedure.module-lair-of-the-lamb.handle-a-sunken-gallery-coffer", "situation.module-lair-of-the-lamb.poison-coffer-discharge"]
topology_node: "place.module-lair-of-the-lamb.area-42-sunken-gallery"
load_with:
  actors: []
  situations: ["cards/situations/situation.module-lair-of-the-lamb.poison-coffer-discharge.md"]
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.handle-a-sunken-gallery-coffer.md"]
  knowledge: ["cards/knowledge/knowledge.module-lair-of-the-lamb.the-scribes-scroll.md"]
---

# Sunken Gallery

## First impression

A 40-foot-tall gallery lies under 10 feet of water. Six huge statues loom from the pool, each holding a stone coffer.

## Contents

- Six huge statues, each with an integral stone coffer that cannot be removed.
- A proud king holds his coffer overhead and gazes at the shepherd.
- A weary knight watches the crone.
- A smiling shepherd with a sheep under one arm watches the scribe.
- A beggar extends a plate toward the crone.
- A crone bows to the king and holds her coffer behind her back.
- A scribe watches the crone while clutching a scroll to his chest.

## Discoverable

- **Read the scroll clutched by the scribe statue.** — The scribe's scroll reads: 'The sheep do not know the shepherd, but they follow nonetheless'.

## Hidden

- The king, knight, shepherd, beggar, and scribe coffers contain poisonous gas.
- The crone's coffer contains the hand mirror of lies, a bottle of liquid boat, and a pouch of 50 golden gorbels worth 500s.
- The room connects to 24 CRUSH HALLWAY and 25 TRICKY HALLWAY, but neither can be accessed unless its trap door is open.

## Triggers

- Opening a poison-filled coffer exposes anyone in front of it to a Dex save against poisoning and then releases gas that fills the room.
- Open trap doors permit access to 24 CRUSH HALLWAY and 25 TRICKY HALLWAY.

## Hazards

- Five coffers contain poison gas that expands to fill the room and takes 10 minutes to settle.

## Resources

- The hand mirror of lies.
- A bottle of liquid boat.
- A pouch containing 50 golden gorbels, worth 500s.

## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.area-24b

- Destination: `place.module-lair-of-the-lamb.area-24b`
- Direction: not stated
- Passage kind: portcullis opening
- Baseline state: blocked
- Visibility: visible
- Barriers: rusted-shut portcullis

### place.module-lair-of-the-lamb.area-41-sunken-shrine

- Destination: `place.module-lair-of-the-lamb.area-41-sunken-shrine`
- Direction: both
- Passage kind: flooded corridor and doorway
- Visibility: visible
- Barriers: metal door shown on the map

### place.module-lair-of-the-lamb.area-43-spider-crab

- Destination: `place.module-lair-of-the-lamb.area-43-spider-crab`
- Direction: both
- Passage kind: flooded corridor and doorway
- Visibility: visible
- Barriers: metal door shown on the map

### place.module-lair-of-the-lamb.waypoint-35a-trapdoor-pit

- Destination: `place.module-lair-of-the-lamb.waypoint-35a-trapdoor-pit`
- Direction: both
- Passage kind: pit-bottom opening
- Baseline state: open
- Visibility: visible
