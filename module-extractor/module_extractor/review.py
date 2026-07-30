"""Review overlay application without evidence mutation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .contracts import REQUIRED_FIELDS
from .errors import ExtractorError


def resolved_aliases(review: Mapping[str, Any]) -> dict[str, str]:
    aliases = {item["alias"]: item["canonical_id"] for item in review["aliases"]}
    resolved: dict[str, str] = {}
    for alias, target in aliases.items():
        visited = {alias}
        while target in aliases:
            if target in visited:
                raise ExtractorError(f"review alias cycle includes {alias}")
            visited.add(target)
            target = aliases[target]
        resolved[alias] = target
    return resolved


def canonicalize_evidence_aliases(
    evidence: Mapping[str, Any], review: Mapping[str, Any]
) -> dict[str, Any]:
    """Rewrite in-memory conceptual identities before reconciliation."""
    result = deepcopy(dict(evidence))
    aliases = resolved_aliases(review)
    if not aliases:
        return result
    for observation in result["content_observations"]:
        observation["concept_id"] = aliases.get(
            observation["concept_id"], observation["concept_id"]
        )
        observation["references"] = [
            aliases.get(reference, reference)
            for reference in observation["references"]
        ]
    for map_result in result["map_results"]:
        for node in map_result["nodes"]:
            node["concept_id"] = aliases.get(
                node["concept_id"], node["concept_id"]
            )
        for passage in map_result["passages"]:
            passage["from"] = aliases.get(passage["from"], passage["from"])
            passage["to"] = aliases.get(passage["to"], passage["to"])
    for uncertainty in result["uncertainties"]:
        uncertainty["target_id"] = aliases.get(
            uncertainty["target_id"], uncertainty["target_id"]
        )
    return result


def _alias_map(
    review: Mapping[str, Any], object_ids: set[str]
) -> dict[str, str]:
    aliases = resolved_aliases(review)
    for alias, target in aliases.items():
        if alias in object_ids and alias != target:
            raise ExtractorError(f"alias was not reconciled into its target: {alias}")
        if target not in object_ids:
            raise ExtractorError(f"alias {alias} targets unknown ID {target}")
    return aliases


def _resolve(value: str, aliases: Mapping[str, str]) -> str:
    while value in aliases:
        value = aliases[value]
    return value


def apply_review(
    records: Sequence[Mapping[str, Any]],
    topology: Mapping[str, Any],
    conflicts: Sequence[Mapping[str, Any]],
    uncertainties: Sequence[Mapping[str, Any]],
    review: Mapping[str, Any],
) -> dict[str, Any]:
    canonical_records = deepcopy(list(records))
    canonical_topology = deepcopy(dict(topology))
    record_by_id = {record["id"]: record for record in canonical_records}
    edge_by_id = {
        edge["id"]: edge for edge in canonical_topology["passages"]
    }
    node_by_id = {node["id"]: node for node in canonical_topology["nodes"]}
    object_ids = set(record_by_id) | set(edge_by_id) | set(node_by_id)
    aliases = _alias_map(review, object_ids)
    applied_values: set[tuple[str, str]] = set()
    for operation in review["values"]:
        object_id = _resolve(operation["object_id"], aliases)
        field = operation["field"]
        if object_id in record_by_id:
            record_by_id[object_id]["fields"][field] = operation["value"]
        elif object_id in edge_by_id:
            edge_by_id[object_id]["facets"][field] = operation["value"]
            if field in edge_by_id[object_id]["conflict_fields"]:
                edge_by_id[object_id]["conflict_fields"].remove(field)
        elif object_id in node_by_id:
            if field not in {"labels", "titles"}:
                raise ExtractorError(
                    f"review cannot author topology node field {field!r}"
                )
            node_by_id[object_id][field] = operation["value"]
        else:
            raise ExtractorError(f"review value targets unknown ID: {object_id}")
        applied_values.add((object_id, field))
    unresolved = []
    for conflict in conflicts:
        object_id = _resolve(conflict["object_id"], aliases)
        if (object_id, conflict["field"]) not in applied_values:
            unresolved.append(dict(conflict))
    uncertainty_ids = {item["id"] for item in uncertainties}
    accepted_ids = {
        item["uncertainty_id"] for item in review["accepted_uncertainties"]
    }
    unknown_accepted = sorted(accepted_ids - uncertainty_ids)
    if unknown_accepted:
        raise ExtractorError(
            "review accepts unknown uncertainties: " + ", ".join(unknown_accepted)
        )
    pending_uncertainties = [
        dict(item) for item in uncertainties if item["id"] not in accepted_ids
    ]
    for record in canonical_records:
        record["references"] = sorted(
            {_resolve(reference, aliases) for reference in record["references"]}
        )
    return {
        "records": sorted(canonical_records, key=lambda item: item["id"]),
        "topology": canonical_topology,
        "aliases": aliases,
        "unresolved_conflicts": sorted(
            unresolved, key=lambda item: item["id"]
        ),
        "pending_uncertainties": sorted(
            pending_uncertainties, key=lambda item: item["id"]
        ),
        "accepted_uncertainties": sorted(accepted_ids),
    }


def release_gate(
    reviewed: Mapping[str, Any],
    coverage: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    if not coverage.get("complete"):
        errors.append("coverage is incomplete")
    if reviewed["unresolved_conflicts"]:
        errors.append(
            f"{len(reviewed['unresolved_conflicts'])} blocking conflicts remain"
        )
    if reviewed["pending_uncertainties"]:
        errors.append(
            f"{len(reviewed['pending_uncertainties'])} uncertainties are unreviewed"
        )
    records = reviewed["records"]
    identifiers = [record["id"] for record in records]
    if len(identifiers) != len(set(identifiers)):
        errors.append("canonical record IDs are duplicated")
    for record in records:
        record_type = record["record_type"]
        if record_type not in REQUIRED_FIELDS:
            errors.append(f"{record['id']} has no canonical record type")
            continue
        for field in REQUIRED_FIELDS[record_type]:
            if field not in record["fields"]:
                errors.append(f"{record['id']} is missing required field {field}")
    object_ids = (
        set(identifiers)
        | {node["id"] for node in reviewed["topology"]["nodes"]}
        | {edge["id"] for edge in reviewed["topology"]["passages"]}
    )
    for record in records:
        for reference in record["references"]:
            if reference not in object_ids:
                errors.append(f"{record['id']} references missing ID {reference}")
    node_ids = {node["id"] for node in reviewed["topology"]["nodes"]}
    for edge in reviewed["topology"]["passages"]:
        if edge["from"] not in node_ids or edge["to"] not in node_ids:
            errors.append(f"{edge['id']} has a broken topology endpoint")
    return sorted(set(errors))
