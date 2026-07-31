Smoke run only: use this small contract check for iteration; run the quick suite for formal triage and the full suite for the complete evaluation.

# Local model benchmark summary

Machine: `mac`  Suite requested: `smoke`  Prompt SHA-256: `57671a04b87ac7c0a596dca0a403b2d774d632d6ca92041c1b3963f1d916f503`

## Technical environment

- OS: `Darwin 24.6.0`; architecture: `arm64`
- Python: `3.14.6`; logical CPUs: `11`; physical RAM: `18.0 GiB`
- GPU: `Apple M3 Pro`
- Ollama: `ollama version is 0.32.5` at `http://127.0.0.1:11434`

The first-generation and final-generation measurements are retained in `results.json`; every raw response is under `raw/`.

## Per-model result

| Model | Actual tag | Tier | S1 | S2 | S3 | Substance recall | Gen tok/s | Projected whole adventure |
|---|---|---|---|---|---|---:|---:|---:|
| `qwen3:14b` | `qwen3:14b` | tier2 | FAIL | FAIL | manual review required | 20.0% | 14.1 | 80.4m |
| `phi4:14b` | `phi4:14b` | tier2 | FAIL | FAIL | manual review required | 3.6% | 14.0 | 76.5m |
| `gemma3:12b` | `gemma3:12b` | tier2 | FAIL | FAIL | manual review required | 9.1% | 15.6 | 74.5m |

## Failure taxonomy

- `added_commentary`: 2 response/attempt occurrence(s)
- `escaped_quotes`: 2 response/attempt occurrence(s)
- `extra_fields`: 0 response/attempt occurrence(s)
- `invalid_json`: 3 response/attempt occurrence(s)
- `malformed_row`: 6 response/attempt occurrence(s)
- `structural_incomplete`: 6 response/attempt occurrence(s)
- `unknown_vocabulary`: 5 response/attempt occurrence(s)
- `wrapped_in_fence`: 2 response/attempt occurrence(s)
- `wrapped_in_json`: 0 response/attempt occurrence(s)
- `wrong_field_count`: 0 response/attempt occurrence(s)

## Prompt and scoring notes

All models received one shared prompt with temperature 0 and seed 0. The prompt is saved per fixture under `prompts/`; no model-specific examples or tuning are hidden in the runner.

S3 is a required human gate. The deterministic number/entity checks are only audit leads; they do not replace reading a sample against the source. S4 is reported as a lexical-semantic proxy against a strong reference, not as gold truth.

## Mac and Windows comparison

Run this command once per machine and compare the generated summaries or combine their `results.json` files with the `summary` command. Tier 2 is intentionally reported separately from the Tier 1 decision.

## S6

S6 was not completed in this run.
