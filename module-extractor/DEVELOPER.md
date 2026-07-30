# Module Extractor developer reference

The [user guide](USER_GUIDE.md) is the sole authority for the human workflow.
This document describes contracts and implementation boundaries.

## Repository boundary

`module-extractor/` contains reusable source code, tests, and documentation
only. Runtime data is rooted beside it:

```text
_exchange/                 ignored manual handoff files
.module-extractor-cache/   ignored prepared PDF assets
module-input/              durable pipeline inputs
module/                    generated product
```

One Git branch owns one active module. The CLI therefore has no run selector or
source-hash directory. `run PDF` derives a slug from the filename and takes
optional `--slug` and `--title` overrides. A second preparation with the same
slug stages and replaces the active workspace. An existing different slug is
rejected.

The source SHA-256 remains a required identity field in every contract. It
guards against mixing source material without becoming a user-facing path.

## Pipeline

```text
PDF
  -> disposable prepared assets and routing ZIP
  -> durable routing response
  -> disposable focused ZIPs
  -> validated durable evidence responses
  -> reconciliation and review overlay
  -> canonical module and selective views
```

The CLI performs no model calls.

## CLI and state machine

The public parser exposes only:

```text
run [PDF] [--slug SLUG] [--title TITLE]
status [--json]
clean
advanced
```

`run PDF` prepares the source and stops after creating `routing.zip`. `run`
without a PDF detects and advances these states:

```text
not-started
waiting-for-routing
routing-response-ready
waiting-for-focused-responses
codex-review-required
release-ready
already-released
```

It executes all available deterministic transitions in one invocation:
routing acceptance and focusing, validation and partial ingestion, evidence
evaluation and Codex-task generation, then release assembly when the gate
passes. Waiting is successful workflow state, not an error. A rejected response
names the JSON, validation reason, ZIP to retry, and rerun command.

`status` is read-only and human-readable. `status --json` is the explicit
structured interface.

Technical commands are intentionally available only below `advanced`:

```text
advanced prepare
advanced focus
advanced ingest
advanced validate
advanced review
advanced assemble
```

They preserve stage-level debugging and testing without forming part of the
normal human workflow.

## Current contracts

| Artifact | Schema |
| --- | --- |
| page routing | `module-routing/v1` |
| content evidence | `module-content-evidence/v1` |
| map evidence | `module-map-evidence/v1` |
| coverage manifest | `module-coverage/v1` |
| review overlay | `module-review-overlay/v1` |
| canonical module | `operational-module/v1` |

Routing is page-total and multi-label. Content records retain stable IDs,
physical-page citations, confidence, references, and targeted uncertainties.
Topology passages keep kind, medium, elevation, barriers, features, conditions,
and traversal direction as independent facets. Kind and medium are open,
source-faithful strings. Elevation and direction use small controlled
vocabularies; unknown scalar values make no assertion.

## Durable input layout

```text
module-input/
  source.json
  routing.json
  packs.json
  responses/
    <pack-id>.json
  review.json
```

`packs.json` records pack kind, pages, size budget, pack SHA-256, response path,
and—after ingestion—the exact ingested response SHA-256. Content packs also
record the task union and page-by-page task matrix. Ingestion validates the
exchange archive before recording that response hash.

Assembly accepts either:

- a still-present archive whose bytes match `pack_sha256`; or
- an ingested response whose bytes match `ingested_response_sha256`.

This permits `_exchange/` and the preparation cache to be deleted without
making durable inputs impossible to validate or assemble.

## Exchange and cache

`_exchange/` is flat:

```text
routing.zip
routing.json
<pack-id>.zip
<pack-id>.json
codex-task.md
```

Every new archive contains human `README.md`, model `prompt.md`, and
`response-template.json`. Focused archives additionally contain `pack.json`,
page text, and relevant images.

Content packs combine every semantic task on at most eight contiguous pages.
They split near 30 KiB of prepared UTF-8 text once the current chunk contains
at least 15 KiB. Non-operational illustration pages may bridge content; covers,
dividers, and blanks break a run.

Map pages are ordered but need not be physically contiguous. A pack contains
at most 20 pages and 16 MiB of uncompressed PNG renders; one oversized render
is allowed alone. Pack ZIPs are deterministic for identical source assets,
routing, and code.

`advanced focus` generates a complete replacement workspace in staging. It
preserves an exchange or ingested response only when the new pack has the same
ID and exact ZIP hash and the response validates against the current contract.
Any pack-set change resets the review overlay. Generation failure leaves all
three runtime directories untouched.

Content responses include an exact page/task checklist. Each pair either names
compatible, page-citing record IDs or reports `not-found` with an explanation.
Map coverage is derived from node and passage citations.

`.module-extractor-cache/` contains the copied source PDF, layout text,
per-page text, thumbnails, and map renders. Nothing in it is a durable
correction or canonical output.

## Reconciliation and review

Cross-pack records remain source observations. Reconciliation groups them by
conceptual ID while retaining field values, packs, pages, confidence, and
uncertainties.

`module-input/review.json` is the only durable canonicalization layer. It may
alias IDs, select or author canonical values, and explicitly accept source
uncertainties. `_exchange/codex-task.md` is generated and inert. It includes
release-gate errors, coverage gaps, complete conflict candidates and provenance,
uncertainties, neighboring topology, cited source paths, and exact permitted
correction paths and commands.

The stable agent contract is [CODEX_WORKFLOW.md](CODEX_WORKFLOW.md). Codex may
correct an exchange response and re-ingest it, or write a source-cited review
operation. It must inspect cited source evidence before deciding, rerun `run`
until release or a genuine blocker, and never commit or clean. It must not
modify ingested evidence, coverage, or generated output. Local validation and
the release gate remain authoritative, and the human approves the resulting
Git diff.

## Canonical output

`module/module.json` is authoritative. The remaining files are deterministic
selective views:

```text
module/
  GENERATED_OUTPUT.json
  module.json
  index.json
  topology.json
  cards/
  reports/
```

Release assembly requires total coverage, valid required fields, references
and topology endpoints, and no unresolved conflicts or pending uncertainties.
Generated output replacement remains marker-gated and atomic.

## Prototype format

Pack and response formats are replaced in place while the extractor remains a
prototype. `advanced focus` regenerates disposable archives and invalidates
responses whose exact pack bytes changed. The production CLI does not carry
legacy-pack options or compatibility branches.

## Verification

```bash
python3 -m unittest discover -s module-extractor/tests -v
python3 scripts/validate_repo.py
git diff --check
```

The historical PoC has its own isolated regression tests.
