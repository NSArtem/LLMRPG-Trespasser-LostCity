---
id: "situation.module-lair-of-the-lamb.spider-crab-in-the-pool"
type: "situation"
title: "Spider Crab in the Pool"
aliases: ["situation.43-spider-crab-pool"]
source_pages: [38]
verification: verified
references: ["actor.module-lair-of-the-lamb.spider-crab", "effect.spider-crab-grab", "place.module-lair-of-the-lamb.spider-crab"]
activation: {"condition": "The giant undead spider crab remains hidden in the pool while creatures or objects are within the room.", "type": "ongoing"}
repeat: {"condition": "The crab can lunge whenever something drops within its 38-foot reach.", "mode": "repeatable"}
locations: ["cards/places/place.module-lair-of-the-lamb.spider-crab.md"]
participants: [{"actor_id": "actor.module-lair-of-the-lamb.spider-crab", "role": "Watches from hiding, lunges at falling targets, and seeks a way out."}]
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.spider-crab.md"]
  procedures: []
  knowledge: []
# Possible effects are source possibilities. Nothing here is applied or copied into a checkpoint.
possible_effects: [{"description": "After escaping, the spider crab is added to the wandering monster table.", "effect": "future-thread"}]
---

# Spider Crab in the Pool

## What the players perceive

Eyestalks watch from the murky water. When noticed, they dip away for a few seconds; anything falling close enough draws a sudden lunge from the pool.

## Pressure and stakes

- Anything falling within 38 feet of the surface can be attacked and grabbed.
- A large dropped object can release the crab into the dungeon.

## Likely approaches

- Avoid dropping creatures or objects within the crab's reach.
- Recognize that a large object in the pool will let the crab climb out.

## Actor reactions

- **Spider Crab** (`actor.module-lair-of-the-lamb.spider-crab`) takes part: Watches from hiding, lunges at falling targets, and seeks a way out.
- **Spider Crab** (`actor.module-lair-of-the-lamb.spider-crab`) — The first time it knows it has been seen, it hides for a few seconds.
- **Spider Crab** (`actor.module-lair-of-the-lamb.spider-crab`) — It lunges at anything dropped within its reach.
- **Spider Crab** (`actor.module-lair-of-the-lamb.spider-crab`) — It uses a large dropped object as a platform and eventually escapes.

## Consequences

- The crab lunges at a falling target.
- If a large object is dropped into the pool, the crab eventually escapes and is added to the wandering monster table.

### Possible effects

<!-- Source possibilities only. The runtime never applies these automatically and never copies them into a checkpoint. -->

- `future-thread` — After escaping, the spider crab is added to the wandering monster table.

## Completion conditions

- The crab escapes the pit after gaining a large object to stand on.

### Repeat behavior

- Mode: repeatable
- Condition: The crab can lunge whenever something drops within its 38-foot reach.
