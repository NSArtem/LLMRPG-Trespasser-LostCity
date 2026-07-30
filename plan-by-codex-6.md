# Implementation 6: hardening and clean pipeline qualification

## Outcome

After this implementation, the redesigned extractor and runtime model are
qualified by running the whole pipeline from original source material with no
reuse of any previous produced result.

## Dependency

[Implementation 5](plan-by-codex-5.md) is complete and green.

## Clean-workspace rule

This rule is the purpose of the slice:

- no existing `module/`;
- no existing `module-input/`;
- no existing exchange responses;
- no existing preparation cache;
- no existing review overlay;
- no copied aliases, canonical choices, or generated cards.

The source PDF and implementation repository are the only starting inputs.

Use the extractor's safe cleanup/replacement workflow. Resolve exact paths
before removal or isolation. Do not delete extractor source code or unrelated
campaign data.

## Work

### 1. Freeze the implemented contracts

Before starting the real-source run:

- all schema changes are complete;
- prompts and response templates match validators;
- rendering and release gates are complete;
- documentation matches commands;
- synthetic tests are green;
- no later phase is required to interpret the produced result.

### 2. Run preparation from the source

- Prepare the PDF in a clean workspace.
- Verify source identity and page count.
- Generate routing assets with the final prompt contract.
- Confirm no prior artifact was discovered or reused.

### 3. Run routing again

- Obtain a new routing response.
- Validate every physical page.
- Generate all focused packs from the new routing.
- Record fresh pack hashes.

### 4. Run focused extraction again

- Obtain a new response for every focused pack.
- Ingest only responses matching fresh pack hashes and current schemas.
- Reject missing, stale, or foreign responses.
- Complete coverage from the new run.

### 5. Run semantic review again

From newly prepared source text and images:

- resolve duplicate candidates;
- select canonical IDs;
- create only new-run aliases;
- resolve place-to-topology links;
- review visible, discoverable, and hidden sections;
- review situation activation and possible effects;
- review knowledge truth and acquisition;
- resolve genuine uncertainties.

Do not consult any discarded review overlay or generated card as evidence.

### 6. Assemble and validate

Generate:

- `MODULE.md`;
- compact indexes;
- all runtime cards;
- canonical topology;
- audit data and reports;
- generated-output markers.

Verify:

- atomic publication;
- release-gate success;
- no dangling references;
- no unresolved duplicate candidates;
- no audit data in runtime bundles;
- deterministic reassembly from the fresh durable inputs.

### 7. Qualify runtime scenes

Review a representative set:

- an initial approach;
- a normal keyed room;
- a hidden passage;
- an actor negotiation;
- a combat or hazard situation;
- a knowledge discovery;
- a repeat visit after an override;
- movement after a topology change.

For each scene, verify:

- immediate player-safe presentation;
- GM-only information remains hidden;
- required actors and situations load;
- exits match effective topology;
- acquired knowledge is correct;
- hypothetical effects remain hypothetical;
- total loaded context is bounded.

### 8. Test repeatability and failures

- Reassemble twice and compare deterministic files.
- Start a second clean synthetic run to confirm workspace isolation.
- Inject invalid responses, ambiguous aliases, missing topology joins, and
  render failures.
- Confirm the pipeline stops in a clear recoverable state.
- Confirm no partial output is published.

### 9. Final documentation audit

Verify that a new operator can:

1. start with a PDF;
2. complete routing and focused extraction;
3. perform required review;
4. assemble a verified module;
5. start a campaign at a canonical place;
6. load a bounded scene;
7. apply a checkpoint without mutating module baseline.

Remove documentation that describes obsolete produced layouts or migration.

## Pipeline invariant

Every stage consumes only artifacts produced earlier in this same clean run.
The final output must be reproducible from its new durable inputs, but those
inputs are never mixed with a different run.

Waiting for manual model responses or semantic review is a valid state.
Schema mismatch, stale hashes, and unresolved semantic blockers must fail
clearly without corrupting the workspace.

## Tests and validation

Run the complete suite:

```bash
python3 -m unittest discover -s module-extractor/tests -v
python3 scripts/validate_repo.py
git diff --check
```

Also run:

- clean synthetic end-to-end extraction;
- clean real-source end-to-end extraction;
- runtime scene resolution;
- campaign override and topology-overlay tests;
- deterministic output comparison;
- atomic failure tests.

## Exit criteria

- The whole pipeline succeeds from a source PDF and an empty extractor
  workspace.
- Every response and decision belongs to that clean run.
- No prior produced output contributed data or identity.
- Runtime cards are operational, bounded, and secret-safe.
- Places and topology are explicitly joined.
- Duplicate concepts are resolved or block release.
- Campaign changes overlay rather than mutate module baseline.
- Scene loading and checkpoint application work together.
- Audit evidence remains available outside runtime context.
- A repeated assembly is deterministic.
- Failure leaves no partial published module.
- Tests, repository validation, and human scene review pass.

## Completion

When these criteria pass, the redesign is complete. Future adventure modules
are created by rerunning the final pipeline from source, not by migrating old
produced directories.
