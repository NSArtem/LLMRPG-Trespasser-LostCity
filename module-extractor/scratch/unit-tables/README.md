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

## Text retention, the number this gate turns on — and the one it cannot see

The unit count says nothing about whether anything was lost. Retention does —
every character the line layer produced, against the characters that reached a
unit. It is the first row of every digest, and it is what turned a
plausible-looking 33-unit segmentation of Doom into a defect report.

**It is not sufficient, and defects 5–7 are why.** All three reorder or
misattach text without losing any. Braided columns lose nothing: every character
arrives, interleaved with another column's. A heading emitted ahead of the prose
it introduces loses nothing; the prose simply lands under the next heading.
Retention read 100% on Шпиль Кетцаль throughout all three. **A measure that
counts characters cannot check their order.** Reading the lines is what found
them — and looking at the short units, which the reviewer's list invited, is
what found the last two.

| Source | Units | Keyed | Under 40B | Pages | Retained |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lair of the Lamb | 214 → 192 → **202** | 51 → **54** | 18 → 11 → **18** | 53 / 54 | 99.9% |
| Winter's Daughter | 115 → 96 → **103** | 42 → **48** | 20 → 18 → **15** | 29 / 31 | 99.8% |
| Falkrest Abbey | 80 → 55 → **56** | 35 → **22** | 18 → **13** | 42 / 46 | 99.8% |
| Doom of the Savage Kings | 33 → **37** | 23 → **26** | 2 → **1** | 13 → **15** / 18 | 82.9% → **99.0%** |
| Шпиль Кетцаль | 280 → 180 → **182** | 77 → **80** | 25 → 9 → **5** | 73 / 74 | 100.0% |

The middle figure is where defects 1–4 left each source; the last is after
defects 5–7. Not one keyed area was lost at any point, and three sources gained
keyed areas once their columns stopped braiding — those areas had been
swallowed into a neighbouring column's line and were never visible. Falkrest's
keyed count *falls* because thirteen of its thirty-five were rows of its
contents page.

## The questions, as they were answered

The gate opened with four. Checking the last of them found a fifth defect, which
is described after them. What follows is what was found, what was done, and what
is left for the reviewer to accept or reject.

**1. Doom's uncovered pages were content, and the cause is a drop cap.** Of the
five pages it left uncovered, p1 and p18 are full-bleed cover images with no
text layer and p2 is the credits page — those are correct exclusions. **p3 and
p4 were not: they hold `Introduction`, `The Hound of Hirot`, `Adventure
Background` and `The Village of Hirot`, 10,509 characters of prose, and no unit
contained any of it.**

DCC opens each section with a 72pt `RomantiqueInitials` initial — an 85pt-tall
run sitting across three 18pt body baselines. Line assembly groups by vertical
span, so the initial fuses the heading and the first body lines into one line
whose style is the body's:

```
runs   y= 52 'IntroductIon'            21pt Duvall bold
       y= 78 'R'                       72pt RomantiqueInitials
       y= 89 'emember the good old days, when adventures were'  14pt BookAntiqua
line   'R emember the good old days, when adventures were  IntroductIon'  14pt BookAntiqua
```

The heading loses its rank, `assemble` finds no heading on either page, and both
pages fall through the `current is None` branch as front matter. `Adventure
Background` fails a second way: it survives line assembly and is then folded
into its body row by `rejoin_run_ins`, which has no rank information and so
cannot know it is folding away a top-rank heading.

*Fixed.* An initial no longer sets the row's vertical tolerance (`is_drop_cap`,
`_row_span` in `columns.py`); a row that is only an initial still adopts the
paragraph it opens, so no letter is orphaned. Doom now retains **98.9%**, its
only remaining loss is the credits page, and `Introduction`, `Adventure
Background` and `The Hound of Hirot` are units carrying their prose.

**2. Doom's 8,882-byte unit is not one authored section.** `Area D – The Sunken
Fens` spans five pages because it absorbed `Area D-1 – Lair of the Hound` — the
adventure's climax. Checking all 26 area keys in the source against the unit
headings, three were absorbed: **C-7, C-10 and D-1.**

They present as over-long headings, because the line carries the heading *and*
the first words of its paragraph:

```
'Area C-7 – Antechamber of the Savage King:  Tall slabs of'   -> 11 words, rejected
'Area A-4 – Chapel of Justicia:  The chapel is'               ->  9 words, accepted
```

The word count is the symptom. The cause is that the run-in split only cut a row
where the tail matched the document's body style exactly, and Doom sets the
read-aloud text after a keyed heading in **bold italic** — so these three rows
were never split, while A-4's was.

*Fixed.* The split now cuts where the row leaves its *opening* style, and where
the tail is not body it requires the prefix to close like a heading (`:` or `.`)
— without that guard, Шпиль Кетцаль's stat lines, which change style mid-row
with no heading present, produced fifteen spurious units. Italic also joined the
style tuple: blind to it, Doom's bold-italic read-aloud text was indistinguishable
from its bold act titles and every boxed paragraph became a heading. **All 26 of
Doom's area keys are now units**, and its largest is `Area D-1` at 5,145B rather
than `Area D` at 8,882B.

**3. Lair's stat blocks fragment, and the boundaries are wrong, not merely
fine.** Page 20 is the monster appendix. The author writes each monster twice:
the name over its prose, then the name again over its stat lines. We emitted ten
units where three monsters were written, and `Immunity – Acid.` was not a
36-character fragment but a **1,065-byte unit** that had swallowed the `Phobia`
trait and the prose after it. A unit named for one line of a stat block and
containing another monster's description is a boundary defect.

*Fixed.* Size settles it (`opens_a_section` in `units.py`): a subordinate
heading no larger than body is a label inside something, not a section of its
own. Lair's rules chapter sets `Time`, `Doors` and `Movement` *above* body and
keeps segmenting; its bestiary sets the stat-block name and traits *at* body and
now absorbs them. A key overrides size, because Doom's 26 areas are set at body
size in a display family. Page 20 is now three units — one per monster.

This is the change with the widest reach: it is why Шпиль Кетцаль falls from 280
units to 180. Every absorbed unit there is a stat-block internal
(`КЛАСС ЗАЩИТЫ: 2 (мех)`, `ПЕРЕДВИЖЕНИЕ: 2`, `НАВЫКИ: разведка 3`); every named
section survives, larger — `ПРЕДЫСТОРИЯ` grew from 192B to 3,697B by reclaiming
what had been shredded out of it.

**It also has a cost, and the reviewer should price it.** Lair sets page 20 and
page 28 identically — a 21pt heading, then 16pt stat-block names under it — but
means different things by them. On page 20 the 16pt name repeats the creature
above and belongs to it. On page 28 the 21pt heading is `Indirect Encounters`, a
table, and the 16pt names below it are `Ghoul (Jasper or Luntz)` and `Lantern
Worm`. No typographic signal separates the two cases, so both absorb.

Nothing is lost or truncated: of the fourteen Lair units carrying a stat line,
twelve are named for the creature or the room holding it, and the two carrying
two blocks each group them defensibly — Father Bastoval with his bodyguards, and
the wandering-encounter table with the creatures it rolls. But `p28.lantern-worm`
is no longer a unit of its own, and it was a deliberate member of the T1.1 pack
precisely because it was a standalone stat block. The pack builder now names
`p28.indirect-encounters` instead; the zip already sent to the models is
untouched, and `csv_check.py` still reads that zip.

**4. Falkrest's short units are three different things.** Thirteen of the
eighteen are on page 3, which is the map: legend entries (`Portal`, `Statue`,
`Secret doors`) and in-map labels (`N`, `S`, `P`, `Rowayn`, `Ghost`). Three are
table-of-contents rows on page 7, identifiable by their dot leaders
(`Hooks .........6`). Two — `Appendix`, `Treasure & Monster Overview` — are
genuine headings that happen to have no body.

*Decided: the map labels stay, the contents page goes.* Keeping the labels is
the safer direction — the dataflow document is explicit that a false negative
loses source material and nothing downstream can detect it — and their home is
Stage 3 classification at T2.4, not another segmentation heuristic. A dot leader
points at a page and never opens one, so those rows are no longer headings.

That single rule is why Falkrest's keyed count falls from 35 to **22**: thirteen
of the thirty-five were contents rows, and being keyed they had survived every
rule aimed at short units. All nineteen of its real rooms remain, and every room
its contents page names has a unit.

**Falkrest's page coverage is clean.** Its four uncovered pages are the title
page, two blank pages (p4 carries no text and no image at all) and p42, whose
only text is the folio `38`.

**5. A page may hold more than one layout, and columns braided where it does.**
Checking the last open question — Шпиль Кетцаль's 8,433-byte maximum — showed
the earlier note about it was wrong. `11. ЗАЛ МУЗЫКИ ВЕТРА 12. ПОГОСТ ГРОМОВЫХ`
was not two keyed areas joined by the wrapped-heading rule. The two headings
arrived **already fused from the line layer**, and so did both rooms' prose:

```
p65 :: 11. ЗАЛ МУЗЫКИ ВЕТРА 12. ПОГОСТ ГРОМОВЫХ
p65 :: ся друг о друга, нарушая тишину обширного  Пол пещеры устилает несметное
p65 :: зала. С потолка свисают сотни таких музы -  гигантских костей громовых
```

`find_gutter` asks one question of a whole page. Page 65 sets two rooms side by
side above a full-width table of berry effects; the table crosses the middle on
twenty-five rows, so the middle is genuinely no clearer than the rest and
detection **correctly** declines. Every row was then assembled across the full
width. Eight pages across four sources were affected, up to 7.9% of a source's
text. Poppler's own reading-order mode braids the same page, so this is not a
threshold that was set carelessly.

*Fixed.* `region_lines` in `columns.py` counts a boundary as supported by a *run
of consecutive rows* rather than by the page, so it can hold for part of a page
and lapse for the rest, and one run may hold several boundaries at once — which
is what the three-column rumour table on Doom's page 4 is, and what a single
gutter could never express. A cluster of holes is reduced by **intersection**,
not by averaging: averaging put Doom's boundary at 448.6 while one justified
line reached 449.0, so that line counted as crossing and orphaned every row
above it.

**It is a fallback, never a replacement.** The real gutters are narrow — Шпиль
Кетцаль's median is four points on a 698-point page — far below the hole width
this model needs to see a boundary at all. `find_gutter` reads them from the
crossing profile and still wins wherever it fires, so the 151 pages that already
worked are untouched. A parameter sweep over 36 settings picked the one that
loses no keyed area on any source.

**6. A full-width heading was emitted before every column, not where it sits.**
Reading order put all spanning content first. Winter's Daughter page 13 sets two
centred keyed headings with prose between them, so both headings came out ahead
of all the prose: `3. Tomb Entrance` was a 16-byte unit and its granite slab was
filed under `4. Worm Hole`. The same on page 15 with `6. Blindfolded Statue`.

*Fixed.* Each spanning line opens a section and the columns beneath it belong to
that section (`page_lines` in `columns.py`). Winter's Daughter gains three keyed
areas, and `3. Tomb Entrance` now carries its own door.

**7. A keyed heading could never wrap.** `join_wrapped_headings` refused to join
any pair where *either* line opened a key. The guard exists so a table keyed by
die number (`1 Athletic`, `2 Beautiful`) does not collapse — but that is the
*second* line opening a key. With the first line barred too, every keyed heading
too long for its measure was cut in half:

```
   33B  12. ПОГОСТ ГРОМОВЫХ
 7734B  ЯЩЕРИЦ            <- the rest of its own name, carrying the room
```

Four of Шпиль Кетцаль's keyed areas were cut this way, and the source's largest
unit was named for the second half of a heading.

*Fixed.* Only the second line is tested. Шпиль's largest unit is now
`12. ПОГОСТ ГРОМОВЫХ ЯЩЕРИЦ`, and its units under 40 bytes fall from eleven to
five.

## The reviewer's judgment calls, as decided

Every question of judgment this gate raised has been put and answered. The
answers are recorded here so no later task re-opens them.

- **Falkrest's twelve map labels stay as units.** Keeping them is the safer
  direction — a false negative loses source material and nothing downstream can
  detect it — and their home is Stage 3 classification at T2.4, not another
  segmentation heuristic. If Stage 3 cannot classify them cheaply, this is the
  place that changes.
- **Lair page 28's absorbed stat blocks are accepted.** A stat block may live
  inside the table that summons it. Nothing is lost or truncated: twelve of the
  fourteen Lair units carrying a stat line are named for the creature or the
  room holding it, and the two carrying two blocks group them defensibly.
  Separating page 28 from page 20 would need a signal the typography does not
  provide — both set a 21pt heading over 16pt names — so it would mean matching
  the stat-block template (`Lvl`/`Def`/`Int`) as a boundary signal. Not worth a
  new heuristic for one unit.
- **Doom's p2 credits page stays uncovered until T4.4.** It is the last
  uncovered page holding text (685 characters). It is front matter, but the
  segmenter has no concept of *"excluded as credits"* to record that with, and
  the page-completeness invariant that wants the statement is T4.4's. Recording
  it there, once, beats inventing an exclusion vocabulary here.

**The remaining units under 40 bytes are not defects.** Lair's eighteen are
section dividers with no body of their own (`Appendices`, `Part 3: The Cistern`)
and three map labels on p54; Falkrest's thirteen are the map labels decided
above; Шпиль's five are two contents rows, a stat label, a die-column header and
a section title. Doom has one. None is a truncation — that was defects 6 and 7,
and they are fixed — but the count is where the next one would show, and it is
worth re-reading whenever it moves.

## What a decision here unblocks

T2.3 promotes this segmenter into the package as `segmentation.py`. Reviewing
after that means changing shipped code rather than a prototype.

Stage 3's claim to determinism is conditional on this gate: the dataflow
document says that if the classifier's human queue is not small, **segmentation**
is what needs fixing. A boundary problem left here resurfaces at T2.4, two
phases later and harder to attribute.
