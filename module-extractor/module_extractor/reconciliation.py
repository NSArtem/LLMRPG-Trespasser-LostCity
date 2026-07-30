"""Observation-preserving record and topology reconciliation."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence

from .errors import ExtractorError
from .util import canonical_json_bytes


SCALAR_FACETS = (
    "kind",
    "medium",
    "elevation",
    "traversal_direction",
)
SET_FACETS = ("barriers", "features", "conditions")


def _value_key(value: Any) -> bytes:
    return canonical_json_bytes(value)


def reconcile_records(
    observations: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for observation in observations:
        grouped[observation["concept_id"]].append(observation)
    records: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for concept_id in sorted(grouped):
        group = sorted(grouped[concept_id], key=lambda item: item["observation_id"])
        types = sorted(set(item["record_type"] for item in group))
        if len(types) != 1:
            conflicts.append(
                {
                    "id": f"conflict.{concept_id}.record-type",
                    "object_id": concept_id,
                    "field": "record_type",
                    "values": types,
                    "blocking": True,
                }
            )
        fields: dict[str, Any] = {}
        field_observations: dict[str, list[dict[str, Any]]] = {}
        for field in sorted(
            {key for observation in group for key in observation["fields"]}
        ):
            values = []
            for observation in group:
                if field not in observation["fields"]:
                    continue
                value = observation["fields"][field]
                values.append(
                    {
                        "value": value,
                        "source_pages": observation["source_pages"],
                        "confidence": observation["confidence"],
                        "pack_id": observation["pack_id"],
                        "observation_id": observation["observation_id"],
                    }
                )
            field_observations[field] = values
            concrete: dict[bytes, Any] = {}
            for item in values:
                if item["value"] is not None:
                    concrete[_value_key(item["value"])] = item["value"]
            if len(concrete) == 1:
                fields[field] = next(iter(concrete.values()))
            elif len(concrete) > 1:
                conflict_id = f"conflict.{concept_id}.{field.replace('_', '-')}"
                conflicts.append(
                    {
                        "id": conflict_id,
                        "object_id": concept_id,
                        "field": field,
                        "values": [concrete[key] for key in sorted(concrete)],
                        "blocking": True,
                    }
                )
        records.append(
            {
                "id": concept_id,
                "record_type": types[0] if len(types) == 1 else None,
                "fields": fields,
                "field_observations": field_observations,
                "references": sorted(
                    {
                        reference
                        for observation in group
                        for reference in observation["references"]
                    }
                ),
                "source_pages": sorted(
                    {
                        page
                        for observation in group
                        for page in observation["source_pages"]
                    }
                ),
                "observation_ids": [
                    observation["observation_id"] for observation in group
                ],
            }
        )
    return records, conflicts


def _relative_direction(
    direction: str | None, start: str, canonical_start: str
) -> str | None:
    if direction not in {"from_to", "to_from"} or start == canonical_start:
        return direction
    return "to_from" if direction == "from_to" else "from_to"


def reconcile_topology(
    map_results: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    node_groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    edge_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for result in map_results:
        for node in result["nodes"]:
            node_groups[node["concept_id"]].append(node)
        for raw in result["passages"]:
            start, end = sorted((raw["from"], raw["to"]))
            observation = dict(raw)
            observation["facets"] = dict(raw["facets"])
            observation["facets"]["traversal_direction"] = _relative_direction(
                raw["facets"].get("traversal_direction"), raw["from"], start
            )
            edge_groups[(start, end)].append(observation)
    nodes = []
    for identifier in sorted(node_groups):
        observations = sorted(
            node_groups[identifier], key=lambda item: item["observation_id"]
        )
        nodes.append(
            {
                "id": identifier,
                "labels": sorted(set(item["label"] for item in observations)),
                "titles": sorted(
                    set(item["title"] for item in observations if item.get("title"))
                ),
                "source_pages": sorted(
                    {page for item in observations for page in item["source_pages"]}
                ),
                "observations": observations,
            }
        )
    node_ids = {node["id"] for node in nodes}
    passages = []
    conflicts = []
    for endpoints in sorted(edge_groups):
        start, end = endpoints
        if start not in node_ids or end not in node_ids:
            raise ExtractorError("topology passage references a missing canonical node")
        observations = sorted(
            edge_groups[endpoints], key=lambda item: item["observation_id"]
        )
        edge_id = f"edge-{start}-{end}"
        facets: dict[str, Any] = {}
        facet_observations: dict[str, list[dict[str, Any]]] = {}
        conflict_fields = []
        for field in SCALAR_FACETS:
            values = []
            concrete: set[Any] = set()
            for observation in observations:
                value = observation["facets"].get(field)
                values.append(
                    {
                        "value": value,
                        "source_pages": observation["source_pages"],
                        "confidence": observation["confidence"],
                        "pack_id": observation["pack_id"],
                        "observation_id": observation["observation_id"],
                    }
                )
                if value is not None:
                    concrete.add(value)
            facet_observations[field] = values
            if len(concrete) == 1:
                facets[field] = next(iter(concrete))
            elif len(concrete) > 1:
                conflict_fields.append(field)
                conflicts.append(
                    {
                        "id": f"conflict.{edge_id}.{field.replace('_', '-')}",
                        "object_id": edge_id,
                        "field": field,
                        "values": sorted(concrete),
                        "blocking": True,
                    }
                )
        for field in SET_FACETS:
            values = []
            merged: set[str] = set()
            for observation in observations:
                value = observation["facets"].get(field, [])
                merged.update(value)
                values.append(
                    {
                        "value": value,
                        "source_pages": observation["source_pages"],
                        "confidence": observation["confidence"],
                        "pack_id": observation["pack_id"],
                        "observation_id": observation["observation_id"],
                    }
                )
            facets[field] = sorted(merged)
            facet_observations[field] = values
        passages.append(
            {
                "id": edge_id,
                "from": start,
                "to": end,
                "facets": facets,
                "facet_observations": facet_observations,
                "source_pages": sorted(
                    {page for item in observations for page in item["source_pages"]}
                ),
                "observation_ids": [
                    observation["observation_id"] for observation in observations
                ],
                "conflict_fields": sorted(conflict_fields),
            }
        )
    return {"nodes": nodes, "passages": passages}, conflicts
