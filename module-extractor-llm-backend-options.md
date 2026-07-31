# Module Extractor: LLM Backend Options

## Purpose

This document summarizes the options discussed for replacing the current
manual ChatGPT extraction workflow in `module-extractor` with an automated LLM
backend.

The existing extractor is deliberately model-independent: local Python code
prepares source material, creates bounded packs, validates returned JSON,
reconciles observations, and assembles the released module. Today, ChatGPT is
used manually for bounded extraction and Codex performs final semantic review.
The proposed change is to automate model calls without weakening the existing
validation and evidence contracts.

## Shape of the current workload

The active *Lair of the Lamb* example has:

- 54 source pages;
- one routing pass containing 54 thumbnails;
- 11 content packs;
- one map pack containing 18 map images;
- approximately 342 KB of packaged text;
- schema-constrained, potentially large JSON responses;
- a final source-based semantic and identity review.

The current map pack is about 13.4 MiB and contains 18 PNG images at
1700 by 2200 pixels. Although that is usually acceptable for a frontier online
model, it is a difficult visual-attention and output-completeness task,
especially for small local models.

The workload should be treated as several model roles rather than one generic
call:

1. page routing and classification;
2. bounded content extraction;
3. visual map/topology extraction;
4. regional and global reconciliation;
5. final semantic review.

## Available inference approaches

### Direct provider APIs

The strongest production option is to call provider APIs directly:

- OpenAI Responses API;
- Anthropic Messages API;
- Google Gemini Developer API;
- equivalent managed APIs through Azure, Amazon Bedrock, or Vertex AI.

Direct APIs provide predictable request/response formats, usage accounting,
concurrency, retry handling, and asynchronous batch processing. They are a
better extraction transport than interactive web applications or agent CLIs.

Estimated model cost for an adventure of the current size is normally below
USD 5 and often below USD 1 when economical models and batch processing are
used. Retries and agentic final review may increase that amount.

Representative estimates discussed were:

| Backend | Approximate cost per module |
| --- | ---: |
| Economical OpenAI model | USD 0.25–1 |
| Frontier OpenAI model | USD 1–4 |
| Claude Sonnet-class model | USD 1–4; batch about half |
| Gemini Flash-class model | USD 1–4; batch about half |
| Hosted open text model | USD 0.10–1 |

These are planning estimates, not guarantees. Image-token accounting, output
length, reasoning tokens, and retries differ by provider.

### Hosted open models

Providers such as Together, Groq, Fireworks, and similar services expose open
models at low per-token prices. OpenRouter can provide a common facade over
multiple commercial and open models.

These are useful for evaluation and inexpensive text-heavy extraction. Their
limitations must be checked per model and provider:

- vision availability;
- image and request-size limits;
- maximum output length;
- actual JSON Schema enforcement;
- model stability and deprecation policy;
- data retention and upstream provider selection.

An “OpenAI-compatible” endpoint generally means similar request syntax, not
identical capabilities or behavior.

### Local inference

Local inference can be exposed through:

- Ollama;
- llama.cpp server;
- vLLM;
- SGLang;
- MLX on Apple Silicon;
- LocalAI.

Ollama is a runtime and API, not a model. A model must still be selected and
benchmarked. Local inference has almost zero marginal model cost when hardware
already exists, but electricity, execution time, hardware cost, and additional
review must be considered.

The primary reasons to run locally are privacy, offline operation, independence
from providers, and experimentation. Avoiding a roughly USD 1 API bill is not
by itself a strong justification for buying expensive hardware.

### Codex CLI and Claude Code

Codex and Claude Code are valuable for final semantic review because they can
inspect repository files, run validators, examine cited source pages, repair
responses, and iterate until the release gate passes.

They are not the preferred transport for repetitive pack extraction. An agent
CLI adds filesystem context, tool use, permissions, additional reasoning turns,
less predictable cost, and terminal-output handling to a task that should be a
bounded multimodal request returning one JSON object.

Consumer subscriptions and API billing are separate:

- a ChatGPT subscription is not a pool of OpenAI API credits;
- a Claude.ai subscription is not a pool of Anthropic API credits.

Browser automation, response scraping, or unattended CLI use intended to turn
a consumer subscription into generic inference capacity would be fragile and
should not form the production architecture.

## Local hardware feasibility

### Laptop with an 8 GB GPU and 32 GB system RAM

Assuming an NVIDIA RTX 3060/4060/4070-class laptop GPU, the realistic sweet
spot is a quantized 7B–8B model.

Models likely to fit fully or nearly fully in GPU memory include:

- Qwen3-VL 4B or 8B;
- Gemma 3 4B;
- MiniCPM-V 8B;
- Ministral 3B or 8B;
- ordinary 7B–8B text models at Q4/Q5.

Qwen3-VL 8B is approximately 6.1 GB in its common Ollama package. It should fit,
but the remaining VRAM must also hold runtime buffers, image state, KV cache,
and the graphical desktop. Conservative context sizes are therefore advisable.

Quantized 12B–14B models can be partially offloaded into 32 GB system RAM, but
generation becomes significantly slower. A 30B model can technically be made
to run mostly from system RAM, but it is not operationally attractive for this
pipeline.

Approximate generation speeds:

| Configuration | Approximate generation rate |
| --- | ---: |
| 8B fully on laptop GPU | 25–60 tokens/s |
| 12B–14B partially offloaded | 7–20 tokens/s |
| 30B mostly in system RAM | 2–6 tokens/s |

A complete 54-page extraction with an 8B model was estimated at roughly
1–3 hours without major retries. A partially offloaded 12B–14B model may take
3–8 hours, and a 30B model could become an overnight or all-day job.

The limiting factor is more likely to be semantic quality than raw speed.
Eight-billion-parameter models may omit checklist entries, produce subtly
invalid nested records, conflate identities, miss map passages, or invent
references.

### MacBook Pro with 18 GB unified memory

The 18 GB MacBook is the more flexible local inference machine because model
weights and GPU execution share one memory pool. Its realistic sweet spot is
an 8B–14B quantized model, particularly a 12B vision model.

Likely practical:

- Qwen3-VL 8B;
- Gemma 3 12B Q4 or QAT;
- 12B–14B text models at Q4;
- smaller vision models with moderate context.

Borderline:

- aggressively quantized 20B-class models;
- some 24B models at very low precision and small context.

Not comfortable:

- Qwen3-VL 30B/32B;
- Gemma 3 27B at quality-preserving quantization;
- other 30B-class vision models.

macOS, the runtime, image tensors, and KV cache also consume unified memory.
A model file around 10–12 GB is a safer practical ceiling than trying to use
all 18 GB.

Approximate generation speeds:

| Model size | Approximate generation rate |
| --- | ---: |
| 4B | 25–50 tokens/s |
| 8B | 15–30 tokens/s |
| 12B | 9–20 tokens/s |
| 14B | 8–17 tokens/s |
| heavily compressed 20B | 4–10 tokens/s |

A complete extraction was estimated at roughly 1.5–4 hours with an 8B model or
2.5–6 hours with a 12B model, excluding extensive retries. Final local semantic
review could add several more hours.

### Realistic local model candidates

The initial benchmark candidates should be:

1. Qwen3-VL 8B on both machines;
2. Gemma 3 12B QAT/Q4 on the Mac;
3. optionally Ministral 8B/14B or MiniCPM-V 8B;
4. a strong 12B–14B text-only model for packs whose PDF text is already
   extracted deterministically.

Models in the 2B–4B range may be useful for cheap routing but are unlikely to
be trustworthy authoritative extractors. Models in the 30B–32B range do not
fit either machine comfortably. Extreme Q2 quantization merely to fit a larger
model may erase much of its quality advantage.

## Smaller packs and hierarchical map extraction

Splitting the large map pack is probably the highest-value change for local
inference and may improve cloud reliability as well.

Recommended map pipeline:

```text
18 map pages
  -> 18 single-page visual observations
  -> 4–6 regional reconciliation groups
  -> one global text-only topology consolidation
  -> deterministic validation and semantic review
```

### Per-page visual extraction

Each request should receive one rendered map page and record only evidence
visible there:

- nodes and labels;
- passages and independent passage facets;
- boundary connectors;
- references to other maps or keyed areas;
- uncertainties.

The per-page model should not guess global canonical identities or invisible
connections.

### Regional reconciliation

Group observations from two to five related pages, preferably based on dungeon
region, level, or explicit continuation rather than arbitrary byte size.
Regional reconciliation can normally operate on Stage 1 JSON and prepared
text; images need only be reattached to resolve ambiguity.

### Global consolidation

A stronger text model receives normalized regional topology rather than all
original images. It proposes canonical nodes, cross-region passages, aliases,
and unresolved uncertainties. Existing deterministic validation and the review
overlay remain authoritative.

### Boundary representation

Single-page extraction needs an explicit way to represent connections leaving
the visible sheet. A local passage can terminate at a `boundary` node such as
“stairs to Area 12.” Later reconciliation can match that boundary to a node on
another page without forcing the visual extractor to invent an unseen target.

### Smaller content packs

The current content limit of up to eight pages is easy for frontier context
windows but can produce overly complex output for an 8B–12B local model.

Suggested packing profiles:

| Profile | Content pages | Map pages |
| --- | ---: | ---: |
| Cloud frontier | 6–8 | 3–4 related pages |
| Cloud economical | 3–4 | 1–2 |
| Local 12B | 2–3 | 1 |
| Local 8B | 1–2 | 1 |

Packing should consider image count, resolution, text tokens, semantic tasks,
expected record count, expected output size, and narrative/map continuity—not
ZIP byte size alone.

Smaller packs increase duplicate observations. The extractor should preserve
those observations and reconcile them later rather than asking isolated page
extractors to guess global identities.

## Accessing commercial models

### OpenAI

For application use, create an OpenAI Platform project, configure billing,
issue a project-scoped API key, and call the Responses API. Image input and
Structured Outputs are relevant to this pipeline. Independent packs are good
candidates for the asynchronous Batch API.

Codex should remain an optional review operator rather than the bulk inference
transport.

### Anthropic

For application use, obtain an Anthropic Console API key and call the Messages
API. Claude models support image input, long context, prompt caching, and batch
processing. An economical model can process routine pages while a Sonnet-class
model handles difficult maps and review.

Claude Code should occupy the same optional review role as Codex.

### Google

The Gemini Developer API is the simplest developer route and supports document,
PDF, image, and batch workflows. Vertex AI is preferable when service accounts,
IAM, audit logs, regional processing, organizational quotas, and consolidated
cloud billing are required.

### Enterprise clouds

Amazon Bedrock, Google Vertex AI, Azure OpenAI/Azure AI Foundry, and related
platforms provide cloud-native identity and governance. They are appropriate
for organizational deployments but add configuration, provider-specific model
IDs, possible regional premiums, and capability differences relative to
first-party APIs.

## Credential and adapter design

Secrets must not be stored in repository configuration. Local development can
use environment variables or an operating-system secret store:

```text
OPENAI_API_KEY
ANTHROPIC_API_KEY
GEMINI_API_KEY
OPENROUTER_API_KEY
```

Organizational deployments should prefer project-scoped credentials, service
accounts, workload identity, spending limits, and narrowly scoped permissions.

Provider SDK types should not leak into extractor core logic. The extractor
should define one normalized multimodal request containing:

- request/pack ID;
- instructions;
- text parts;
- image paths;
- desired output schema;
- output and reasoning limits.

Provider adapters translate that request to OpenAI, Anthropic, Gemini,
OpenAI-compatible services, or Ollama. They return a normalized result
containing parsed content, provider/model identity, provider request ID, token
usage, timing, and error information.

Suggested model roles:

```text
routing_model
content_model
map_model
reconciliation_model
review_model
```

The generated response must still pass the current deterministic schema,
coverage, citation, identity, and release validators. Provider-side structured
output reduces syntax failures but does not replace semantic validation.

## Recommended implementation direction

1. Introduce a provider-neutral inference interface.
2. Add synchronous OpenAI and Ollama adapters first.
3. Add Anthropic as the next direct provider.
4. Split map extraction into single-page observations plus hierarchical
   reconciliation.
5. Add configurable packing profiles for local and cloud models.
6. Add provider batch execution once synchronous requests are validated.
7. Automatically retry only failed packs, escalating to a stronger model after
   repeated semantic or schema failures.
8. Keep Codex, Claude Code, or a frontier review workflow as the final review
   layer.
9. Benchmark local models in shadow mode before allowing them to provide
   release-authoritative evidence.

A practical initial hybrid would be:

```text
routine routing/content
  -> local Qwen3-VL 8B or Gemma 3 12B

dense maps and repeatedly rejected packs
  -> economical cloud vision model

regional/global consolidation
  -> strong text or multimodal cloud model

final semantic review
  -> Codex, Claude Code, frontier API model, or human reviewer
```

Because API inference is inexpensive for this workload, reliability,
repeatability, targeted retries, and semantic correctness are more important
than eliminating the final few dollars of inference cost.

## Proposed evaluation

Before selecting a default model, run each candidate against the same fixed
benchmark:

- the complete routing pack;
- one easy content pack;
- one record-heavy content pack;
- several representative single map pages;
- one regional topology reconciliation;
- one difficult identity/reconciliation case.

Measure:

- JSON/schema validation rate;
- page/task checklist completeness;
- citation correctness;
- unsupported claims;
- map node and passage recall;
- duplicate and identity behavior;
- output tokens and wall-clock time;
- retry count;
- corrections required during final semantic review.

The benchmark, rather than advertised context size or general model rankings,
should decide which model is suitable for each pipeline role.
