"""Human-facing command-line interface for one module per repository branch."""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Mapping, Sequence

from .assembly import assemble, canonical_module, evaluate, load_run
from .contracts import (
    GENERATED_OUTPUT_SCHEMA,
    REVIEW_SCHEMA,
    validate_pack_manifest,
    validate_review,
    validate_routing,
    validate_source,
)
from .errors import ExtractorError
from .evidence import import_exchange_responses, validate_pack_response
from .packs import create_focused_packs
from .preparation import inferred_slug, prepare
from .scene import resolve_scene
from .util import load_json, sha256_file, write_json


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACKAGE_ROOT.parent


@dataclass(frozen=True)
class Workspace:
    root: Path
    input: Path
    exchange: Path
    cache: Path
    module: Path


def _workspace(args: argparse.Namespace) -> Workspace:
    root = Path(args.workspace_root).resolve()
    return Workspace(
        root=root,
        input=root / "module-input",
        exchange=root / "_exchange",
        cache=root / ".module-extractor-cache",
        module=root / "module",
    )


def command_prepare(args: argparse.Namespace) -> None:
    workspace = _workspace(args)
    exchange = prepare(
        Path(args.pdf),
        slug=args.slug,
        title=args.title,
        input_dir=workspace.input,
        exchange_dir=workspace.exchange,
        cache_dir=workspace.cache,
    )
    print(exchange)
    print(
        "Upload routing.zip to ChatGPT and save its result beside it as "
        "routing.json.",
        file=sys.stderr,
    )
    print(
        "Then run: python3 module-extractor/cli.py run",
        file=sys.stderr,
    )


def _silently(function: Any, args: argparse.Namespace) -> None:
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        function(args)


def _response_filenames(
    workspace: Workspace, packs: Sequence[Mapping[str, Any]]
) -> tuple[list[str], list[str]]:
    missing = []
    exchange_available = []
    for pack in packs:
        filename = f"{pack['pack_id']}.json"
        if not (workspace.input / pack["response_path"]).is_file():
            missing.append(filename)
        if (workspace.exchange / filename).is_file():
            exchange_available.append(filename)
    return sorted(missing), sorted(exchange_available)


def _released_module_matches(
    workspace: Workspace, evaluated: Mapping[str, Any]
) -> bool:
    marker = workspace.module / "GENERATED_OUTPUT.json"
    module_path = workspace.module / "audit" / "module.json"
    if not marker.is_file() or not module_path.is_file():
        return False
    try:
        marker_value = load_json(marker)
        module_value = load_json(module_path)
    except ExtractorError:
        return False
    if (
        not isinstance(marker_value, dict)
        or marker_value.get("schema") != GENERATED_OUTPUT_SCHEMA
    ):
        return False
    expected = canonical_module(evaluated, profile="release")
    return (
        isinstance(module_value, dict)
        and module_value.get("module_sha256") == expected["module_sha256"]
    )


def inspect_workspace(workspace: Workspace) -> dict[str, Any]:
    """Return the user-facing state without changing the workspace."""
    source_path = workspace.input / "source.json"
    if not source_path.is_file():
        return {
            "stage": "not-started",
            "completed": [],
            "missing_responses": [],
            "next_action": (
                "Run `python3 module-extractor/cli.py run adventure.pdf`."
            ),
        }
    source = validate_source(load_json(source_path))
    completed = ["PDF prepared", "routing.zip created"]
    packs_path = workspace.input / "packs.json"
    routing_response = workspace.exchange / "routing.json"
    if not packs_path.is_file():
        if routing_response.is_file():
            return {
                "stage": "routing-response-ready",
                "source": source,
                "completed": completed + ["routing.json saved"],
                "missing_responses": [],
                "next_action": "Run `python3 module-extractor/cli.py run`.",
            }
        return {
            "stage": "waiting-for-routing",
            "source": source,
            "completed": completed,
            "missing_responses": ["routing.json"],
            "next_action": (
                "Upload `_exchange/routing.zip` to ChatGPT, save the result "
                "as `_exchange/routing.json`, then run "
                "`python3 module-extractor/cli.py run`."
            ),
        }
    packs = validate_pack_manifest(load_json(packs_path), source)
    missing, available = _response_filenames(workspace, packs)
    completed.extend(
        [
            "routing.json accepted",
            f"{len(packs)} focused pack(s) created",
            f"{len(packs) - len(missing)} focused response(s) ingested",
        ]
    )
    if missing:
        return {
            "stage": "waiting-for-focused-responses",
            "source": source,
            "packs": packs,
            "completed": completed,
            "missing_responses": missing,
            "waiting_to_ingest": sorted(set(missing) & set(available)),
            "next_action": (
                "Upload each missing focused ZIP to ChatGPT, save each JSON "
                "beside it with the same basename, then run "
                "`python3 module-extractor/cli.py run`."
            ),
        }
    evaluated = evaluate(workspace.input)
    completed.append("all focused responses validated")
    if evaluated["gate_errors"]:
        task_exists = (workspace.exchange / "codex-task.md").is_file()
        return {
            "stage": "codex-review-required",
            "source": source,
            "packs": packs,
            "evaluated": evaluated,
            "completed": completed
            + (["Codex task generated"] if task_exists else []),
            "missing_responses": [],
            "next_action": (
                "Tell Codex: `Finish the module extraction by following "
                "module-extractor/CODEX_WORKFLOW.md.`"
                if task_exists
                else "Run `python3 module-extractor/cli.py run` to generate "
                "the Codex task."
            ),
        }
    released = _released_module_matches(workspace, evaluated)
    return {
        "stage": "already-released" if released else "release-ready",
        "source": source,
        "packs": packs,
        "evaluated": evaluated,
        "completed": completed + ["release gate passed"]
        + (["module assembled"] if released else []),
        "missing_responses": [],
        "next_action": (
            "Review the uncommitted `module/` and durable `module-input/`."
            if released
            else "Run `python3 module-extractor/cli.py run` to assemble the release."
        ),
    }


def _rejected_response(
    filename: str, pack_id: str, reason: ExtractorError
) -> ExtractorError:
    return ExtractorError(
        f"Rejected _exchange/{filename}: {reason}. Ask ChatGPT to retry "
        f"_exchange/{pack_id}.zip, replace _exchange/{filename}, then run "
        "`python3 module-extractor/cli.py run` again."
    )


def _validate_available_responses(
    workspace: Workspace,
    source: Mapping[str, Any],
    packs: Sequence[Mapping[str, Any]],
) -> None:
    for pack in packs:
        pack_id = pack["pack_id"]
        filename = f"{pack_id}.json"
        response_path = workspace.exchange / filename
        if not response_path.is_file():
            continue
        try:
            archive = workspace.exchange / f"{pack_id}.zip"
            if not archive.is_file():
                raise ExtractorError(f"expected pack is missing: {archive}")
            if sha256_file(archive) != pack["pack_sha256"]:
                raise ExtractorError("the focused ZIP no longer has its expected hash")
            response = load_json(response_path)
            if not isinstance(response, dict):
                raise ExtractorError("the response must be a JSON object")
            validate_pack_response(response, pack, source)
        except ExtractorError as exc:
            raise _rejected_response(filename, pack_id, exc) from exc


def command_run(args: argparse.Namespace) -> None:
    workspace = _workspace(args)
    if args.pdf:
        pdf = Path(args.pdf)
        slug = args.slug if args.slug is not None else inferred_slug(pdf)
        if not slug:
            raise ExtractorError(
                "could not derive a slug from the PDF filename; provide --slug"
            )
        command_prepare(
            argparse.Namespace(
                pdf=str(pdf),
                slug=slug,
                title=args.title,
                workspace_root=args.workspace_root,
            )
        )
        return
    if args.slug is not None or args.title is not None:
        raise ExtractorError("--slug and --title require a PDF")

    state = inspect_workspace(workspace)
    if state["stage"] == "not-started":
        raise ExtractorError(state["next_action"].strip("`"))
    if state["stage"] == "waiting-for-routing":
        print("Waiting for `_exchange/routing.json`.")
        print(state["next_action"])
        return
    if state["stage"] == "routing-response-ready":
        try:
            _silently(
                command_focus,
                argparse.Namespace(
                    workspace_root=args.workspace_root, routing=None
                ),
            )
        except ExtractorError as exc:
            raise ExtractorError(
                f"Rejected _exchange/routing.json: {exc}. Ask ChatGPT to "
                "retry _exchange/routing.zip, replace _exchange/routing.json, "
                "then run `python3 module-extractor/cli.py run` again."
            ) from exc

    source = validate_source(load_json(workspace.input / "source.json"))
    packs = validate_pack_manifest(
        load_json(workspace.input / "packs.json"), source
    )
    if workspace.exchange.is_dir():
        _validate_available_responses(workspace, source, packs)
        _silently(
            command_ingest,
            argparse.Namespace(workspace_root=args.workspace_root),
        )
    missing, _ = _response_filenames(workspace, packs)
    if missing:
        print("Waiting for focused ChatGPT responses.")
        print("Missing: " + ", ".join(missing))
        print(
            "Save each JSON in `_exchange/` beside the ZIP with the same "
            "basename, then run `python3 module-extractor/cli.py run` again."
        )
        return

    review_path = workspace.input / "review.json"
    if not review_path.is_file():
        write_json(review_path, _empty_review(source["sha256"]))
    evaluated = evaluate(workspace.input)
    task_path = workspace.exchange / "codex-task.md"
    workspace.exchange.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        render_codex_task(evaluated, Path("module-input/review.json")),
        encoding="utf-8",
        newline="\n",
    )
    if evaluated["gate_errors"]:
        print(f"Codex review required. Task: {task_path}")
        print(
            "Tell Codex: `Finish the module extraction by following "
            "module-extractor/CODEX_WORKFLOW.md.`"
        )
        return
    if _released_module_matches(workspace, evaluated):
        print("Release is already assembled and up to date.")
        print(workspace.module)
        return
    module = assemble(
        workspace.input,
        workspace.module,
        profile="release",
        replace_generated_output=True,
    )
    print(f"Release assembled: {workspace.module}")
    print(module["module_sha256"])


def _existing_packs(
    workspace: Workspace, source: Mapping[str, Any]
) -> list[dict[str, Any]]:
    manifest = workspace.input / "packs.json"
    if not manifest.is_file():
        return []
    return validate_pack_manifest(load_json(manifest), source)


def _copy_if_present(source: Path, destination: Path) -> None:
    if source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def _pack_identity(packs: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    return {pack["pack_id"]: pack["pack_sha256"] for pack in packs}


def _preserve_responses(
    workspace: Workspace,
    staged_exchange: Path,
    staged_input: Path,
    old_packs: Sequence[Mapping[str, Any]],
    new_packs: Sequence[Mapping[str, Any]],
    source: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    old_by_id = {pack["pack_id"]: pack for pack in old_packs}
    preserved: list[str] = []
    invalidated: list[str] = []
    updated_packs: list[dict[str, Any]] = []
    for raw_new in new_packs:
        new_pack = dict(raw_new)
        old_pack = old_by_id.get(new_pack["pack_id"])
        old_response_exists = bool(
            old_pack is not None
            and (
                (workspace.exchange / f"{new_pack['pack_id']}.json").is_file()
                or (workspace.input / old_pack["response_path"]).is_file()
            )
        )
        unchanged = (
            old_pack is not None
            and old_pack["pack_sha256"] == new_pack["pack_sha256"]
        )
        response_preserved = False
        if unchanged:
            exchange_response = workspace.exchange / f"{new_pack['pack_id']}.json"
            if exchange_response.is_file():
                try:
                    validate_pack_response(
                        load_json(exchange_response), new_pack, source
                    )
                except ExtractorError:
                    pass
                else:
                    shutil.copyfile(
                        exchange_response,
                        staged_exchange / exchange_response.name,
                    )
                    response_preserved = True

            ingested_response = workspace.input / old_pack["response_path"]
            recorded_hash = old_pack.get("ingested_response_sha256")
            if (
                ingested_response.is_file()
                and recorded_hash is not None
                and sha256_file(ingested_response) == recorded_hash
            ):
                try:
                    validate_pack_response(
                        load_json(ingested_response), new_pack, source
                    )
                except ExtractorError:
                    pass
                else:
                    destination = staged_input / new_pack["response_path"]
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ingested_response, destination)
                    new_pack["ingested_response_sha256"] = recorded_hash
                    response_preserved = True
        if response_preserved:
            preserved.append(new_pack["pack_id"])
        elif old_response_exists:
            invalidated.append(new_pack["pack_id"])
        updated_packs.append(new_pack)
    removed_ids = sorted(
        set(old_by_id) - {pack["pack_id"] for pack in new_packs}
    )
    for pack_id in removed_ids:
        old_pack = old_by_id[pack_id]
        if (
            (workspace.exchange / f"{pack_id}.json").is_file()
            or (workspace.input / old_pack["response_path"]).is_file()
        ):
            invalidated.append(pack_id)
    return updated_packs, sorted(preserved), sorted(set(invalidated))


def _publish_workspace_directories(
    staged: Sequence[tuple[Path, Path]], root: Path
) -> None:
    backups: list[tuple[Path, Path | None]] = []
    published: list[Path] = []
    try:
        for _, destination in staged:
            backup: Path | None = None
            if destination.exists():
                backup = Path(
                    tempfile.mkdtemp(
                        prefix=f".{destination.name}-focus-backup-",
                        dir=root,
                    )
                )
                backup.rmdir()
                os.replace(destination, backup)
            backups.append((destination, backup))
        for stage, destination in staged:
            os.replace(stage, destination)
            published.append(destination)
    except BaseException:
        for destination in reversed(published):
            if destination.is_dir():
                shutil.rmtree(destination)
            elif destination.exists():
                destination.unlink()
        for destination, backup in reversed(backups):
            if backup is not None and backup.exists():
                os.replace(backup, destination)
        raise
    for _, backup in backups:
        if backup is not None:
            if backup.is_dir():
                shutil.rmtree(backup)
            elif backup.exists():
                backup.unlink()


def command_focus(args: argparse.Namespace) -> None:
    workspace = _workspace(args)
    source = validate_source(load_json(workspace.input / "source.json"))
    prepared = load_json(workspace.cache / "prepared.json")
    routing_path = (
        Path(args.routing).resolve()
        if args.routing
        else workspace.exchange / "routing.json"
    )
    routing_value = load_json(routing_path)
    routing = validate_routing(routing_value, source)
    old_packs = _existing_packs(workspace, source)
    if not workspace.exchange.is_dir():
        raise ExtractorError(
            f"exchange directory does not exist: {workspace.exchange}"
        )
    workspace.root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".module-extractor-focus-", dir=workspace.root
    ) as temporary:
        stage = Path(temporary)
        staged_exchange = stage / "_exchange"
        staged_input = stage / "module-input"
        staged_cache = stage / ".module-extractor-cache"
        staged_exchange.mkdir()
        staged_input.mkdir()
        shutil.copytree(workspace.cache, staged_cache)
        staged_renders = staged_cache / "map-renders"
        if staged_renders.is_dir():
            shutil.rmtree(staged_renders)

        for name in ("routing.zip", ".module-extractor.json"):
            _copy_if_present(
                workspace.exchange / name, staged_exchange / name
            )
        write_json(staged_exchange / "routing.json", routing_value)
        write_json(staged_input / "source.json", source)
        write_json(staged_input / "routing.json", routing_value)

        packs = create_focused_packs(
            staged_input,
            source,
            prepared,
            routing,
            asset_base_dir=staged_cache,
            archive_dir=staged_exchange,
            render_dir=staged_renders,
        )
        packs, preserved, invalidated = _preserve_responses(
            workspace,
            staged_exchange,
            staged_input,
            old_packs,
            packs,
            source,
        )
        write_json(
            staged_input / "packs.json",
            {
                "schema": "module-pack-manifest/v1",
                "source_sha256": source["sha256"],
                "packs": packs,
            },
        )
        same_pack_set = _pack_identity(old_packs) == _pack_identity(packs)
        review_path = workspace.input / "review.json"
        review_preserved = False
        if same_pack_set and review_path.is_file():
            try:
                validate_review(load_json(review_path), source)
            except ExtractorError:
                pass
            else:
                shutil.copyfile(review_path, staged_input / "review.json")
                review_preserved = True
        review_reset = review_path.is_file() and not review_preserved

        _publish_workspace_directories(
            (
                (staged_exchange, workspace.exchange),
                (staged_input, workspace.input),
                (staged_cache, workspace.cache),
            ),
            workspace.root,
        )
    content_count = sum(pack["task"] == "content" for pack in packs)
    map_count = sum(pack["task"] == "maps" for pack in packs)
    content_label = "pack" if content_count == 1 else "packs"
    map_label = "pack" if map_count == 1 else "packs"
    print(workspace.exchange)
    print(
        f"Created {content_count} content {content_label} and "
        f"{map_count} map {map_label}. "
        "For every <pack-id>.zip, save ChatGPT's result beside it as "
        "<pack-id>.json.",
        file=sys.stderr,
    )
    if preserved:
        print(
            "Preserved unchanged responses: " + ", ".join(preserved),
            file=sys.stderr,
        )
    if invalidated:
        print(
            "Invalidated changed responses: " + ", ".join(invalidated),
            file=sys.stderr,
        )
    if review_reset:
        print(
            "The review overlay was reset because it no longer safely matches "
            "the focused packs.",
            file=sys.stderr,
        )
    print(
        "Then run: python3 module-extractor/cli.py run",
        file=sys.stderr,
    )


def command_ingest(args: argparse.Namespace) -> None:
    workspace = _workspace(args)
    source = validate_source(load_json(workspace.input / "source.json"))
    packs = validate_pack_manifest(
        load_json(workspace.input / "packs.json"), source
    )
    result = import_exchange_responses(
        workspace.exchange, workspace.input, packs, source
    )
    print(
        json.dumps(
            {
                "imported": result["imported"],
                "missing": result["missing"],
                "complete": not result["missing"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if result["missing"]:
        print(
            "Add the missing JSON files to _exchange and run "
            "python3 module-extractor/cli.py run again.",
            file=sys.stderr,
        )
    else:
        print(
            "All responses are valid. Run python3 module-extractor/cli.py run.",
            file=sys.stderr,
        )


def _status(evaluated: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "slug": evaluated["source"].get("slug"),
        "source_sha256": evaluated["source"]["sha256"],
        "physical_pages": evaluated["source"]["pdf_pages"],
        "packs": len(evaluated["packs"]),
        "valid_responses": len(evaluated["evidence"]["responses"]),
        "records": len(evaluated["reviewed"]["records"]),
        "topology_nodes": len(evaluated["reviewed"]["topology"]["nodes"]),
        "topology_passages": len(evaluated["reviewed"]["topology"]["passages"]),
        "mapped_places": sum(
            link["topology_node"] is not None
            for link in evaluated["reviewed"].get("topology_links", [])
        ),
        "topology_errors": len(
            evaluated["reviewed"].get("topology_errors", [])
        ),
        "record_errors": len(evaluated["reviewed"].get("record_errors", [])),
        "coverage_complete": evaluated["coverage"]["complete"],
        "blocking_conflicts": len(evaluated["reviewed"]["unresolved_conflicts"]),
        "pending_uncertainties": len(
            evaluated["reviewed"]["pending_uncertainties"]
        ),
        "release_ready": not evaluated["gate_errors"],
        "release_gate_errors": evaluated["gate_errors"],
    }


def command_status(args: argparse.Namespace) -> None:
    workspace = _workspace(args)
    situation = getattr(args, "situation", None)
    if getattr(args, "scene", None):
        resolved = resolve_scene(workspace.module, args.scene, situation)
        print(json.dumps(resolved, indent=2, sort_keys=True))
        return
    if situation:
        raise ExtractorError("--situation requires --scene PLACE_ID")
    try:
        state = inspect_workspace(workspace)
    except ExtractorError as exc:
        state = {
            "stage": "invalid-workspace",
            "completed": [],
            "missing_responses": [],
            "next_action": "Correct the reported file, then run `status` again.",
            "validation_error": str(exc),
        }
    evaluated = state.get("evaluated")
    structured = {
        "stage": state["stage"],
        "slug": state.get("source", {}).get("slug"),
        "completed": state["completed"],
        "missing_responses": state["missing_responses"],
        "waiting_to_ingest": state.get("waiting_to_ingest", []),
        "next_action": state["next_action"],
        "release_ready": bool(
            evaluated is not None and not evaluated["gate_errors"]
        ),
        **(
            {"release_gate_errors": evaluated["gate_errors"]}
            if evaluated is not None
            else {}
        ),
        **(
            {"validation_error": state["validation_error"]}
            if "validation_error" in state
            else {}
        ),
    }
    if args.json:
        print(json.dumps(structured, indent=2, sort_keys=True))
        return
    print(f"Stage: {state['stage']}")
    if state.get("source"):
        print(
            f"Source: {state['source']['title']} "
            f"({state['source'].get('slug') or 'legacy workspace'})"
        )
    print("Completed:")
    for item in state["completed"]:
        print(f"  - {item}")
    if state["missing_responses"]:
        print("Missing responses:")
        for filename in state["missing_responses"]:
            print(f"  - {filename}")
    if evaluated is not None and evaluated["gate_errors"]:
        print("Release gate:")
        for error in evaluated["gate_errors"]:
            print(f"  - {error}")
    if "validation_error" in state:
        print(f"Problem: {state['validation_error']}")
    print(f"Next: {state['next_action']}")


def command_validate(args: argparse.Namespace) -> None:
    evaluated = evaluate(_workspace(args).input)
    status = _status(evaluated)
    if args.profile == "release" and evaluated["gate_errors"]:
        raise ExtractorError(
            "release validation failed: " + "; ".join(evaluated["gate_errors"])
        )
    print(json.dumps(status, indent=2, sort_keys=True))


def _source_pages_for_conflict(
    evaluated: Mapping[str, Any], conflict: Mapping[str, Any]
) -> list[int]:
    object_id = conflict["object_id"]
    field = conflict["field"]
    for record in evaluated["raw_records"]:
        if record["id"] == object_id:
            return sorted(
                {
                    page
                    for observation in record["field_observations"].get(field, [])
                    for page in observation["source_pages"]
                }
            )
    for edge in evaluated["raw_topology"]["passages"]:
        if edge["id"] == object_id:
            return sorted(
                {
                    page
                    for observation in edge["facet_observations"].get(field, [])
                    for page in observation["source_pages"]
                }
            )
    return []


def _observations_for_conflict(
    evaluated: Mapping[str, Any], conflict: Mapping[str, Any]
) -> list[dict[str, Any]]:
    object_id = conflict["object_id"]
    field = conflict["field"]
    for record in evaluated["raw_records"]:
        if record["id"] == object_id:
            if field == "record_type":
                return [
                    {
                        "value": observation["record_type"],
                        "source_pages": observation["source_pages"],
                        "confidence": observation["confidence"],
                        "pack_id": observation["pack_id"],
                        "observation_id": observation["observation_id"],
                    }
                    for observation in evaluated["evidence"][
                        "content_observations"
                    ]
                    if observation["concept_id"] == object_id
                ]
            return list(record["field_observations"].get(field, []))
    for edge in evaluated["raw_topology"]["passages"]:
        if edge["id"] == object_id:
            return list(edge["facet_observations"].get(field, []))
    return []


def _topology_context(
    evaluated: Mapping[str, Any], object_id: str
) -> dict[str, Any] | None:
    topology = evaluated["raw_topology"]
    nodes = topology.get("nodes", [])
    passages = topology.get("passages", [])
    node_by_id = {node["id"]: node for node in nodes}
    for edge in passages:
        if edge["id"] != object_id:
            continue
        return {
            "passage": {
                "id": edge["id"],
                "from": edge["from"],
                "to": edge["to"],
            },
            "nodes": [
                {
                    "id": identifier,
                    "labels": node_by_id[identifier]["labels"],
                    "titles": node_by_id[identifier]["titles"],
                    "source_pages": node_by_id[identifier]["source_pages"],
                }
                for identifier in (edge["from"], edge["to"])
                if identifier in node_by_id
            ],
        }
    if object_id in node_by_id:
        adjacent = [
            {
                "id": edge["id"],
                "from": edge["from"],
                "to": edge["to"],
            }
            for edge in passages
            if object_id in {edge["from"], edge["to"]}
        ]
        return {
            "node": {
                "id": object_id,
                "labels": node_by_id[object_id]["labels"],
                "titles": node_by_id[object_id]["titles"],
                "source_pages": node_by_id[object_id]["source_pages"],
            },
            "adjacent_passages": adjacent,
        }
    return None


def _review_paths(
    *,
    pack_ids: Sequence[str],
    pages: Sequence[int],
    include_map_renders: bool,
) -> list[str]:
    paths = {
        f"module-input/responses/{pack_id}.json" for pack_id in pack_ids
    }
    paths.update(f"_exchange/{pack_id}.json" for pack_id in pack_ids)
    paths.update(
        f".module-extractor-cache/text/pages/page-{page:04d}.txt"
        for page in pages
    )
    if include_map_renders:
        paths.update(
            f".module-extractor-cache/map-renders/page-{page:04d}.png"
            for page in pages
        )
    return sorted(paths)


def _empty_review(source_sha256: str) -> dict[str, Any]:
    return {
        "schema": REVIEW_SCHEMA,
        "source_sha256": source_sha256,
        "canonical_ids": [],
        "aliases": [],
        "distinct": [],
        "values": [],
        "accepted_uncertainties": [],
        "topology_composites": [],
        "notes": "",
    }


def _json_block(value: Any) -> list[str]:
    return ["```json", json.dumps(value, indent=2, sort_keys=True), "```"]


def render_codex_task(
    evaluated: Mapping[str, Any], overlay_path: Path
) -> str:
    conflicts = evaluated["reviewed"]["unresolved_conflicts"]
    uncertainties = evaluated["reviewed"]["pending_uncertainties"]
    coverage = evaluated.get("coverage", {"gaps": []})
    gaps = coverage["gaps"]
    candidates = [
        candidate
        for candidate in evaluated.get("identity", {}).get("candidate_groups", [])
        if candidate["status"] == "unresolved"
    ]
    topology_errors = evaluated["reviewed"].get("topology_errors", [])
    topology_links = evaluated["reviewed"].get("topology_links", [])
    lines = [
        "# Codex extraction task",
        "",
        "This is a generated, inert work queue for final source-based review.",
        f"Record canonical decisions only in `{overlay_path}`.",
        "",
        "Correct extraction mistakes only in `_exchange/<pack-id>.json`. "
        "Never edit ingested responses, coverage, or generated module files.",
        "",
        "After every correction or decision, run "
        "`python3 module-extractor/cli.py run`. Do not accept an uncertainty "
        "merely to make the release gate pass. Never commit or clean the workspace.",
        "",
        "## Release gate",
        "",
        *(
            [f"- {error}" for error in evaluated.get("gate_errors", [])]
            or ["The release gate currently passes."]
        ),
        "",
        "## Coverage gaps",
        "",
    ]
    if not gaps:
        lines.extend(["No coverage gaps.", ""])
    for gap in gaps:
        page = gap["pdf_page"]
        candidate_packs = sorted(
            pack["pack_id"]
            for pack in evaluated["packs"]
            if page in pack["physical_pages"]
            and (
                gap["task"] == "maps"
                or gap["task"] is None
                or gap["task"] in pack.get("tasks", [])
            )
        )
        paths = _review_paths(
            pack_ids=candidate_packs,
            pages=[page],
            include_map_renders=gap["task"] == "maps",
        )
        lines.extend(
            [
                f"### Physical page {page}: {gap['task'] or 'unassigned'}",
                "",
                f"- Reason: `{gap['reason']}`",
                f"- Candidate packs: {', '.join(f'`{value}`' for value in candidate_packs) or 'none'}",
                "- Source and evidence paths:",
                *[f"  - `{path}`" for path in paths],
                "",
            ]
        )
    lines.extend(
        [
        "## Duplicate candidates",
        "",
        f"- Unresolved candidates: {len(candidates)}",
        f"- High-confidence unresolved candidates: "
        f"{sum(item['confidence'] == 'high' for item in candidates)}",
        "",
        ]
    )
    if not candidates:
        lines.extend(["No unresolved duplicate candidates.", ""])
    for candidate in candidates:
        left_id, right_id = candidate["extracted_ids"]
        pages = candidate["source_pages"]
        observations = [
            observation
            for observation in evaluated["evidence"]["content_observations"]
            if observation["concept_id"] in candidate["extracted_ids"]
        ]
        topology_observations = [
            node
            for result in evaluated["evidence"]["map_results"]
            for node in result["nodes"]
            if node["concept_id"] in candidate["extracted_ids"]
        ]
        all_observations = sorted(
            observations + topology_observations,
            key=lambda item: item["observation_id"],
        )
        pack_ids = sorted(
            {
                observation["pack_id"]
                for observation in all_observations
                if observation.get("pack_id")
            }
        )
        paths = _review_paths(
            pack_ids=pack_ids,
            pages=pages,
            include_map_renders=bool(topology_observations),
        )
        lines.extend(
            [
                f"### `{candidate['id']}`",
                "",
                f"- Confidence: `{candidate['confidence']}`",
                f"- Extracted IDs: `{left_id}`, `{right_id}`",
                f"- Signals: {', '.join(candidate['signals'])}",
                f"- Source pages: {', '.join(map(str, pages))}",
                f"- Decision needed: {candidate['evidence_needed']}",
                "- Relevant paths:",
                *[f"  - `{path}`" for path in paths],
                "- Observations:",
                "",
                *_json_block(all_observations),
                "",
                "If these are one concept, declare the canonical ID and alias "
                "one extracted ID to the other:",
                "",
                *_json_block(
                    {
                        "canonical_ids": [
                            {
                                "extracted_id": left_id,
                                "canonical_id": (
                                    "replace.with.policy-compliant-canonical-id"
                                ),
                                "source_pages": pages,
                                "rationale": "Replace with source-based rationale.",
                            }
                        ],
                        "aliases": [
                            {
                                "alias": right_id,
                                "target_id": left_id,
                                "source_pages": pages,
                                "rationale": "Replace with source-based rationale.",
                            }
                        ],
                    }
                ),
                "",
                "If they are different concepts, add this decision to `distinct`:",
                "",
                *_json_block(
                    {
                        "left_id": left_id,
                        "right_id": right_id,
                        "source_pages": pages,
                        "rationale": "Replace with evidence proving distinction.",
                    }
                ),
                "",
            ]
        )
    lines.extend(
        [
            "## Place and topology decisions",
            "",
            f"- Unresolved topology decisions: {len(topology_errors)}",
            f"- Resolved place links: {len(topology_links)}",
            "",
        ]
    )
    if not topology_errors:
        lines.extend(["No unresolved place-to-topology decisions.", ""])
    else:
        lines.extend(f"- {error}" for error in topology_errors)
        lines.extend(
            [
                "",
                "Inspect the cited content response, map response, page text, and "
                "map render. Correct extraction errors in the exchange response. "
                "For an evidence-backed canonical decision, select "
                "`topology_node` on the place or `classification` on the map node "
                "through `values`. Use null only for a source-supported unmapped "
                "place.",
                "",
                "If multiple place cards intentionally compose one map node, add "
                "a source-cited `topology_composites` operation naming that node "
                "and every place ID.",
                "",
            ]
        )
    if topology_links:
        lines.extend(["Current resolved links:", ""])
        lines.extend(_json_block(topology_links))
        lines.append("")
    record_errors = evaluated["reviewed"].get("record_errors", [])
    lines.extend(
        [
            "## Actor and situation decisions",
            "",
            f"- Unresolved actor and situation errors: {len(record_errors)}",
            "",
        ]
    )
    if not record_errors:
        lines.extend(["No unresolved actor or situation decisions.", ""])
    else:
        lines.extend(f"- {error}" for error in record_errors)
        lines.extend(
            [
                "",
                "Read the cited source pages before deciding. Correct a wrong "
                "observation in `_exchange/<pack-id>.json`; record a canonical "
                "decision through `values` on the named record. Keep observable "
                "material and GM-only material separate: `hidden` is GM-only. "
                "Do not place mutable health, position, attitude, or inventory "
                "in a card; use `starting_state` only for a source-stated "
                "starting state. Possible effects stay hypothetical and are "
                "never applied here.",
                "",
            ]
        )
    lines.extend(
        [
        f"- Unresolved conflicts: {len(conflicts)}",
        f"- Pending uncertainties: {len(uncertainties)}",
        "",
        "## Conflicts",
        "",
        ]
    )
    if not conflicts:
        lines.extend(["No unresolved conflicts.", ""])
    for conflict in conflicts:
        observations = _observations_for_conflict(evaluated, conflict)
        pages = sorted(
            {
                page
                for observation in observations
                for page in observation["source_pages"]
            }
        ) or _source_pages_for_conflict(evaluated, conflict)
        pack_ids = sorted(
            {
                observation["pack_id"]
                for observation in observations
                if observation.get("pack_id")
            }
        )
        topology_context = _topology_context(
            evaluated, conflict["object_id"]
        )
        relevant_paths = _review_paths(
            pack_ids=pack_ids,
            pages=pages,
            include_map_renders=topology_context is not None,
        )
        lines.extend(
            [
                f"### `{conflict['id']}`",
                "",
                f"- Target: `{conflict['object_id']}.{conflict['field']}`",
                f"- Source pages: {', '.join(map(str, pages)) or 'not reported'}",
                f"- Packs: {', '.join(f'`{value}`' for value in pack_ids) or 'not reported'}",
                "- Relevant paths:",
                *[f"  - `{path}`" for path in relevant_paths],
                "- Source observations:",
                "",
            ]
        )
        lines.extend(_json_block(observations))
        if topology_context is not None:
            lines.extend(["", "- Neighboring topology:", ""])
            lines.extend(_json_block(topology_context))
        lines.extend(
            [
                "",
                "After checking the cited pages, add one explicit selection to "
                "`values`:",
                "",
            ]
        )
        example_value = conflict["values"][0] if conflict["values"] else None
        lines.extend(
            _json_block(
                {
                    "object_id": conflict["object_id"],
                    "field": conflict["field"],
                    "value": example_value,
                    "rationale": "Replace with the reviewer's source-based rationale.",
                    "source_pages": pages,
                }
            )
        )
        lines.append("")
    lines.extend(["## Uncertainties", ""])
    if not uncertainties:
        lines.extend(["No pending uncertainties.", ""])
    for uncertainty in uncertainties:
        pages = uncertainty["source_pages"]
        pack_ids = [uncertainty["pack_id"]]
        topology_context = _topology_context(
            evaluated, uncertainty["target_id"]
        )
        relevant_paths = _review_paths(
            pack_ids=pack_ids,
            pages=pages,
            include_map_renders=uncertainty.get("target_kind")
            in {"topology-node", "topology-edge"},
        )
        lines.extend(
            [
                f"### `{uncertainty['id']}`",
                "",
                f"- Target: `{uncertainty['target_id']}`",
                f"- Pack: `{uncertainty['pack_id']}`",
                f"- Source pages: {', '.join(map(str, pages))}",
                f"- Question: {uncertainty['description']}",
                "- Relevant paths:",
                *[f"  - `{path}`" for path in relevant_paths],
                "",
            ]
        )
        if topology_context is not None:
            lines.extend(["Neighboring topology:", ""])
            lines.extend(_json_block(topology_context))
            lines.append("")
        lines.extend(
            [
                "If the uncertainty is acceptable after source review, add this "
                "entry to `accepted_uncertainties`:",
                "",
            ]
        )
        lines.extend(
            _json_block(
                {
                    "uncertainty_id": uncertainty["id"],
                    "rationale": (
                        "Replace with why the remaining uncertainty is acceptable."
                    ),
                    "source_pages": pages,
                }
            )
        )
        lines.extend(
            [
                "",
                "If it is not acceptable, correct the source evidence or add the "
                "necessary canonical value instead of accepting it.",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


# Kept as a source-level alias for callers of the former advanced helper.
render_review_queue = render_codex_task


def command_review(args: argparse.Namespace) -> None:
    workspace = _workspace(args)
    output = (
        Path(args.output).resolve()
        if args.output
        else workspace.input / "review.json"
    )
    source = load_json(workspace.input / "source.json")
    if not output.exists() or args.force:
        write_json(output, _empty_review(source["sha256"]))
    evaluated = evaluate(workspace.input)
    queue = workspace.exchange / "codex-task.md"
    queue.write_text(
        render_codex_task(evaluated, output),
        encoding="utf-8",
        newline="\n",
    )
    print(output)
    print(f"Codex task: {queue}", file=sys.stderr)


def command_assemble(args: argparse.Namespace) -> None:
    workspace = _workspace(args)
    output = Path(args.output).resolve() if args.output else workspace.module
    module = assemble(
        workspace.input,
        output,
        profile=args.profile,
        replace_generated_output=args.replace_generated_output,
    )
    print(output)
    print(module["module_sha256"])


def command_clean(args: argparse.Namespace) -> None:
    workspace = _workspace(args)
    for path in (workspace.exchange, workspace.cache):
        if path.is_dir():
            shutil.rmtree(path)
            print(path)


def _workspace_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--workspace-root",
        default=str(REPOSITORY_ROOT),
        help="repository root containing module-input and _exchange",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare deterministic extraction packs for ChatGPT and assemble "
            "one validated module per repository branch."
        )
    )
    commands = parser.add_subparsers(dest="command", required=True)

    run_parser = commands.add_parser(
        "run", help="start or continue the state-aware extraction workflow"
    )
    run_parser.add_argument("pdf", metavar="PDF", nargs="?")
    run_parser.add_argument("--slug", help="override the filename-derived slug")
    run_parser.add_argument("--title", help="override PDF metadata or filename title")
    _workspace_option(run_parser)
    run_parser.set_defaults(function=command_run)

    status_parser = commands.add_parser(
        "status", help="show the current stage and next action"
    )
    _workspace_option(status_parser)
    status_parser.add_argument(
        "--json", action="store_true", help="print structured status"
    )
    status_parser.add_argument(
        "--scene",
        metavar="PLACE_ID",
        help="resolve one bounded scene context bundle from the released module",
    )
    status_parser.add_argument(
        "--situation",
        metavar="SITUATION_ID",
        help=(
            "explicitly select which situation available at --scene is active"
        ),
    )
    status_parser.set_defaults(function=command_status)

    clean_parser = commands.add_parser(
        "clean", help="remove disposable _exchange and preparation cache"
    )
    _workspace_option(clean_parser)
    clean_parser.set_defaults(function=command_clean)

    advanced_parser = commands.add_parser(
        "advanced", help="show deterministic pipeline stage commands"
    )
    advanced = advanced_parser.add_subparsers(
        dest="advanced_command", required=True
    )

    prepare_parser = advanced.add_parser(
        "prepare", help="replace the workspace and create routing.zip"
    )
    prepare_parser.add_argument("pdf", metavar="PDF")
    prepare_parser.add_argument("--slug", required=True)
    prepare_parser.add_argument("--title", required=True)
    _workspace_option(prepare_parser)
    prepare_parser.set_defaults(function=command_prepare)

    focus_parser = advanced.add_parser(
        "focus", help="accept routing.json and create focused ZIPs"
    )
    _workspace_option(focus_parser)
    focus_parser.add_argument(
        "--routing",
        help="routing response (default: _exchange/routing.json)",
    )
    focus_parser.set_defaults(function=command_focus)

    ingest_parser = advanced.add_parser(
        "ingest", help="validate and copy focused JSON responses"
    )
    _workspace_option(ingest_parser)
    ingest_parser.set_defaults(function=command_ingest)

    validate_parser = advanced.add_parser(
        "validate", help="validate evidence, review, and release gates"
    )
    _workspace_option(validate_parser)
    validate_parser.add_argument(
        "--profile", choices=("draft", "release"), default="draft"
    )
    validate_parser.set_defaults(function=command_validate)

    review_parser = advanced.add_parser(
        "review", help="create or refresh the Codex task"
    )
    _workspace_option(review_parser)
    review_parser.add_argument("--output")
    review_parser.add_argument("--force", action="store_true")
    review_parser.set_defaults(function=command_review)

    assemble_parser = advanced.add_parser(
        "assemble", help="render a draft or release module"
    )
    _workspace_option(assemble_parser)
    assemble_parser.add_argument(
        "--profile", choices=("draft", "release"), required=True
    )
    assemble_parser.add_argument(
        "--output", help="output directory (default: module)"
    )
    assemble_parser.add_argument(
        "--replace-generated-output", action="store_true"
    )
    assemble_parser.set_defaults(function=command_assemble)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.function(args)
    except ExtractorError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
