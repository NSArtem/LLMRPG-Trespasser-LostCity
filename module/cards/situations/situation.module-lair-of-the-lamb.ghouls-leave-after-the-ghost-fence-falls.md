---
id: "situation.module-lair-of-the-lamb.ghouls-leave-after-the-ghost-fence-falls"
type: "situation"
title: "Ghouls Leave After the Ghost Fence Falls"
aliases: ["situation.ghoul-departure-after-ghost-fence"]
source_pages: [29]
verification: verified
references: ["actor.module-lair-of-the-lamb.captain-conroy", "actor.module-lair-of-the-lamb.gerdith", "actor.module-lair-of-the-lamb.jasper", "actor.module-lair-of-the-lamb.luntz", "actor.module-lair-of-the-lamb.molina"]
activation: {"condition": "40 GHOST FENCE is destroyed.", "type": "triggered"}
repeat: {"mode": "once"}
locations: []
participants: [{"actor_id": "actor.module-lair-of-the-lamb.jasper", "role": "One of the surviving ghouls who may depart."}, {"actor_id": "actor.module-lair-of-the-lamb.luntz", "role": "One of the surviving ghouls who may depart."}, {"actor_id": "actor.module-lair-of-the-lamb.gerdith", "role": "One of the surviving ghouls who may depart."}, {"actor_id": "actor.module-lair-of-the-lamb.molina", "role": "One of the surviving ghouls who may depart."}]
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.captain-conroy.md", "cards/actors/actor.module-lair-of-the-lamb.gerdith.md", "cards/actors/actor.module-lair-of-the-lamb.jasper.md", "cards/actors/actor.module-lair-of-the-lamb.luntz.md", "cards/actors/actor.module-lair-of-the-lamb.molina.md"]
  procedures: []
  knowledge: []
# Possible effects are source possibilities. Nothing here is applied or copied into a checkpoint.
possible_effects: [{"description": "The party may meet the departed ghouls again as NPCs.", "effect": "future-thread"}]
---

# Ghouls Leave After the Ghost Fence Falls

## What the players perceive

After the ghost fence is destroyed, the surviving ghouls prepare to collect belongings, revisit their home, and say farewell to Captain Conroy before leaving.

## Pressure and stakes


## Likely approaches


## Actor reactions

- **Jasper** (`actor.module-lair-of-the-lamb.jasper`) takes part: One of the surviving ghouls who may depart.
- **Luntz** (`actor.module-lair-of-the-lamb.luntz`) takes part: One of the surviving ghouls who may depart.
- **Gerdith** (`actor.module-lair-of-the-lamb.gerdith`) takes part: One of the surviving ghouls who may depart.
- **Molina** (`actor.module-lair-of-the-lamb.molina`) takes part: One of the surviving ghouls who may depart.

## Consequences

- The ghouls leave the dungeon within 12 hours.
- If the party promises to return and help kill the Lamb, they may remain for as long as 24 hours.
- The party may encounter them later as NPCs.

### Possible effects

<!-- Source possibilities only. The runtime never applies these automatically and never copies them into a checkpoint. -->

- `future-thread` — The party may meet the departed ghouls again as NPCs.

## Completion conditions

- The surviving ghouls depart after their final preparations, no later than the applicable 12- or 24-hour window.

### Repeat behavior

- Mode: once
