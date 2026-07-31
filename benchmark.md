# Local model benchmark for fact extraction

**Status:** implemented in [`benchmark/benchmark.py`](benchmark/benchmark.py).
The harness, scorer, raw-response capture, and report generator are available;
the model runs and human contamination audit are intentionally environment
specific.

**Audience:** an implementing agent working on an Apple M3 Pro / 18 GB machine,
producing a harness that will also run on Windows with an 8 GB GPU and 32 GB
system RAM.

---

## The question this answers

[architecture-new-dataflow.md](architecture-new-dataflow.md) has exactly one
bulk model stage — Stage 5, where source text becomes CSV fact rows. It offers
three transports for that stage, and the local one is described as unproven:

> **Local model.** A local 8B-class model called per unit by the runner, with
> automatic validation and retry. Removes the human from the loop and makes
> per-unit calls practical, at the cost of setting up inference and of unproven
> quality on this material.

The document also flags the format itself as unmeasured:

> How reliably do models follow the "four fields, free text last, never escape
> anything" rule in practice? The rule is verifiable on data; model compliance
> with it is not yet known and should be measured on a prototype before the
> format is committed to.

**This benchmark answers both, for local models specifically.** Its output is a
decision: which local model, if any, is good enough to be Stage 5's default
transport — and if none is, that is a finding, not a failure.

**What it is not.** Not a general LLM leaderboard. Not a test of prose quality,
reasoning, or knowledge. A model that writes beautiful room descriptions and
cannot emit four comma-separated fields is useless here, and must score as such.

---

## Hardware targets

| | Mac | Windows |
|---|---|---|
| Compute | M3 Pro, 18 GB unified | 8 GB VRAM, 32 GB system RAM |
| Practical model ceiling | ~14B at q4 | ~8B at q4 in VRAM |
| Spill behaviour | degrades gradually (unified memory) | falls off a cliff to system RAM |

**The 8 GB VRAM machine is the binding constraint.** A q4 8B model is roughly
4.5–5 GB of weights and fits with room for context; a q4 14B is roughly 8–9 GB
and will not. Anything that spills to system RAM on Windows drops to a few
tokens per second and is not viable for per-unit calls across a whole adventure.

**Both machines must run an identical core set** so results are comparable.
Models that only fit the Mac are run as a separate tier and reported separately
— they inform "what if we relax the Windows constraint", not the main decision.

---

## Models

**Verify tags and sizes before running.** The list below reflects a knowledge
cutoff and the local-model landscape moves quickly. Run `ollama list` and check
current tags; substitute freely, but keep the *reasons* for inclusion, and
record any substitution in the results.

### Tier 1 — core set, must run on both machines

Every one of these should be ≤ ~5.5 GB at q4.

| Model | Why it is here |
|---|---|
| `qwen3:8b` | Strongest small-model instruction following in this class; the one most likely to hold a rigid output contract. |
| `llama3.1:8b` | The baseline everything else is measured against. Widely deployed, well understood, unremarkable in both directions. |
| `granite3.3:8b` | Explicitly trained for structured/enterprise output. Should be good at exactly this and bad at nothing else that matters here. |
| `qwen2.5-coder:7b` | Code models are drilled on rigid syntax. CSV-with-embedded-JSON is closer to code than to prose, and this tests whether that transfers. |
| `mistral:7b` | Older, small, fast. Establishes the floor — if it passes, the task is easy; if only it fails, the task is discriminating. |

### Tier 2 — Mac only, reported separately

| Model | Why |
|---|---|
| `qwen3:14b` | Tests whether the Windows constraint is what is costing accuracy. If Tier 1 fails and this passes, the answer is "buy VRAM", not "abandon local". |
| `phi4:14b` | Strong reasoning per parameter; a second opinion at the 14B tier. |
| `gemma3:12b` | Different lineage from the Qwen/Llama families; guards against the result being an artefact of one training tradition. |

### Explicitly out of scope

- **Reasoning models** (`deepseek-r1` and its distills, any `:thinking` variant).
  They emit long chains of thought before answering, which is pure cost for a
  task with a fixed output shape. If one is tried anyway, it must be scored on
  wall-clock like everything else, with the reasoning tokens counted.
- **Anything above 14B.** Neither machine runs it usefully.
- **Base (non-instruct) models.** They will not follow the contract.

---

## What to measure

Six suites. **The first three are pass/fail gates — a model failing any of them
is not viable regardless of how it scores elsewhere.** Report all six.

### S1 — Format compliance *(gate)*

The CSV contract, restated from the dataflow document:

1. Every row splits into exactly four fields on `line.split(",", 3)`.
2. Fields 1–3 contain no comma and come from the controlled vocabulary.
3. Field 4 is free text or JSON; it is never quoted or escaped.
4. Nothing outside the rows — no prose preamble, no markdown fence, no apology,
   no trailing commentary.

**Measure:** percentage of rows that parse; percentage of responses that are
*entirely* clean; and a breakdown of failure kinds — extra fields, escaped
quotes, wrapped in JSON, wrapped in a fence, added commentary.

**Why it gates:** stage 6 rejects a unit on any malformed row. A model at 95 %
row compliance fails most multi-row units.

### S2 — Structural completeness *(gate)*

Every fixture is one unit. The response must contain exactly one `#unit` marker
for it, every entity must be declared with `#entity` before any fact references
it, and every fact subject must resolve to a declared entity.

**Measure:** unit markers present / duplicated / missing; count of facts whose
subject was never declared.

### S3 — Contamination *(gate)*

The model must report what the text says and nothing else.

**Measure:** facts with no support in the source; invented entities; invented
numbers; rules knowledge imported from elsewhere (a model that "knows" D&D
filling in stats the text does not give). Requires reading a sample by hand —
budget for it, and do not automate it away.

**Why it gates:** a fabricated fact is worse than a missing one. Missing facts
show up as coverage gaps; fabrications reach the table as truth.

### S4 — Extraction recall

Against the ground truth in `benchmark/fixtures/ground-truth/`.

**Measure:** what fraction of the ground-truth records' substance appears in the
model's facts. Match on entity name and predicate meaning, not string equality
— the ground truth is record-shaped and the model emits fact-shaped output, so
exact comparison is impossible and attempting it will produce a meaningless
number.

**Read the caveat.** The ground truth was produced by a frontier model and
reviewed by a human. **It is a strong reference, not gold truth.** A local model
that finds something the reference missed is scoring correctly; note those cases
rather than counting them as errors.

### S5 — Throughput

**Measure:** tokens/second generation, wall-clock per fixture, and time-to-first-token.

**Then extrapolate:** the full *Lair of the Lamb* is 54 pages ≈ 150 KB of text.
Report projected wall-clock for a whole adventure at the measured rate. **This
is the number that decides whether the local path is practical at all** — a
model at 100 % compliance and 3 tokens/second is not a usable transport.

### S6 — Determinism and recovery

Two sub-tests:

- **Determinism.** Same fixture, same prompt, `temperature 0`, run twice.
  Byte-identical output or not. The pipeline promises determinism after
  extraction; knowing how much variance the model itself injects sets the floor.
- **Recovery.** Feed back one deliberately malformed response with the
  validator's error and ask for a corrected one. Does the retry converge? Stage
  6 retries per unit, so a model that cannot self-correct doubles its own cost.

---

## Data

**Already committed to this branch — do not regenerate it.**

```text
benchmark/fixtures/
  manifest.json            suite membership, expected counts, provenance
  source/p<NN>.txt         source text, one file per page
  ground-truth/p<NN>.json  the records the reference build produced from it
```

Nine fixtures drawn from *Lair of the Lamb*, extracted with
`pdftotext -bbox-layout` and split into columns at word level. The PDF itself is
**not** in the repository and is not needed.

| Fixture | Suite | Bytes | Records | Material |
|---|---|---:|---:|---|
| `p16` | quick | 959 | 8 | actors and knowledge — the hook, NPCs |
| `p21` | quick | 1 170 | 20 | keyed rooms plus a dense item list |
| `p31` | quick | 1 524 | 9 | keyed room with a trap mechanism, sub-areas, a procedure |
| `p09` | full | 2 564 | 5 | rules prose and tables |
| `p13` | full | 3 147 | 4 | random encounter tables |
| `p28` | full | 1 618 | 13 | actors, effects, tables |
| `p41` | full | 2 124 | 37 | **density stress test** — most records of any page |
| `p46` | full | 1 647 | 14 | spells and effects |
| `p49` | full | 1 797 | 14 | character classes |

`p31` is the worked example in the dataflow document — the CRUSH HALLWAY, its
descending ceiling, three disguised trap doors, three flooded sub-areas, and four
ways to cross. If a model handles only one fixture well, this is the one to read
by hand: it is where nested mechanisms, hidden information, and structured
values all appear at once.

**More fixtures are available** if a suite proves undiscriminating. The
`lair-lamb` branch holds the complete build — `module-input/responses/*.json`
(all 613 records with page citations) and `module/cards/`. Source text for any
page can be regenerated from the PDF with the method above.

---

## Suites

### Quick — under 60 s per model

Fixtures `p16`, `p21`, `p31`. 3.6 KB in, 37 reference records.

For triage: does this model produce parseable rows at a usable speed? Runs S1,
S2, S5. **A model that fails the quick suite is not run against the full one.**

### Full — around 300 s per model

All nine fixtures. 16.5 KB in, 124 reference records. Adds S3, S4, S6, and the
S6 determinism pass means two generations for at least one fixture.

**Budget honestly.** At 25 tokens/second — a reasonable M3 Pro expectation for a
q4 8B — 300 seconds is roughly 7 500 output tokens across ten-plus generations.
If the suite overruns on the slowest Tier 1 model, cut fixtures rather than
silently letting runs take fifteen minutes. Record what was cut.

---

## Reporting

One machine-readable results file plus one human summary. The summary must open
with a **recommendation**, not a table: which model to use, whether local
extraction is viable at all, and what the deciding evidence was.

Required in the summary:

- Per model: the three gates as pass/fail, then recall, throughput, projected
  whole-adventure wall-clock.
- **The failure taxonomy.** *How* models break the format matters more than the
  percentage. If every model wraps output in a markdown fence, that is a
  one-line fix in ingest, not a reason to reject them. If they invent facts,
  nothing downstream can save it.
- **Any prompt engineering that was required**, stated plainly. If a model only
  complies after three examples in the prompt, that is a real cost and belongs in
  the result rather than hidden inside a working prompt.
- Mac and Windows numbers side by side for Tier 1, with Tier 2 reported apart.

---

## Constraints

- **Do not change the CSV contract to make models pass.** The contract is
  specified in the dataflow document, which this benchmark serves. If it is
  genuinely unworkable, that is a finding to report — the most valuable one
  available — not something to fix locally.
- **Do not tune per model beyond a documented shared prompt.** One prompt for
  everything, or a stated per-model variant with its cost recorded. A benchmark
  where each model gets a bespoke prompt measures the prompt author, not the
  model.
- **Do not commit model weights or `ollama` cache.** Results, prompts, harness
  code, and raw responses are welcome; gigabytes of GGUF are not.
- **Keep raw responses.** Every generation, verbatim, alongside the scores. The
  failure taxonomy cannot be rebuilt later from aggregate numbers, and someone
  will want to re-score with a different rubric.
- **The harness must run on both machines from one codebase.** Standard library
  plus `ollama` only, consistent with the extractor's own no-dependency rule.

---

## Definition of done

1. Quick suite runs all five Tier 1 models on both machines.
2. Full suite runs every model that passed quick.
3. Raw responses committed.
4. A summary opening with a recommendation, whichever way it points.

**"No local model is viable yet" is a complete and useful answer.** It closes the
transport question in the dataflow document and moves the default to the cloud
API path. Do not manufacture a winner.

## Implementation

The standard-library harness talks to Ollama over its local HTTP API and keeps
the model boundary identical on Mac and Windows. It provides:

- `inventory` to record installed tags, sizes, parameter counts, and
  quantization;
- `run` for the quick/full suites, per-fixture validation, one documented retry,
  S1–S6 measurements, prompts, and verbatim raw responses;
- `score` to re-score captured responses after a human S3 audit or revised S4
  review, without calling a model; and
- `summary` to render a recommendation and Mac/Windows comparison.

The runner first performs a model preflight and reports every requested tag as
`FOUND` or `UNAVAILABLE`. An unavailable model aborts the run by default;
`--skip-unavailable` is required to continue with the installed subset. Model
weights are never downloaded by the benchmark itself.

Machine identity is automatic: Mac and Windows are detected from the host, with
no machine override flag. Each result also records best-effort technical
metadata—OS, architecture, Python, logical CPU count, physical RAM, detected
GPU information, Ollama CLI version, and the Ollama URL.

The shared prompt explicitly separates ordinary fact rows from structural
`#option` rows, lists valid option slots, and forbids numeric slots. A rejected
response receives the validator errors plus a concrete corrected-row example
on the shared retry. This prompt and retry policy are applied uniformly to all
models.

During a run, the terminal shows a timestamped live progress bar for each model
and suite, including fixture count, attempt number, elapsed time, and streaming
generation heartbeats. Raw responses and prompts are written as they are
produced; a manually interrupted run may therefore contain raw artifacts
without a completed `results.json`.

Typical commands are:

```bash
python3 benchmark/benchmark.py inventory
python3 benchmark/benchmark.py run --suite quick
python3 benchmark/benchmark.py run --suite full --skip-unavailable
python3 benchmark/benchmark.py score benchmark/results/<run-id> --audit audit.json
```

See [`benchmark/README.md`](benchmark/README.md) for the complete command
reference. No benchmark winner is claimed until actual local runs and the
required S3 hand audit have been completed.
