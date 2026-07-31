---
id: "place.module-lair-of-the-lamb.stone-egg"
type: "place"
title: "Stone Egg"
aliases: ["location.39-stone-egg"]
source_pages: [36]
verification: verified
references: ["actor.module-lair-of-the-lamb.shawson-the-ghoul", "effect.stone-egg-suffocation-transformation", "item.module-lair-of-the-lamb.600-silver-shilavos", "item.module-lair-of-the-lamb.abacus-of-vandoh", "item.module-lair-of-the-lamb.perpetually-screaming-head", "procedure.module-lair-of-the-lamb.open-the-stone-egg", "situation.module-lair-of-the-lamb.the-stone-egg-opens"]
topology_node: "place.module-lair-of-the-lamb.area-39-stone-egg"
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.shawson-the-ghoul.md"]
  situations: ["cards/situations/situation.module-lair-of-the-lamb.the-stone-egg-opens.md"]
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.open-the-stone-egg.md"]
  knowledge: []
---

# Stone Egg

## First impression

A ravenous ghoul shares the room with a polished pinkish-brown stone egg about 3 feet tall, covered in grooves, whorls, and carved animals.

## Contents

- A polished pinkish-brown stone egg about 3 feet tall, covered with grooves, whorls, and carved animals.
- The carvings depict an ape, elephant, bat, chicken, snake, octopus, rat, pyorn (giant bird), horse, and toad.
- Occupant: Shawson the ghoul.

## Discoverable

- **Put an ear against the egg.** — Faint screaming can be heard from inside the Stone Egg.
- **Touch an animal carving.** — Each animal carving lights up when touched.
- **Experiment with the carvings or identify and touch all egg-laying animals at once.** — The egg unfolds like a flower when the chicken, snake, octopus, pyorn, and toad are touched simultaneously.
- **Accumulate incorrect inputs while testing the carvings.** — Every five incorrect animal touches makes the glow of a touched animal dimmer; after four failed attempts the egg becomes inert for 24 hours.

## Hidden

- The egg is Shawson the ghoul's prison.
- Inside are 600 silver shilavos, the Abacus of Vandoh, a head that never stops screaming, and a headless skeleton.
- Climbing inside causes the egg to zip shut and trap the entrant until suffocation; the corpse becomes a perpetually screaming head attached to a skeleton.

## Triggers

- Touching all five egg-laying animal carvings simultaneously opens the egg.
- Each five incorrect animal touches advances the failure track; after four failed attempts the egg is inert for 24 hours.
- Opening the egg fills the air with screaming and provokes an Encounter check.
- Climbing inside the opened egg causes it to zip shut.

## Hazards

- The egg can trap and suffocate anyone who climbs inside.

## Resources

- 600 silver shilavos.
- The Abacus of Vandoh.

## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.area-37-chewed-bones

- Destination: `place.module-lair-of-the-lamb.area-37-chewed-bones`
- Direction: conditional
- Passage kind: 2-foot by 2-foot secret panel
- Baseline state: concealed
- Visibility: hidden
- Barriers: secret panel in the north wall, 8 feet above the ground
- Conditions: Press both switches in the two 4-foot-deep wall holes simultaneously; climb 8 feet to the opening.
- Hazards: Shawson waits beside the opening and may drag the first climber into 39 STONE EGG.
