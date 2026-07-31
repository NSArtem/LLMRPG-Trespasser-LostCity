---
id: "place.module-lair-of-the-lamb.19-priests"
type: "place"
title: "19 PRIESTS"
aliases: ["location.19-priests"]
source_pages: [26]
verification: verified
references: ["actor.module-lair-of-the-lamb.priest-of-the-pool", "effect.pink-pool-compulsion", "effect.pink-urine-ecstasy-and-longevity", "effect.pink-urine-language-loss", "situation.module-lair-of-the-lamb.priests-awaken-and-attack"]
topology_node: "place.module-lair-of-the-lamb.area-19-priests"
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.priest-of-the-pool.md"]
  situations: ["cards/situations/situation.module-lair-of-the-lamb.priests-awaken-and-attack.md"]
  procedures: []
  knowledge: []
---

# 19 PRIESTS

## First impression

Three perfectly round pools of pink liquid are set into the floor, each about 1 foot deep in the middle. Three old people in loincloths lie one per pool, smiling in their sleep, twitching, and groaning; one wears a jeweled crab bracer. Two iron spikes hold the east door shut.

## Contents

- Three perfectly round pools of pink liquid, each about 1 foot deep in the middle.
- Three old people in loincloths, one in each pool, apparently asleep and occasionally twitching and groaning.
- A jeweled crab bracer worth 600s, worn by one sleeper.
- Two iron spikes holding the east door shut.
- Occupant: Three Priests of the Pool, one in each pink pool.

## Discoverable


## Hidden

- The sleepers are retired priests of Vandoh, and immersion in the Lamb's psychotropic urine is their reward.
- They will remain in the urine, writhing in ecstasy, until they die hundreds of years from now.
- The urine has robbed these three priests of all language except the words ‘lamb’, ‘blasphemy’, and ‘magenta’.

## Triggers

- Touching any one of the priests causes that priest to scream verbally and psychically, awakening all four priests, including Vandress in area 20, who then attack.

## Hazards

- Tasting the pink liquid causes a compulsion to taste more, lie down in it, and do everything possible to return to it; there is No Save.
- Touching a priest awakens all four priests and triggers their attack.

## Resources

- Jeweled crab bracer worth 600s.
- Two iron spikes securing the east door.

## Exits

<!-- Generated from topology.yaml; canonical passage state lives there. -->

### place.module-lair-of-the-lamb.area-11-crab-mural

- Destination: `place.module-lair-of-the-lamb.area-11-crab-mural`
- Direction: conditional
- Passage kind: doorway
- Baseline state: closed
- Visibility: visible
- Barriers: locked wooden door
- Conditions: The locked wooden door must be opened or bypassed.

### place.module-lair-of-the-lamb.area-20-pools

- Destination: `place.module-lair-of-the-lamb.area-20-pools`
- Direction: both
- Passage kind: doorway
- Visibility: visible
- Barriers: wooden door shown on the map

### place.module-lair-of-the-lamb.boundary-21-heavy-doors

- Destination: `place.module-lair-of-the-lamb.boundary-21-heavy-doors`
- Direction: conditional
- Passage kind: ascending stairway
- Baseline state: closed
- Visibility: visible
- Barriers: east door held shut by two iron spikes
- Conditions: Remove or bypass the two iron spikes holding the east door shut.
