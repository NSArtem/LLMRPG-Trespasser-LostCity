"""Deterministic runtime cards and extraction-only audit views."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contracts import GENERATED_OUTPUT_SCHEMA, PLAY_CONTRACT, RUNTIME_INDEX_SCHEMA
from .errors import ExtractorError
from .util import canonical_json_bytes, load_json, write_json


CARD_DIRECTORIES = {
    "location": ("place", "places"),
    "actor": ("actor", "actors"),
    "situation": ("situation", "situations"),
    "knowledge": ("knowledge", "knowledge"),
    "procedure": ("procedure", "procedures"),
    "rule": ("rule", "reference"),
    "table": ("table", "reference"),
    "item": ("item", "reference"),
    "spell": ("spell", "reference"),
    "class": ("class", "reference"),
    "effect": ("effect", "reference"),
}
CARD_DIRECTORY_ORDER = (
    ("place", "places"),
    ("actor", "actors"),
    ("situation", "situations"),
    ("knowledge", "knowledge"),
    ("procedure", "procedures"),
    ("reference", "reference"),
)
FIXED_RUNTIME_FILES = {
    "MODULE.md",
    "index.md",
    "index.json",
    "topology.yaml",
}
FIXED_AUDIT_FILES = {
    "audit/module.json",
    "audit/coverage.md",
    "audit/conflicts-and-gaps.md",
    "audit/review.md",
}
PROHIBITED_INDEX_FIELDS = {
    "observations",
    "observation_ids",
    "raw_observations",
    "pack_id",
    "packs",
    "confidence",
    "field_observations",
    "review",
    "coverage",
    "identity",
    "candidate_groups",
    "canonical_ids",
    "rejected_merges",
    "merge_rationale",
    "extracted_ids",
}


def _display(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _yaml_value(value: Any) -> str:
    """Render a deterministic JSON value, which is also valid YAML 1.2."""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(", ", ": ")
    )


def _aliases_by_target(module: Mapping[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for alias, target in module["aliases"].items():
        result.setdefault(target, []).append(alias)
    return {target: sorted(values) for target, values in result.items()}


def _verification(module: Mapping[str, Any]) -> str:
    return "verified" if module["profile"] == "release" else "unverified"


def _runtime_type(record_type: str) -> str:
    try:
        return CARD_DIRECTORIES[record_type][0]
    except KeyError as exc:
        raise ExtractorError(f"cannot route unknown record type: {record_type}") from exc


def card_path(record: Mapping[str, Any]) -> str:
    try:
        directory = CARD_DIRECTORIES[record["record_type"]][1]
    except KeyError as exc:
        raise ExtractorError(
            f"cannot route unknown record type: {record['record_type']}"
        ) from exc
    return f"cards/{directory}/{record['id']}.md"


LOAD_WITH_TYPES = {
    "actor": "actors",
    "situation": "situations",
    "procedure": "procedures",
    "knowledge": "knowledge",
}
# A place bundles every situation available there. A situation bundles the
# actors, procedures, and knowledge it needs, and never another situation: its
# possible effects may name situations that must stay dormant.
LOAD_WITH_GROUPS = {
    "location": ("actors", "situations", "procedures", "knowledge"),
    "situation": ("actors", "procedures", "knowledge"),
}


def _load_with(
    record: Mapping[str, Any], records: Sequence[Mapping[str, Any]]
) -> dict[str, list[str]]:
    groups = LOAD_WITH_GROUPS.get(record["record_type"])
    if groups is None:
        return {}
    result: dict[str, list[str]] = {key: [] for key in groups}
    by_id = {item["id"]: item for item in records}
    for reference in record["references"]:
        target = by_id.get(reference)
        if target is None:
            continue
        group = LOAD_WITH_TYPES.get(target["record_type"])
        if group in result:
            result[group].append(card_path(target))
    return {key: sorted(set(values)) for key, values in result.items()}


def _referenced_cards(
    record: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    field: str,
    record_type: str,
) -> list[dict[str, str]]:
    """Return card links for one typed reference field, in canonical order."""
    by_id = {item["id"]: item for item in records}
    values = record["fields"].get(field, [])
    links = []
    for identifier in values if isinstance(values, list) else []:
        target = by_id.get(identifier)
        if target is None or target["record_type"] != record_type:
            continue
        links.append(
            {
                "id": identifier,
                "title": str(target["fields"].get("title", identifier)),
                "path": card_path(target),
            }
        )
    return sorted(links, key=lambda item: item["id"])


def _label(identifier: str, records: Sequence[Mapping[str, Any]]) -> str:
    """Name a referenced record by title and ID, or by ID alone if unknown."""
    for item in records:
        if item["id"] == identifier:
            title = str(item["fields"].get("title", identifier))
            return f"**{title}** (`{identifier}`)"
    return f"`{identifier}`"


def _reverse_cards(
    record: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    record_type: str,
) -> list[str]:
    """Return card paths of records of one type that reference this record."""
    return sorted(
        {
            card_path(item)
            for item in records
            if item["record_type"] == record_type
            and record["id"] in item["references"]
        }
    )


def _relative_exit_direction(edge: Mapping[str, Any], node_id: str) -> str:
    direction = edge["facets"].get("traversal_direction")
    if direction in {None, "both", "conditional"}:
        return direction or "not stated"
    outbound = (
        direction == "from_to" and edge["from"] == node_id
    ) or (
        direction == "to_from" and edge["to"] == node_id
    )
    return "outbound" if outbound else "inbound"


def _place_exits(
    record: Mapping[str, Any], topology: Mapping[str, Any]
) -> list[dict[str, Any]]:
    node_id = record["fields"].get("topology_node")
    if not isinstance(node_id, str):
        return []
    nodes = {node["id"]: node for node in topology.get("nodes", [])}
    exits = []
    for edge in topology.get("passages", []):
        if node_id not in {edge["from"], edge["to"]}:
            continue
        destination_id = edge["to"] if edge["from"] == node_id else edge["from"]
        destination = nodes.get(destination_id, {})
        titles = destination.get("titles", [])
        exits.append(
            {
                "edge_id": edge["id"],
                "destination_id": destination_id,
                "destination": titles[0] if titles else destination_id,
                "direction": _relative_exit_direction(edge, node_id),
                "facets": edge["facets"],
            }
        )
    return sorted(exits, key=lambda item: (item["destination_id"], item["edge_id"]))


def _append_list_section(
    lines: list[str], heading: str, values: Sequence[Any]
) -> None:
    lines.extend([f"## {heading}", ""])
    lines.extend(f"- {_display(value)}" for value in values)
    lines.append("")


def _append_text_section(lines: list[str], heading: str, value: Any) -> None:
    lines.extend([f"## {heading}", ""])
    if isinstance(value, str) and value.strip():
        lines.extend([value, ""])


def _append_link_section(
    lines: list[str], heading: str, links: Sequence[Mapping[str, str]]
) -> None:
    lines.extend([f"## {heading}", ""])
    lines.extend(
        f"- [{link['title']}]({link['path']}) — `{link['id']}`" for link in links
    )
    lines.append("")


def _envelope(
    record: Mapping[str, Any],
    *,
    runtime_type: str,
    title: str,
    aliases: Sequence[str],
    verification: str,
) -> list[str]:
    """Return the stable YAML front-matter head shared by every card."""
    return [
        "---",
        f"id: {_yaml_value(record['id'])}",
        f"type: {_yaml_value(runtime_type)}",
        f"title: {_yaml_value(title)}",
        f"aliases: {_yaml_value(list(aliases))}",
        f"source_pages: {_yaml_value(record['source_pages'])}",
        f"verification: {verification}",
        f"references: {_yaml_value(record['references'])}",
    ]


def _place_card(
    record: Mapping[str, Any],
    *,
    aliases: Sequence[str],
    verification: str,
    records: Sequence[Mapping[str, Any]],
    topology: Mapping[str, Any],
) -> str:
    fields = record["fields"]
    title = str(fields.get("title", record["id"]))
    first_impression = fields.get("first_impression", "")
    if not isinstance(first_impression, str):
        first_impression = ""
    load_with = _load_with(record, records)
    lines = _envelope(
        record,
        runtime_type="place",
        title=title,
        aliases=aliases,
        verification=verification,
    )
    lines.extend(
        [
            f"topology_node: {_yaml_value(fields.get('topology_node'))}",
            "load_with:",
            f"  actors: {_yaml_value(load_with['actors'])}",
            f"  situations: {_yaml_value(load_with['situations'])}",
            f"  procedures: {_yaml_value(load_with['procedures'])}",
            f"  knowledge: {_yaml_value(load_with['knowledge'])}",
            "---",
            "",
            f"# {title}",
            "",
            "## First impression",
            "",
            first_impression,
            "",
        ]
    )
    contents = (
        list(fields.get("contents", []))
        if isinstance(fields.get("contents", []), list)
        else []
    )
    occupants = fields.get("occupants", [])
    if isinstance(occupants, list):
        contents.extend(f"Occupant: {value}" for value in occupants)
    _append_list_section(lines, "Contents", contents)
    lines.extend(["## Discoverable", ""])
    discoverable = fields.get("discoverable", [])
    if isinstance(discoverable, list):
        for item in discoverable:
            if isinstance(item, dict) and {"condition", "information"} <= set(item):
                lines.append(f"- **{item['condition']}** — {item['information']}")
    lines.append("")
    for heading, field in (
        ("Hidden", "hidden"),
        ("Triggers", "triggers"),
        ("Hazards", "hazards"),
        ("Resources", "resources"),
    ):
        values = fields.get(field, [])
        _append_list_section(
            lines, heading, values if isinstance(values, list) else []
        )
    lines.extend(
        [
            "## Exits",
            "",
            "<!-- Generated from topology.yaml; canonical passage state lives there. -->",
            "",
        ]
    )
    for item in _place_exits(record, topology):
        facets = item["facets"]
        lines.extend(
            [
                f"### {item['destination']}",
                "",
                f"- Destination: `{item['destination_id']}`",
                f"- Direction: {item['direction']}",
            ]
        )
        for label, field in (
            ("Passage kind", "kind"),
            ("Baseline state", "baseline_state"),
            ("Visibility", "visibility"),
        ):
            value = facets.get(field)
            if value is not None:
                lines.append(f"- {label}: {_display(value)}")
        for label, field in (
            ("Barriers", "barriers"),
            ("Conditions", "conditions"),
            ("Hazards", "hazards"),
        ):
            values = facets.get(field, [])
            if values:
                lines.append(f"- {label}: " + "; ".join(values))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _actor_card(
    record: Mapping[str, Any],
    *,
    aliases: Sequence[str],
    verification: str,
    records: Sequence[Mapping[str, Any]],
) -> str:
    fields = record["fields"]
    title = str(fields.get("title", record["id"]))
    knowledge = _referenced_cards(record, records, "knowledge_references", "knowledge")
    places = sorted(
        set(
            link["path"]
            for link in _referenced_cards(
                record, records, "location_references", "location"
            )
        )
        | set(_reverse_cards(record, records, "location"))
    )
    situations = sorted(
        set(
            link["path"]
            for link in _referenced_cards(
                record, records, "situation_references", "situation"
            )
        )
        | set(_reverse_cards(record, records, "situation"))
    )
    lines = _envelope(
        record,
        runtime_type="actor",
        title=title,
        aliases=aliases,
        verification=verification,
    )
    lines.extend(
        [
            "appears_in:",
            f"  places: {_yaml_value(places)}",
            f"  situations: {_yaml_value(situations)}",
            f"knowledge: {_yaml_value([link['path'] for link in knowledge])}",
            "---",
            "",
            f"# {title}",
            "",
        ]
    )
    _append_text_section(lines, "Appearance", fields.get("appearance"))
    _append_text_section(lines, "Role", fields.get("role"))
    _append_list_section(
        lines,
        "Goals",
        fields.get("goals", []) if isinstance(fields.get("goals"), list) else [],
    )
    lines.extend(["## Behavior and reactions", ""])
    behavior = fields.get("behavior", [])
    if isinstance(behavior, list):
        lines.extend(f"- {_display(item)}" for item in behavior)
    reactions = fields.get("reactions", [])
    if isinstance(reactions, list):
        for item in reactions:
            if isinstance(item, dict) and {"stimulus", "response"} <= set(item):
                lines.append(f"- **{item['stimulus']}** — {item['response']}")
    lines.append("")
    lines.extend(["## Relationships", ""])
    relationships = fields.get("relationships", [])
    if isinstance(relationships, list):
        for item in relationships:
            if isinstance(item, dict) and {"relationship", "target_id"} <= set(item):
                lines.append(
                    f"- {_label(item['target_id'], records)} — "
                    f"{item['relationship']}"
                )
    lines.append("")
    _append_list_section(
        lines,
        "Capabilities and mechanics",
        fields.get("capabilities", [])
        if isinstance(fields.get("capabilities"), list)
        else [],
    )
    lines.extend(
        [
            "## Starting state",
            "",
            "<!-- Source-stated starting state only. Current state belongs to "
            "the campaign checkpoint. -->",
            "",
        ]
    )
    starting_state = fields.get("starting_state", [])
    if isinstance(starting_state, list):
        lines.extend(f"- {_display(item)}" for item in starting_state)
    lines.append("")
    _append_link_section(lines, "Knowledge", knowledge)
    _append_list_section(
        lines,
        "Hidden",
        fields.get("hidden", []) if isinstance(fields.get("hidden"), list) else [],
    )
    return "\n".join(lines).rstrip() + "\n"


def _situation_card(
    record: Mapping[str, Any],
    *,
    aliases: Sequence[str],
    verification: str,
    records: Sequence[Mapping[str, Any]],
) -> str:
    fields = record["fields"]
    title = str(fields.get("title", record["id"]))
    load_with = _load_with(record, records)
    activation = fields.get("activation")
    repeat = fields.get("repeat")
    effects = fields.get("possible_effects", [])
    if not isinstance(effects, list):
        effects = []
    locations = _referenced_cards(record, records, "location_references", "location")
    participants = (
        fields.get("participants", [])
        if isinstance(fields.get("participants"), list)
        else []
    )
    lines = _envelope(
        record,
        runtime_type="situation",
        title=title,
        aliases=aliases,
        verification=verification,
    )
    lines.extend(
        [
            f"activation: {_yaml_value(activation)}",
            f"repeat: {_yaml_value(repeat)}",
            f"locations: {_yaml_value([link['path'] for link in locations])}",
            f"participants: {_yaml_value(participants)}",
            "load_with:",
            f"  actors: {_yaml_value(load_with.get('actors', []))}",
            f"  procedures: {_yaml_value(load_with.get('procedures', []))}",
            f"  knowledge: {_yaml_value(load_with.get('knowledge', []))}",
            "# Possible effects are source possibilities. Nothing here is "
            "applied or copied into a checkpoint.",
            f"possible_effects: {_yaml_value(effects)}",
            "---",
            "",
            f"# {title}",
            "",
        ]
    )
    _append_text_section(lines, "What the players perceive", fields.get("perceived"))
    _append_list_section(
        lines,
        "Pressure and stakes",
        fields.get("stakes", []) if isinstance(fields.get("stakes"), list) else [],
    )
    _append_list_section(
        lines,
        "Likely approaches",
        fields.get("approaches", [])
        if isinstance(fields.get("approaches"), list)
        else [],
    )
    lines.extend(["## Actor reactions", ""])
    for item in participants:
        if isinstance(item, dict) and {"actor_id", "role"} <= set(item):
            lines.append(
                f"- {_label(item['actor_id'], records)} takes part: {item['role']}"
            )
    reactions = fields.get("actor_reactions", [])
    if isinstance(reactions, list):
        for item in reactions:
            if isinstance(item, dict) and {"actor_id", "reaction"} <= set(item):
                lines.append(
                    f"- {_label(item['actor_id'], records)} — {item['reaction']}"
                )
    lines.append("")
    _append_list_section(
        lines,
        "Consequences",
        fields.get("outcomes", []) if isinstance(fields.get("outcomes"), list) else [],
    )
    lines.extend(
        [
            "### Possible effects",
            "",
            "<!-- Source possibilities only. The runtime never applies these "
            "automatically and never copies them into a checkpoint. -->",
            "",
        ]
    )
    for effect in effects:
        if not isinstance(effect, dict):
            continue
        target = effect.get("target")
        suffix = (
            f" (condition: {effect['condition']})" if effect.get("condition") else ""
        )
        lines.append(
            f"- `{effect.get('effect')}`"
            + (
                f" → {_label(target, records)}"
                if isinstance(target, str)
                else ""
            )
            + f" — {effect.get('description')}{suffix}"
        )
    lines.append("")
    _append_list_section(
        lines,
        "Completion conditions",
        fields.get("completion", [])
        if isinstance(fields.get("completion"), list)
        else [],
    )
    lines.extend(["### Repeat behavior", ""])
    if isinstance(repeat, dict):
        lines.append(f"- Mode: {_display(repeat.get('mode'))}")
        if repeat.get("condition"):
            lines.append(f"- Condition: {_display(repeat['condition'])}")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _card(
    record: Mapping[str, Any],
    *,
    aliases: Sequence[str],
    verification: str,
    records: Sequence[Mapping[str, Any]] = (),
    topology: Mapping[str, Any] | None = None,
) -> str:
    if record["record_type"] == "location":
        return _place_card(
            record,
            aliases=aliases,
            verification=verification,
            records=records,
            topology=topology or {"nodes": [], "passages": []},
        )
    if record["record_type"] == "actor":
        return _actor_card(
            record,
            aliases=aliases,
            verification=verification,
            records=records,
        )
    if record["record_type"] == "situation":
        return _situation_card(
            record,
            aliases=aliases,
            verification=verification,
            records=records,
        )
    title = str(record["fields"].get("title", record["id"]))
    lines = [
        "---",
        f"id: {_yaml_value(record['id'])}",
        f"type: {_yaml_value(_runtime_type(record['record_type']))}",
        f"title: {_yaml_value(title)}",
        f"aliases: {_yaml_value(list(aliases))}",
        f"source_pages: {_yaml_value(record['source_pages'])}",
        f"verification: {verification}",
        f"references: {_yaml_value(record['references'])}",
        "---",
        "",
        f"# {title}",
        "",
        "## Operational fields",
        "",
    ]
    for field, value in sorted(record["fields"].items()):
        if field == "title":
            continue
        label = field.replace("_", " ").capitalize()
        if isinstance(value, list):
            lines.extend([f"### {label}", ""])
            if value:
                lines.extend(f"- {_display(item)}" for item in value)
            else:
                lines.append("- None recorded.")
            lines.append("")
        else:
            lines.extend([f"### {label}", "", _display(value), ""])
    return "\n".join(lines).rstrip() + "\n"


def _coverage_report(coverage: Mapping[str, Any]) -> str:
    extracted = sum(page["status"] == "extracted" for page in coverage["pages"])
    excluded = sum(page["status"] == "excluded" for page in coverage["pages"])
    lines = [
        "# Coverage report",
        "",
        f"- Schema: `{coverage['schema']}`",
        f"- Physical pages: {coverage['physical_pages']}",
        f"- Extracted pages: {extracted}",
        f"- Explicitly excluded pages: {excluded}",
        f"- Complete: {'yes' if coverage['complete'] else 'no'}",
        "",
        "| Page | Status | Tasks or exclusion |",
        "| ---: | --- | --- |",
    ]
    for page in coverage["pages"]:
        detail = (
            ", ".join(page["routing_tasks"])
            if page["routing_tasks"]
            else page["exclusion_reason"]
        )
        lines.append(f"| {page['pdf_page']} | {page['status']} | {detail} |")
    return "\n".join(lines) + "\n"


def _conflict_report(module: Mapping[str, Any]) -> str:
    conflicts = module["unresolved_conflicts"]
    pending = module["pending_uncertainties"]
    lines = [
        "# Conflict and gap report",
        "",
        f"- Coverage gaps: {len(module['coverage']['gaps'])}",
        f"- Unresolved blocking conflicts: {len(conflicts)}",
        f"- Unreviewed uncertainties: {len(pending)}",
        f"- Operational topology errors: {len(module.get('topology_errors', []))}",
        f"- Operational record errors: {len(module.get('record_errors', []))}",
        f"- High-confidence duplicate candidates: "
        f"{len(module.get('unresolved_duplicate_candidates', []))}",
        f"- Identity errors: {len(module.get('identity', {}).get('errors', []))}",
        "",
    ]
    for item in conflicts:
        lines.append(f"- `{item['id']}`: {item['object_id']}.{item['field']}")
    for item in pending:
        lines.append(f"- `{item['id']}`: {item['description']}")
    for item in module.get("unresolved_duplicate_candidates", []):
        lines.append(
            f"- `{item['id']}`: possible duplicate "
            + " / ".join(f"`{value}`" for value in item["extracted_ids"])
        )
    for error in module.get("identity", {}).get("errors", []):
        lines.append(f"- Identity: {error}")
    for error in module.get("topology_errors", []):
        lines.append(f"- Topology: {error}")
    for error in module.get("record_errors", []):
        lines.append(f"- Record: {error}")
    if (
        not conflicts
        and not pending
        and not module["coverage"]["gaps"]
        and not module.get("unresolved_duplicate_candidates")
        and not module.get("identity", {}).get("errors")
        and not module.get("topology_errors")
        and not module.get("record_errors")
    ):
        lines.append("No blocking gaps, conflicts, or unreviewed uncertainties.")
    return "\n".join(lines) + "\n"


def _review_report(module: Mapping[str, Any]) -> str:
    review = module["review"]
    identity = module.get("identity", {})
    candidates = identity.get("candidate_groups", [])
    aliases = identity.get("confirmed_aliases", [])
    canonical_ids = identity.get("canonical_ids", [])
    rejected = identity.get("rejected_merges", [])
    lines = [
        "# Review report",
        "",
        f"- Overlay schema: `{review['schema']}`",
        f"- Overlay SHA-256: `{module['review_sha256']}`",
        f"- Canonical ID declarations: {len(review.get('canonical_ids', []))}",
        f"- Alias operations: {len(review['aliases'])}",
        f"- Distinct decisions: {len(review.get('distinct', []))}",
        f"- Canonical field operations: {len(review['values'])}",
        f"- Accepted uncertainties: {len(review['accepted_uncertainties'])}",
        f"- Reviewed topology composites: "
        f"{len(review.get('topology_composites', []))}",
        f"- Candidate groups: {len(candidates)}",
        "",
        "## Candidate groups",
        "",
    ]
    if not candidates:
        lines.append("No duplicate candidates.")
    for candidate in candidates:
        lines.extend(
            [
                f"- `{candidate['id']}` ({candidate['confidence']}, "
                f"{candidate['status']}): "
                + ", ".join(f"`{value}`" for value in candidate["extracted_ids"]),
                f"  - Signals: {', '.join(candidate['signals'])}",
                f"  - Source pages: {', '.join(map(str, candidate['source_pages']))}",
            ]
        )
    lines.extend(["", "## Canonical IDs", ""])
    for decision in canonical_ids:
        lines.extend(
            [
                f"- `{decision['canonical_id']}` ← "
                + ", ".join(f"`{value}`" for value in decision["extracted_ids"]),
                f"  - Source pages: {', '.join(map(str, decision['source_pages']))}",
                f"  - Rationale: {decision['rationale']}",
            ]
        )
    if not canonical_ids:
        lines.append("No canonical records.")
    lines.extend(["", "## Confirmed aliases", ""])
    for alias in aliases:
        lines.extend(
            [
                f"- `{alias['alias']}` → `{alias['canonical_id']}`",
                f"  - Source pages: {', '.join(map(str, alias['source_pages']))}",
                f"  - Rationale: {alias['rationale']}",
            ]
        )
    if not aliases:
        lines.append("No reviewed aliases.")
    lines.extend(["", "## Rejected merges", ""])
    for decision in rejected:
        lines.extend(
            [
                f"- `{decision['candidate_id']}`: "
                + " / ".join(
                    f"`{value}`" for value in decision["extracted_ids"]
                ),
                f"  - Source pages: {', '.join(map(str, decision['source_pages']))}",
                f"  - Rationale: {decision['rationale']}",
            ]
        )
    if not rejected:
        lines.append("No reviewed rejected merges.")
    lines.extend(["", review.get("notes", ""), ""])
    return "\n".join(lines)


def _module_id(module: Mapping[str, Any]) -> str:
    return module["source"].get("slug") or f"module-{module['source']['sha256'][:12]}"


def _module_entry(module: Mapping[str, Any]) -> str:
    source = module["source"]
    lines = [
        f"# {source['title']}",
        "",
        f"- Module ID: `{_module_id(module)}`",
        f"- Verification: `{_verification(module)}`",
        f"- Source file: `{source['filename']}`",
    ]
    metadata = (
        ("System", source.get("source_system") or source.get("system")),
        ("Edition", source.get("edition")),
        ("Ruleset", source.get("ruleset")),
    )
    for label, value in metadata:
        if value:
            lines.append(f"- {label}: {_display(value)}")
    lines.extend(
        [
            "",
            "## Runtime loading",
            "",
            "Use `index.md` or `index.json` to locate a relevant card, then load "
            "only that card and the cards named in its references.",
            "",
            "`audit/` is extraction evidence and is not gameplay context. Do not "
            "load it during normal play.",
            "",
            "On place cards, only `First impression` is player-safe. The other "
            "sections are GM context.",
            "",
        ]
    )
    return "\n".join(lines)


def _index_records(module: Mapping[str, Any]) -> list[dict[str, Any]]:
    aliases = _aliases_by_target(module)
    records = []
    for record in sorted(module["records"], key=lambda item: item["id"]):
        item = {
            "id": record["id"],
            "type": _runtime_type(record["record_type"]),
            "title": record["fields"].get("title", record["id"]),
            "path": card_path(record),
            "aliases": aliases.get(record["id"], []),
            "references": record["references"],
        }
        if record["record_type"] == "location":
            item["topology_node"] = record["fields"].get("topology_node")
            item["load_with"] = _load_with(record, module["records"])
        elif record["record_type"] == "situation":
            fields = record["fields"]
            effects = fields.get("possible_effects", [])
            item["activation"] = fields.get("activation")
            item["repeat"] = fields.get("repeat")
            item["load_with"] = _load_with(record, module["records"])
            item["possible_effects"] = effects if isinstance(effects, list) else []
        records.append(item)
    return records


def _runtime_topology(module: Mapping[str, Any]) -> dict[str, Any]:
    topology = module["topology"]
    return {
        "nodes": [
            {
                "id": node["id"],
                "labels": node["labels"],
                "titles": node["titles"],
                "source_pages": node["source_pages"],
                "classification": node.get("classification"),
            }
            for node in sorted(topology["nodes"], key=lambda item: item["id"])
        ],
        "passages": [
            {
                "id": passage["id"],
                "from": passage["from"],
                "to": passage["to"],
                "facets": passage["facets"],
                "source_pages": passage["source_pages"],
            }
            for passage in sorted(
                topology["passages"], key=lambda item: item["id"]
            )
        ],
    }


def _index_markdown(records: Sequence[Mapping[str, Any]]) -> str:
    lines = ["# Module index", ""]
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for record in records:
        grouped.setdefault(record["type"], []).append(record)
    for runtime_type, directory in CARD_DIRECTORY_ORDER:
        group_type = runtime_type
        if directory == "reference":
            selected = [
                item
                for item in records
                if item["path"].startswith("cards/reference/")
            ]
            heading = "Reference"
        else:
            selected = grouped.get(group_type, [])
            heading = directory.capitalize()
        if not selected:
            continue
        lines.extend([f"## {heading}", ""])
        for item in selected:
            lines.append(f"- [{item['title']}]({item['path']}) — `{item['id']}`")
        lines.append("")
    return "\n".join(lines)


def _tree_hash(root: Path, relative_paths: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(relative_paths):
        encoded = relative.encode("utf-8")
        payload = (root / relative).read_bytes()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def render_module(stage: Path, module: Mapping[str, Any]) -> None:
    stage.mkdir(parents=True, exist_ok=True)
    for _, directory in CARD_DIRECTORY_ORDER:
        (stage / "cards" / directory).mkdir(parents=True, exist_ok=True)
    audit = stage / "audit"
    audit.mkdir()

    verification = _verification(module)
    aliases = _aliases_by_target(module)
    runtime_files = set(FIXED_RUNTIME_FILES)
    for record in sorted(module["records"], key=lambda item: item["id"]):
        relative = card_path(record)
        (stage / relative).write_text(
            _card(
                record,
                aliases=aliases.get(record["id"], []),
                verification=verification,
                records=module["records"],
                topology=module["topology"],
            ),
            encoding="utf-8",
            newline="\n",
        )
        runtime_files.add(relative)

    index_records = _index_records(module)
    (stage / "MODULE.md").write_text(
        _module_entry(module), encoding="utf-8", newline="\n"
    )
    (stage / "index.md").write_text(
        _index_markdown(index_records), encoding="utf-8", newline="\n"
    )
    write_json(
        stage / "index.json",
        {"schema": RUNTIME_INDEX_SCHEMA, "records": index_records},
    )
    # Canonical JSON is a deterministic YAML 1.2 subset and preserves every
    # currently validated topology field without a YAML dependency.
    write_json(stage / "topology.yaml", _runtime_topology(module))

    write_json(audit / "module.json", module)
    (audit / "coverage.md").write_text(
        _coverage_report(module["coverage"]), encoding="utf-8", newline="\n"
    )
    (audit / "conflicts-and-gaps.md").write_text(
        _conflict_report(module), encoding="utf-8", newline="\n"
    )
    (audit / "review.md").write_text(
        _review_report(module), encoding="utf-8", newline="\n"
    )

    generated_files = sorted(runtime_files | FIXED_AUDIT_FILES)
    write_json(
        stage / "GENERATED_OUTPUT.json",
        {
            "schema": GENERATED_OUTPUT_SCHEMA,
            "play_contract": PLAY_CONTRACT,
            "module_id": _module_id(module),
            "verification": verification,
            "source_sha256": module["source"]["sha256"],
            "module_sha256": module["module_sha256"],
            "runtime_files": sorted(runtime_files),
            "audit_files": sorted(FIXED_AUDIT_FILES),
            "tree_sha256": _tree_hash(stage, generated_files),
        },
    )


def _walk_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            key for child in value.values() for key in _walk_keys(child)
        }
    if isinstance(value, list):
        return {key for child in value for key in _walk_keys(child)}
    return set()


def generated_output_is_replaceable(path: Path) -> bool:
    """Return whether an existing tree is wholly owned by the current marker."""
    if not path.is_dir():
        return False
    try:
        marker = load_json(path / "GENERATED_OUTPUT.json")
    except ExtractorError:
        return False
    expected_fields = {
        "schema",
        "play_contract",
        "module_id",
        "verification",
        "source_sha256",
        "module_sha256",
        "runtime_files",
        "audit_files",
        "tree_sha256",
    }
    if (
        not isinstance(marker, dict)
        or set(marker) != expected_fields
        or marker.get("schema") != GENERATED_OUTPUT_SCHEMA
        or marker.get("play_contract") != PLAY_CONTRACT
        or marker.get("verification") not in {"verified", "unverified"}
    ):
        return False
    runtime_files = marker.get("runtime_files")
    audit_files = marker.get("audit_files")
    if (
        not isinstance(runtime_files, list)
        or not isinstance(audit_files, list)
        or any(not isinstance(item, str) for item in runtime_files)
        or any(not isinstance(item, str) for item in audit_files)
        or runtime_files != sorted(set(runtime_files))
        or audit_files != sorted(set(audit_files))
        or set(runtime_files) & set(audit_files)
    ):
        return False
    listed = set(runtime_files) | set(audit_files)
    if any(
        relative.startswith("/") or ".." in Path(relative).parts
        for relative in listed
    ):
        return False
    actual = {
        item.relative_to(path).as_posix()
        for item in path.rglob("*")
        if item.is_file() and item.name != "GENERATED_OUTPUT.json"
    }
    if any(item.is_symlink() for item in path.rglob("*")):
        return False
    if (
        listed != actual
        or not FIXED_RUNTIME_FILES <= set(runtime_files)
        or set(audit_files) != FIXED_AUDIT_FILES
    ):
        return False
    try:
        return marker.get("tree_sha256") == _tree_hash(path, sorted(listed))
    except OSError:
        return False


def validate_rendered_module(stage: Path, module: Mapping[str, Any]) -> None:
    """Validate the complete staged tree before it can be published."""
    if not stage.is_dir():
        raise ExtractorError("generated output stage is not a directory")
    for path in stage.rglob("*"):
        if path.is_symlink():
            raise ExtractorError(f"generated output contains a symlink: {path}")

    expected_directories = {
        "audit",
        "cards",
        *(f"cards/{directory}" for _, directory in CARD_DIRECTORY_ORDER),
    }
    actual_directories = {
        path.relative_to(stage).as_posix()
        for path in stage.rglob("*")
        if path.is_dir()
    }
    if actual_directories != expected_directories:
        raise ExtractorError("generated output contains unexpected directories")

    marker = load_json(stage / "GENERATED_OUTPUT.json")
    expected_marker_fields = {
        "schema",
        "play_contract",
        "module_id",
        "verification",
        "source_sha256",
        "module_sha256",
        "runtime_files",
        "audit_files",
        "tree_sha256",
    }
    if not isinstance(marker, dict) or set(marker) != expected_marker_fields:
        raise ExtractorError("generated output marker has unexpected fields")
    if marker.get("schema") != GENERATED_OUTPUT_SCHEMA:
        raise ExtractorError("generated output marker has the wrong schema")
    if marker.get("play_contract") != PLAY_CONTRACT:
        raise ExtractorError("generated output marker has the wrong play contract")
    runtime_files = marker.get("runtime_files")
    audit_files = marker.get("audit_files")
    if (
        not isinstance(runtime_files, list)
        or not isinstance(audit_files, list)
        or any(not isinstance(item, str) for item in runtime_files)
        or any(not isinstance(item, str) for item in audit_files)
        or runtime_files != sorted(set(runtime_files))
        or audit_files != sorted(set(audit_files))
        or set(runtime_files) & set(audit_files)
    ):
        raise ExtractorError("generated output marker has invalid file lists")
    listed = set(runtime_files) | set(audit_files)
    for relative in listed:
        if (
            not isinstance(relative, str)
            or relative.startswith("/")
            or ".." in Path(relative).parts
        ):
            raise ExtractorError("generated output marker contains an unsafe path")
    actual_files = {
        path.relative_to(stage).as_posix()
        for path in stage.rglob("*")
        if path.is_file() and path.name != "GENERATED_OUTPUT.json"
    }
    if listed != actual_files:
        raise ExtractorError("generated output marker does not own the complete tree")
    expected_runtime_files = FIXED_RUNTIME_FILES | {
        card_path(record) for record in module["records"]
    }
    if set(runtime_files) != expected_runtime_files:
        raise ExtractorError("generated output has the wrong runtime file set")
    if set(audit_files) != FIXED_AUDIT_FILES:
        raise ExtractorError("generated output has the wrong audit file set")
    if (
        marker.get("module_id") != _module_id(module)
        or marker.get("verification") != _verification(module)
        or marker.get("source_sha256") != module["source"]["sha256"]
    ):
        raise ExtractorError("generated output marker has the wrong identity")
    if marker.get("tree_sha256") != _tree_hash(stage, sorted(listed)):
        raise ExtractorError("generated output tree hash does not match its contents")
    if marker.get("module_sha256") != module["module_sha256"]:
        raise ExtractorError("generated output marker has the wrong module hash")
    if load_json(stage / "audit" / "module.json") != module:
        raise ExtractorError("audit/module.json is not the authoritative module")

    expected_index = {
        "schema": RUNTIME_INDEX_SCHEMA,
        "records": _index_records(module),
    }
    index = load_json(stage / "index.json")
    if index != expected_index:
        raise ExtractorError("runtime index does not match the canonical module")
    allowed_record_fields = {
        "id",
        "type",
        "title",
        "path",
        "aliases",
        "references",
        "topology_node",
        "load_with",
        "activation",
        "repeat",
        "possible_effects",
    }
    for item in expected_index["records"]:
        if (
            not isinstance(item, dict)
            or not {"id", "type", "title", "path", "aliases", "references"}
            <= set(item)
            or not set(item) <= allowed_record_fields
        ):
            raise ExtractorError("runtime index record has unexpected fields")
    leaked = _walk_keys(index) & PROHIBITED_INDEX_FIELDS
    if leaked:
        raise ExtractorError(
            "runtime index contains audit fields: " + ", ".join(sorted(leaked))
        )
    if canonical_json_bytes(_runtime_topology(module)) != (
        stage / "topology.yaml"
    ).read_bytes():
        raise ExtractorError("topology.yaml is not canonical and deterministic")
    topology_keys = _walk_keys(load_json(stage / "topology.yaml"))
    leaked_topology = topology_keys & PROHIBITED_INDEX_FIELDS
    if leaked_topology:
        raise ExtractorError(
            "runtime topology contains audit fields: "
            + ", ".join(sorted(leaked_topology))
        )
    module_text = (stage / "MODULE.md").read_text(encoding="utf-8")
    if module_text != _module_entry(module):
        raise ExtractorError("MODULE.md does not match the canonical module")
    if (stage / "index.md").read_text(encoding="utf-8") != _index_markdown(
        expected_index["records"]
    ):
        raise ExtractorError("index.md does not match the runtime index")
    aliases = _aliases_by_target(module)
    for record in module["records"]:
        relative = card_path(record)
        expected_card = _card(
            record,
            aliases=aliases.get(record["id"], []),
            verification=_verification(module),
            records=module["records"],
            topology=module["topology"],
        )
        if (stage / relative).read_text(encoding="utf-8") != expected_card:
            raise ExtractorError(
                f"runtime card does not match the canonical record: {relative}"
            )
    expected_reports = {
        "audit/coverage.md": _coverage_report(module["coverage"]),
        "audit/conflicts-and-gaps.md": _conflict_report(module),
        "audit/review.md": _review_report(module),
    }
    for relative, expected in expected_reports.items():
        if (stage / relative).read_text(encoding="utf-8") != expected:
            raise ExtractorError(
                f"audit report does not match the canonical module: {relative}"
            )
    if marker.get("verification") == "verified":
        for relative in runtime_files:
            if relative.startswith("cards/"):
                text = (stage / relative).read_text(encoding="utf-8")
                if "\nverification: verified\n" not in text:
                    raise ExtractorError(
                        f"verified output contains an unverified card: {relative}"
                    )
