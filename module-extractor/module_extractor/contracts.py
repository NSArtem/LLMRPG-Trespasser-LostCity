"""Versioned v1 contracts and strict validators."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from .errors import ExtractorError
from .util import SAFE_SLUG, require_safe_id, require_sha256


ROUTING_SCHEMA = "module-routing/v1"
CONTENT_SCHEMA = "module-content-evidence/v1"
MAP_SCHEMA = "module-map-evidence/v1"
REVIEW_SCHEMA = "module-review-overlay/v1"
COVERAGE_SCHEMA = "module-coverage/v1"
CANONICAL_SCHEMA = "operational-module/v1"

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
    "location": ("title", "description"),
    "actor": ("title", "role"),
    "situation": ("title", "trigger"),
    "procedure": ("title", "trigger", "steps"),
    "knowledge": ("title", "text"),
    "rule": ("title", "text"),
    "table": ("title", "entries"),
    "item": ("title", "text"),
    "spell": ("title", "text"),
    "class": ("title", "text"),
    "effect": ("title", "text"),
}


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
        expected = list if field in {"steps", "entries"} else str
        if not isinstance(fields[field], expected):
            raise ExtractorError(
                f"{context}.fields.{field} must be {expected.__name__}"
            )
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
    aliases = as_array(review.get("aliases", []), "review.aliases")
    values = as_array(review.get("values", []), "review.values")
    accepted = as_array(
        review.get("accepted_uncertainties", []), "review.accepted_uncertainties"
    )
    alias_names: set[str] = set()
    checked_aliases = []
    for index, raw in enumerate(aliases):
        context = f"review.aliases[{index}]"
        item = as_object(raw, context)
        alias = require_safe_id(item.get("alias"), f"{context}.alias")
        canonical_id = require_safe_id(
            item.get("canonical_id"), f"{context}.canonical_id"
        )
        if alias in alias_names:
            raise ExtractorError(f"ambiguous duplicate alias: {alias}")
        alias_names.add(alias)
        pages = validate_pages(
            item.get("source_pages"),
            f"{context}.source_pages",
            page_count=source["pdf_pages"],
        )
        rationale = as_string(item.get("rationale"), f"{context}.rationale")
        checked_aliases.append(
            {
                "alias": alias,
                "canonical_id": canonical_id,
                "source_pages": pages,
                "rationale": rationale,
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
    return {
        "schema": REVIEW_SCHEMA,
        "source_sha256": source["sha256"],
        "aliases": sorted(checked_aliases, key=lambda item: item["alias"]),
        "values": sorted(
            checked_values, key=lambda item: (item["object_id"], item["field"])
        ),
        "accepted_uncertainties": sorted(
            checked_accepted, key=lambda item: item["uncertainty_id"]
        ),
        "notes": as_string(review.get("notes", ""), "review.notes", nonempty=False),
    }
