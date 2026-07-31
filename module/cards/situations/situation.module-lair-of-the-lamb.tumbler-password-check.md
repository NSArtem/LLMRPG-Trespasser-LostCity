---
id: "situation.module-lair-of-the-lamb.tumbler-password-check"
type: "situation"
title: "Tumbler Password Check"
aliases: ["situation.tumbler-password-result"]
source_pages: [22]
verification: verified
references: ["effect.tumbler-acid-spray", "knowledge.module-lair-of-the-lamb.tumbler-password", "place.module-lair-of-the-lamb.6-tumblers", "place.module-lair-of-the-lamb.7-throne", "procedure.module-lair-of-the-lamb.operating-the-tumbler-password-system"]
activation: {"condition": "Set the four tumblers and pull the lever in 6 TUMBLERS.", "type": "chosen"}
repeat: {"condition": "The acid sprays only once; the grinding noise occurs on every incorrect attempt.", "mode": "repeatable"}
locations: ["cards/places/place.module-lair-of-the-lamb.6-tumblers.md"]
participants: []
load_with:
  actors: []
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.operating-the-tumbler-password-system.md"]
  knowledge: ["cards/knowledge/knowledge.module-lair-of-the-lamb.tumbler-password.md"]
# Possible effects are source possibilities. Nothing here is applied or copied into a checkpoint.
possible_effects: []
---

# Tumbler Password Check

## What the players perceive

Pulling the lever makes the mechanism evaluate the four numbered disks.

## Pressure and stakes

- An incorrect code triggers noise and acid.
- The correct code opens access to 7 THRONE.

## Likely approaches

- Enter 1-2-1-2 and pull the lever.
- Try another four-digit setting.

## Actor reactions


## Consequences

- Correct setting: the door to 7 THRONE opens.
- Incorrect setting: a horrible grinding noise occurs every time and milky acid sprays once, dealing 1d6 diminishing damage each turn until rinsed off.

### Possible effects

<!-- Source possibilities only. The runtime never applies these automatically and never copies them into a checkpoint. -->


## Completion conditions


### Repeat behavior

- Mode: repeatable
- Condition: The acid sprays only once; the grinding noise occurs on every incorrect attempt.
