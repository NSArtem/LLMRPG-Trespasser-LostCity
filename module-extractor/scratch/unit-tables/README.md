# T0.5 — the unit-boundary review

**This directory is the artefact for a human review gate.** The question it
exists to answer is the one no test can: *are the unit boundaries right?*

An implementer may not close this gate. The work order is explicit — judgment
about whether the work is good is not the implementer's to make.

One `.md` per source is the readable view; the `.json` beside it is Contract A in
full. Regenerate both with:

```bash
python3 module-extractor/scratch/units.py --all --dump module-extractor/scratch/unit-tables
python3 module-extractor/scratch/digest.py --all --out module-extractor/scratch/unit-tables
```

## Where the numbers stand

After the T0.3/T0.4 corrections:

| Source | Units | Keyed | Under 40B | Pages covered |
| --- | ---: | ---: | ---: | ---: |
| Lair of the Lamb | 237 → **214** | 51 | 21 → **18** | 53 / 54 |
| Winter's Daughter | 128 → **115** | 42 | 26 → **20** | 29 / 31 |
| Falkrest Abbey | 68 → **80** | 34 → **35** | 10 → **18** | 42 / 46 |
| Doom of the Savage Kings | 72 → **33** | 23 | 3 → **2** | 13 / 18 |
| Шпиль Кетцаль | 281 → **280** | 82 → **77** | 34 → **25** | 73 / 74 |

No real keyed area was lost. Шпиль Кетцаль's five are d6 attack-table rows
(`1 РАЗРЫВАЮЩАЯ АТАКА`, `2 СМЕРТОНОСНЫЙ РЫВОК`) folding into their table, which
is what should happen to them.

## Look at these four first

**Falkrest moved the wrong way, and the cause is known.** Its map pages label
features `Statue`, `Ghost`, `N`, `P`, `Rowayn` across five to nine pages at
scattered vertical positions. The old furniture rule counted pages only and
deleted them silently; the positional rule keeps them, and page 3 alone now
yields 14 short label units. Keeping them is the safer direction — the dataflow
document is explicit that a false negative loses source material and nothing
downstream can detect it — but the right home for map labels is Stage 3
classification at T2.4, not another segmentation heuristic. **Decide whether
they stay as units.**

**Stat-block internals still fragment on Lair page 20.** `Immunity – Acid.` and
`Spells - delay, haste, scry` become their own units. The text is present and
adjacent to the block it belongs to, so this is a boundary-quality question
rather than a loss.

**Doom covers 13 of 18 pages and Falkrest 42 of 46.** T4.4 preserves a
page-completeness invariant: every physical page must be covered by some unit or
explicitly excluded as a cover, divider, blank or non-operational illustration.
Those gaps have not been classified either way. If they are art and front
matter, nothing is wrong; if they are content, segmentation is losing pages
silently, which is the exact failure the invariant exists to make visible.

**Doom's 8,882-byte maximum unit.** Large units are a cost problem and truncated
ones are a correctness problem, so the size alone is not a defect — but it is
worth confirming it really is one authored section.

## What a decision here unblocks

T2.3 promotes this segmenter into the package as `segmentation.py`. Reviewing
after that means changing shipped code rather than a prototype.

Stage 3's claim to determinism is conditional on this gate: the dataflow
document says that if the classifier's human queue is not small, **segmentation**
is what needs fixing. A boundary problem left here resurfaces at T2.4, two
phases later and harder to attribute.
