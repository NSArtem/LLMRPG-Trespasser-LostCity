"""Response ingestion and evidence normalization."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contracts import (
    CONFIDENCES,
    CONTENT_SCHEMA,
    MAP_SCHEMA,
    validate_content_response,
    validate_content_task_coverage,
)
from .errors import ExtractorError, MapFacetError
from .util import load_json, require_safe_id, sha256_bytes, sha256_file, write_json


ELEVATIONS = {"level", "up", "down", "vertical", "variable"}
DIRECTIONS = {"both", "from_to", "to_from", "conditional"}


def _checked_string_set(value: Any) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        return []
    return sorted(set(value))


def _pages(
    value: Any,
    *,
    context: str,
    allowed: set[int],
    page_count: int,
) -> list[int]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(page, int) or isinstance(page, bool) for page in value)
    ):
        raise ExtractorError(f"{context} must be a non-empty page array")
    if len(value) != len(set(value)):
        raise ExtractorError(f"{context} contains duplicate pages")
    if any(page < 1 or page > page_count for page in value):
        raise ExtractorError(f"{context} is outside the PDF page range")
    if any(page not in allowed for page in value):
        raise ExtractorError(f"{context} cites a page outside its pack")
    return sorted(value)


def _content_observations(
    records: Sequence[Mapping[str, Any]], pack_id: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    observations: list[dict[str, Any]] = []
    uncertainties: list[dict[str, Any]] = []
    for record in records:
        observation_id = f"observation.{pack_id}.{record['id']}"
        observations.append(
            {
                "observation_id": observation_id,
                "concept_id": record["id"],
                "record_type": record["record_type"],
                "fields": record["fields"],
                "source_pages": record["source_pages"],
                "confidence": record["confidence"],
                "references": record["references"],
                "pack_id": pack_id,
            }
        )
        for index, uncertainty in enumerate(record["uncertainties"], 1):
            uncertainties.append(
                {
                    "id": f"uncertainty.{pack_id}.{record['id']}.{index:03d}",
                    "target_id": record["id"],
                    "target_observation_id": observation_id,
                    "description": uncertainty["description"],
                    "source_pages": uncertainty["source_pages"],
                    "pack_id": pack_id,
                }
            )
    return observations, uncertainties


def validate_v1_map(
    response: Mapping[str, Any], pack: Mapping[str, Any], source: Mapping[str, Any]
) -> dict[str, Any]:
    if response.get("schema") != MAP_SCHEMA:
        raise ExtractorError(f"{pack['pack_id']} map response has the wrong schema")
    if response.get("source_sha256") != source["sha256"]:
        raise ExtractorError(f"{pack['pack_id']} source hash does not match")
    if response.get("pack_id") != pack["pack_id"]:
        raise ExtractorError(f"{pack['pack_id']} response pack ID does not match")
    allowed = set(pack["physical_pages"])
    node_ids: set[str] = set()
    nodes = []
    for index, raw in enumerate(response.get("nodes", [])):
        context = f"{pack['pack_id']}.nodes[{index}]"
        if not isinstance(raw, dict):
            raise ExtractorError(f"{context} must be an object")
        identifier = require_safe_id(raw.get("id"), f"{context}.id")
        if identifier in node_ids:
            raise ExtractorError(f"duplicate map node {identifier}")
        node_ids.add(identifier)
        nodes.append(
            {
                "observation_id": f"observation.{pack['pack_id']}.node.{identifier}",
                "concept_id": identifier,
                "label": str(raw.get("label", "")),
                "title": raw.get("title"),
                "source_pages": _pages(
                    raw.get("source_pages"),
                    context=f"{context}.source_pages",
                    allowed=allowed,
                    page_count=source["pdf_pages"],
                ),
                "confidence": raw.get("confidence"),
                "pack_id": pack["pack_id"],
            }
        )
        if raw.get("confidence") not in CONFIDENCES:
            raise ExtractorError(f"{context}.confidence is invalid")
    passages = []
    passage_ids: set[str] = set()
    facet_errors: list[str] = []
    for index, raw in enumerate(response.get("passages", [])):
        context = f"{pack['pack_id']}.passages[{index}]"
        if not isinstance(raw, dict):
            raise ExtractorError(f"{context} must be an object")
        identifier = require_safe_id(raw.get("id"), f"{context}.id")
        if identifier in passage_ids or identifier in node_ids:
            raise ExtractorError(f"{context}.id is duplicated")
        passage_ids.add(identifier)
        start = require_safe_id(raw.get("from"), f"{context}.from")
        end = require_safe_id(raw.get("to"), f"{context}.to")
        if start not in node_ids or end not in node_ids:
            raise ExtractorError(f"{context} references an unknown node")
        facets = raw.get("facets")
        if not isinstance(facets, dict):
            raise ExtractorError(f"{context}.facets must be an object")
        allowed_facet_fields = {
            "kind",
            "medium",
            "elevation",
            "barriers",
            "features",
            "conditions",
            "traversal_direction",
        }
        unknown_fields = sorted(set(facets) - allowed_facet_fields)
        if unknown_fields:
            facet_errors.append(
                f"{context}.facets contains unsupported fields: "
                + ", ".join(unknown_fields)
            )
        for field in ("kind", "medium"):
            value = facets.get(field)
            if value is not None and (
                not isinstance(value, str) or not value.strip()
            ):
                facet_errors.append(
                    f"{context}.facets.{field} must be a non-empty string or null"
                )
        for field, allowed_values in (
            ("elevation", ELEVATIONS),
            ("traversal_direction", DIRECTIONS),
        ):
            value = facets.get(field)
            if value is not None and (
                not isinstance(value, str) or value not in allowed_values
            ):
                choices = ", ".join(sorted(allowed_values))
                facet_errors.append(
                    f"{context}.facets.{field} must be one of "
                    f"{choices}, or null; got {value!r}"
                )
        for field in ("barriers", "features", "conditions"):
            value = facets.get(field, [])
            if not isinstance(value, list) or any(
                not isinstance(item, str) or not item.strip() for item in value
            ):
                facet_errors.append(
                    f"{context}.facets.{field} must be an array of "
                    "non-empty strings"
                )
        passages.append(
            {
                "observation_id": (
                    f"observation.{pack['pack_id']}.passage.{identifier}"
                ),
                "source_id": identifier,
                "from": start,
                "to": end,
                "facets": {
                    "kind": facets.get("kind"),
                    "medium": facets.get("medium"),
                    "elevation": facets.get("elevation"),
                    "barriers": _checked_string_set(
                        facets.get("barriers", [])
                    ),
                    "features": _checked_string_set(
                        facets.get("features", [])
                    ),
                    "conditions": _checked_string_set(
                        facets.get("conditions", [])
                    ),
                    "traversal_direction": facets.get("traversal_direction"),
                },
                "source_pages": _pages(
                    raw.get("source_pages"),
                    context=f"{context}.source_pages",
                    allowed=allowed,
                    page_count=source["pdf_pages"],
                ),
                "confidence": raw.get("confidence"),
                "pack_id": pack["pack_id"],
            }
        )
        if raw.get("confidence") not in CONFIDENCES:
            raise ExtractorError(f"{context}.confidence is invalid")
    if facet_errors:
        raise MapFacetError(facet_errors)
    uncertainties = []
    passage_by_id = {
        passage["source_id"]: passage for passage in passages
    }
    valid_targets = node_ids | passage_ids
    for index, raw in enumerate(response.get("uncertainties", []), 1):
        context = f"{pack['pack_id']}.uncertainties[{index - 1}]"
        if not isinstance(raw, dict):
            raise ExtractorError(f"{context} must be an object")
        target = require_safe_id(raw.get("target_id"), f"{context}.target_id")
        if target not in valid_targets:
            raise ExtractorError(f"{context} references an unknown target")
        description = raw.get("description")
        if not isinstance(description, str) or not description:
            raise ExtractorError(f"{context}.description must be a string")
        if target in node_ids:
            canonical_target = target
            target_kind = "topology-node"
            target_observation_id = (
                f"observation.{pack['pack_id']}.node.{target}"
            )
        else:
            passage = passage_by_id[target]
            canonical_target = (
                f"edge-{'-'.join(sorted((passage['from'], passage['to'])))}"
            )
            target_kind = "topology-edge"
            target_observation_id = passage["observation_id"]
        uncertainties.append(
            {
                "id": f"uncertainty.{pack['pack_id']}.{index:03d}",
                "target_id": canonical_target,
                "target_kind": target_kind,
                "target_observation_id": target_observation_id,
                "description": description,
                "source_pages": _pages(
                    raw.get("source_pages"),
                    context=f"{context}.source_pages",
                    allowed=allowed,
                    page_count=source["pdf_pages"],
                ),
                "pack_id": pack["pack_id"],
            }
        )
    cited_pages = {
        page
        for observation in [*nodes, *passages]
        for page in observation["source_pages"]
    }
    missing_pages = sorted(allowed - cited_pages)
    if missing_pages:
        raise ExtractorError(
            f"{pack['pack_id']} has no topology evidence for pages: {missing_pages}"
        )
    return {
        "pack_id": pack["pack_id"],
        "nodes": nodes,
        "passages": passages,
        "uncertainties": uncertainties,
    }


def validate_pack_response(
    response: Any, pack: Mapping[str, Any], source: Mapping[str, Any]
) -> None:
    if not isinstance(response, dict):
        raise ExtractorError(f"response {pack['pack_id']} must be an object")
    if pack["task"] == "maps":
        validate_v1_map(response, pack, source)
    else:
        validate_content_response(response, pack, source)


def import_exchange_responses(
    exchange_dir: Path,
    run_dir: Path,
    packs: Sequence[Mapping[str, Any]],
    source: Mapping[str, Any],
) -> dict[str, list[str]]:
    """Validate all available exchange responses, then copy them atomically."""
    checked: list[tuple[dict[str, Any], Path, bytes, str]] = []
    missing: list[str] = []
    facet_errors: list[str] = []
    for raw_pack in sorted(packs, key=lambda item: item["pack_id"]):
        pack = dict(raw_pack)
        pack_id = pack["pack_id"]
        archive = exchange_dir / f"{pack_id}.zip"
        response_path = exchange_dir / f"{pack_id}.json"
        if not response_path.is_file():
            missing.append(pack_id)
            continue
        if not archive.is_file():
            raise ExtractorError(f"exchange pack is missing: {archive}")
        if sha256_file(archive) != pack["pack_sha256"]:
            raise ExtractorError(f"pack hash changed: {pack_id}")
        response = load_json(response_path)
        try:
            validate_pack_response(response, pack, source)
        except MapFacetError as exc:
            facet_errors.extend(exc.errors)
            continue
        payload = response_path.read_bytes()
        checked.append((pack, response_path, payload, sha256_bytes(payload)))

    if facet_errors:
        raise MapFacetError(facet_errors)

    responses_dir = run_dir / "responses"
    responses_dir.mkdir(parents=True, exist_ok=True)
    imported_hashes = {
        pack["pack_id"]: digest for pack, _, _, digest in checked
    }
    for pack, _, payload, _ in checked:
        destination = (run_dir / pack["response_path"]).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.tmp")
        temporary.write_bytes(payload)
        temporary.replace(destination)

    updated_packs = []
    for raw_pack in packs:
        pack = deepcopy(dict(raw_pack))
        digest = imported_hashes.get(pack["pack_id"])
        if digest is not None:
            pack["ingested_response_sha256"] = digest
        updated_packs.append(pack)
    write_json(
        run_dir / "packs.json",
        {
            "schema": "module-pack-manifest/v1",
            "source_sha256": source["sha256"],
            "packs": updated_packs,
        },
    )
    return {
        "imported": sorted(imported_hashes),
        "missing": missing,
    }


def ingest_responses(
    run_dir: Path,
    packs: Sequence[Mapping[str, Any]],
    source: Mapping[str, Any],
) -> dict[str, Any]:
    content: list[dict[str, Any]] = []
    map_results: list[dict[str, Any]] = []
    uncertainties: list[dict[str, Any]] = []
    response_info: list[dict[str, Any]] = []
    for pack in sorted(packs, key=lambda item: item["pack_id"]):
        pack_record_ids: list[str] = []
        archive = (run_dir / pack["archive_path"]).resolve()
        response_path = (run_dir / pack["response_path"]).resolve()
        if archive.is_file() and sha256_file(archive) != pack["pack_sha256"]:
            raise ExtractorError(f"pack hash changed: {pack['pack_id']}")
        if (
            not archive.is_file()
            and not pack.get("ingested_response_sha256")
        ):
            raise ExtractorError(f"pack archive is missing: {archive}")
        if not response_path.is_file():
            raise ExtractorError(f"response is missing: {pack['pack_id']}")
        response_digest = sha256_file(response_path)
        recorded_digest = pack.get("ingested_response_sha256")
        if recorded_digest is not None and response_digest != recorded_digest:
            raise ExtractorError(
                f"response changed after ingest: {pack['pack_id']}"
            )
        response = load_json(response_path)
        if not isinstance(response, dict):
            raise ExtractorError(f"response {pack['pack_id']} must be an object")
        task_coverage: list[dict[str, Any]]
        if pack["task"] == "maps":
            result = validate_v1_map(response, pack, source)
            map_results.append(result)
            uncertainties.extend(result["uncertainties"])
            pack_record_ids.extend(node["concept_id"] for node in result["nodes"])
            pack_record_ids.extend(
                f"edge-{'-'.join(sorted((passage['from'], passage['to'])))}"
                for passage in result["passages"]
            )
            task_coverage = []
            for page in pack["physical_pages"]:
                record_ids = [
                    node["concept_id"]
                    for node in result["nodes"]
                    if page in node["source_pages"]
                ]
                record_ids.extend(
                    f"edge-{'-'.join(sorted((passage['from'], passage['to'])))}"
                    for passage in result["passages"]
                    if page in passage["source_pages"]
                )
                task_coverage.append(
                    {
                        "pdf_page": page,
                        "task": "maps",
                        "status": "extracted",
                        "record_ids": sorted(set(record_ids)),
                        "notes": "",
                    }
                )
        else:
            records = validate_content_response(response, pack, source)
            task_coverage = validate_content_task_coverage(
                response, pack, records
            )
            observations, response_uncertainties = _content_observations(
                records, pack["pack_id"]
            )
            content.extend(observations)
            uncertainties.extend(response_uncertainties)
            pack_record_ids.extend(
                observation["concept_id"] for observation in observations
            )
        response_info.append(
            {
                "pack_id": pack["pack_id"],
                "response_path": pack["response_path"],
                "response_sha256": response_digest,
                "record_ids": sorted(set(pack_record_ids)),
                "task_coverage": task_coverage,
                "validation": "valid",
            }
        )
    return {
        "content_observations": sorted(
            content, key=lambda item: item["observation_id"]
        ),
        "map_results": sorted(map_results, key=lambda item: item["pack_id"]),
        "uncertainties": sorted(uncertainties, key=lambda item: item["id"]),
        "responses": response_info,
    }
