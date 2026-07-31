---
id: "situation.module-lair-of-the-lamb.the-lamb-blocks-the-bone-pile-tunnel"
type: "situation"
title: "The Lamb Blocks the Bone-Pile Tunnel"
aliases: ["situation.lamb-blocks-bone-tunnel"]
source_pages: [23]
verification: verified
references: ["actor.module-lair-of-the-lamb.the-lamb-c0865d75", "place.module-lair-of-the-lamb.10-bone-pile", "place.module-lair-of-the-lamb.14-sarcophagus", "procedure.module-lair-of-the-lamb.clearing-the-blocked-bone-pile-tunnel"]
activation: {"condition": "After 3 encounters with the Lamb.", "type": "triggered"}
repeat: {"mode": "once"}
locations: ["cards/places/place.module-lair-of-the-lamb.10-bone-pile.md", "cards/places/place.module-lair-of-the-lamb.14-sarcophagus.md"]
participants: [{"actor_id": "actor.module-lair-of-the-lamb.the-lamb-c0865d75", "role": "Blocks the tunnel after becoming cunning."}]
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.the-lamb-c0865d75.md"]
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.clearing-the-blocked-bone-pile-tunnel.md"]
  knowledge: []
# Possible effects are source possibilities. Nothing here is applied or copied into a checkpoint.
possible_effects: []
---

# The Lamb Blocks the Bone-Pile Tunnel

## What the players perceive

Bones begin filling the small crawl tunnel between 10 BONE PILE and 14 SARCOPHAGUS.

## Pressure and stakes

- The dungeon loop can be obstructed.

## Likely approaches


## Actor reactions

- **The Lamb** (`actor.module-lair-of-the-lamb.the-lamb-c0865d75`) takes part: Blocks the tunnel after becoming cunning.

## Consequences

- The Lamb begins blocking the crawl tunnel with bones.
- A blocked tunnel takes 10 minutes to clear by hand.

### Possible effects

<!-- Source possibilities only. The runtime never applies these automatically and never copies them into a checkpoint. -->


## Completion conditions


### Repeat behavior

- Mode: once
