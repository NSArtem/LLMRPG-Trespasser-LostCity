---
id: "situation.module-lair-of-the-lamb.negotiating-favors-with-the-ghouls"
type: "situation"
title: "Negotiating Favors with the Ghouls"
aliases: ["situation.ghoul-favor-negotiation"]
source_pages: [29]
verification: verified
references: ["actor.module-lair-of-the-lamb.gerdith", "actor.module-lair-of-the-lamb.jasper", "actor.module-lair-of-the-lamb.luntz", "actor.module-lair-of-the-lamb.molina", "item.module-lair-of-the-lamb.crysmere-blade-of-far-charcorra", "knowledge.module-lair-of-the-lamb.ghoul-favors-and-rewards"]
activation: {"condition": "The party treats the non-feral ghouls respectfully, supplies enough fresh meat for lucidity, or begins military-style parlay.", "type": "chosen"}
repeat: {"condition": "The party can complete additional favors and improve its standing; each ghoul killed reduces the total by one.", "mode": "repeatable"}
locations: []
participants: [{"actor_id": "actor.module-lair-of-the-lamb.jasper", "role": "Requests meat and can judge a stage performance."}, {"actor_id": "actor.module-lair-of-the-lamb.luntz", "role": "Participates in the ghoul bargain."}, {"actor_id": "actor.module-lair-of-the-lamb.gerdith", "role": "Can be challenged at the miniature wargame and gives the crysmere blade at seven favors."}, {"actor_id": "actor.module-lair-of-the-lamb.molina", "role": "Participates in the ghoul bargain."}]
load_with:
  actors: ["cards/actors/actor.module-lair-of-the-lamb.gerdith.md", "cards/actors/actor.module-lair-of-the-lamb.jasper.md", "cards/actors/actor.module-lair-of-the-lamb.luntz.md", "cards/actors/actor.module-lair-of-the-lamb.molina.md"]
  procedures: []
  knowledge: ["cards/knowledge/knowledge.module-lair-of-the-lamb.ghoul-favors-and-rewards.md"]
# Possible effects are source possibilities. Nothing here is applied or copied into a checkpoint.
possible_effects: [{"description": "The favor ladder and later secrets become available through successful bargaining.", "effect": "reveal-knowledge", "target": "knowledge.module-lair-of-the-lamb.ghoul-favors-and-rewards"}, {"description": "At five favors, the party's favorite non-feral ghoul may join the party.", "effect": "future-thread"}, {"description": "The ghouls may assist against the Lamb without taking risks.", "effect": "future-thread"}]
---

# Negotiating Favors with the Ghouls

## What the players perceive

Lucid ghouls bargain for meat, escape, humiliation of a rival creature, games, a performance, and the Lamb's destruction, treating the party better as more favors are completed.

## Pressure and stakes

- The party may be eaten while the ghouls remain hungry.
- The party can gain information, a companion, the crysmere blade, and cautious help against the Lamb.

## Likely approaches


## Actor reactions

- **Jasper** (`actor.module-lair-of-the-lamb.jasper`) takes part: Requests meat and can judge a stage performance.
- **Luntz** (`actor.module-lair-of-the-lamb.luntz`) takes part: Participates in the ghoul bargain.
- **Gerdith** (`actor.module-lair-of-the-lamb.gerdith`) takes part: Can be challenged at the miniature wargame and gives the crysmere blade at seven favors.
- **Molina** (`actor.module-lair-of-the-lamb.molina`) takes part: Participates in the ghoul bargain.

## Consequences

- At 4 favors, the ghouls make a strong effort not to eat the party, with a Cha save to resist.
- At 5 favors, the party's favorite ghoul joins the party.
- At 6 favors, the ghouls reveal the door behind Captain Conroy in 33 FUNGUS and discuss their trauma.
- At 7 favors, Gerdith gives the crysmere blade and the ghouls reveal Shawson's prison and magic item.
- The ghouls may help kill the Lamb but will not take risks.
- They will not help kill Shawson, though they do not condemn the party for doing so.

### Possible effects

<!-- Source possibilities only. The runtime never applies these automatically and never copies them into a checkpoint. -->

- `reveal-knowledge` → **Ghoul Favors and Rewards** (`knowledge.module-lair-of-the-lamb.ghoul-favors-and-rewards`) — The favor ladder and later secrets become available through successful bargaining.
- `future-thread` — At five favors, the party's favorite non-feral ghoul may join the party.
- `future-thread` — The ghouls may assist against the Lamb without taking risks.

## Completion conditions


### Repeat behavior

- Mode: repeatable
- Condition: The party can complete additional favors and improve its standing; each ghoul killed reduces the total by one.
