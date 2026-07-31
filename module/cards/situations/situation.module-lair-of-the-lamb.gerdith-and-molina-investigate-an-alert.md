---
id: "situation.module-lair-of-the-lamb.gerdith-and-molina-investigate-an-alert"
type: "situation"
title: "Gerdith and Molina Investigate an Alert"
aliases: ["situation.ballista-alert-and-investigation"]
source_pages: [32, 33]
verification: verified
references: ["actor.module-lair-of-the-lamb.gerdith", "actor.module-lair-of-the-lamb.molina", "effect.ballista-ghouls-alerted", "place.module-lair-of-the-lamb.25-crypt", "place.module-lair-of-the-lamb.27-ballista", "place.module-lair-of-the-lamb.29-stage", "procedure.module-lair-of-the-lamb.gerdiths-investigation"]
activation: {"condition": "Combat, a portcullis winch, a dropped sarcophagus lid, or visible light in 25E, 25F, 25G, or 29 STAGE alerts Gerdith.", "type": "triggered"}
repeat: {"mode": "repeatable"}
locations: ["cards/places/place.module-lair-of-the-lamb.25-crypt.md", "cards/places/place.module-lair-of-the-lamb.27-ballista.md", "cards/places/place.module-lair-of-the-lamb.29-stage.md"]
participants: [{"actor_id": "actor.module-lair-of-the-lamb.gerdith", "role": "Detects the disturbance, commands the response, and leads the investigation."}, {"actor_id": "actor.module-lair-of-the-lamb.molina", "role": "Accompanies Gerdith while complaining and joking."}]
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.gerdith.md", "cards/actors/actor.module-lair-of-the-lamb.molina.md"]
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.gerdiths-investigation.md"]
  knowledge: []
# Possible effects are source possibilities. Nothing here is applied or copied into a checkpoint.
possible_effects: [{"description": "The disturbance alerts Gerdith.", "effect": "actor-state", "target": "actor.module-lair-of-the-lamb.gerdith"}, {"description": "Gerdith initiates an investigation with Molina.", "effect": "schedule-procedure", "target": "procedure.module-lair-of-the-lamb.gerdiths-investigation"}]
---

# Gerdith and Molina Investigate an Alert

## What the players perceive

Heavy bootsteps and humming are audible from 27 BALLISTA; after an alert, Gerdith loudly orders Molina to accompany her and the two armored ghouls move to investigate.

## Pressure and stakes

- Exploration of the crypts and stage can draw two intelligent, ravenous armored ghouls.

## Likely approaches


## Actor reactions

- **Gerdith** (`actor.module-lair-of-the-lamb.gerdith`) takes part: Detects the disturbance, commands the response, and leads the investigation.
- **Molina** (`actor.module-lair-of-the-lamb.molina`) takes part: Accompanies Gerdith while complaining and joking.
- **Gerdith** (`actor.module-lair-of-the-lamb.gerdith`) — Loudly orders Molina to accompany her and investigates.
- **Molina** (`actor.module-lair-of-the-lamb.molina`) — Complains, cracks jokes, and accompanies Gerdith.

## Consequences

- Gerdith and Molina investigate together.

### Possible effects

<!-- Source possibilities only. The runtime never applies these automatically and never copies them into a checkpoint. -->

- `actor-state` → **Gerdith** (`actor.module-lair-of-the-lamb.gerdith`) — The disturbance alerts Gerdith.
- `schedule-procedure` → **Gerdith's Investigation** (`procedure.module-lair-of-the-lamb.gerdiths-investigation`) — Gerdith initiates an investigation with Molina.

## Completion conditions


### Repeat behavior

- Mode: repeatable
