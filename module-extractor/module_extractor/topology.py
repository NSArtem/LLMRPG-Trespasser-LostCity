"""Operational place-to-topology resolution and release validation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .identity import keyed_area


# Typed place references are resolved against canonical records in
# `operations.py`; this module owns place-to-topology resolution only.
PLACE_REFERENCE_TYPES = {
    "actor_references": "actor",
    "situation_references": "situation",
    "procedure_references": "procedure",
    "knowledge_references": "knowledge",
}
NODE_CLASSIFICATIONS = {"place", "waypoint", "boundary"}
ELEVATIONS = {"level", "up", "down", "vertical", "variable"}
DIRECTIONS = {"both", "from_to", "to_from", "conditional"}
VISIBILITIES = {"visible", "hidden"}
PLACE_LIST_FIELDS = {
    "contents",
    "hidden",
    "triggers",
    "hazards",
    "resources",
    "occupants",
}


def _place_areas(record: Mapping[str, Any]) -> set[str]:
    fields = record["fields"]
    areas: set[str] = set()
    for name in ("keyed_area", "area_number", "map_label", "topology_label"):
        value = fields.get(name)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            area = keyed_area(f"area {value}")
            if area is not None:
                areas.add(area)
    for value in (fields.get("title"), record["id"]):
        if isinstance(value, str):
            area = keyed_area(value)
            if area is not None:
                areas.add(area)
    return areas


def _node_label_areas(node: Mapping[str, Any]) -> set[str]:
    """Areas printed on the map itself, ignoring the arbitrary node ID."""
    areas: set[str] = set()
    labels = [
        node[name]
        for name in ("label", "title")
        if isinstance(node.get(name), str)
    ]
    for value in [*labels, *node.get("labels", []), *node.get("titles", [])]:
        area = keyed_area(f"area {value}")
        if area is not None:
            areas.add(area)
    return areas


def _node_areas(node: Mapping[str, Any]) -> set[str]:
    areas = _node_label_areas(node)
    area = keyed_area(f"area {node['id']}")
    if area is not None:
        areas.add(area)
    return areas


def resolve_operational_topology(
    reviewed: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve explicit/unique joins and return a validated reviewed copy."""
    result = deepcopy(dict(reviewed))
    records = result["records"]
    topology = result["topology"]
    places = [record for record in records if record["record_type"] == "location"]
    nodes = {node["id"]: node for node in topology["nodes"]}
    node_areas = {
        node_id: _node_areas(node) for node_id, node in nodes.items()
    }
    node_label_areas = {
        node_id: _node_label_areas(node) for node_id, node in nodes.items()
    }
    errors: list[str] = []
    links: list[dict[str, Any]] = []

    for place in sorted(places, key=lambda item: item["id"]):
        fields = place["fields"]
        for field in ("title", "first_impression"):
            if not isinstance(fields.get(field), str) or not fields[field].strip():
                errors.append(f"{place['id']} has invalid {field}")
        for field in sorted(PLACE_LIST_FIELDS):
            value = fields.get(field)
            if value is not None and (
                not isinstance(value, list)
                or not value
                or any(
                    not isinstance(item, str) or not item.strip()
                    for item in value
                )
            ):
                errors.append(f"{place['id']} has invalid {field}")
        discoverable = fields.get("discoverable")
        if discoverable is not None and (
            not isinstance(discoverable, list)
            or not discoverable
            or any(
                not isinstance(item, dict)
                or set(item) != {"information", "condition"}
                or any(
                    not isinstance(item[name], str) or not item[name].strip()
                    for name in ("information", "condition")
                )
                for item in discoverable
            )
        ):
            errors.append(f"{place['id']} has invalid discoverable details")
        for field in PLACE_REFERENCE_TYPES:
            value = fields.get(field)
            if value is not None and (
                not isinstance(value, list)
                or not value
                or any(not isinstance(item, str) for item in value)
                or len(value) != len(set(value))
            ):
                errors.append(f"{place['id']} has invalid {field}")
        resolution = "evidence"
        if "topology_node" in fields:
            node_id = fields["topology_node"]
            if node_id is None:
                links.append(
                    {
                        "place_id": place["id"],
                        "topology_node": None,
                        "resolution": "explicit-unmapped",
                    }
                )
                continue
            if not isinstance(node_id, str):
                errors.append(f"{place['id']} has invalid topology_node")
                continue
            if node_id not in nodes:
                errors.append(
                    f"{place['id']} points to missing topology node {node_id}"
                )
                continue
        elif place["id"] in nodes:
            node_id = place["id"]
            fields["topology_node"] = node_id
            resolution = "shared-identity"
        else:
            areas = _place_areas(place)
            candidates = sorted(
                node_id
                for node_id, candidate_areas in node_areas.items()
                if areas & candidate_areas
            )
            if len(candidates) > 1:
                # A node whose printed label carries the area key outranks one
                # that only matched through its arbitrary ID slug.
                labelled = [
                    candidate
                    for candidate in candidates
                    if areas & node_label_areas[candidate]
                ]
                if len(labelled) == 1:
                    candidates = labelled
            if len(candidates) > 1:
                # A keyed place card joins to a mapped place, not to a
                # waypoint or boundary that merely cites the same area key.
                place_candidates = [
                    candidate
                    for candidate in candidates
                    if nodes[candidate].get("classification") == "place"
                ]
                if len(place_candidates) == 1:
                    candidates = place_candidates
            if len(candidates) == 1:
                node_id = candidates[0]
                fields["topology_node"] = node_id
                resolution = "unique-keyed-area"
            elif len(candidates) > 1:
                errors.append(
                    f"{place['id']} has an ambiguous topology join: "
                    + ", ".join(candidates)
                )
                continue
            elif areas:
                errors.append(
                    f"{place['id']} is keyed but has no matching topology node"
                )
                continue
            else:
                errors.append(
                    f"{place['id']} requires an evidence-backed topology_node "
                    "or an explicit null unmapped decision"
                )
                continue
        links.append(
            {
                "place_id": place["id"],
                "topology_node": node_id,
                "resolution": resolution,
            }
        )

    place_by_id = {place["id"]: place for place in places}
    mapped: dict[str, list[str]] = {}
    for link in links:
        if link["topology_node"] is not None:
            mapped.setdefault(link["topology_node"], []).append(link["place_id"])

    composite_by_node = {
        item["topology_node"]: item
        for item in result.get("topology_composites", [])
    }
    for node_id, composite in sorted(composite_by_node.items()):
        if node_id not in nodes:
            errors.append(f"reviewed composite targets missing node {node_id}")
        missing_places = sorted(set(composite["place_ids"]) - set(place_by_id))
        if missing_places:
            errors.append(
                f"reviewed composite {node_id} names missing places: "
                + ", ".join(missing_places)
            )
        actual = sorted(mapped.get(node_id, []))
        if actual != sorted(composite["place_ids"]):
            errors.append(
                f"reviewed composite {node_id} does not match mapped places"
            )

    for node_id, node in sorted(nodes.items()):
        classification = node.get("classification")
        mapped_places = sorted(mapped.get(node_id, []))
        if classification is None:
            errors.append(f"topology node {node_id} needs a classification")
        elif classification not in NODE_CLASSIFICATIONS:
            errors.append(
                f"topology node {node_id} has invalid classification "
                f"{classification!r}"
            )
        elif classification == "place" and not mapped_places:
            errors.append(f"operational topology node {node_id} has no place")
        elif classification in {"waypoint", "boundary"} and mapped_places:
            errors.append(
                f"non-place topology node {node_id} maps to "
                + ", ".join(mapped_places)
            )
        if len(mapped_places) > 1 and node_id not in composite_by_node:
            errors.append(
                f"topology node {node_id} maps to multiple places without a "
                "reviewed composite rule"
            )

    node_ids = set(nodes)
    for edge in topology["passages"]:
        if edge["from"] not in node_ids or edge["to"] not in node_ids:
            errors.append(f"{edge['id']} has a broken topology endpoint")
        if edge["from"] == edge["to"]:
            errors.append(f"{edge['id']} is a self-referential topology passage")
        facets = edge["facets"]
        for field, allowed in (
            ("elevation", ELEVATIONS),
            ("traversal_direction", DIRECTIONS),
            ("visibility", VISIBILITIES),
        ):
            value = facets.get(field)
            if value is not None and value not in allowed:
                errors.append(f"{edge['id']} has invalid {field} {value!r}")
        for field in ("kind", "medium", "baseline_state"):
            value = facets.get(field)
            if value is not None and (
                not isinstance(value, str) or not value.strip()
            ):
                errors.append(f"{edge['id']} has invalid {field}")
        for field in ("barriers", "features", "conditions", "hazards"):
            value = facets.get(field, [])
            if not isinstance(value, list) or any(
                not isinstance(item, str) or not item.strip() for item in value
            ):
                errors.append(f"{edge['id']} has invalid {field}")
        conditions = facets.get("conditions", [])
        if facets.get("visibility") == "hidden" and not conditions:
            errors.append(f"hidden passage {edge['id']} has no reveal condition")
        if facets.get("traversal_direction") == "conditional" and not conditions:
            errors.append(f"conditional passage {edge['id']} has no condition")

    result["topology_links"] = sorted(
        links, key=lambda item: item["place_id"]
    )
    result["topology_errors"] = sorted(set(errors))
    return result
