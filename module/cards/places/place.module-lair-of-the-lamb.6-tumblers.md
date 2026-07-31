---
id: "place.module-lair-of-the-lamb.6-tumblers"
type: "place"
title: "6 TUMBLERS"
aliases: ["location.6-tumblers"]
source_pages: [22]
verification: verified
references: ["knowledge.module-lair-of-the-lamb.tumbler-password", "procedure.module-lair-of-the-lamb.operating-the-tumbler-password-system", "situation.module-lair-of-the-lamb.tumbler-password-check"]
topology_node: "place.module-lair-of-the-lamb.area-6-tumblers"
load_with:
  actors: []
  situations: ["cards/situations/situation.module-lair-of-the-lamb.tumbler-password-check.md"]
  procedures: ["cards/procedures/procedure.module-lair-of-the-lamb.operating-the-tumbler-password-system.md"]
  knowledge: ["cards/knowledge/knowledge.module-lair-of-the-lamb.tumbler-password.md"]
---

# 6 TUMBLERS

## First impression

A fish-with-hands statue holds four numbered rotating disks. A recessed doorway on the far wall cannot be forced open; a wall lever and a tiny pool of milky liquid are nearby.

## Contents

- Statue of a fish with hands.
- Four rotating disks, each showing a number from 1 to 8.
- Recessed doorway impossible to force open.
- Wall lever.
- Tiny pool of milky acid.

## Discoverable

- **Investigate the ceiling.** — A quartet of small acid nozzles is set in the ceiling.

## Hidden

- The room is a password-entry system.
- The password is 1-2-1-2.

## Triggers

- Pulling the lever checks the four-digit tumbler setting.

## Hazards

- An incorrect entry produces a horrible grinding noise every time and sprays milky acid once.

## Resources


## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.area-7-throne

- Destination: `place.module-lair-of-the-lamb.area-7-throne`
- Direction: conditional
- Passage kind: recessed doorway
- Baseline state: closed
- Visibility: visible
- Barriers: door impossible to force open
- Conditions: Set the four tumblers to 1-2-1-2 and pull the lever.
- Hazards: An incorrect setting produces grinding noise and, once, sprays milky acid.

### place.module-lair-of-the-lamb.waypoint-5-6-corridor

- Destination: `place.module-lair-of-the-lamb.waypoint-5-6-corridor`
- Direction: both
- Passage kind: corridor
- Baseline state: open
- Visibility: visible
