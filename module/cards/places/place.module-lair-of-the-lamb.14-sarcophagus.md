---
id: "place.module-lair-of-the-lamb.14-sarcophagus"
type: "place"
title: "14 SARCOPHAGUS"
aliases: ["location.14-sarcophagus"]
source_pages: [24]
verification: verified
references: ["place.module-lair-of-the-lamb.14a-shadrakul", "procedure.module-lair-of-the-lamb.using-the-sarcophagus-trapdoor", "situation.module-lair-of-the-lamb.sarcophagus-trapdoor"]
topology_node: "place.module-lair-of-the-lamb.area-14-sarcophagus"
load_with:
  actors: []
  situations: ["cards/situations/situation.module-lair-of-the-lamb.sarcophagus-trapdoor.md"]
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.using-the-sarcophagus-trapdoor.md"]
  knowledge: []
---

# 14 SARCOPHAGUS

## First impression

An unused wall torch hangs beside an obvious northward crawl tunnel and an empty sarcophagus inscribed “Shadrakul, who will not meet her apprentice in this life.” The lid edges are bladed.

## Contents

- Unused torch on the wall.
- Obvious crawl tunnel north to 10 BONE PILE.
- Sarcophagus with bladed lid edges.
- Inscription: “Shadrakul, who will not meet her apprentice in this life.”

## Discoverable

- **Clear dust from the empty sarcophagus.** — A seam runs along the middle of the sarcophagus bottom.
- **Clear dust and inspect or tap the sarcophagus bottom.** — The bottom is metal and sounds hollow.

## Hidden

- Replacing the lid over an occupant opens the sarcophagus bottom and dumps the occupant into 14A SHADRAKUL.
- Removing the lid again closes the bottom.

## Triggers

- Lifting or replacing the lid produces mechanical sounds from below.
- Replacing the lid while someone is inside activates the trapdoor.

## Hazards

- The bladed lid edges are sharp enough to cut ropes and sever ropes when the trap operates.

## Resources


## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.area-10-bone-pile

- Destination: `place.module-lair-of-the-lamb.area-10-bone-pile`
- Direction: conditional
- Passage kind: small crawl-tunnel
- Baseline state: open
- Visibility: hidden
- Barriers: Bones if the Lamb blocks the tunnel after three encounters.
- Conditions: Searching 10 BONE PILE reveals the tunnel; if blocked with bones, clearing it by hand takes 10 minutes.

### place.module-lair-of-the-lamb.area-13-city-mural

- Destination: `place.module-lair-of-the-lamb.area-13-city-mural`
- Direction: both
- Passage kind: corridor
- Baseline state: open
- Visibility: visible

### place.module-lair-of-the-lamb.area-14a-shadrakul

- Destination: `place.module-lair-of-the-lamb.area-14a-shadrakul`
- Direction: outbound
- Passage kind: sarcophagus trapdoor
- Baseline state: concealed
- Visibility: hidden
- Barriers: sarcophagus lid and swinging metal bottom
- Conditions: Enter the sarcophagus and have the lid replaced.
- Hazards: 10-foot fall; Bladed lid edges sever ropes.
