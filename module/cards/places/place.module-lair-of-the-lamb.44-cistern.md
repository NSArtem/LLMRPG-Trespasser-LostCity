---
id: "place.module-lair-of-the-lamb.44-cistern"
type: "place"
title: "44 CISTERN"
aliases: ["location.44-cistern"]
source_pages: [40, 41]
verification: verified
references: ["actor.module-lair-of-the-lamb.the-lamb", "effect.44-cistern-ammonia-warning", "effect.cistern-carried-item-swim-penalty", "effect.first-lamb-fishing-success", "effect.lamb-movement-rates", "effect.noria-crushes-lamb", "effect.noria-no-human-escape", "effect.table-boat-speed-modifiers", "knowledge.module-lair-of-the-lamb.the-noria-feeds-the-white-temple", "knowledge.module-lair-of-the-lamb.white-temple-response-to-the-lambs-death-in-the-noria", "place.module-lair-of-the-lamb.44a-wall", "place.module-lair-of-the-lamb.46-daylight", "procedure.module-lair-of-the-lamb.calculate-human-swim-speed-in-44-cistern", "procedure.module-lair-of-the-lamb.calculate-makeshift-table-boat-speed", "procedure.module-lair-of-the-lamb.crush-the-lamb-with-the-noria", "procedure.module-lair-of-the-lamb.fish-for-the-lamb", "procedure.module-lair-of-the-lamb.run-a-fight-with-the-lamb-in-the-cistern", "situation.module-lair-of-the-lamb.fighting-the-lamb", "situation.module-lair-of-the-lamb.the-lamb-approaches-in-44-cistern"]
topology_node: "place.module-lair-of-the-lamb.area-44-cistern"
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.the-lamb.md"]
  situations: ["cards/situations/situation.module-lair-of-the-lamb.fighting-the-lamb.md", "cards/situations/situation.module-lair-of-the-lamb.the-lamb-approaches-in-44-cistern.md"]
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.calculate-human-swim-speed-in-44-cistern.md", "cards/procedures/procedure.module-lair-of-the-lamb.calculate-makeshift-table-boat-speed.md", "cards/procedures/procedure.module-lair-of-the-lamb.crush-the-lamb-with-the-noria.md", "cards/procedures/procedure.module-lair-of-the-lamb.fish-for-the-lamb.md", "cards/procedures/procedure.module-lair-of-the-lamb.run-a-fight-with-the-lamb-in-the-cistern.md"]
  knowledge: ["cards/knowledge/knowledge.module-lair-of-the-lamb.the-noria-feeds-the-white-temple.md", "cards/knowledge/knowledge.module-lair-of-the-lamb.white-temple-response-to-the-lambs-death-in-the-noria.md"]
---

# 44 CISTERN

## First impression

Ten-foot-deep water fills a vast chamber crowded by sixteen huge, water-stained pillars. A towering wooden waterwheel near the south wall splashes and creaks loudly.

## Contents

- Water 10 feet deep.
- Sixteen huge water-stained pillars, each about 5 feet in diameter.
- A 60-foot-tall noria of stout lumber near the south wall, extending into the ceiling and constantly spilling water.

## Discoverable

- **Enter the central 50-foot-by-50-foot part of the room.** — A glow of sunlight is visible from the north.
- **Gain line of sight to 46 DAYLIGHT.** — A thick pillar of dusty light fills 46 DAYLIGHT.
- **Closely observe the noria and where it enters the ceiling.** — The noria carries water up to the White Temple and dumps it into a trough; there is no human-sized space to escape through the mechanism.

## Hidden

- As soon as someone enters the central 50-foot-by-50-foot area, the Lamb begins swimming toward them.

## Triggers

- Entering the central 50-foot-by-50-foot area starts the Lamb's approach sequence.

## Hazards

- Deep water slows swimmers who carry items.
- The Lamb can pursue swimmers at 10 feet per round.
- The moving noria can crush the Lamb against the slotted ceiling if it is ensnared.

## Resources

- A table can serve as a makeshift boat.
- Planks or similar objects can serve as paddles.
- The noria can be used as an environmental weapon against the Lamb.
- Harpoons, hooked nets, ropes, and burning oil are suggested tools for fighting the Lamb here.

## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.area-45-barrels

- Destination: `place.module-lair-of-the-lamb.area-45-barrels`
- Direction: conditional
- Passage kind: flooded corridor
- Baseline state: open
- Visibility: visible
- Conditions: Swim or use a makeshift boat.

### place.module-lair-of-the-lamb.area-46-daylight

- Destination: `place.module-lair-of-the-lamb.area-46-daylight`
- Direction: conditional
- Passage kind: flooded corridor
- Baseline state: open
- Visibility: visible
- Conditions: Swim or use a makeshift boat.

### place.module-lair-of-the-lamb.boundary-44a-wall

- Destination: `place.module-lair-of-the-lamb.boundary-44a-wall`
- Direction: conditional
- Passage kind: breached brick wall
- Baseline state: closed
- Visibility: hidden
- Barriers: modern brick wall
- Conditions: With suitable tools, make a man-sized opening in 6 minutes or a table-sized opening in 10 minutes.
- Hazards: Noise attracts available ghouls, the apparatus, the spider crab, and the Lamb in 5+1d4 minutes if able to reach the location.

### place.module-lair-of-the-lamb.waypoint-9a-underwater-tunnel

- Destination: `place.module-lair-of-the-lamb.waypoint-9a-underwater-tunnel`
- Direction: conditional
- Passage kind: underwater tunnel
- Baseline state: open
- Visibility: visible
- Conditions: Traversal requires swimming underwater.
- Hazards: Drowning risk during a five-minute swim.
