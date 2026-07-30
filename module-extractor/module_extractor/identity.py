"""Canonical identity policy, duplicate candidates, and review decisions."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import hashlib
import re
import unicodedata
from typing import Any, Mapping, Sequence

from .util import canonical_json_bytes


CANONICAL_PREFIXES = {
    "location": "place",
    "actor": "actor",
    "situation": "situation",
    "knowledge": "knowledge",
    "procedure": "procedure",
    "item": "item",
}
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'", "`": "'"})
_AREA = re.compile(
    r"(?:^|[\s._-])(?:area|room|location|loc|map)?[\s._-]*0*(\d+)(?:$|[\s._-])",
    re.IGNORECASE,
)
_CANONICAL = re.compile(
    r"^(place|actor|situation|knowledge|procedure|item)"
    r"\.([a-z0-9]+(?:-[a-z0-9]+)*)\.([a-z0-9]+(?:-[a-z0-9]+)*)$"
)
# Typed reference fields that hold canonical IDs directly.
TYPED_REFERENCE_FIELDS = {
    "location": (
        "actor_references",
        "situation_references",
        "procedure_references",
        "knowledge_references",
    ),
    "actor": (
        "knowledge_references",
        "location_references",
        "situation_references",
    ),
    "situation": (
        "knowledge_references",
        "location_references",
        "procedure_references",
    ),
}
# Typed fields whose objects hold a canonical ID under a named key.
NESTED_REFERENCE_FIELDS = {
    "actor": (("relationships", "target_id"),),
    "situation": (
        ("actor_reactions", "actor_id"),
        ("participants", "actor_id"),
        ("possible_effects", "target"),
    ),
}


def normalize_identity_text(value: str) -> str:
    """Normalize matching text without asserting global identity."""
    value = unicodedata.normalize("NFKD", value.translate(_APOSTROPHES))
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.casefold().replace("'", "")
    tokens = re.findall(r"[a-z0-9]+", value)
    return " ".join(str(int(token)) if token.isdigit() else token for token in tokens)


def identity_slug(value: str) -> str:
    normalized = normalize_identity_text(value)
    return "-".join(normalized.split()) or "untitled"


def module_slug(source: Mapping[str, Any]) -> str:
    value = source.get("slug")
    if isinstance(value, str) and value:
        return identity_slug(value)
    return f"module-{source['sha256'][:12]}"


def keyed_area(value: str) -> str | None:
    match = _AREA.search(f" {value} ")
    return str(int(match.group(1))) if match else None


def canonical_id_is_valid(
    identifier: str, record_type: str, source: Mapping[str, Any]
) -> bool:
    match = _CANONICAL.fullmatch(identifier)
    return bool(
        match
        and CANONICAL_PREFIXES.get(record_type) == match.group(1)
        and module_slug(source) == match.group(2)
    )


def _identifier_stem(identifier: str, source: Mapping[str, Any]) -> str:
    tokens = normalize_identity_text(identifier).split()
    ignored = {
        "location",
        "place",
        "actor",
        "situation",
        "knowledge",
        "procedure",
        "item",
        *module_slug(source).split("-"),
    }
    while tokens and tokens[0] in ignored:
        tokens.pop(0)
    return " ".join(tokens)


def _descriptor_table(
    evidence: Mapping[str, Any], source: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    table: dict[str, dict[str, Any]] = {}

    def entry(identifier: str, record_type: str) -> dict[str, Any]:
        current = table.setdefault(
            identifier,
            {
                "extracted_id": identifier,
                "record_types": set(),
                "titles": set(),
                "normalized_titles": set(),
                "source_pages": set(),
                "observation_ids": set(),
                "references": set(),
                "keyed_areas": set(),
                "topology_labels": set(),
                "fields": [],
                "kinds": set(),
            },
        )
        current["record_types"].add(record_type)
        return current

    for observation in evidence["content_observations"]:
        current = entry(observation["concept_id"], observation["record_type"])
        current["kinds"].add("record")
        title = observation["fields"].get("title")
        if isinstance(title, str) and title.strip():
            current["titles"].add(title)
            current["normalized_titles"].add(normalize_identity_text(title))
            area = keyed_area(title)
            if area is not None:
                current["keyed_areas"].add(area)
        for name in ("keyed_area", "area_number", "map_label", "topology_label"):
            value = observation["fields"].get(name)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                text = str(value)
                area = keyed_area(f"area {text}")
                if area is not None:
                    current["keyed_areas"].add(area)
                if name in {"map_label", "topology_label"}:
                    current["topology_labels"].add(normalize_identity_text(text))
        area = keyed_area(observation["concept_id"])
        if area is not None:
            current["keyed_areas"].add(area)
        current["source_pages"].update(observation["source_pages"])
        current["observation_ids"].add(observation["observation_id"])
        current["references"].update(observation["references"])
        current["fields"].append(observation["fields"])

    for result in evidence["map_results"]:
        for node in result["nodes"]:
            current = entry(node["concept_id"], "location")
            current["kinds"].add("topology-node")
            title = node.get("title")
            if isinstance(title, str) and title.strip():
                current["titles"].add(title)
                current["normalized_titles"].add(normalize_identity_text(title))
                area = keyed_area(title)
                if area is not None:
                    current["keyed_areas"].add(area)
            label = str(node.get("label", "")).strip()
            if label:
                current["topology_labels"].add(normalize_identity_text(label))
                area = keyed_area(f"area {label}")
                if area is not None:
                    current["keyed_areas"].add(area)
            area = keyed_area(node["concept_id"])
            if area is not None:
                current["keyed_areas"].add(area)
            current["source_pages"].update(node["source_pages"])
            current["observation_ids"].add(node["observation_id"])

    result: dict[str, dict[str, Any]] = {}
    for identifier, raw in table.items():
        record_types = sorted(raw["record_types"])
        result[identifier] = {
            **raw,
            "record_type": record_types[0] if len(record_types) == 1 else None,
            "record_types": record_types,
            "titles": sorted(raw["titles"]),
            "normalized_titles": sorted(raw["normalized_titles"]),
            "source_pages": sorted(raw["source_pages"]),
            "observation_ids": sorted(raw["observation_ids"]),
            "references": sorted(raw["references"]),
            "keyed_areas": sorted(raw["keyed_areas"]),
            "topology_labels": sorted(raw["topology_labels"]),
            "kinds": sorted(raw["kinds"]),
            "id_stem": _identifier_stem(identifier, source),
        }
    return result


def _compatible_fields(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    for left_fields in left["fields"]:
        for right_fields in right["fields"]:
            for field in set(left_fields) & set(right_fields) - {"title"}:
                left_value = left_fields[field]
                right_value = right_fields[field]
                if (
                    left_value is not None
                    and right_value is not None
                    and left_value != right_value
                ):
                    return False
    return True


def detect_duplicate_candidates(
    evidence: Mapping[str, Any], source: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Return deterministic, evidence-only candidate pairs."""
    descriptors = _descriptor_table(evidence, source)
    candidates = []
    identifiers = sorted(descriptors)
    for index, left_id in enumerate(identifiers):
        left = descriptors[left_id]
        for right_id in identifiers[index + 1 :]:
            right = descriptors[right_id]
            if (
                left["record_type"] is None
                or left["record_type"] != right["record_type"]
            ):
                continue
            signals = []
            if set(left["normalized_titles"]) & set(right["normalized_titles"]):
                signals.append("normalized-title")
            if left["id_stem"] and left["id_stem"] == right["id_stem"]:
                signals.append("normalized-extracted-id")
            shared_areas = set(left["keyed_areas"]) & set(right["keyed_areas"])
            if shared_areas:
                signals.append("keyed-area")
            distinct_areas = bool(
                left["keyed_areas"] and right["keyed_areas"] and not shared_areas
            )
            if distinct_areas:
                signals.append("distinct-keyed-area")
            if set(left["topology_labels"]) & set(right["topology_labels"]):
                signals.append("topology-label")
            if set(left["source_pages"]) & set(right["source_pages"]):
                signals.append("overlapping-source-context")
            shared_relationships = set(left["references"]) & set(right["references"])
            if shared_relationships:
                signals.append("shared-relationships")
            direct_relationship = (
                left_id in right["references"] or right_id in left["references"]
            )
            if direct_relationship:
                signals.append("direct-relationship")
            compatible = _compatible_fields(left, right)
            if compatible:
                signals.append("compatible-operational-fields")
            if not (
                "normalized-title" in signals
                or "normalized-extracted-id" in signals
                or "keyed-area" in signals
                or "topology-label" in signals
                or "shared-relationships" in signals
                or direct_relationship
            ):
                continue
            # The source keyed these objects as separate areas, so they cannot
            # be the same object. The pair still surfaces for review.
            high = not distinct_areas and (
                {"normalized-title", "normalized-extracted-id"} <= set(signals)
                or (
                    "keyed-area" in signals
                    and bool(
                        {"normalized-title", "topology-label", "shared-relationships"}
                        & set(signals)
                    )
                )
                or (
                    "topology-label" in signals
                    and "normalized-title" in signals
                )
                # A typed operational link alone is not identity evidence: a
                # situation may legitimately name another situation.
                or (
                    direct_relationship
                    and bool(
                        {
                            "normalized-title",
                            "normalized-extracted-id",
                            "keyed-area",
                            "topology-label",
                        }
                        & set(signals)
                    )
                )
                or (
                    "shared-relationships" in signals
                    and left["record_type"] == "location"
                )
            )
            pair = [left_id, right_id]
            digest = hashlib.sha256(canonical_json_bytes(pair)).hexdigest()[:12]
            candidates.append(
                {
                    "id": f"duplicate-candidate.{digest}",
                    "record_type": left["record_type"],
                    "extracted_ids": pair,
                    "confidence": "high" if high else "medium",
                    "signals": sorted(signals),
                    "source_pages": sorted(
                        set(left["source_pages"]) | set(right["source_pages"])
                    ),
                    "observation_ids": sorted(
                        set(left["observation_ids"]) | set(right["observation_ids"])
                    ),
                    "evidence_needed": (
                        "Compare the cited observations and pages, then alias the "
                        "same concept or declare the candidates distinct."
                    ),
                }
            )
    return sorted(candidates, key=lambda item: item["id"])


def _pairs(review: Mapping[str, Any]) -> set[tuple[str, str]]:
    return {
        tuple(sorted((item["left_id"], item["right_id"])))
        for item in review.get("distinct", [])
    }


def _alias_resolution(
    review: Mapping[str, Any], descriptors: Mapping[str, Any]
) -> tuple[dict[str, str], list[str], list[dict[str, Any]]]:
    targets: dict[str, set[str]] = defaultdict(set)
    operations: dict[tuple[str, str], dict[str, Any]] = {}
    errors = []
    invalid_edges: set[tuple[str, str]] = set()
    distinct_pairs = _pairs(review)
    for item in review.get("aliases", []):
        alias, target = item["alias"], item["target_id"]
        targets[alias].add(target)
        operations[(alias, target)] = item
        if alias not in descriptors:
            errors.append(f"alias {alias} is not an extracted ID from this run")
        if target not in descriptors:
            errors.append(f"alias {alias} targets unknown extracted ID {target}")
        if (
            alias in descriptors
            and target in descriptors
            and descriptors[alias]["record_type"]
            != descriptors[target]["record_type"]
        ):
            errors.append(
                f"alias {alias} crosses record types to {target}"
            )
            invalid_edges.add((alias, target))
        if tuple(sorted((alias, target))) in distinct_pairs:
            errors.append(
                f"candidate {sorted((alias, target))} is both aliased and "
                "declared distinct"
            )
            invalid_edges.add((alias, target))
    ambiguous = {alias for alias, values in targets.items() if len(values) > 1}
    for alias in sorted(ambiguous):
        errors.append(f"alias {alias} has ambiguous targets: {sorted(targets[alias])}")
    graph = {
        alias: next(iter(values))
        for alias, values in targets.items()
        if (
            len(values) == 1
            and alias in descriptors
            and next(iter(values)) in descriptors
            and (alias, next(iter(values))) not in invalid_edges
        )
    }
    cycles: set[str] = set()
    for start in sorted(graph):
        order = []
        positions = {}
        current = start
        while current in graph:
            if current in positions:
                cycles.update(order[positions[current] :])
                break
            positions[current] = len(order)
            order.append(current)
            current = graph[current]
    if cycles:
        errors.append("alias cycle includes: " + ", ".join(sorted(cycles)))
    invalid = ambiguous | cycles
    graph = {
        alias: target
        for alias, target in graph.items()
        if alias not in invalid and target not in invalid
    }
    return graph, sorted(set(errors)), [
        operations[key] for key in sorted(operations)
    ]


def _components(
    identifiers: Sequence[str], aliases: Mapping[str, str]
) -> list[list[str]]:
    parent = {identifier: identifier for identifier in identifiers}

    def find(value: str) -> str:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    for alias, target in sorted(aliases.items()):
        left, right = find(alias), find(target)
        if left != right:
            parent[max(left, right)] = min(left, right)
    groups: dict[str, list[str]] = defaultdict(list)
    for identifier in sorted(identifiers):
        groups[find(identifier)].append(identifier)
    return sorted(groups.values(), key=lambda group: group[0])


def _default_base(
    component: Sequence[str],
    descriptors: Mapping[str, Mapping[str, Any]],
    source: Mapping[str, Any],
) -> str:
    descriptor = descriptors[component[0]]
    record_type = descriptor["record_type"]
    if record_type not in CANONICAL_PREFIXES:
        return component[0]
    titles = sorted(
        {
            title
            for identifier in component
            for title in descriptors[identifier]["normalized_titles"]
        }
    )
    if titles:
        slug = identity_slug(titles[0])
    else:
        stems = sorted(
            descriptors[identifier]["id_stem"]
            for identifier in component
            if descriptors[identifier]["id_stem"]
        )
        slug = identity_slug(stems[0] if stems else component[0])
    return f"{CANONICAL_PREFIXES[record_type]}.{module_slug(source)}.{slug}"


def _canonical_mapping(
    descriptors: Mapping[str, Mapping[str, Any]],
    aliases: Mapping[str, str],
    review: Mapping[str, Any],
    source: Mapping[str, Any],
) -> tuple[dict[str, str], list[str], list[dict[str, Any]]]:
    errors = []
    declarations_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in review.get("canonical_ids", []):
        extracted_id = item["extracted_id"]
        if extracted_id not in descriptors:
            errors.append(
                f"canonical ID declaration targets unknown extracted ID {extracted_id}"
            )
            continue
        record_type = descriptors[extracted_id]["record_type"]
        if record_type not in CANONICAL_PREFIXES:
            errors.append(
                f"{extracted_id} has no canonical ID policy for type {record_type}"
            )
        elif not canonical_id_is_valid(item["canonical_id"], record_type, source):
            errors.append(
                f"{item['canonical_id']} violates the canonical ID policy for "
                f"{extracted_id}"
            )
        declarations_by_id[extracted_id].append(item)

    components = _components(sorted(descriptors), aliases)
    assigned: list[tuple[list[str], str]] = []
    for component in components:
        declarations = [
            item
            for identifier in component
            for item in declarations_by_id.get(identifier, [])
        ]
        choices = sorted({item["canonical_id"] for item in declarations})
        if len(choices) > 1:
            errors.append(
                f"aliased IDs {component} declare ambiguous canonical IDs {choices}"
            )
        selected = choices[0] if len(choices) == 1 else _default_base(
            component, descriptors, source
        )
        assigned.append((component, selected))

    by_base: dict[str, list[list[str]]] = defaultdict(list)
    for component, selected in assigned:
        by_base[selected].append(component)
    mapping = {}
    decisions = []
    for component, selected in assigned:
        collisions = by_base[selected]
        explicit = any(
            declarations_by_id.get(identifier) for identifier in component
        )
        if len(collisions) > 1:
            if explicit:
                errors.append(
                    f"canonical ID {selected} is claimed by distinct extracted groups"
                )
                selected = (
                    f"{selected}-"
                    + hashlib.sha256(canonical_json_bytes(component)).hexdigest()[:8]
                )
            else:
                area_values = sorted(
                    {
                        area
                        for identifier in component
                        for area in descriptors[identifier]["keyed_areas"]
                    }
                )
                collision_areas = [
                    sorted(
                        {
                            area
                            for identifier in other_component
                            for area in descriptors[identifier]["keyed_areas"]
                        }
                    )
                    for other_component in collisions
                ]
                suffix = (
                    f"area-{area_values[0]}"
                    if (
                        len(area_values) == 1
                        and sum(
                            values == area_values for values in collision_areas
                        )
                        == 1
                    )
                    else hashlib.sha256(
                        canonical_json_bytes(component)
                    ).hexdigest()[:8]
                )
                selected = f"{selected}-{suffix}"
        for identifier in component:
            mapping[identifier] = selected
        declarations = [
            item
            for identifier in component
            for item in declarations_by_id.get(identifier, [])
        ]
        decisions.append(
            {
                "canonical_id": selected,
                "extracted_ids": list(component),
                "source_pages": sorted(
                    {
                        page
                        for identifier in component
                        for page in descriptors[identifier]["source_pages"]
                    }
                ),
                "rationale": (
                    "; ".join(sorted({item["rationale"] for item in declarations}))
                    if declarations
                    else "Applied the deterministic canonical ID policy."
                ),
                "reviewed": bool(declarations),
            }
        )
    return mapping, sorted(set(errors)), sorted(
        decisions, key=lambda item: item["canonical_id"]
    )


def _validate_current_run_pages(
    review: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> list[str]:
    run_pages = {
        page
        for observation in evidence["content_observations"]
        for page in observation["source_pages"]
    }
    for result in evidence["map_results"]:
        run_pages.update(
            page
            for observation in [*result["nodes"], *result["passages"]]
            for page in observation["source_pages"]
        )
    errors = []
    for collection in (
        "canonical_ids",
        "aliases",
        "distinct",
        "values",
        "accepted_uncertainties",
        "topology_composites",
    ):
        for item in review.get(collection, []):
            outside = sorted(set(item["source_pages"]) - run_pages)
            if outside:
                errors.append(
                    f"review {collection} operation cites pages without current-run "
                    f"identity evidence: {outside}"
                )
    return errors


def apply_identity_review(
    evidence: Mapping[str, Any],
    review: Mapping[str, Any],
    source: Mapping[str, Any],
) -> dict[str, Any]:
    """Analyze identity, apply safe decisions, and rewrite a copy of evidence."""
    descriptors = _descriptor_table(evidence, source)
    candidates = detect_duplicate_candidates(evidence, source)
    aliases, alias_errors, alias_operations = _alias_resolution(review, descriptors)
    mapping, canonical_errors, canonical_decisions = _canonical_mapping(
        descriptors, aliases, review, source
    )
    distinct_pairs = _pairs(review)
    candidate_pairs = {
        tuple(candidate["extracted_ids"]): candidate for candidate in candidates
    }
    errors = alias_errors + canonical_errors + _validate_current_run_pages(
        review, evidence
    )
    rejected_merges = []
    for item in review.get("distinct", []):
        pair = tuple(sorted((item["left_id"], item["right_id"])))
        if pair[0] not in descriptors or pair[1] not in descriptors:
            errors.append(f"distinct decision targets IDs outside this run: {list(pair)}")
            continue
        if pair not in candidate_pairs:
            errors.append(f"distinct decision does not match a candidate: {list(pair)}")
            continue
        rejected_merges.append(
            {
                "candidate_id": candidate_pairs[pair]["id"],
                "extracted_ids": list(pair),
                "source_pages": item["source_pages"],
                "rationale": item["rationale"],
            }
        )
        if mapping.get(pair[0]) == mapping.get(pair[1]):
            errors.append(
                f"candidate {list(pair)} is both aliased and declared distinct"
            )

    candidate_groups = []
    unresolved_high = []
    for candidate in candidates:
        pair = tuple(candidate["extracted_ids"])
        topology_proposal = (
            candidate["record_type"] == "location"
            and {
                tuple(descriptors[pair[0]]["kinds"]),
                tuple(descriptors[pair[1]]["kinds"]),
            }
            == {("record",), ("topology-node",)}
        )
        if topology_proposal:
            status = "topology-proposal"
        elif mapping.get(pair[0]) == mapping.get(pair[1]) and pair[0] in aliases:
            status = "confirmed-alias"
        elif mapping.get(pair[0]) == mapping.get(pair[1]) and pair[1] in aliases:
            status = "confirmed-alias"
        elif pair in distinct_pairs:
            status = "distinct"
        else:
            status = "unresolved"
            if candidate["confidence"] == "high":
                unresolved_high.append(candidate)
        candidate_groups.append({**candidate, "status": status})

    rewritten = deepcopy(dict(evidence))
    for observation in rewritten["content_observations"]:
        extracted_id = observation["concept_id"]
        observation["extracted_concept_id"] = extracted_id
        observation["concept_id"] = mapping.get(extracted_id, extracted_id)
        observation["references"] = [
            mapping.get(reference, reference) for reference in observation["references"]
        ]
        record_type = observation["record_type"]
        if record_type == "location" and isinstance(
            observation["fields"].get("topology_node"), str
        ):
            node = observation["fields"]["topology_node"]
            observation["fields"]["topology_node"] = mapping.get(node, node)
        for field in TYPED_REFERENCE_FIELDS.get(record_type, ()):
            if isinstance(observation["fields"].get(field), list):
                observation["fields"][field] = [
                    mapping.get(reference, reference)
                    for reference in observation["fields"][field]
                ]
        for field, key in NESTED_REFERENCE_FIELDS.get(record_type, ()):
            value = observation["fields"].get(field)
            if not isinstance(value, list):
                continue
            observation["fields"][field] = [
                {
                    **item,
                    key: mapping.get(item[key], item[key]),
                }
                if isinstance(item, dict) and isinstance(item.get(key), str)
                else item
                for item in value
            ]
    passage_targets = {}
    for result in rewritten["map_results"]:
        for node in result["nodes"]:
            extracted_id = node["concept_id"]
            node["extracted_concept_id"] = extracted_id
            node["concept_id"] = mapping.get(extracted_id, extracted_id)
        for passage in result["passages"]:
            old_from, old_to = passage["from"], passage["to"]
            passage["from"] = mapping.get(old_from, old_from)
            passage["to"] = mapping.get(old_to, old_to)
            passage_targets[passage["observation_id"]] = (
                f"edge-{'-'.join(sorted((passage['from'], passage['to'])))}"
            )
    for uncertainty in rewritten["uncertainties"]:
        if uncertainty.get("target_kind") == "topology-edge":
            uncertainty["target_id"] = passage_targets.get(
                uncertainty["target_observation_id"], uncertainty["target_id"]
            )
        else:
            uncertainty["target_id"] = mapping.get(
                uncertainty["target_id"], uncertainty["target_id"]
            )

    final_aliases = {
        extracted_id: canonical_id
        for extracted_id, canonical_id in sorted(mapping.items())
        if extracted_id != canonical_id
    }
    confirmed_aliases = []
    for item in alias_operations:
        if (
            item["alias"] in aliases
            and aliases[item["alias"]] == item["target_id"]
            and item["alias"] in mapping
            and item["target_id"] in mapping
            and mapping[item["alias"]] == mapping[item["target_id"]]
        ):
            confirmed_aliases.append(
                {
                    **item,
                    "canonical_id": mapping[item["alias"]],
                }
            )

    keyed_claims: dict[str, set[str]] = defaultdict(set)
    component_ids_by_canonical: dict[str, set[str]] = defaultdict(set)
    for extracted_id, canonical_id in mapping.items():
        component_ids_by_canonical[canonical_id].add(extracted_id)
        if (
            descriptors[extracted_id]["record_type"] == "location"
            and "record" in descriptors[extracted_id]["kinds"]
        ):
            for area in descriptors[extracted_id]["keyed_areas"]:
                keyed_claims[area].add(canonical_id)
    keyed_area_conflicts = []
    for area, canonical_ids in sorted(keyed_claims.items()):
        if len(canonical_ids) < 2:
            continue
        groups = [
            component_ids_by_canonical[canonical_id]
            for canonical_id in sorted(canonical_ids)
        ]
        reviewed_distinct = all(
            any(
                tuple(sorted((left, right))) in distinct_pairs
                for left in groups[left_index]
                for right in groups[right_index]
            )
            for left_index in range(len(groups))
            for right_index in range(left_index + 1, len(groups))
        )
        if not reviewed_distinct:
            keyed_area_conflicts.append(
                {
                    "keyed_area": area,
                    "canonical_ids": sorted(canonical_ids),
                    "evidence_needed": (
                        "Alias duplicate places or explicitly declare every "
                        "same-area candidate pair distinct."
                    ),
                }
            )

    return {
        "evidence": rewritten,
        "mapping": mapping,
        "aliases": final_aliases,
        "candidate_groups": candidate_groups,
        "unresolved_high_confidence": unresolved_high,
        "confirmed_aliases": sorted(
            confirmed_aliases, key=lambda item: (item["alias"], item["target_id"])
        ),
        "canonical_ids": canonical_decisions,
        "rejected_merges": sorted(
            rejected_merges, key=lambda item: item["candidate_id"]
        ),
        "keyed_area_conflicts": keyed_area_conflicts,
        "errors": sorted(set(errors)),
    }
