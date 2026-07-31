---
id: "situation.module-lair-of-the-lamb.akinas-rescue-bargain"
type: "situation"
title: "Akina’s Rescue Bargain"
aliases: ["situation.akina-rescue-bargain"]
source_pages: [23]
verification: verified
references: ["actor.module-lair-of-the-lamb.akina", "item.module-lair-of-the-lamb.ruby-ring-of-wisdom", "knowledge.module-lair-of-the-lamb.akinas-knowledge", "place.module-lair-of-the-lamb.8-pit"]
activation: {"condition": "The party communicates with Akina in 8 PIT.", "type": "keyed"}
repeat: {"condition": "Until Akina is rescued or the offer is otherwise resolved.", "mode": "repeatable"}
locations: ["cards/places/place.module-lair-of-the-lamb.8-pit.md"]
participants: [{"actor_id": "actor.module-lair-of-the-lamb.akina", "role": "Captive offering payment and information."}]
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.akina.md"]
  procedures: []
  knowledge: ["cards/knowledge/knowledge.module-lair-of-the-lamb.akinas-knowledge.md"]
# Possible effects are source possibilities. Nothing here is applied or copied into a checkpoint.
possible_effects: []
---

# Akina’s Rescue Bargain

## What the players perceive

Akina, a ragged captive in the pit, offers a valuable ruby ring in exchange for rescue.

## Pressure and stakes

- Akina’s freedom.
- The Ruby Ring of Wisdom worth 1000s.
- Access to basic information about the White Temple, Vandoh, and the Lamb.

## Likely approaches

- Agree to rescue Akina.
- Ask Akina about the White Temple, Vandoh, or the Lamb.

## Actor reactions

- **Akina** (`actor.module-lair-of-the-lamb.akina`) takes part: Captive offering payment and information.

## Consequences

- Akina offers the Ruby Ring of Wisdom in exchange for rescue.
- Akina can provide basic information about the White Temple, Vandoh, and the Lamb.

### Possible effects

<!-- Source possibilities only. The runtime never applies these automatically and never copies them into a checkpoint. -->


## Completion conditions


### Repeat behavior

- Mode: repeatable
- Condition: Until Akina is rescued or the offer is otherwise resolved.
