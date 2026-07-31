---
id: "situation.module-lair-of-the-lamb.noisy-breach-at-44a"
type: "situation"
title: "Noisy Breach at 44A"
aliases: ["situation.44a-noisy-breach-response"]
source_pages: [40]
verification: verified
references: ["actor.module-lair-of-the-lamb.available-ghouls", "actor.module-lair-of-the-lamb.the-apparatus", "actor.module-lair-of-the-lamb.the-lamb", "actor.module-lair-of-the-lamb.the-spider-crab", "effect.44a-breach-attracts-threats", "place.module-lair-of-the-lamb.44-cistern", "place.module-lair-of-the-lamb.44a-wall", "procedure.module-lair-of-the-lamb.resolve-arrivals-after-the-44a-breach"]
activation: {"condition": "The party breaks down or otherwise breaches the wall at 44A noisily.", "type": "triggered"}
repeat: null
locations: ["cards/places/place.module-lair-of-the-lamb.44-cistern.md", "cards/places/place.module-lair-of-the-lamb.44a-wall.md"]
participants: [{"actor_id": "actor.module-lair-of-the-lamb.available-ghouls", "role": "Converging hostile party if alive and able to reach the breach."}, {"actor_id": "actor.module-lair-of-the-lamb.the-apparatus", "role": "Converging hostile party if alive and able to reach the breach."}, {"actor_id": "actor.module-lair-of-the-lamb.the-spider-crab", "role": "Converging hostile party if alive and able to reach the breach."}, {"actor_id": "actor.module-lair-of-the-lamb.the-lamb", "role": "Approaches separately and waits underwater in the cistern."}]
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.available-ghouls.md", "cards/actors/actor.module-lair-of-the-lamb.the-apparatus.md", "cards/actors/actor.module-lair-of-the-lamb.the-lamb.md", "cards/actors/actor.module-lair-of-the-lamb.the-spider-crab.md"]
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.resolve-arrivals-after-the-44a-breach.md"]
  knowledge: []
# Possible effects are source possibilities. Nothing here is applied or copied into a checkpoint.
possible_effects: [{"condition": "The wall is breached noisily.", "description": "Schedule the delayed arrivals of all surviving, reachable parties and the Lamb.", "effect": "schedule-procedure", "target": "procedure.module-lair-of-the-lamb.resolve-arrivals-after-the-44a-breach"}, {"condition": "The Lamb is alive when its arrival delay resolves.", "description": "After arriving, the Lamb waits on the bottom near the underwater tunnel mouth.", "effect": "actor-state", "target": "actor.module-lair-of-the-lamb.the-lamb"}, {"description": "Parties that arrive simultaneously may fight atop the stairs.", "effect": "future-thread"}]
---

# Noisy Breach at 44A

## What the players perceive

Breaking down the newer brick wall makes enough noise and vibration to carry through the dungeon.

## Pressure and stakes

- Several hostile parties may converge while the party is opening the route.
- Simultaneous arrivals may produce violence atop the stairs.

## Likely approaches

- Use suitable tools to make a controlled opening.
- Accept the noise and prepare for delayed arrivals.

## Actor reactions

- **Available Ghouls** (`actor.module-lair-of-the-lamb.available-ghouls`) takes part: Converging hostile party if alive and able to reach the breach.
- **The Apparatus** (`actor.module-lair-of-the-lamb.the-apparatus`) takes part: Converging hostile party if alive and able to reach the breach.
- **The Spider Crab** (`actor.module-lair-of-the-lamb.the-spider-crab`) takes part: Converging hostile party if alive and able to reach the breach.
- **The Lamb** (`actor.module-lair-of-the-lamb.the-lamb`) takes part: Approaches separately and waits underwater in the cistern.
- **Available Ghouls** (`actor.module-lair-of-the-lamb.available-ghouls`) — Arrive in 5+1d4 minutes if available.
- **The Apparatus** (`actor.module-lair-of-the-lamb.the-apparatus`) — Arrive in 5+1d4 minutes if available.
- **The Spider Crab** (`actor.module-lair-of-the-lamb.the-spider-crab`) — Arrive in 5+1d4 minutes if available.
- **The Lamb** (`actor.module-lair-of-the-lamb.the-lamb`) — Arrive in 5+1d4 minutes and wait on the cistern bottom near the underwater tunnel mouth.

## Consequences

- Each surviving, reachable hostile party arrives after 5+1d4 minutes.
- The Lamb waits submerged near the underwater tunnel mouth after it arrives.
- Multiple parties arriving together may fight one another atop the stairs.

### Possible effects

<!-- Source possibilities only. The runtime never applies these automatically and never copies them into a checkpoint. -->

- `schedule-procedure` → **Resolve Arrivals After the 44A Breach** (`procedure.module-lair-of-the-lamb.resolve-arrivals-after-the-44a-breach`) — Schedule the delayed arrivals of all surviving, reachable parties and the Lamb. (condition: The wall is breached noisily.)
- `actor-state` → **The Lamb** (`actor.module-lair-of-the-lamb.the-lamb`) — After arriving, the Lamb waits on the bottom near the underwater tunnel mouth. (condition: The Lamb is alive when its arrival delay resolves.)
- `future-thread` — Parties that arrive simultaneously may fight atop the stairs.

## Completion conditions

- All applicable 5+1d4-minute arrival delays have resolved.

### Repeat behavior
