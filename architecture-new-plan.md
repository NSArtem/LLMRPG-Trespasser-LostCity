# Migration plan: from the page/record pipeline to the unit/fact dataflow

**Status:** plan. Describes how to get from the code in `module-extractor/` to
the design specified in [architecture-new-dataflow.md](architecture-new-dataflow.md).

The dataflow document is the target and the sole authority on what the pipeline
should do. This document is only about sequencing, disposition of existing code,
and the gates that decide whether each step worked.

## The state this plan starts from

The branch was reset to `base/extractor-v1` — the extractor implementation,
before *Lair of the Lamb* was ever imported. The adventure data, the generated
module, and the campaign built on it are all off this branch.

**Both fixed points in this document are tags, not hashes.** The history before
the rebuild was squashed from 31 commits to 6, which changed every hash in it. A
tag survives that; a hash reads as `unknown revision` and does so silently.

What remains is the extractor and nothing it has ever been run on: roughly 7,900
lines under `module-extractor/module_extractor/` and 6,300 lines of tests. The
campaign is back to `campaign_status: preparation` with no applied checkpoints
and an empty `module_id`, so **no downstream consumer is currently bound to any
extractor output**.

That cuts in two directions:

- **It removed the largest human cost.** There is no review overlay whose 63
  field-scoped decisions must be re-authored against fact-scoped identities, and
  no live campaign whose place IDs must survive the rebuild. That work does not
  exist now.
- **It removed the reference build.** Nothing on this branch says what good
  output looks like.

The second problem is already solved. The previous build was recovered from
`baseline/lair-lamb` — the tip of the `lair-lamb` branch — and is **committed to
this branch** at
`module-extractor/scratch/baseline/` — 613 canonical records, the runtime index,
and the old review overlay.

It is the only existing example of a finished module for this source, and Phase 3
depends on comparing new compiled cards against it field by field. Committing it
rather than leaving it derivable means no checkout can lose it.

**It is a comparison baseline, not an input.** Nothing under
`module_extractor/` may read it. If compilation could see the old output it could
copy from it, and the Phase 3 diff would prove nothing.

## Where the pipeline splits

The twelve stages do not divide evenly into "keep" and "replace". They divide at
one seam, and the seam is the durable fact store between Stage 6 and Stage 7.

```text
Stages 1-6    new front end        text -> units -> packs -> facts
   ---------- the fact store --------- the seam
Stages 7-12   preserved back end   facts -> identity -> records -> cards -> scene
```

**Everything upstream of the fact store is new work.** Stage 1 keeps its shape
but changes tooling. Stage 2 does not exist at all. Stage 3 replaces a model
stage with deterministic code. Stage 4 rekeys its partitioning from page runs to
unit lists. Stage 5 replaces the extraction contract outright. Stage 6 loses most
of its validation surface and gains a four-field parser.

**Everything downstream survives.** `reconciliation.py` already implements
Stage 8 almost exactly as specified. `rendering.py`, `topology.py`,
`operations.py`, and `scene.py` — about 2,000 lines — are untouched provided the
Stage 10 compiler emits `operational-module/v3`, and `assembly.py` needs only the
compiler wired in ahead of it.
`identity.py` and `review.py` keep their concepts and rewrite their internals.

The seam is already present in the code. Stage 6 calls for facts written to
durable storage "in a rich, self-describing form", and that is close to what
`evidence._content_observations` produces today: `observation_id`, `concept_id`,
typed fields, source pages, confidence, originating pack. Stage 7 onward already
consumes exactly that shape. The new front end should terminate in it rather
than invent a parallel one.

This is why the work is a new front end attached to a preserved back end, and not
a new repository. Rebuilding `deterministic_zip`, `atomic_publish`,
`content_tree_hash`, the staging-and-publish discipline in
`cli._publish_workspace_directories`, and the whole rendering and scene layer
would re-derive subtle, working, tested code that the dataflow document does not
change in kind.

## Constraints that do not move

The extractor is not a standalone tool. Three things outside `module-extractor/`
consume its output and none of them are in scope to change.

**The play contract.** `module/GENERATED_OUTPUT.json` must declare
`play_contract: module-play/v1` with `verification: verified`. Enforced in four
places, all findable with `grep -rn 'module-play/v1'`:
`scripts/validate_repo.py` (`PLAY_CONTRACT`), `MANIFEST.md`,
`rules/precedence.md`, and `chatgpt-project/SETUP_AND_PROMPTS.md`.

**The output tree.** `MANIFEST.md` and the ChatGPT project navigate
`module/MODULE.md`, `module/index.json`, `module/cards/`, `module/topology.yaml`,
and treat `module/audit/` as never-load. Stage 11 already produces exactly this
and should not be redesigned.

**Determinism.** Identical inputs produce identical outputs, and the generated
tree is hash-enumerated and refuses to overwrite output it did not generate.
Preserved as-is.

**What is no longer a constraint.** An earlier revision of this plan treated the
live campaign as a fourth fixed point — `CURRENT.md` pinning
`place.module-lair-of-the-lamb.1-bowls`, with applied checkpoints bound to it.
Resetting to `base/extractor-v1` removed the campaign, so nothing external now requires the
rebuild to reproduce a specific canonical place ID. **The identity policy should
still produce those IDs** — Phase 3 diffs against a baseline that uses them — but
that is now a correctness check against the old build, not an external contract.
If a future campaign binds before the rebuild lands, this becomes a hard
constraint again.

**The repository currently validates clean.** `scripts/validate_repo.py` reports
zero errors and zero warnings across 67 files, because the campaign no longer
references a module that is not there. That is the baseline Phase 6 must not
break, rather than a failure it has to clear.

## Phases

Each phase has a gate. A failed gate stops the phase and reopens the design
question behind it rather than being worked around.

---

### Phase 0 — Segmentation spike

**Why first.** Stage 2 is specified in terms of typographic signals — "heading
case, weight, and size changes", "stat-block and table layout patterns", "list
and column structure" — and Stages 3, 4, and 6 all sit on top of it. Stage 3's
claim to determinism is explicitly conditional: *"if [the human queue] is not
[small], segmentation needs fixing rather than the classifier."*

**Partially answered already.** A spike against *Lair of the Lamb* settled the
central question, and the results change what this phase still has to do.

`preparation.py` invokes `pdftotext -layout`, whose output genuinely does discard
font, weight, and size — and on this two-column source it also interleaves both
columns onto shared lines, so `1 BOWLS` arrives with the neighbouring column's
body text appended to it. Regexing that output finds headings that are really
cross-references inside prose (`14 SARCOPHAGUS.`, `15 CRACK).`).

But the fix needs no new library. **`pdftotext -bbox-layout` emits word-level
bounding boxes as XHTML** — same Poppler binary the pipeline already shells out
to, parseable with stdlib `xml.etree`. Measured on the source:

| Line height | Meaning | Count |
|---:|---|---:|
| 56.1 | part titles | 8 |
| 20.8 | section headings | 24 |
| **14.5** | **keyed-area headings** | **58** |
| 12.2 | body text | 1663 |

All 58 keyed areas sit at exactly one height and nothing else in the document
does — no false positives. Columns separate cleanly by `xMin` (≈43 left, ≈310
right). Glyph height substitutes for font size; font *name* and *weight* are not
exposed by `-bbox-layout` and were not needed.

**What remains.**

1. Generalize across the other four sources. They span three Adobe producers and
   one 1982 Ghostscript scan; all five have usable text layers, but none of the
   height thresholds are portable constants. Heights must be clustered per
   document, not hardcoded.
2. Continuation across page breaks — a unit spanning pages 31–32 must join and
   cite both.
3. Non-keyed units: stat blocks, random tables, titled sidebars, rules sections.
   The keyed-area result says nothing about these, and they are most of the
   non-adventure material.
4. Emit the unit table — ID, heading, pages, column, byte size — for review.

**Gate.** Every keyed area in each of the five sources appears as exactly one
unit, units spanning a page break are joined, and no unit is cut mid-concept.
Judged by reading the table against the PDF, not by a metric.

**If it fails on the remaining sources.** The fallback from the dataflow document
applies — manual unit boundaries, or per-page units as a degraded mode. Note that
it can now fail *per document*: a per-source segmentation profile is an
acceptable outcome, a per-source hand-tuned threshold table is not.

**Deliverable.** A `segmentation.py` prototype and a unit table for all five
sources. The Stage 1 library question is closed: Poppler and the standard
library, no new dependency.

---

### Phase 1 — CSV contract prototype

**Why before implementation.** The dataflow document is candid that model
compliance with the row format is unmeasured: *"How reliably do models follow the
'four fields, free text last, never escape anything' rule in practice? The rule
is verifiable on data; model compliance with it is not yet known and should be
measured on a prototype before the format is committed to."*

**Work.**

1. Take five to eight units from Phase 0, spanning a keyed room, a stat block, a
   random table, and a rules section.
2. Hand-assemble one pack: `README.md`, `prompt.md`, `schema.md`, `units.csv`,
   `units/*.txt`.
3. Run it through the manual exchange path.
4. Write a throwaway parser: `line.split(",", 3)`, vocabulary check on the first
   three fields, JSON parse on the fourth where present.

**Gate.** Every row splits into exactly four fields. The first three fields stay
inside the controlled vocabulary. Embedded JSON parses. Every packed unit appears
exactly once with a `#unit` marker. Measured across at least two independent
responses to the same pack.

**If it fails.** The failure mode determines the response. Occasional malformed
rows are acceptable — Stage 6 rejects and retries per unit, which is the designed
behavior. Systematic escaping, wrapping in JSON, or column drift means the format
needs revision before any code depends on it.

**Also decide here:** whether the predicate vocabulary is closed or open. It is
listed as an open question in the dataflow document and Stage 6 validation cannot
be written without an answer.

**Deliverable.** A frozen `schema.md` — the predicate vocabulary, the row types,
the visibility values — and measured compliance figures.

---

### Phase 2 — The front end

Only now is there enough evidence to write production code.

**New modules.**

| Module | Stage | Replaces |
|---|---|---|
| `segmentation.py` | 2 | nothing |
| `classification.py` | 3 | `routing.py` |
| `facts.py` | 5, 6 | the content half of `contracts.py` |

**Modified.**

- `preparation.py` — add `pdftotext -bbox-layout` alongside the existing
  `-layout` call, keep the source identity record, thumbnails, map renders, and
  atomic publish. **Add the explicit no-text-layer failure** required by Stage 1;
  there is currently no such check, and `_split_pages` will happily emit blank
  pages.
- `packs.py` — keep `deterministic_zip`, the manifest with pack hashes, the
  README and template scaffolding. Rekey partitioning from page runs to unit
  lists. Discard `_content_prompt` entirely (~150 lines).
- `contracts.py` — delete the record-shape validators: `_validate_place_fields`,
  `_validate_actor_fields`, `_validate_situation_fields`, `_validate_activation`,
  `_validate_repeat`, `_validate_possible_effects`,
  `validate_content_task_coverage`, and the field-vocabulary constants that
  support them. Roughly 800 of 1,066 lines. Keep `validate_source`,
  `validate_pages`, `validate_pack_manifest`, `validate_review`, and the schema
  constants.
- `evidence.py` — delete `_content_observations` and the content branch of
  `ingest_responses`; the new fact ingest writes the same observation shape.
  Keep `validate_map_response` unchanged — map evidence does not travel the CSV
  path.

**Deleted.** `routing.py`, and the routing round trip with it.

**Gate.** A PDF goes in, and validated facts land in the durable store with unit
IDs and page citations attached, with no model call beyond Stage 5. Stages 7–12
are not wired up yet.

---

### Phase 3 — The compiler

This is the load-bearing bet. The dataflow document names it as such: Stage 10
does in code what the model used to do implicitly, and *"Do compiled cards read
acceptably?"* is listed as needing a side-by-side prototype.

**Work.** Write `compilation.py` mapping facts onto `operational-module/v3`
record fields, targeting the existing canonical schema so `rendering.py`,
`operations.py`, `topology.py`, and `scene.py` need no changes.

`assembly.py` needs one: `canonical_module` currently wires reconciled records
straight into the module, because under the old design the model's records were
already card-shaped. Compilation is inserted between `apply_review` and
`canonical_module`. The assembly logic itself is untouched.

Start with the three or four keyed rooms most heavily used in the recovered
baseline, not with breadth.

**Gate.** Compile those rooms and diff the resulting place, situation, and
procedure cards field by field against the same records in the recovered
`module.json`. The compiled cards must be *at least as good* — no lost mechanics,
no lost numbers, no lost page citations.

**Watch specifically for flattening.** In the recovered build,
`location.hidden`, `location.triggers`, and `situation.activation` are worded
differently because they answer different questions — what players cannot see,
what starts the trap, what the activation condition is. Compiling all three from
one fact risks making them read identically. That is the specific failure this
gate exists to catch.

**If it fails.** The fix is a richer fact schema — separate predicates where one
was assumed sufficient — not per-card special cases in the compiler. If it fails
broadly, the shared-fact premise itself is in question and Phase 4 should not
start.

**Scope note.** Of the 613 records in the baseline, 393 are only `title` + `text`
and compile trivially. The compiler's hard surface is the remaining ~220
structured records, across 59 distinct `(record_type, field)` pairs.

---

### Phase 4 — Identity, reconciliation, review

**`reconciliation.py` — a rename, not a rewrite.** An earlier revision of this
plan said `reconcile_records` "regroups on `(entity, predicate)`". It does not
need to. Because the fact ingest emits **one observation per (entity, unit)**
with `fields` keyed by predicate — see Contract C in
[architecture-new-implementation.md](architecture-new-implementation.md) — the
existing grouping by `concept_id` over `fields` is already the required
behaviour. It retains every value with its pack, pages, and confidence, and never
picks a winner. The only change is `record_type` → `entity_kind`.

`reconcile_topology` is unchanged. Stage 8's requirement that map-asserted and
text-asserted passages reconcile as ordinary observations falls out of the
existing edge grouping.

**`identity.py` — largest change in this phase.** `_default_base` derives
canonical IDs from record *titles* (`identity._default_base`); facts have entity
*names*. `_descriptor_table`, `_default_base`, and the collision-suffix logic all
need rework. What survives: `normalize_identity_text`, `identity_slug`,
`keyed_area`, `module_slug`, alias resolution, and duplicate-candidate detection.

**Pin the ID shape with a test before touching the module.** The entity named
`1 BOWLS` should still canonicalize to
`place.module-lair-of-the-lamb.1-bowls`. No campaign depends on that any more,
but Phase 3's baseline diff does — matching IDs are what make the comparison
mechanical instead of manual.

**`review.py` — mechanism survives, identities change.** Conflicts become
per-fact rather than per-field. `validate_review`, `release_gate`, and
`cli.render_codex_task` (360 lines) keep their structure. Because the old
overlay was deleted, there is nothing to migrate — the new overlay is authored
fresh against fact identities.

**Coverage — genuine redesign.** `coverage.build_coverage` walks routing rows and
keys on `(pdf_page, task)`, raising when two packs cover the same pair. Unit
extraction breaks that contract. Rewrite it to key on `(unit_id, concern)`.

**Preserve the page-completeness invariant.** The current implementation asserts
that every physical page is accounted for, and the release gate depends on total
coverage. Units carry their pages, so the same guarantee still holds: every
physical page must be covered by some unit, or explicitly excluded as a cover,
divider, blank, or non-operational illustration. Keep that assertion — it is what
makes a false negative in segmentation detectable, and Stage 3's "uncertain units
are labelled broadly, never excluded" has no teeth without it.

---

### Phase 5 — Tests

Of 6,301 test lines, **5,085 are coupled to the record schema**: `test_v1.py`
(2,369), `test_operational_actors.py` (1,379), `test_operational_places.py`
(610), and `test_identity.py` (727). The first three build synthetic
`module-content-evidence/v3` responses and drive the CLI end to end; the fourth
imports `CONTENT_SCHEMA` and `ROUTING_SCHEMA` directly.

**The fixtures die; the assertions survive.** What those tests check — rendered
card sections, visibility separation, release-gate behavior, scene bundle
boundaries, campaign binding — remains exactly as valid under the fact model.
Only the input shape changes, from record JSON to CSV fact rows.

Re-author fixtures per phase rather than in one pass, so each phase lands with
its own coverage. `test_scene_loading.py` and `test_campaign_binding.py` (501
lines combined) reference no content schema at all and should pass untouched —
treat them as the regression signal that the back end really did survive.

`scripts/poc.py` and `test_poc.py` are historical and isolated. Leave them or
delete them; they are not on the path.

---

### Phase 6 — Rebuild and rebind

Run the full pipeline on *Lair of the Lamb* and publish `module/`.

**Gate, in order:**

1. `python3 scripts/validate_repo.py` still reports zero errors.
2. `GENERATED_OUTPUT.json` declares `play_contract: module-play/v1` and
   `verification: verified`.
3. `module/index.json` contains `place.module-lair-of-the-lamb.1-bowls`.
4. `status --scene place.module-lair-of-the-lamb.1-bowls` resolves.
5. Record counts and card sections are compared against the recovered baseline
   one final time, whole-module rather than the handful of rooms in Phase 3.

Binding a campaign to the result is a separate decision and not part of this
gate. The repository is in `preparation`, and nothing needs to bind for the
rebuild to be judged complete.

Only then update `DEVELOPER.md`, `USER_GUIDE.md`, `CODEX_WORKFLOW.md`, and
`IDENTITY.md`, which all describe the page/record pipeline throughout.

---

## Component disposition

| Component | Lines | Disposition |
|---|---:|---|
| `preparation.py` | 238 | Modified — bbox extraction, no-text-layer failure |
| `routing.py` | 79 | **Deleted** |
| `packs.py` | 675 | Modified — rekeyed, prompt discarded |
| `contracts.py` | 1066 | ~800 deleted, remainder kept |
| `evidence.py` | 480 | Content path deleted, map path kept |
| `identity.py` | 824 | Substantially rewritten, concepts kept |
| `reconciliation.py` | 277 | **Near-unchanged** — one rename |
| `review.py` | 301 | Identities change, mechanism kept |
| `coverage.py` | 108 | Rewritten, invariant preserved |
| `operations.py` | 326 | **Unchanged** |
| `topology.py` | 296 | **Unchanged** |
| `rendering.py` | 1251 | **Unchanged** |
| `assembly.py` | 235 | One wiring change — compiler inserted before it |
| `scene.py` | 196 | **Unchanged** |
| `util.py` | 132 | **Unchanged** |
| `cli.py` | 1425 | State machine reworked, `render_codex_task` kept |
| `segmentation.py` | — | **New** |
| `classification.py` | — | **New** |
| `facts.py` | — | **New** |
| `compilation.py` | — | **New** |

Roughly 2,300 lines unchanged, 3,600 modified, 1,000 deleted, 800–1,200 new.

## Risks, in order of expected cost

1. **Segmentation does not generalize past the source it was demonstrated on.**
   Largely closed by Phase 0. Four of the five sources segment: Lair of the Lamb
   (324 units, 101 keyed), Winter's Daughter (122), Falkrest Abbey (177) and
   Doom of the Savage Kings (49). The fifth, *The Lost City*, is **deferred** --
   its text layer is damaged rather than its layout unusual, which is a Stage 1
   problem. See "Deferred: The Lost City" in
   [architecture-new-implementation.md](architecture-new-implementation.md).
   What remains is whether unit *boundaries* are right, which is T0.5's review
   gate and not something the implementer can self-certify.
2. **Compilation flattens the cards.** The shared-fact premise is the reason for
   the whole redesign, and Phase 3 is the only place it gets tested. The
   recovered baseline makes the test cheap; skipping it makes the failure
   expensive and late.
3. **Identity does not reproduce the baseline's place IDs.** Now a Phase 3
   problem rather than a Phase 6 one: divergent IDs do not break a campaign any
   more, they just turn the baseline diff into manual work. Cheap to prevent with
   one test written before the rework.
4. **The compiler reads the baseline instead of being compared against it.**
   Now that the baseline is committed in-tree, contamination is the live risk
   rather than loss. A compiler that can see the old cards can copy them, and
   Phase 3's gate would pass while proving nothing.
5. **Deleting model routing raises the human queue.** Stage 3 replaces one cheap
   model round trip per module with deterministic classification plus a queue
   that is asserted to be small. If Phase 0 is marginal, this queue is where the
   cost appears.
6. **Test fixture re-authoring.** ~5,100 lines. Mechanical and voluminous rather
   than difficult, but it is real time and it is easy to underestimate.

## Carried open questions

**The register lives in
[architecture-new-implementation.md](architecture-new-implementation.md), in the
D-table**, where each question is bound to the task that closes it and carries
its answer once decided. Duplicating it here would drift — it already had, before
this note replaced it.

What belongs in *this* document is the reasoning behind where they sit:

**The topology questions (D-8, D-9, D-10) are deferred to Phase 4** because
`reconcile_topology` and `resolve_operational_topology` already answer several of
them in code. That existing answer should be read before it is replaced, and it
cannot be read usefully until facts flow through reconciliation.

**The vocabulary questions (D-4, D-5, D-6) sit in Phase 1** because Stage 6
validation cannot be written without them, and because they are cheap to settle
against two real model responses rather than by argument.

**D-11 — whether one fact-to-field mapping suffices across rulesets — cannot be
answered by this work at all.** Every phase here builds one module in one
ruleset. An earlier revision of this plan assigned it to Phase 3, which was
wrong: compiling *Lair of the Lamb* well says nothing about portability. It needs
a second module from a different system, and that is follow-on work. Until then
the compiler's mapping is per-system by assumption.
