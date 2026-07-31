---
id: "place.module-lair-of-the-lamb.32-isopods"
type: "place"
title: "32 ISOPODS"
aliases: ["location.32-isopods"]
source_pages: [34]
verification: verified
references: ["actor.module-lair-of-the-lamb.three-armored-isopods", "item.module-lair-of-the-lamb.armored-isopod-shell", "procedure.module-lair-of-the-lamb.open-the-secret-door-in-32-isopods", "situation.module-lair-of-the-lamb.three-armored-isopods-foraging"]
topology_node: "place.module-lair-of-the-lamb.area-32-isopods"
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.three-armored-isopods.md"]
  situations: ["cards/situations/situation.module-lair-of-the-lamb.three-armored-isopods-foraging.md"]
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.open-the-secret-door-in-32-isopods.md"]
  knowledge: []
---

# 32 ISOPODS

## First impression

Three armored isopods forage in a room whose floor is worn unevenly near the east wall; a small round hole pierces the north wall.

## Contents

- Three foraging armored isopods.
- Uneven floor wear near the east wall, as if marking a doorway.
- A small round hole in the north wall, 5' deep.
- Occupant: Three armored isopods.

## Discoverable

- **Reach to the back of the north-wall hole and operate the switch.** — A switch at the back of the 5'-deep north-wall hole opens the secret door.

## Hidden

- The floor wear marks a secret doorway.

## Triggers


## Hazards


## Resources


## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.area-33-fungus

- Destination: `place.module-lair-of-the-lamb.area-33-fungus`
- Direction: conditional
- Passage kind: secret doorway
- Baseline state: concealed
- Visibility: hidden
- Barriers: secret door in the east wall
- Conditions: Press the switch at the back of the 5-foot-deep round hole in the north wall.

### place.module-lair-of-the-lamb.waypoint-31-traverse

- Destination: `place.module-lair-of-the-lamb.waypoint-31-traverse`
- Direction: conditional
- Passage kind: rope traverse across a broad pit
- Baseline state: open
- Visibility: visible
- Barriers: partially collapsed floor forming a broad pit
- Conditions: Use the fixed rope or another method to cross the pit.
- Hazards: 40-foot fall to water; Spider crab can reach 38 feet out of the water.

### place.module-lair-of-the-lamb.waypoint-35-tricky-hallway

- Destination: `place.module-lair-of-the-lamb.waypoint-35-tricky-hallway`
- Direction: both
- Passage kind: hallway
- Baseline state: open
- Visibility: visible
