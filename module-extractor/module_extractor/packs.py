"""Deterministic task/page partitioning and focused archive creation."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
from typing import Any, Iterable, Mapping, Sequence

from .contracts import (
    CONTENT_SCHEMA,
    CONTENT_TASKS,
    MAP_RENDER_BUDGET,
    MAP_SCHEMA,
)
from .errors import ExtractorError
from .util import (
    canonical_json_bytes,
    deterministic_zip,
    resolve_asset_root,
    sha256_file,
    write_json,
)


CONTENT_MIN_TEXT = 15 * 1024
CONTENT_TARGET_TEXT = 30 * 1024
CONTENT_PAGE_LIMIT = 8
MAP_PAGE_LIMIT = 20


def _content_prompt(
    source: Mapping[str, Any],
    pack_id: str,
    page_tasks: Sequence[Mapping[str, Any]],
) -> str:
    pages = [row["pdf_page"] for row in page_tasks]
    checklist = "\n".join(
        (
            f"- Page {row['pdf_page']}: "
            + (
                ", ".join(row["tasks"])
                if row["tasks"]
                else "illustration context only"
            )
        )
        for row in page_tasks
    )
    return f"""Extract all routed semantic evidence from physical pages {', '.join(map(str, pages))}.

Page/task checklist:
{checklist}

Task-to-record mapping:
- adventure: location, actor, situation, procedure, knowledge
- rules: rule
- tables: table
- items: item
- spells: spell
- classes: class
- effects: effect

Every record needs id, record_type, fields, source_pages, confidence,
references, and uncertainties. Required fields by record type:
- location: title and player-safe first_impression
- actor: title, role
- situation: title, player-safe perceived, activation
- procedure: title, trigger, steps (array)
- knowledge, rule, item, spell, class, effect: title, text
- table: title, entries (array)

Each uncertainty needs description and source_pages. Confidence is high,
medium, or low.

For a location, extract only source-supported operational fields:
- contents: visible contents (array of strings);
- discoverable: objects with information and the action or condition needed
  to acquire it;
- hidden: GM-only information (array of strings);
- triggers, hazards, resources, and occupants (arrays of strings);
- actor_references, situation_references, procedure_references, and
  knowledge_references (arrays of record IDs also listed in references);
- keyed_area, map_label, or topology_label when the source supplies it;
- topology_node when the text explicitly names a map node, or null only when
  the source explicitly establishes that the location is not mapped.

Omit optional location fields when the source provides no evidence. Never add
empty arrays, generic prose, or invented defaults merely to fill the shape.
First impression is player-safe: do not include secrets, concealed features,
or facts that require investigation. Discoverable entries must pair the
information with a non-empty acquisition condition. Hidden is GM-only.
For an actor, extract only source-supported operational fields:
- appearance: what observers immediately notice (string);
- role: what the actor is and does in the adventure (string);
- goals, behavior, capabilities: arrays of strings; capabilities retain exact
  statistics, numbers, and mechanics;
- reactions: objects with stimulus and response;
- relationships: objects with target_id (another actor record ID) and
  relationship;
- knowledge_references, location_references, and situation_references: arrays
  of record IDs also listed in references;
- hidden: GM-only motivations, orders, or constraints (array of strings);
- starting_state: only a state the source explicitly states as the starting
  state (array of strings).

Everything except hidden may be revealed through play. Never record mutable
runtime state such as current health, position, attitude, or inventory.

For a situation, extract only source-supported operational fields:
- perceived: what the players perceive when it occurs (player-safe string);
- activation: an object with type (triggered, timed, random, keyed, ongoing,
  or chosen) and condition;
- repeat: an object with mode (once or repeatable) and an optional condition;
- location_references, procedure_references, knowledge_references: arrays of
  record IDs also listed in references;
- participants: objects with actor_id and role;
- actor_reactions: objects with actor_id and reaction;
- stakes: the pressure and what is at risk (array of strings);
- approaches: likely player approaches or decisions (array of strings);
- outcomes: possible outcomes (array of strings);
- completion: completion conditions (array of strings);
- possible_effects: objects with effect, description, an optional condition,
  and a target. Effect is one of activate-situation, actor-state,
  future-thread, reveal-knowledge, schedule-procedure, stop-procedure, or
  topology-state. Every effect except future-thread names a target: the
  situation, actor, knowledge, or procedure record ID, or, for
  topology-state, the map node ID. Possible effects describe what the source
  says may happen. They are never applied and never record that a situation
  already ran.

`place_record_template`, `actor_record_template`, and
`situation_record_template` in the response template illustrate the shape only;
do not return them as evidence or copy fields that the source does not support.

Return only a JSON file matching response-template.json. Copy schema,
source_sha256, pack_id, and task exactly. Each source-specific observation must
have a stable conceptual id, typed fields, confidence, and physical-page
citations. Paraphrase operational content while retaining exact mechanics,
names, numbers, and table entries. Attach uncertainty to its affected record.
Use a source-faithful extracted ID; do not guess the final canonical runtime
ID. Alternate IDs from different passages are retained as observations and
reviewed after all packs are ingested.
Complete task_coverage for every routed page/task pair. Use extracted with
compatible record IDs when evidence was found. Use not-found with a concise
explanation only when close reading finds no evidence for a routed task.
Illustration-context pages require no coverage entry. Do not infer unsupported
facts or generate canonical module files.

schema: {CONTENT_SCHEMA}
source_sha256: {source['sha256']}
pack_id: {pack_id}
task: content
"""


def focused_pack_readme(
    source: Mapping[str, Any],
    pack_id: str,
    task: str,
    pages: Sequence[int],
    *,
    tasks: Sequence[str] = (),
) -> str:
    page_text = ", ".join(map(str, pages))
    purpose = (
        "all routed semantic tasks"
        + (f" ({', '.join(tasks)})" if tasks else "")
        if task == "content"
        else "map topology"
    )
    return f"""# Focused evidence pack

This archive extracts **{purpose}** from physical pages {page_text} of
**{source['title']}**.

- Pack ID: `{pack_id}`
- Expected response filename: `{pack_id}.json`
- Save beside this ZIP as: `{pack_id}.json`

## In ChatGPT

1. Attach this ZIP to a new chat. Use a fresh chat for each pack.
2. Send this message:

   > Open the attached ZIP, read `prompt.md`, follow it exactly, and return only
   > the completed JSON response as a downloadable file.

3. Download the response, name it `{pack_id}.json`, and place it beside
   `{pack_id}.zip` in the `_exchange/` directory.

If ChatGPT cannot inspect the ZIP, extract it locally and attach `prompt.md`,
`response-template.json`, and the supplied page text and images. Then send the
same message.

Process every page/task pair listed in `prompt.md`. Do not combine evidence from
other packs or edit the response template in this archive. Module Extractor
validates the saved response before assembly.
"""


def _content_template(
    source: Mapping[str, Any],
    pack_id: str,
    page_tasks: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": CONTENT_SCHEMA,
        "source_sha256": source["sha256"],
        "pack_id": pack_id,
        "task": "content",
        "task_coverage": [
            {
                "pdf_page": row["pdf_page"],
                "task": task,
                "status": "extracted",
                "record_ids": [],
                "notes": "",
            }
            for row in page_tasks
            for task in row["tasks"]
        ],
        "place_record_template": {
            "id": "location.area-example",
            "record_type": "location",
            "fields": {
                "title": "Example Room",
                "first_impression": "A source-supported player-safe impression.",
                "contents": ["A visible source-supported feature."],
                "discoverable": [
                    {
                        "information": "A source-supported concealed detail.",
                        "condition": "Search the indicated feature.",
                    }
                ],
                "hidden": ["A source-supported GM-only fact."],
                "topology_label": "1",
            },
            "source_pages": [page_tasks[0]["pdf_page"]],
            "confidence": "low",
            "references": [],
            "uncertainties": [],
        },
        "actor_record_template": {
            "id": "actor.example-guard",
            "record_type": "actor",
            "fields": {
                "title": "Example Guard",
                "appearance": "A source-supported observable description.",
                "role": "What the source says this actor does here.",
                "goals": ["A source-supported goal."],
                "behavior": ["A source-supported public behavior."],
                "reactions": [
                    {
                        "stimulus": "A source-supported provocation.",
                        "response": "The source-supported response.",
                    }
                ],
                "capabilities": ["Exact source statistics and mechanics."],
                "hidden": ["A source-supported secret order or motivation."],
            },
            "source_pages": [page_tasks[0]["pdf_page"]],
            "confidence": "low",
            "references": [],
            "uncertainties": [],
        },
        "situation_record_template": {
            "id": "situation.example-standoff",
            "record_type": "situation",
            "fields": {
                "title": "Example Standoff",
                "perceived": "A player-safe description of what happens.",
                "activation": {
                    "type": "triggered",
                    "condition": "The source-stated activation condition.",
                },
                "repeat": {"mode": "once", "condition": None},
                "participants": [
                    {"actor_id": "actor.example-guard", "role": "Blocks the way."}
                ],
                "stakes": ["What the source says is at risk."],
                "approaches": ["A likely source-supported approach."],
                "outcomes": ["A source-supported possible outcome."],
                "completion": ["The source-stated completion condition."],
                "possible_effects": [
                    {
                        "effect": "future-thread",
                        "description": "A source-supported later consequence.",
                    }
                ],
            },
            "source_pages": [page_tasks[0]["pdf_page"]],
            "confidence": "low",
            "references": ["actor.example-guard"],
            "uncertainties": [],
        },
        "records": [],
    }


def _map_prompt(
    source: Mapping[str, Any], pack_id: str, pages: Sequence[int]
) -> str:
    return f"""Extract visible topology evidence from physical pages {', '.join(map(str, pages))}.

Return only JSON matching response-template.json. Copy schema, source_sha256,
and pack_id exactly. Record source-specific nodes and passages. Classify each
node as place, waypoint, or boundary. A waypoint or boundary remains topology
and does not need a full place card. Use null only when the source does not
support a classification and record the uncertainty. A passage has independent
facets:
- kind: a concise source-faithful description such as corridor, path, doorway,
  hatch, stairway, shaft, bridge, portal, or transport ward;
- medium: a concise source-faithful traversal medium such as ground, water,
  air, vacuum, dream, or magical;
- elevation: exactly level, up, down, vertical, variable, or null;
- barriers: visible or stated obstacles such as a door, lock, rubble, seal,
  force field, or guarded threshold;
- features: other operational properties of the connection;
- conditions: requirements or circumstances that control whether traversal is
  possible, including keyed, timed, one-use, vehicle-only, or spell-dependent;
- baseline_state: the source-stated default state such as open, closed,
  blocked, dormant, or concealed;
- visibility: exactly visible, hidden, or null;
- hazards: hazards intrinsic to traversing the connection;
- traversal_direction: exactly both, from_to, to_from, conditional, or null.

Hidden and conditional passages must name their revealing or traversal
requirements under conditions. Use null for an unknown scalar facet and [] for
an unknown set facet; unknown values assert nothing. Put arbitrary source
wording in kind, medium, barriers, features, or conditions rather than
inventing a controlled value. A direction is conditional when its availability
or direction depends on a stated condition; record that condition under
conditions. Cite only pages in this pack and attach each uncertainty to a node
or passage ID. Do not infer invisible connections or generate canonical files.

schema: {MAP_SCHEMA}
source_sha256: {source['sha256']}
pack_id: {pack_id}
"""


def _map_template(
    source: Mapping[str, Any], pack_id: str, page: int
) -> dict[str, Any]:
    return {
        "schema": MAP_SCHEMA,
        "source_sha256": source["sha256"],
        "pack_id": pack_id,
        "nodes": [
            {
                "id": "area-example",
                "label": "Example",
                "classification": "place",
                "source_pages": [page],
                "confidence": "low",
            },
            {
                "id": "area-other",
                "label": "Other",
                "classification": "waypoint",
                "source_pages": [page],
                "confidence": "low",
            }
        ],
        "passages": [
            {
                "id": "passage-example",
                "from": "area-example",
                "to": "area-other",
                "facets": {
                    "kind": None,
                    "medium": None,
                    "elevation": None,
                    "barriers": [],
                    "features": [],
                    "conditions": [],
                    "baseline_state": None,
                    "visibility": None,
                    "hazards": [],
                    "traversal_direction": None,
                },
                "source_pages": [page],
                "confidence": "low",
            }
        ],
        "uncertainties": [
            {
                "target_id": "area-example",
                "description": "",
                "source_pages": [page],
            }
        ],
    }


def _render_map_page(source_pdf: Path, destination: Path, page: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            [
                "pdftoppm",
                "-png",
                "-r",
                "200",
                "-f",
                str(page),
                "-l",
                str(page),
                "-singlefile",
                str(source_pdf),
                str(destination.with_suffix("")),
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise ExtractorError(f"could not render map page {page}: {exc}") from exc
    if result.returncode or not destination.is_file():
        detail = result.stderr.strip() or "no output file"
        raise ExtractorError(f"could not render map page {page}: {detail}")


def _content_runs(
    routing: Sequence[Mapping[str, Any]],
) -> list[list[dict[str, Any]]]:
    runs: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []

    def finish() -> None:
        while current and not current[-1]["tasks"]:
            current.pop()
        if current:
            runs.append(list(current))
        current.clear()

    for raw in sorted(routing, key=lambda item: item["pdf_page"]):
        tasks = sorted(set(raw["tasks"]) & CONTENT_TASKS)
        reason = raw.get("exclusion_reason")
        if tasks:
            current.append(
                {
                    "pdf_page": raw["pdf_page"],
                    "tasks": tasks,
                    "context_reason": None,
                }
            )
        elif reason == "non-operational-illustration" and current:
            current.append(
                {
                    "pdf_page": raw["pdf_page"],
                    "tasks": [],
                    "context_reason": reason,
                }
            )
        else:
            finish()
    finish()
    return runs


def partition_content_pages(
    routing: Sequence[Mapping[str, Any]],
    text_sizes: Mapping[int, int],
) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    for run in _content_runs(routing):
        current: list[dict[str, Any]] = []
        current_bytes = 0
        for row in run:
            page_bytes = text_sizes[row["pdf_page"]]
            projected = current_bytes + page_bytes
            if current and (
                len(current) == CONTENT_PAGE_LIMIT
                or (
                    current_bytes >= CONTENT_MIN_TEXT
                    and projected > CONTENT_TARGET_TEXT
                )
            ):
                groups.append(current)
                current = []
                current_bytes = 0
            current.append(row)
            current_bytes += page_bytes
        if current:
            groups.append(current)
    return groups


def partition_map_pages(
    pages: Iterable[int],
    render_sizes: Mapping[int, int],
) -> list[list[int]]:
    groups: list[list[int]] = []
    current: list[int] = []
    current_bytes = 0
    for page in sorted(set(pages)):
        size = render_sizes[page]
        if current and (
            len(current) == MAP_PAGE_LIMIT
            or current_bytes + size > MAP_RENDER_BUDGET
        ):
            groups.append(current)
            current = []
            current_bytes = 0
        current.append(page)
        current_bytes += size
    if current:
        groups.append(current)
    return groups


def create_focused_packs(
    run_dir: Path,
    source: Mapping[str, Any],
    prepared: Mapping[str, Any],
    routing: Sequence[Mapping[str, Any]],
    *,
    asset_base_dir: Path | None = None,
    archive_dir: Path | None = None,
    render_dir: Path | None = None,
) -> list[dict[str, Any]]:
    assets = resolve_asset_root(asset_base_dir or run_dir, prepared)
    pack_dir = archive_dir or run_dir / "packs"
    pack_dir.mkdir(parents=True, exist_ok=True)
    response_dir = run_dir / "responses"
    response_dir.mkdir(parents=True, exist_ok=True)
    packs: list[dict[str, Any]] = []

    routed_map_pages = {
        row["pdf_page"] for row in routing if "maps" in row["tasks"]
    }
    map_renders = render_dir or run_dir / "map-renders"
    source_pdf = assets / "source.pdf"
    rendered_maps: dict[int, Path] = {}
    for page in sorted(routed_map_pages):
        render = map_renders / f"page-{page:04d}.png"
        preserved_render = (
            assets / "focused" / "map-renders" / f"page-{page:04d}.png"
        )
        if preserved_render.is_file():
            render = preserved_render
        elif not render.is_file():
            if not source_pdf.is_file():
                raise ExtractorError(
                    f"prepared source PDF is missing for map page {page}"
                )
            _render_map_page(source_pdf, render, page)
        rendered_maps[page] = render
    map_sizes = {page: path.stat().st_size for page, path in rendered_maps.items()}
    for number, group in enumerate(
        partition_map_pages(routed_map_pages, map_sizes), 1
    ):
        pack_id = f"map.v2.{number:03d}"
        render_bytes = sum(map_sizes[page] for page in group)
        entries: dict[str, bytes | Path] = {
            "README.md": focused_pack_readme(
                source, pack_id, "maps", group
            ).encode("utf-8"),
            "pack.json": canonical_json_bytes(
                {
                    "schema": "module-pack/v1",
                    "source": source,
                    "pack_id": pack_id,
                    "task": "maps",
                    "physical_pages": group,
                    "render_bytes": render_bytes,
                }
            ),
            "prompt.md": _map_prompt(source, pack_id, group).encode("utf-8"),
            "response-template.json": canonical_json_bytes(
                _map_template(source, pack_id, group[0])
            ),
        }
        for page in group:
            text_path = assets / "text" / "pages" / f"page-{page:04d}.txt"
            if not text_path.is_file():
                raise ExtractorError(f"prepared text is missing for page {page}")
            entries[f"pages/page-{page:04d}.txt"] = text_path
            entries[f"renders/page-{page:04d}.png"] = rendered_maps[page]
        archive = pack_dir / f"{pack_id}.zip"
        deterministic_zip(archive, entries)
        archive_relative = os.path.relpath(archive, run_dir)
        packs.append(
            {
                "pack_id": pack_id,
                "task": "maps",
                "physical_pages": group,
                "render_bytes": render_bytes,
                "archive_path": Path(archive_relative).as_posix(),
                "pack_sha256": sha256_file(archive),
                "response_path": f"responses/{pack_id}.json",
            }
        )

    text_paths = {
        row["pdf_page"]: assets
        / "text"
        / "pages"
        / f"page-{row['pdf_page']:04d}.txt"
        for row in routing
    }
    missing_text = [page for page, path in text_paths.items() if not path.is_file()]
    if missing_text:
        raise ExtractorError(f"prepared text is missing for pages: {missing_text}")
    text_sizes = {page: path.stat().st_size for page, path in text_paths.items()}
    content_groups = partition_content_pages(routing, text_sizes)
    for number, page_tasks in enumerate(content_groups, 1):
        pack_id = f"content.{number:03d}"
        pages = [row["pdf_page"] for row in page_tasks]
        tasks = sorted({task for row in page_tasks for task in row["tasks"]})
        text_bytes = sum(text_sizes[page] for page in pages)
        entries = {
            "README.md": focused_pack_readme(
                source, pack_id, "content", pages, tasks=tasks
            ).encode("utf-8"),
            "pack.json": canonical_json_bytes(
                {
                    "schema": "module-pack/v1",
                    "source": source,
                    "pack_id": pack_id,
                    "task": "content",
                    "tasks": tasks,
                    "physical_pages": pages,
                    "page_tasks": page_tasks,
                    "text_bytes": text_bytes,
                }
            ),
            "prompt.md": _content_prompt(source, pack_id, page_tasks).encode(
                "utf-8"
            ),
            "response-template.json": canonical_json_bytes(
                _content_template(source, pack_id, page_tasks)
            ),
        }
        for page in pages:
            entries[f"pages/page-{page:04d}.txt"] = text_paths[page]
            thumbnail = assets / "thumbnails" / f"page-{page:04d}.png"
            if thumbnail.is_file():
                entries[f"thumbnails/page-{page:04d}.png"] = thumbnail
        archive = pack_dir / f"{pack_id}.zip"
        deterministic_zip(archive, entries)
        archive_relative = os.path.relpath(archive, run_dir)
        packs.append(
            {
                "pack_id": pack_id,
                "task": "content",
                "tasks": tasks,
                "physical_pages": pages,
                "page_tasks": page_tasks,
                "text_bytes": text_bytes,
                "archive_path": Path(archive_relative).as_posix(),
                "pack_sha256": sha256_file(archive),
                "response_path": f"responses/{pack_id}.json",
            }
        )
    packs.sort(key=lambda item: item["pack_id"])
    write_json(
        run_dir / "packs.json",
        {
            "schema": "module-pack-manifest/v1",
            "source_sha256": source["sha256"],
            "packs": packs,
        },
    )
    return packs
