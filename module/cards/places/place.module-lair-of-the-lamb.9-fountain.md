---
id: "place.module-lair-of-the-lamb.9-fountain"
type: "place"
title: "9 FOUNTAIN"
aliases: ["location.9-fountain"]
source_pages: [23]
verification: verified
references: ["actor.module-lair-of-the-lamb.the-lamb-c0865d75", "knowledge.module-lair-of-the-lamb.tumbler-password", "procedure.module-lair-of-the-lamb.ending-the-fountain-haunting", "situation.module-lair-of-the-lamb.the-haunting-of-9-fountain"]
topology_node: "place.module-lair-of-the-lamb.area-9-fountain"
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.the-lamb-c0865d75.md"]
  situations: ["cards/situations/situation.module-lair-of-the-lamb.the-haunting-of-9-fountain.md"]
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.ending-the-fountain-haunting.md"]
  knowledge: ["cards/knowledge/knowledge.module-lair-of-the-lamb.tumbler-password.md"]
---

# 9 FOUNTAIN

## First impression

A 30-foot-deep slimy pool surrounds a dripping fountain shaped like a fish with hands. Its water falls in the regular rhythm “drip . . . drip drip . . . drip . . . drip drip.”

## Contents

- Slimy pool, 30 feet deep.
- Dripping fountain shaped like a fish with hands.
- Water dripping in a 1-2-1-2 pattern.
- Occupant: The Lamb is present 100% of the time on the first visit and 2-in-6 on subsequent visits.

## Discoverable

- **Investigate the pool.** — An armored skeleton lies in the shallows.

## Hidden

- The location is haunted.
- The first person to touch the water is supernaturally shoved in and held beneath the surface.

## Triggers


## Hazards

- The first entrant hallucinates drowning for 1 round.
- The first person to touch the water is pulled in with no save and cannot bring any body part out of the water.

## Resources


## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.area-8-pit

- Destination: `place.module-lair-of-the-lamb.area-8-pit`
- Direction: both
- Passage kind: doorway
- Visibility: visible
- Barriers: wooden door shown on the map

### place.module-lair-of-the-lamb.waypoint-9a-underwater-tunnel

- Destination: `place.module-lair-of-the-lamb.waypoint-9a-underwater-tunnel`
- Direction: conditional
- Passage kind: underwater opening
- Baseline state: concealed
- Visibility: hidden
- Conditions: Enter the 30-foot-deep pool and locate the underwater tunnel.
- Hazards: Drowning risk during underwater traversal.
