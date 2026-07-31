---
id: "place.module-lair-of-the-lamb.33-fungus"
type: "place"
title: "33 FUNGUS"
aliases: ["location.33-fungus"]
source_pages: [34]
verification: verified
references: ["actor.module-lair-of-the-lamb.captain-conroy", "effect.polypore-nonviolence", "item.module-lair-of-the-lamb.harpoon", "item.module-lair-of-the-lamb.six-silver-shilavos", "knowledge.module-lair-of-the-lamb.captain-conroys-fate-and-last-order"]
topology_node: "place.module-lair-of-the-lamb.area-33-fungus"
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.captain-conroy.md"]
  situations: []
  procedures: []
  knowledge: ["cards/knowledge/knowledge.module-lair-of-the-lamb.captain-conroys-fate-and-last-order.md"]
---

# 33 FUNGUS

## First impression

Huge blue polypores cover the south wall; a complex chromatic fungal mass covers the north wall around a chair, visible legs, and a barely discernible skull; a harpoon and six silver shilavos stand along the east side.

## Contents

- Fat stacks of huge blue polypores on the south wall.
- A chair and pair of legs beneath a north-wall mass of chromatic fungus, with the shape of a skull near the ceiling.
- A harpoon leaning against the east wall.
- Six silver shilavos arranged at the harpoon's foot to represent the ghouls.

## Discoverable

- **Excavate the north-wall fungus.** — The fungal mass conceals the door to 34 CACHE.
- **Interpret or investigate the body-like fungal formation.** — The mass is Captain Conroy's remains.

## Hidden

- The blue polypores emit an aura that prevents violence while intact.
- The fungal remains are Captain Conroy, transformed after praying to Shendormu.
- Captain Conroy's last order was that his soldiers destroy themselves.

## Triggers


## Hazards

- While the blue polypores remain intact, no violence is possible in the room; a damaged character gets a Cha Save to resist.

## Resources

- A harpoon.
- Six silver shilavos.

## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.area-32-isopods

- Destination: `place.module-lair-of-the-lamb.area-32-isopods`
- Direction: conditional
- Passage kind: secret doorway
- Baseline state: concealed
- Visibility: hidden
- Barriers: secret door in the east wall
- Conditions: Press the switch at the back of the 5-foot-deep round hole in the north wall.

### place.module-lair-of-the-lamb.area-34-cache

- Destination: `place.module-lair-of-the-lamb.area-34-cache`
- Direction: conditional
- Passage kind: concealed doorway
- Baseline state: concealed
- Visibility: hidden
- Barriers: complex mass of fungus covering the north wall and door
- Conditions: Excavate the fungus to reveal the door to 34 CACHE.
