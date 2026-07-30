# Implementation 1: canonical identity and duplicate review

## Outcome

After this implementation, one source concept produces one canonical runtime
record. Alternate IDs found within a fresh extraction become aliases, and
unresolved duplicate candidates block release through the normal review
state.

## Dependency

[Implementation 0](plan-by-codex-0.md) is complete and green.

## Clean-workspace rule

Use new synthetic responses only. Do not import IDs, aliases, canonical
choices, or review decisions from any prior produced workspace.

Aliases in this implementation describe variants encountered inside the same
new run, not compatibility with discarded results.

## Work

### 1. Define canonical ID policy

Adopt one convention:

```text
place.<module>.<slug>
actor.<module>.<slug>
situation.<module>.<slug>
knowledge.<module>.<slug>
procedure.<module>.<slug>
item.<module>.<slug>
```

Document normalization for:

- case;
- punctuation;
- numbering;
- apostrophes;
- source-specific prefixes;
- map labels.

Do not make normalized titles globally unique; same-name entities may be
distinct.

### 2. Add duplicate-candidate analysis

Run candidate detection after ingestion and before final reconciliation.
Signals may include:

- same record type;
- normalized title;
- keyed-area number;
- topology label;
- overlapping source context;
- shared relationships;
- compatible operational fields.

Candidate detection proposes possible equivalence. It does not silently merge
ambiguous records.

### 3. Represent review decisions

Extend the review overlay with explicit operations:

- declare canonical ID;
- alias one extracted ID to another;
- declare two candidates distinct;
- select or compose canonical field values;
- record source pages and rationale.

Review operations must refer only to observations and evidence from the
current run.

### 4. Reconcile through aliases

- Resolve aliases before grouping observations.
- Merge complementary observations under the selected canonical ID.
- Rewrite references through the alias map.
- Detect alias cycles and ambiguous aliases.
- Preserve extracted observation IDs in audit data.
- Emit only canonical IDs in runtime cards and indexes.

### 5. Strengthen the release gate

Block release when:

- a high-confidence duplicate candidate is unresolved;
- an alias points to no canonical record;
- an alias cycle exists;
- rewritten references dangle;
- two canonical records claim the same unique keyed area without a reviewed
  distinction.

An unresolved review state is a valid pipeline state, not a crash. The review
queue must explain the decision and evidence needed.

### 6. Report identity decisions

Add audit reporting for:

- candidate groups;
- confirmed aliases;
- canonical IDs;
- rejected merges;
- merge rationale;
- source pages involved.

Keep this out of runtime indexes except for the final alias mapping.

## Pipeline invariant

The pipeline remains complete in both expected paths:

1. no duplicate candidates → assembly proceeds;
2. duplicate candidates → pipeline stops successfully at review-required,
   accepts current-run review operations, then assembles.

No half-merged output may be published.

## Tests

Create synthetic cases for:

- one entity described under hyphen and dot IDs;
- complementary introduction and keyed-area observations;
- two distinct guards with the same title;
- duplicate locations connected to one topology label;
- an alias cycle;
- a dangling rewritten reference;
- response packs supplied in different orders.

Verify:

- deterministic candidate generation;
- review queue stability;
- canonical output independent of response order;
- aliases present in runtime index;
- audit observations preserved;
- release blocks only when required.

Run the entire clean synthetic pipeline after all unit and integration tests.

## Exit criteria

- One canonical record is emitted for every reviewed concept.
- Alternate current-run IDs resolve through aliases.
- Distinct same-name entities remain distinct.
- Unresolved candidates cannot receive a clean release report.
- All canonical references resolve.
- Pack order does not change canonical output.
- No legacy output or prior review state is read.
- The complete clean pipeline and repository validation pass.

## Handoff to implementation 2

Implementation 2 may rely on stable canonical place IDs, alias rewriting, and
a release gate that refuses unresolved identity.
