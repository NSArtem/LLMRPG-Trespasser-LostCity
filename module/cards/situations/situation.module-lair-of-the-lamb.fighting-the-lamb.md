---
id: "situation.module-lair-of-the-lamb.fighting-the-lamb"
type: "situation"
title: "FIGHTING THE LAMB"
aliases: ["situation.fighting-lamb-in-cistern"]
source_pages: [41]
verification: verified
references: ["actor.module-lair-of-the-lamb.the-lamb", "actor.module-lair-of-the-lamb.the-white-temple", "effect.first-lamb-fishing-success", "effect.lamb-resting-in-8-pit", "effect.noria-crushes-lamb", "effect.white-temple-forceful-response", "item.module-lair-of-the-lamb.harpoon", "item.module-lair-of-the-lamb.hook-hand", "item.module-lair-of-the-lamb.hooked-net", "item.module-lair-of-the-lamb.oil", "item.module-lair-of-the-lamb.rope", "knowledge.module-lair-of-the-lamb.preferred-opportunity-to-kill-the-lamb", "knowledge.module-lair-of-the-lamb.white-temple-response-to-the-lambs-death-in-the-noria", "place.module-lair-of-the-lamb.44-cistern", "procedure.module-lair-of-the-lamb.crush-the-lamb-with-the-noria", "procedure.module-lair-of-the-lamb.fish-for-the-lamb", "procedure.module-lair-of-the-lamb.run-a-fight-with-the-lamb-in-the-cistern"]
activation: {"condition": "The party chooses to fight the Lamb in the cistern instead of attacking it while it rests in 8 PIT.", "type": "chosen"}
repeat: null
locations: ["cards/places/place.module-lair-of-the-lamb.44-cistern.md"]
participants: [{"actor_id": "actor.module-lair-of-the-lamb.the-lamb", "role": "Primary enemy in the arena."}]
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.the-lamb.md", "cards/actors/actor.module-lair-of-the-lamb.the-white-temple.md"]
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.crush-the-lamb-with-the-noria.md", "cards/procedures/procedure.module-lair-of-the-lamb.fish-for-the-lamb.md", "cards/procedures/procedure.module-lair-of-the-lamb.run-a-fight-with-the-lamb-in-the-cistern.md"]
  knowledge: ["cards/knowledge/knowledge.module-lair-of-the-lamb.preferred-opportunity-to-kill-the-lamb.md", "cards/knowledge/knowledge.module-lair-of-the-lamb.white-temple-response-to-the-lambs-death-in-the-noria.md"]
# Possible effects are source possibilities. Nothing here is applied or copied into a checkpoint.
possible_effects: [{"condition": "The party gets the Lamb ensnared in the noria.", "description": "The noria can crush and kill the ensnared Lamb against the slotted ceiling.", "effect": "actor-state", "target": "actor.module-lair-of-the-lamb.the-lamb"}, {"description": "The White Temple may respond swiftly and forcefully if its godling is ejected into its drinking fountain.", "effect": "future-thread"}]
---

# FIGHTING THE LAMB

## What the players perceive

The cistern becomes a difficult moving battle across deep water, boats, swimmers, pillars, and the operating noria.

## Pressure and stakes

- The party must kill or survive the Lamb while movement is constrained by deep water.
- Using the noria to kill the Lamb can provoke the White Temple.

## Likely approaches

- Use harpoons, hooked nets, ropes, and burning oil in combination.
- Fish for the Lamb with the hook hand and acceptable bait.
- Ensnare the Lamb in the noria so the waterwheel drags and crushes it.

## Actor reactions

- **The Lamb** (`actor.module-lair-of-the-lamb.the-lamb`) takes part: Primary enemy in the arena.

## Consequences

- The first acceptable hook-hand fishing attempt works automatically.
- An ensnared Lamb can be dragged by the noria and crushed against the slotted ceiling.
- A Lamb ejected into the White Temple's drinking fountain can bring a swift, forceful response.

### Possible effects

<!-- Source possibilities only. The runtime never applies these automatically and never copies them into a checkpoint. -->

- `actor-state` → **The Lamb** (`actor.module-lair-of-the-lamb.the-lamb`) — The noria can crush and kill the ensnared Lamb against the slotted ceiling. (condition: The party gets the Lamb ensnared in the noria.)
- `future-thread` — The White Temple may respond swiftly and forcefully if its godling is ejected into its drinking fountain.

## Completion conditions

- The Lamb is killed in the cistern.

### Repeat behavior
