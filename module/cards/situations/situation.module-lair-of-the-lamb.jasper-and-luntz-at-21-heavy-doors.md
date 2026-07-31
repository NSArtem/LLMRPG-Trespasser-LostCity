---
id: "situation.module-lair-of-the-lamb.jasper-and-luntz-at-21-heavy-doors"
type: "situation"
title: "Jasper and Luntz at 21 HEAVY DOORS"
aliases: ["situation.ghoul-parley-at-heavy-doors"]
source_pages: [30]
verification: verified
references: ["actor.module-lair-of-the-lamb.jasper", "actor.module-lair-of-the-lamb.luntz", "place.module-lair-of-the-lamb.21-heavy-doors", "procedure.module-lair-of-the-lamb.open-21-heavy-doors"]
activation: {"condition": "The party approaches or fumbles with 21 HEAVY DOORS.", "type": "triggered"}
repeat: {"condition": "If the party leaves, Jasper and Luntz later move into the random-encounter rotation instead of resetting this scene.", "mode": "once"}
locations: ["cards/places/place.module-lair-of-the-lamb.21-heavy-doors.md"]
participants: [{"actor_id": "actor.module-lair-of-the-lamb.jasper", "role": "Leads the theatrical, unconvincing friendly overture."}, {"actor_id": "actor.module-lair-of-the-lamb.luntz", "role": "Supports the overture and shares the intent to eat the party."}]
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.jasper.md", "cards/actors/actor.module-lair-of-the-lamb.luntz.md"]
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.open-21-heavy-doors.md"]
  knowledge: []
# Possible effects are source possibilities. Nothing here is applied or copied into a checkpoint.
possible_effects: [{"description": "Jasper and Luntz can become later wandering encounters if the party leaves.", "effect": "future-thread"}]
---

# Jasper and Luntz at 21 HEAVY DOORS

## What the players perceive

Chatter and laughter come from beyond the barred doors; Jasper addresses the door like a party host and the two ghouls openly complain of hunger while attempting friendliness.

## Pressure and stakes

- The party risks a deceptive ghoul attack while trying to pass the doors.

## Likely approaches

- Pry the bar and squeeze through.
- Use heavy tools to remove the chains.
- Offer the ghouls dead bodies elsewhere.

## Actor reactions

- **Jasper** (`actor.module-lair-of-the-lamb.jasper`) takes part: Leads the theatrical, unconvincing friendly overture.
- **Luntz** (`actor.module-lair-of-the-lamb.luntz`) takes part: Supports the overture and shares the intent to eat the party.
- **Jasper** (`actor.module-lair-of-the-lamb.jasper`) — Pretends friendship while looking for an opportunity to eat the party.
- **Luntz** (`actor.module-lair-of-the-lamb.luntz`) — Pretends friendship while looking for an opportunity to eat the party.

## Consequences

- If offered bodies elsewhere, the ghouls pretend to agree, circle back, and attack shortly afterward.
- If the party leaves, the pair later wander the halls and can appear as random encounters.

### Possible effects

<!-- Source possibilities only. The runtime never applies these automatically and never copies them into a checkpoint. -->

- `future-thread` — Jasper and Luntz can become later wandering encounters if the party leaves.

## Completion conditions


### Repeat behavior

- Mode: once
- Condition: If the party leaves, Jasper and Luntz later move into the random-encounter rotation instead of resetting this scene.
