---
id: "situation.module-lair-of-the-lamb.vandoh-possesses-a-left-hand"
type: "situation"
title: "Vandoh Possesses a Left Hand"
aliases: ["situation.41-vandoh-hand-possession"]
source_pages: [37]
verification: verified
references: ["effect.favored-by-vandoh", "effect.vandoh-possessed-hand", "place.module-lair-of-the-lamb.sunken-shrine"]
activation: {"condition": "The first person speaks or prays to the statue of Vandoh.", "type": "triggered"}
repeat: {"mode": "once"}
locations: ["cards/places/place.module-lair-of-the-lamb.sunken-shrine.md"]
participants: []
load_with:
  actors: []
  procedures: []
  knowledge: []
# Possible effects are source possibilities. Nothing here is applied or copied into a checkpoint.
possible_effects: [{"description": "If all ghouls are killed, the possessed character becomes Favored by Vandoh as described in Appendix D.", "effect": "future-thread"}]
---

# Vandoh Possesses a Left Hand

## What the players perceive

The first speaker or supplicant's left hand becomes rigid and holds up a number of fingers. It clenches with rage whenever a ghoul is encountered.

## Pressure and stakes

- A character's left hand is possessed and rigid.

## Likely approaches


## Actor reactions


## Consequences

- The raised finger count equals the number of ghouls remaining in the dungeon.
- The hand clenches with rage whenever a ghoul is encountered.
- If all ghouls are killed, the character becomes Favored by Vandoh.

### Possible effects

<!-- Source possibilities only. The runtime never applies these automatically and never copies them into a checkpoint. -->

- `future-thread` — If all ghouls are killed, the possessed character becomes Favored by Vandoh as described in Appendix D.

## Completion conditions

- Killing all ghouls triggers the character becoming Favored by Vandoh.

### Repeat behavior

- Mode: once
