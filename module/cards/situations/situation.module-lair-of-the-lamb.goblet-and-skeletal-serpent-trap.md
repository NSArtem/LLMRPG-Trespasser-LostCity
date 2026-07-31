---
id: "situation.module-lair-of-the-lamb.goblet-and-skeletal-serpent-trap"
type: "situation"
title: "Goblet and Skeletal Serpent Trap"
aliases: ["situation.goblet-serpent-trap"]
source_pages: [24]
verification: verified
references: ["actor.module-lair-of-the-lamb.robed-skeleton", "actor.module-lair-of-the-lamb.skeletal-serpent", "effect.skeletal-serpent-bite", "item.module-lair-of-the-lamb.black-iron-spellbook", "item.module-lair-of-the-lamb.delicate-crystal-goblet", "place.module-lair-of-the-lamb.14a-shadrakul"]
activation: {"condition": "Touch the goblet or approach the robed skeleton in 14A SHADRAKUL.", "type": "keyed"}
repeat: {"mode": "once"}
locations: ["cards/places/place.module-lair-of-the-lamb.14a-shadrakul.md"]
participants: [{"actor_id": "actor.module-lair-of-the-lamb.robed-skeleton", "role": "Holds the spellbook and precarious goblet."}, {"actor_id": "actor.module-lair-of-the-lamb.skeletal-serpent", "role": "Hidden guardian that attacks."}]
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.robed-skeleton.md", "cards/actors/actor.module-lair-of-the-lamb.skeletal-serpent.md"]
  procedures: []
  knowledge: []
# Possible effects are source possibilities. Nothing here is applied or copied into a checkpoint.
possible_effects: []
---

# Goblet and Skeletal Serpent Trap

## What the players perceive

The delicate goblet begins to topple at the slightest touch, and a skeletal serpent lunges from the robed skeleton when anyone approaches.

## Pressure and stakes

- The crystal goblet worth 800s can break.
- The serpent’s bite requires a save or causes death.

## Likely approaches

- Try to secure the goblet without touching or jostling it.
- Approach the skeleton to take the spellbook.

## Actor reactions

- **Robed Skeleton** (`actor.module-lair-of-the-lamb.robed-skeleton`) takes part: Holds the spellbook and precarious goblet.
- **Skeletal Serpent** (`actor.module-lair-of-the-lamb.skeletal-serpent`) takes part: Hidden guardian that attacks.

## Consequences

- The slightest touch makes the goblet fall and break.
- Approaching the skeleton triggers a skeletal serpent attack.

### Possible effects

<!-- Source possibilities only. The runtime never applies these automatically and never copies them into a checkpoint. -->


## Completion conditions


### Repeat behavior

- Mode: once
