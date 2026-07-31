---
id: "situation.module-lair-of-the-lamb.reassemble-the-seven-mummies"
type: "situation"
title: "Reassemble the Seven Mummies"
aliases: ["situation.reassemble-seven-mummies"]
source_pages: [32]
verification: verified
references: ["effect.favored-by-vandoh", "item.module-lair-of-the-lamb.five-costumed-mummified-heads", "item.module-lair-of-the-lamb.parts-of-seven-mummies", "place.module-lair-of-the-lamb.25-crypt", "place.module-lair-of-the-lamb.29-stage", "procedure.module-lair-of-the-lamb.reassemble-and-return-the-seven-mummies"]
activation: {"condition": "The party decides to collect, reassemble, and return all seven mummies or a sufficiently close reconstruction.", "type": "chosen"}
repeat: {"mode": "once"}
locations: ["cards/places/place.module-lair-of-the-lamb.25-crypt.md", "cards/places/place.module-lair-of-the-lamb.29-stage.md"]
participants: []
load_with:
  actors: []
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.reassemble-and-return-the-seven-mummies.md"]
  knowledge: []
# Possible effects are source possibilities. Nothing here is applied or copied into a checkpoint.
possible_effects: [{"description": "The most proactive character becomes Favored by Vandoh.", "effect": "future-thread"}]
---

# Reassemble the Seven Mummies

## What the players perceive

Moon-marked crypts contain grouped mummy limbs and torsos, while five costumed heads appear on the stage and two more heads rest in a sack.

## Pressure and stakes

- The scattered remains and missing heads must be matched and returned.

## Likely approaches


## Actor reactions


## Consequences

- The character who took the most initiative becomes Favored by Vandoh.

### Possible effects

<!-- Source possibilities only. The runtime never applies these automatically and never copies them into a checkpoint. -->

- `future-thread` — The most proactive character becomes Favored by Vandoh.

## Completion conditions

- All seven mummies are reassembled and returned, or the reconstruction is close enough.

### Repeat behavior

- Mode: once
