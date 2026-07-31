---
id: "place.module-lair-of-the-lamb.37-chewed-bones"
type: "place"
title: "37 CHEWED BONES"
aliases: ["location.37-chewed-bones"]
source_pages: [35]
verification: verified
references: ["actor.module-lair-of-the-lamb.shawson", "effect.ghost-fence-teeth-chattering", "item.module-lair-of-the-lamb.spear-with-a-shrunken-head", "item.module-lair-of-the-lamb.tattered-red-banner", "procedure.module-lair-of-the-lamb.toggle-the-secret-door-in-37-chewed-bones", "situation.module-lair-of-the-lamb.ghost-fence-effect-reaches-37-chewed-bones", "situation.module-lair-of-the-lamb.shawson-ambushes-the-secret-opening"]
topology_node: "place.module-lair-of-the-lamb.area-37-chewed-bones"
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.shawson.md"]
  situations: ["cards/situations/situation.module-lair-of-the-lamb.ghost-fence-effect-reaches-37-chewed-bones.md", "cards/situations/situation.module-lair-of-the-lamb.shawson-ambushes-the-secret-opening.md"]
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.toggle-the-secret-door-in-37-chewed-bones.md"]
  knowledge: []
---

# 37 CHEWED BONES

## First impression

A mountain of gnawed bones fills the room, with a sack of more bones, a tattered red banner on the north wall, and two broken chair legs fixed through it into the wall.

## Contents

- Gnawed bones amounting to about 2 dozen human skeletons if reassembled.
- Several spider-crab shell and claw fragments, none as large as the specimen in 43 SPIDER CRAB.
- A burlap sack of more gnawed bones.
- A tattered red banner on the north wall, supported by two broken chair legs inserted into wall holes.

## Discoverable

- **Search the bone rubbish.** — A spear with a shrunken head tied to it by the hair lies in the rubbish.
- **Remove both chair legs and inspect the holes.** — Each chair-leg hole is 4' deep and contains a switch; both must be pressed together to toggle the secret door.
- **Stand on a chair in the middle of the room while holding a torch.** — Shawson's yellow eyes are visible before he growls and retreats.

## Hidden

- The closest person feels their teeth chattering from the heads in 40 GHOST FENCE as soon as the room is entered.
- The remote effect extends into 38 SHROUD as far as the heads can see.
- The secret door is a 2' by 2' north-wall panel 8' above the ground.
- Shawson hears the door open and waits beside the opening to ambush the first climber.

## Triggers

- Entering the room causes the closest person to feel the ghost-fence heads' effect.
- Pressing both hidden switches simultaneously opens the secret door; pressing both again closes it.
- Opening the secret door prepares Shawson's ambush.

## Hazards

- Shawson waits to surprise, grab, and drag the first climber into 39 STONE EGG.

## Resources

- A spear with a shrunken head.
- A tattered red banner.

## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.area-36-table

- Destination: `place.module-lair-of-the-lamb.area-36-table`
- Direction: both
- Passage kind: corridor
- Baseline state: open
- Visibility: visible

### place.module-lair-of-the-lamb.area-38-shroud

- Destination: `place.module-lair-of-the-lamb.area-38-shroud`
- Direction: both
- Passage kind: doorway
- Baseline state: partially blocked
- Visibility: visible
- Barriers: stack of 12 planks partially obscuring the doorway

### place.module-lair-of-the-lamb.area-39-stone-egg

- Destination: `place.module-lair-of-the-lamb.area-39-stone-egg`
- Direction: conditional
- Passage kind: 2-foot by 2-foot secret panel
- Baseline state: concealed
- Visibility: hidden
- Barriers: secret panel in the north wall, 8 feet above the ground
- Conditions: Press both switches in the two 4-foot-deep wall holes simultaneously; climb 8 feet to the opening.
- Hazards: Shawson waits beside the opening and may drag the first climber into 39 STONE EGG.

### place.module-lair-of-the-lamb.boundary-40-ghost-fence

- Destination: `place.module-lair-of-the-lamb.boundary-40-ghost-fence`
- Direction: both
- Passage kind: room opening
- Baseline state: open
- Visibility: visible
