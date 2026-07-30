# Codex module extraction workflow

Finish the active repository-local extraction. Do not commit or clean the
workspace.

1. Run `python3 module-extractor/cli.py run` to ingest available responses and
   assess the current state.
2. Read `_exchange/codex-task.md`. Before making any semantic decision, inspect
   every cited prepared source page, relevant map render, and candidate
   observation needed for that decision.
3. If ChatGPT extracted the source incorrectly, correct only the matching
   `_exchange/<pack-id>.json`. Never edit `module-input/responses/`, coverage
   data, or generated `module/` files.
4. Follow [IDENTITY.md](IDENTITY.md). Record canonical ID declarations,
   current-run aliases, distinct-candidate decisions, canonical values, and
   accepted source uncertainties only in `module-input/review.json`, with
   source pages and an evidence-based rationale. Do not accept an uncertainty
   or reject a merge merely to satisfy the release gate.
5. Rerun `python3 module-extractor/cli.py run` after corrections or decisions.
   Continue until release assembly succeeds or a genuine blocker remains.

Missing source, illegible evidence, contradictory source that cannot be
canonically resolved, and unsupported decisions are blockers. Report them
clearly; never invent evidence or weaken the gate.

The CLI owns ingestion, reconciliation, coverage, validation, and atomic
assembly. It may replace only extractor-marked `module/`. Leave `module/`,
`module-input/`, and all other changes uncommitted for human review.
