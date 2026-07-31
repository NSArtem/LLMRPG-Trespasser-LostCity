No. The current architecture is easy to validate, but it is not token-efficient.

The fundamental problem is that Step 4 asks the model to produce final-shaped records. Those records are partly different views of the same underlying facts.

For the hallway, the statement:

> Any touch greater than a feather triggers the ceiling; it falls for 10 seconds, rests, and resets.

gets repeated as:

- `location.hidden`
- `location.triggers`
- `location.hazards`
- `situation.activation`
- `situation.repeat`
- `situation.outcomes`
- `effect.text`

We are paying the model to paraphrase the same fact repeatedly—and then asking later stages to ensure that the paraphrases agree.

## What is wrong with the current split

The current conceptual flow is:

```text
source passage
  ├─ adventure shard
  │    ├─ location record
  │    ├─ situation record
  │    └─ procedure record
  │
  └─ effects shard
       ├─ ceiling effect
       └─ trapdoor effect
```

There are three problems.

First, the same source is processed twice: once for `adventure`, once for `effects`.

Second, the model must understand our final card architecture while reading the source. It is simultaneously extracting facts, deciding ownership, creating IDs, constructing references, and producing player-facing prose.

Third, records contain duplicated facts instead of references to shared facts.

The large JSON is a symptom. The real problem is duplicated semantic work.

## Better architecture: facts first, cards later

Step 4 should answer a simpler question:

> What does this source section assert?

It should produce one compact semantic bundle for the entire keyed section. Local code can then compile that bundle into places, situations, procedures, and effects.

```text
source section
    ↓
one semantic extraction
    ↓
facts + entities + events + options
    ↓
deterministic compiler
    ├─ place card
    ├─ situation card
    ├─ procedure card
    └─ effects, where actually useful
```

For the hallway, the model might produce:

```json
{
  "unit": "page31.area24",
  "source_pages": [31],
  "entities": [
    {
      "id": "area.24",
      "kind": "place",
      "name": "24 CRUSH HALLWAY"
    },
    {
      "id": "mechanism.ceiling",
      "kind": "mechanism"
    },
    {
      "id": "mechanism.trapdoors",
      "kind": "mechanism",
      "count": 3
    }
  ],
  "facts": [
    {
      "id": "f1",
      "subject": "area.24",
      "predicate": "dimensions",
      "value": {"length_ft": 90}
    },
    {
      "id": "f2",
      "subject": "area.24",
      "predicate": "visible-feature",
      "value": "Thick splinters and wood shards lie around the east side.",
      "visibility": "player"
    },
    {
      "id": "f3",
      "subject": "mechanism.ceiling",
      "predicate": "activation",
      "value": "Contact greater than a feather.",
      "visibility": "hidden"
    },
    {
      "id": "f4",
      "subject": "mechanism.ceiling",
      "predicate": "cycle",
      "value": {
        "fall_distance_ft": 10,
        "fall_seconds": 10,
        "rest_seconds": 10,
        "then": "reset"
      }
    },
    {
      "id": "f5",
      "subject": "mechanism.trapdoors",
      "predicate": "concealment",
      "value": "Perfectly disguised but sound hollow when tapped."
    },
    {
      "id": "f6",
      "subject": "mechanism.trapdoors",
      "predicate": "consequence",
      "value": {
        "fall_distance_ft": 40,
        "destination": "water below"
      }
    }
  ],
  "options": [
    {
      "id": "o1",
      "action": "Sprint across",
      "result": "Avoid the ceiling without a Movement check.",
      "condition": "Trapdoors must still be jumped or disabled."
    },
    {
      "id": "o2",
      "action": "Jam the ceiling with an uncrushable object",
      "cost": "The object cannot be recovered."
    },
    {
      "id": "o3",
      "action": "Climb along the wall with spikes and ropes",
      "cost": "About one hour and several encounter checks."
    },
    {
      "id": "o4",
      "action": "Hold the remote switches in 22 MUSHROOM",
      "result": "Disable the three trapdoors."
    }
  ]
}
```

This is still JSON, but every source assertion appears approximately once.

## Cards become projections

The deterministic compiler can describe which facts belong in each artifact:

```text
place 24:
  first_impression = f1 + f2
  discoverable     = f5
  hidden           = f3
  hazards          = f4 + f6

situation hallway-trap:
  activation       = f3
  repeat           = f4
  stakes           = f4 + f6

procedure cross-hallway:
  steps            = o1 + o2 + o3 + o4
```

We can retain explicit provenance:

```json
{
  "field": "situation.activation",
  "fact_refs": ["f3"]
}
```

The rendered situation can contain the sentence:

```text
Any contact heavier than a feather activates the ceiling.
```

But that sentence is generated deterministically from `f3` or copied from its normalized text. The extraction model does not have to repeat it in five record fields.

## Do we need separate effect records?

Probably not by default.

The current architecture treats many individual mechanical assertions as global `effect` records. That produces a large `cards/reference/` collection and considerable duplication.

A better rule would be:

Create a separate effect only when it is:

- referenced by multiple places or situations;
- part of a reusable rules vocabulary;
- independently applied by the campaign runtime;
- important enough to load or track separately.

Otherwise, keep the fact inside its source bundle.

For example:

```text
ceiling cycle
  → local fact used by hallway place and situation

Dying
  → reusable global effect record

Haste
  → reusable global spell/effect record
```

The crush-hallway ceiling probably does not need its own reference card. Both the place and situation can refer to `fact.page31.area24.ceiling-cycle`.

This could remove a large fraction of Lair’s 649 records.

## Shard by source unit, not output type

Instead of:

```text
page 31 × adventure
page 31 × effects
```

use:

```text
source unit: 24 CRUSH HALLWAY
tasks: discover all relevant semantic facts
```

The model should see the section once and emit all entities, facts, events, and options it finds.

Task labels can remain useful for coverage:

```json
{
  "unit": "page31.area24",
  "coverage": {
    "places": true,
    "situations": true,
    "procedures": true,
    "effects": true,
    "actors": false,
    "items": false
  }
}
```

But they should not necessarily create separate calls.

Some genuinely different material may still deserve independent extraction:

- a large class definition;
- a complex random table;
- a spell catalogue;
- a full-page actor stat block.

The primary boundary should be a source-native unit—room, actor entry, rule section, table—not an arbitrary semantic task.

## Make the model output even more compact

Several techniques can reduce output further.

### Preallocate the source-unit skeleton

Local code identifies the heading and gives the model:

```json
{
  "unit": "p31.area24",
  "name": "24 CRUSH HALLWAY",
  "page": 31
}
```

The model does not need to repeat source hashes, pack IDs, citations, and standard metadata for every fact. The runner adds them after the response.

### Use short local IDs

Inside one unit:

```text
p = place
c = ceiling
t = trapdoors
```

The compiler expands these to globally safe IDs.

### Store provenance at unit level

If every fact came from page 31, do this once:

```json
{
  "unit": "p31.area24",
  "source_pages": [31],
  "facts": [...]
}
```

Only facts spanning different pages need individual page lists.

### Use typed compact facts

Instead of verbose repeated objects:

```json
{"id":"f3","s":"c","p":"activation","v":"touch > feather","visibility":"hidden"}
```

The compiler expands the abbreviations into the durable audit schema.

I would keep JSON rather than inventing a fragile custom language, but use a compact extraction schema distinct from the rich canonical schema.

### Use JSON Lines for resumability

Each source unit can be one JSON line:

```jsonl
{"unit":"p31.area24","entities":[...],"facts":[...],"options":[...]}
{"unit":"p31.area24a","entities":[...],"facts":[...],"options":[...]}
```

Advantages:

- one failed unit does not invalidate a 100 KB response;
- output can be streamed and validated incrementally;
- retries replace one line;
- local models do not need to maintain a giant JSON document;
- partial progress survives interruption.

The durable pack response can still be assembled later if compatibility with the current contract is needed.

## Separate extraction from writing

The model currently both discovers information and writes polished operational prose.

Those are different tasks.

A better division is:

```text
LLM:
  identify facts, conditions, entities, events, choices, relationships

code:
  assign standard structure
  propagate shared facts
  build references
  render straightforward prose

optional stronger model:
  rewrite only awkward passages that cannot be rendered mechanically
```

For example, code can safely render:

```json
{
  "fall_distance_ft": 10,
  "fall_seconds": 10,
  "rest_seconds": 10,
  "then": "reset"
}
```

as:

> The ceiling falls 10 feet in 10 seconds, rests for 10 seconds, then resets.

There is no reason to pay an LLM to write that sentence three times.

## A more radical alternative: lazy semantic extraction

We could avoid extracting the entire adventure upfront.

Initial ingestion would produce only:

```text
source units
+ headings
+ page citations
+ lightweight entity index
+ map topology
```

When the GM first approaches area 24, the system extracts that room’s semantic bundle and caches it.

```text
adventure ingestion:
  cheap index only

during preparation or play:
  extract requested places and neighbors
  cache resulting semantic bundles
```

This drastically reduces initial cost when only part of an adventure is played.

The drawbacks are:

- latency before a new area is ready;
- extraction failures can occur during play;
- global identity and cross-reference resolution are incomplete;
- it is harder to guarantee module-wide consistency.

A useful compromise is to extract the main keyed locations upfront and lazily extract appendices, optional encounters, spells, and secondary rules.

## Recommended architecture

I would use this:

```text
1. Deterministically divide text into source-native units
   room, actor entry, rule, table, spell, etc.

2. Send each unit once to the semantic model

3. Receive a compact semantic bundle
   entities + facts + events + options + relations

4. Validate every fact and preserve unit/page provenance

5. Reconcile entities and relations across bundles

6. Compile facts into runtime projections
   places, situations, procedures, reusable effects

7. Render cards deterministically
```

The major conceptual change is:

> Places, situations, procedures, and effects should be read models derived from shared semantic facts—not independent LLM-authored copies of those facts.

## Expected token reduction

For Lair, the current Step 4 output is approximately 145k–170k tokens.

A source-unit/fact architecture could plausibly reduce it to:

| Output architecture | Estimated output |
|---|---:|
| Current record-first extraction | 145k–170k tokens |
| Leaner record-first extraction | 80k–120k |
| Shared fact bundles | **45k–80k** |
| Lightweight index plus lazy extraction | **15k–35k initially** |

Those are design estimates, not benchmark results. But the direction is strong: the current 586 KB response set contains substantial semantic duplication.

The best near-term improvement is not changing models. It is:

1. Stop making separate `adventure` and `effects` calls for the same section.
2. Extract one source-unit fact bundle.
3. Stop promoting every local mechanic to a global effect record.
4. Derive cards from shared facts.
5. Use one independently valid JSONL object per source unit.

That should reduce cost, improve local-model reliability, and eliminate many inconsistencies at the same time.
