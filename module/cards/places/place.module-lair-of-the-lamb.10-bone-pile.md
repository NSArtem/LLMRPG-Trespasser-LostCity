---
id: "place.module-lair-of-the-lamb.10-bone-pile"
type: "place"
title: "10 BONE PILE"
aliases: ["location.10-bone-pile"]
source_pages: [23]
verification: verified
references: ["procedure.module-lair-of-the-lamb.clearing-the-blocked-bone-pile-tunnel", "procedure.module-lair-of-the-lamb.searching-10-bone-pile", "situation.module-lair-of-the-lamb.the-lamb-blocks-the-bone-pile-tunnel", "table.bone-pile-search"]
topology_node: "place.module-lair-of-the-lamb.area-10-bone-pile"
load_with:
  actors: []
  situations: ["cards/situations/situation.module-lair-of-the-lamb.the-lamb-blocks-the-bone-pile-tunnel.md"]
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.clearing-the-blocked-bone-pile-tunnel.md", "cards/procedures/procedure.module-lair-of-the-lamb.searching-10-bone-pile.md"]
  knowledge: []
---

# 10 BONE PILE

## First impression

A pile contains 255 bone pellets, each holding about 100 pounds of compressed bone fragments only slightly smoothed by digestion.

## Contents

- 255 bone pellets, each about 100 pounds.

## Discoverable

- **Spend any amount of time searching the pile.** — A small crawl tunnel leads to 14 SARCOPHAGUS.

## Hidden

- After 3 encounters with the Lamb, it becomes cunning and begins blocking the crawl tunnel with bones.

## Triggers

- After 3 encounters with the Lamb, the Lamb begins blocking the crawl tunnel.

## Hazards


## Resources

- One d20 search result per man-hour, using the Bone Pile Search table.

## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.area-14-sarcophagus

- Destination: `place.module-lair-of-the-lamb.area-14-sarcophagus`
- Direction: conditional
- Passage kind: small crawl-tunnel
- Baseline state: open
- Visibility: hidden
- Barriers: Bones if the Lamb blocks the tunnel after three encounters.
- Conditions: Searching 10 BONE PILE reveals the tunnel; if blocked with bones, clearing it by hand takes 10 minutes.

### place.module-lair-of-the-lamb.area-8-pit

- Destination: `place.module-lair-of-the-lamb.area-8-pit`
- Direction: both
- Passage kind: doorway
- Visibility: visible
- Barriers: wooden door shown on the map
