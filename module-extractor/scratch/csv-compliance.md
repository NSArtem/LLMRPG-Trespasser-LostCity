# T1.3 — CSV contract compliance

**Gate status: passed, with a finding the gate was not looking for.** Two
independent responses were measured. The row format is reliable. **Entity
decomposition is not**, and nothing downstream is designed to absorb that — see
[Granularity varies between runs](#granularity-varies-between-runs).

The measurement is not a formality. The dataflow document commits to the row
format on an explicitly unmeasured assumption — *"How reliably do models follow
the 'four fields, free text last, never escape anything' rule in practice? The
rule is verifiable on data; model compliance with it is not yet known and should
be measured on a prototype before the format is committed to."*

| | |
|---|---|
| Pack (response 1) | `pack-001`, sha256 `647282156437c204ae557b1b7c5a82b66604341e1e99f7034913d99098467866` |
| Pack (response 2 onward) | same units and schema, sha256 `5267f439e7a743de9d1719be0a39d694bc9bc1988b74d55e07c1f73448baed2a` — the delivery instruction differs, see *Transport* |
| Units | 6 (`p31.24-crush-hallway`, `p33.27-ballista`, `p28.lantern-worm`, `p18.active-encounters-2`, `p8.doors`, `p46.haste`) |
| Responses | `_exchange/pack-001.csv`, `_exchange/pack-001.r1.csv` |
| Model | ChatGPT, `sol`, thinking effort high, independent conversations |
| Transport | manual (H-1) |
| Checker | `scratch/csv_check.py`, covered by `scratch/test_csv_check.py` |

## Both responses

```text
                                    response 1   response 2
non-blank lines                            129          122
rows splitting into four fields        129/129      122/122
                                          100%         100%
structural rows                             47           42
facts                                       82           80
units marked                               6/6          6/6
violations                                   2            2
```

Neither response omitted a unit, duplicated one, invented one, or emitted a row
that failed to split. The violations are the same two in both, on the same
predicate, with the same keys:

```text
response 1   line 63  stat: ['Dis', 'Halberd', 'Int', 'Move', 'Str']
             line 78  stat: ['Crawl', 'Dis', 'Int', 'Slam']
response 2   line 73  stat: ['Dis', 'Halberd', 'Int', 'Move', 'Str']
             line 81  stat: ['Crawl', 'Dis', 'Int', 'Slam']
```

A defect that reproduces identically across independent runs is a defect in the
schema, not variance in the model. See *Both violations* below.

## Response 1

```text
non-blank lines                              129
rows splitting into exactly four fields  129/129   (100%)
structural rows                               47
facts                                         82
units marked                                 6/6   (none missing, none duplicated)
violations                                     2   (both schema defects, see below)
```

| Category | Count |
|---|---:|
| json key | 2 |

Everything else the checker can detect scored zero: field count, unknown row
type, unknown predicate, unknown visibility, unknown entity kind, unknown option
slot, undeclared subject, repeated scalar, unparseable JSON, campaign state,
missing unit, duplicated unit, unpacked unit, fact before unit, malformed page
list, stray Markdown fence.

Rows per unit: 45, 30, 8, 13, 22, 11. 32 entities declared across 23 distinct
predicates, 8 `#option` rows, 1 `#uncertain` row.

## The escaping rule holds

This is the assumption the whole format rests on, and it survived:

- **24 of 129 rows carry a comma inside the fourth field**, and every one parsed
  correctly. `a24a,dimensions,,Water, 10' deep.` and
  `#option,uncrushable,action,Throw an uncrushable object into the hallway, such
  as the metal cage, the ballista, or a combination of other sturdy objects.`
- **4 rows carry a quotation mark.** None was escaped, and none needed to be.
- No row was wrapped in JSON, no column drifted, and the model volunteered no
  quoting of its own.

The model also emitted no fence and no preamble, so `clean()` had nothing to
strip. That is the outcome the prompt asked for, though see *Transport* below
for why asking for it was a mistake in a different way.

Response 2 used one predicate response 1 did not (`visible`) and omitted one it
did (`disarm-from`); 22 of 23 predicates were common to both. Vocabulary usage
is stable even where granularity is not.

## Both violations are defects in `schema.md`, not in the response

```text
line 63  stat: ['Dis', 'Halberd', 'Int', 'Move', 'Str']
line 78  stat: ['Crawl', 'Dis', 'Int', 'Slam']
```

The rows are:

```text
armored-ghoul,stat,,{"Lvl":2,"Def":"plate","Halberd":"1d8","Move":"as human","Int":5,"Str":7,"Dis":"hungry"}
worm,stat,,{"Lvl":4,"Def":"leather","Slam":"1d6","Crawl":"slow","Int":2,"Dis":"hungry"}
```

The source reads `Lvl 2 Def plate Halberd 1d8 / Move as human Int 5 Str 7 Dis
hungry`. The model transcribed it exactly. The draft schema declared

```text
stat  {"Lvl": n, "Def": <text>, "<attack>": <dice>, ...}
```

which is not a key set at all — it is a key set with an ellipsis. **A stat
block's keys are open by construction**: they are whatever statistics the
ruleset names, and a contract that closes them is a contract that fails on the
second ruleset it meets. Contract D item 3 requires structured predicates to
declare their key set, and `stat` cannot satisfy that requirement as written.

This is a finding for T1.4, not something to fix here. The two candidate
resolutions:

1. **`stat` stops being structured** and becomes list-valued free text, one row
   per statistic — `worm,stat,,Lvl 4`. Loses computability, gains portability.
2. **`stat` keeps JSON with an open key set**, and ingest validates that the
   value parses as a flat object of scalars without checking key names.

Option 2 preserves what the JSON was for. Whichever is chosen, the general rule
it implies should be written down: *a structured predicate either declares a
closed key set or is explicitly declared open, and there is no third state.*

## Findings for T1.4 that the counters cannot show

**`#option` slots have no declared arity.** The response contains

```text
#option,wall,cost,It takes about an hour.
#option,wall,cost,A couple of encounter checks will occur during it.
```

Two `cost` rows for one option. That reads correctly and is faithful to the
source, but `schema.md` declares arity for predicates and says nothing about
option slots, so the checker cannot judge it either way. Contract D item 2's
requirement — declared, never inferred — applies to slots as much as to
predicates.

**A fact value referring to a unit-external entity.** `trapdoors,disarm-from,,22
MUSHROOM.` names a keyed area that this unit does not declare, and could not:
22 MUSHROOM is described on a different page. D-2 derives `references`
deterministically from values that resolve to declared entities, and this one
resolves to nothing until Stage 7 has seen the whole module. Either
`disarm-from` values are late-bound, or the model needs a way to mark a
cross-unit reference as such. T2.8 must not silently drop it.

**Entity kind `rule` used for a procedure.** The model declared
`#entity,crossing,rule,Crossing the Hallway` and hung two `rule` facts off it.
The source section is a set of ways to cross a hazard — closer to a procedure
than to a rule — and the pack offers `#option` for exactly that, which the model
also used, for the other three approaches. So one section came out as a mix of
`rule` facts and `#option` rows. Whether that is a vocabulary gap or acceptable
variation is a T1.4 judgement.

**The trailing period.** Many values end in a full stop copied from the source
mid-sentence: `trapdoors,disarm-from,,22 MUSHROOM.` The compiler will render
these into prose at Stage 10, and a value that is sometimes a sentence and
sometimes a fragment is a rendering problem, not a parsing one. Worth a note in
the frozen schema.

## Transport

**The response arrives as chat text, not as a file.** The pack's `prompt.md`
asks for "plain CSV lines and nothing else — no Markdown fences", which produces
exactly that: 129 bare lines in a chat bubble, to be selected by hand and pasted
into a file. That instruction optimised for the parser and ignored the human,
and H-1 is a human step.

It is also unnecessary. The dataflow document already permits deterministic
removal of transport artefacts, naming "a stray markdown fence" as the example,
and `csv_check.clean` strips fences and counts them. A single fenced block gives
the reader a copy control in every chat client, gives the response an
unambiguous beginning and end, and costs the parser one `startswith("```")`.

Changed in `phase1_pack._prompt`: ask for one fenced ` ```csv ` block, and for a
downloadable file where the client can produce one. **This does not touch the
row contract** — not a field, not a predicate, not a vocabulary — so response 2
remains comparable to response 1 on every figure in this report.

## Granularity varies between runs

This is what the second response bought, and it is not about the row format.

```text
unit                        facts A  facts B   entities A  entities B
p31.24-crush-hallway             24       23           12          11
p33.27-ballista                  22       25            7          10
p28.lantern-worm                  6        5            1           1
p18.active-encounters-2           7        9            5           5
p8.doors                         15       14            6           1
p46.haste                         8        4            1           1
```

**No content was lost in either direction.** Both runs carry every rule on page
8 and every clause of *Haste*. What differs is how many things the model decided
were in the unit:

```text
run 1   #entity,doors,rule,Doors        run 2   #entity,doors,rule,Doors
        #entity,wooden,rule,Wooden doors
        #entity,metal,rule,Metal doors          doors,rule,,Wooden doors can be
        #entity,locked,rule,Locked doors                    kicked in...
        #entity,portcullises,rule,...           doors,rule,,Metal doors cannot...
        #entity,barred,rule,Barred doors        doors,rule,,Locked doors can...
```

Six entities against one, for identical input. *Haste* likewise: run 1 split the
spell into `effect` plus four `note` rows, run 2 put all five sentences in one
`effect` value.

### The baseline says which one is right

```text
rule records in the baseline citing page 8:  8
  doors, exploration-time, investigation-and-searching, light,
  mapping, movement, noise, stealth
```

One record per *section*, which is one record per **unit** — and the segmenter
produces exactly those units. `Haste` is likewise a single baseline record with
one `text` blob. So run 2 matches the target granularity for both, and run 1
over-decomposes a rules section by six to one.

That is not universal: for `p31.24-crush-hallway` both runs declared 11–12
entities, and the baseline does produce a place, a situation, two procedures and
two effects from that one unit. A keyed room contains several things; a rules
section is one thing. Nothing in `schema.md` says so, so the model decides per
run, and the decisions differ by up to sixfold.

### Why this matters more than the format did

**Entity identity is what Stage 7 canonicalises and Stage 8 groups on.** Run 1
yields five canonical `rule` records for the doors section, run 2 yields one.
The module's record count, its card count and its index are all downstream of a
choice the contract does not constrain.

**Stage 6 mandates per-unit retry** — *"Rejection is per unit. A failed unit is
re-requested on its own."* A retried unit is a fresh sample, so a module can
finish with unit X finely decomposed and unit Y coarsely, decided by which units
happened to fail validation once.

**Stage 8 cannot see it.** Its conflict machinery detects two units asserting
different *values* for the same `(entity, predicate)`. It has no notion of two
runs disagreeing about how many entities exist, and since only one response per
pack is ever ingested, the disagreement is invisible rather than escalated. The
one mechanism designed to catch extraction disagreement is blind to the largest
disagreement measured here.

### For T1.4

`schema.md` must state a decomposition rule, not just a vocabulary. The rule
that reproduces the baseline is roughly: *declare one entity per distinct thing
the unit describes; a rules section, a spell, a table and a stat block are each
one thing, while a keyed room is a place plus whatever mechanisms, actors and
items it contains.* Whatever wording is chosen, it needs the same treatment as
list-versus-scalar in Contract D item 2 — declared, never inferred.

Worth measuring on the next pack: whether stating the rule actually narrows the
spread. If it does not, granularity has to be constrained structurally rather
than by instruction — for example by having the runner declare the expected
entity kinds per unit from its classification, which Stage 3 already computes.
