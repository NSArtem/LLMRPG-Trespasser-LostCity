"""Versioned extraction contracts and strict validators."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from .errors import ExtractorError
from .util import SAFE_ID, SAFE_SLUG, require_safe_id, require_sha256


ROUTING_SCHEMA = "module-routing/v1"
CONTENT_SCHEMA = "module-content-evidence/v3"
MAP_SCHEMA = "module-map-evidence/v2"
REVIEW_SCHEMA = "module-review-overlay/v3"
COVERAGE_SCHEMA = "module-coverage/v1"
CANONICAL_SCHEMA = "operational-module/v3"
GENERATED_OUTPUT_SCHEMA = "module-extractor-generated-output/v4"
RUNTIME_INDEX_SCHEMA = "operational-module-index/v4"
PLAY_CONTRACT = "module-play/v1"

ROUTING_TASKS = {
    "adventure",
    "rules",
    "tables",
    "items",
    "spells",
    "classes",
    "effects",
    "maps",
    "illustrations",
}
EXCLUSION_REASONS = {
    "cover",
    "divider",
    "blank",
    "non-operational-illustration",
}
CONTENT_TASKS = ROUTING_TASKS - {"illustrations", "maps"}
PACK_TASKS = {"content", "maps"}
TASK_RECORD_TYPES = {
    "adventure": {"location", "actor", "situation", "procedure", "knowledge"},
    "rules": {"rule"},
    "tables": {"table"},
    "items": {"item"},
    "spells": {"spell"},
    "classes": {"class"},
    "effects": {"effect"},
}
MAP_RENDER_BUDGET = 16 * 1024 * 1024
CONFIDENCES = {"high", "medium", "low"}
RECORD_TYPES = {
    "location",
    "actor",
    "situation",
    "procedure",
    "knowledge",
    "rule",
    "table",
    "item",
    "spell",
    "class",
    "effect",
}
REQUIRED_FIELDS = {
    "location": ("title", "first_impression"),
    "actor": ("title", "role"),
    "situation": ("title", "perceived", "activation"),
    "procedure": ("title", "trigger", "steps"),
    "knowledge": ("title", "text"),
    "rule": ("title", "text"),
    "table": ("title", "entries"),
    "item": ("title", "text"),
    "spell": ("title", "text"),
    "class": ("title", "text"),
    "effect": ("title", "text"),
}
REQUIRED_FIELD_KINDS = {
    "steps": list,
    "entries": list,
    "activation": dict,
}

PLACE_LIST_FIELDS = {
    "contents",
    "hidden",
    "triggers",
    "hazards",
    "resources",
    "occupants",
}
PLACE_REFERENCE_FIELDS = {
    "actor_references",
    "situation_references",
    "procedure_references",
    "knowledge_references",
}
PLACE_MATCH_FIELDS = {
    "keyed_area",
    "area_number",
    "map_label",
    "topology_label",
}

ACTOR_TEXT_FIELDS = {"appearance", "role"}
ACTOR_LIST_FIELDS = {
    "goals",
    "behavior",
    "capabilities",
    "hidden",
    "starting_state",
}
ACTOR_OBJECT_FIELDS = {
    "reactions": ("stimulus", "response"),
    "relationships": ("relationship", "target_id"),
}
ACTOR_REFERENCE_FIELDS = {
    "knowledge_references",
    "location_references",
    "situation_references",
}
# Runtime state belongs to the campaign checkpoint, never to the immutable
# module baseline. `starting_state` is the one labeled exception.
MUTABLE_ACTOR_FIELDS = {
    "attitude",
    "current_attitude",
    "current_health",
    "current_location",
    "current_position",
    "current_status",
    "disposition",
    "health",
    "hit_points",
    "hp",
    "inventory",
    "mood",
    "position",
    "status",
    "wounds",
}

SITUATION_TEXT_FIELDS = {"perceived"}
SITUATION_LIST_FIELDS = {"stakes", "approaches", "outcomes", "completion"}
SITUATION_OBJECT_FIELDS = {
    "participants": ("actor_id", "role"),
    "actor_reactions": ("actor_id", "reaction"),
}
SITUATION_REFERENCE_FIELDS = {
    "location_references",
    "procedure_references",
    "knowledge_references",
}
# A situation card describes source possibilities. It never records that an
# effect was applied or that the situation already ran.
MUTABLE_SITUATION_FIELDS = {
    "active",
    "applied_effects",
    "completed",
    "current_state",
    "progress",
    "resolved",
    "state",
    "status",
}
ACTIVATION_TYPES = {
    "triggered",
    "timed",
    "random",
    "keyed",
    "ongoing",
    "chosen",
}
REPEAT_MODES = {"once", "repeatable"}
POSSIBLE_EFFECT_TYPES = {
    "activate-situation",
    "actor-state",
    "future-thread",
    "reveal-knowledge",
    "schedule-procedure",
    "stop-procedure",
    "topology-state",
}
# Effects that name a record of a specific canonical type.
EFFECT_RECORD_TYPES = {
    "activate-situation": "situation",
    "actor-state": "actor",
    "reveal-knowledge": "knowledge",
    "schedule-procedure": "procedure",
    "stop-procedure": "procedure",
}
# `topology-state` names a topology node or passage; `future-thread` names
# nothing that exists yet.
UNTARGETED_EFFECT_TYPES = {"future-thread"}
# Object keys inside typed fields that hold a record or topology identifier.
IDENTIFIER_KEYS = {"actor_id", "target_id", "target"}


def as_object(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExtractorError(f"{context} must be an object")
    return value


def as_array(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise ExtractorError(f"{context} must be an array")
    return value


def as_string(value: Any, context: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value.strip()):
        raise ExtractorError(f"{context} must be a string")
    return value


def validate_source(value: Any, context: str = "source") -> dict[str, Any]:
    source = as_object(value, context)
    require_sha256(source.get("sha256"), f"{context}.sha256")
    pages = source.get("pdf_pages")
    if not isinstance(pages, int) or isinstance(pages, bool) or pages < 1:
        raise ExtractorError(f"{context}.pdf_pages must be a positive integer")
    as_string(source.get("title"), f"{context}.title")
    as_string(source.get("filename"), f"{context}.filename")
    if source.get("slug") is not None and (
        not isinstance(source["slug"], str)
        or not SAFE_SLUG.fullmatch(source["slug"])
    ):
        raise ExtractorError(f"{context}.slug is invalid")
    return source


def validate_pages(
    value: Any,
    context: str,
    *,
    page_count: int,
    allowed: set[int] | None = None,
) -> list[int]:
    pages = as_array(value, context)
    if not pages:
        raise ExtractorError(f"{context} must not be empty")
    if any(not isinstance(page, int) or isinstance(page, bool) for page in pages):
        raise ExtractorError(f"{context} must contain integers")
    if len(pages) != len(set(pages)):
        raise ExtractorError(f"{context} contains duplicate pages")
    outside = [page for page in pages if page < 1 or page > page_count]
    if outside:
        raise ExtractorError(f"{context} is outside physical page range")
    if allowed is not None and any(page not in allowed for page in pages):
        raise ExtractorError(f"{context} cites pages outside its pack")
    return sorted(pages)


def validate_routing(value: Any, source: Mapping[str, Any]) -> list[dict[str, Any]]:
    response = as_object(value, "routing response")
    if response.get("schema") != ROUTING_SCHEMA:
        raise ExtractorError(f"routing response schema must be {ROUTING_SCHEMA}")
    if response.get("source_sha256") != source["sha256"]:
        raise ExtractorError("routing source_sha256 does not match prepared source")
    pages = as_array(response.get("pages"), "routing.pages")
    seen: set[int] = set()
    results: list[dict[str, Any]] = []
    for index, raw in enumerate(pages):
        context = f"routing.pages[{index}]"
        item = as_object(raw, context)
        page = item.get("pdf_page")
        if (
            not isinstance(page, int)
            or isinstance(page, bool)
            or page < 1
            or page > source["pdf_pages"]
        ):
            raise ExtractorError(f"{context}.pdf_page is invalid")
        if page in seen:
            raise ExtractorError(f"routing contains duplicate physical page {page}")
        seen.add(page)
        tasks = as_array(item.get("tasks"), f"{context}.tasks")
        if any(task not in ROUTING_TASKS for task in tasks):
            raise ExtractorError(f"{context}.tasks contains an unknown task")
        if len(tasks) != len(set(tasks)):
            raise ExtractorError(f"{context}.tasks contains duplicates")
        reason = item.get("exclusion_reason")
        if tasks and reason is not None:
            raise ExtractorError(f"{context} cannot be both routed and excluded")
        if not tasks and reason not in EXCLUSION_REASONS:
            raise ExtractorError(f"{context} needs an explicit exclusion_reason")
        if tasks == ["illustrations"] or set(tasks) == {"illustrations"}:
            raise ExtractorError(
                f"{context} has only an illustration; explicitly exclude it instead"
            )
        confidence = item.get("confidence")
        if confidence not in CONFIDENCES:
            raise ExtractorError(f"{context}.confidence is invalid")
        as_string(item.get("notes", ""), f"{context}.notes", nonempty=False)
        results.append(
            {
                "pdf_page": page,
                "tasks": sorted(tasks),
                "exclusion_reason": reason,
                "confidence": confidence,
                "notes": item.get("notes", ""),
            }
        )
    missing = sorted(set(range(1, source["pdf_pages"] + 1)) - seen)
    if missing:
        raise ExtractorError(f"routing is missing physical pages: {missing}")
    if len(pages) != source["pdf_pages"]:
        raise ExtractorError("routing must contain exactly one row per physical page")
    return sorted(results, key=lambda item: item["pdf_page"])


def validate_pack_manifest(
    value: Any, source: Mapping[str, Any]
) -> list[dict[str, Any]]:
    manifest = as_object(value, "packs manifest")
    if manifest.get("schema") != "module-pack-manifest/v1":
        raise ExtractorError("packs manifest has the wrong schema")
    if manifest.get("source_sha256") != source["sha256"]:
        raise ExtractorError("packs manifest source hash does not match")
    packs = as_array(manifest.get("packs"), "packs")
    identifiers: set[str] = set()
    results: list[dict[str, Any]] = []
    for index, raw in enumerate(packs):
        context = f"packs[{index}]"
        pack = as_object(raw, context)
        identifier = require_safe_id(pack.get("pack_id"), f"{context}.pack_id")
        if identifier in identifiers:
            raise ExtractorError(f"duplicate pack ID: {identifier}")
        identifiers.add(identifier)
        task = pack.get("task")
        if task not in PACK_TASKS:
            raise ExtractorError(f"{context}.task is invalid")
        pages = validate_pages(
            pack.get("physical_pages"),
            f"{context}.physical_pages",
            page_count=source["pdf_pages"],
        )
        maximum = 20 if task == "maps" else 8
        if len(pages) > maximum:
            raise ExtractorError(f"{identifier} exceeds the {maximum}-page pack limit")
        if task == "content" and any(
            right != left + 1 for left, right in zip(pages, pages[1:])
        ):
            raise ExtractorError(f"{identifier} pages must be contiguous")
        if task == "content":
            text_bytes = pack.get("text_bytes")
            if (
                not isinstance(text_bytes, int)
                or isinstance(text_bytes, bool)
                or text_bytes < 0
            ):
                raise ExtractorError(f"{context}.text_bytes must be a nonnegative integer")
            tasks = as_array(pack.get("tasks"), f"{context}.tasks")
            if (
                not tasks
                or any(not isinstance(item, str) for item in tasks)
                or len(tasks) != len(set(tasks))
                or any(item not in CONTENT_TASKS for item in tasks)
            ):
                raise ExtractorError(f"{context}.tasks must contain unique content tasks")
            page_tasks = as_array(pack.get("page_tasks"), f"{context}.page_tasks")
            seen_pages: set[int] = set()
            routed_tasks: set[str] = set()
            checked_page_tasks = []
            for page_index, raw_page in enumerate(page_tasks):
                page_context = f"{context}.page_tasks[{page_index}]"
                page_row = as_object(raw_page, page_context)
                page = page_row.get("pdf_page")
                if (
                    not isinstance(page, int)
                    or isinstance(page, bool)
                    or page not in pages
                    or page in seen_pages
                ):
                    raise ExtractorError(
                        f"{page_context}.pdf_page must uniquely identify a pack page"
                    )
                seen_pages.add(page)
                row_tasks = as_array(page_row.get("tasks"), f"{page_context}.tasks")
                if (
                    any(not isinstance(item, str) for item in row_tasks)
                    or len(row_tasks) != len(set(row_tasks))
                    or any(item not in CONTENT_TASKS for item in row_tasks)
                ):
                    raise ExtractorError(
                        f"{page_context}.tasks contains an invalid content task"
                    )
                reason = page_row.get("context_reason")
                if row_tasks and reason is not None:
                    raise ExtractorError(
                        f"{page_context} cannot have tasks and a context reason"
                    )
                if not row_tasks and reason != "non-operational-illustration":
                    raise ExtractorError(
                        f"{page_context} without tasks must be illustration context"
                    )
                routed_tasks.update(row_tasks)
                checked_page_tasks.append(
                    {
                        "pdf_page": page,
                        "tasks": sorted(row_tasks),
                        "context_reason": reason,
                    }
                )
            if seen_pages != set(pages):
                raise ExtractorError(f"{context}.page_tasks must cover every pack page")
            if sorted(routed_tasks) != sorted(tasks):
                raise ExtractorError(f"{context}.tasks does not match page_tasks")
            pack = {
                **pack,
                "tasks": sorted(tasks),
                "page_tasks": sorted(
                    checked_page_tasks, key=lambda item: item["pdf_page"]
                ),
                "text_bytes": text_bytes,
            }
        else:
            render_bytes = pack.get("render_bytes")
            if (
                not isinstance(render_bytes, int)
                or isinstance(render_bytes, bool)
                or render_bytes < 1
            ):
                raise ExtractorError(
                    f"{context}.render_bytes must be a positive integer"
                )
            if render_bytes > MAP_RENDER_BUDGET and len(pages) > 1:
                raise ExtractorError(
                    f"{identifier} exceeds the map render budget"
                )
            pack = {**pack, "render_bytes": render_bytes}
        require_sha256(pack.get("pack_sha256"), f"{context}.pack_sha256")
        if pack.get("ingested_response_sha256") is not None:
            require_sha256(
                pack["ingested_response_sha256"],
                f"{context}.ingested_response_sha256",
            )
        response_path = as_string(
            pack.get("response_path"), f"{context}.response_path"
        )
        archive_path = as_string(pack.get("archive_path"), f"{context}.archive_path")
        results.append(
            {
                **pack,
                "pack_id": identifier,
                "physical_pages": pages,
                "response_path": response_path,
                "archive_path": archive_path,
            }
        )
    return sorted(results, key=lambda item: item["pack_id"])


def _validate_string_list(
    fields: Mapping[str, Any], field: str, context: str
) -> None:
    if field not in fields:
        return
    items = as_array(fields[field], f"{context}.fields.{field}")
    if not items or any(
        not isinstance(item, str) or not item.strip() for item in items
    ):
        raise ExtractorError(
            f"{context}.fields.{field} must contain one or more non-empty strings"
        )


def _validate_reference_list(
    fields: Mapping[str, Any], field: str, context: str
) -> None:
    if field not in fields:
        return
    items = as_array(fields[field], f"{context}.fields.{field}")
    if not items:
        raise ExtractorError(
            f"{context}.fields.{field} must be omitted instead of empty"
        )
    if len(items) != len(set(items)):
        raise ExtractorError(f"{context}.fields.{field} contains duplicates")
    for index, item in enumerate(items):
        require_safe_id(item, f"{context}.fields.{field}[{index}]")


def _validate_object_list(
    fields: Mapping[str, Any],
    field: str,
    keys: Sequence[str],
    context: str,
) -> None:
    if field not in fields:
        return
    items = as_array(fields[field], f"{context}.fields.{field}")
    if not items:
        raise ExtractorError(
            f"{context}.fields.{field} must be omitted instead of empty"
        )
    for index, raw in enumerate(items):
        item_context = f"{context}.fields.{field}[{index}]"
        item = as_object(raw, item_context)
        if set(item) != set(keys):
            raise ExtractorError(
                f"{item_context} must contain exactly " + ", ".join(sorted(keys))
            )
        for key in sorted(keys):
            if key in IDENTIFIER_KEYS:
                require_safe_id(item[key], f"{item_context}.{key}")
            else:
                as_string(item[key], f"{item_context}.{key}")


def _validate_mutable_fields(
    fields: Mapping[str, Any], forbidden: set[str], context: str
) -> None:
    present = sorted(set(fields) & forbidden)
    if present:
        raise ExtractorError(
            f"{context}.fields must not carry mutable runtime state: "
            + ", ".join(present)
        )


def _validate_activation(value: Any, context: str) -> None:
    activation = as_object(value, context)
    if set(activation) != {"type", "condition"}:
        raise ExtractorError(f"{context} must contain type and condition")
    if activation["type"] not in ACTIVATION_TYPES:
        raise ExtractorError(
            f"{context}.type must be one of " + ", ".join(sorted(ACTIVATION_TYPES))
        )
    as_string(activation["condition"], f"{context}.condition")


def _validate_repeat(value: Any, context: str) -> None:
    repeat = as_object(value, context)
    if not {"mode"} <= set(repeat) or not set(repeat) <= {"mode", "condition"}:
        raise ExtractorError(f"{context} must contain mode and optional condition")
    if repeat["mode"] not in REPEAT_MODES:
        raise ExtractorError(
            f"{context}.mode must be one of " + ", ".join(sorted(REPEAT_MODES))
        )
    if repeat.get("condition") is not None:
        as_string(repeat["condition"], f"{context}.condition")


def _validate_possible_effects(value: Any, context: str) -> None:
    effects = as_array(value, context)
    if not effects:
        raise ExtractorError(f"{context} must be omitted instead of empty")
    seen: set[tuple[str, str | None, str]] = set()
    for index, raw in enumerate(effects):
        item_context = f"{context}[{index}]"
        effect = as_object(raw, item_context)
        if not {"effect", "description"} <= set(effect) or not set(effect) <= {
            "effect",
            "target",
            "description",
            "condition",
        }:
            raise ExtractorError(
                f"{item_context} must contain effect, description, and optional "
                "target and condition"
            )
        kind = effect["effect"]
        if kind not in POSSIBLE_EFFECT_TYPES:
            raise ExtractorError(
                f"{item_context}.effect must be one of "
                + ", ".join(sorted(POSSIBLE_EFFECT_TYPES))
            )
        description = as_string(effect["description"], f"{item_context}.description")
        target = effect.get("target")
        if kind in UNTARGETED_EFFECT_TYPES:
            if target is not None:
                raise ExtractorError(f"{item_context} must not name a target")
        else:
            require_safe_id(target, f"{item_context}.target")
        if effect.get("condition") is not None:
            as_string(effect["condition"], f"{item_context}.condition")
        key = (kind, target, description)
        if key in seen:
            raise ExtractorError(f"{item_context} duplicates an earlier effect")
        seen.add(key)


def _validate_place_fields(fields: Mapping[str, Any], context: str) -> None:
    for field in sorted(PLACE_LIST_FIELDS):
        _validate_string_list(fields, field, context)
    for field in sorted(PLACE_REFERENCE_FIELDS):
        _validate_reference_list(fields, field, context)
    if "discoverable" in fields:
        _validate_object_list(
            fields, "discoverable", ("information", "condition"), context
        )
    if "topology_node" in fields and fields["topology_node"] is not None:
        node = fields["topology_node"]
        if not isinstance(node, str) or not SAFE_ID.fullmatch(node):
            raise ExtractorError(
                f"{context}.fields.topology_node must be a map node ID or "
                "null; record the printed area key in keyed_area or map_label "
                "instead of a map label"
            )
    for field in sorted(PLACE_MATCH_FIELDS):
        if field in fields and (
            not isinstance(fields[field], (str, int))
            or isinstance(fields[field], bool)
            or not str(fields[field]).strip()
        ):
            raise ExtractorError(
                f"{context}.fields.{field} must be a non-empty string or integer"
            )


def _validate_actor_fields(fields: Mapping[str, Any], context: str) -> None:
    _validate_mutable_fields(fields, MUTABLE_ACTOR_FIELDS, context)
    for field in sorted(ACTOR_TEXT_FIELDS):
        if field in fields:
            as_string(fields[field], f"{context}.fields.{field}")
    for field in sorted(ACTOR_LIST_FIELDS):
        _validate_string_list(fields, field, context)
    for field, keys in sorted(ACTOR_OBJECT_FIELDS.items()):
        _validate_object_list(fields, field, keys, context)
    for field in sorted(ACTOR_REFERENCE_FIELDS):
        _validate_reference_list(fields, field, context)


def _validate_situation_fields(fields: Mapping[str, Any], context: str) -> None:
    _validate_mutable_fields(fields, MUTABLE_SITUATION_FIELDS, context)
    for field in sorted(SITUATION_TEXT_FIELDS):
        if field in fields:
            as_string(fields[field], f"{context}.fields.{field}")
    if "activation" in fields:
        _validate_activation(fields["activation"], f"{context}.fields.activation")
    if "repeat" in fields:
        _validate_repeat(fields["repeat"], f"{context}.fields.repeat")
    for field in sorted(SITUATION_LIST_FIELDS):
        _validate_string_list(fields, field, context)
    for field, keys in sorted(SITUATION_OBJECT_FIELDS.items()):
        _validate_object_list(fields, field, keys, context)
    for field in sorted(SITUATION_REFERENCE_FIELDS):
        _validate_reference_list(fields, field, context)
    if "possible_effects" in fields:
        _validate_possible_effects(
            fields["possible_effects"], f"{context}.fields.possible_effects"
        )


RECORD_FIELD_VALIDATORS = {
    "location": _validate_place_fields,
    "actor": _validate_actor_fields,
    "situation": _validate_situation_fields,
}


def validate_record(
    value: Any,
    context: str,
    *,
    page_count: int,
    allowed_pages: set[int],
) -> dict[str, Any]:
    record = as_object(value, context)
    identifier = require_safe_id(record.get("id"), f"{context}.id")
    record_type = record.get("record_type")
    if record_type not in RECORD_TYPES:
        raise ExtractorError(f"{context}.record_type is invalid")
    fields = as_object(record.get("fields"), f"{context}.fields")
    for field in REQUIRED_FIELDS[record_type]:
        if field not in fields:
            raise ExtractorError(f"{context}.fields.{field} is required")
        expected = REQUIRED_FIELD_KINDS.get(field, str)
        if not isinstance(fields[field], expected):
            raise ExtractorError(
                f"{context}.fields.{field} must be {expected.__name__}"
            )
    validator = RECORD_FIELD_VALIDATORS.get(record_type)
    if validator is not None:
        validator(fields, context)
    pages = validate_pages(
        record.get("source_pages"),
        f"{context}.source_pages",
        page_count=page_count,
        allowed=allowed_pages,
    )
    if record.get("confidence") not in CONFIDENCES:
        raise ExtractorError(f"{context}.confidence is invalid")
    references = record.get("references", [])
    if not isinstance(references, list):
        raise ExtractorError(f"{context}.references must be an array")
    for ref_index, reference in enumerate(references):
        require_safe_id(reference, f"{context}.references[{ref_index}]")
    uncertainties = record.get("uncertainties", [])
    if not isinstance(uncertainties, list):
        raise ExtractorError(f"{context}.uncertainties must be an array")
    checked_uncertainties: list[dict[str, Any]] = []
    for number, uncertainty in enumerate(uncertainties, 1):
        item = as_object(uncertainty, f"{context}.uncertainties[{number - 1}]")
        description = as_string(
            item.get("description"), f"{context}.uncertainties[{number - 1}].description"
        )
        uncertainty_pages = validate_pages(
            item.get("source_pages"),
            f"{context}.uncertainties[{number - 1}].source_pages",
            page_count=page_count,
            allowed=allowed_pages,
        )
        checked_uncertainties.append(
            {
                "id": item.get("id") or f"{identifier}.uncertainty-{number:03d}",
                "target_id": identifier,
                "description": description,
                "source_pages": uncertainty_pages,
            }
        )
    return {
        "id": identifier,
        "record_type": record_type,
        "fields": fields,
        "source_pages": pages,
        "confidence": record["confidence"],
        "references": references,
        "uncertainties": checked_uncertainties,
    }


def validate_content_response(
    value: Any, pack: Mapping[str, Any], source: Mapping[str, Any]
) -> list[dict[str, Any]]:
    response = as_object(value, f"response {pack['pack_id']}")
    if response.get("schema") != CONTENT_SCHEMA:
        raise ExtractorError(
            f"response {pack['pack_id']} schema must be {CONTENT_SCHEMA}"
        )
    if response.get("source_sha256") != source["sha256"]:
        raise ExtractorError(f"response {pack['pack_id']} source hash does not match")
    if response.get("pack_id") != pack["pack_id"]:
        raise ExtractorError(f"response pack ID does not match {pack['pack_id']}")
    if response.get("task") != pack["task"]:
        raise ExtractorError(f"response {pack['pack_id']} task does not match")
    records = [
        validate_record(
            raw,
            f"response {pack['pack_id']}.records[{index}]",
            page_count=source["pdf_pages"],
            allowed_pages=set(pack["physical_pages"]),
        )
        for index, raw in enumerate(
            as_array(response.get("records"), f"response {pack['pack_id']}.records")
        )
    ]
    identifiers = [record["id"] for record in records]
    duplicates = sorted(
        identifier for identifier, count in Counter(identifiers).items() if count > 1
    )
    if duplicates:
        raise ExtractorError(
            f"response {pack['pack_id']} has duplicate record IDs: {duplicates}"
        )
    validate_content_task_coverage(response, pack, records)
    return records


def validate_content_task_coverage(
    response: Mapping[str, Any],
    pack: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    planned = {
        (row["pdf_page"], task)
        for row in pack["page_tasks"]
        for task in row["tasks"]
    }
    by_id = {record["id"]: record for record in records}
    covered_records: set[str] = set()
    seen: set[tuple[int, str]] = set()
    checked = []
    for index, raw in enumerate(
        as_array(
            response.get("task_coverage"),
            f"response {pack['pack_id']}.task_coverage",
        )
    ):
        context = f"response {pack['pack_id']}.task_coverage[{index}]"
        item = as_object(raw, context)
        page = item.get("pdf_page")
        task = item.get("task")
        if (
            not isinstance(page, int)
            or isinstance(page, bool)
            or not isinstance(task, str)
        ):
            raise ExtractorError(f"{context} needs a physical page and task")
        key = (page, task)
        if key not in planned:
            raise ExtractorError(f"{context} is not a routed page/task pair")
        if key in seen:
            raise ExtractorError(f"{context} duplicates a page/task pair")
        seen.add(key)
        status = item.get("status")
        if status not in {"extracted", "not-found"}:
            raise ExtractorError(f"{context}.status is invalid")
        record_ids = as_array(item.get("record_ids"), f"{context}.record_ids")
        if any(not isinstance(record_id, str) for record_id in record_ids) or len(
            record_ids
        ) != len(set(record_ids)):
            raise ExtractorError(f"{context}.record_ids must be unique strings")
        notes = item.get("notes", "")
        if not isinstance(notes, str):
            raise ExtractorError(f"{context}.notes must be a string")
        if status == "not-found":
            if record_ids or not notes.strip():
                raise ExtractorError(
                    f"{context} not-found coverage needs notes and no record IDs"
                )
        else:
            if not record_ids:
                raise ExtractorError(
                    f"{context} extracted coverage needs record IDs"
                )
            for record_id in record_ids:
                record = by_id.get(record_id)
                if record is None:
                    raise ExtractorError(
                        f"{context} references unknown record {record_id}"
                    )
                if record["record_type"] not in TASK_RECORD_TYPES[task]:
                    raise ExtractorError(
                        f"{context} record {record_id} has an incompatible type"
                    )
                if page not in record["source_pages"]:
                    raise ExtractorError(
                        f"{context} record {record_id} does not cite page {page}"
                    )
                covered_records.add(record_id)
        checked.append(
            {
                "pdf_page": page,
                "task": task,
                "status": status,
                "record_ids": sorted(record_ids),
                "notes": notes,
            }
        )
    missing = sorted(planned - seen)
    if missing:
        raise ExtractorError(
            f"response {pack['pack_id']} is missing task coverage: {missing}"
        )
    orphaned = sorted(set(by_id) - covered_records)
    if orphaned:
        raise ExtractorError(
            f"response {pack['pack_id']} has records outside task coverage: {orphaned}"
        )
    return sorted(checked, key=lambda item: (item["pdf_page"], item["task"]))


def validate_review(
    value: Any, source: Mapping[str, Any]
) -> dict[str, Any]:
    review = as_object(value, "review overlay")
    if review.get("schema") != REVIEW_SCHEMA:
        raise ExtractorError(f"review overlay schema must be {REVIEW_SCHEMA}")
    if review.get("source_sha256") != source["sha256"]:
        raise ExtractorError("review overlay source hash does not match")
    canonical_ids = as_array(
        review.get("canonical_ids", []), "review.canonical_ids"
    )
    aliases = as_array(review.get("aliases", []), "review.aliases")
    distinct = as_array(review.get("distinct", []), "review.distinct")
    values = as_array(review.get("values", []), "review.values")
    accepted = as_array(
        review.get("accepted_uncertainties", []), "review.accepted_uncertainties"
    )
    composites = as_array(
        review.get("topology_composites", []), "review.topology_composites"
    )
    checked_canonical_ids = []
    canonical_declarations: set[str] = set()
    for index, raw in enumerate(canonical_ids):
        context = f"review.canonical_ids[{index}]"
        item = as_object(raw, context)
        extracted_id = require_safe_id(
            item.get("extracted_id"), f"{context}.extracted_id"
        )
        if extracted_id in canonical_declarations:
            raise ExtractorError(
                f"review declares a canonical ID for {extracted_id} more than once"
            )
        canonical_declarations.add(extracted_id)
        checked_canonical_ids.append(
            {
                "extracted_id": extracted_id,
                "canonical_id": require_safe_id(
                    item.get("canonical_id"), f"{context}.canonical_id"
                ),
                "source_pages": validate_pages(
                    item.get("source_pages"),
                    f"{context}.source_pages",
                    page_count=source["pdf_pages"],
                ),
                "rationale": as_string(
                    item.get("rationale"), f"{context}.rationale"
                ),
            }
        )

    checked_aliases = []
    for index, raw in enumerate(aliases):
        context = f"review.aliases[{index}]"
        item = as_object(raw, context)
        alias = require_safe_id(item.get("alias"), f"{context}.alias")
        target_id = require_safe_id(item.get("target_id"), f"{context}.target_id")
        pages = validate_pages(
            item.get("source_pages"),
            f"{context}.source_pages",
            page_count=source["pdf_pages"],
        )
        rationale = as_string(item.get("rationale"), f"{context}.rationale")
        checked_aliases.append(
            {
                "alias": alias,
                "target_id": target_id,
                "source_pages": pages,
                "rationale": rationale,
            }
        )
    checked_distinct = []
    distinct_pairs: set[tuple[str, str]] = set()
    for index, raw in enumerate(distinct):
        context = f"review.distinct[{index}]"
        item = as_object(raw, context)
        left_id = require_safe_id(item.get("left_id"), f"{context}.left_id")
        right_id = require_safe_id(item.get("right_id"), f"{context}.right_id")
        if left_id == right_id:
            raise ExtractorError(f"{context} must name two different IDs")
        pair = tuple(sorted((left_id, right_id)))
        if pair in distinct_pairs:
            raise ExtractorError(f"duplicate distinct decision: {list(pair)}")
        distinct_pairs.add(pair)
        checked_distinct.append(
            {
                "left_id": pair[0],
                "right_id": pair[1],
                "source_pages": validate_pages(
                    item.get("source_pages"),
                    f"{context}.source_pages",
                    page_count=source["pdf_pages"],
                ),
                "rationale": as_string(
                    item.get("rationale"), f"{context}.rationale"
                ),
            }
        )
    checked_values = []
    value_keys: set[tuple[str, str]] = set()
    for index, raw in enumerate(values):
        context = f"review.values[{index}]"
        item = as_object(raw, context)
        object_id = require_safe_id(item.get("object_id"), f"{context}.object_id")
        field = as_string(item.get("field"), f"{context}.field")
        key = (object_id, field)
        if key in value_keys:
            raise ExtractorError(f"review selects {object_id}.{field} more than once")
        value_keys.add(key)
        if "value" not in item:
            raise ExtractorError(f"{context}.value is required")
        mode = item.get("mode", "select")
        if mode not in {"select", "compose"}:
            raise ExtractorError(f"{context}.mode must be select or compose")
        pages = validate_pages(
            item.get("source_pages"),
            f"{context}.source_pages",
            page_count=source["pdf_pages"],
        )
        rationale = as_string(item.get("rationale"), f"{context}.rationale")
        checked_values.append(
            {
                "object_id": object_id,
                "field": field,
                "value": item["value"],
                "mode": mode,
                "source_pages": pages,
                "rationale": rationale,
            }
        )
    checked_accepted = []
    accepted_ids: set[str] = set()
    for index, raw in enumerate(accepted):
        context = f"review.accepted_uncertainties[{index}]"
        item = as_object(raw, context)
        identifier = require_safe_id(
            item.get("uncertainty_id"), f"{context}.uncertainty_id"
        )
        if identifier in accepted_ids:
            raise ExtractorError(f"duplicate accepted uncertainty: {identifier}")
        accepted_ids.add(identifier)
        checked_accepted.append(
            {
                "uncertainty_id": identifier,
                "rationale": as_string(item.get("rationale"), f"{context}.rationale"),
                "source_pages": validate_pages(
                    item.get("source_pages"),
                    f"{context}.source_pages",
                    page_count=source["pdf_pages"],
                ),
            }
        )
    checked_composites = []
    composite_nodes: set[str] = set()
    for index, raw in enumerate(composites):
        context = f"review.topology_composites[{index}]"
        item = as_object(raw, context)
        topology_node = require_safe_id(
            item.get("topology_node"), f"{context}.topology_node"
        )
        if topology_node in composite_nodes:
            raise ExtractorError(
                f"review declares composite node {topology_node} more than once"
            )
        composite_nodes.add(topology_node)
        place_ids = as_array(item.get("place_ids"), f"{context}.place_ids")
        if (
            len(place_ids) < 2
            or any(not isinstance(place_id, str) for place_id in place_ids)
            or len(place_ids) != len(set(place_ids))
        ):
            raise ExtractorError(
                f"{context}.place_ids must contain at least two unique IDs"
            )
        for place_index, place_id in enumerate(place_ids):
            require_safe_id(place_id, f"{context}.place_ids[{place_index}]")
        checked_composites.append(
            {
                "topology_node": topology_node,
                "place_ids": sorted(place_ids),
                "source_pages": validate_pages(
                    item.get("source_pages"),
                    f"{context}.source_pages",
                    page_count=source["pdf_pages"],
                ),
                "rationale": as_string(
                    item.get("rationale"), f"{context}.rationale"
                ),
            }
        )
    return {
        "schema": REVIEW_SCHEMA,
        "source_sha256": source["sha256"],
        "canonical_ids": sorted(
            checked_canonical_ids, key=lambda item: item["extracted_id"]
        ),
        "aliases": sorted(
            checked_aliases, key=lambda item: (item["alias"], item["target_id"])
        ),
        "distinct": sorted(
            checked_distinct, key=lambda item: (item["left_id"], item["right_id"])
        ),
        "values": sorted(
            checked_values, key=lambda item: (item["object_id"], item["field"])
        ),
        "accepted_uncertainties": sorted(
            checked_accepted, key=lambda item: item["uncertainty_id"]
        ),
        "topology_composites": sorted(
            checked_composites, key=lambda item: item["topology_node"]
        ),
        "notes": as_string(review.get("notes", ""), "review.notes", nonempty=False),
    }
