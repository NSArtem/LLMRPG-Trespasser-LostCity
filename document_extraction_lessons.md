# Lessons for LLM-Assisted Document Extraction

This document records an architectural lesson from the module-extractor proof
of concept. It is intended to guide future work on adventures, TTRPG rulebooks,
reference books, and other document-heavy sources.

## Central finding

An LLM is most useful as a bounded semantic transformer, not as the workflow
engine for document extraction.

Our earlier approach asked ChatGPT to do too much: discover files, run scripts,
manage repository state, decide what remained, package intermediate material,
validate coverage, and generate final files. That work consumed model context,
introduced fragile state, made failures hard to reproduce, and distracted the
model from the task it performed best: interpreting text and images.

The proof of concept was substantially simpler:

```text
source document
→ deterministic local preparation
→ small, explicit model task
→ structured evidence
→ deterministic local validation and assembly
```

The important change was not a better prompt. It was moving each kind of work
to the environment best suited to it.

## Division of responsibility

### Local tools should own mechanical work

Use ordinary programs for operations that are deterministic, inspectable, and
cheap to repeat:

- identify and hash source files;
- inspect PDF metadata and physical page counts;
- extract and split text;
- inventory embedded images;
- render pages at known resolutions;
- build contact sheets and focused input packs;
- partition work into bounded batches;
- name files and assign pack identities;
- check JSON syntax and required fields;
- validate page references, IDs, enums, and graph endpoints;
- detect missing or duplicate responses;
- assemble Markdown, YAML, indexes, and directory layouts;
- measure timings and preserve reproducible artifacts.

These operations should not consume model context or depend on the model
remembering workflow state. If an operation can be expressed as a reliable
program with an objective result, it usually belongs locally.

### The LLM should own semantic work

Delegate tasks that require interpretation rather than orchestration:

- decide whether a page contains a map, table, illustration, or prose;
- read visible labels and spatial relationships;
- turn source prose into concise operational paraphrases;
- identify actors, places, procedures, situations, rules, and knowledge;
- distinguish explicit statements from claims or uncertainty;
- relate information that is present within the supplied focused context;
- report ambiguity instead of inventing an answer.

Each model call should have a narrow input, a clear identity, a constrained
output contract, and no responsibility for the surrounding workflow.

## Why the orchestration-heavy approach was counterproductive

Asking ChatGPT to manage the entire extraction pipeline created several
avoidable problems:

1. **Context was spent on logistics.** File lists, progress reports, packaging
   instructions, repository layouts, and pending-work ledgers displaced source
   material and semantic reasoning.
2. **State was implicit and fragile.** It was difficult to know whether a page
   had been processed, whether an artifact matched the current source, or
   whether a retry duplicated earlier work.
3. **Mechanical output was inconsistent.** Naming, formatting, directory
   layout, and coverage checks are easier to enforce in code than through
   repeated prompting.
4. **Failures were expensive to replay.** A long conversational workflow could
   not be reproduced as reliably as a local command plus a saved JSON response.
5. **The model was asked to verify itself.** The same system generating content
   also tracked completion and judged validity, weakening the value of those
   checks.
6. **Large inputs reduced focus.** Sending broad source material encouraged
   omission and inference. Focused packs made the evidence boundary explicit.

The result was more agent activity without a corresponding improvement in the
quality of extracted evidence.

## Recommended architecture

Use a staged pipeline with deterministic boundaries:

```text
PDF or document set
│
├─ 1. Local preparation
│    metadata, hashes, text, images, thumbnails, signals
│
├─ 2. Semantic routing
│    model classifies pages or sections; favor recall
│
├─ 3. Local focusing
│    high-quality renders and relevant text in small packs
│
├─ 4. Semantic extraction
│    model returns source-cited evidence and uncertainties
│
└─ 5. Local assembly
     validate, normalize, render, index, and publish
```

The routing stage and extraction stage should remain separate. A cheap,
recall-first classification pass avoids sending every page at extraction
quality while allowing uncertain pages to continue. The focused extraction
stage can then use higher-resolution images and more specific instructions.

## Model-call contract

Every model input pack should contain:

- a source hash or other immutable source identity;
- a unique pack ID;
- the exact physical pages or sections in scope;
- only the source material needed for that task;
- a prompt defining what may and may not be inferred;
- a machine-readable response template;
- a requested downloadable output filename.

Every response should contain:

- the matching source identity and pack ID;
- stable object IDs;
- physical page or section references for each object;
- values drawn from controlled enums where appropriate;
- explicit, object-specific uncertainties;
- a small count summary that local code can check.

The model should not be asked to access the repository, run the pipeline,
package artifacts, maintain a work ledger, generate final module files, or
provide narrative progress reports. Its deliverable is the structured semantic
artifact.

## Determinism and validation

Local code should treat model output as untrusted evidence:

- reject invalid JSON;
- reject responses for the wrong source or pack;
- require exactly one response per expected pack;
- reject unknown and duplicate pack IDs;
- validate safe and unique object IDs;
- validate all physical source references;
- validate controlled values;
- reject graph edges whose endpoints do not exist;
- retain source-specific duplicate observations, consolidate only compatible
  variants, and expose conflicts rather than merging them heuristically;
- stage generated output before publication;
- refuse destructive overwrites by default.

The final files should be reproducible from the saved source identity, packs,
responses, and assembler version. A model retry should replace one bounded
evidence artifact, not require replaying an entire conversational process.

## Applying the lesson to TTRPG rulebooks

A future rulebook parser can use the same shape while changing the semantic
categories.

The routing stage might classify pages as:

- rules prose;
- character option;
- spell, item, creature, or ability;
- procedure or subsystem;
- table or chart;
- example of play;
- setting material;
- index, legal text, or other non-rule content;
- mixed or uncertain.

Focused extraction packs could then request category-specific evidence. For
example, a procedure pack might extract triggers, ordered steps, state,
exceptions, and cross-references, while a creature pack might extract traits,
actions, statistics, and source-defined variants.

The local assembler would own normalization, cross-reference resolution,
duplicate detection, indexes, presentation files, and coverage reporting. The
model would not need to know the repository layout or the state of other packs.

## Evaluation criteria

Evaluate the system rather than the apparent sophistication of the workflow:

- recall of relevant pages and objects;
- precision of source citations;
- rate of unsupported high-confidence claims;
- accuracy of visible map labels and connections;
- completeness of required fields;
- reproducibility of local artifacts;
- time and number of model calls;
- ease of retrying one failed unit;
- usefulness of the assembled output to a human reader.

A simpler workflow is better when it produces stronger evidence, faster replay,
and clearer failure boundaries.

## Practical rule

Before assigning a step to the model, ask:

> Does this step require semantic judgment, or can a local tool produce and
> verify the result deterministically?

If it is deterministic, keep it local. If it requires interpretation, give the
model the smallest sufficient source pack and require structured, source-cited
evidence in return.
