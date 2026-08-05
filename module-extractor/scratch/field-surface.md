# T3.2 (first half) — the field surface the compiler must fill

**Why this is early.** The work order sequences T3.2 after T1.5, so that the
frozen vocabulary can be mapped onto the baseline's fields. That is backwards
for the half of the task that only reads the baseline. If a card field has no
predicate that can produce it, the cheapest moment to learn that is **before**
the vocabulary is frozen, not after — and the plan's own risk register puts
"compilation flattens the cards" second, with Phase 3 as the only place it gets
tested. This enumerates the surface now so T1.4 can decide against evidence.

**This is the first half only.** Marking each pair against a *frozen* predicate
still waits for T1.5. What follows maps against the T1.1 draft, which is what
exists.

Nothing here reads `scratch/baseline/` from inside the package — this is a
scratch script's output, and the contamination rule stands.

## The surface

613 records, 11 record types, **59 distinct `(record_type, field)` pairs**,
393 records carrying nothing but `title` + `text` against 220 structured. Those
figures reproduce the plan's exactly.

| | Pairs | |
|---|---:|---|
| Derived by code, never asked of the model | 23 | `title` ×11, `topology_node`, `keyed_area`, and 10 `*_references` |
| Producible from the draft vocabulary | 11 | |
| **No predicate can produce them** | **25** | |

### Derived, not extracted

`title` comes from `entity_name`. `keyed_area` comes from the unit's own key,
which Contract A already carries. `topology_node` is a Stage 9 review decision —
the baseline sets it to `null` for 24 CRUSH HALLWAY with a written rationale.
The ten `*_references` fields are D-2's deterministic derivation. None of these
is a vocabulary question, and none should ever reach the model.

### The 25 that nothing can produce

```text
location    (70 records)  discoverable, hazards, hidden, occupants, resources, triggers
situation   (51 records)  activation, actor_reactions, approaches, completion,
                          outcomes, participants, perceived, possible_effects,
                          repeat, stakes
procedure   (37 records)  steps, trigger
actor       (35 records)  behavior, goals, hidden, reactions, relationships,
                          starting_state
table       (27 records)  entries
```

Most of these are ordinary gaps: a predicate is missing and T1.4 can add one.
Two are not, and they are the reason this document exists.

## Two shape mismatches the vocabulary cannot close by adding a predicate

Both are the same defect, and both are already visible in the response measured
at T1.3 — not hypothetical.

### `table.entries` — a roll and a result

The baseline holds:

```json
{"roll": "1-2", "result": "Unique. Jasper and Luntz (if alive)."}
```

The draft declares `entry` as list-valued free text, so the model produced:

```text
encounters,entry,,1-3 Unique. The Three Little Lambs, crawling on the ceiling.
```

The roll range and the result are fused into one string. A deterministic
compiler cannot split them without guessing at a regular expression, and
guessing at Stage 10 is the thing the design exists to prevent. 27 table records
depend on this.

### `location.discoverable` — an action and what it reveals

The baseline holds:

```json
{"condition": "Spend any amount of time searching the pile.",
 "information": "A small crawl tunnel leads to 14 SARCOPHAGUS."}
```

The draft expresses discoverability through the visibility column, which can
only record **that** something is discoverable, never **how**. `schema.md`
papers over this by telling the model to "state the action in the value", and
the response did exactly as asked:

```text
trapdoors,concealment,discoverable,Perfectly disguised; tapping them reveals that they sound hollow.
```

Condition and information, fused by a semicolon. 37 of 70 location records
depend on separating them, and the rendered card prints them as
`**<condition>** — <information>`.

### They share one cause, and the contract already answers it

A row carries at most one free-text field. Where a concept needs two pieces of
prose, the dataflow document is explicit: *"it becomes two rows"*. That is
exactly what `#option` does with its `action` / `result` / `cost` slots, and it
works — the response used it correctly for all four ways across the crush
hallway.

So the pattern exists and simply was not applied to `discoverable` or `entry`.
Two candidate resolutions for T1.4:

1. **Slot rows, like `#option`.** `#entry,e1,roll,1-2` + `#entry,e1,result,…`,
   and the same for discoveries. Consistent with the contract's own answer,
   costs one more row per item.
2. **Structured JSON.** `entry` and `discoverable` join `exit`/`cycle` with
   declared key sets `{roll, result}` and `{condition, information}`. Fewer
   rows, and JSON has already proven reliable in practice — every JSON value in
   the measured response parsed.

Option 2 is cheaper and fits what the model already does well. Option 1 keeps
prose out of JSON, which matters if a result ever contains a brace.

## What the response suggests about the other 23

The measured response covered four of the five affected record types without
being asked to, which is evidence the gaps are nameable rather than deep:

- `procedure.steps` / `trigger` arrived as `#option` rows with `action`,
  `result`, `cost` and `requires` slots — richer than the baseline's flat
  `steps` list, not poorer.
- `actor.behavior`, `goals` and `starting_state` arrived as `role`,
  `disposition` and `note`. Serviceable, but three baseline fields collapsing
  into `note` is precisely the flattening T3.5 is meant to catch.
- `situation` was not exercised: no unit in `pack-001` is a situation. **Ten of
  the 25 uncovered pairs are situation fields, the largest single block, and the
  prototype pack has no evidence about any of them.** Whatever else T1.4
  decides, a second pack should carry a unit that produces a situation.

## Recommendation for T1.4

1. Close the two shape mismatches. They cannot be deferred to T3.3 — a compiler
   cannot invent a split that the wire format discarded.
2. Add predicates for `hazards`, `resources`, `triggers`, `occupants`,
   `stakes`, `outcomes`, `perceived`, `completion`, `approaches`. These are
   plain naming.
3. Decide whether `situation.activation` and `repeat` stay objects. The baseline
   has `{type, condition}` and `{mode, condition}`; the draft's `activation` is
   scalar text and there is no `repeat` at all.
4. Get a situation-bearing unit into the next pack before freezing anything.
