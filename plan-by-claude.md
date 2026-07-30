# Plan: making `module/` usable at runtime

Derived from `review-by-claude.md` (see also `review-by-codex.md`). This turns the
findings into ordered work with concrete file targets, acceptance criteria, and an honest
split between work that costs model calls and work that does not.

## Guiding constraints

From `DOCUMENT_EXTRACTION_LESSONS.md`: the model is a bounded semantic transformer; every
mechanical operation stays local. This plan holds to that — no phase asks a model to
manage repository state, and each phase's output is verifiable by a local command.

Two facts shape the sequencing:

- **Re-extraction is cheap here.** The whole adventure is 5 packs
  (`module-input/responses/content.001–004.json`, `map.v1.001.json`). Deepening the field
  contract costs 5 model calls, not a rebuild. This de-risks the expensive-looking phase.
- **The merge mechanism already exists and is unused.** `review.json.aliases` is empty,
  but `review.py:26` (`canonicalize_evidence_aliases`) rewrites `concept_id` *before*
  reconciliation, so an alias makes two records genuinely merge — observations pool, and
  real disagreements surface as conflicts. Most of Phase 1 is data entry against working
  code.

## Cost and dependency overview

| Phase | Work | Model calls | Blocks |
| --- | --- | --- | --- |
| 0 | Settle three decisions | — | 1, 2, 3 |
| 1 | Reconcile identity via `review.json` | none | 3 |
| 2 | Deepen field contracts + re-extract | 5 | 3 |
| 3 | Rewrite the renderer | none | 4 |
| 4 | Wire into prompts and campaign files | none | — |
| 5 | Gates and tests | none | — |

Phases 1, 2 and 4 are independent of each other and can run in parallel. Phase 4 delivers
value even if 1–3 slip: it is what makes `module/` visible to the GM at all.

---

## Phase 0 — Decisions to settle first

Three choices change downstream work and cannot be defaulted safely.

**0.1 Card language.** Module cards are English; every campaign file is Russian. If
`## First impression` must be narratable verbatim, extraction must produce Russian — a
change to the *pack prompt*, not the renderer, and therefore a Phase 2 input. Cheaper
default: keep extraction source-faithful (English) and let the GM translate at narration
time. Decide before Phase 2 or pay for extraction twice.

**0.2 Canonical ID namespace.** Three schemes exist today (127 `<type>-<slug>`, 75
`<type>.<slug>`, 54 `winters-daughter.<type>.<slug>`). Recommend
`<type>.<module-slug>.<area-or-name>` — dotted, module-qualified, so a campaign using two
modules cannot collide, and so `place.winters-daughter.area-13` reads unambiguously in a
checkpoint package. Everything in Phase 1 keys on this.

**0.3 Whether topology nodes and place records share an ID.** Aliasing `area-13` →
`place.winters-daughter.area-13` unifies them with zero code change and permanently
solves the join. Cost: `apply_review` (`review.py:92`) dispatches `values` operations by
checking `record_by_id` before `node_by_id`, so once unified you can no longer author a
node's `labels`/`titles` through the review overlay. Given labels come from the map and
are already correct, that is an acceptable trade — but confirm it rather than discover it.

---

## Phase 1 — Reconcile identity (no code changes)

All work happens in `module-input/review.json`. Each alias entry needs four fields per
`contracts.py:547`: `alias`, `canonical_id`, `source_pages`, `rationale`.

**1.1 Merge duplicate concepts.** Exact type+title matching finds 19 groups over 39
records; that is a floor, since it misses same-entity-different-title cases such as
`actor-sir-chyde` / `actor-ghost-of-sir-chyde` /
`winters-daughter.actor.area-13-sir-chyde`. Work from the map instead: for each of the 19
topology nodes, list every record mentioning that area and decide which describe one
concept. The duplicates are complementary (page 19 prose vs page 29 map-derived), so merge
— do not alias-and-keep-both.

**1.2 Unify topology nodes with place records.** Per decision 0.3, alias each `area-N` to
its canonical place ID. `review.py:42` rewrites map node `concept_id` and passage
`from`/`to`, so passages follow automatically.

**1.3 Resolve the conflicts this surfaces.** Merging complementary records will produce
real field conflicts where page 19 and page 29 disagree. That is the system working: pick
canonical values through `review.values`, which `release_gate` (`review.py:145`) then
stops reporting as unresolved.

**Acceptance:** `python3 -m module_extractor advanced validate --profile release` passes;
`module/reports/conflicts-and-gaps.md` reports 0 *after* aliases exist rather than because
they don't; location record count drops from 52 toward ~19–25; `index.json.aliases` is
non-empty.

---

## Phase 2 — Deepen the field contracts

`contracts.py:62` currently requires `title`+`description` for a location, `title`+`role`
for an actor, `title`+`trigger` for a situation. That cannot express what a GM needs.

**2.1 Extend `REQUIRED_FIELDS`** to the operational shape:

| Type | Add |
| --- | --- |
| location | `first_impression`, `occupants`, `hazards`, `resources`, `gm_secrets` |
| actor | `goals`, `knowledge`, `reactions`, `mechanics` |
| situation | `activation`, `participants`, `decisions`, `outcomes`, `completion`, `repeat` |
| knowledge | `kind` (fact/clue/rumor), `truth_status`, `discoverable_at`, `acquisition`, `reveals` |
| procedure | `stop_when`, `reset_when` (keep `trigger`, `steps`) |

Add controlled enums for `kind`, `truth_status`, `repeat`, and `activation` — cheap to
validate locally, and they are the checkpoint format's own vocabulary
(`new_facts.kind: established|npc-claim|rumor|belief`,
`truth_status: confirmed|unverified|false|mixed`), so module IDs become usable directly as
`knowledge_changes.knowledge_ref`.

**2.2 Add a per-field secrecy signal.** Minimum viable: a `gm_secrets` field on every
record type, distinct from player-safe fields. A single file-level `knowledge_level`
cannot express a card that has both boxed text and a secret — and the ghost card has both.

**2.3 Update the pack prompt and re-extract.** Regenerate `content.001–004` against the
new contract. Keep `map.v1.001` — the topology facets are already good.

**Acceptance:** every record carries the new required fields; `validate --profile release`
passes; a spot-check of `place.winters-daughter.area-13` answers all four runtime
questions (see, contains, exits, hidden).

---

## Phase 3 — Rewrite the renderer

`rendering.py:22` (`_card`) is type-agnostic — it dumps `### <field>` for every key,
alphabetically. Replace with per-type templates.

**3.1 Emit YAML frontmatter** on every card: `id`, `type`, `title`, `topology_node`,
`source_pages`, and typed `refs:` (`situations`, `actors`, `knowledge`, `procedures`) —
the existing flat `references` list, grouped by type. Not a second mechanism; the same
data, typed.

**3.2 Join topology into place cards.** `rendering.py:155` already builds adjacency but
keys it `area-N` into `index.json` where nothing can reach it. Instead, emit per-place
`exits:` in frontmatter carrying the facets that already exist — `kind`, `barriers`,
`conditions`, `elevation`, `traversal_direction` — plus `initial_state` and a
per-exit `knowledge_level` so a concealed door is not narrated.

**3.3 Stable per-type body headings.** Place: First impression / Features / Occupants /
Triggers / Hazards / Resources / Exits / GM secrets. Situation: What the players perceive
/ Pressure and stakes / Likely approaches / Actor reactions / Consequences / Completion
conditions. One file per concept — do not adopt the heavy branch's card+YAML split
identity.

**3.4 Split audit from runtime.** Move observations, pack IDs, confidence, coverage and
review hashes to `module/audit/`. Keep `source_pages` on the card. Target: `index.json`
well under 20 KB, and nothing over ~50 KB in the paths a GM LLM might glob.

**3.5 Restructure the tree** to `cards/{places,actors,situations,knowledge,procedures,
reference}/`, plus `MODULE.md` (~2 KB: system, level range, premise, area list, how to
use) as the entry point.

**Acceptance:** `module/cards/places/*.md` is self-sufficient for running its room;
`module.json` no longer sits beside runtime files; `du -sh module` well below today's
2 MB in the runtime paths.

---

## Phase 4 — Wire into the runtime

The highest-value phase and the cheapest. Today `MANIFEST.md` never mentions `module/` and
`SETUP_AND_PROMPTS.md` §4 routes adventure content to the PDF, so the extracted module is
never opened.

**4.1 Add an ID column to `gm/module-overrides.md`.** Its table keys on free-text
«Объект / место» today, so "apply overrides" cannot be executed deterministically. Module
IDs make it a lookup.

**4.2 Adopt the topology overlay for route state.** Lift
`schemas/topology-overlay.schema.json` and `templates/campaign/topology-overlay.yaml` from
`feature/module-extractor`. It already speaks the checkpoint vocabulary — `operation` from
a closed set (`set_state`, `collapse`, `block_temporarily`, `reveal_secret`, …) with
`target`, `checkpoint_id: cp-NNNN`, `source_event: event-NNN`, `reason`,
`knowledge_subjects`. Keeps `module/` immutable while route state changes.

**4.3 Add the loading contract** to `MANIFEST.md` and `SETUP_AND_PROMPTS.md` §4:

1. Read `CURRENT.md` and active campaign files.
2. Resolve the scene's `module_ref` to a place card.
3. Load that place card.
4. Load its `refs` — active situations, present actors — and the knowledge and procedures
   those situations reference. Nothing else.
5. For movement use the card's `exits`; open `topology.yaml` only for multi-hop routes.
6. Apply `gm/module-overrides.md` and the topology overlay by module ID; the overlay wins
   over the card's `initial_state`.
7. Never narrate from `## GM secrets` or a `knowledge_level: gm-secret` exit.
8. Consult the PDF only for a missing detail, a suspected extraction error, or an audit.

**4.4 State the precedence** explicitly: `gm/module-overrides.md` + topology overlay →
`module/cards/**` → PDF. This demotes the PDF from default scene context to cold audit
source — the point of having extracted the module at all.

**4.5 Carry `module_ref` in campaign files.** Add it to `locations/location-template.md`
and `npcs/npc-template.md` frontmatter so step 2 resolves.

**Acceptance:** a cold-start play session loads a room from `module/` without opening the
PDF; the GM LLM can answer "is area 5 still as written?" by ID.

---

## Phase 5 — Gates and tests

**5.1 Extend `release_gate`** (`review.py:145`): fail on unmerged near-duplicates (same
type, high title similarity, no alias), on any place record without a `topology_node`, and
on any place whose `exits` are empty while topology shows passages.

**5.2 Extend `scripts/validate_repo.py`**: every `module_ref` in a campaign file resolves
to a module ID; every `gm/module-overrides.md` row has a resolvable ID; every topology
overlay `target` exists in the base graph.

**5.3 Add a fixture module** — the heavy branch's
`tests/fixtures/module-ingestion/dungeon/` is a good model, two rooms and one situation —
and assert the rendered card shape rather than the JSON.

---

## Non-goals

Explicitly out of scope, to avoid re-importing the heavy branch's costs:

- Separate identities for a situation's card and its graph entry (`situation_ref`).
- Mandatory geometry, measurements, and `verification` on every field.
- `generated/` SVG output. Mermaid is worth keeping — a compact text map is genuinely
  useful to a text model — but SVG is not.
- `active_situations` anywhere in `module/`. Which situations are active is campaign
  state; the module is an immutable baseline.
- Making `module/` writable during play. All change goes through overrides, the topology
  overlay, and checkpoints.

## Suggested order

Phase 0 → Phase 4 (independent, immediate value) → Phase 1 → Phase 2 → Phase 3 →
Phase 5. Phase 4 first is deliberate: until `module/` is in the loading contract, every
improvement to its shape is unobservable.
