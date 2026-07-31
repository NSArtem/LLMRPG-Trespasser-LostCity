---
id: "situation.module-lair-of-the-lamb.shawson-ambushes-the-secret-opening"
type: "situation"
title: "Shawson Ambushes the Secret Opening"
aliases: ["situation.shawson-secret-door-ambush"]
source_pages: [35]
verification: verified
references: ["actor.module-lair-of-the-lamb.shawson", "place.module-lair-of-the-lamb.37-chewed-bones", "procedure.module-lair-of-the-lamb.toggle-the-secret-door-in-37-chewed-bones"]
activation: {"condition": "Both hidden switches open the secret door from 37 CHEWED BONES to 39 STONE EGG.", "type": "triggered"}
repeat: {"condition": "Shawson can wait again after retreating while the passage remains relevant.", "mode": "repeatable"}
locations: ["cards/places/place.module-lair-of-the-lamb.37-chewed-bones.md"]
participants: [{"actor_id": "actor.module-lair-of-the-lamb.shawson", "role": "Waits beside the opening, surprises the first climber, and drags the victim into 39 STONE EGG."}]
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.shawson.md"]
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.toggle-the-secret-door-in-37-chewed-bones.md"]
  knowledge: []
# Possible effects are source possibilities. Nothing here is applied or copied into a checkpoint.
possible_effects: []
---

# Shawson Ambushes the Secret Opening

## What the players perceive

When the high secret panel opens, the first climber entering it is seized from the other side; torchlight can reveal a brief glimpse of yellow eyes before a growl.

## Pressure and stakes

- The first climber can be isolated in 39 STONE EGG with a feral ghoul.

## Likely approaches


## Actor reactions

- **Shawson** (`actor.module-lair-of-the-lamb.shawson`) takes part: Waits beside the opening, surprises the first climber, and drags the victim into 39 STONE EGG.
- **Shawson** (`actor.module-lair-of-the-lamb.shawson`) — Grabs and drags the first climber into 39 STONE EGG to eat them.
- **Shawson** (`actor.module-lair-of-the-lamb.shawson`) — Growls and retreats if torchlight from a chair reveals his eyes.

## Consequences

- Shawson surprises and drags the first climber into 39 STONE EGG.
- A torch-bearing observer on a central chair glimpses Shawson's yellow eyes and causes him to retreat.

### Possible effects

<!-- Source possibilities only. The runtime never applies these automatically and never copies them into a checkpoint. -->


## Completion conditions


### Repeat behavior

- Mode: repeatable
- Condition: Shawson can wait again after retreating while the passage remains relevant.
