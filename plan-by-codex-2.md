# Implementation 2: operational places, topology, and scene loading

## Outcome

After this implementation, a canonical place card is the entry point for
running a scene. It contains structured visible, discoverable, and hidden
content, links explicitly to topology, presents derived exits, and resolves a
bounded context bundle.

## Dependency

[Implementation 1](plan-by-codex-1.md) is complete and green.

## Clean-workspace rule

Replace the prototype contract in place and rerun all synthetic extraction
steps. Do not add compatibility branches for prior response or output files.

## Work

### 1. Replace the place evidence contract

Update focused prompts, response templates, validators, reconciliation, and
tests together.

A place observation must support:

- title;
- first impression;
- visible contents;
- discoverable details with acquisition conditions;
- hidden GM information;
- triggers;
- hazards;
- resources;
- occupants or actor references;
- situation references;
- source pages and uncertainty.

Only source-supported fields are asserted. Optional absent material must not
be filled with invented defaults.

### 2. Add explicit place-to-topology linkage

Represent the canonical link as `topology_node`.

Automatic proposals may use keyed-area labels, but:

- ambiguous matches require review;
- unnumbered locations require evidence;
- waypoints and boundaries need not become full place cards;
- one topology node may map to one place unless a reviewed composite rule says
  otherwise.

### 3. Validate topology coverage

Require:

- every mapped place points to an existing node;
- every operational map node maps to a place or has an explicit non-place
  classification;
- every edge endpoint exists;
- conditional and hidden passages retain requirements;
- traversal direction is internally coherent.

### 4. Render operational place cards

Use stable sections:

```markdown
## First impression
## Contents
## Discoverable
## Hidden
## Triggers
## Hazards
## Resources
## Exits
```

`First impression` is player-safe. `Discoverable` pairs information with
actions or conditions. `Hidden` is GM-only.

### 5. Derive exits from canonical topology

Render into each mapped place:

- destination;
- passage kind;
- direction;
- baseline state;
- barriers;
- conditions;
- hazards.

Mark the section as generated. `topology.yaml` remains the sole canonical
owner.

### 6. Introduce typed `load_with`

Place front matter contains:

```yaml
load_with:
  actors: []
  situations: []
  procedures: []
  knowledge: []
```

At this slice, actor, situation, procedure, and knowledge cards may still use
their prior shallow bodies. Their references are nevertheless explicit and
bounded.

### 7. Add a scene resolver

Add a read-only library function and CLI/status interface that resolves:

```text
place ID
→ place card
→ load_with paths
→ current topology node and adjacent edges
```

Return exact paths and total bytes. Do not include:

- `audit/`;
- unrelated cards;
- complete topology;
- complete index;
- PDF.

## Pipeline invariant

Every contract change is delivered vertically:

- pack prompt and template;
- response validation;
- ingestion;
- reconciliation and review;
- release gate;
- card rendering;
- runtime index;
- documentation;
- tests.

A clean extraction either assembles valid operational places or stops at a
specific review requirement. It never emits a place without a required
topology decision.

## Tests

Create fresh synthetic sources for:

- a normal room with two exits;
- a secret door revealed by a search;
- a crawlway with a traversal condition;
- an unmapped social location;
- an ambiguous repeated area number;
- a map waypoint that is not a place;
- a place with mixed visible and hidden details.

Verify:

- explicit place-node resolution;
- derived exit fidelity;
- no duplicated canonical passage state;
- visibility sections;
- bounded scene resolver output;
- deterministic card rendering;
- review-required behavior for ambiguous joins.

Run the complete synthetic pipeline from preparation through assembly.

## Exit criteria

- Every keyed place is operationally runnable.
- Every mapped place has an explicit topology node.
- Immediate exits are present without loading complete topology.
- Hidden passages remain hidden until their condition is met.
- A place ID resolves an exact bounded context bundle.
- Audit files and the PDF are absent from that bundle.
- No prior produced result is consumed.
- The complete clean pipeline and repository validation pass.

## Handoff to implementation 3

Implementation 3 may rely on canonical places, typed scene references,
visibility sections, and bounded context resolution.
