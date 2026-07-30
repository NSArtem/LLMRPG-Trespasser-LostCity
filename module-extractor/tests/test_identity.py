from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import sys
import tempfile
import unittest


EXTRACTOR_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXTRACTOR_ROOT))

from module_extractor.assembly import canonical_module, evaluate  # noqa: E402
from module_extractor.cli import (  # noqa: E402
    Workspace,
    command_run,
    inspect_workspace,
    render_codex_task,
)
from module_extractor.contracts import (  # noqa: E402
    CONTENT_SCHEMA,
    REVIEW_SCHEMA,
    ROUTING_SCHEMA,
)
from module_extractor.identity import (  # noqa: E402
    apply_identity_review,
    detect_duplicate_candidates,
    normalize_identity_text,
)
from module_extractor.reconciliation import reconcile_records  # noqa: E402
from module_extractor.review import apply_review, release_gate  # noqa: E402
from module_extractor.util import load_json, sha256_file, write_json  # noqa: E402


SOURCE = {
    "filename": "synthetic.pdf",
    "title": "Synthetic Module",
    "slug": "synthetic-module",
    "pdf_pages": 2,
    "sha256": "a" * 64,
}


def content_observation(
    observation_id: str,
    concept_id: str,
    title: str,
    *,
    record_type: str = "location",
    page: int = 1,
    references: list[str] | None = None,
    extra_fields: dict | None = None,
) -> dict:
    fields = {
        "title": title,
        (
            "first_impression"
            if record_type == "location"
            else "role"
            if record_type == "actor"
            else "text"
        ): "Synthetic evidence.",
        **(extra_fields or {}),
    }
    return {
        "observation_id": observation_id,
        "concept_id": concept_id,
        "record_type": record_type,
        "fields": fields,
        "source_pages": [page],
        "confidence": "high",
        "references": references or [],
        "pack_id": f"content.{page:03d}",
    }


def evidence(observations: list[dict], map_results: list[dict] | None = None) -> dict:
    return {
        "content_observations": observations,
        "map_results": map_results or [],
        "uncertainties": [],
        "responses": [],
    }


def empty_review() -> dict:
    return {
        "schema": REVIEW_SCHEMA,
        "source_sha256": SOURCE["sha256"],
        "canonical_ids": [],
        "aliases": [],
        "distinct": [],
        "values": [],
        "accepted_uncertainties": [],
        "notes": "",
    }


class IdentityAnalysisTests(unittest.TestCase):
    def test_normalization_and_candidate_order_are_deterministic(self) -> None:
        self.assertEqual(
            normalize_identity_text("The Princess’s Area-03"),
            "the princesss area 3",
        )
        observations = [
            content_observation(
                "observation.two",
                "location.area.03.iron-gate",
                "Area 3: Iron Gate",
                page=2,
            ),
            content_observation(
                "observation.one",
                "location-area-03-iron-gate",
                "Area 03 — Iron Gate",
            ),
        ]
        first = detect_duplicate_candidates(evidence(observations), SOURCE)
        second = detect_duplicate_candidates(evidence(observations[::-1]), SOURCE)
        self.assertEqual(first, second)
        self.assertEqual(first[0]["confidence"], "high")
        self.assertIn("normalized-extracted-id", first[0]["signals"])

    def test_alias_merges_complementary_observations_and_preserves_audit_ids(self) -> None:
        observations = [
            content_observation(
                "observation.introduction",
                "location-iron-gate",
                "Iron Gate",
                references=["location.iron-gate"],
                extra_fields={"introduction": "Seen from the road."},
            ),
            content_observation(
                "observation.keyed-area",
                "location.iron-gate",
                "Iron Gate",
                page=2,
                extra_fields={"keyed_area": "3"},
            ),
        ]
        raw = evidence(observations)
        review = empty_review()
        review["canonical_ids"] = [
            {
                "extracted_id": "location-iron-gate",
                "canonical_id": "place.synthetic-module.iron-gate",
                "source_pages": [1, 2],
                "rationale": "Both passages describe the same gate.",
            }
        ]
        review["aliases"] = [
            {
                "alias": "location.iron-gate",
                "target_id": "location-iron-gate",
                "source_pages": [1, 2],
                "rationale": "The keyed entry continues the introduction.",
            }
        ]
        identity = apply_identity_review(raw, review, SOURCE)
        records, conflicts = reconcile_records(
            identity["evidence"]["content_observations"]
        )
        self.assertEqual(conflicts, [])
        self.assertEqual([record["id"] for record in records], [
            "place.synthetic-module.iron-gate"
        ])
        self.assertEqual(
            set(records[0]["fields"]),
            {"first_impression", "introduction", "keyed_area", "title"},
        )
        self.assertEqual(
            records[0]["observation_ids"],
            ["observation.introduction", "observation.keyed-area"],
        )
        self.assertEqual(
            records[0]["references"], ["place.synthetic-module.iron-gate"]
        )
        self.assertEqual(
            [item["concept_id"] for item in raw["content_observations"]],
            ["location-iron-gate", "location.iron-gate"],
        )

    def test_same_title_guards_remain_distinct(self) -> None:
        raw = evidence(
            [
                content_observation(
                    "observation.north",
                    "actor.north.guard",
                    "Guard",
                    record_type="actor",
                ),
                content_observation(
                    "observation.south",
                    "actor.south.guard",
                    "Guard",
                    record_type="actor",
                    page=2,
                ),
            ]
        )
        candidates = detect_duplicate_candidates(raw, SOURCE)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["confidence"], "medium")
        unreviewed_identity = apply_identity_review(raw, empty_review(), SOURCE)
        unreviewed_records, unreviewed_conflicts = reconcile_records(
            unreviewed_identity["evidence"]["content_observations"]
        )
        unreviewed = apply_review(
            unreviewed_records,
            {"nodes": [], "passages": []},
            unreviewed_conflicts,
            [],
            empty_review(),
            unreviewed_identity,
        )
        self.assertFalse(
            any(
                "duplicate candidates" in error
                for error in release_gate(unreviewed, {"complete": True})
            )
        )
        review = empty_review()
        review["distinct"] = [
            {
                "left_id": "actor.north.guard",
                "right_id": "actor.south.guard",
                "source_pages": [1, 2],
                "rationale": "The source places one guard at each separate post.",
            }
        ]
        identity = apply_identity_review(raw, review, SOURCE)
        canonical_ids = sorted(identity["mapping"].values())
        self.assertEqual(len(set(canonical_ids)), 2)
        self.assertEqual(identity["candidate_groups"][0]["status"], "distinct")
        self.assertEqual(len(identity["rejected_merges"]), 1)
        self.assertEqual(identity["unresolved_high_confidence"], [])

    def test_shared_topology_relationship_flags_duplicate_locations(self) -> None:
        raw = evidence(
            [
                content_observation(
                    "observation.entry",
                    "location.old-entry",
                    "Old Entry",
                    references=["map-node.7"],
                ),
                content_observation(
                    "observation.entrance",
                    "location.ancient-entrance",
                    "Ancient Entrance",
                    page=2,
                    references=["map-node.7"],
                ),
            ]
        )
        candidate = detect_duplicate_candidates(raw, SOURCE)[0]
        self.assertEqual(candidate["confidence"], "high")
        self.assertIn("shared-relationships", candidate["signals"])

    def test_location_alias_rewrites_topology_endpoints(self) -> None:
        raw = evidence(
            [
                content_observation(
                    "observation.entry",
                    "location-entry",
                    "Entry",
                    extra_fields={"topology_label": "01"},
                )
            ],
            [
                {
                    "pack_id": "map.001",
                    "nodes": [
                        {
                            "observation_id": "observation.map.node.entry",
                            "concept_id": "map.area-1",
                            "label": "1",
                            "title": "Entry",
                            "source_pages": [1],
                            "confidence": "high",
                            "pack_id": "map.001",
                        },
                        {
                            "observation_id": "observation.map.node.hall",
                            "concept_id": "map.area-2",
                            "label": "2",
                            "title": "Hall",
                            "source_pages": [1],
                            "confidence": "high",
                            "pack_id": "map.001",
                        },
                    ],
                    "passages": [
                        {
                            "observation_id": "observation.map.passage.one",
                            "source_id": "passage.one",
                            "from": "map.area-1",
                            "to": "map.area-2",
                            "facets": {
                                "kind": "doorway",
                                "medium": None,
                                "elevation": None,
                                "barriers": [],
                                "features": [],
                                "conditions": [],
                                "traversal_direction": "both",
                            },
                            "source_pages": [1],
                            "confidence": "high",
                            "pack_id": "map.001",
                        }
                    ],
                    "uncertainties": [],
                }
            ],
        )
        candidate = next(
            item
            for item in detect_duplicate_candidates(raw, SOURCE)
            if set(item["extracted_ids"]) == {"location-entry", "map.area-1"}
        )
        self.assertEqual(candidate["confidence"], "high")
        self.assertIn("topology-label", candidate["signals"])
        review = empty_review()
        review["canonical_ids"] = [
            {
                "extracted_id": "location-entry",
                "canonical_id": "place.synthetic-module.entry",
                "source_pages": [1],
                "rationale": "The keyed location and map label are one place.",
            }
        ]
        review["aliases"] = [
            {
                "alias": "map.area-1",
                "target_id": "location-entry",
                "source_pages": [1],
                "rationale": "Map label 1 names the Entry.",
            }
        ]
        identity = apply_identity_review(raw, review, SOURCE)
        passage = identity["evidence"]["map_results"][0]["passages"][0]
        self.assertEqual(passage["from"], "place.synthetic-module.entry")
        self.assertEqual(passage["to"], "place.synthetic-module.hall")

    def test_alias_cycles_are_review_required_and_do_not_crash(self) -> None:
        raw = evidence(
            [
                content_observation("observation.a", "location.a", "A"),
                content_observation(
                    "observation.b", "location.b", "B", page=2
                ),
            ]
        )
        review = empty_review()
        review["aliases"] = [
            {
                "alias": "location.a",
                "target_id": "location.b",
                "source_pages": [1, 2],
                "rationale": "Synthetic cycle edge.",
            },
            {
                "alias": "location.b",
                "target_id": "location.a",
                "source_pages": [1, 2],
                "rationale": "Synthetic cycle edge.",
            },
        ]
        identity = apply_identity_review(raw, review, SOURCE)
        self.assertTrue(any("alias cycle" in error for error in identity["errors"]))
        records, conflicts = reconcile_records(
            identity["evidence"]["content_observations"]
        )
        reviewed = apply_review(
            records,
            {"nodes": [], "passages": []},
            conflicts,
            [],
            review,
            identity,
        )
        errors = release_gate(reviewed, {"complete": True})
        self.assertTrue(any("alias cycle" in error for error in errors))

    def test_ambiguous_and_missing_alias_targets_block_release(self) -> None:
        raw = evidence(
            [
                content_observation("observation.a", "location.a", "A"),
                content_observation("observation.b", "location.b", "B"),
                content_observation("observation.c", "location.c", "C"),
            ]
        )
        review = empty_review()
        review["aliases"] = [
            {
                "alias": "location.a",
                "target_id": "location.b",
                "source_pages": [1],
                "rationale": "First proposed target.",
            },
            {
                "alias": "location.a",
                "target_id": "location.c",
                "source_pages": [1],
                "rationale": "Second proposed target.",
            },
            {
                "alias": "location.b",
                "target_id": "location.missing",
                "source_pages": [1],
                "rationale": "Synthetic missing target.",
            },
        ]
        identity = apply_identity_review(raw, review, SOURCE)
        self.assertTrue(
            any("ambiguous targets" in error for error in identity["errors"])
        )
        self.assertTrue(
            any("unknown extracted ID" in error for error in identity["errors"])
        )
        records, conflicts = reconcile_records(
            identity["evidence"]["content_observations"]
        )
        reviewed = apply_review(
            records,
            {"nodes": [], "passages": []},
            conflicts,
            [],
            review,
            identity,
        )
        errors = release_gate(reviewed, {"complete": True})
        self.assertTrue(any("ambiguous targets" in error for error in errors))
        self.assertTrue(any("unknown extracted ID" in error for error in errors))

    def test_same_keyed_area_requires_a_reviewed_distinction(self) -> None:
        raw = evidence(
            [
                content_observation(
                    "observation.east",
                    "location.east-door",
                    "East Door",
                    extra_fields={"keyed_area": "7"},
                ),
                content_observation(
                    "observation.west",
                    "location.west-door",
                    "West Door",
                    page=2,
                    extra_fields={"keyed_area": "07"},
                ),
            ]
        )
        identity = apply_identity_review(raw, empty_review(), SOURCE)
        self.assertEqual(len(identity["keyed_area_conflicts"]), 1)
        records, conflicts = reconcile_records(
            identity["evidence"]["content_observations"]
        )
        reviewed = apply_review(
            records,
            {"nodes": [], "passages": []},
            conflicts,
            [],
            empty_review(),
            identity,
        )
        self.assertTrue(
            any(
                "keyed area 7 is claimed" in error
                for error in release_gate(reviewed, {"complete": True})
            )
        )
        review = empty_review()
        review["distinct"] = [
            {
                "left_id": "location.east-door",
                "right_id": "location.west-door",
                "source_pages": [1, 2],
                "rationale": "The map shows separate east and west doors.",
            }
        ]
        reviewed_identity = apply_identity_review(raw, review, SOURCE)
        self.assertEqual(reviewed_identity["keyed_area_conflicts"], [])

    def test_dangling_rewritten_reference_blocks_release(self) -> None:
        raw = evidence(
            [
                content_observation(
                    "observation.gate",
                    "location.gate",
                    "Gate",
                    references=["actor.missing"],
                )
            ]
        )
        review = empty_review()
        identity = apply_identity_review(raw, review, SOURCE)
        records, conflicts = reconcile_records(
            identity["evidence"]["content_observations"]
        )
        reviewed = apply_review(
            records,
            {"nodes": [], "passages": []},
            conflicts,
            [],
            review,
            identity,
        )
        errors = release_gate(reviewed, {"complete": True})
        self.assertTrue(any("references missing ID actor.missing" in item for item in errors))


class CleanIdentityPipelineTests(unittest.TestCase):
    def _write_run(self, root: Path, *, reverse_packs: bool) -> Path:
        run = root / "module-input"
        responses = run / "responses"
        responses.mkdir(parents=True)
        write_json(run / "source.json", SOURCE)
        write_json(
            run / "routing.json",
            {
                "schema": ROUTING_SCHEMA,
                "source_sha256": SOURCE["sha256"],
                "pages": [
                    {
                        "pdf_page": page,
                        "tasks": ["adventure"],
                        "exclusion_reason": None,
                        "confidence": "high",
                        "notes": "",
                    }
                    for page in (1, 2)
                ],
            },
        )
        packs = []
        records = [
            {
                "id": "location-iron-gate",
                "record_type": "location",
                "fields": {
                    "title": "Iron Gate",
                    "first_impression": "A synthetic iron gate.",
                    "introduction": "Visible from the road.",
                    "topology_node": None,
                },
                "source_pages": [1],
                "confidence": "high",
                "references": [],
                "uncertainties": [],
            },
            {
                "id": "location.iron-gate",
                "record_type": "location",
                "fields": {
                    "title": "Iron Gate",
                    "first_impression": "A synthetic iron gate.",
                    "keyed_area": "3",
                    "topology_node": None,
                },
                "source_pages": [2],
                "confidence": "high",
                "references": [],
                "uncertainties": [],
            },
        ]
        for page, record in zip((1, 2), records):
            pack_id = f"content.{page:03d}"
            response_path = responses / f"{pack_id}.json"
            response = {
                "schema": CONTENT_SCHEMA,
                "source_sha256": SOURCE["sha256"],
                "pack_id": pack_id,
                "task": "content",
                "task_coverage": [
                    {
                        "pdf_page": page,
                        "task": "adventure",
                        "status": "extracted",
                        "record_ids": [record["id"]],
                        "notes": "",
                    }
                ],
                "records": [record],
            }
            write_json(response_path, response)
            packs.append(
                {
                    "pack_id": pack_id,
                    "task": "content",
                    "tasks": ["adventure"],
                    "physical_pages": [page],
                    "page_tasks": [
                        {
                            "pdf_page": page,
                            "tasks": ["adventure"],
                            "context_reason": None,
                        }
                    ],
                    "text_bytes": 100,
                    "archive_path": f"../_exchange/{pack_id}.zip",
                    "pack_sha256": str(page) * 64,
                    "response_path": f"responses/{pack_id}.json",
                    "ingested_response_sha256": sha256_file(response_path),
                }
            )
        write_json(
            run / "packs.json",
            {
                "schema": "module-pack-manifest/v1",
                "source_sha256": SOURCE["sha256"],
                "packs": list(reversed(packs)) if reverse_packs else packs,
            },
        )
        write_json(run / "review.json", empty_review())
        return run

    def _review_duplicates(self, run: Path) -> None:
        review = empty_review()
        review["canonical_ids"] = [
            {
                "extracted_id": "location-iron-gate",
                "canonical_id": "place.synthetic-module.iron-gate",
                "source_pages": [1, 2],
                "rationale": "The introduction and keyed entry describe one gate.",
            }
        ]
        review["aliases"] = [
            {
                "alias": "location.iron-gate",
                "target_id": "location-iron-gate",
                "source_pages": [1, 2],
                "rationale": "The keyed entry continues the introduction.",
            }
        ]
        write_json(run / "review.json", review)

    def test_clean_review_required_then_release_is_order_independent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_run = self._write_run(root / "first", reverse_packs=False)
            second_run = self._write_run(root / "second", reverse_packs=True)

            unresolved = evaluate(first_run)
            unresolved_reordered = evaluate(second_run)
            self.assertTrue(
                any("duplicate candidates" in item for item in unresolved["gate_errors"])
            )
            self.assertEqual(
                unresolved["identity"]["candidate_groups"][0]["status"],
                "unresolved",
            )
            self.assertEqual(
                unresolved["identity"]["candidate_groups"],
                unresolved_reordered["identity"]["candidate_groups"],
            )
            self.assertEqual(
                render_codex_task(unresolved, Path("module-input/review.json")),
                render_codex_task(
                    unresolved_reordered, Path("module-input/review.json")
                ),
            )
            workspace_root = first_run.parent
            workspace = Workspace(
                root=workspace_root,
                input=first_run,
                exchange=workspace_root / "_exchange",
                cache=workspace_root / ".module-extractor-cache",
                module=workspace_root / "module",
            )
            self.assertEqual(
                inspect_workspace(workspace)["stage"], "codex-review-required"
            )
            run_args = argparse.Namespace(
                pdf=None,
                slug=None,
                title=None,
                workspace_root=str(workspace_root),
            )
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                command_run(run_args)
            self.assertTrue((workspace.exchange / "codex-task.md").is_file())
            self.assertFalse(workspace.module.exists())

            self._review_duplicates(first_run)
            self._review_duplicates(second_run)
            first = evaluate(first_run)
            second = evaluate(second_run)
            self.assertEqual(first["gate_errors"], [])
            self.assertEqual(second["gate_errors"], [])
            self.assertEqual(
                canonical_module(first, profile="release"),
                canonical_module(second, profile="release"),
            )

            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                command_run(run_args)
            output = workspace.module
            module = load_json(output / "audit" / "module.json")
            self.assertEqual(
                [record["id"] for record in module["records"]],
                ["place.synthetic-module.iron-gate"],
            )
            index = load_json(output / "index.json")
            self.assertEqual(
                index["records"][0]["aliases"],
                ["location-iron-gate", "location.iron-gate"],
            )
            audit = load_json(output / "audit" / "module.json")
            self.assertEqual(
                sorted(
                    item["concept_id"]
                    for item in audit["raw_observations"]["content"]
                ),
                ["location-iron-gate", "location.iron-gate"],
            )
            self.assertEqual(
                audit["identity"]["candidate_groups"][0]["status"],
                "confirmed-alias",
            )


if __name__ == "__main__":
    unittest.main()
