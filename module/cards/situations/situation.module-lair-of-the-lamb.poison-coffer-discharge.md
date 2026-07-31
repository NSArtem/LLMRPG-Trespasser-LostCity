---
id: "situation.module-lair-of-the-lamb.poison-coffer-discharge"
type: "situation"
title: "Poison Coffer Discharge"
aliases: ["situation.42-poison-coffer-discharge"]
source_pages: [38]
verification: verified
references: ["effect.sunken-gallery-poison", "place.module-lair-of-the-lamb.sunken-gallery", "procedure.module-lair-of-the-lamb.handle-a-sunken-gallery-coffer"]
activation: {"condition": "Any of the five poison-filled coffers is opened.", "type": "triggered"}
repeat: {"condition": "The hazard can trigger from each poison-filled coffer.", "mode": "repeatable"}
locations: ["cards/places/place.module-lair-of-the-lamb.sunken-gallery.md"]
participants: []
load_with:
  actors: []
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.handle-a-sunken-gallery-coffer.md"]
  knowledge: []
# Possible effects are source possibilities. Nothing here is applied or copied into a checkpoint.
possible_effects: []
---

# Poison Coffer Discharge

## What the players perceive

A poison-filled coffer releases gas from its front and the cloud expands through the gallery.

## Pressure and stakes

- Anyone in front of the coffer risks ongoing poison damage.
- The expanding gas can poison characters who do not flee immediately.

## Likely approaches

- Open the coffer with a hooked pole or from the side for a +4 bonus.
- Flee immediately when the gas begins to fill the room.

## Actor reactions


## Consequences

- A failed Dex save poisons a character for 1d6 damage per round until a Con check succeeds.
- Immediate flight avoids poisoning from the room-filling cloud.
- The gas settles after 10 minutes.

### Possible effects

<!-- Source possibilities only. The runtime never applies these automatically and never copies them into a checkpoint. -->


## Completion conditions

- The gas settles 10 minutes after release.

### Repeat behavior

- Mode: repeatable
- Condition: The hazard can trigger from each poison-filled coffer.
