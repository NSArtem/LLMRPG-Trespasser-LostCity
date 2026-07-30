"""Canonical actor and situation validation after review is applied.

Response validation (`contracts.py`) rejects a malformed observation before it
is ever ingested. This module validates the *reconciled* record, which may also
carry values authored by the review overlay, and resolves typed references
across records and topology. It reports errors instead of raising so the Codex
task and the release gate can present every remaining decision at once.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .contracts import (
    ACTIVATION_TYPES,
    ACTOR_LIST_FIELDS,
    ACTOR_OBJECT_FIELDS,
    ACTOR_REFERENCE_FIELDS,
    ACTOR_TEXT_FIELDS,
    EFFECT_RECORD_TYPES,
    MUTABLE_ACTOR_FIELDS,
    MUTABLE_SITUATION_FIELDS,
    PLACE_REFERENCE_FIELDS,
    POSSIBLE_EFFECT_TYPES,
    REPEAT_MODES,
    SITUATION_LIST_FIELDS,
    SITUATION_OBJECT_FIELDS,
    SITUATION_REFERENCE_FIELDS,
    SITUATION_TEXT_FIELDS,
    UNTARGETED_EFFECT_TYPES,
)


REFERENCE_FIELD_TYPES = {
    "actor_references": "actor",
    "location_references": "location",
    "situation_references": "situation",
    "procedure_references": "procedure",
    "knowledge_references": "knowledge",
}
OBJECT_FIELD_TYPES = {
    "participants": ("actor_id", "actor"),
    "actor_reactions": ("actor_id", "actor"),
    "relationships": ("target_id", "actor"),
}


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_string_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(_is_text(item) for item in value)
    )


class _Resolver:
    """Shared typed-reference checks for one canonical record set."""

    def __init__(
        self,
        record_types: Mapping[str, str],
        topology_ids: set[str],
    ) -> None:
        self.record_types = record_types
        self.topology_ids = topology_ids

    def reference(
        self,
        record: Mapping[str, Any],
        identifier: Any,
        expected_type: str,
        label: str,
        errors: list[str],
    ) -> None:
        if not isinstance(identifier, str):
            errors.append(f"{record['id']}.{label} has an invalid reference")
            return
        if identifier not in record["references"]:
            errors.append(
                f"{record['id']}.{label} reference {identifier} is not in the "
                "record references"
            )
        actual = self.record_types.get(identifier)
        if actual is None:
            errors.append(
                f"{record['id']}.{label} names missing {expected_type} "
                f"{identifier}"
            )
        elif actual != expected_type:
            errors.append(
                f"{record['id']}.{label} references {actual} {identifier}"
            )

    def topology_reference(
        self,
        record: Mapping[str, Any],
        identifier: Any,
        label: str,
        errors: list[str],
    ) -> None:
        if not isinstance(identifier, str):
            errors.append(f"{record['id']}.{label} has an invalid reference")
            return
        if identifier not in record["references"]:
            errors.append(
                f"{record['id']}.{label} reference {identifier} is not in the "
                "record references"
            )
        if identifier in self.record_types:
            errors.append(
                f"{record['id']}.{label} names record {identifier} instead of a "
                "topology node or passage"
            )
        elif identifier not in self.topology_ids:
            errors.append(
                f"{record['id']}.{label} names missing topology object "
                f"{identifier}"
            )


def _check_shared_fields(
    record: Mapping[str, Any],
    resolver: _Resolver,
    *,
    forbidden: set[str],
    text_fields: set[str],
    list_fields: set[str],
    object_fields: Mapping[str, Sequence[str]],
    reference_fields: set[str],
    errors: list[str],
) -> None:
    fields = record["fields"]
    present = sorted(set(fields) & forbidden)
    if present:
        errors.append(
            f"{record['id']} carries mutable runtime state: " + ", ".join(present)
        )
    for field in sorted(text_fields):
        if field in fields and not _is_text(fields[field]):
            errors.append(f"{record['id']} has invalid {field}")
    for field in sorted(list_fields):
        if field in fields and not _is_string_list(fields[field]):
            errors.append(f"{record['id']} has invalid {field}")
    for field, keys in sorted(object_fields.items()):
        value = fields.get(field)
        if value is None:
            continue
        if not isinstance(value, list) or not value:
            errors.append(f"{record['id']} has invalid {field}")
            continue
        for item in value:
            if not isinstance(item, dict) or set(item) != set(keys):
                errors.append(f"{record['id']} has invalid {field}")
                continue
            if any(not _is_text(item[key]) for key in keys):
                errors.append(f"{record['id']} has invalid {field}")
                continue
            typed = OBJECT_FIELD_TYPES.get(field)
            if typed is not None:
                key, expected_type = typed
                resolver.reference(
                    record, item[key], expected_type, field, errors
                )
    for field in sorted(reference_fields):
        value = fields.get(field)
        if value is None:
            continue
        if (
            not isinstance(value, list)
            or not value
            or any(not isinstance(item, str) for item in value)
            or len(value) != len(set(value))
        ):
            errors.append(f"{record['id']} has invalid {field}")
            continue
        for identifier in value:
            resolver.reference(
                record, identifier, REFERENCE_FIELD_TYPES[field], field, errors
            )


def _check_actor(
    record: Mapping[str, Any], resolver: _Resolver, errors: list[str]
) -> None:
    fields = record["fields"]
    for field in ("title", "role"):
        if not _is_text(fields.get(field)):
            errors.append(f"{record['id']} has invalid {field}")
    _check_shared_fields(
        record,
        resolver,
        forbidden=MUTABLE_ACTOR_FIELDS,
        text_fields=ACTOR_TEXT_FIELDS,
        list_fields=ACTOR_LIST_FIELDS,
        object_fields=ACTOR_OBJECT_FIELDS,
        reference_fields=ACTOR_REFERENCE_FIELDS,
        errors=errors,
    )


def _check_possible_effects(
    record: Mapping[str, Any], resolver: _Resolver, errors: list[str]
) -> None:
    effects = record["fields"].get("possible_effects")
    if effects is None:
        return
    if not isinstance(effects, list) or not effects:
        errors.append(f"{record['id']} has invalid possible_effects")
        return
    for effect in effects:
        if (
            not isinstance(effect, dict)
            or effect.get("effect") not in POSSIBLE_EFFECT_TYPES
            or not _is_text(effect.get("description"))
            or not set(effect)
            <= {"effect", "target", "description", "condition"}
            or (
                effect.get("condition") is not None
                and not _is_text(effect.get("condition"))
            )
        ):
            errors.append(f"{record['id']} has invalid possible_effects")
            continue
        kind = effect["effect"]
        target = effect.get("target")
        if kind in UNTARGETED_EFFECT_TYPES:
            if target is not None:
                errors.append(
                    f"{record['id']} possible effect {kind} must not name a target"
                )
            continue
        label = f"possible_effects[{kind}]"
        expected_type = EFFECT_RECORD_TYPES.get(kind)
        if expected_type is None:
            resolver.topology_reference(record, target, label, errors)
        else:
            resolver.reference(record, target, expected_type, label, errors)


def _check_situation(
    record: Mapping[str, Any], resolver: _Resolver, errors: list[str]
) -> None:
    fields = record["fields"]
    for field in ("title", "perceived"):
        if not _is_text(fields.get(field)):
            errors.append(f"{record['id']} has invalid {field}")
    activation = fields.get("activation")
    if (
        not isinstance(activation, dict)
        or set(activation) != {"type", "condition"}
        or activation.get("type") not in ACTIVATION_TYPES
        or not _is_text(activation.get("condition"))
    ):
        errors.append(f"{record['id']} has invalid activation")
    repeat = fields.get("repeat")
    if repeat is not None and (
        not isinstance(repeat, dict)
        or not {"mode"} <= set(repeat)
        or not set(repeat) <= {"mode", "condition"}
        or repeat.get("mode") not in REPEAT_MODES
        or (
            repeat.get("condition") is not None
            and not _is_text(repeat.get("condition"))
        )
    ):
        errors.append(f"{record['id']} has invalid repeat")
    _check_shared_fields(
        record,
        resolver,
        forbidden=MUTABLE_SITUATION_FIELDS,
        text_fields=SITUATION_TEXT_FIELDS,
        list_fields=SITUATION_LIST_FIELDS,
        object_fields=SITUATION_OBJECT_FIELDS,
        reference_fields=SITUATION_REFERENCE_FIELDS,
        errors=errors,
    )
    _check_possible_effects(record, resolver, errors)


def _check_place_references(
    record: Mapping[str, Any], resolver: _Resolver, errors: list[str]
) -> None:
    for field in sorted(PLACE_REFERENCE_FIELDS):
        value = record["fields"].get(field)
        if not isinstance(value, list):
            continue
        for identifier in value:
            resolver.reference(
                record, identifier, REFERENCE_FIELD_TYPES[field], field, errors
            )


def resolve_operational_records(
    reviewed: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate canonical actors and situations and return a reviewed copy."""
    result = deepcopy(dict(reviewed))
    records = result["records"]
    topology = result.get("topology", {"nodes": [], "passages": []})
    topology_ids = {node["id"] for node in topology.get("nodes", [])} | {
        edge["id"] for edge in topology.get("passages", [])
    }
    record_types = {record["id"]: record["record_type"] for record in records}
    resolver = _Resolver(record_types, topology_ids)
    errors: list[str] = []
    for record in sorted(records, key=lambda item: item["id"]):
        record_type = record["record_type"]
        if record_type == "actor":
            _check_actor(record, resolver, errors)
        elif record_type == "situation":
            _check_situation(record, resolver, errors)
            # One situation has one identity: the card ID is also the only ID
            # any other object may use to reach it.
            if record["id"] in topology_ids:
                errors.append(
                    f"situation {record['id']} also claims a topology identity"
                )
        elif record_type == "location":
            _check_place_references(record, resolver, errors)
    result["record_errors"] = sorted(set(errors))
    return result
