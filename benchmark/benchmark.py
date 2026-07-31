#!/usr/bin/env python3
"""Run and score the local fact-extraction benchmark.

The benchmark deliberately talks to Ollama over its small HTTP API instead of
depending on an Ollama Python package.  That keeps the runner portable between
the Mac and Windows targets and makes the scorer usable without Ollama at all.

Typical commands::

    python3 benchmark/benchmark.py inventory
    python3 benchmark/benchmark.py install --tier tier1
    python3 benchmark/benchmark.py run --suite smoke --skip-unavailable
    python3 benchmark/benchmark.py run --suite full
    python3 benchmark/benchmark.py score benchmark/results/<run-id>

The runner stores every response verbatim under the run directory.  The JSON
result file contains only deterministic data and paths into that raw-response
tree, so it can be re-scored later without making another model call.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import difflib
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Callable, Iterable, Mapping, Sequence
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "benchmark" / "fixtures"
DEFAULT_RESULTS_ROOT = ROOT / "benchmark" / "results"
MANIFEST_PATH = FIXTURE_ROOT / "manifest.json"
OLLAMA_URL = "http://127.0.0.1:11434"
WHOLE_ADVENTURE_BYTES = 150_000
_PROGRESS_STARTED_AT: float | None = None
_ACTIVE_PROGRESS_DISPLAY: Any = None

SCHEMA = "benchmark-results/v1"
FIXTURE_SCHEMA = "benchmark-fixtures/v1"

TIER_MODELS: dict[str, tuple[str, ...]] = {
    "tier1": (
        "qwen3:8b",
        "llama3.1:8b",
        "granite3.3:8b",
        "qwen2.5-coder:7b",
        "mistral:7b",
    ),
    "tier2": (
        "qwen3:14b",
        "phi4:14b",
        "gemma3:12b",
    ),
}

MODEL_REASONS = {
    "qwen3:8b": "strong small-model instruction following and rigid-output potential",
    "llama3.1:8b": "widely deployed baseline",
    "granite3.3:8b": "structured and enterprise-output training",
    "qwen2.5-coder:7b": "tests whether code-model syntax discipline transfers",
    "mistral:7b": "older small-model floor",
    "qwen3:14b": "tests the quality cost of the Windows VRAM constraint",
    "phi4:14b": "second opinion in the Mac-only 14B tier",
    "gemma3:12b": "different model lineage in the Mac-only tier",
}

# The architecture's final schema.md is a later deliverable, but the benchmark
# must be self-contained.  This is the closed vocabulary used by the fixture
# benchmark and by the shared prompt.  It includes the field surface present in
# the committed reference records plus the worked CSV example.
PREDICATES = frozenset(
    {
        "activation",
        "actor_reactions",
        "actor_references",
        "appearance",
        "approaches",
        "behavior",
        "capabilities",
        "completion",
        "consequence",
        "contents",
        "cycle",
        "dimensions",
        "discoverable",
        "entries",
        "exit",
        "features",
        "first_impression",
        "goals",
        "hazards",
        "hidden",
        "keyed_area",
        "knowledge_references",
        "location_references",
        "mechanism",
        "occupants",
        "options",
        "outcomes",
        "participants",
        "perceived",
        "possible_effects",
        "procedure_references",
        "reactions",
        "relationships",
        "repeat",
        "resources",
        "role",
        "situation_references",
        "stakes",
        "starting_state",
        "steps",
        "text",
        "title",
        "trigger",
        "triggers",
        "visible",
    }
)
ENTITY_KINDS = frozenset(
    {
        "actor",
        "class",
        "effect",
        "event",
        "item",
        "knowledge",
        "location",
        "mechanism",
        "place",
        "procedure",
        "rule",
        "situation",
        "spell",
        "table",
        "object",
    }
)
VISIBILITIES = frozenset({"", "public", "hidden", "discoverable"})
OPTION_SLOTS = frozenset({"action", "cost", "condition", "result", "when", "outcome"})
STRUCTURED_PREDICATES = frozenset(
    {
        "activation",
        "actor_reactions",
        "cycle",
        "discoverable",
        "exit",
        "participants",
        "possible_effects",
        "reactions",
        "relationships",
        "repeat",
    }
)
FAILURE_TAXONOMY_KEYS = (
    "extra_fields",
    "escaped_quotes",
    "wrapped_in_json",
    "wrapped_in_fence",
    "added_commentary",
    "wrong_field_count",
    "unknown_vocabulary",
    "invalid_json",
    "structural_incomplete",
)
SAFE_ID = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$")
SAFE_ID_GUIDANCE = (
    "start with a lowercase letter, then use only lowercase letters, digits, "
    "or single '-' / '.' separators; underscores, spaces, and uppercase "
    "letters are invalid"
)
NUMBER_RE = re.compile(r"(?<![a-z])\d+(?:\.\d+)?(?:\s*[+\-]\s*\d+)?", re.I)


SHARED_PROMPT = """You extract source-faithful facts for a tabletop adventure.

Answer the question: what does this one source unit assert? Return ONLY the
rows below. Do not use Markdown fences, JSON wrappers, headings, explanations,
or commentary. Do not quote or escape fields. There must be exactly one
#unit row, and it must be the first row.

Every row has four comma-separated fields. Split on the first three commas;
the fourth field is free text or JSON and may contain commas. The first three
fields use this closed vocabulary:

- entity kinds: actor, class, effect, event, item, knowledge, location,
  mechanism, object, place, procedure, rule, situation, spell, table
- visibility: public, hidden, discoverable, or empty
- option slots: action, cost, condition, result, when, or outcome
- predicates: activation, actor_reactions, actor_references, appearance,
  approaches, behavior, capabilities, completion, consequence, contents,
  cycle, dimensions, discoverable, entries, exit, features, first_impression,
  goals, hazards, hidden, keyed_area, knowledge_references, mechanism,
  occupants, options, outcomes, participants, perceived, possible_effects,
  procedure_references, reactions, relationships, repeat, resources, role,
  situation_references, stakes, starting_state, steps, text, title, trigger,
  triggers, visible

Rows:

  #unit,<unit-id>,pages,<page-list>
  #entity,<local-id>,<entity-kind>,<source-faithful name>
  #option,<local-id>,<slot>,<source-faithful text>
  #uncertain,<local-id>,<about>,<source-faithful note>
  <local-id>,<predicate>,<visibility>,<value>

The last form is the normal fact row. Use it for ordinary source assertions
about an entity: descriptions, roles, contents, beliefs, events, mechanics,
numbers, and rules. Do not turn each sentence or paragraph into an #option row.
The #option form is special and is used only when the source describes a
distinct player approach or choice. Its slot must be one of action, cost,
condition, result, when, or outcome. Never use a numeric slot such as 0, and
never use #option for a heading or a general fact. For example:

  #entity,city,place,Free City
  city,visible,public,The city is known for freedom and lawlessness.
  #entity,temple,actor,White Temple
  temple,role,public,The temple worships Vandoh.
  #option,sprint,action,Sprint across
  #option,sprint,result,Reach the far side

Declare every entity before any fact that names it. Facts may use only local
entity IDs declared in this unit. Local IDs must start with a lowercase letter
and may contain only lowercase letters, digits, hyphens, or dots. Use short IDs
such as a24, ceil, or trap; `white-temple` is valid but `white_temple` is
invalid. Do not use spaces, uppercase letters, or underscores in IDs.
Use only the predicate vocabulary listed above. In particular, `description`
and `history` are invalid predicate names: use `text` for descriptive or
narrative prose, `role` for what an entity is or does, and `starting_state`
for an event's aftermath or current state.
Use JSON in the fourth field for genuinely structured values (including
activation, cycle, exit, reactions, relationships, and other structured
predicates); otherwise use plain source-faithful text. Preserve names,
numbers, distances, durations, dice, and mechanics exactly. Split repeated
list-valued facts into repeated rows. Do not invent rules, statistics, entities,
numbers, or details from general knowledge. Omit unsupported facts.

The fourth field is never quoted, even when it contains commas. The parser
splits only on the first three commas. For example, this is valid:

  #entity,room,place,Room
  room,contents,public,Three bowls, one live goat, and a chest.

Do not write the value as `"Three bowls, one live goat, and a chest."`.

The unit to extract follows.
"""


@dataclass(frozen=True)
class Fixture:
    identifier: str
    source_path: Path
    ground_truth_path: Path
    source_bytes: int
    expected_records: int
    record_types: Mapping[str, int]
    suite: str


@dataclass(frozen=True)
class ModelSpec:
    requested: str
    actual: str
    tier: str
    substitution: str | None = None


@dataclass
class Generation:
    text: str
    wall_clock_s: float
    time_to_first_token_s: float | None
    generated_tokens: int | None
    prompt_tokens: int | None
    tokens_per_second: float | None
    eval_duration_s: float | None
    error: str | None = None


class BenchmarkError(RuntimeError):
    """A user-facing benchmark error."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value), encoding="utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BenchmarkError(f"cannot read JSON from {path}: {exc}") from exc


def load_fixtures(root: Path = ROOT) -> tuple[dict[str, Fixture], dict[str, Any]]:
    manifest_path = root / "benchmark" / "fixtures" / "manifest.json"
    manifest = load_json(manifest_path)
    if manifest.get("schema") != FIXTURE_SCHEMA:
        raise BenchmarkError(f"unsupported fixture manifest schema in {manifest_path}")
    fixtures: dict[str, Fixture] = {}
    for entry in manifest.get("fixtures", []):
        identifier = entry.get("id")
        if not isinstance(identifier, str) or identifier in fixtures:
            raise BenchmarkError(f"invalid or duplicate fixture id: {identifier!r}")
        source_path = root / "benchmark" / entry["source"]
        ground_truth_path = root / "benchmark" / entry["ground_truth"]
        if not source_path.is_file() or not ground_truth_path.is_file():
            raise BenchmarkError(f"fixture {identifier} is missing source or ground truth")
        actual_bytes = source_path.stat().st_size
        if actual_bytes != entry["source_bytes"]:
            raise BenchmarkError(
                f"fixture {identifier} has {actual_bytes} bytes; manifest says "
                f"{entry['source_bytes']}"
            )
        fixtures[identifier] = Fixture(
            identifier=identifier,
            source_path=source_path,
            ground_truth_path=ground_truth_path,
            source_bytes=actual_bytes,
            expected_records=entry["expected_records"],
            record_types=entry.get("record_types", {}),
            suite=entry["suite"],
        )
    return fixtures, manifest


def fixture_prompt(fixture: Fixture) -> str:
    source = fixture.source_path.read_text(encoding="utf-8")
    return (
        SHARED_PROMPT
        + f"\n#unit,{fixture.identifier},pages,{fixture.identifier[1:]}\n"
        + "\nSOURCE TEXT\n"
        + source
        + "\nEND SOURCE TEXT\n"
        + f"\nThe required unit ID is {fixture.identifier}. Return only its rows.\n"
        + "\nBefore returning, silently verify: the first row is the single correct "
        + "#unit marker; every local ID uses lowercase letters, digits, '-' or "
        + "'.' only; every fact subject was declared first; every predicate is "
        + "from the listed vocabulary; and no fourth field is surrounded by "
        + "quotes.\n"
    )


def recovery_prompt(fixture: Fixture, response: str, errors: Sequence[str]) -> str:
    error_text = "\n".join(f"- {item}" for item in errors) or "- response did not validate"
    return (
        fixture_prompt(fixture)
        + "\nA previous response was rejected by the validator. Correct it.\n"
        + "Use normal fact rows for ordinary source statements. Do not copy the "
        + "previous response's #option rows. In particular, #option,<id>,0,... "
        + "is invalid. Valid option rows use only action, cost, condition, "
        + "result, when, or outcome as the third field. A valid correction has "
        + "this shape:\n"
        + "#entity,thing,place,A source-named thing\n"
        + "thing,visible,public,An ordinary source-supported fact\n"
        + "#option,choice,action,An explicitly described player approach\n"
        + "#option,choice,result,Its explicitly described result\n"
        + "Local IDs must follow this exact rule: lowercase letters and digits, "
        + "with '-' or '.' separators only. Replace `white_temple` with "
        + "`white-temple`; underscores are invalid. Use `text` instead of the "
        + "invalid predicate `description` or `history`. Never quote the fourth "
        + "field, even when it contains commas.\n"
        + "Validator errors:\n"
        + error_text
        + "\nPrevious response (untrusted; do not copy its wrappers or commentary):\n"
        + response
        + "\nReturn the complete corrected response only. Before returning, silently "
        + "verify the first-row #unit rule, ID syntax, declared-before-use order, "
        + "listed predicates, and unquoted fourth fields.\n"
    )


def _transport_body(response: str) -> tuple[str, set[str]]:
    """Remove only transport wrappers that the deterministic ingest may strip."""
    body = response.replace("\r\n", "\n").replace("\r", "\n")
    body = body.lstrip("\ufeff")
    stripped = body.strip()
    issues: set[str] = set()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        if len(lines) >= 2 and lines[-1].strip() == "```":
            issues.add("wrapped_in_fence")
            stripped = "\n".join(lines[1:-1]).strip()
    try:
        parsed = json.loads(stripped)
    except (TypeError, json.JSONDecodeError):
        parsed = None
    if isinstance(parsed, (dict, list)):
        issues.add("wrapped_in_json")
    return stripped, issues


def _line_error(line: str) -> str | None:
    if len(line.split(",", 3)) != 4:
        return "wrong_field_count"
    fields = line.split(",", 3)
    if any('"' in field for field in fields[:3]):
        return "escaped_quotes"
    if len(fields) == 4 and len(fields[3]) >= 2 and fields[3].startswith('"') and fields[3].endswith('"'):
        return "escaped_quotes"
    return None


def _fact_value_is_valid(predicate: str, value: str) -> bool:
    if predicate not in STRUCTURED_PREDICATES:
        return True
    try:
        json.loads(value)
    except json.JSONDecodeError:
        return False
    return True


def validate_response(response: str, expected_unit: str) -> dict[str, Any]:
    """Validate one model response without mutating the response text.

    ``line.split(',', 3)`` is intentionally used for every row.  A comma in
    field four is therefore legal; treating it as an extra CSV column would
    change the contract this benchmark is measuring.
    """
    body, transport_issues = _transport_body(response)
    lines = [line for line in body.split("\n") if line.strip()]
    response_issues = set(transport_issues)
    rows: list[dict[str, Any]] = []
    valid_row_count = 0
    structural_errors: list[str] = []
    format_errors: list[str] = []
    entities: dict[str, dict[str, str]] = {}
    facts: list[dict[str, str]] = []
    unit_markers: list[dict[str, str]] = []
    declared_before = set()
    saw_fact = False

    for line_number, line in enumerate(lines, 1):
        error = _line_error(line)
        if error:
            format_errors.append(f"line {line_number}: {error}")
            response_issues.add(error)
            rows.append({"line": line_number, "text": line, "valid": False, "kind": "malformed"})
            continue
        first, second, third, fourth = line.split(",", 3)
        row: dict[str, Any] = {
            "line": line_number,
            "text": line,
            "valid": True,
            "kind": "structural" if first.startswith("#") else "fact",
        }
        if first == "#unit":
            if second != expected_unit or third != "pages" or not fourth.strip():
                row["valid"] = False
                structural_errors.append(
                    f"line {line_number}: invalid #unit marker (expected {expected_unit})"
                )
            unit_markers.append({"id": second, "pages": fourth})
        elif first == "#entity":
            if not SAFE_ID.fullmatch(second):
                row["valid"] = False
                structural_errors.append(
                    f"line {line_number}: invalid entity id {second!r}; {SAFE_ID_GUIDANCE}"
                )
            if third not in ENTITY_KINDS:
                row["valid"] = False
                format_errors.append(f"line {line_number}: unknown entity kind {third!r}")
                response_issues.add("unknown_vocabulary")
            if not fourth.strip():
                row["valid"] = False
                structural_errors.append(f"line {line_number}: empty entity name")
            if second in entities:
                row["valid"] = False
                structural_errors.append(f"line {line_number}: duplicate entity {second!r}")
            entities[second] = {"kind": third, "name": fourth}
            declared_before.add(second)
        elif first == "#option":
            if not SAFE_ID.fullmatch(second):
                row["valid"] = False
                structural_errors.append(
                    f"line {line_number}: invalid option id {second!r}; {SAFE_ID_GUIDANCE}"
                )
            if third not in OPTION_SLOTS:
                row["valid"] = False
                format_errors.append(f"line {line_number}: unknown option slot {third!r}")
                response_issues.add("unknown_vocabulary")
        elif first == "#uncertain":
            if not SAFE_ID.fullmatch(second):
                row["valid"] = False
                structural_errors.append(
                    f"line {line_number}: invalid uncertainty id {second!r}; {SAFE_ID_GUIDANCE}"
                )
            if not third.strip() or not fourth.strip():
                row["valid"] = False
                structural_errors.append(f"line {line_number}: incomplete uncertainty row")
        elif first.startswith("#"):
            row["valid"] = False
            structural_errors.append(f"line {line_number}: unknown structural row {first!r}")
        else:
            saw_fact = True
            fact = {"subject": first, "predicate": second, "visibility": third, "value": fourth}
            facts.append(fact)
            if not SAFE_ID.fullmatch(first):
                row["valid"] = False
                format_errors.append(
                    f"line {line_number}: invalid fact subject {first!r}; {SAFE_ID_GUIDANCE}"
                )
                response_issues.add("unknown_vocabulary")
            if second not in PREDICATES:
                row["valid"] = False
                format_errors.append(f"line {line_number}: unknown predicate {second!r}")
                response_issues.add("unknown_vocabulary")
            if third not in VISIBILITIES:
                row["valid"] = False
                format_errors.append(f"line {line_number}: invalid visibility {third!r}")
                response_issues.add("unknown_vocabulary")
            if not _fact_value_is_valid(second, fourth):
                row["valid"] = False
                format_errors.append(f"line {line_number}: structured value is not JSON")
                response_issues.add("invalid_json")
            if first not in declared_before:
                structural_errors.append(
                    f"line {line_number}: fact subject {first!r} was not declared first"
                )
        if row["valid"]:
            valid_row_count += 1
        rows.append(row)

    if not lines:
        response_issues.add("empty_response")
        format_errors.append("response contains no rows")
    if any(not line.startswith(("#",)) and "," not in line for line in lines):
        response_issues.add("added_commentary")
    # A preamble or trailing prose can have commas, so classify every invalid
    # non-structural row as commentary in addition to its precise row error.
    for row in rows:
        if row["kind"] == "malformed" and row["text"] and not row["text"].startswith("#"):
            response_issues.add("added_commentary")

    expected_units = len(unit_markers) == 1 and unit_markers[0]["id"] == expected_unit
    if len(unit_markers) == 0:
        structural_errors.append(f"missing #unit marker for {expected_unit}")
    elif len(unit_markers) > 1:
        structural_errors.append("duplicated #unit marker")
    elif unit_markers[0]["id"] != expected_unit:
        structural_errors.append(
            f"wrong #unit marker {unit_markers[0]['id']!r}; expected {expected_unit!r}"
        )
    if not saw_fact and not structural_errors:
        structural_errors.append("unit has no facts")

    s1_valid = not format_errors and all(row["valid"] for row in rows)
    s2_valid = expected_units and not structural_errors
    entirely_clean = s1_valid and s2_valid and not response_issues
    if not s1_valid:
        response_issues.add("malformed_row")
    if not s2_valid:
        response_issues.add("structural_incomplete")
    return {
        "s1_valid": s1_valid,
        "s2_valid": s2_valid,
        "entirely_clean": entirely_clean,
        "row_count": len(rows),
        "valid_row_count": valid_row_count,
        "unit_markers": unit_markers,
        "entities": entities,
        "facts": facts,
        "rows": rows,
        "format_errors": format_errors,
        "structural_errors": structural_errors,
        "failure_kinds": sorted(response_issues),
        "cleaned_body": body,
    }


def _tokens(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        parts: list[str] = []
        for key, item in value.items():
            parts.extend(_tokens(key))
            parts.extend(_tokens(item))
        return parts
    if isinstance(value, (list, tuple, set)):
        result: list[str] = []
        for item in value:
            result.extend(_tokens(item))
        return result
    text = str(value).lower().replace("’", "'")
    words = re.findall(r"[a-z0-9]+", text)
    stop = {
        "a", "an", "and", "as", "at", "be", "by", "for", "from", "in",
        "into", "is", "it", "of", "on", "or", "the", "that", "their",
        "this", "to", "with", "when", "which", "while", "will",
    }
    return [word for word in words if word not in stop]


def _semantic_similarity(expected: Any, actual: Any) -> float:
    expected_tokens = _tokens(expected)
    actual_tokens = _tokens(actual)
    if not expected_tokens or not actual_tokens:
        return 1.0 if str(expected).strip().lower() == str(actual).strip().lower() else 0.0
    expected_set = set(expected_tokens)
    actual_set = set(actual_tokens)
    overlap = len(expected_set & actual_set) / len(expected_set)
    sequence = difflib.SequenceMatcher(
        None, " ".join(expected_tokens), " ".join(actual_tokens)
    ).ratio()
    expected_numbers = set(NUMBER_RE.findall(str(expected)))
    actual_numbers = set(NUMBER_RE.findall(str(actual)))
    number_bonus = 0.12 if expected_numbers and expected_numbers <= actual_numbers else 0.0
    if expected_numbers and not expected_numbers <= actual_numbers:
        number_bonus = -0.18
    return min(1.0, max(0.0, 0.62 * overlap + 0.38 * sequence + number_bonus))


PREDICATE_ALIASES: dict[str, tuple[str, ...]] = {
    "first_impression": ("visible",),
    "visible": ("first_impression",),
    "keyed_area": ("dimensions",),
    "text": ("description",),
    "trigger": ("activation",),
}


def _record_entity_matches(record: Mapping[str, Any], entities: Mapping[str, Mapping[str, str]]) -> list[str]:
    title = str(record.get("fields", {}).get("title", ""))
    record_type = str(record.get("record_type", ""))
    wanted_kinds = {
        "location": {"place", "location"},
        "actor": {"actor"},
        "effect": {"effect"},
        "item": {"item", "object"},
        "knowledge": {"knowledge"},
        "procedure": {"procedure"},
        "rule": {"rule"},
        "situation": {"situation", "event"},
        "spell": {"spell"},
        "class": {"class"},
        "table": {"table"},
    }.get(record_type, {record_type})
    title_tokens = set(_tokens(title))
    candidates: list[tuple[float, str]] = []
    for identifier, entity in entities.items():
        if entity.get("kind") not in wanted_kinds:
            continue
        name_tokens = set(_tokens(entity.get("name", "")))
        if not name_tokens:
            continue
        overlap = len(title_tokens & name_tokens) / max(1, len(title_tokens))
        ratio = difflib.SequenceMatcher(None, " ".join(_tokens(title)), " ".join(_tokens(entity.get("name", "")))).ratio()
        score = max(overlap, ratio)
        if title_tokens <= name_tokens or name_tokens <= title_tokens:
            score = max(score, 0.9)
        if score >= 0.45:
            candidates.append((score, identifier))
    candidates.sort(reverse=True)
    return [identifier for _, identifier in candidates]


def _json_or_text(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def score_recall(fixture: Fixture, validation: Mapping[str, Any], review: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Score reference substance with a transparent lexical semantic proxy.

    The reference is not gold truth and no local dependency can perform the
    human semantic judgment promised by the specification.  This scorer uses
    entity-name matching, predicate aliases, token overlap, sequence similarity,
    and number preservation.  A review file can override individual matches;
    the report labels this method explicitly rather than presenting it as gold.
    """
    records = load_json(fixture.ground_truth_path)
    entities = validation.get("entities", {})
    facts = validation.get("facts", [])
    by_subject: dict[str, list[Mapping[str, str]]] = {}
    for fact in facts:
        by_subject.setdefault(fact["subject"], []).append(fact)
    atoms: list[dict[str, Any]] = []
    matched_atoms = 0
    matched_records = 0
    for record in records:
        record_id = str(record.get("id", ""))
        candidates = _record_entity_matches(record, entities)
        chosen = candidates[0] if candidates else None
        record_review = (review or {}).get(record_id, {}) if isinstance(review, Mapping) else {}
        record_atoms: list[dict[str, Any]] = []
        title = record.get("fields", {}).get("title", record_id)
        title_match = bool(chosen)
        if "title" in record_review:
            title_match = bool(record_review["title"])
        record_atoms.append({"field": "title", "matched": title_match, "score": 1.0 if title_match else 0.0})
        if title_match:
            matched_atoms += 1
        for predicate, expected in record.get("fields", {}).items():
            if predicate == "title":
                continue
            expected_items = expected if isinstance(expected, list) else [expected]
            for item_index, expected_item in enumerate(expected_items):
                best = 0.0
                best_fact: Mapping[str, str] | None = None
                if chosen:
                    accepted_predicates = {predicate, *PREDICATE_ALIASES.get(predicate, ())}
                    for fact in by_subject.get(chosen, []):
                        if fact["predicate"] not in accepted_predicates:
                            continue
                        actual = _json_or_text(fact["value"])
                        score = _semantic_similarity(expected_item, actual)
                        if score > best:
                            best, best_fact = score, fact
                if isinstance(record_review, Mapping):
                    overrides = record_review.get("fields", {})
                    override = overrides.get(predicate) if isinstance(overrides, Mapping) else None
                    if isinstance(override, list) and item_index < len(override):
                        best = 1.0 if override[item_index] else 0.0
                matched = best >= 0.48
                if matched:
                    matched_atoms += 1
                record_atoms.append(
                    {
                        "field": predicate,
                        "index": item_index,
                        "matched": matched,
                        "similarity": round(best, 4),
                        "actual": best_fact.get("value") if best_fact else None,
                    }
                )
        record_matched = all(atom["matched"] for atom in record_atoms)
        if record_matched:
            matched_records += 1
        atoms.extend(
            [{"record": record_id, **atom} for atom in record_atoms]
        )
    total_atoms = len(atoms)
    return {
        "method": "lexical-semantic proxy with optional human review overrides",
        "records_total": len(records),
        "records_matched": matched_records,
        "record_recall": matched_records / len(records) if records else 1.0,
        "atoms_total": total_atoms,
        "atoms_matched": matched_atoms,
        "substance_recall": matched_atoms / total_atoms if total_atoms else 1.0,
        "details": atoms,
    }


def contamination_heuristics(fixture: Fixture, validation: Mapping[str, Any]) -> dict[str, Any]:
    source = fixture.source_path.read_text(encoding="utf-8").lower()
    source_numbers = set(NUMBER_RE.findall(source))
    suspicious_numbers: list[str] = []
    for entity in validation.get("entities", {}).values():
        for number in NUMBER_RE.findall(entity.get("name", "")):
            if number not in source_numbers:
                suspicious_numbers.append(number)
    for fact in validation.get("facts", []):
        for number in NUMBER_RE.findall(fact.get("value", "")):
            if number not in source_numbers:
                suspicious_numbers.append(number)
    suspicious_entities = [
        identifier
        for identifier, entity in validation.get("entities", {}).items()
        if _tokens(entity.get("name", ""))
        and not set(_tokens(entity.get("name", ""))).intersection(set(_tokens(source)))
    ]
    return {
        "status": "manual_review_required",
        "suspicious_numbers": sorted(set(suspicious_numbers)),
        "suspicious_entities": suspicious_entities,
        "unsupported_facts": None,
        "invented_entities": None,
        "invented_numbers": None,
        "imported_rules": None,
        "note": "Heuristics are leads for the required hand audit, not a contamination verdict.",
    }


class OllamaClient:
    """Minimal streaming client for Ollama's local HTTP API."""

    def __init__(self, base_url: str = OLLAMA_URL, timeout: float = 600.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, path: str, payload: Mapping[str, Any] | None = None) -> Any:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST" if data is not None else "GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise BenchmarkError(f"Ollama HTTP {exc.code}: {detail[:500]}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise BenchmarkError(
                f"cannot reach Ollama at {self.base_url}: {exc}"
            ) from exc
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BenchmarkError(f"Ollama returned invalid JSON from {path}") from exc

    def inventory(self) -> list[dict[str, Any]]:
        payload = self._request("/api/tags")
        models = payload.get("models", []) if isinstance(payload, Mapping) else []
        return [dict(item) for item in models if isinstance(item, Mapping)]

    def running_models(self) -> list[dict[str, Any]]:
        """Return the models currently loaded by Ollama."""
        payload = self._request("/api/ps")
        models = payload.get("models", []) if isinstance(payload, Mapping) else []
        return [dict(item) for item in models if isinstance(item, Mapping)]

    def pull(
        self,
        model: str,
        on_progress: Callable[[Mapping[str, Any]], None] | None = None,
    ) -> Mapping[str, Any]:
        """Pull a model through Ollama's streaming pull endpoint."""
        payload = {"model": model, "stream": True}
        request = urllib.request.Request(
            self.base_url + "/api/pull",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        final: Mapping[str, Any] | None = None
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                for raw_line in response:
                    if not raw_line.strip():
                        continue
                    try:
                        event = json.loads(raw_line.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                        raise BenchmarkError("Ollama emitted a non-JSON pull event") from exc
                    if not isinstance(event, Mapping):
                        raise BenchmarkError("Ollama emitted a non-object pull event")
                    if event.get("error"):
                        raise BenchmarkError(f"Ollama pull failed for {model}: {event['error']}")
                    if on_progress is not None:
                        on_progress(event)
                    if event.get("done") or event.get("status") == "success":
                        final = event
                        break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise BenchmarkError(f"Ollama HTTP {exc.code}: {detail[:500]}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise BenchmarkError(f"Ollama pull failed for {model}: {exc}") from exc
        if final is None:
            raise BenchmarkError(f"Ollama pull for {model} ended without success")
        return final

    def generate(
        self,
        model: str,
        prompt: str,
        on_progress: Callable[[int], None] | None = None,
    ) -> Generation:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "think": False,
            "keep_alive": "10m",
            "options": {"temperature": 0, "seed": 0},
        }
        request = urllib.request.Request(
            self.base_url + "/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = time.perf_counter()
        first_token_at: float | None = None
        chunks: list[str] = []
        generated_chars = 0
        final: dict[str, Any] = {}
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                for raw_line in response:
                    if not raw_line.strip():
                        continue
                    try:
                        event = json.loads(raw_line.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                        raise BenchmarkError("Ollama emitted a non-JSON stream event") from exc
                    if event.get("error"):
                        raise BenchmarkError(str(event["error"]))
                    piece = event.get("response", "")
                    if piece and first_token_at is None:
                        first_token_at = time.perf_counter()
                    chunks.append(piece)
                    generated_chars += len(piece)
                    if on_progress is not None and piece:
                        on_progress(generated_chars)
                    if event.get("done"):
                        final = event
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise BenchmarkError(f"Ollama HTTP {exc.code}: {detail[:500]}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise BenchmarkError(f"Ollama generation failed: {exc}") from exc
        ended = time.perf_counter()
        eval_duration_ns = final.get("eval_duration")
        eval_duration_s = (
            float(eval_duration_ns) / 1_000_000_000
            if isinstance(eval_duration_ns, (int, float)) and eval_duration_ns > 0
            else None
        )
        generated_tokens = final.get("eval_count")
        prompt_tokens = final.get("prompt_eval_count")
        tps = (
            float(generated_tokens) / eval_duration_s
            if isinstance(generated_tokens, (int, float)) and eval_duration_s
            else None
        )
        return Generation(
            text="".join(chunks),
            wall_clock_s=ended - started,
            time_to_first_token_s=(first_token_at - started if first_token_at else None),
            generated_tokens=int(generated_tokens) if isinstance(generated_tokens, (int, float)) else None,
            prompt_tokens=int(prompt_tokens) if isinstance(prompt_tokens, (int, float)) else None,
            tokens_per_second=tps,
            eval_duration_s=eval_duration_s,
        )


class ProgressDisplay:
    """A terminal-safe per-suite live status display."""

    def __init__(self, model: str, suite: str, total: int):
        self.model = model
        self.suite = suite
        self.total = total
        self.completed = 0
        self.current_fixture = "-"
        self.attempt = "-"
        self.status = "waiting"
        self.generated_chars = 0
        self.generation_started_at: float | None = None
        self.started_at = time.perf_counter()
        self.last_render = 0.0
        self.line_active = False
        self.tty = sys.stdout.isatty()

    def _text(self) -> str:
        elapsed = time.perf_counter() - self.started_at
        generation_elapsed = (
            time.perf_counter() - self.generation_started_at
            if self.generation_started_at is not None
            else 0.0
        )
        return (
            f"[benchmark] {self.model} [{self.suite}] "
            f"fixtures {self.completed}/{self.total} | "
            f"{self.current_fixture} attempt {self.attempt} | "
            f"output {self.generated_chars} chars "
            f"(+{generation_elapsed:.1f}s) — {self.status} "
            f"(+{elapsed:.1f}s)"
        )

    def render(self, *, force: bool = False) -> None:
        now = time.perf_counter()
        render_interval = 0.25 if self.tty else 0.75
        if not force and now - self.last_render < render_interval:
            return
        self.last_render = now
        line = self._text()
        if self.tty:
            sys.stdout.write("\r\033[2K" + line)
            sys.stdout.flush()
            self.line_active = True
        else:
            print(line, flush=True)

    def pause(self) -> None:
        if self.tty and self.line_active:
            sys.stdout.write("\r\033[2K")
            sys.stdout.flush()
            self.line_active = False

    def close(self) -> None:
        self.pause()
        if self.tty:
            sys.stdout.write("\n")
            sys.stdout.flush()

    def begin_fixture(self, index: int, fixture: str) -> None:
        self.current_fixture = fixture
        self.completed = index - 1
        self.attempt = "-"
        self.generated_chars = 0
        self.generation_started_at = None
        self.status = "starting"
        self.render(force=True)

    def begin_attempt(self, attempt: int, total_attempts: int) -> None:
        self.attempt = f"{attempt}/{total_attempts}"
        self.generated_chars = 0
        self.generation_started_at = time.perf_counter()
        self.status = "generating"
        self.render(force=True)

    def stream(self, generated_chars: int) -> None:
        self.generated_chars = generated_chars
        self.status = "streaming"
        self.render()

    def set_status(self, status: str) -> None:
        self.status = status
        self.render(force=True)

    def complete_fixture(self, index: int, status: str) -> None:
        self.completed = index
        self.status = status
        self.render(force=True)


def _generate_with_progress(
    client: Any,
    model: str,
    prompt: str,
    on_progress: Callable[[int], None] | None,
) -> Generation:
    """Call real or test clients, tolerating older two-argument test doubles."""
    if on_progress is None:
        return client.generate(model, prompt)
    try:
        return client.generate(model, prompt, on_progress=on_progress)
    except TypeError as exc:
        if "on_progress" not in str(exc) and "keyword" not in str(exc):
            raise
        return client.generate(model, prompt)


def detect_machine() -> str:
    if platform.system().lower() == "darwin":
        return "mac"
    if platform.system().lower() == "windows":
        return "windows"
    return platform.system().lower() or "unknown"


def _command_output(command: Sequence[str], timeout: float = 5.0) -> str | None:
    """Run a local informational command without invoking a shell."""
    if not command or shutil.which(command[0]) is None:
        return None
    try:
        completed = subprocess.run(
            list(command),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


def _physical_memory_bytes() -> int | None:
    system = platform.system()
    if system == "Darwin":
        value = _command_output(["sysctl", "-n", "hw.memsize"])
        try:
            return int(value) if value else None
        except ValueError:
            return None
    if system == "Windows":
        try:
            import ctypes

            class MemoryStatusEx(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatusEx()
            status.dwLength = ctypes.sizeof(MemoryStatusEx)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullTotalPhys)
        except (AttributeError, OSError, TypeError):
            return None
        return None
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        page_count = os.sysconf("SC_PHYS_PAGES")
        return int(page_size * page_count)
    except (AttributeError, OSError, ValueError):
        return None


def _mac_gpu_info() -> list[dict[str, Any]]:
    raw = _command_output(["system_profiler", "SPDisplaysDataType", "-json"], timeout=15.0)
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    result: list[dict[str, Any]] = []
    for item in payload.get("SPDisplaysDataType", []):
        if not isinstance(item, Mapping):
            continue
        gpu: dict[str, Any] = {}
        for source_key, target_key in (
            ("sppci_model", "name"),
            ("sppci_vendor", "vendor"),
            ("spdisplays_vram", "vram"),
            ("spdisplays_vram_dynamic", "vram_dynamic"),
        ):
            if item.get(source_key) is not None:
                gpu[target_key] = item[source_key]
        if gpu:
            result.append(gpu)
    return result


def _gpu_info() -> list[dict[str, Any]]:
    system = platform.system()
    if system == "Darwin":
        return _mac_gpu_info()
    nvidia = _command_output(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total",
            "--format=csv,noheader,nounits",
        ]
    )
    if nvidia:
        result = []
        for line in nvidia.splitlines():
            fields = [field.strip() for field in line.split(",", 1)]
            if fields and fields[0]:
                item: dict[str, Any] = {"name": fields[0]}
                if len(fields) == 2:
                    item["vram_mb"] = fields[1]
                result.append(item)
        if result:
            return result
    if system == "Windows":
        powershell = shutil.which("powershell.exe") or shutil.which("powershell")
        if powershell:
            raw = _command_output(
                [
                    powershell,
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    "Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM | ConvertTo-Json -Compress",
                ]
            )
            if raw:
                try:
                    parsed = json.loads(raw)
                    values = parsed if isinstance(parsed, list) else [parsed]
                    return [
                        {key: item[key] for key in ("Name", "AdapterRAM") if key in item}
                        for item in values
                        if isinstance(item, Mapping) and item.get("Name")
                    ]
                except json.JSONDecodeError:
                    pass
    return []


def collect_technical_info(ollama_url: str) -> dict[str, Any]:
    """Collect reproducibility metadata without requiring extra packages."""
    memory_bytes = _physical_memory_bytes()
    ollama_cli_version = _command_output(["ollama", "--version"])
    if ollama_cli_version:
        version_lines = [
            line.strip()
            for line in ollama_cli_version.splitlines()
            if "warning" not in line.lower() and "version" in line.lower()
        ]
        ollama_cli_version = version_lines[-1] if version_lines else ollama_cli_version
    return {
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor() or None,
        },
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
        "cpu": {"logical_count": os.cpu_count()},
        "memory": {"physical_bytes": memory_bytes},
        "gpu": _gpu_info(),
        "ollama": {
            "url": ollama_url,
            "cli_path": shutil.which("ollama"),
            "cli_version": ollama_cli_version,
        },
    }


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "model"


def _failure_errors(validation: Mapping[str, Any]) -> list[str]:
    return list(validation.get("format_errors", [])) + list(validation.get("structural_errors", []))


def _offload_snapshot(client: OllamaClient, model: str) -> dict[str, Any]:
    """Capture Ollama's loaded-model memory split without failing a run."""
    try:
        running_models = client.running_models()
    except (BenchmarkError, AttributeError) as exc:
        return {
            "model": model,
            "mode": "unavailable",
            "mode_source": "api_error",
            "error": str(exc),
        }

    loaded: Mapping[str, Any] | None = None
    for item in running_models:
        names = [item.get("name"), item.get("model")]
        if model in names:
            loaded = item
            break
        if model.endswith(":latest") and model[:-7] in names:
            loaded = item
            break
        if any(
            isinstance(name, str) and name.endswith(":latest") and name[:-7] == model
            for name in names
        ):
            loaded = item
            break
    if loaded is None:
        return {"model": model, "mode": "not_loaded", "mode_source": "api"}

    processor = loaded.get("processor")
    size = loaded.get("size")
    size_vram = loaded.get("size_vram")
    snapshot: dict[str, Any] = {
        "model": loaded.get("name") or loaded.get("model") or model,
        "mode": "unknown",
        "mode_source": "api",
        "processor": processor if isinstance(processor, str) else None,
        "size_bytes": size if isinstance(size, (int, float)) else None,
        "size_vram_bytes": size_vram if isinstance(size_vram, (int, float)) else None,
        "vram_fraction": None,
    }

    if isinstance(processor, str):
        normalized = processor.lower()
        if "cpu" in normalized and "gpu" in normalized:
            snapshot["mode"] = "mixed"
            snapshot["mode_source"] = "processor"
        elif "gpu" in normalized:
            snapshot["mode"] = "gpu"
            snapshot["mode_source"] = "processor"
        elif "cpu" in normalized:
            snapshot["mode"] = "cpu"
            snapshot["mode_source"] = "processor"

    if (
        isinstance(size, (int, float))
        and isinstance(size_vram, (int, float))
        and size > 0
    ):
        fraction = max(0.0, min(1.0, float(size_vram) / float(size)))
        snapshot["vram_fraction"] = round(fraction, 6)
        if snapshot["mode"] == "unknown":
            snapshot["mode_source"] = "size_vram_estimate"
            if fraction <= 0.01:
                snapshot["mode"] = "cpu"
            elif fraction >= 0.99:
                snapshot["mode"] = "gpu"
            else:
                snapshot["mode"] = "mixed"
    return snapshot


def _generation_dict(
    generation: Generation,
    raw_path: str,
    validation: Mapping[str, Any],
    offload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "raw_file": raw_path,
        "wall_clock_s": round(generation.wall_clock_s, 6),
        "time_to_first_token_s": (
            round(generation.time_to_first_token_s, 6)
            if generation.time_to_first_token_s is not None
            else None
        ),
        "generated_tokens": generation.generated_tokens,
        "prompt_tokens": generation.prompt_tokens,
        "tokens_per_second": (
            round(generation.tokens_per_second, 4)
            if generation.tokens_per_second is not None
            else None
        ),
        "eval_duration_s": (
            round(generation.eval_duration_s, 6) if generation.eval_duration_s is not None else None
        ),
        "offload": dict(offload) if offload is not None else None,
        "validation": {key: value for key, value in validation.items() if key != "cleaned_body"},
    }


def _progress(message: str) -> None:
    """Write a line immediately; model generations can otherwise look idle."""
    active = _ACTIVE_PROGRESS_DISPLAY
    if active is not None:
        active.pause()
    elapsed = (
        time.perf_counter() - _PROGRESS_STARTED_AT
        if _PROGRESS_STARTED_AT is not None
        else 0.0
    )
    timestamp = datetime.now().astimezone().strftime("%H:%M:%S")
    print(f"[benchmark {timestamp} +{elapsed:.1f}s] {message}", flush=True)
    if active is not None:
        active.render(force=True)


def _response_score(
    fixture: Fixture,
    attempts: Sequence[Mapping[str, Any]],
    audit: Mapping[str, Any] | None,
    recall_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    final = attempts[-1]
    validation = final["validation"]
    contamination = contamination_heuristics(fixture, validation)
    if isinstance(audit, Mapping):
        contamination.update(
            {
                "status": "pass" if all(not audit.get(key) for key in ("unsupported_facts", "invented_entities", "invented_numbers", "imported_rules")) else "fail",
                "reviewed": True,
                "unsupported_facts": audit.get("unsupported_facts", []),
                "invented_entities": audit.get("invented_entities", []),
                "invented_numbers": audit.get("invented_numbers", []),
                "imported_rules": audit.get("imported_rules", []),
                "notes": audit.get("notes", ""),
            }
        )
    return {
        "fixture": fixture.identifier,
        "source_bytes": fixture.source_bytes,
        "expected_records": fixture.expected_records,
        "attempts": list(attempts),
        "initial_s1_valid": attempts[0]["validation"]["s1_valid"],
        "initial_s2_valid": attempts[0]["validation"]["s2_valid"],
        "final_s1_valid": validation["s1_valid"],
        "final_s2_valid": validation["s2_valid"],
        "s1_failure_kinds": sorted({kind for attempt in attempts for kind in attempt["validation"]["failure_kinds"]}),
        "contamination": contamination,
        "recall": score_recall(fixture, validation, recall_review),
    }


def _aggregate_metrics(
    fixtures: Sequence[Mapping[str, Any]],
    budget_s: float | None = None,
    elapsed_s: float | None = None,
) -> dict[str, Any]:
    response_count = len(fixtures)
    row_total = sum(item["attempts"][-1]["validation"]["row_count"] for item in fixtures)
    valid_rows = sum(item["attempts"][-1]["validation"]["valid_row_count"] for item in fixtures)
    clean_responses = sum(bool(item["attempts"][-1]["validation"]["entirely_clean"]) for item in fixtures)
    failure_taxonomy: dict[str, int] = {}
    for item in fixtures:
        for attempt in item["attempts"]:
            for kind in attempt["validation"]["failure_kinds"]:
                failure_taxonomy[kind] = failure_taxonomy.get(kind, 0) + 1
    for kind in FAILURE_TAXONOMY_KEYS:
        failure_taxonomy.setdefault(kind, 0)
    primary_generations = [item["attempts"][0] for item in fixtures if item.get("attempts")]
    measured = [
        attempt
        for attempt in primary_generations
        if attempt.get("tokens_per_second") is not None
    ]
    total_source_bytes = sum(item["source_bytes"] for item in fixtures)
    total_generated_tokens = sum(
        attempt.get("generated_tokens") or 0 for attempt in primary_generations
    )
    wall = [attempt.get("wall_clock_s") for attempt in primary_generations if attempt.get("wall_clock_s") is not None]
    tps_values = [attempt["tokens_per_second"] for attempt in measured]
    ttft_values = [attempt["time_to_first_token_s"] for attempt in primary_generations if attempt.get("time_to_first_token_s") is not None]
    offload_snapshots = [
        attempt.get("offload")
        for attempt in primary_generations
        if isinstance(attempt.get("offload"), Mapping)
    ]
    offload_modes = sorted(
        {
            snapshot.get("mode")
            for snapshot in offload_snapshots
            if snapshot.get("mode")
        }
    )
    offload_processors = sorted(
        {
            snapshot.get("processor")
            for snapshot in offload_snapshots
            if snapshot.get("processor")
        }
    )
    vram_fractions = [
        float(snapshot["vram_fraction"])
        for snapshot in offload_snapshots
        if isinstance(snapshot.get("vram_fraction"), (int, float))
    ]
    source_scale = WHOLE_ADVENTURE_BYTES / total_source_bytes if total_source_bytes else None
    projected_wall = sum(wall) * source_scale if source_scale is not None else None
    projected_tokens = total_generated_tokens * source_scale if source_scale is not None else None
    if fixtures:
        record_total = sum(item["recall"]["atoms_total"] for item in fixtures)
        record_matched = sum(item["recall"]["atoms_matched"] for item in fixtures)
        records_total = sum(item["recall"]["records_total"] for item in fixtures)
        records_matched = sum(item["recall"]["records_matched"] for item in fixtures)
    else:
        record_total = record_matched = records_total = records_matched = 0
    contamination_statuses = {item["contamination"].get("status") for item in fixtures}
    s3_status = "pass" if contamination_statuses == {"pass"} else "fail" if "fail" in contamination_statuses else "manual_review_required"
    # Throughput projections intentionally use only primary generations.  The
    # suite elapsed time and budget gate must include every retry, however.
    # During a live run we receive the real wall-clock duration; when scoring
    # an existing run, sum all recorded attempt durations as the best available
    # reconstruction of that duration.
    recorded_attempt_elapsed = sum(
        float(attempt.get("wall_clock_s"))
        for item in fixtures
        for attempt in item.get("attempts", [])
        if isinstance(attempt.get("wall_clock_s"), (int, float))
    )
    elapsed = elapsed_s if elapsed_s is not None else recorded_attempt_elapsed
    marker_counts = {"present": 0, "duplicated": 0, "missing": 0, "wrong": 0}
    unresolved_subjects = 0
    for item in fixtures:
        validation = item["attempts"][-1]["validation"]
        marker_count = len(validation.get("unit_markers", []))
        if marker_count == 0:
            marker_counts["missing"] += 1
        elif marker_count > 1:
            marker_counts["duplicated"] += 1
        elif validation["unit_markers"][0].get("id") == item["fixture"]:
            marker_counts["present"] += 1
        else:
            marker_counts["wrong"] += 1
        unresolved_subjects += sum(
            "fact subject" in error for error in validation.get("structural_errors", [])
        )
    return {
        "responses": response_count,
        "rows": {"total": row_total, "valid": valid_rows, "parse_rate": valid_rows / row_total if row_total else 0.0},
        "entirely_clean_responses": clean_responses,
        "entirely_clean_rate": clean_responses / response_count if response_count else 0.0,
        "failure_taxonomy": dict(sorted(failure_taxonomy.items())),
        "s1_gate": bool(fixtures) and all(item["final_s1_valid"] for item in fixtures),
        "s2_gate": bool(fixtures) and all(item["final_s2_valid"] for item in fixtures),
        "structural": {
            "unit_markers": marker_counts,
            "unresolved_fact_subjects": unresolved_subjects,
        },
        "s3_gate": s3_status == "pass",
        "s3_status": s3_status,
        "recall": {
            "atoms_total": record_total,
            "atoms_matched": record_matched,
            "substance_recall": record_matched / record_total if record_total else 0.0,
            "records_total": records_total,
            "records_matched": records_matched,
            "record_recall": records_matched / records_total if records_total else 0.0,
        },
        "throughput": {
            "mean_tokens_per_second": sum(tps_values) / len(tps_values) if tps_values else None,
            "median_tokens_per_second": sorted(tps_values)[len(tps_values) // 2] if tps_values else None,
            "mean_wall_clock_s": sum(wall) / len(wall) if wall else None,
            "mean_time_to_first_token_s": sum(ttft_values) / len(ttft_values) if ttft_values else None,
            "total_generated_tokens": total_generated_tokens,
            "source_bytes": total_source_bytes,
            "projected_generated_tokens": projected_tokens,
            "projected_whole_adventure_wall_clock_s": projected_wall,
        },
        "offload": {
            "modes": offload_modes,
            "processors": offload_processors,
            "samples": len(offload_snapshots),
            "mean_vram_fraction": (
                sum(vram_fractions) / len(vram_fractions) if vram_fractions else None
            ),
        },
        "elapsed_s": round(elapsed, 6),
        "budget_s": budget_s,
        "budget_exceeded": budget_s is not None and elapsed > budget_s,
    }


def _has_benchmark_results(result: Mapping[str, Any]) -> bool:
    """Return whether a run contains at least one scored fixture response."""
    for model in result.get("models", []):
        if not isinstance(model, Mapping):
            continue
        suites = model.get("suites", {})
        if not isinstance(suites, Mapping):
            continue
        if any(
            isinstance(suite, Mapping) and suite.get("fixtures")
            for suite in suites.values()
        ):
            return True
    return False


def _load_audit(path: Path | None) -> dict[str, Any]:
    return load_json(path) if path else {}


def _audit_for(audit: Mapping[str, Any], model: str, fixture: str) -> Mapping[str, Any] | None:
    models = audit.get("models", audit) if isinstance(audit, Mapping) else {}
    model_audit = models.get(model, {}) if isinstance(models, Mapping) else {}
    value = model_audit.get(fixture) if isinstance(model_audit, Mapping) else None
    return value if isinstance(value, Mapping) and value.get("reviewed", True) else None


def _recall_review_for(review: Mapping[str, Any], model: str, fixture: str) -> Mapping[str, Any] | None:
    models = review.get("models", review) if isinstance(review, Mapping) else {}
    model_review = models.get(model, {}) if isinstance(models, Mapping) else {}
    value = model_review.get(fixture) if isinstance(model_review, Mapping) else None
    return value if isinstance(value, Mapping) else None


def _model_specs(names: Sequence[str], substitutions: Mapping[str, str]) -> list[ModelSpec]:
    specs: list[ModelSpec] = []
    for requested in names:
        actual = substitutions.get(requested, requested)
        tier = "tier1" if requested in TIER_MODELS["tier1"] else "tier2" if requested in TIER_MODELS["tier2"] else "custom"
        specs.append(ModelSpec(requested, actual, tier, actual if actual != requested else None))
    return specs


def _inventory_match(inventory: Sequence[Mapping[str, Any]], actual: str) -> Mapping[str, Any] | None:
    for item in inventory:
        name = item.get("name")
        if name == actual:
            return item
        # Ollama sometimes reports a tag-less name while the CLI argument has
        # :latest.  Record the exact installed name, but permit that harmless
        # equivalent when resolving a requested model.
        if isinstance(name, str) and actual.endswith(":latest") and name == actual[:-7]:
            return item
    return None


def _run_model(
    client: OllamaClient,
    spec: ModelSpec,
    fixtures: Mapping[str, Fixture],
    fixture_ids: Sequence[str],
    output_dir: Path,
    suite_name: str,
    budget_s: float | None,
    retries: int,
    audit: Mapping[str, Any],
    recall_review: Mapping[str, Any],
    run_started: float,
    progress: Callable[[str], None] = _progress,
) -> dict[str, Any]:
    """Run a suite while keeping a live progress display clean on Ctrl-C."""
    global _ACTIVE_PROGRESS_DISPLAY
    display = ProgressDisplay(spec.requested, suite_name, len(fixture_ids))
    previous_display = _ACTIVE_PROGRESS_DISPLAY
    _ACTIVE_PROGRESS_DISPLAY = display
    try:
        return _run_model_body(
            client,
            spec,
            fixtures,
            fixture_ids,
            output_dir,
            suite_name,
            budget_s,
            retries,
            audit,
            recall_review,
            run_started,
            progress,
            display,
        )
    finally:
        display.close()
        _ACTIVE_PROGRESS_DISPLAY = previous_display


def _run_model_body(
    client: OllamaClient,
    spec: ModelSpec,
    fixtures: Mapping[str, Fixture],
    fixture_ids: Sequence[str],
    output_dir: Path,
    suite_name: str,
    budget_s: float | None,
    retries: int,
    audit: Mapping[str, Any],
    recall_review: Mapping[str, Any],
    run_started: float,
    progress: Callable[[str], None] = _progress,
    display: ProgressDisplay | None = None,
) -> dict[str, Any]:
    model_raw_root = output_dir / "raw" / _safe_filename(spec.requested) / suite_name
    prompt_root = output_dir / "prompts" / suite_name
    results: list[dict[str, Any]] = []
    skipped: list[str] = []
    total_fixtures = len(fixture_ids)
    for fixture_index, fixture_id in enumerate(fixture_ids, 1):
        elapsed = time.perf_counter() - run_started
        if budget_s is not None and elapsed >= budget_s:
            remaining = fixture_ids[fixture_index - 1 :]
            skipped.extend(remaining)
            for skipped_id in remaining:
                progress(
                    f"{spec.requested} [{suite_name}] {skipped_id}: skipped; "
                    f"{suite_name} budget ({budget_s:.0f}s) exhausted"
                )
            break
        fixture = fixtures[fixture_id]
        if display is not None:
            display.begin_fixture(fixture_index, fixture_id)
        progress(
            f"{spec.requested} [{suite_name}] {fixture_index}/{total_fixtures} "
            f"{fixture_id}: starting"
        )
        prompt = fixture_prompt(fixture)
        prompt_path = prompt_root / f"{fixture.identifier}.md"
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(prompt, encoding="utf-8")
        attempts: list[dict[str, Any]] = []
        for attempt_number in range(1, retries + 2):
            if display is not None:
                display.begin_attempt(attempt_number, retries + 1)
            progress(
                f"{spec.requested} [{suite_name}] {fixture_id}: "
                f"generation attempt {attempt_number}/{retries + 1}"
            )
            try:
                generation = _generate_with_progress(
                    client,
                    spec.actual,
                    prompt if attempt_number == 1 else recovery_prompt(fixture, previous_text, _failure_errors(previous_validation)),
                    display.stream if display is not None else None,
                )
            except BenchmarkError as exc:
                skipped.append(fixture_id)
                if display is not None:
                    display.set_status("generation error")
                progress(
                    f"{spec.requested} [{suite_name}] {fixture_id}: "
                    f"generation error: {exc}"
                )
                attempts.append({"error": str(exc), "validation": {"s1_valid": False, "s2_valid": False, "entirely_clean": False, "row_count": 0, "valid_row_count": 0, "failure_kinds": ["generation_error"], "format_errors": [str(exc)], "structural_errors": []}})
                break
            raw_path = model_raw_root / f"{fixture.identifier}.attempt-{attempt_number}.txt"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(generation.text, encoding="utf-8")
            validation = validate_response(generation.text, fixture.identifier)
            attempts.append(
                _generation_dict(
                    generation,
                    raw_path.relative_to(output_dir).as_posix(),
                    validation,
                    _offload_snapshot(client, spec.actual),
                )
            )
            previous_text = generation.text
            previous_validation = validation
            if validation["s1_valid"] and validation["s2_valid"]:
                if display is not None:
                    display.set_status("accepted")
                progress(
                    f"{spec.requested} [{suite_name}] {fixture_id}: "
                    f"attempt {attempt_number} accepted in {generation.wall_clock_s:.1f}s"
                )
                break
            if display is not None:
                display.set_status("rejected; retrying")
            progress(
                f"{spec.requested} [{suite_name}] {fixture_id}: "
                f"attempt {attempt_number} rejected; retrying "
                f"({', '.join(validation['failure_kinds']) or 'validation error'})"
            )
        if not attempts:
            continue
        if "validation" not in attempts[-1]:
            # A generation error has no meaningful recall/contamination score.
            continue
        result = _response_score(
            fixture,
            attempts,
            _audit_for(audit, spec.requested, fixture.identifier),
            _recall_review_for(recall_review, spec.requested, fixture.identifier),
        )
        results.append(result)
        final_validation = attempts[-1]["validation"]
        if display is not None:
            display.complete_fixture(
                fixture_index,
                f"S1={'PASS' if final_validation['s1_valid'] else 'FAIL'} "
                f"S2={'PASS' if final_validation['s2_valid'] else 'FAIL'}",
            )
        progress(
            f"{spec.requested} [{suite_name}] {fixture_id}: done — "
            f"S1={'PASS' if final_validation['s1_valid'] else 'FAIL'}, "
            f"S2={'PASS' if final_validation['s2_valid'] else 'FAIL'}"
        )
    return {
        "name": suite_name,
        "fixtures": results,
        "skipped": skipped,
        "metrics": _aggregate_metrics(
            results,
            budget_s,
            elapsed_s=time.perf_counter() - run_started,
        ),
    }


def _run_s6(
    client: OllamaClient,
    spec: ModelSpec,
    fixture: Fixture,
    output_dir: Path,
    full_suite: Mapping[str, Any],
    progress: Callable[[str], None] = _progress,
) -> dict[str, Any]:
    root = output_dir / "raw" / _safe_filename(spec.requested) / "s6"
    prompt = fixture_prompt(fixture)
    progress(f"{spec.requested} [s6] {fixture.identifier}: determinism run 1/2")
    first = client.generate(spec.actual, prompt)
    first_offload = _offload_snapshot(client, spec.actual)
    progress(f"{spec.requested} [s6] {fixture.identifier}: determinism run 2/2")
    second = client.generate(spec.actual, prompt)
    second_offload = _offload_snapshot(client, spec.actual)
    root.mkdir(parents=True, exist_ok=True)
    first_path = root / f"{fixture.identifier}.determinism-1.txt"
    second_path = root / f"{fixture.identifier}.determinism-2.txt"
    first_path.write_text(first.text, encoding="utf-8")
    second_path.write_text(second.text, encoding="utf-8")
    first_validation = validate_response(first.text, fixture.identifier)
    second_validation = validate_response(second.text, fixture.identifier)
    source = next((item for item in full_suite.get("fixtures", []) if item["fixture"] == fixture.identifier), None)
    baseline = source["attempts"][0]["raw_file"] if source and source.get("attempts") else None
    malformed = first.text + "\nThis sentence is deliberately outside the rows."
    malformed_validation = validate_response(malformed, fixture.identifier)
    progress(f"{spec.requested} [s6] {fixture.identifier}: recovery run")
    retry = client.generate(spec.actual, recovery_prompt(fixture, malformed, _failure_errors(malformed_validation)))
    retry_offload = _offload_snapshot(client, spec.actual)
    retry_path = root / f"{fixture.identifier}.recovery.txt"
    retry_path.write_text(retry.text, encoding="utf-8")
    retry_validation = validate_response(retry.text, fixture.identifier)
    result = {
        "fixture": fixture.identifier,
        "baseline_raw_file": baseline,
        "determinism": {
            "raw_files": [first_path.relative_to(output_dir).as_posix(), second_path.relative_to(output_dir).as_posix()],
            "byte_identical": first.text == second.text,
            "first": _generation_dict(
                first,
                first_path.relative_to(output_dir).as_posix(),
                first_validation,
                first_offload,
            ),
            "second": _generation_dict(
                second,
                second_path.relative_to(output_dir).as_posix(),
                second_validation,
                second_offload,
            ),
        },
        "recovery": {
            "malformed_failure_kinds": malformed_validation["failure_kinds"],
            "raw_file": retry_path.relative_to(output_dir).as_posix(),
            "converged": retry_validation["s1_valid"] and retry_validation["s2_valid"],
            "validation": {key: value for key, value in retry_validation.items() if key != "cleaned_body"},
            "generation": _generation_dict(
                retry,
                retry_path.relative_to(output_dir).as_posix(),
                retry_validation,
                retry_offload,
            ),
        },
    }
    progress(
        f"{spec.requested} [s6] {fixture.identifier}: done — "
        f"determinism={'PASS' if result['determinism']['byte_identical'] else 'FAIL'}, "
        f"recovery={'PASS' if result['recovery']['converged'] else 'FAIL'}"
    )
    return result


def _default_model_names(tier: str) -> list[str]:
    if tier == "all":
        return list(TIER_MODELS["tier1"] + TIER_MODELS["tier2"])
    if tier not in TIER_MODELS:
        raise BenchmarkError(f"unknown tier {tier!r}")
    return list(TIER_MODELS[tier])


def _requested_names(args: argparse.Namespace) -> list[str]:
    if args.models:
        return [name.strip() for name in args.models.split(",") if name.strip()]
    tier = "all" if getattr(args, "include_tier2", False) else args.tier
    return _default_model_names(tier)


def _parse_substitutions(values: Sequence[str]) -> dict[str, str]:
    substitutions: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise BenchmarkError(f"--model-map expects REQUESTED=ACTUAL, got {value!r}")
        requested, actual = value.split("=", 1)
        if not requested or not actual:
            raise BenchmarkError(f"invalid model substitution {value!r}")
        substitutions[requested] = actual
    return substitutions


def _timestamp_id(machine: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{now}-{machine}"


def run_benchmark(args: argparse.Namespace) -> Path | None:
    global _PROGRESS_STARTED_AT
    _PROGRESS_STARTED_AT = time.perf_counter()
    fixtures, manifest = load_fixtures(ROOT)
    machine = detect_machine()
    technical_info = collect_technical_info(args.ollama_url)
    requested_names = _requested_names(args)
    specs = _model_specs(requested_names, _parse_substitutions(args.model_map))
    output_dir = Path(args.output) if args.output else DEFAULT_RESULTS_ROOT / _timestamp_id(machine)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise BenchmarkError(f"refusing to overwrite non-empty output directory: {output_dir}")
    output_dir_preexisted = output_dir.exists()
    audit = _load_audit(Path(args.audit) if args.audit else None)
    recall_review = _load_audit(Path(args.recall_review) if args.recall_review else None)
    client = OllamaClient(args.ollama_url, args.request_timeout)
    inventory = client.inventory()
    prompt_hash = sha256_bytes(SHARED_PROMPT.encode("utf-8"))
    platform_info = technical_info["platform"]
    memory_bytes = technical_info["memory"].get("physical_bytes")
    memory_text = (
        f"{float(memory_bytes) / (1024**3):.1f} GiB"
        if isinstance(memory_bytes, (int, float))
        else "unknown RAM"
    )
    _progress(
        f"environment: machine={machine} (auto-detected), "
        f"OS={platform_info['system']} {platform_info['release']}, "
        f"arch={platform_info['machine'] or 'unknown'}, "
        f"CPU={technical_info['cpu']['logical_count'] or 'unknown'} logical, "
        f"RAM={memory_text}, GPUs={len(technical_info['gpu'])}"
    )
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "run_id": output_dir.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "machine": machine,
        "environment": technical_info,
        "host": platform.platform(),
        "suite_requested": args.suite,
        "prompt_sha256": prompt_hash,
        "fixture_manifest_sha256": sha256_file(MANIFEST_PATH),
        "whole_adventure_bytes_assumption": WHOLE_ADVENTURE_BYTES,
        "config": {
            "ollama_url": args.ollama_url,
            "temperature": 0,
            "seed": 0,
            "retries": args.retries,
            "skip_unavailable": args.skip_unavailable,
            "smoke_budget_s": None,
            "quick_budget_s": args.quick_budget,
            "full_budget_s": args.full_budget,
        },
        "model_inventory": inventory,
        "models": [],
    }
    availability: dict[str, Mapping[str, Any] | None] = {}
    unavailable: list[str] = []
    for spec in specs:
        installed = _inventory_match(inventory, spec.actual)
        availability[spec.requested] = installed
        if installed is None:
            unavailable.append(f"{spec.requested} (requested actual tag: {spec.actual})")
            _progress(
                f"model check: UNAVAILABLE {spec.requested} "
                f"(actual tag: {spec.actual})"
            )
        else:
            details = installed.get("details", {}) or {}
            size = installed.get("size")
            size_text = (
                f", {float(size) / (1024**3):.2f} GiB"
                if isinstance(size, (int, float))
                else ""
            )
            _progress(
                f"model check: FOUND {spec.requested} -> {installed.get('name', spec.actual)}"
                f"{size_text}, {details.get('parameter_size', '?')}, "
                f"{details.get('quantization_level', '?')}"
            )
    if unavailable and not args.skip_unavailable:
        raise BenchmarkError(
            "unavailable model(s): "
            + ", ".join(unavailable)
            + "; install them or rerun with --skip-unavailable"
        )
    if not any(availability.values()):
        _progress("no requested models are available; no benchmark results written")
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    all_fixture_ids = [item["id"] for item in manifest["fixtures"]]
    smoke_ids = manifest["suites"]["smoke"]["fixtures"]
    quick_ids = manifest["suites"]["quick"]["fixtures"]
    full_ids = manifest["suites"]["full"]["fixtures"]
    for spec in specs:
        model_result: dict[str, Any] = {
            "requested": spec.requested,
            "actual": spec.actual,
            "tier": spec.tier,
            "reason": MODEL_REASONS.get(spec.requested, "user-specified model"),
            "substitution": spec.substitution,
            "available": availability[spec.requested] is not None,
            "suites": {},
        }
        if not model_result["available"]:
            model_result["status"] = "unavailable"
            _progress(
                f"{spec.requested}: unavailable ({spec.actual}); "
                "use inventory or --model-map to select an installed tag"
            )
            result["models"].append(model_result)
            continue
        _progress(f"{spec.requested} -> {spec.actual}: starting {args.suite} benchmark")
        if args.suite == "smoke":
            smoke_started = time.perf_counter()
            smoke = _run_model(
                client, spec, fixtures, smoke_ids, output_dir, "smoke", None,
                args.retries, audit, recall_review, smoke_started,
            )
            model_result["suites"]["smoke"] = smoke
            _progress(
                f"{spec.requested} [smoke]: complete — "
                f"S1={'PASS' if smoke['metrics']['s1_gate'] else 'FAIL'}, "
                f"S2={'PASS' if smoke['metrics']['s2_gate'] else 'FAIL'}, "
                f"elapsed={smoke['metrics']['elapsed_s']:.1f}s"
            )
            model_result["status"] = "completed"
            _progress(f"{spec.requested}: benchmark complete")
            result["models"].append(model_result)
            continue
        model_start = time.perf_counter()
        quick = _run_model(
            client, spec, fixtures, quick_ids, output_dir, "quick", args.quick_budget,
            args.retries, audit, recall_review, model_start,
        )
        model_result["suites"]["quick"] = quick
        _progress(
            f"{spec.requested} [quick]: complete — "
            f"S1={'PASS' if quick['metrics']['s1_gate'] else 'FAIL'}, "
            f"S2={'PASS' if quick['metrics']['s2_gate'] else 'FAIL'}, "
            f"elapsed={quick['metrics']['elapsed_s']:.1f}s"
        )
        quick_pass = quick["metrics"]["s1_gate"] and quick["metrics"]["s2_gate"] and not quick["metrics"]["budget_exceeded"]
        if args.suite == "full" and quick_pass:
            full_started = time.perf_counter()
            full = _run_model(
                client, spec, fixtures, full_ids, output_dir, "full", args.full_budget,
                args.retries, audit, recall_review, full_started,
            )
            model_result["suites"]["full"] = full
            _progress(
                f"{spec.requested} [full]: fixtures complete — "
                f"S1={'PASS' if full['metrics']['s1_gate'] else 'FAIL'}, "
                f"S2={'PASS' if full['metrics']['s2_gate'] else 'FAIL'}, "
                f"elapsed={full['metrics']['elapsed_s']:.1f}s"
            )
            if full["fixtures"] and not full["metrics"]["budget_exceeded"]:
                try:
                    model_result["s6"] = _run_s6(client, spec, fixtures["p31"], output_dir, full)
                except BenchmarkError as exc:
                    model_result["s6"] = {"status": "error", "error": str(exc)}
            elif full["fixtures"]:
                model_result["s6"] = {
                    "status": "skipped",
                    "reason": "full-suite budget was exhausted before S6",
                }
            full["metrics"]["elapsed_s"] = round(time.perf_counter() - full_started, 6)
            full["metrics"]["budget_exceeded"] = full["metrics"]["elapsed_s"] > args.full_budget
        elif args.suite == "full":
            model_result["full_skipped_reason"] = "quick suite did not pass S1/S2/throughput budget"
            _progress(
                f"{spec.requested} [full]: skipped because quick suite did not pass "
                "S1/S2/throughput budget"
            )
        model_result["status"] = "completed"
        _progress(f"{spec.requested}: benchmark complete")
        result["models"].append(model_result)
    result["notes"] = {
        "smoke_fixture_ids": smoke_ids,
        "quick_fixture_ids": quick_ids,
        "full_fixture_ids": full_ids,
        "smoke_note": "The smoke suite runs p31 only and has no time budget; it is a contract check, not the formal quick gate.",
        "skipped_fixture_ids_if_budget_exceeded": all_fixture_ids,
        "recall_caveat": "Ground truth is a strong human-reviewed reference, not gold truth; recall uses a lexical semantic proxy.",
        "contamination_caveat": "S3 remains pending until a human audit file is supplied.",
    }
    if not _has_benchmark_results(result):
        if not output_dir_preexisted:
            shutil.rmtree(output_dir)
        _progress("no fixture responses were collected; no benchmark results written")
        return None
    write_json(output_dir / "results.json", result)
    write_json(output_dir / "contamination-audit.template.json", build_audit_template(result))
    (output_dir / "summary.md").write_text(render_summary(result), encoding="utf-8")
    return output_dir


def build_audit_template(result: Mapping[str, Any]) -> dict[str, Any]:
    models: dict[str, Any] = {}
    for model in result.get("models", []):
        if not model.get("available"):
            continue
        fixtures: dict[str, Any] = {}
        full = model.get("suites", {}).get("full", {})
        for item in full.get("fixtures", []):
            fixtures[item["fixture"]] = {
                "reviewed": False,
                "unsupported_facts": [],
                "invented_entities": [],
                "invented_numbers": [],
                "imported_rules": [],
                "notes": "Review the raw response against the source text by hand.",
            }
        models[model["requested"]] = fixtures
    return {
        "schema": "benchmark-contamination-audit/v1",
        "instructions": "Set reviewed=true after hand review. Any non-empty finding fails S3 for that fixture.",
        "models": models,
    }


def _format_seconds(value: Any) -> str:
    if value is None:
        return "—"
    seconds = float(value)
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{seconds / 60:.1f}m"


def _format_bytes(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "unknown"
    return f"{float(value) / (1024**3):.1f} GiB"


def _model_summary_rows(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model in result.get("models", []):
        suite = (
            model.get("suites", {}).get("full")
            or model.get("suites", {}).get("quick")
            or model.get("suites", {}).get("smoke")
            or {}
        )
        metrics = suite.get("metrics", {})
        recall = metrics.get("recall", {})
        throughput = metrics.get("throughput", {})
        offload = metrics.get("offload", {})
        offload_modes = offload.get("modes", []) if isinstance(offload, Mapping) else []
        rows.append(
            {
                "requested": model.get("requested"),
                "actual": model.get("actual"),
                "tier": model.get("tier"),
                "available": model.get("available", False),
                "s1": metrics.get("s1_gate", False) if suite else False,
                "s2": metrics.get("s2_gate", False) if suite else False,
                "s3": metrics.get("s3_status", "not-run") if suite else "not-run",
                "recall": recall.get("substance_recall"),
                "tps": throughput.get("mean_tokens_per_second"),
                "offload": ", ".join(str(mode) for mode in offload_modes) or None,
                "wall": throughput.get("projected_whole_adventure_wall_clock_s"),
                "failure_taxonomy": metrics.get("failure_taxonomy", {}),
                "model": model,
            }
        )
    return rows


def recommendation(result: Mapping[str, Any]) -> str:
    rows = _model_summary_rows(result)
    if result.get("suite_requested") == "smoke":
        return "Smoke run only: use this small contract check for iteration; run the quick suite for formal triage and the full suite for the complete evaluation."
    if result.get("suite_requested") == "quick":
        return "Recommendation pending: this run covers the quick triage suite only; run the full suite and complete the required S3 contamination audit before selecting a local model."
    pending = [row for row in rows if row["available"] and row["s3"] == "manual_review_required"]
    candidates = [row for row in rows if row["available"] and row["s1"] and row["s2"] and row["s3"] is True]
    if pending and not candidates:
        return "Recommendation pending: complete the required manual S3 contamination audit in `contamination-audit.template.json`; no model is declared viable before that gate passes."
    if not candidates:
        return "Recommendation: no local model is viable yet. No available model passed all required gates in this run."
    chosen = sorted(
        candidates,
        key=lambda row: (
            -(row["recall"] if row["recall"] is not None else -1),
            row["wall"] if row["wall"] is not None else math.inf,
        ),
    )[0]
    return (
        f"Recommendation: use `{chosen['actual']}` on {result.get('machine', 'the tested machine')} "
        f"for the local Stage 5 transport. It passed S1, S2, and S3 with "
        f"{(chosen['recall'] or 0) * 100:.1f}% substance recall; projected whole-adventure wall-clock is "
        f"{_format_seconds(chosen['wall'])}."
    )


def render_summary(result: Mapping[str, Any]) -> str:
    rows = _model_summary_rows(result)
    lines = [recommendation(result), "", "# Local model benchmark summary", ""]
    lines.append(
        f"Machine: `{result.get('machine', 'unknown')}`  "
        f"Suite requested: `{result.get('suite_requested', 'unknown')}`  "
        f"Prompt SHA-256: `{result.get('prompt_sha256', '')}`"
    )
    environment = result.get("environment", {})
    platform_info = environment.get("platform", {})
    cpu_info = environment.get("cpu", {})
    memory_info = environment.get("memory", {})
    ollama_info = environment.get("ollama", {})
    gpu_info = environment.get("gpu", [])
    gpu_names = [str(item.get("name")) for item in gpu_info if isinstance(item, Mapping) and item.get("name")]
    lines.extend(
        [
            "",
            "## Technical environment",
            "",
            f"- OS: `{platform_info.get('system', 'unknown')} {platform_info.get('release', '')}`; architecture: `{platform_info.get('machine', 'unknown')}`",
            f"- Python: `{environment.get('python', {}).get('version', 'unknown')}`; logical CPUs: `{cpu_info.get('logical_count', 'unknown')}`; physical RAM: `{_format_bytes(memory_info.get('physical_bytes'))}`",
            f"- GPU: `{', '.join(gpu_names) if gpu_names else 'not detected'}`",
            f"- Ollama: `{ollama_info.get('cli_version') or 'CLI version unavailable'}` at `{ollama_info.get('url', 'unknown')}`",
            "",
            "The first-generation and final-generation measurements are retained "
            "in `results.json`; every raw response is under `raw/`.",
            "",
            "## Per-model result",
            "",
            "| Model | Actual tag | Tier | S1 | S2 | S3 | Substance recall | Gen tok/s | Offload | Projected whole adventure |",
            "|---|---|---|---|---|---|---:|---:|---|---:|",
        ]
    )
    for row in rows:
        if not row["available"]:
            lines.append(f"| `{row['requested']}` | unavailable | {row['tier']} | — | — | — | — | — | — | — |")
            continue
        s3 = "PASS" if row["s3"] is True else str(row["s3"]).replace("_", " ")
        recall = "—" if row["recall"] is None else f"{row['recall'] * 100:.1f}%"
        tps = "—" if row["tps"] is None else f"{row['tps']:.1f}"
        offload = row["offload"] or "—"
        lines.append(
            f"| `{row['requested']}` | `{row['actual']}` | {row['tier']} | "
            f"{'PASS' if row['s1'] else 'FAIL'} | {'PASS' if row['s2'] else 'FAIL'} | {s3} | "
            f"{recall} | {tps} | {offload} | {_format_seconds(row['wall'])} |"
        )
    lines.extend(["", "## Failure taxonomy", ""])
    taxonomy: dict[str, int] = {}
    for row in rows:
        for key, count in row["failure_taxonomy"].items():
            taxonomy[key] = taxonomy.get(key, 0) + count
    if taxonomy:
        for key, count in sorted(taxonomy.items()):
            lines.append(f"- `{key}`: {count} response/attempt occurrence(s)")
    else:
        lines.append("No format failures were recorded.")
    lines.extend(
        [
            "",
            "## Prompt and scoring notes",
            "",
            "All models received one shared prompt with temperature 0 and seed 0. "
            "The prompt is saved per fixture under `prompts/`; no model-specific "
            "examples or tuning are hidden in the runner.",
            "",
            "S3 is a required human gate. The deterministic number/entity checks "
            "are only audit leads; they do not replace reading a sample against "
            "the source. S4 is reported as a lexical-semantic proxy against a "
            "strong reference, not as gold truth.",
            "",
            "## Mac and Windows comparison",
            "",
            "Run this command once per machine and compare the generated summaries "
            "or combine their `results.json` files with the `summary` command. "
            "Tier 2 is intentionally reported separately from the Tier 1 decision.",
            "",
            "## S6",
            "",
        ]
    )
    s6_rows = []
    for model in result.get("models", []):
        s6 = model.get("s6")
        if not s6 or s6.get("status") == "error":
            continue
        det = s6.get("determinism", {})
        recovery = s6.get("recovery", {})
        s6_rows.append(
            f"- `{model['requested']}` on `{result.get('machine', 'unknown')}`: "
            f"deterministic={'yes' if det.get('byte_identical') else 'no'}, "
            f"recovery={'converged' if recovery.get('converged') else 'failed'}"
        )
    lines.extend(s6_rows or ["S6 was not completed in this run."])
    return "\n".join(lines) + "\n"


def load_result(path: Path) -> dict[str, Any]:
    if path.is_dir():
        path = path / "results.json"
    value = load_json(path)
    if value.get("schema") != SCHEMA:
        raise BenchmarkError(f"unsupported benchmark results schema in {path}")
    return value


def rescore_run(run_dir: Path, audit_path: Path | None = None, recall_review_path: Path | None = None) -> Path:
    result = load_result(run_dir)
    fixtures, _ = load_fixtures(ROOT)
    audit = _load_audit(audit_path)
    review = _load_audit(recall_review_path)
    for model in result.get("models", []):
        for suite in model.get("suites", {}).values():
            for item in suite.get("fixtures", []):
                fixture = fixtures[item["fixture"]]
                attempts = item.get("attempts", [])
                if not attempts:
                    continue
                for attempt in attempts:
                    raw_file = attempt.get("raw_file")
                    if not raw_file:
                        continue
                    text = (run_dir / raw_file).read_text(encoding="utf-8")
                    attempt["validation"] = {
                        key: value
                        for key, value in validate_response(text, fixture.identifier).items()
                        if key != "cleaned_body"
                    }
                rescored = _response_score(
                    fixture,
                    attempts,
                    _audit_for(audit, model["requested"], fixture.identifier),
                    _recall_review_for(review, model["requested"], fixture.identifier),
                )
                item.update({key: value for key, value in rescored.items() if key not in {"fixture", "source_bytes", "expected_records", "attempts"}})
            suite["metrics"] = _aggregate_metrics(
                suite.get("fixtures", []),
                suite.get("metrics", {}).get("budget_s"),
            )
    output = run_dir / "rescored.json"
    write_json(output, result)
    (run_dir / "rescored-summary.md").write_text(render_summary(result), encoding="utf-8")
    return output


def render_combined_summary(paths: Sequence[Path]) -> str:
    results = [load_result(path) for path in paths]
    if len(results) == 1:
        return render_summary(results[0])
    lines = [
        "Recommendation: choose only among models that pass S1, S2, and the manually audited S3 on the target machine; the machine-specific rows below are the evidence.",
        "",
        "# Local model benchmark comparison",
        "",
        "| Requested model | Tier | Mac | Windows |",
        "|---|---|---|---|",
    ]
    by_model: dict[str, dict[str, dict[str, Any]]] = {}
    for result in results:
        for row in _model_summary_rows(result):
            by_model.setdefault(row["requested"], {})[result.get("machine", "unknown")] = row
    for name, machines in sorted(by_model.items()):
        tier = next(iter(machines.values()))["tier"]
        cells = []
        for machine in ("mac", "windows"):
            row = machines.get(machine)
            if not row:
                cells.append("—")
            elif not row["available"]:
                cells.append("unavailable")
            else:
                s3 = "PASS" if row["s3"] is True else str(row["s3"]).replace("_", " ")
                recall = "—" if row["recall"] is None else f"{row['recall'] * 100:.1f}%"
                cells.append(f"S1 {'P' if row['s1'] else 'F'} / S2 {'P' if row['s2'] else 'F'} / S3 {s3}; recall {recall}; {_format_seconds(row['wall'])}")
        lines.append(f"| `{name}` | {tier} | {cells[0]} | {cells[1]} |")
    lines.extend(["", "Tier 1 is the cross-machine decision set. Tier 2 is Mac-only and is reported separately in each run.", ""])
    return "\n".join(lines)


def cmd_inventory(args: argparse.Namespace) -> int:
    client = OllamaClient(args.ollama_url, args.request_timeout)
    inventory = client.inventory()
    if args.json:
        print(canonical_json({"models": inventory}))
    else:
        print("MODEL\tSIZE\tPARAMETERS\tQUANTIZATION")
        for model in inventory:
            details = model.get("details", {}) or {}
            size = model.get("size")
            size_text = f"{float(size) / (1024**3):.2f} GiB" if isinstance(size, (int, float)) else "?"
            print(f"{model.get('name', '?')}\t{size_text}\t{details.get('parameter_size', '?')}\t{details.get('quantization_level', '?')}")
    return 0


def _pull_progress_message(model: str, event: Mapping[str, Any]) -> tuple[str, tuple[Any, ...]]:
    status = str(event.get("status", "working"))
    completed = event.get("completed")
    total = event.get("total")
    if (
        isinstance(completed, (int, float))
        and isinstance(total, (int, float))
        and total > 0
    ):
        percent = max(0.0, min(100.0, float(completed) / float(total) * 100.0))
        message = (
            f"{model}: {status} {percent:.0f}% "
            f"({_format_bytes(completed)}/{_format_bytes(total)})"
        )
        return message, (status, int(percent // 5))
    return f"{model}: {status}", (status,)


def cmd_install(args: argparse.Namespace) -> int:
    global _PROGRESS_STARTED_AT
    _PROGRESS_STARTED_AT = time.perf_counter()
    models = _default_model_names(args.tier)
    client = OllamaClient(args.ollama_url, args.request_timeout)
    _progress(f"installing {len(models)} {args.tier} Ollama models")
    for model in models:
        last_key: tuple[Any, ...] | None = None

        def report(event: Mapping[str, Any], model: str = model) -> None:
            nonlocal last_key
            message, key = _pull_progress_message(model, event)
            if key != last_key:
                last_key = key
                _progress(message)

        _progress(f"{model}: starting pull")
        client.pull(model, on_progress=report)
        _progress(f"{model}: installed")
    _progress(f"installed all {args.tier} models")
    return 0


def build_parser() -> argparse.ArgumentParser:
    formatter = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark local Ollama models for source-faithful CSV fact extraction. "
            "The runner validates responses, retries malformed generations, records "
            "timings, and preserves raw output."
        ),
        epilog="""Examples:
  python3 benchmark/benchmark.py inventory
  python3 benchmark/benchmark.py install --tier tier1
  python3 benchmark/benchmark.py run --suite smoke --skip-unavailable
  python3 benchmark/benchmark.py run --suite quick
  python3 benchmark/benchmark.py run --suite full --skip-unavailable
  python3 benchmark/benchmark.py score benchmark/results/<run-id> --audit audit.json
  python3 benchmark/benchmark.py summary benchmark/results/<mac>/results.json \\
      benchmark/results/<windows>/results.json

Use '<command> --help' for the complete options of a command. Smoke runs one
compact fixture with no time cutoff. The full suite runs quick triage first and
only continues with models that pass it.""",
        formatter_class=formatter,
    )
    sub = parser.add_subparsers(dest="command", required=True, title="commands")
    inventory = sub.add_parser(
        "inventory",
        help="list installed Ollama models",
        description="Query Ollama and display installed model tags, sizes, parameter counts, and quantization.",
        formatter_class=formatter,
    )
    inventory.add_argument(
        "--ollama-url",
        default=OLLAMA_URL,
        metavar="URL",
        help=f"Ollama server URL (default: {OLLAMA_URL})",
    )
    inventory.add_argument(
        "--request-timeout",
        type=float,
        default=30.0,
        metavar="SECONDS",
        help="HTTP timeout for the inventory request (default: 30)",
    )
    inventory.add_argument(
        "--json",
        action="store_true",
        help="emit the inventory as machine-readable JSON",
    )

    install = sub.add_parser(
        "install",
        help="install the model tags for a tier through Ollama",
        description=(
            "Pull every model in the selected tier through Ollama's local HTTP API. "
            "Ollama must be installed and running, and the host must have network access."
        ),
        formatter_class=formatter,
    )
    install.add_argument(
        "--tier",
        choices=("tier1", "tier2"),
        default="tier1",
        metavar="{tier1,tier2}",
        help="model tier to install (default: tier1)",
    )
    install.add_argument(
        "--ollama-url",
        default=OLLAMA_URL,
        metavar="URL",
        help=f"Ollama server URL (default: {OLLAMA_URL})",
    )
    install.add_argument(
        "--request-timeout",
        type=float,
        default=3600.0,
        metavar="SECONDS",
        help="timeout for the streaming pull request (default: 3600)",
    )

    run = sub.add_parser(
        "run",
        help="run smoke, quick, or full benchmark suites",
        description=(
            "Run each selected model per fixture. Before testing, all requested "
            "models are reported as FOUND or UNAVAILABLE. Missing models abort the "
            "run unless --skip-unavailable is supplied."
        ),
        formatter_class=formatter,
    )
    run.add_argument(
        "--suite",
        choices=("smoke", "quick", "full"),
        default="full",
        metavar="{smoke,quick,full}",
        help="suite to run; smoke is one no-budget fixture, full runs quick triage first (default: full)",
    )
    run.add_argument(
        "--tier",
        choices=("tier1", "tier2"),
        default="tier1",
        metavar="{tier1,tier2}",
        help="default model tier: tier1 is cross-machine, tier2 is Mac-only (default: tier1)",
    )
    run.add_argument(
        "--include-tier2",
        action="store_true",
        help="run both Tier 1 and Tier 2 models; overrides --tier",
    )
    run.add_argument(
        "--models",
        metavar="MODEL[,MODEL...]",
        help="comma-separated model tags to run; overrides the tier selection",
    )
    run.add_argument(
        "--model-map",
        action="append",
        default=[],
        metavar="REQUESTED=ACTUAL",
        help="record a replacement Ollama tag; may be supplied multiple times",
    )
    run.add_argument(
        "--skip-unavailable",
        action="store_true",
        help="continue with installed models after preflight; default is to abort",
    )
    run.add_argument(
        "--ollama-url",
        default=OLLAMA_URL,
        metavar="URL",
        help=f"Ollama server URL (default: {OLLAMA_URL})",
    )
    run.add_argument(
        "--request-timeout",
        type=float,
        default=600.0,
        metavar="SECONDS",
        help="timeout for each streaming generation request (default: 600)",
    )
    run.add_argument(
        "--retries",
        type=int,
        default=1,
        metavar="N",
        help="automatic correction retries after a rejected response (default: 1)",
    )
    run.add_argument(
        "--quick-budget",
        type=float,
        default=240.0,
        metavar="SECONDS",
        help="quick-suite budget per model (default: 240)",
    )
    run.add_argument(
        "--full-budget",
        type=float,
        default=300.0,
        metavar="SECONDS",
        help="full-suite budget per model, including S6 when reached (default: 300)",
    )
    run.add_argument(
        "--audit",
        metavar="PATH",
        help="manual S3 contamination-audit JSON to apply while scoring",
    )
    run.add_argument(
        "--recall-review",
        metavar="PATH",
        help="optional S4 human match-override JSON",
    )
    run.add_argument(
        "--output",
        metavar="PATH",
        help="empty directory for this run (default: benchmark/results/<timestamp>-<machine>)",
    )

    score = sub.add_parser(
        "score",
        help="re-score captured raw responses",
        description=(
            "Re-validate and re-score an existing run without calling Ollama. "
            "Writes rescored.json and rescored-summary.md beside the original results."
        ),
        formatter_class=formatter,
    )
    score.add_argument(
        "run_dir",
        type=Path,
        help="run directory or its results.json file",
    )
    score.add_argument(
        "--audit",
        type=Path,
        metavar="PATH",
        help="manual S3 contamination-audit JSON",
    )
    score.add_argument(
        "--recall-review",
        type=Path,
        metavar="PATH",
        help="optional S4 human match-override JSON",
    )

    summary = sub.add_parser(
        "summary",
        help="render a Markdown report",
        description=(
            "Render one result file, or compare Mac and Windows result files. "
            "With multiple files, the report places machine results side by side."
        ),
        formatter_class=formatter,
    )
    summary.add_argument(
        "results",
        nargs="+",
        type=Path,
        metavar="RESULTS_JSON",
        help="one or more results.json files or run directories",
    )
    summary.add_argument(
        "--output",
        type=Path,
        metavar="PATH",
        help="write Markdown to PATH instead of stdout",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "inventory":
            return cmd_inventory(args)
        if args.command == "install":
            return cmd_install(args)
        if args.command == "run":
            if args.retries < 0:
                raise BenchmarkError("--retries must be non-negative")
            output = run_benchmark(args)
            if output is None:
                print("No benchmark results written.")
            else:
                print(f"Wrote benchmark run to {output}")
            return 0
        if args.command == "score":
            output = rescore_run(args.run_dir, args.audit, args.recall_review)
            print(f"Wrote rescored results to {output}")
            return 0
        if args.command == "summary":
            rendered = render_combined_summary(args.results)
            if args.output:
                args.output.write_text(rendered, encoding="utf-8")
                print(f"Wrote summary to {args.output}")
            else:
                print(rendered, end="")
            return 0
    except BenchmarkError as exc:
        print(f"benchmark: error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
