---
id: "place.module-lair-of-the-lamb.shroud"
type: "place"
title: "Shroud"
aliases: ["location.38-shroud"]
source_pages: [36]
verification: verified
references: ["effect.shroud-soul-severance", "procedure.module-lair-of-the-lamb.operate-the-shroud-guillotine", "situation.module-lair-of-the-lamb.soul-severing-guillotine-cycle"]
topology_node: "place.module-lair-of-the-lamb.area-38-shroud"
load_with:
  actors: []
  situations: ["cards/situations/situation.module-lair-of-the-lamb.soul-severing-guillotine-cycle.md"]
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.operate-the-shroud-guillotine.md"]
  knowledge: []
---

# Shroud

## First impression

A stack of 12 planks partly obscures the doorway. Beyond it stands a huge shrouded object about 9 feet tall.

## Contents

- A stack of 12 planks partially obscures the doorway and appears to have boarded it up previously.
- A huge shrouded object stands 9 feet tall.

## Discoverable

- **Remove the shroud.** — Removing the shroud reveals a guillotine with no blade and a winch on its side.
- **Turn the winch.** — Turning the winch sounds and feels like a blade is being raised; after about 12 seconds the unseen mechanism falls with a heavy thunk.

## Hidden

- The blade-less guillotine severs a victim's soul rather than the victim's head.
- A severed soul is sent to room 99, which the source marks as not written yet.

## Triggers

- Turning the winch starts a roughly 12-second cycle that ends with a heavy thunk.
- A person whose head is in the guillotine when the cycle completes has their soul severed.

## Hazards

- The guillotine can sever a person's soul without physically injuring the head or neck.

## Resources


## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.area-37-chewed-bones

- Destination: `place.module-lair-of-the-lamb.area-37-chewed-bones`
- Direction: both
- Passage kind: doorway
- Baseline state: partially blocked
- Visibility: visible
- Barriers: stack of 12 planks partially obscuring the doorway

### place.module-lair-of-the-lamb.area-99-not-written-yet

- Destination: `place.module-lair-of-the-lamb.area-99-not-written-yet`
- Direction: outbound
- Passage kind: guillotine soul transport
- Baseline state: dormant
- Visibility: hidden
- Conditions: Place a person's head in the bladeless guillotine and operate the winch until the unseen blade falls.
- Hazards: The person's soul is severed from the body and sent to room 99; the soulless body loses normal emotional and developmental capacities.
