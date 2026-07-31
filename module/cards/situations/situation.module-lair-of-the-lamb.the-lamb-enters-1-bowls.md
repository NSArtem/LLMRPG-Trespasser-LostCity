---
id: "situation.module-lair-of-the-lamb.the-lamb-enters-1-bowls"
type: "situation"
title: "The Lamb Enters 1 BOWLS"
aliases: ["situation.starting-lamb-entry"]
source_pages: [19]
verification: verified
references: ["actor.module-lair-of-the-lamb.the-lamb", "place.module-lair-of-the-lamb.1-bowls", "procedure.module-lair-of-the-lamb.starting-the-game", "rule.dark-door-wisdom-check"]
activation: {"condition": "The game begins in 1 BOWLS.", "type": "keyed"}
repeat: {"mode": "once"}
locations: ["cards/places/place.module-lair-of-the-lamb.1-bowls.md"]
participants: [{"actor_id": "actor.module-lair-of-the-lamb.the-lamb", "role": "Immediate predator entering the starting room."}]
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.the-lamb.md"]
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.starting-the-game.md"]
  knowledge: []
# Possible effects are source possibilities. Nothing here is applied or copied into a checkpoint.
possible_effects: []
---

# The Lamb Enters 1 BOWLS

## What the players perceive

In pitch darkness, the Lamb is lumbering into the room.

## Pressure and stakes

- A restrained human may be devoured.
- Noisy flight can provoke an attack.
- The free characters begin dehydrated, naked, and poorly equipped.

## Likely approaches

- Hide from the Lamb.
- Flee noisily.
- Leave slowly and quietly.

## Actor reactions

- **The Lamb** (`actor.module-lair-of-the-lamb.the-lamb`) takes part: Immediate predator entering the starting room.

## Consequences

- If the PCs hide, the Lamb devours one restrained human at random over 10 minutes and is not very alert during that time.
- If the PCs flee noisily, the Lamb attacks; finding the door in the dark requires a Wisdom check.
- If the PCs leave slowly and quietly, they are not noticed.
- After eating or losing track of the party, the Lamb goes to 9 FOUNTAIN for a bath.

### Possible effects

<!-- Source possibilities only. The runtime never applies these automatically and never copies them into a checkpoint. -->


## Completion conditions

- The party leaves the room or the Lamb loses track of them.

### Repeat behavior

- Mode: once
