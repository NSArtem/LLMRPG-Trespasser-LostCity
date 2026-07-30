"""Read-only bounded scene context resolution."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .contracts import PLAY_CONTRACT
from .errors import ExtractorError
from .rendering import LOAD_WITH_GROUPS
from .util import load_json


SCENE_CONTEXT_SCHEMA = "operational-scene-context/v2"
PLACE_LOAD_GROUPS = LOAD_WITH_GROUPS["location"]
SITUATION_LOAD_GROUPS = LOAD_WITH_GROUPS["situation"]
POSSIBLE_EFFECT_NOTE = (
    "Possible effects describe source possibilities. They are not applied, "
    "not current facts, and never enter a checkpoint automatically."
)


def _safe_runtime_path(module_root: Path, relative: str) -> Path:
    if (
        not isinstance(relative, str)
        or relative.startswith("/")
        or ".." in Path(relative).parts
        or relative in {"index.json", "index.md", "topology.yaml"}
        or relative.startswith("audit/")
        or relative.lower().endswith(".pdf")
    ):
        raise ExtractorError(f"scene bundle contains forbidden path: {relative}")
    path = (module_root / relative).resolve()
    try:
        path.relative_to(module_root)
    except ValueError as exc:
        raise ExtractorError(f"scene bundle path escapes module: {relative}") from exc
    if not path.is_file() or path.is_symlink():
        raise ExtractorError(f"scene bundle path is not a runtime file: {relative}")
    return path


def _select(by_id: Mapping[str, Any], identifier: str) -> dict[str, Any] | None:
    """Select only a canonical runtime ID; aliases are not place bindings."""
    return by_id.get(identifier)


def _checked_load_with(
    record: Mapping[str, Any], groups: tuple[str, ...]
) -> dict[str, list[str]]:
    load_with = record.get("load_with")
    if not isinstance(load_with, dict) or set(load_with) != set(groups):
        raise ExtractorError(f"record has invalid load_with: {record['id']}")
    checked: dict[str, list[str]] = {}
    for group in groups:
        values = load_with[group]
        if (
            not isinstance(values, list)
            or any(not isinstance(value, str) for value in values)
            or values != sorted(set(values))
        ):
            raise ExtractorError(
                f"record has invalid load_with.{group}: {record['id']}"
            )
        checked[group] = values
    return checked


def resolve_scene(
    module_root: Path, place_id: str, situation_id: str | None = None
) -> dict[str, Any]:
    """Resolve one place, its available situations, and one optional active one.

    Selecting which available situation is active is an explicit runtime
    decision: without `situation_id` the bundle stays at the place level.
    """
    module_root = module_root.resolve()
    marker = load_json(module_root / "GENERATED_OUTPUT.json")
    if (
        not isinstance(marker, dict)
        or marker.get("play_contract") != PLAY_CONTRACT
        or marker.get("verification") != "verified"
        or not (module_root / "MODULE.md").is_file()
        or not (module_root / "index.json").is_file()
    ):
        raise ExtractorError(
            "module is not play-ready: expected play_contract "
            f"{PLAY_CONTRACT}, verification verified, MODULE.md, and index.json"
        )
    index = load_json(module_root / "index.json")
    if not isinstance(index, dict) or not isinstance(index.get("records"), list):
        raise ExtractorError("runtime index is invalid")
    by_id = {
        item["id"]: item
        for item in index["records"]
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    selected = _select(by_id, place_id)
    if selected is None:
        raise ExtractorError(f"unknown place ID: {place_id}")
    if selected.get("type") != "place":
        raise ExtractorError(f"scene ID is not a place: {place_id}")

    checked_load_with = _checked_load_with(selected, PLACE_LOAD_GROUPS)
    paths = [selected["path"], *(
        value for group in PLACE_LOAD_GROUPS for value in checked_load_with[group]
    )]

    by_path = {
        item["path"]: item
        for item in by_id.values()
        if isinstance(item.get("path"), str)
    }
    available = []
    for relative in checked_load_with["situations"]:
        record = by_path.get(relative)
        if record is None or record.get("type") != "situation":
            raise ExtractorError(
                f"place references a missing situation card: {relative}"
            )
        available.append(
            {
                "id": record["id"],
                "title": record.get("title", record["id"]),
                "path": relative,
                "activation": record.get("activation"),
                "repeat": record.get("repeat"),
            }
        )
    available.sort(key=lambda item: item["id"])

    active: dict[str, Any] | None = None
    if situation_id is not None:
        record = _select(by_id, situation_id)
        if record is None or record.get("type") != "situation":
            raise ExtractorError(f"unknown situation ID: {situation_id}")
        if record["id"] not in {item["id"] for item in available}:
            raise ExtractorError(
                f"situation is not available at {selected['id']}: {record['id']}"
            )
        situation_load_with = _checked_load_with(record, SITUATION_LOAD_GROUPS)
        for group in SITUATION_LOAD_GROUPS:
            paths.extend(situation_load_with[group])
        effects = record.get("possible_effects")
        active = {
            "id": record["id"],
            "title": record.get("title", record["id"]),
            "path": record["path"],
            "activation": record.get("activation"),
            "repeat": record.get("repeat"),
            "load_with": situation_load_with,
            "possible_effects": {
                "applied": False,
                "note": POSSIBLE_EFFECT_NOTE,
                "effects": effects if isinstance(effects, list) else [],
            },
        }

    files = []
    for relative in sorted(set(paths)):
        path = _safe_runtime_path(module_root, relative)
        files.append({"path": relative, "bytes": path.stat().st_size})

    topology = load_json(module_root / "topology.yaml")
    node_id = selected.get("topology_node")
    nodes = {
        node["id"]: node
        for node in topology.get("nodes", [])
        if isinstance(node, dict) and isinstance(node.get("id"), str)
    }
    if node_id is not None and node_id not in nodes:
        raise ExtractorError(
            f"place points to missing runtime topology node: {node_id}"
        )
    adjacent = sorted(
        [
            edge
            for edge in topology.get("passages", [])
            if node_id is not None and node_id in {edge.get("from"), edge.get("to")}
        ],
        key=lambda item: item["id"],
    )
    return {
        "schema": SCENE_CONTEXT_SCHEMA,
        "place_id": selected["id"],
        "place_path": selected["path"],
        "load_with": checked_load_with,
        "available_situations": available,
        "active_situation": active,
        "files": files,
        "total_bytes": sum(item["bytes"] for item in files),
        "topology": {
            "node": nodes.get(node_id),
            "adjacent_edges": adjacent,
        },
    }
