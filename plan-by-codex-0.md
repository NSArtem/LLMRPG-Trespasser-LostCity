# Implementation 0: establish the runtime output boundary

## Outcome

After this implementation, a complete clean extraction still works, but its
assembled output has the new runtime/audit boundary:

```text
module/
  MODULE.md
  index.md
  index.json
  cards/
    places/
    actors/
    situations/
    knowledge/
    procedures/
    reference/
  topology.yaml
  audit/
    module.json
    coverage.md
    conflicts-and-gaps.md
    review.md
  GENERATED_OUTPUT.json
```

This slice changes packaging and loading boundaries, not the depth of semantic
extraction. Existing record fields can be rendered into the new card
directories while later slices enrich them.

## Dependency

None. This is the first implementation slice.

## Clean-workspace rule

Use only synthetic source fixtures and artifacts created after this
implementation begins. Do not open, convert, copy, or preserve any existing
produced module workspace as an input or expected-output fixture.

Every end-to-end test must:

1. create a new temporary workspace;
2. prepare a synthetic source;
3. supply responses matching the currently authored contracts;
4. run every deterministic pipeline transition;
5. assemble output into an empty destination.

## Work

### 1. Declare the new assembled-output contract

- Introduce a new generated-output schema/version.
- Define runtime files separately from audit files.
- Define `MODULE.md`, `index.md`, and `index.json` as runtime entry points.
- Define `audit/module.json` as authoritative extraction/audit data.
- Keep the generated-output marker responsible for the complete tree.
- Do not implement compatibility readers or migrators for prior output.

### 2. Make rendering transactional

- Render the entire future `module/` into staging.
- Validate staged paths and contents.
- Publish only after every runtime and audit file succeeds.
- Preserve marker-gated overwrite safety.
- A failed render must leave the prior target untouched.

This safety behavior is tested with temporary generated targets, not an
existing adventure result.

### 3. Add a stable card envelope

Render every card with YAML front matter:

```yaml
---
id: actor.example.guard
type: actor
title: Guard
aliases: []
source_pages: [1]
verification: verified
references: []
---
```

For this slice, retain the current operational body fields under generated
Markdown headings. Type-specific bodies arrive in later slices.

Route records to:

- locations → `cards/places/`;
- actors → `cards/actors/`;
- situations → `cards/situations/`;
- knowledge → `cards/knowledge/`;
- procedures → `cards/procedures/`;
- rules, tables, items, spells, classes, effects →
  `cards/reference/`.

### 4. Produce small runtime indexes

`index.json` contains only:

- canonical record ID;
- type;
- title;
- card path;
- aliases;
- references;
- topology node when available.

It must not contain:

- observations;
- pack IDs;
- confidence histories;
- review operations;
- coverage details.

Generate `index.md` as a compact directory grouped by operational type.

### 5. Generate `MODULE.md`

Include:

- module ID and title;
- source-system metadata when known;
- verification status;
- short instructions for loading cards;
- a statement that `audit/` is not gameplay context;
- a statement that all module material is GM-only until later contracts
  identify player-safe sections.

### 6. Separate audit output

Render full extraction state and reports exclusively under `audit/`.
Source-page citations may remain in runtime front matter, but observation and
pack provenance do not.

### 7. Render canonical topology

Render the existing topology information to deterministic `topology.yaml`.
Do not yet infer place-to-node joins. Preserve every currently validated
topology facet without adding unsupported structure.

Use a deterministic, conservative YAML subset. If the implementation cannot
guarantee round-trip stability without a new dependency, use JSON-compatible
YAML and test byte-for-byte determinism.

### 8. Update documentation and prompts together

- Document the new paths.
- Tell runtime prompts to use only verified new-contract output.
- Tell prompts not to load `audit/`, the complete topology, or the PDF by
  default.
- If no verified new-contract module exists, report that state instead of
  attempting to interpret an older layout.
- Update root templates in the same change.

## Pipeline invariant

At the end of this slice:

- prepare works in a clean workspace;
- routing packs match their validators;
- focused packs match their validators;
- ingestion works;
- review works;
- assembly produces the new tree;
- validation accepts that tree;
- a second identical clean run is deterministic.

The cards may still be semantically shallow, but the pipeline is not broken
and the output boundary will not need another structural migration.

## Tests

- Unit-test front-matter escaping and deterministic ordering.
- Unit-test card-directory routing by record type.
- Unit-test compact index contents and prohibited audit fields.
- Unit-test `MODULE.md` metadata.
- Unit-test deterministic topology YAML.
- Inject a rendering failure and verify atomic publication.
- Run a complete synthetic adventure through the pipeline.
- Run repository validation and `git diff --check`.

## Exit criteria

- A clean synthetic source reaches assembled release output.
- Every output path matches the target layout.
- Runtime files contain no response-pack or observation histories.
- Audit data remains complete and source-traceable.
- The runtime index is bounded and materially smaller than audit JSON.
- No code path attempts to migrate or recognize prior produced output.
- All tests and repository validation pass.

## Handoff to implementation 1

Implementation 1 may rely on:

- the new card envelope;
- compact runtime indexes;
- audit/runtime separation;
- atomic whole-tree assembly;
- clean-workspace-only tests.
