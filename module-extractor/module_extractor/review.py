"""Review overlay application without evidence mutation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .contracts import (
    ACTOR_REFERENCE_FIELDS,
    IDENTIFIER_KEYS,
    PLACE_REFERENCE_FIELDS,
    REQUIRED_FIELDS,
    SITUATION_REFERENCE_FIELDS,
)
from .errors import ExtractorError


# A reviewer cites the IDs visible in the source evidence. Canonical IDs are
# assigned by policy, so an authored reference is resolved the same way an
# extracted one is.
REFERENCE_VALUE_FIELDS = (
    PLACE_REFERENCE_FIELDS | ACTOR_REFERENCE_FIELDS | SITUATION_REFERENCE_FIELDS
)
NESTED_VALUE_FIELDS = {
    "actor_reactions",
    "participants",
    "possible_effects",
    "relationships",
}


def _canonical_value(
    field: str, value: Any, mapping: Mapping[str, str]
) -> Any:
    if field == "topology_node" and isinstance(value, str):
        return mapping.get(value, value)
    if field in REFERENCE_VALUE_FIELDS and isinstance(value, list):
        return [
            mapping.get(item, item) if isinstance(item, str) else item
            for item in value
        ]
    if field in NESTED_VALUE_FIELDS and isinstance(value, list):
        resolved = []
        for item in value:
            if not isinstance(item, dict):
                resolved.append(item)
                continue
            resolved.append(
                {
                    key: mapping.get(entry, entry)
                    if key in IDENTIFIER_KEYS and isinstance(entry, str)
                    else entry
                    for key, entry in item.items()
                }
            )
        return resolved
    return value


def resolved_aliases(review: Mapping[str, Any]) -> dict[str, str]:
    targets: dict[str, set[str]] = {}
    for item in review["aliases"]:
        targets.setdefault(item["alias"], set()).add(item["target_id"])
    ambiguous = {
        alias: sorted(values) for alias, values in targets.items() if len(values) > 1
    }
    if ambiguous:
        raise ExtractorError(f"review has ambiguous aliases: {ambiguous}")
    aliases = {alias: next(iter(values)) for alias, values in targets.items()}
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
    identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    canonical_records = deepcopy(list(records))
    canonical_topology = deepcopy(dict(topology))
    record_by_id = {record["id"]: record for record in canonical_records}
    edge_by_id = {
        edge["id"]: edge for edge in canonical_topology["passages"]
    }
    node_by_id = {node["id"]: node for node in canonical_topology["nodes"]}
    object_ids = set(record_by_id) | set(edge_by_id) | set(node_by_id)
    aliases = (
        dict(identity["aliases"])
        if identity is not None
        else _alias_map(review, object_ids)
    )
    identity_mapping = dict(identity["mapping"]) if identity is not None else aliases
    identity_errors = list(identity["errors"]) if identity is not None else []
    applied_values: set[tuple[str, str]] = set()
    for operation in review["values"]:
        object_id = identity_mapping.get(operation["object_id"], operation["object_id"])
        object_id = _resolve(object_id, aliases)
        field = operation["field"]
        if object_id in record_by_id:
            record_by_id[object_id]["fields"][field] = _canonical_value(
                field, operation["value"], identity_mapping
            )
        elif object_id in edge_by_id:
            edge_by_id[object_id]["facets"][field] = operation["value"]
            if field in edge_by_id[object_id]["conflict_fields"]:
                edge_by_id[object_id]["conflict_fields"].remove(field)
        elif object_id in node_by_id:
            if field not in {"labels", "titles", "classification"}:
                identity_errors.append(
                    f"review cannot author topology node field {field!r}"
                )
                continue
            node_by_id[object_id][field] = operation["value"]
        else:
            identity_errors.append(
                f"review value targets no current-run object: {object_id}"
            )
            continue
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
        identity_errors.append(
            "review accepts no current-run uncertainties: "
            + ", ".join(unknown_accepted)
        )
        accepted_ids -= set(unknown_accepted)
    pending_uncertainties = [
        dict(item) for item in uncertainties if item["id"] not in accepted_ids
    ]
    for record in canonical_records:
        record["references"] = sorted(
            {_resolve(reference, aliases) for reference in record["references"]}
        )
    composites = []
    for item in review.get("topology_composites", []):
        composites.append(
            {
                **item,
                "topology_node": identity_mapping.get(
                    item["topology_node"], item["topology_node"]
                ),
                "place_ids": sorted(
                    {
                        identity_mapping.get(place_id, place_id)
                        for place_id in item["place_ids"]
                    }
                ),
            }
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
        "identity_errors": sorted(set(identity_errors)),
        "unresolved_duplicate_candidates": (
            list(identity["unresolved_high_confidence"])
            if identity is not None
            else []
        ),
        "keyed_area_conflicts": (
            list(identity["keyed_area_conflicts"]) if identity is not None else []
        ),
        "topology_composites": sorted(
            composites, key=lambda item: item["topology_node"]
        ),
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
    if reviewed.get("unresolved_duplicate_candidates"):
        errors.append(
            f"{len(reviewed['unresolved_duplicate_candidates'])} high-confidence "
            "duplicate candidates are unresolved"
        )
    errors.extend(reviewed.get("identity_errors", []))
    errors.extend(reviewed.get("topology_errors", []))
    errors.extend(reviewed.get("record_errors", []))
    for conflict in reviewed.get("keyed_area_conflicts", []):
        errors.append(
            f"keyed area {conflict['keyed_area']} is claimed by canonical records: "
            + ", ".join(conflict["canonical_ids"])
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
    for alias, target in reviewed.get("aliases", {}).items():
        if target not in object_ids:
            errors.append(f"alias {alias} targets missing canonical ID {target}")
    for record in records:
        for reference in record["references"]:
            if reference not in object_ids:
                errors.append(f"{record['id']} references missing ID {reference}")
    node_ids = {node["id"] for node in reviewed["topology"]["nodes"]}
    for edge in reviewed["topology"]["passages"]:
        if edge["from"] not in node_ids or edge["to"] not in node_ids:
            errors.append(f"{edge['id']} has a broken topology endpoint")
    return sorted(set(errors))
