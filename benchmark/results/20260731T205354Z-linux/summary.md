Smoke run only: use this small contract check for iteration; run the quick suite for formal triage and the full suite for the complete evaluation.

# Local model benchmark summary

Machine: `linux`  Suite requested: `smoke`  Prompt SHA-256: `57671a04b87ac7c0a596dca0a403b2d774d632d6ca92041c1b3963f1d916f503`

## Technical environment

- OS: `Linux 7.1.5-1-cachyos`; architecture: `x86_64`
- Python: `3.14.6`; logical CPUs: `20`; physical RAM: `30.8 GiB`
- GPU: `NVIDIA GeForce RTX 5070 Laptop GPU`
- Ollama: `ollama version is 0.32.5` at `http://127.0.0.1:11434`

The first-generation and final-generation measurements are retained in `results.json`; every raw response is under `raw/`.

## Per-model result

| Model | Actual tag | Tier | S1 | S2 | S3 | Substance recall | Gen tok/s | Projected whole adventure |
|---|---|---|---|---|---|---:|---:|---:|
| `qwen3:8b` | `qwen3:8b` | tier1 | PASS | PASS | manual review required | 1.8% | 62.9 | 20.6m |
| `llama3.1:8b` | unavailable | tier1 | — | — | — | — | — | — |
| `granite3.3:8b` | unavailable | tier1 | — | — | — | — | — | — |
| `qwen2.5-coder:7b` | unavailable | tier1 | — | — | — | — | — | — |
| `mistral:7b` | unavailable | tier1 | — | — | — | — | — | — |

## Failure taxonomy

- `added_commentary`: 0 response/attempt occurrence(s)
- `escaped_quotes`: 0 response/attempt occurrence(s)
- `extra_fields`: 0 response/attempt occurrence(s)
- `invalid_json`: 0 response/attempt occurrence(s)
- `malformed_row`: 1 response/attempt occurrence(s)
- `structural_incomplete`: 1 response/attempt occurrence(s)
- `unknown_vocabulary`: 1 response/attempt occurrence(s)
- `wrapped_in_fence`: 0 response/attempt occurrence(s)
- `wrapped_in_json`: 0 response/attempt occurrence(s)
- `wrong_field_count`: 0 response/attempt occurrence(s)

## Prompt and scoring notes

All models received one shared prompt with temperature 0 and seed 0. The prompt is saved per fixture under `prompts/`; no model-specific examples or tuning are hidden in the runner.

S3 is a required human gate. The deterministic number/entity checks are only audit leads; they do not replace reading a sample against the source. S4 is reported as a lexical-semantic proxy against a strong reference, not as gold truth.

## Mac and Windows comparison

Run this command once per machine and compare the generated summaries or combine their `results.json` files with the `summary` command. Tier 2 is intentionally reported separately from the Tier 1 decision.

## S6

S6 was not completed in this run.
