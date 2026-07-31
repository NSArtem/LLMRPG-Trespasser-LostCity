# Local model benchmark

`benchmark/benchmark.py` implements the benchmark specified in the repository
root's [`benchmark.md`](../benchmark.md). It uses only Python's standard
library and the local Ollama HTTP API.

Inspect installed tags and sizes before a run:

```bash
python3 benchmark/benchmark.py inventory
```

Run the Tier 1 quick suite, or the full suite (which runs quick first and only
continues with models that pass quick):

```bash
python3 benchmark/benchmark.py run --suite quick
python3 benchmark/benchmark.py run --suite full
```

Before testing, the runner reports every requested model as FOUND or
UNAVAILABLE. By default, any unavailable model aborts the run before testing
starts. To explicitly continue with only installed models, add:

```bash
python3 benchmark/benchmark.py run --suite quick \
  --skip-unavailable
```

The default model names are the names in the specification. If Ollama has a
substitute tag, record it explicitly:

```bash
python3 benchmark/benchmark.py run \
  --model-map qwen3:8b=qwen3:8b-instruct-q4_K_M
```

Each run writes `results.json`, `summary.md`, per-fixture prompts, and every
raw response under `raw/`. S3 is intentionally a human gate. Complete the
generated `contamination-audit.template.json`, then re-score without making
new model calls:

During a run, a terminal shows a live per-model/per-suite progress bar with
fixture count, current attempt, elapsed time, and streaming-generation
heartbeats. When output is redirected, the same updates are emitted as readable
line-oriented snapshots. The raw response is still preserved even if a later
fixture fails.

The runner auto-detects Mac or Windows and records that label. Each result also
contains best-effort technical metadata:
OS and architecture, Python version, logical CPU count, physical RAM, detected
GPU information, and Ollama CLI version.

```bash
python3 benchmark/benchmark.py score benchmark/results/<run-id> \
  --audit benchmark/results/<run-id>/contamination-audit.json
```

Compare the Mac and Windows result files side by side:

```bash
python3 benchmark/benchmark.py summary \
  benchmark/results/<mac-run>/results.json \
  benchmark/results/<windows-run>/results.json
```
