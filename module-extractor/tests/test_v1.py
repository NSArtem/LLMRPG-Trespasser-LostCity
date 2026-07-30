from __future__ import annotations

import argparse
from copy import deepcopy
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
from module_extractor import assembly as assembly_module  # noqa: E402
from module_extractor.assembly import (  # noqa: E402
    _replaceable_output,
    assemble,
)
from module_extractor.contracts import (  # noqa: E402
    CONTENT_SCHEMA,
    GENERATED_OUTPUT_SCHEMA,
    MAP_SCHEMA,
    RECORD_TYPES,
    REQUIRED_FIELDS,
    REVIEW_SCHEMA,
    ROUTING_SCHEMA,
    validate_content_response,
    validate_pack_manifest,
    validate_review,
    validate_routing,
)
from module_extractor.coverage import build_coverage  # noqa: E402
from module_extractor.errors import ExtractorError  # noqa: E402
from module_extractor.evidence import (  # noqa: E402
    import_exchange_responses,
    ingest_responses,
    validate_map_response,
)
from module_extractor.packs import (  # noqa: E402
    create_focused_packs,
    focused_pack_readme,
    partition_content_pages,
    partition_map_pages,
)
from module_extractor.preparation import prepare  # noqa: E402
from module_extractor.reconciliation import (  # noqa: E402
    reconcile_records,
    reconcile_topology,
)
from module_extractor.rendering import (  # noqa: E402
    _card,
    card_path,
    render_module,
    validate_rendered_module,
)
from module_extractor.review import (  # noqa: E402
    apply_review,
    canonicalize_evidence_aliases,
    release_gate,
)
from module_extractor.routing import routing_pack_readme  # noqa: E402
from module_extractor.util import (  # noqa: E402
    content_tree_hash,
    sha256_file,
)


def source(page_count: int = 3) -> dict:
    return {
        "filename": "test.pdf",
        "title": "Test",
        "pdf_title": "Test",
        "pdf_pages": page_count,
        "sha256": "a" * 64,
    }


def routing(page_count: int = 3) -> dict:
    return {
        "schema": ROUTING_SCHEMA,
        "source_sha256": "a" * 64,
        "pages": [
            {
                "pdf_page": page,
                "tasks": ["rules"],
                "exclusion_reason": None,
                "confidence": "high",
                "notes": "",
            }
            for page in range(1, page_count + 1)
        ],
    }


def required_fields(record_type: str) -> dict:
    result = {}
    for field in REQUIRED_FIELDS[record_type]:
        if field in {"entries", "steps"}:
            result[field] = []
        elif field == "activation":
            result[field] = {
                "type": "triggered",
                "condition": "The party enters the hall.",
            }
        else:
            result[field] = field
    return result


def content_pack(
    *,
    pages: list[int] | None = None,
    tasks: list[str] | None = None,
    pack_id: str = "content.001",
) -> dict:
    pages = pages or [1]
    tasks = tasks or ["rules"]
    return {
        "pack_id": pack_id,
        "task": "content",
        "tasks": sorted(tasks),
        "physical_pages": pages,
        "page_tasks": [
            {
                "pdf_page": page,
                "tasks": sorted(tasks),
                "context_reason": None,
            }
            for page in pages
        ],
        "text_bytes": 100,
    }


def content_response(
    pack: dict,
    records: list[dict],
    *,
    task: str = "rules",
) -> dict:
    return {
        "schema": CONTENT_SCHEMA,
        "source_sha256": "a" * 64,
        "pack_id": pack["pack_id"],
        "task": "content",
        "task_coverage": [
            {
                "pdf_page": page,
                "task": task,
                "status": "extracted",
                "record_ids": [record["id"] for record in records],
                "notes": "",
            }
            for page in pack["physical_pages"]
        ],
        "records": records,
    }


def observation(
    observation_id: str,
    concept_id: str,
    fields: dict,
    *,
    record_type: str = "rule",
    pack_id: str = "content.rules.001",
) -> dict:
    return {
        "observation_id": observation_id,
        "concept_id": concept_id,
        "record_type": record_type,
        "fields": fields,
        "source_pages": [1],
        "confidence": "high",
        "references": [],
        "pack_id": pack_id,
    }


def map_result(
    pack_id: str,
    facets: dict,
    *,
    reverse: bool = False,
) -> dict:
    start, end = ("area-2", "area-1") if reverse else ("area-1", "area-2")
    nodes = [
        {
            "observation_id": f"observation.{pack_id}.node.area-1",
            "concept_id": "area-1",
            "label": "1",
            "title": None,
            "source_pages": [1],
            "confidence": "high",
            "pack_id": pack_id,
        },
        {
            "observation_id": f"observation.{pack_id}.node.area-2",
            "concept_id": "area-2",
            "label": "2",
            "title": None,
            "source_pages": [1],
            "confidence": "high",
            "pack_id": pack_id,
        },
    ]
    return {
        "pack_id": pack_id,
        "nodes": nodes,
        "passages": [
            {
                "observation_id": f"observation.{pack_id}.passage.edge",
                "source_id": "edge",
                "from": start,
                "to": end,
                "facets": {
                    "kind": None,
                    "medium": None,
                    "elevation": None,
                    "barriers": [],
                    "features": [],
                    "conditions": [],
                    "traversal_direction": None,
                    **facets,
                },
                "source_pages": [1],
                "confidence": "high",
                "pack_id": pack_id,
            }
        ],
        "uncertainties": [],
    }


def rendered_module(records: list[dict] | None = None) -> dict:
    records = records or [
        {
            "id": "actor.example.guard",
            "record_type": "actor",
            "fields": {"title": "Guard", "role": "Protects the gate."},
            "source_pages": [1],
            "references": [],
            "field_observations": {
                "role": [
                    {
                        "pack_id": "content.001",
                        "confidence": "high",
                        "observation_id": "observation.guard",
                    }
                ]
            },
            "observation_ids": ["observation.guard"],
        }
    ]
    return {
        "schema": "operational-module/v2",
        "profile": "release",
        "source": {
            "slug": "example-adventure",
            "filename": "example.pdf",
            "title": "Example Adventure",
            "source_system": "Example System",
            "edition": "Second",
            "pdf_pages": 1,
            "sha256": "a" * 64,
        },
        "coverage": {
            "schema": "module-coverage/v1",
            "physical_pages": 1,
            "complete": True,
            "gaps": [],
            "pages": [
                {
                    "pdf_page": 1,
                    "status": "extracted",
                    "routing_tasks": ["adventure"],
                    "exclusion_reason": None,
                }
            ],
        },
        "packs": [{"pack_id": "content.001"}],
        "review_sha256": "b" * 64,
        "review": {
            "schema": REVIEW_SCHEMA,
            "aliases": [],
            "values": [],
            "accepted_uncertainties": [],
            "notes": "",
        },
        "records": records,
        "topology": {
            "nodes": [
                {
                    "id": "place.gate",
                    "labels": ["1"],
                    "titles": ["Gate"],
                    "source_pages": [1],
                    "observations": [{"pack_id": "map.v1.001"}],
                },
                {
                    "id": "place.courtyard",
                    "labels": ["2"],
                    "titles": ["Courtyard"],
                    "source_pages": [1],
                    "observations": [{"pack_id": "map.v1.001"}],
                },
            ],
            "passages": [
                {
                    "id": "edge-place.gate-place.courtyard",
                    "from": "place.gate",
                    "to": "place.courtyard",
                    "facets": {
                        "kind": "doorway",
                        "medium": "ground",
                        "elevation": "level",
                        "barriers": ["locked gate"],
                        "features": [],
                        "conditions": ["requires key"],
                        "traversal_direction": "both",
                    },
                    "facet_observations": {
                        "kind": [
                            {
                                "pack_id": "map.v1.001",
                                "confidence": "high",
                            }
                        ]
                    },
                    "source_pages": [1],
                    "observation_ids": ["observation.passage"],
                    "conflict_fields": [],
                }
            ],
        },
        "aliases": {"actor.old-guard": "actor.example.guard"},
        "raw_observations": {
            "content": [{"pack_id": "content.001", "confidence": "high"}],
            "topology": [{"pack_id": "map.v1.001"}],
        },
        "uncertainties": [],
        "accepted_uncertainties": [],
        "pending_uncertainties": [],
        "conflicts": [],
        "unresolved_conflicts": [],
        "release_gate": {"passed": True, "errors": []},
        "module_sha256": "c" * 64,
    }


class RoutingAndPackTests(unittest.TestCase):
    def test_routing_is_multilabel_and_page_total(self) -> None:
        value = routing()
        value["pages"][0]["tasks"] = ["rules", "tables", "illustrations"]
        rows = validate_routing(value, source())
        self.assertEqual(
            rows[0]["tasks"], ["illustrations", "rules", "tables"]
        )
        value["pages"].pop()
        with self.assertRaisesRegex(ExtractorError, "missing physical pages"):
            validate_routing(value, source())

    def test_exclusions_are_explicit(self) -> None:
        value = routing()
        value["pages"][1].update(tasks=[], exclusion_reason=None)
        with self.assertRaisesRegex(ExtractorError, "exclusion_reason"):
            validate_routing(value, source())
        value["pages"][1].update(
            tasks=["illustrations"], exclusion_reason=None
        )
        with self.assertRaisesRegex(ExtractorError, "only an illustration"):
            validate_routing(value, source())

    def test_content_partition_combines_tasks_and_bridges_illustrations(self) -> None:
        routes = [
            {
                "pdf_page": 1,
                "tasks": ["adventure", "rules"],
                "exclusion_reason": None,
            },
            {
                "pdf_page": 2,
                "tasks": [],
                "exclusion_reason": "non-operational-illustration",
            },
            {
                "pdf_page": 3,
                "tasks": ["items"],
                "exclusion_reason": None,
            },
            {
                "pdf_page": 4,
                "tasks": [],
                "exclusion_reason": "divider",
            },
            {
                "pdf_page": 5,
                "tasks": ["tables"],
                "exclusion_reason": None,
            },
        ]
        groups = partition_content_pages(
            routes, {page: 1024 for page in range(1, 6)}
        )
        self.assertEqual(
            [[row["pdf_page"] for row in group] for group in groups],
            [[1, 2, 3], [5]],
        )
        self.assertEqual(groups[0][0]["tasks"], ["adventure", "rules"])
        self.assertEqual(groups[0][1]["tasks"], [])

    def test_content_partition_uses_page_and_soft_text_limits(self) -> None:
        routes = [
            {
                "pdf_page": page,
                "tasks": ["rules"],
                "exclusion_reason": None,
            }
            for page in range(1, 11)
        ]
        groups = partition_content_pages(
            routes,
            {
                1: 8 * 1024,
                2: 8 * 1024,
                3: 16 * 1024,
                **{page: 1024 for page in range(4, 11)},
            },
        )
        self.assertEqual(
            [[row["pdf_page"] for row in group] for group in groups],
            [[1, 2], list(range(3, 11))],
        )
        page_limited_routes = [
            {
                "pdf_page": page,
                "tasks": ["rules"],
                "exclusion_reason": None,
            }
            for page in range(1, 18)
        ]
        self.assertEqual(
            [
                len(group)
                for group in partition_content_pages(
                    page_limited_routes,
                    {page: 1 for page in range(1, 18)},
                )
            ],
            [8, 8, 1],
        )

    def test_map_partition_uses_render_budget_not_contiguity(self) -> None:
        mib = 1024 * 1024
        self.assertEqual(
            partition_map_pages(
                [1, 4, 9, 12],
                {1: 5 * mib, 4: 5 * mib, 9: 5 * mib, 12: 5 * mib},
            ),
            [[1, 4, 9], [12]],
        )
        pages = list(range(1, 23))
        self.assertEqual(
            [len(group) for group in partition_map_pages(
                pages, {page: 1 for page in pages}
            )],
            [20, 2],
        )
        self.assertEqual(
            partition_map_pages([3], {3: 17 * mib}), [[3]]
        )

    def test_human_pack_instructions_are_module_neutral(self) -> None:
        identity = source(page_count=2)
        identity["title"] = "Winter Example"
        routing_readme = routing_pack_readme(identity)
        focused_readme = focused_pack_readme(
            identity,
            "content.001",
            "content",
            [1, 2],
            tasks=["rules", "tables"],
        )
        for value in (routing_readme, focused_readme):
            self.assertIn("prompt.md", value)
            self.assertIn("Open the attached ZIP", value)
            self.assertNotIn("Lair", value)
        self.assertIn("content.001.zip", focused_readme)
        self.assertIn("content.001.json", focused_readme)

    def test_new_routing_and_focused_archives_are_self_describing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / "source.pdf"
            pdf.write_bytes(b"synthetic pdf")
            input_dir = root / "module-input"
            exchange_dir = root / "_exchange"
            cache_dir = root / ".module-extractor-cache"

            def fake_poppler(arguments: list[str]) -> mock.Mock:
                if arguments[0] == "pdftotext":
                    Path(arguments[-1]).write_text(
                        "Visible page text\f", encoding="utf-8"
                    )
                elif arguments[0] == "pdftoppm":
                    prefix = Path(arguments[-1])
                    (prefix.parent / f"{prefix.name}-1.png").write_bytes(b"png")
                return mock.Mock(returncode=0, stdout="", stderr="")

            with (
                mock.patch(
                    "module_extractor.preparation.shutil.which",
                    return_value="/usr/bin/tool",
                ),
                mock.patch(
                    "module_extractor.preparation._pdf_info",
                    return_value={"pdf_pages": 1, "pdf_title": ""},
                ),
                mock.patch(
                    "module_extractor.preparation._run",
                    side_effect=fake_poppler,
                ),
            ):
                exchange = prepare(
                    pdf,
                    slug="winter-example",
                    title="Winter Example",
                    input_dir=input_dir,
                    exchange_dir=exchange_dir,
                    cache_dir=cache_dir,
                )
                (input_dir / "stale.json").write_text(
                    "{}", encoding="utf-8"
                )
                (exchange_dir / "stale.zip").write_bytes(b"stale")
                (cache_dir / "stale.txt").write_text(
                    "stale", encoding="utf-8"
                )
                exchange = prepare(
                    pdf,
                    slug="winter-example",
                    title="Winter Example",
                    input_dir=input_dir,
                    exchange_dir=exchange_dir,
                    cache_dir=cache_dir,
                )
                self.assertFalse((input_dir / "stale.json").exists())
                self.assertFalse((exchange_dir / "stale.zip").exists())
                self.assertFalse((cache_dir / "stale.txt").exists())
                with self.assertRaisesRegex(
                    ExtractorError, "belongs to slug"
                ):
                    prepare(
                        pdf,
                        slug="different-example",
                        title="Different Example",
                        input_dir=input_dir,
                        exchange_dir=exchange_dir,
                        cache_dir=cache_dir,
                    )

            self.assertEqual(exchange, exchange_dir)
            with zipfile.ZipFile(exchange / "routing.zip") as archive:
                self.assertIn("README.md", archive.namelist())
                self.assertIn("prompt.md", archive.namelist())
                self.assertNotIn("prompt.txt", archive.namelist())
                self.assertIn(
                    "Open the attached ZIP",
                    archive.read("README.md").decode("utf-8"),
                )

            prepared = json.loads(
                (cache_dir / "prepared.json").read_text(encoding="utf-8")
            )
            identity = json.loads(
                (input_dir / "source.json").read_text(encoding="utf-8")
            )
            self.assertEqual(identity["slug"], "winter-example")
            routes = [
                {
                    "pdf_page": 1,
                    "tasks": ["maps", "rules"],
                    "exclusion_reason": None,
                    "confidence": "high",
                    "notes": "",
                }
            ]
            preserved = cache_dir / "map-renders" / "page-0001.png"
            preserved.parent.mkdir(parents=True)
            preserved.write_bytes(b"map")
            packs = create_focused_packs(
                input_dir,
                identity,
                prepared,
                routes,
                asset_base_dir=cache_dir,
                archive_dir=exchange_dir,
                render_dir=cache_dir / "map-renders",
            )
            first_bytes = {
                pack["pack_id"]: (input_dir / pack["archive_path"]).read_bytes()
                for pack in packs
            }
            packs = create_focused_packs(
                input_dir,
                identity,
                prepared,
                routes,
                asset_base_dir=cache_dir,
                archive_dir=exchange_dir,
                render_dir=cache_dir / "map-renders",
            )
            self.assertEqual(
                first_bytes,
                {
                    pack["pack_id"]: (
                        input_dir / pack["archive_path"]
                    ).read_bytes()
                    for pack in packs
                },
            )
            for pack in packs:
                with zipfile.ZipFile(
                    input_dir / pack["archive_path"]
                ) as archive:
                    self.assertIn("README.md", archive.namelist())
                    self.assertIn("prompt.md", archive.namelist())
                    self.assertNotIn("prompt.txt", archive.namelist())
                    readme = archive.read("README.md").decode("utf-8")
                    self.assertIn(pack["pack_id"], readme)
                    self.assertIn(f"{pack['pack_id']}.json", readme)
                    if pack["task"] == "content":
                        prompt = archive.read("prompt.md").decode("utf-8")
                        self.assertIn("Task-to-record mapping", prompt)
                        template = json.loads(
                            archive.read("response-template.json")
                        )
                        self.assertEqual(template["task"], "content")
                        self.assertEqual(
                            {
                                (row["pdf_page"], row["task"])
                                for row in template["task_coverage"]
                            },
                            {(1, "rules")},
                        )


class ContractTests(unittest.TestCase):
    def test_every_typed_record_contract(self) -> None:
        task_for_type = {
            "location": "adventure",
            "actor": "adventure",
            "situation": "adventure",
            "procedure": "adventure",
            "knowledge": "adventure",
            "rule": "rules",
            "table": "tables",
            "item": "items",
            "spell": "spells",
            "class": "classes",
            "effect": "effects",
        }
        for record_type in sorted(RECORD_TYPES):
            task = task_for_type[record_type]
            pack = content_pack(tasks=[task])
            record = {
                "id": f"{record_type}.example",
                "record_type": record_type,
                "fields": required_fields(record_type),
                "source_pages": [1],
                "confidence": "high",
                "references": [],
                "uncertainties": [],
            }
            response = content_response(pack, [record], task=task)
            self.assertEqual(
                validate_content_response(response, pack, source())[0][
                    "record_type"
                ],
                record_type,
            )

    def test_duplicate_unsafe_and_missing_fields_fail(self) -> None:
        pack = content_pack()
        record = {
            "id": "rule.example",
            "record_type": "rule",
            "fields": {"title": "Example", "text": "Text"},
            "source_pages": [1],
            "confidence": "high",
            "references": [],
            "uncertainties": [],
        }
        response = content_response(pack, [record, deepcopy(record)])
        with self.assertRaisesRegex(ExtractorError, "duplicate record IDs"):
            validate_content_response(response, pack, source())
        response["records"] = [{**record, "id": "../unsafe"}]
        with self.assertRaisesRegex(ExtractorError, "safe stable ID"):
            validate_content_response(response, pack, source())
        broken = deepcopy(record)
        del broken["fields"]["text"]
        response["records"] = [broken]
        with self.assertRaisesRegex(ExtractorError, "text is required"):
            validate_content_response(response, pack, source())

    def test_task_coverage_is_exact_and_typed(self) -> None:
        pack = content_pack(tasks=["items", "rules"])
        records = [
            {
                "id": "rule.example",
                "record_type": "rule",
                "fields": {"title": "Rule", "text": "Text"},
                "source_pages": [1],
                "confidence": "high",
                "references": [],
                "uncertainties": [],
            },
            {
                "id": "item.example",
                "record_type": "item",
                "fields": {"title": "Item", "text": "Text"},
                "source_pages": [1],
                "confidence": "high",
                "references": [],
                "uncertainties": [],
            },
        ]
        response = {
            "schema": CONTENT_SCHEMA,
            "source_sha256": "a" * 64,
            "pack_id": pack["pack_id"],
            "task": "content",
            "task_coverage": [
                {
                    "pdf_page": 1,
                    "task": "rules",
                    "status": "extracted",
                    "record_ids": ["rule.example"],
                    "notes": "",
                },
                {
                    "pdf_page": 1,
                    "task": "items",
                    "status": "extracted",
                    "record_ids": ["item.example"],
                    "notes": "",
                },
            ],
            "records": records,
        }
        self.assertEqual(
            len(validate_content_response(response, pack, source())), 2
        )
        response["task_coverage"].pop()
        with self.assertRaisesRegex(ExtractorError, "missing task coverage"):
            validate_content_response(response, pack, source())
        response["task_coverage"].append(
            {
                "pdf_page": 1,
                "task": "items",
                "status": "extracted",
                "record_ids": ["rule.example"],
                "notes": "",
            }
        )
        with self.assertRaisesRegex(ExtractorError, "incompatible type"):
            validate_content_response(response, pack, source())

    def test_not_found_requires_notes_and_blocks_coverage(self) -> None:
        pack = content_pack()
        record = {
            "id": "rule.other",
            "record_type": "rule",
            "fields": {"title": "Other", "text": "Text"},
            "source_pages": [1],
            "confidence": "high",
            "references": [],
            "uncertainties": [],
        }
        response = content_response(pack, [record])
        response["task_coverage"][0] = {
            "pdf_page": 1,
            "task": "rules",
            "status": "not-found",
            "record_ids": [],
            "notes": "Routing appears mistaken.",
        }
        response["records"] = []
        self.assertEqual(validate_content_response(response, pack, source()), [])
        response["task_coverage"][0]["notes"] = ""
        with self.assertRaisesRegex(ExtractorError, "needs notes"):
            validate_content_response(response, pack, source())

    def test_pack_manifest_accepts_noncontiguous_size_bounded_maps(self) -> None:
        pack = {
            "pack_id": "map.v1.001",
            "task": "maps",
            "physical_pages": [1, 3],
            "render_bytes": 16 * 1024 * 1024,
            "archive_path": "../_exchange/map.v1.001.zip",
            "pack_sha256": "b" * 64,
            "response_path": "responses/map.v1.001.json",
        }
        manifest = {
            "schema": "module-pack-manifest/v1",
            "source_sha256": "a" * 64,
            "packs": [pack],
        }
        self.assertEqual(
            validate_pack_manifest(manifest, source())[0]["physical_pages"],
            [1, 3],
        )
        pack["render_bytes"] += 1
        with self.assertRaisesRegex(ExtractorError, "render budget"):
            validate_pack_manifest(manifest, source())

    def test_not_found_task_coverage_is_a_release_gap(self) -> None:
        pack = {
            **content_pack(),
            "archive_path": "../_exchange/content.001.zip",
            "pack_sha256": "b" * 64,
            "response_path": "responses/content.001.json",
        }
        coverage = build_coverage(
            source(page_count=1),
            routing(page_count=1)["pages"],
            [pack],
            [
                {
                    "pack_id": "content.001",
                    "response_sha256": "c" * 64,
                    "record_ids": [],
                    "validation": "valid",
                    "task_coverage": [
                        {
                            "pdf_page": 1,
                            "task": "rules",
                            "status": "not-found",
                            "record_ids": [],
                            "notes": "Routing appears mistaken.",
                        }
                    ],
                }
            ],
        )
        self.assertFalse(coverage["complete"])
        self.assertEqual(coverage["gaps"][0]["reason"], "not-found")


class WorkspaceCliTests(unittest.TestCase):
    def test_public_help_and_advanced_command_surface(self) -> None:
        parser = cli_module.build_parser()
        top_help = parser.format_help()
        self.assertIn("{run,status,clean,advanced}", top_help)
        self.assertNotIn("prepare the workspace", top_help)
        for hidden in ("prepare", "focus", "ingest", "validate", "review", "assemble"):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                parser.parse_args([hidden])
        advanced = parser.parse_args(
            [
                "advanced",
                "validate",
                "--workspace-root",
                "/tmp/example",
            ]
        )
        self.assertIs(advanced.function, cli_module.command_validate)

    def test_run_infers_identity_and_accepts_overrides(self) -> None:
        for arguments, expected_slug, expected_title in (
            (["My Adventure.pdf"], "my-adventure", None),
            (
                [
                    "My Adventure.pdf",
                    "--slug",
                    "chosen-slug",
                    "--title",
                    "Chosen Title",
                ],
                "chosen-slug",
                "Chosen Title",
            ),
        ):
            with self.subTest(arguments=arguments):
                args = cli_module.build_parser().parse_args(
                    ["run", *arguments, "--workspace-root", "/tmp/example"]
                )
                with mock.patch.object(cli_module, "command_prepare") as called:
                    cli_module.command_run(args)
                prepared = called.call_args.args[0]
                self.assertEqual(prepared.slug, expected_slug)
                self.assertEqual(prepared.title, expected_title)
        args = cli_module.build_parser().parse_args(
            ["run", "日本語.pdf", "--workspace-root", "/tmp/example"]
        )
        with self.assertRaisesRegex(ExtractorError, "provide --slug"):
            cli_module.command_run(args)

    def test_preparation_title_metadata_and_filename_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / "My_Adventure.pdf"
            pdf.write_bytes(b"synthetic pdf")

            def fake_poppler(arguments: list[str]) -> mock.Mock:
                if arguments[0] == "pdftotext":
                    Path(arguments[-1]).write_text("Text\f", encoding="utf-8")
                elif arguments[0] == "pdftoppm":
                    prefix = Path(arguments[-1])
                    (prefix.parent / f"{prefix.name}-1.png").write_bytes(b"png")
                return mock.Mock(returncode=0, stdout="", stderr="")

            with (
                mock.patch(
                    "module_extractor.preparation.shutil.which",
                    return_value="/usr/bin/tool",
                ),
                mock.patch(
                    "module_extractor.preparation._run",
                    side_effect=fake_poppler,
                ),
                mock.patch(
                    "module_extractor.preparation._pdf_info",
                    return_value={
                        "pdf_pages": 1,
                        "pdf_title": "Metadata Title",
                    },
                ),
            ):
                prepare(
                    pdf,
                    slug="my-adventure",
                    title=None,
                    input_dir=root / "module-input",
                    exchange_dir=root / "_exchange",
                    cache_dir=root / ".module-extractor-cache",
                )
            saved = json.loads(
                (root / "module-input" / "source.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(saved["title"], "Metadata Title")

            with (
                mock.patch(
                    "module_extractor.preparation.shutil.which",
                    return_value="/usr/bin/tool",
                ),
                mock.patch(
                    "module_extractor.preparation._run",
                    side_effect=fake_poppler,
                ),
                mock.patch(
                    "module_extractor.preparation._pdf_info",
                    return_value={"pdf_pages": 1, "pdf_title": "  "},
                ),
            ):
                prepare(
                    pdf,
                    slug="my-adventure",
                    title=None,
                    input_dir=root / "module-input",
                    exchange_dir=root / "_exchange",
                    cache_dir=root / ".module-extractor-cache",
                )
            saved = json.loads(
                (root / "module-input" / "source.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(saved["title"], "My Adventure")

    def test_state_detection_waits_normally_for_routing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            module_input = root / "module-input"
            module_input.mkdir()
            identity = {**source(page_count=1), "slug": "test"}
            (module_input / "source.json").write_text(
                json.dumps(identity), encoding="utf-8"
            )
            workspace = cli_module.Workspace(
                root,
                module_input,
                root / "_exchange",
                root / ".module-extractor-cache",
                root / "module",
            )
            state = cli_module.inspect_workspace(workspace)
            self.assertEqual(state["stage"], "waiting-for-routing")
            self.assertEqual(state["missing_responses"], ["routing.json"])
            args = argparse.Namespace(
                pdf=None,
                slug=None,
                title=None,
                workspace_root=str(root),
            )
            output = io.StringIO()
            with redirect_stdout(output):
                cli_module.command_run(args)
            self.assertIn("Waiting for `_exchange/routing.json`", output.getvalue())

    def test_run_partially_ingests_and_names_rejected_response(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            module_input = root / "module-input"
            exchange = root / "_exchange"
            module_input.mkdir()
            exchange.mkdir()
            identity = {**source(page_count=2), "slug": "test"}
            route = routing(page_count=2)
            packs = []
            for index in (1, 2):
                pack_id = f"content.{index:03d}"
                archive = exchange / f"{pack_id}.zip"
                archive.write_bytes(f"pack {index}".encode())
                packs.append(
                    {
                        **content_pack(pages=[index], pack_id=pack_id),
                        "archive_path": f"../_exchange/{pack_id}.zip",
                        "pack_sha256": sha256_file(archive),
                        "response_path": f"responses/{pack_id}.json",
                    }
                )
            for name, value in (
                ("source.json", identity),
                ("routing.json", route),
                (
                    "packs.json",
                    {
                        "schema": "module-pack-manifest/v1",
                        "source_sha256": identity["sha256"],
                        "packs": packs,
                    },
                ),
            ):
                (module_input / name).write_text(
                    json.dumps(value), encoding="utf-8"
                )
            record = {
                "id": "rule.example",
                "record_type": "rule",
                "fields": {"title": "Example", "text": "Text"},
                "source_pages": [1],
                "confidence": "high",
                "references": [],
                "uncertainties": [],
            }
            response = content_response(packs[0], [record])
            (exchange / "content.001.json").write_text(
                json.dumps(response), encoding="utf-8"
            )
            args = argparse.Namespace(
                pdf=None,
                slug=None,
                title=None,
                workspace_root=str(root),
            )
            output = io.StringIO()
            with redirect_stdout(output):
                cli_module.command_run(args)
            self.assertTrue(
                (module_input / "responses" / "content.001.json").is_file()
            )
            self.assertIn("content.002.json", output.getvalue())

            (exchange / "content.002.json").write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(
                ExtractorError,
                r"Rejected _exchange/content\.002\.json.*content\.002\.zip",
            ):
                cli_module.command_run(args)

    def test_refocus_preserves_review_only_for_the_exact_pack_set(self) -> None:
        for changed in (False, True):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                module_input = root / "module-input"
                exchange = root / "_exchange"
                cache = root / ".module-extractor-cache"
                module_input.mkdir()
                exchange.mkdir()
                cache.mkdir()
                identity = source(page_count=1)
                route = routing(page_count=1)
                old_pack = {
                    **content_pack(),
                    "archive_path": "../_exchange/content.001.zip",
                    "pack_sha256": "1" * 64,
                    "response_path": "responses/content.001.json",
                }
                record = {
                    "id": "rule.example",
                    "record_type": "rule",
                    "fields": {"title": "Example", "text": "Rule text."},
                    "source_pages": [1],
                    "confidence": "high",
                    "references": [],
                    "uncertainties": [],
                }
                response = content_response(old_pack, [record])
                exchange_response = exchange / "content.001.json"
                exchange_response.write_text(
                    json.dumps(response), encoding="utf-8"
                )
                ingested_response = (
                    module_input / "responses" / "content.001.json"
                )
                ingested_response.parent.mkdir()
                ingested_response.write_text(
                    json.dumps(response), encoding="utf-8"
                )
                old_pack["ingested_response_sha256"] = sha256_file(
                    ingested_response
                )
                new_pack = {
                    **old_pack,
                    "pack_sha256": ("2" * 64 if changed else "1" * 64),
                }
                new_pack.pop("ingested_response_sha256", None)
                (module_input / "source.json").write_text(
                    json.dumps(identity), encoding="utf-8"
                )
                (module_input / "packs.json").write_text(
                    json.dumps(
                        {
                            "schema": "module-pack-manifest/v1",
                            "source_sha256": identity["sha256"],
                            "packs": [old_pack],
                        }
                    ),
                    encoding="utf-8",
                )
                review = {
                    "schema": REVIEW_SCHEMA,
                    "source_sha256": identity["sha256"],
                    "aliases": [],
                    "values": [],
                    "accepted_uncertainties": [],
                    "notes": "keep only for identical packs",
                }
                (module_input / "review.json").write_text(
                    json.dumps(review), encoding="utf-8"
                )
                (exchange / "routing.json").write_text(
                    json.dumps(route), encoding="utf-8"
                )
                (exchange / "routing.zip").write_bytes(b"routing")
                (cache / "prepared.json").write_text(
                    json.dumps({"asset_root": "."}), encoding="utf-8"
                )
                args = argparse.Namespace(
                    workspace_root=str(root),
                    routing=None,
                )
                with (
                    mock.patch.object(
                        cli_module,
                        "create_focused_packs",
                        return_value=[new_pack],
                    ),
                    redirect_stdout(io.StringIO()),
                    redirect_stderr(io.StringIO()),
                ):
                    cli_module.command_focus(args)
                self.assertEqual(
                    (module_input / "review.json").is_file(), not changed
                )
                self.assertEqual(
                    (exchange / "content.001.json").is_file(), not changed
                )
                self.assertEqual(
                    (
                        module_input / "responses" / "content.001.json"
                    ).is_file(),
                    not changed,
                )
                checked_pack = json.loads(
                    (module_input / "packs.json").read_text(encoding="utf-8")
                )["packs"][0]
                self.assertEqual(
                    "ingested_response_sha256" in checked_pack,
                    not changed,
                )

    def test_refocus_generation_failure_leaves_workspace_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            module_input = root / "module-input"
            exchange = root / "_exchange"
            cache = root / ".module-extractor-cache"
            module_input.mkdir()
            exchange.mkdir()
            cache.mkdir()
            identity = source(page_count=1)
            (module_input / "source.json").write_text(
                json.dumps(identity), encoding="utf-8"
            )
            (module_input / "keep.txt").write_text("input", encoding="utf-8")
            (exchange / "routing.json").write_text(
                json.dumps(routing(page_count=1)), encoding="utf-8"
            )
            (exchange / "keep.txt").write_text("exchange", encoding="utf-8")
            (cache / "prepared.json").write_text(
                json.dumps({"asset_root": "."}), encoding="utf-8"
            )
            (cache / "keep.txt").write_text("cache", encoding="utf-8")
            args = argparse.Namespace(workspace_root=str(root), routing=None)
            with mock.patch.object(
                cli_module,
                "create_focused_packs",
                side_effect=ExtractorError("synthetic generation failure"),
            ):
                with self.assertRaisesRegex(
                    ExtractorError, "synthetic generation failure"
                ):
                    cli_module.command_focus(args)
            self.assertEqual(
                (module_input / "keep.txt").read_text(encoding="utf-8"),
                "input",
            )
            self.assertEqual(
                (exchange / "keep.txt").read_text(encoding="utf-8"),
                "exchange",
            )
            self.assertEqual(
                (cache / "keep.txt").read_text(encoding="utf-8"), "cache"
            )

    def test_flat_exchange_ingest_clean_and_release(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / "source.pdf"
            pdf.write_bytes(b"synthetic pdf")

            def fake_poppler(arguments: list[str]) -> mock.Mock:
                if arguments[0] == "pdftotext":
                    Path(arguments[-1]).write_text(
                        "Visible page text\f", encoding="utf-8"
                    )
                elif arguments[0] == "pdftoppm":
                    prefix = Path(arguments[-1])
                    (prefix.parent / f"{prefix.name}-1.png").write_bytes(b"png")
                return mock.Mock(returncode=0, stdout="", stderr="")

            prepare_args = argparse.Namespace(
                pdf=str(pdf),
                slug="example-adventure",
                title="Example Adventure",
                workspace_root=str(root),
            )
            with (
                mock.patch(
                    "module_extractor.preparation.shutil.which",
                    return_value="/usr/bin/tool",
                ),
                mock.patch(
                    "module_extractor.preparation._pdf_info",
                    return_value={"pdf_pages": 1, "pdf_title": ""},
                ),
                mock.patch(
                    "module_extractor.preparation._run",
                    side_effect=fake_poppler,
                ),
                redirect_stdout(io.StringIO()),
                redirect_stderr(io.StringIO()),
            ):
                cli_module.command_prepare(prepare_args)

            exchange = root / "_exchange"
            module_input = root / "module-input"
            self.assertTrue((exchange / "routing.zip").is_file())
            identity = json.loads(
                (module_input / "source.json").read_text(encoding="utf-8")
            )
            route = routing(page_count=1)
            route["source_sha256"] = identity["sha256"]
            route["pages"][0]["tasks"] = ["adventure"]
            (exchange / "routing.json").write_text(
                json.dumps(route), encoding="utf-8"
            )
            focus_args = argparse.Namespace(
                workspace_root=str(root),
                routing=None,
            )
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                cli_module.command_focus(focus_args)

            pack_id = "content.001"
            self.assertTrue((exchange / f"{pack_id}.zip").is_file())
            pack = content_pack(
                pack_id=pack_id, tasks=["adventure"]
            )
            record = {
                "id": "location.example-gate",
                "record_type": "location",
                "fields": {
                    "title": "Example Gate",
                    "first_impression": "A synthetic adventure location.",
                    "topology_node": None,
                },
                "source_pages": [1],
                "confidence": "high",
                "references": [],
                "uncertainties": [],
            }
            response = content_response(pack, [record], task="adventure")
            response["source_sha256"] = identity["sha256"]
            (exchange / f"{pack_id}.json").write_text(
                json.dumps(response), encoding="utf-8"
            )
            workspace_args = argparse.Namespace(workspace_root=str(root))
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                cli_module.command_ingest(workspace_args)
                cli_module.command_clean(workspace_args)

            self.assertFalse(exchange.exists())
            self.assertFalse((root / ".module-extractor-cache").exists())
            self.assertTrue(
                (module_input / "responses" / f"{pack_id}.json").is_file()
            )
            run_args = argparse.Namespace(
                pdf=None,
                slug=None,
                title=None,
                workspace_root=str(root),
            )
            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(io.StringIO()):
                cli_module.command_run(run_args)
            assembled = root / "module"
            self.assertTrue((assembled / "audit" / "module.json").is_file())
            self.assertTrue((assembled / "MODULE.md").is_file())
            self.assertIn("Release assembled", output.getvalue())
            first_hash = content_tree_hash(assembled)
            self.assertTrue(_replaceable_output(assembled))

            duplicate = root / "second-module"
            assemble(module_input, duplicate, profile="release")
            self.assertEqual(first_hash, content_tree_hash(duplicate))

            def fail_after_partial_render(stage: Path, module: dict) -> None:
                stage.mkdir(parents=True)
                (stage / "partial.txt").write_text(
                    "incomplete", encoding="utf-8"
                )
                raise ExtractorError("synthetic rendering failure")

            with (
                mock.patch.object(
                    assembly_module,
                    "render_module",
                    side_effect=fail_after_partial_render,
                ),
                self.assertRaisesRegex(
                    ExtractorError, "synthetic rendering failure"
                ),
            ):
                assemble(
                    module_input,
                    assembled,
                    profile="release",
                    replace_generated_output=True,
                )
            self.assertEqual(first_hash, content_tree_hash(assembled))

            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(io.StringIO()):
                cli_module.command_run(run_args)
            self.assertIn("already assembled", output.getvalue())


class ReconciliationTests(unittest.TestCase):
    def test_record_order_cannot_change_reconciliation(self) -> None:
        values = [
            observation("observation.one", "rule.test", {"title": "T", "text": "A"}),
            observation(
                "observation.two",
                "rule.test",
                {"title": "T", "text": "A"},
                pack_id="content.rules.002",
            ),
        ]
        self.assertEqual(reconcile_records(values), reconcile_records(values[::-1]))

    def test_review_aliases_group_observations_before_reconciliation(self) -> None:
        evidence = {
            "content_observations": [
                observation(
                    "observation.one",
                    "rule.alias",
                    {"title": "T", "text": "A"},
                ),
                observation(
                    "observation.two",
                    "rule.canonical",
                    {"title": "T", "text": "A"},
                ),
            ],
            "map_results": [],
            "uncertainties": [],
        }
        review = {
            "aliases": [
                {
                    "alias": "rule.alias",
                    "target_id": "rule.canonical",
                }
            ]
        }
        rewritten = canonicalize_evidence_aliases(evidence, review)
        records, conflicts = reconcile_records(rewritten["content_observations"])
        self.assertEqual(conflicts, [])
        self.assertEqual([record["id"] for record in records], ["rule.canonical"])
        self.assertEqual(len(records[0]["observation_ids"]), 2)

    def test_unknown_topology_facets_make_no_assertion(self) -> None:
        concrete = map_result(
            "map-001",
            {"kind": "corridor", "traversal_direction": "both"},
        )
        unknown = map_result("map-002", {}, reverse=True)
        topology, conflicts = reconcile_topology([unknown, concrete])
        self.assertEqual(conflicts, [])
        self.assertEqual(
            topology["passages"][0]["facets"]["kind"], "corridor"
        )
        self.assertEqual(
            topology["passages"][0]["facets"]["traversal_direction"], "both"
        )

    def test_compound_facets_do_not_overload_doors(self) -> None:
        corridor = map_result("map-001", {"kind": "corridor"})
        door = map_result("map-002", {"barriers": ["door"]})
        topology, conflicts = reconcile_topology([corridor, door])
        self.assertEqual(conflicts, [])
        self.assertEqual(
            topology["passages"][0]["facets"],
            {
                "kind": "corridor",
                "barriers": ["door"],
                "features": [],
                "conditions": [],
                "hazards": [],
            },
        )

    def test_incompatible_concrete_facets_remain_conflicts(self) -> None:
        first = map_result("map-001", {"kind": "corridor"})
        second = map_result("map-002", {"kind": "transport ward"})
        topology, conflicts = reconcile_topology([second, first])
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["field"], "kind")
        self.assertNotIn("kind", topology["passages"][0]["facets"])

    def test_exotic_connection_conditions_merge_without_losing_provenance(self) -> None:
        hatch = map_result(
            "map-001",
            {
                "kind": "airlock hatch",
                "medium": "vacuum",
                "elevation": "variable",
                "barriers": ["sealed hatch"],
                "features": ["pressure chamber"],
                "conditions": ["pressure must be equalized"],
                "traversal_direction": "conditional",
            },
        )
        second = map_result(
            "map-002",
            {
                "conditions": ["requires ship power"],
                "features": ["warning beacon"],
            },
        )
        topology, conflicts = reconcile_topology([second, hatch])
        self.assertEqual(conflicts, [])
        passage = topology["passages"][0]
        self.assertEqual(passage["facets"]["kind"], "airlock hatch")
        self.assertEqual(passage["facets"]["medium"], "vacuum")
        self.assertEqual(
            passage["facets"]["conditions"],
            ["pressure must be equalized", "requires ship power"],
        )
        self.assertEqual(
            [item["pack_id"] for item in passage["facet_observations"]["conditions"]],
            ["map-001", "map-002"],
        )


class ReviewAndGateTests(unittest.TestCase):
    def _records_topology(self):
        records, record_conflicts = reconcile_records(
            [
                observation(
                    "observation.one",
                    "rule.test",
                    {"title": "Test", "text": "One"},
                ),
                observation(
                    "observation.two",
                    "rule.test",
                    {"title": "Test", "text": "Two"},
                    pack_id="content.rules.002",
                ),
            ]
        )
        topology, topology_conflicts = reconcile_topology(
            [map_result("map-001", {"kind": "corridor"})]
        )
        return records, topology, record_conflicts + topology_conflicts

    def test_review_resolves_fields_and_accepts_uncertainty(self) -> None:
        records, topology, conflicts = self._records_topology()
        uncertainty = {
            "id": "uncertainty.test.001",
            "target_id": "rule.test",
            "description": "Test uncertainty",
            "source_pages": [1],
        }
        review = {
            "schema": REVIEW_SCHEMA,
            "source_sha256": "a" * 64,
            "aliases": [],
            "values": [
                {
                    "object_id": "rule.test",
                    "field": "text",
                    "value": "One",
                    "source_pages": [1],
                    "rationale": "Source-backed selection.",
                }
            ],
            "accepted_uncertainties": [
                {
                    "uncertainty_id": "uncertainty.test.001",
                    "source_pages": [1],
                    "rationale": "Bounded ambiguity.",
                }
            ],
            "notes": "",
        }
        checked = validate_review(review, source())
        result = apply_review(records, topology, conflicts, [uncertainty], checked)
        self.assertEqual(result["records"][0]["fields"]["text"], "One")
        self.assertEqual(result["unresolved_conflicts"], [])
        self.assertEqual(result["pending_uncertainties"], [])

    def test_ambiguous_aliases_are_preserved_for_gate_analysis(self) -> None:
        review = {
            "schema": REVIEW_SCHEMA,
            "source_sha256": "a" * 64,
            "aliases": [
                {
                    "alias": "rule.alias",
                    "target_id": "rule.test",
                    "source_pages": [1],
                    "rationale": "Same rule.",
                },
                {
                    "alias": "rule.alias",
                    "target_id": "rule.other",
                    "source_pages": [1],
                    "rationale": "Conflicting target.",
                },
            ],
            "values": [],
            "accepted_uncertainties": [],
            "notes": "",
        }
        checked_ambiguous = validate_review(review, source())
        self.assertEqual(len(checked_ambiguous["aliases"]), 2)
        records, topology, conflicts = self._records_topology()
        checked = validate_review(
            {
                **review,
                "aliases": [
                    {
                        "alias": "rule.alias-a",
                        "target_id": "rule.alias-b",
                        "source_pages": [1],
                        "rationale": "Cycle.",
                    },
                    {
                        "alias": "rule.alias-b",
                        "target_id": "rule.alias-a",
                        "source_pages": [1],
                        "rationale": "Cycle.",
                    },
                ],
            },
            source(),
        )
        with self.assertRaisesRegex(ExtractorError, "alias cycle"):
            apply_review(records, topology, conflicts, [], checked)

    def test_release_gate_reports_required_fields_refs_and_gaps(self) -> None:
        reviewed = {
            "records": [
                {
                    "id": "rule.test",
                    "record_type": "rule",
                    "fields": {"title": "Test"},
                    "references": ["rule.missing"],
                }
            ],
            "topology": {"nodes": [], "passages": []},
            "unresolved_conflicts": [{"id": "conflict.test"}],
            "pending_uncertainties": [{"id": "uncertainty.test"}],
        }
        errors = release_gate(reviewed, {"complete": False})
        self.assertIn("coverage is incomplete", errors)
        self.assertTrue(any("missing required field text" in item for item in errors))
        self.assertTrue(any("references missing ID" in item for item in errors))

    def test_review_command_creates_inert_queue_and_preserves_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "module-input"
            exchange = root / "_exchange"
            run.mkdir()
            exchange.mkdir()
            (run / "source.json").write_text(
                json.dumps({"sha256": "a" * 64}), encoding="utf-8"
            )
            conflict = {
                "id": "conflict.rule-example.text",
                "object_id": "rule.example",
                "field": "text",
                "values": ["First", "Second"],
            }
            map_conflict = {
                "id": "conflict.edge-area-a-area-b.kind",
                "object_id": "edge-area-a-area-b",
                "field": "kind",
                "values": ["doorway", "portal"],
            }
            uncertainty = {
                "id": "uncertainty.content.rules.001.001",
                "target_id": "rule.example",
                "target_kind": "record",
                "target_observation_id": "observation.one",
                "description": "The timing is unclear.",
                "source_pages": [1],
                "pack_id": "content.rules.001",
            }
            evaluated = {
                "source": {"sha256": "a" * 64},
                "gate_errors": [
                    "coverage is incomplete",
                    "2 blocking conflicts remain",
                ],
                "coverage": {
                    "gaps": [
                        {
                            "pdf_page": 1,
                            "task": "rules",
                            "reason": "not-found",
                        }
                    ]
                },
                "packs": [
                    {
                        "pack_id": "content.001",
                        "task": "content",
                        "tasks": ["rules"],
                        "physical_pages": [1],
                    }
                ],
                "reviewed": {
                    "unresolved_conflicts": [conflict, map_conflict],
                    "pending_uncertainties": [uncertainty],
                },
                "raw_records": [
                    {
                        "id": "rule.example",
                        "field_observations": {
                            "text": [
                                {
                                    "value": "First",
                                    "source_pages": [1],
                                    "confidence": "high",
                                    "pack_id": "content.001",
                                    "observation_id": "observation.one",
                                },
                                {
                                    "value": "Second",
                                    "source_pages": [2],
                                    "confidence": "medium",
                                    "pack_id": "content.002",
                                    "observation_id": "observation.two",
                                },
                            ]
                        },
                    }
                ],
                "raw_topology": {
                    "nodes": [
                        {
                            "id": "area-a",
                            "labels": ["A"],
                            "titles": ["Atrium"],
                            "source_pages": [3],
                        },
                        {
                            "id": "area-b",
                            "labels": ["B"],
                            "titles": ["Beyond"],
                            "source_pages": [3],
                        },
                    ],
                    "passages": [
                        {
                            "id": "edge-area-a-area-b",
                            "from": "area-a",
                            "to": "area-b",
                            "facet_observations": {
                                "kind": [
                                    {
                                        "value": "doorway",
                                        "source_pages": [3],
                                        "confidence": "high",
                                        "pack_id": "map.v1.001",
                                        "observation_id": "observation.map.one",
                                    },
                                    {
                                        "value": "portal",
                                        "source_pages": [3],
                                        "confidence": "medium",
                                        "pack_id": "map.v1.002",
                                        "observation_id": "observation.map.two",
                                    },
                                ]
                            },
                        }
                    ],
                },
            }
            args = argparse.Namespace(
                output=None, force=False, workspace_root=str(root)
            )
            with (
                mock.patch.object(
                    cli_module, "evaluate", return_value=evaluated
                ),
                redirect_stdout(io.StringIO()),
                redirect_stderr(io.StringIO()),
            ):
                cli_module.command_review(args)
                overlay_path = run / "review.json"
                overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
                self.assertEqual(overlay["values"], [])
                self.assertEqual(overlay["accepted_uncertainties"], [])
                queue = (exchange / "codex-task.md").read_text(
                    encoding="utf-8"
                )
                self.assertIn(conflict["id"], queue)
                self.assertIn(map_conflict["id"], queue)
                self.assertIn(uncertainty["id"], queue)
                self.assertIn('"value": "First"', queue)
                self.assertIn('"confidence": "high"', queue)
                self.assertIn(
                    "module-input/responses/content.001.json", queue
                )
                self.assertIn("Correct extraction mistakes only", queue)
                self.assertIn("coverage is incomplete", queue)
                self.assertIn("Coverage gaps", queue)
                self.assertIn("Reason: `not-found`", queue)
                self.assertIn("Neighboring topology", queue)
                self.assertIn(
                    ".module-extractor-cache/map-renders/page-0003.png",
                    queue,
                )

                overlay["notes"] = "Human decision preserved."
                overlay_path.write_text(json.dumps(overlay), encoding="utf-8")
                cli_module.command_review(args)
                preserved = json.loads(overlay_path.read_text(encoding="utf-8"))
                self.assertEqual(preserved["notes"], "Human decision preserved.")

                args.force = True
                cli_module.command_review(args)
                reset = json.loads(overlay_path.read_text(encoding="utf-8"))
                self.assertEqual(reset["notes"], "")
                self.assertEqual(reset["values"], [])


class IngestionTests(unittest.TestCase):
    def test_missing_response_and_wrong_pack_hash_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "pack.zip"
            archive.write_bytes(b"pack")
            pack = {
                **content_pack(),
                "archive_path": "pack.zip",
                "pack_sha256": "0" * 64,
                "response_path": "response.json",
            }
            with self.assertRaisesRegex(ExtractorError, "pack hash changed"):
                ingest_responses(root, [pack], source())
            pack["pack_sha256"] = sha256_file(archive)
            with self.assertRaisesRegex(ExtractorError, "response is missing"):
                ingest_responses(root, [pack], source())

    def test_exchange_ingest_survives_disposable_pack_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "module-input"
            exchange = root / "_exchange"
            run.mkdir()
            exchange.mkdir()
            pack_id = "content.001"
            archive = exchange / f"{pack_id}.zip"
            archive.write_bytes(b"pack")
            pack = {
                **content_pack(pack_id=pack_id),
                "archive_path": f"../_exchange/{pack_id}.zip",
                "pack_sha256": sha256_file(archive),
                "response_path": f"responses/{pack_id}.json",
            }
            record = {
                "id": "rule.example",
                "record_type": "rule",
                "fields": {"title": "Example", "text": "Rule text."},
                "source_pages": [1],
                "confidence": "high",
                "references": [],
                "uncertainties": [],
            }
            response = content_response(pack, [record])
            (exchange / f"{pack_id}.json").write_text(
                json.dumps(response), encoding="utf-8"
            )
            result = import_exchange_responses(
                exchange, run, [pack], source()
            )
            self.assertEqual(result["imported"], [pack_id])
            checked_pack = json.loads(
                (run / "packs.json").read_text(encoding="utf-8")
            )["packs"][0]
            self.assertIn("ingested_response_sha256", checked_pack)

            archive.unlink()
            evidence = ingest_responses(run, [checked_pack], source())
            self.assertEqual(evidence["responses"][0]["pack_id"], pack_id)

            saved = run / checked_pack["response_path"]
            saved.write_text(saved.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaisesRegex(
                ExtractorError, "response changed after ingest"
            ):
                ingest_responses(run, [checked_pack], source())

    def test_v1_map_uncertainty_targets_are_typed_and_validated(self) -> None:
        pack = {
            "pack_id": "map.v1.001",
            "task": "maps",
            "physical_pages": [1],
        }
        response = {
            "schema": MAP_SCHEMA,
            "source_sha256": "a" * 64,
            "pack_id": "map.v1.001",
            "nodes": [
                {
                    "id": "area-1",
                    "label": "1",
                    "source_pages": [1],
                    "confidence": "high",
                },
                {
                    "id": "area-2",
                    "label": "2",
                    "source_pages": [1],
                    "confidence": "high",
                },
            ],
            "passages": [
                {
                    "id": "passage-one-two",
                    "from": "area-1",
                    "to": "area-2",
                    "facets": {
                        "kind": "airlock hatch",
                        "medium": "vacuum",
                        "elevation": "variable",
                        "barriers": ["door"],
                        "features": ["pressure equalization chamber"],
                        "conditions": ["opens only after pressure equalization"],
                        "traversal_direction": "conditional",
                    },
                    "source_pages": [1],
                    "confidence": "high",
                }
            ],
            "uncertainties": [
                {
                    "target_id": "passage-one-two",
                    "description": "Door state is unclear.",
                    "source_pages": [1],
                }
            ],
        }
        result = validate_map_response(response, pack, source())
        self.assertEqual(
            result["uncertainties"][0]["target_id"], "edge-area-1-area-2"
        )
        self.assertEqual(
            result["uncertainties"][0]["target_kind"], "topology-edge"
        )
        response["uncertainties"][0]["target_id"] = "passage-missing"
        with self.assertRaisesRegex(ExtractorError, "unknown target"):
            validate_map_response(response, pack, source())
        response["uncertainties"][0]["target_id"] = "passage-one-two"
        pack["physical_pages"] = [1, 2]
        with self.assertRaisesRegex(ExtractorError, "no topology evidence"):
            validate_map_response(response, pack, source())

    def test_map_facet_errors_are_aggregated_but_structure_fails_fast(self) -> None:
        pack = {
            "pack_id": "map.v1.001",
            "task": "maps",
            "physical_pages": [1],
        }
        response = {
            "schema": MAP_SCHEMA,
            "source_sha256": "a" * 64,
            "pack_id": "map.v1.001",
            "nodes": [
                {
                    "id": "airlock",
                    "label": "Airlock",
                    "source_pages": [1],
                    "confidence": "high",
                },
                {
                    "id": "exterior",
                    "label": "Exterior",
                    "source_pages": [1],
                    "confidence": "high",
                },
            ],
            "passages": [
                {
                    "id": "hatch",
                    "from": "airlock",
                    "to": "exterior",
                    "facets": {
                        "kind": "",
                        "passage_kind": "corridor",
                        "medium": ["vacuum"],
                        "elevation": "descends",
                        "barriers": "sealed hatch",
                        "features": [],
                        "conditions": [""],
                        "traversal_direction": "only when depressurized",
                    },
                    "source_pages": [1],
                    "confidence": "high",
                }
            ],
            "uncertainties": [],
        }
        with self.assertRaises(ExtractorError) as raised:
            validate_map_response(response, pack, source())
        message = str(raised.exception)
        self.assertIn("map facet validation failed", message)
        self.assertIn("unsupported fields: passage_kind", message)
        for field in (
            "kind",
            "medium",
            "elevation",
            "barriers",
            "conditions",
            "traversal_direction",
        ):
            self.assertIn(f"facets.{field}", message)

        response["passages"][0]["to"] = "missing"
        with self.assertRaisesRegex(ExtractorError, "unknown node") as structural:
            validate_map_response(response, pack, source())
        self.assertNotIn("facet validation", str(structural.exception))

    def test_ingest_aggregates_facet_errors_across_map_packs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            exchange = root / "_exchange"
            run = root / "module-input"
            exchange.mkdir()
            run.mkdir()
            packs = []
            for number, page in enumerate((1, 2), 1):
                pack_id = f"map.v1.{number:03d}"
                archive = exchange / f"{pack_id}.zip"
                archive.write_bytes(pack_id.encode("utf-8"))
                pack = {
                    "pack_id": pack_id,
                    "task": "maps",
                    "physical_pages": [page],
                    "archive_path": f"../_exchange/{pack_id}.zip",
                    "pack_sha256": sha256_file(archive),
                    "response_path": f"responses/{pack_id}.json",
                }
                packs.append(pack)
                response = {
                    "schema": MAP_SCHEMA,
                    "source_sha256": "a" * 64,
                    "pack_id": pack_id,
                    "nodes": [
                        {
                            "id": f"area-{number}-a",
                            "label": "A",
                            "source_pages": [page],
                            "confidence": "high",
                        },
                        {
                            "id": f"area-{number}-b",
                            "label": "B",
                            "source_pages": [page],
                            "confidence": "high",
                        },
                    ],
                    "passages": [
                        {
                            "id": f"passage-{number}",
                            "from": f"area-{number}-a",
                            "to": f"area-{number}-b",
                            "facets": {
                                "kind": "path",
                                "medium": "ground",
                                "elevation": "sideways",
                                "barriers": [],
                                "features": [],
                                "conditions": [],
                                "traversal_direction": "sometimes",
                            },
                            "source_pages": [page],
                            "confidence": "high",
                        }
                    ],
                    "uncertainties": [],
                }
                (exchange / f"{pack_id}.json").write_text(
                    json.dumps(response), encoding="utf-8"
                )
            with self.assertRaises(ExtractorError) as raised:
                import_exchange_responses(
                    exchange, run, packs, source(page_count=2)
                )
            message = str(raised.exception)
            self.assertIn("map.v1.001.passages[0].facets.elevation", message)
            self.assertIn(
                "map.v1.002.passages[0].facets.traversal_direction",
                message,
            )
            self.assertFalse((run / "responses").exists())


class EndToEndTests(unittest.TestCase):
    def test_runtime_output_contract_is_compact_routed_and_auditable(self) -> None:
        record_types = (
            "location",
            "actor",
            "situation",
            "knowledge",
            "procedure",
            "rule",
            "table",
            "item",
            "spell",
            "class",
            "effect",
        )
        records = []
        for record_type in record_types:
            fields = required_fields(record_type)
            fields["title"] = f"{record_type.title()} Example"
            if record_type == "location":
                fields["topology_node"] = "place.gate"
            identifier = (
                "place.gate"
                if record_type == "location"
                else f"{record_type}.example"
            )
            records.append(
                {
                    "id": identifier,
                    "record_type": record_type,
                    "fields": fields,
                    "source_pages": [1],
                    "references": [],
                    "field_observations": {
                        "title": [
                            {
                                "pack_id": "content.001",
                                "confidence": "high",
                            }
                        ]
                    },
                    "observation_ids": [f"observation.{record_type}"],
                }
            )
        module = rendered_module(records)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first"
            second = root / "second"
            render_module(first, module)
            validate_rendered_module(first, module)
            render_module(second, module)
            validate_rendered_module(second, module)

            expected_directories = {
                "location": "places",
                "actor": "actors",
                "situation": "situations",
                "knowledge": "knowledge",
                "procedure": "procedures",
                "rule": "reference",
                "table": "reference",
                "item": "reference",
                "spell": "reference",
                "class": "reference",
                "effect": "reference",
            }
            for record, directory in expected_directories.items():
                matching = next(
                    item
                    for item in records
                    if item["record_type"] == record
                )
                expected_path = f"cards/{directory}/{matching['id']}.md"
                self.assertEqual(
                    card_path(matching),
                    expected_path,
                )
                self.assertTrue((first / expected_path).is_file())

            marker = json.loads(
                (first / "GENERATED_OUTPUT.json").read_text(encoding="utf-8")
            )
            self.assertEqual(marker["schema"], GENERATED_OUTPUT_SCHEMA)
            self.assertEqual(
                set(marker["runtime_files"]) | set(marker["audit_files"]),
                {
                    path.relative_to(first).as_posix()
                    for path in first.rglob("*")
                    if path.is_file() and path.name != "GENERATED_OUTPUT.json"
                },
            )
            index_text = (first / "index.json").read_text(encoding="utf-8")
            index = json.loads(index_text)
            allowed = {
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
            self.assertTrue(
                all(set(item) <= allowed for item in index["records"])
            )
            place_index = next(
                item for item in index["records"] if item["id"] == "place.gate"
            )
            self.assertEqual(place_index["type"], "place")
            self.assertEqual(place_index["topology_node"], "place.gate")
            situation_index = next(
                item
                for item in index["records"]
                if item["id"] == "situation.example"
            )
            self.assertEqual(
                situation_index["activation"]["type"], "triggered"
            )
            self.assertEqual(
                set(situation_index["load_with"]),
                {"actors", "procedures", "knowledge"},
            )
            self.assertEqual(situation_index["possible_effects"], [])
            for prohibited in (
                "observation_ids",
                "pack_id",
                "confidence",
                "review",
                "coverage",
            ):
                self.assertNotIn(prohibited, index_text)
            topology_text = (first / "topology.yaml").read_text(
                encoding="utf-8"
            )
            self.assertIn('"kind": "doorway"', topology_text)
            self.assertIn('"conditions": [', topology_text)
            self.assertNotIn("facet_observations", topology_text)
            self.assertNotIn("pack_id", topology_text)
            self.assertNotIn("confidence", topology_text)
            self.assertLess(
                (first / "index.json").stat().st_size,
                (first / "audit" / "module.json").stat().st_size,
            )
            self.assertEqual(
                (first / "topology.yaml").read_bytes(),
                (second / "topology.yaml").read_bytes(),
            )
            self.assertEqual(
                content_tree_hash(first), content_tree_hash(second)
            )

    def test_card_envelope_escapes_yaml_and_orders_fields(self) -> None:
        # Reference cards keep the generic operational-field rendering; places,
        # actors, and situations have dedicated operational layouts.
        text = _card(
            {
                "id": "item.example.horn",
                "record_type": "item",
                "fields": {
                    "zebra": "last",
                    "title": 'Horn: "North"\n---',
                    "alpha": "first",
                },
                "source_pages": [2, 10],
                "references": ["place.example.gate"],
            },
            aliases=["item.horn", "item.old-horn"],
            verification="verified",
        )
        self.assertIn('title: "Horn: \\"North\\"\\n---"', text)
        self.assertIn(
            'aliases: ["item.horn", "item.old-horn"]', text
        )
        self.assertLess(text.index("### Alpha"), text.index("### Zebra"))
        self.assertTrue(text.startswith("---\nid: "))

    def test_module_entry_has_identity_metadata_and_runtime_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            module = rendered_module()
            render_module(root, module)
            text = (root / "MODULE.md").read_text(encoding="utf-8")
            self.assertIn("Module ID: `example-adventure`", text)
            self.assertIn("Verification: `verified`", text)
            self.assertIn("System: Example System", text)
            self.assertIn("Edition: Second", text)
            self.assertIn("not gameplay context", text)
            self.assertIn("only `First impression` is player-safe", text)

    def test_unsafe_replacement_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "personal"
            target.mkdir()
            (target / "notes.txt").write_text("not generated", encoding="utf-8")
            self.assertFalse(_replaceable_output(target))
            self.assertEqual(
                (target / "notes.txt").read_text(encoding="utf-8"), "not generated"
            )

    def test_prior_generated_output_contract_is_not_replaceable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "old-output"
            target.mkdir()
            (target / "GENERATED_OUTPUT.json").write_text(
                json.dumps(
                    {"schema": "module-extractor-generated-output/v1"}
                ),
                encoding="utf-8",
            )
            self.assertFalse(_replaceable_output(target))

    def test_incomplete_or_tampered_v2_output_is_not_replaceable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "generated"
            module = rendered_module()
            render_module(target, module)
            validate_rendered_module(target, module)
            self.assertTrue(_replaceable_output(target))
            (target / "MODULE.md").write_text(
                "personal edit", encoding="utf-8"
            )
            self.assertFalse(_replaceable_output(target))


if __name__ == "__main__":
    unittest.main()
