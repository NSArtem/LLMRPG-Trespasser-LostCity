from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile


EXTRACTOR_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXTRACTOR_ROOT))

from module_extractor import cli as cli_module  # noqa: E402
from module_extractor.assembly import assemble  # noqa: E402
from module_extractor.contracts import (  # noqa: E402
    CONTENT_SCHEMA,
    MAP_SCHEMA,
    ROUTING_SCHEMA,
    validate_content_response,
)
from module_extractor.rendering import validate_rendered_module  # noqa: E402
from module_extractor.errors import ExtractorError  # noqa: E402
from module_extractor.reconciliation import reconcile_records  # noqa: E402
from module_extractor.scene import resolve_scene  # noqa: E402
from module_extractor.topology import resolve_operational_topology  # noqa: E402
from module_extractor.util import content_tree_hash, load_json  # noqa: E402
from module_extractor.review import release_gate  # noqa: E402


def _place(
    identifier: str,
    title: str,
    topology_label: str | None,
    *,
    references: list[str] | None = None,
    mixed_visibility: bool = False,
) -> dict:
    fields: dict = {
        "title": title,
        "first_impression": f"{title} is immediately visible.",
    }
    if topology_label is None:
        fields["topology_node"] = None
    else:
        fields["topology_label"] = topology_label
    if mixed_visibility:
        fields.update(
            {
                "contents": ["A bronze brazier stands in the center."],
                "discoverable": [
                    {
                        "information": "Scratches outline a concealed door.",
                        "condition": "Search the north wall.",
                    }
                ],
                "hidden": ["The concealed door is watched by the steward."],
                "triggers": ["Opening the brazier sounds a chime."],
                "hazards": ["The brazier flares when disturbed."],
                "resources": ["The brazier contains one flask of lamp oil."],
                "occupants": ["A mailed guard."],
                "actor_references": ["actor.guard"],
                "situation_references": ["situation.alarm"],
                "procedure_references": ["procedure.search-wall"],
                "knowledge_references": ["knowledge.old-runes"],
            }
        )
    return {
        "id": identifier,
        "record_type": "location",
        "fields": fields,
        "source_pages": [1],
        "confidence": "high",
        "references": references or [],
        "uncertainties": [],
    }


def _passage(
    identifier: str,
    start: str,
    end: str,
    *,
    kind: str,
    baseline_state: str,
    visibility: str,
    conditions: list[str],
    barriers: list[str] | None = None,
    hazards: list[str] | None = None,
) -> dict:
    return {
        "id": identifier,
        "from": start,
        "to": end,
        "facets": {
            "kind": kind,
            "medium": "ground",
            "elevation": "level",
            "barriers": barriers or [],
            "features": [],
            "conditions": conditions,
            "baseline_state": baseline_state,
            "visibility": visibility,
            "hazards": hazards or [],
            "traversal_direction": "both",
        },
        "source_pages": [2],
        "confidence": "high",
    }


class OperationalTopologyTests(unittest.TestCase):
    def test_optional_place_material_is_omitted_not_defaulted(self) -> None:
        pack = {
            "pack_id": "content.001",
            "task": "content",
            "physical_pages": [1],
            "page_tasks": [{"pdf_page": 1, "tasks": ["adventure"]}],
        }
        record = _place("location.market", "Market", None)
        record["fields"]["contents"] = []
        response = {
            "schema": CONTENT_SCHEMA,
            "source_sha256": "a" * 64,
            "pack_id": "content.001",
            "task": "content",
            "task_coverage": [
                {
                    "pdf_page": 1,
                    "task": "adventure",
                    "status": "extracted",
                    "record_ids": ["location.market"],
                    "notes": "",
                }
            ],
            "records": [record],
        }
        source = {
            "sha256": "a" * 64,
            "pdf_pages": 1,
        }
        with self.assertRaisesRegex(
            ExtractorError, "one or more non-empty strings"
        ):
            validate_content_response(response, pack, source)

    def test_mapped_and_unmapped_observations_conflict(self) -> None:
        observations = []
        for number, node in enumerate((None, "map.area-1"), 1):
            observations.append(
                {
                    "observation_id": f"observation.{number}",
                    "concept_id": "place.test.hall",
                    "record_type": "location",
                    "fields": {
                        "title": "Hall",
                        "first_impression": "A hall.",
                        "topology_node": node,
                    },
                    "source_pages": [number],
                    "confidence": "high",
                    "references": [],
                    "pack_id": f"content.{number:03d}",
                }
            )
        records, conflicts = reconcile_records(observations)
        self.assertNotIn("topology_node", records[0]["fields"])
        self.assertEqual(conflicts[0]["field"], "topology_node")

    def test_ambiguous_repeated_area_number_requires_review(self) -> None:
        reviewed = {
            "records": [
                {
                    "id": "place.test.echo-room",
                    "record_type": "location",
                    "fields": {
                        "title": "Area 7: Echo Room",
                        "first_impression": "An echoing chamber.",
                        "topology_label": "7",
                    },
                    "references": [],
                    "source_pages": [1],
                }
            ],
            "topology": {
                "nodes": [
                    {
                        "id": "map.level-one.area-7",
                        "labels": ["7"],
                        "titles": ["Echo Room"],
                        "classification": "place",
                    },
                    {
                        "id": "map.level-two.area-7",
                        "labels": ["7"],
                        "titles": ["Echo Room"],
                        "classification": "place",
                    },
                ],
                "passages": [],
            },
            "topology_composites": [],
            "unresolved_conflicts": [],
            "pending_uncertainties": [],
        }
        result = resolve_operational_topology(reviewed)
        self.assertTrue(
            any("ambiguous topology join" in error for error in result["topology_errors"])
        )
        self.assertNotIn("topology_node", result["records"][0]["fields"])
        self.assertTrue(
            any(
                "ambiguous topology join" in error
                for error in release_gate(result, {"complete": True})
            )
        )

    def test_waypoints_and_passage_requirements_are_validated(self) -> None:
        reviewed = {
            "records": [
                {
                    "id": "place.test.room",
                    "record_type": "location",
                    "fields": {
                        "title": "Area 1: Room",
                        "first_impression": "A room.",
                        "topology_node": "node.room",
                    },
                    "references": [],
                    "source_pages": [1],
                }
            ],
            "topology": {
                "nodes": [
                    {"id": "node.room", "classification": "place"},
                    {"id": "node.waypoint", "classification": "waypoint"},
                ],
                "passages": [
                    {
                        "id": "edge.hidden",
                        "from": "node.room",
                        "to": "node.waypoint",
                        "facets": {
                            "visibility": "hidden",
                            "traversal_direction": "conditional",
                            "conditions": [],
                        },
                    }
                ],
            },
            "topology_composites": [],
        }
        result = resolve_operational_topology(reviewed)
        self.assertTrue(
            any("has no reveal condition" in error for error in result["topology_errors"])
        )
        self.assertTrue(
            any("has no condition" in error for error in result["topology_errors"])
        )
        self.assertFalse(
            any("waypoint has no place" in error for error in result["topology_errors"])
        )


class CleanOperationalPipelineTests(unittest.TestCase):
    def test_prepare_through_scene_resolution_is_clean_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / "synthetic-operational-places.pdf"
            pdf.write_bytes(b"synthetic pdf")

            def fake_poppler(arguments: list[str]) -> mock.Mock:
                if arguments[0] == "pdftotext":
                    Path(arguments[-1]).write_text(
                        "Operational rooms and social location.\f"
                        "Map with secret door and crawlway.\f",
                        encoding="utf-8",
                    )
                elif arguments[0] == "pdftoppm":
                    prefix = Path(arguments[-1])
                    for page in (1, 2):
                        (prefix.parent / f"{prefix.name}-{page}.png").write_bytes(
                            f"thumb-{page}".encode()
                        )
                return mock.Mock(returncode=0, stdout="", stderr="")

            prepare_args = argparse.Namespace(
                pdf=str(pdf),
                slug="synthetic-places",
                title="Synthetic Operational Places",
                workspace_root=str(root),
            )
            with (
                mock.patch(
                    "module_extractor.preparation.shutil.which",
                    return_value="/usr/bin/tool",
                ),
                mock.patch(
                    "module_extractor.preparation._pdf_info",
                    return_value={"pdf_pages": 2, "pdf_title": ""},
                ),
                mock.patch(
                    "module_extractor.preparation._run",
                    side_effect=fake_poppler,
                ),
                redirect_stdout(io.StringIO()),
                redirect_stderr(io.StringIO()),
            ):
                cli_module.command_prepare(prepare_args)

            module_input = root / "module-input"
            exchange = root / "_exchange"
            source = load_json(module_input / "source.json")
            routing = {
                "schema": ROUTING_SCHEMA,
                "source_sha256": source["sha256"],
                "pages": [
                    {
                        "pdf_page": 1,
                        "tasks": ["adventure"],
                        "exclusion_reason": None,
                        "confidence": "high",
                        "notes": "",
                    },
                    {
                        "pdf_page": 2,
                        "tasks": ["maps"],
                        "exclusion_reason": None,
                        "confidence": "high",
                        "notes": "",
                    },
                ],
            }
            (exchange / "routing.json").write_text(
                json.dumps(routing), encoding="utf-8"
            )

            def fake_map_render(_pdf: Path, destination: Path, page: int) -> None:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(f"map-{page}".encode())

            with (
                mock.patch(
                    "module_extractor.packs._render_map_page",
                    side_effect=fake_map_render,
                ),
                redirect_stdout(io.StringIO()),
                redirect_stderr(io.StringIO()),
            ):
                cli_module.command_focus(
                    argparse.Namespace(workspace_root=str(root), routing=None)
                )
            with zipfile.ZipFile(exchange / "content.001.zip") as archive:
                prompt = archive.read("prompt.md").decode()
                template = json.loads(archive.read("response-template.json"))
                self.assertIn("player-safe first_impression", prompt)
                self.assertIn("place_record_template", template)
                self.assertEqual(template["records"], [])
            with zipfile.ZipFile(exchange / "map.v2.001.zip") as archive:
                prompt = archive.read("prompt.md").decode()
                template = json.loads(archive.read("response-template.json"))
                self.assertIn("baseline_state", prompt)
                self.assertIn("visibility", prompt)
                self.assertEqual(
                    template["nodes"][1]["classification"], "waypoint"
                )

            references = [
                "actor.guard",
                "situation.alarm",
                "procedure.search-wall",
                "knowledge.old-runes",
            ]
            content_records = [
                _place(
                    "location.area-1-hall",
                    "Area 1: Hall",
                    "1",
                    references=references,
                    mixed_visibility=True,
                ),
                _place("location.area-2-vault", "Area 2: Vault", "2"),
                _place("location.market", "Winter Market", None),
                {
                    "id": "actor.guard",
                    "record_type": "actor",
                    "fields": {"title": "Guard", "role": "Watches the hall."},
                    "source_pages": [1],
                    "confidence": "high",
                    "references": [],
                    "uncertainties": [],
                },
                {
                    "id": "situation.alarm",
                    "record_type": "situation",
                    "fields": {
                        "title": "Alarm",
                        "perceived": "A chime rings through the hall.",
                        "activation": {
                            "type": "triggered",
                            "condition": "The brazier is disturbed.",
                        },
                    },
                    "source_pages": [1],
                    "confidence": "high",
                    "references": [],
                    "uncertainties": [],
                },
                {
                    "id": "procedure.search-wall",
                    "record_type": "procedure",
                    "fields": {
                        "title": "Search the Wall",
                        "trigger": "The north wall is searched.",
                        "steps": ["Inspect the scratches."],
                    },
                    "source_pages": [1],
                    "confidence": "high",
                    "references": [],
                    "uncertainties": [],
                },
                {
                    "id": "knowledge.old-runes",
                    "record_type": "knowledge",
                    "fields": {"title": "Old Runes", "text": "The runes mark a vault."},
                    "source_pages": [1],
                    "confidence": "high",
                    "references": [],
                    "uncertainties": [],
                },
            ]
            content_response = {
                "schema": CONTENT_SCHEMA,
                "source_sha256": source["sha256"],
                "pack_id": "content.001",
                "task": "content",
                "task_coverage": [
                    {
                        "pdf_page": 1,
                        "task": "adventure",
                        "status": "extracted",
                        "record_ids": sorted(
                            record["id"] for record in content_records
                        ),
                        "notes": "",
                    }
                ],
                "records": content_records,
            }
            map_response = {
                "schema": MAP_SCHEMA,
                "source_sha256": source["sha256"],
                "pack_id": "map.v2.001",
                "nodes": [
                    {
                        "id": "map.area-1",
                        "label": "1",
                        "title": "Hall",
                        "classification": "place",
                        "source_pages": [2],
                        "confidence": "high",
                    },
                    {
                        "id": "map.area-2",
                        "label": "2",
                        "title": "Vault",
                        "classification": "place",
                        "source_pages": [2],
                        "confidence": "high",
                    },
                    {
                        "id": "map.crawl-junction",
                        "label": "W",
                        "title": "Crawl Junction",
                        "classification": "waypoint",
                        "source_pages": [2],
                        "confidence": "high",
                    },
                ],
                "passages": [
                    _passage(
                        "secret-door",
                        "map.area-1",
                        "map.area-2",
                        kind="secret door",
                        baseline_state="concealed and closed",
                        visibility="hidden",
                        conditions=["Search the north wall to reveal it."],
                        barriers=["closed stone door"],
                    ),
                    _passage(
                        "crawlway",
                        "map.area-1",
                        "map.crawl-junction",
                        kind="crawlway",
                        baseline_state="open",
                        visibility="visible",
                        conditions=["Traverse on hands and knees."],
                        hazards=["Sharp stone"],
                    ),
                ],
                "uncertainties": [],
            }
            for pack_id, response in (
                ("content.001", content_response),
                ("map.v2.001", map_response),
            ):
                (exchange / f"{pack_id}.json").write_text(
                    json.dumps(response), encoding="utf-8"
                )

            args = argparse.Namespace(workspace_root=str(root))
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                cli_module.command_ingest(args)
                cli_module.command_clean(args)
            self.assertFalse(exchange.exists())
            self.assertFalse((root / ".module-extractor-cache").exists())

            run_args = argparse.Namespace(
                pdf=None,
                slug=None,
                title=None,
                workspace_root=str(root),
            )
            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(io.StringIO()):
                cli_module.command_run(run_args)
            self.assertIn("Release assembled", output.getvalue())
            self.assertIn(
                "## Place and topology decisions",
                (root / "_exchange" / "codex-task.md").read_text(encoding="utf-8"),
            )

            module = root / "module"
            audit = load_json(module / "audit" / "module.json")
            validate_rendered_module(module, audit)
            hall = next(
                record
                for record in audit["records"]
                if record["fields"]["title"] == "Area 1: Hall"
            )
            hall_path = module / "cards" / "places" / f"{hall['id']}.md"
            hall_text = hall_path.read_text(encoding="utf-8")
            for heading in (
                "First impression",
                "Contents",
                "Discoverable",
                "Hidden",
                "Triggers",
                "Hazards",
                "Resources",
                "Exits",
            ):
                self.assertIn(f"## {heading}", hall_text)
            self.assertNotIn("watched by the steward", hall["fields"]["first_impression"])
            self.assertIn("Generated from topology.yaml", hall_text)
            self.assertIn("Passage kind: secret door", hall_text)
            self.assertIn("Baseline state: concealed and closed", hall_text)
            self.assertIn("Visibility: hidden", hall_text)
            self.assertIn("Search the north wall to reveal it.", hall_text)
            self.assertIn("Passage kind: crawlway", hall_text)
            self.assertIn("Traverse on hands and knees.", hall_text)
            self.assertNotIn("baseline_state", hall["fields"])
            self.assertNotIn("conditions", hall["fields"])

            scene = resolve_scene(module, hall["id"])
            self.assertEqual(scene["total_bytes"], sum(
                item["bytes"] for item in scene["files"]
            ))
            self.assertEqual(len(scene["topology"]["adjacent_edges"]), 2)
            self.assertTrue(
                all(item["path"].startswith("cards/") for item in scene["files"])
            )
            self.assertFalse(
                any(
                    item["path"].startswith("audit/")
                    or item["path"].endswith(".pdf")
                    or item["path"] in {"index.json", "topology.yaml"}
                    for item in scene["files"]
                )
            )
            self.assertEqual(
                {group: len(paths) for group, paths in scene["load_with"].items()},
                {"actors": 1, "situations": 1, "procedures": 1, "knowledge": 1},
            )

            status_output = io.StringIO()
            with redirect_stdout(status_output):
                cli_module.command_status(
                    argparse.Namespace(
                        workspace_root=str(root),
                        json=True,
                        scene=hall["id"],
                    )
                )
            self.assertEqual(
                json.loads(status_output.getvalue())["place_id"], hall["id"]
            )

            duplicate = root / "module-second"
            assemble(module_input, duplicate, profile="release")
            self.assertEqual(content_tree_hash(module), content_tree_hash(duplicate))


if __name__ == "__main__":
    unittest.main()
