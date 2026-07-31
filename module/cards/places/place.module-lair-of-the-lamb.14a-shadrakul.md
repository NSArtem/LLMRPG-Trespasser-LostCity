---
id: "place.module-lair-of-the-lamb.14a-shadrakul"
type: "place"
title: "14A SHADRAKUL"
aliases: ["location.14a-shadrakul"]
source_pages: [24]
verification: verified
references: ["actor.module-lair-of-the-lamb.robed-skeleton", "actor.module-lair-of-the-lamb.skeletal-serpent", "place.module-lair-of-the-lamb.14-sarcophagus", "situation.module-lair-of-the-lamb.goblet-and-skeletal-serpent-trap"]
topology_node: "place.module-lair-of-the-lamb.area-14a-shadrakul"
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.robed-skeleton.md", "cards/actors/actor.module-lair-of-the-lamb.skeletal-serpent.md"]
  situations: ["cards/situations/situation.module-lair-of-the-lamb.goblet-and-skeletal-serpent-trap.md"]
  procedures: []
  knowledge: []
---

# 14A SHADRAKUL

## First impression

A 10-foot drop lands on eight soft rugs; a robed skeleton sits against the wall holding a black iron spellbook and a precariously balanced crystal goblet.

## Contents

- Eight soft rugs worth 400s.
- Robed skeleton against the wall.
- Black iron spellbook.
- Delicate crystal goblet worth 800s.
- Occupant: A robed skeleton.
- Occupant: A hidden skeletal serpent guardian.

## Discoverable


## Hidden

- Once the black iron spellbook is held, the trapdoor locks in the open position.
- A skeletal serpent is concealed with the skeleton.

## Triggers


## Hazards

- The slightest touch causes the crystal goblet to tumble and break.
- Approaching the skeleton triggers a skeletal serpent attack.

## Resources


## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.area-14-sarcophagus

- Destination: `place.module-lair-of-the-lamb.area-14-sarcophagus`
- Direction: inbound
- Passage kind: sarcophagus trapdoor
- Baseline state: concealed
- Visibility: hidden
- Barriers: sarcophagus lid and swinging metal bottom
- Conditions: Enter the sarcophagus and have the lid replaced.
- Hazards: 10-foot fall; Bladed lid edges sever ropes.
