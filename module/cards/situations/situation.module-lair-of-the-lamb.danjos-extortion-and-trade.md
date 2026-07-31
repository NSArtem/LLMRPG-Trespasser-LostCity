---
id: "situation.module-lair-of-the-lamb.danjos-extortion-and-trade"
type: "situation"
title: "Danjo’s Extortion and Trade"
aliases: ["situation.danjo-extortion-trade"]
source_pages: [24]
verification: verified
references: ["actor.module-lair-of-the-lamb.danjo", "place.module-lair-of-the-lamb.15-crack", "procedure.module-lair-of-the-lamb.trading-with-danjo"]
activation: {"condition": "The party talks to Danjo through the opening in 15 CRACK.", "type": "keyed"}
repeat: {"mode": "repeatable"}
locations: ["cards/places/place.module-lair-of-the-lamb.15-crack.md"]
participants: [{"actor_id": "actor.module-lair-of-the-lamb.danjo", "role": "Extortionist merchant and outside runner."}]
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.danjo.md"]
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.trading-with-danjo.md"]
  knowledge: []
# Possible effects are source possibilities. Nothing here is applied or copied into a checkpoint.
possible_effects: []
---

# Danjo’s Extortion and Trade

## What the players perceive

The chicken vendor outside the crack demands a reason not to report the party to the temple guards, then offers goods at extreme prices.

## Pressure and stakes

- Danjo may alert the temple guards.
- Mundane goods cost at least 20 times market value.
- Special purchases take 1-3 hours.

## Likely approaches

- Give Danjo a reason or payment not to inform the guards.
- Buy candles, chickens, bread, or a knife.
- Ask him to purchase another item across town.

## Actor reactions

- **Danjo** (`actor.module-lair-of-the-lamb.danjo`) takes part: Extortionist merchant and outside runner.

## Consequences

- Once the extortion is resolved, Danjo sells mundane items at no less than 20 times market value.
- He can fetch other items in 1-3 hours.
- Conversation time is real time: 1 in-game minute equals 1 minute at the table.

### Possible effects

<!-- Source possibilities only. The runtime never applies these automatically and never copies them into a checkpoint. -->


## Completion conditions


### Repeat behavior

- Mode: repeatable
