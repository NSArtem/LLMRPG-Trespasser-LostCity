---
id: "place.module-lair-of-the-lamb.5-landing"
type: "place"
title: "5 LANDING"
aliases: ["location.5-landing"]
source_pages: [22]
verification: verified
references: ["procedure.module-lair-of-the-lamb.opening-the-iron-banded-chest-at-5-landing"]
topology_node: "place.module-lair-of-the-lamb.area-5-landing"
load_with:
  actors: []
  situations: []
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.opening-the-iron-banded-chest-at-5-landing.md"]
  knowledge: []
---

# 5 LANDING

## First impression

Heavy steel doors are locked from the far side, with ascending stairs barely visible behind them. A lit torch stands to the left; a sturdy table and locked iron-banded chest stand to the right. A horrible stench comes from the east.

## Contents

- Heavy steel doors locked from the other side.
- Ascending stairs barely visible behind the doors.
- Lit torch atop a metal pole.
- Sturdy table.
- Locked iron-banded chest.
- Fire striker atop the chest.

## Discoverable

- **Open the locked iron-banded chest.** — The chest contains a fresh torch and a vial of lamp oil.

## Hidden


## Triggers


## Hazards

- Methods forceful enough to open the chest break the vial of lamp oil.

## Resources

- Lit torch with about 1 hour of burn time remaining.
- Removable 6-foot iron torch-holder pole.
- Fire striker.
- Fresh torch.
- Vial of lamp oil.

## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.area-8-pit

- Destination: `place.module-lair-of-the-lamb.area-8-pit`
- Direction: both
- Passage kind: corridor
- Baseline state: open
- Visibility: visible

### place.module-lair-of-the-lamb.boundary-5-north-steel-doors

- Destination: `place.module-lair-of-the-lamb.boundary-5-north-steel-doors`
- Direction: conditional
- Passage kind: doorway and ascending stairway
- Baseline state: closed
- Visibility: visible
- Barriers: heavy steel doors locked from the other side
- Conditions: The doors must be opened from the far side or otherwise bypassed.

### place.module-lair-of-the-lamb.waypoint-1b-second-intersection

- Destination: `place.module-lair-of-the-lamb.waypoint-1b-second-intersection`
- Direction: both
- Passage kind: corridor
- Baseline state: open
- Visibility: visible

### place.module-lair-of-the-lamb.waypoint-5-6-corridor

- Destination: `place.module-lair-of-the-lamb.waypoint-5-6-corridor`
- Direction: both
- Passage kind: corridor
- Baseline state: open
- Visibility: visible
