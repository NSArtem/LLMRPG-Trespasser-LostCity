"""Implementation 3: operational actors and situations."""

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
    REVIEW_SCHEMA,
    ROUTING_SCHEMA,
    validate_content_response,
)
from module_extractor.errors import ExtractorError  # noqa: E402
from module_extractor.identity import apply_identity_review  # noqa: E402
from module_extractor.operations import (  # noqa: E402
    resolve_operational_records,
)
from module_extractor.reconciliation import reconcile_records  # noqa: E402
from module_extractor.rendering import validate_rendered_module  # noqa: E402
from module_extractor.review import apply_review, release_gate  # noqa: E402
from module_extractor.scene import resolve_scene  # noqa: E402
from module_extractor.util import content_tree_hash, load_json  # noqa: E402


SOURCE = {
    "filename": "synthetic.pdf",
    "title": "Synthetic Encounters",
    "slug": "synthetic-encounters",
    "pdf_pages": 2,
    "sha256": "a" * 64,
}


def record(
    identifier: str,
    record_type: str,
    fields: dict,
    *,
    page: int = 1,
    references: list[str] | None = None,
) -> dict:
    return {
        "id": identifier,
        "record_type": record_type,
        "fields": fields,
        "source_pages": [page],
        "confidence": "high",
        "references": references or [],
        "uncertainties": [],
    }


def guard_fields(
    *,
    title: str = "Guard",
    role: str = "Holds the gate against strangers.",
) -> dict:
    return {
        "title": title,
        "appearance": "A mailed figure with a chipped spear.",
        "role": role,
        "goals": ["Keep the gate closed until dusk."],
        "behavior": ["Challenges anyone who approaches the gate."],
        "reactions": [
            {
                "stimulus": "A bribe is offered openly.",
                "response": "Refuses loudly so the sergeant hears it.",
            }
        ],
        "capabilities": ["Spear, 1d6 damage; chain shirt, AC 13."],
        "hidden": ["Secretly ordered to let the Winter courier pass."],
        "starting_state": ["Begins the adventure posted at the gate."],
    }


def content_response(records: list[dict], *, pack_id: str = "content.001") -> dict:
    return {
        "schema": CONTENT_SCHEMA,
        "source_sha256": SOURCE["sha256"],
        "pack_id": pack_id,
        "task": "content",
        "task_coverage": [
            {
                "pdf_page": 1,
                "task": "adventure",
                "status": "extracted",
                "record_ids": sorted(item["id"] for item in records),
                "notes": "",
            }
        ],
        "records": records,
    }


CONTENT_PACK = {
    "pack_id": "content.001",
    "task": "content",
    "physical_pages": [1],
    "page_tasks": [{"pdf_page": 1, "tasks": ["adventure"]}],
}


def reviewed(records: list[dict], *, topology: dict | None = None) -> dict:
    canonical = []
    for item in records:
        canonical.append(
            {
                "id": item["id"],
                "record_type": item["record_type"],
                "fields": item["fields"],
                "references": item["references"],
                "source_pages": item["source_pages"],
            }
        )
    return {
        "records": canonical,
        "topology": topology or {"nodes": [], "passages": []},
    }


class ActorContractTests(unittest.TestCase):
    def test_public_behavior_and_hidden_orders_stay_separate(self) -> None:
        guard = record("actor.gate-guard", "actor", guard_fields())
        response = content_response([guard])
        records = validate_content_response(response, CONTENT_PACK, SOURCE)
        fields = records[0]["fields"]
        self.assertIn(
            "Challenges anyone who approaches the gate.", fields["behavior"]
        )
        self.assertNotIn(
            "Winter courier", json.dumps(fields["behavior"], ensure_ascii=False)
        )
        self.assertIn(
            "Secretly ordered to let the Winter courier pass.", fields["hidden"]
        )
        self.assertEqual(resolve_operational_records(reviewed(records))["record_errors"], [])

    def test_mutable_runtime_state_is_rejected(self) -> None:
        for field, value in (
            ("health", "12 hit points"),
            ("inventory", ["a lantern"]),
            ("attitude", "hostile"),
            ("current_position", "at the gate"),
        ):
            fields = guard_fields()
            fields[field] = value
            response = content_response(
                [record("actor.gate-guard", "actor", fields)]
            )
            with self.subTest(field=field):
                with self.assertRaisesRegex(
                    ExtractorError, "must not carry mutable runtime state"
                ):
                    validate_content_response(response, CONTENT_PACK, SOURCE)

    def test_labeled_starting_state_survives_to_the_card(self) -> None:
        guard = record("actor.gate-guard", "actor", guard_fields())
        records = validate_content_response(
            content_response([guard]), CONTENT_PACK, SOURCE
        )
        self.assertEqual(
            records[0]["fields"]["starting_state"],
            ["Begins the adventure posted at the gate."],
        )

    def test_typed_relationships_must_name_an_actor(self) -> None:
        fields = guard_fields()
        fields["relationships"] = [
            {"relationship": "Reports to the sergeant.", "target_id": "actor.sergeant"}
        ]
        guard = record(
            "actor.gate-guard", "actor", fields, references=["actor.sergeant"]
        )
        sergeant_situation = record(
            "actor.sergeant",
            "situation",
            {
                "title": "The Sergeant's Round",
                "perceived": "A sergeant strides across the yard.",
                "activation": {"type": "ongoing", "condition": "Always present."},
            },
        )
        dangling = validate_content_response(
            content_response([guard]), CONTENT_PACK, SOURCE
        )
        self.assertTrue(
            any(
                "names missing actor actor.sergeant" in error
                for error in resolve_operational_records(reviewed(dangling))[
                    "record_errors"
                ]
            )
        )
        mistyped = validate_content_response(
            content_response([guard, sergeant_situation]), CONTENT_PACK, SOURCE
        )
        self.assertTrue(
            any(
                "references situation actor.sergeant" in error
                for error in resolve_operational_records(reviewed(mistyped))[
                    "record_errors"
                ]
            )
        )
        sergeant = record(
            "actor.sergeant",
            "actor",
            guard_fields(title="Sergeant", role="Walks the wall at odd hours."),
        )
        resolved = validate_content_response(
            content_response([guard, sergeant]), CONTENT_PACK, SOURCE
        )
        self.assertEqual(
            resolve_operational_records(reviewed(resolved))["record_errors"], []
        )

    def test_two_same_name_actors_in_different_roles_stay_distinct(self) -> None:
        observations = []
        for number, (identifier, role) in enumerate(
            (
                ("actor.gate-guard", "Holds the gate against strangers."),
                ("actor.yard-guard", "Commands the yard patrol."),
            ),
            1,
        ):
            observations.append(
                {
                    "observation_id": f"observation.{number}",
                    "concept_id": identifier,
                    "record_type": "actor",
                    "fields": guard_fields(role=role),
                    "source_pages": [1],
                    "confidence": "high",
                    "references": [],
                    "pack_id": "content.001",
                }
            )
        evidence = {
            "content_observations": observations,
            "map_results": [],
            "uncertainties": [],
            "responses": [],
        }
        empty_review = {
            "schema": REVIEW_SCHEMA,
            "source_sha256": SOURCE["sha256"],
            "canonical_ids": [],
            "aliases": [],
            "distinct": [],
            "values": [],
            "accepted_uncertainties": [],
            "topology_composites": [],
            "notes": "",
        }
        identity = apply_identity_review(evidence, empty_review, SOURCE)
        self.assertEqual(len(set(identity["mapping"].values())), 2)
        self.assertEqual(identity["unresolved_high_confidence"], [])
        records, conflicts = reconcile_records(
            identity["evidence"]["content_observations"]
        )
        self.assertEqual(conflicts, [])
        self.assertEqual(
            sorted(item["fields"]["role"] for item in records),
            ["Commands the yard patrol.", "Holds the gate against strangers."],
        )

    def test_alias_rewrites_actor_and_situation_references(self) -> None:
        observations = [
            {
                "observation_id": "observation.guard",
                "concept_id": "actor.gate-guard",
                "record_type": "actor",
                "fields": {
                    **guard_fields(),
                    "relationships": [
                        {
                            "relationship": "Serves the captain.",
                            "target_id": "actor.old-captain",
                        }
                    ],
                    "situation_references": ["situation.parley"],
                },
                "source_pages": [1],
                "confidence": "high",
                "references": ["actor.old-captain", "situation.parley"],
                "pack_id": "content.001",
            },
            {
                "observation_id": "observation.old-captain",
                "concept_id": "actor.old-captain",
                "record_type": "actor",
                "fields": guard_fields(title="Captain", role="Commands the watch."),
                "source_pages": [1],
                "confidence": "high",
                "references": [],
                "pack_id": "content.001",
            },
            {
                "observation_id": "observation.captain",
                "concept_id": "actor.captain",
                "record_type": "actor",
                "fields": guard_fields(title="Captain", role="Commands the watch."),
                "source_pages": [1],
                "confidence": "high",
                "references": [],
                "pack_id": "content.001",
            },
            {
                "observation_id": "observation.parley",
                "concept_id": "situation.parley",
                "record_type": "situation",
                "fields": {
                    "title": "Parley",
                    "perceived": "The captain raises an empty hand.",
                    "activation": {
                        "type": "chosen",
                        "condition": "The party asks to talk.",
                    },
                    "participants": [
                        {"actor_id": "actor.old-captain", "role": "Speaks first."}
                    ],
                    "possible_effects": [
                        {
                            "effect": "actor-state",
                            "target": "actor.old-captain",
                            "description": "The captain may stand down.",
                        }
                    ],
                },
                "source_pages": [1],
                "confidence": "high",
                "references": ["actor.old-captain"],
                "pack_id": "content.001",
            },
        ]
        review = {
            "schema": REVIEW_SCHEMA,
            "source_sha256": SOURCE["sha256"],
            "canonical_ids": [],
            "aliases": [
                {
                    "alias": "actor.old-captain",
                    "target_id": "actor.captain",
                    "source_pages": [1],
                    "rationale": "The source names one captain of the watch.",
                }
            ],
            "distinct": [],
            "values": [],
            "accepted_uncertainties": [],
            "topology_composites": [],
            "notes": "",
        }
        identity = apply_identity_review(
            {
                "content_observations": observations,
                "map_results": [],
                "uncertainties": [],
                "responses": [],
            },
            review,
            SOURCE,
        )
        self.assertFalse(identity["errors"])
        canonical = identity["mapping"]["actor.old-captain"]
        self.assertEqual(canonical, identity["mapping"]["actor.captain"])
        rewritten = {
            item["concept_id"]: item
            for item in identity["evidence"]["content_observations"]
        }
        guard = rewritten[identity["mapping"]["actor.gate-guard"]]
        self.assertEqual(
            guard["fields"]["relationships"][0]["target_id"], canonical
        )
        self.assertEqual(
            guard["fields"]["situation_references"],
            [identity["mapping"]["situation.parley"]],
        )
        parley = rewritten[identity["mapping"]["situation.parley"]]
        self.assertEqual(
            parley["fields"]["participants"][0]["actor_id"], canonical
        )
        self.assertEqual(
            parley["fields"]["possible_effects"][0]["target"], canonical
        )


class ReviewedValueTests(unittest.TestCase):
    def test_authored_typed_references_are_canonicalized(self) -> None:
        records = [
            {
                "id": "situation.parley",
                "record_type": "situation",
                "fields": {
                    "title": "Parley",
                    "perceived": "The guard waits.",
                    "activation": {
                        "type": "chosen",
                        "condition": "The party talks.",
                    },
                },
                "references": [],
                "source_pages": [1],
                "field_observations": {},
                "observation_ids": ["observation.parley"],
                "extracted_ids": ["situation.parley"],
            }
        ]
        review = {
            "aliases": [],
            "values": [
                {
                    "object_id": "situation.parley",
                    "field": "participants",
                    "value": [
                        {
                            "actor_id": "actor.old-guard",
                            "role": "Speaks for the gate.",
                        }
                    ],
                    "mode": "select",
                    "source_pages": [1],
                    "rationale": "The source names the guard as the speaker.",
                },
                {
                    "object_id": "situation.parley",
                    "field": "knowledge_references",
                    "value": ["knowledge.old-orders"],
                    "mode": "select",
                    "source_pages": [1],
                    "rationale": "The source cites the sealed order here.",
                },
            ],
            "accepted_uncertainties": [],
            "topology_composites": [],
        }
        identity = {
            "aliases": {},
            "mapping": {
                "actor.old-guard": "actor.synthetic-encounters.guard",
                "knowledge.old-orders": "knowledge.synthetic-encounters.orders",
            },
            "errors": [],
            "unresolved_high_confidence": [],
            "keyed_area_conflicts": [],
        }
        result = apply_review(
            records,
            {"nodes": [], "passages": []},
            [],
            [],
            review,
            identity,
        )
        fields = result["records"][0]["fields"]
        self.assertEqual(
            fields["participants"][0]["actor_id"],
            "actor.synthetic-encounters.guard",
        )
        self.assertEqual(
            fields["knowledge_references"],
            ["knowledge.synthetic-encounters.orders"],
        )


class SituationContractTests(unittest.TestCase):
    def negotiation(self) -> dict:
        return record(
            "situation.parley",
            "situation",
            {
                "title": "Parley at the Gate",
                "perceived": "The guard levels a spear and demands a name.",
                "activation": {
                    "type": "chosen",
                    "condition": "The party approaches the gate openly.",
                },
                "repeat": {"mode": "once", "condition": None},
                "participants": [
                    {"actor_id": "actor.gate-guard", "role": "Speaks for the gate."}
                ],
                "actor_reactions": [
                    {
                        "actor_id": "actor.gate-guard",
                        "reaction": "Lowers the spear once a name is given.",
                    }
                ],
                "stakes": ["The gate closes at dusk and stays closed."],
                "approaches": [
                    "Give a true name and accept an escort.",
                    "Bribe the guard where the sergeant cannot see.",
                    "Claim the Winter courier's errand.",
                ],
                "outcomes": [
                    "The party is escorted through.",
                    "The party is turned away until dawn.",
                ],
                "completion": ["The party passes the gate or withdraws."],
            },
            references=["actor.gate-guard"],
        )

    def test_negotiation_keeps_several_approaches_and_reactions(self) -> None:
        records = validate_content_response(
            content_response(
                [self.negotiation(), record("actor.gate-guard", "actor", guard_fields())]
            ),
            CONTENT_PACK,
            SOURCE,
        )
        parley = next(item for item in records if item["record_type"] == "situation")
        self.assertEqual(len(parley["fields"]["approaches"]), 3)
        self.assertEqual(
            parley["fields"]["actor_reactions"][0]["actor_id"], "actor.gate-guard"
        )
        self.assertEqual(resolve_operational_records(reviewed(records))["record_errors"], [])

    def test_one_shot_hazard_and_repeatable_encounter_differ(self) -> None:
        hazard = record(
            "situation.rockfall",
            "situation",
            {
                "title": "Rockfall",
                "perceived": "The ceiling cracks and stone comes down.",
                "activation": {
                    "type": "triggered",
                    "condition": "The party crosses the shored span.",
                },
                "repeat": {"mode": "once", "condition": None},
                "outcomes": ["The span collapses behind the party."],
                "completion": ["The stone settles."],
            },
        )
        patrol = record(
            "situation.patrol",
            "situation",
            {
                "title": "Wandering Patrol",
                "perceived": "Lanterns bob along the wall walk.",
                "activation": {
                    "type": "random",
                    "condition": "Check once per watch on a roll of 1 in 6.",
                },
                "repeat": {
                    "mode": "repeatable",
                    "condition": "Once per watch while the gate is held.",
                },
                "completion": ["The patrol passes or engages."],
            },
        )
        records = validate_content_response(
            content_response([hazard, patrol]), CONTENT_PACK, SOURCE
        )
        by_id = {item["id"]: item for item in records}
        self.assertEqual(
            by_id["situation.rockfall"]["fields"]["repeat"]["mode"], "once"
        )
        self.assertEqual(
            by_id["situation.rockfall"]["fields"]["activation"]["type"], "triggered"
        )
        self.assertEqual(
            by_id["situation.patrol"]["fields"]["repeat"]["mode"], "repeatable"
        )
        self.assertEqual(
            by_id["situation.patrol"]["fields"]["activation"]["type"], "random"
        )

    def test_activation_and_repeat_vocabularies_are_closed(self) -> None:
        fields = {
            "title": "Rockfall",
            "perceived": "Stone comes down.",
            "activation": {"type": "whenever", "condition": "Something happens."},
        }
        with self.assertRaisesRegex(ExtractorError, "activation.type must be one of"):
            validate_content_response(
                content_response([record("situation.rockfall", "situation", fields)]),
                CONTENT_PACK,
                SOURCE,
            )
        fields["activation"] = {"type": "triggered", "condition": "The span cracks."}
        fields["repeat"] = {"mode": "sometimes"}
        with self.assertRaisesRegex(ExtractorError, "repeat.mode must be one of"):
            validate_content_response(
                content_response([record("situation.rockfall", "situation", fields)]),
                CONTENT_PACK,
                SOURCE,
            )

    def test_possible_effects_are_typed_and_never_applied(self) -> None:
        fields = {
            "title": "Rockfall",
            "perceived": "Stone comes down.",
            "activation": {"type": "triggered", "condition": "The span cracks."},
            "possible_effects": [
                {
                    "effect": "topology-state",
                    "target": "map.area-3",
                    "description": "The span may become impassable.",
                    "condition": "Nobody shores it up.",
                },
                {
                    "effect": "future-thread",
                    "description": "The collapse may strand the party.",
                },
            ],
        }
        records = validate_content_response(
            content_response(
                [
                    record(
                        "situation.rockfall",
                        "situation",
                        fields,
                        references=["map.area-3"],
                    )
                ]
            ),
            CONTENT_PACK,
            SOURCE,
        )
        result = resolve_operational_records(
            reviewed(
                records,
                topology={
                    "nodes": [{"id": "map.area-3"}],
                    "passages": [],
                },
            )
        )
        self.assertEqual(result["record_errors"], [])
        # Nothing in the record asserts that an effect already happened.
        self.assertNotIn("active", records[0]["fields"])
        self.assertNotIn("resolved", records[0]["fields"])

    def test_applied_situation_state_is_rejected(self) -> None:
        fields = {
            "title": "Rockfall",
            "perceived": "Stone comes down.",
            "activation": {"type": "triggered", "condition": "The span cracks."},
            "resolved": True,
        }
        with self.assertRaisesRegex(
            ExtractorError, "must not carry mutable runtime state"
        ):
            validate_content_response(
                content_response([record("situation.rockfall", "situation", fields)]),
                CONTENT_PACK,
                SOURCE,
            )

    def test_untargeted_and_mistyped_effects_are_reported(self) -> None:
        fields = {
            "title": "Parley",
            "perceived": "The guard waits.",
            "activation": {"type": "chosen", "condition": "The party talks."},
            "possible_effects": [
                {
                    "effect": "future-thread",
                    "target": "situation.other",
                    "description": "A later reckoning.",
                }
            ],
        }
        with self.assertRaisesRegex(ExtractorError, "must not name a target"):
            validate_content_response(
                content_response(
                    [
                        record(
                            "situation.parley",
                            "situation",
                            fields,
                            references=["situation.other"],
                        )
                    ]
                ),
                CONTENT_PACK,
                SOURCE,
            )
        fields["possible_effects"] = [
            {
                "effect": "activate-situation",
                "target": "actor.gate-guard",
                "description": "The alarm may follow.",
            }
        ]
        records = validate_content_response(
            content_response(
                [
                    record(
                        "situation.parley",
                        "situation",
                        fields,
                        references=["actor.gate-guard"],
                    ),
                    record("actor.gate-guard", "actor", guard_fields()),
                ]
            ),
            CONTENT_PACK,
            SOURCE,
        )
        result = resolve_operational_records(reviewed(records))
        self.assertTrue(
            any(
                "references actor actor.gate-guard" in error
                for error in result["record_errors"]
            )
        )
        self.assertTrue(
            any(
                "references actor" in error
                for error in release_gate(
                    {**result, "aliases": {}, "unresolved_conflicts": [],
                     "pending_uncertainties": []},
                    {"complete": True},
                )
            )
        )

    def test_typed_participant_and_location_references_must_resolve(self) -> None:
        fields = {
            "title": "Parley",
            "perceived": "The guard waits.",
            "activation": {"type": "chosen", "condition": "The party talks."},
            "participants": [
                {"actor_id": "actor.missing", "role": "Speaks for the gate."}
            ],
            "location_references": ["place.missing"],
        }
        records = validate_content_response(
            content_response(
                [
                    record(
                        "situation.parley",
                        "situation",
                        fields,
                        references=["actor.missing", "place.missing"],
                    )
                ]
            ),
            CONTENT_PACK,
            SOURCE,
        )
        errors = resolve_operational_records(reviewed(records))["record_errors"]
        self.assertTrue(
            any("names missing actor actor.missing" in error for error in errors)
        )
        self.assertTrue(
            any("names missing location place.missing" in error for error in errors)
        )


def _place(
    identifier: str,
    title: str,
    label: str,
    *,
    actors: list[str],
    situations: list[str],
) -> dict:
    fields = {
        "title": title,
        "first_impression": f"{title} opens ahead of the party.",
        "topology_label": label,
    }
    if actors:
        fields["actor_references"] = actors
    if situations:
        fields["situation_references"] = situations
    return record(
        identifier, "location", fields, references=sorted(actors + situations)
    )


def _passage(identifier: str, start: str, end: str) -> dict:
    return {
        "id": identifier,
        "from": start,
        "to": end,
        "facets": {
            "kind": "gateway",
            "medium": "ground",
            "elevation": "level",
            "barriers": [],
            "features": [],
            "conditions": [],
            "baseline_state": "open",
            "visibility": "visible",
            "hazards": [],
            "traversal_direction": "both",
        },
        "source_pages": [2],
        "confidence": "high",
    }


class CleanEncounterPipelineTests(unittest.TestCase):
    def test_clean_pipeline_runs_actors_and_situations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / "synthetic-encounters.pdf"
            pdf.write_bytes(b"synthetic pdf")

            def fake_poppler(arguments: list[str]) -> mock.Mock:
                if arguments[0] == "pdftotext":
                    Path(arguments[-1]).write_text(
                        "Gatehouse, yard, and crypt with guards.\f"
                        "Map of the gatehouse, yard, and crypt.\f",
                        encoding="utf-8",
                    )
                elif arguments[0] == "pdftoppm":
                    prefix = Path(arguments[-1])
                    for page in (1, 2):
                        (prefix.parent / f"{prefix.name}-{page}.png").write_bytes(
                            f"thumb-{page}".encode()
                        )
                return mock.Mock(returncode=0, stdout="", stderr="")

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
                    "module_extractor.preparation._run", side_effect=fake_poppler
                ),
                redirect_stdout(io.StringIO()),
                redirect_stderr(io.StringIO()),
            ):
                cli_module.command_prepare(
                    argparse.Namespace(
                        pdf=str(pdf),
                        slug="synthetic-encounters",
                        title="Synthetic Encounters",
                        workspace_root=str(root),
                    )
                )

            module_input = root / "module-input"
            exchange = root / "_exchange"
            source = load_json(module_input / "source.json")
            (exchange / "routing.json").write_text(
                json.dumps(
                    {
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
                ),
                encoding="utf-8",
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
            self.assertIn("hidden: GM-only motivations", prompt)
            self.assertIn("possible_effects: objects with effect", prompt)
            self.assertIn("never applied", prompt)
            self.assertIn("actor_record_template", template)
            self.assertIn("situation_record_template", template)
            self.assertEqual(template["records"], [])

            records = [
                _place(
                    "location.area-1-gatehouse",
                    "Area 1: Gatehouse",
                    "1",
                    actors=["actor.gate-guard"],
                    situations=["situation.parley", "situation.rockfall"],
                ),
                _place(
                    "location.area-2-yard",
                    "Area 2: Yard",
                    "2",
                    actors=["actor.gate-guard", "actor.yard-guard"],
                    situations=["situation.patrol"],
                ),
                _place(
                    "location.area-3-crypt",
                    "Area 3: Crypt",
                    "3",
                    actors=[],
                    situations=["situation.vigil"],
                ),
                record(
                    "actor.gate-guard",
                    "actor",
                    {
                        **guard_fields(),
                        "knowledge_references": ["knowledge.winter-orders"],
                    },
                    references=["knowledge.winter-orders"],
                ),
                record(
                    "actor.yard-guard",
                    "actor",
                    guard_fields(role="Commands the yard patrol."),
                ),
                record(
                    "situation.parley",
                    "situation",
                    {
                        "title": "Parley at the Gate",
                        "perceived": "The guard levels a spear and demands a name.",
                        "activation": {
                            "type": "chosen",
                            "condition": "The party approaches the gate openly.",
                        },
                        "repeat": {"mode": "once", "condition": None},
                        "participants": [
                            {
                                "actor_id": "actor.gate-guard",
                                "role": "Speaks for the gate.",
                            }
                        ],
                        "actor_reactions": [
                            {
                                "actor_id": "actor.gate-guard",
                                "reaction": "Lowers the spear once a name is given.",
                            }
                        ],
                        "stakes": ["The gate closes at dusk and stays closed."],
                        "approaches": [
                            "Give a true name and accept an escort.",
                            "Bribe the guard out of the sergeant's sight.",
                            "Claim the Winter courier's errand.",
                        ],
                        "outcomes": [
                            "The party is escorted through.",
                            "The party is turned away until dawn.",
                        ],
                        "completion": ["The party passes the gate or withdraws."],
                        "procedure_references": ["procedure.reaction-roll"],
                        "knowledge_references": ["knowledge.winter-orders"],
                        "possible_effects": [
                            {
                                "effect": "reveal-knowledge",
                                "target": "knowledge.winter-orders",
                                "description": "The guard may admit his orders.",
                                "condition": "The courier's errand is claimed truly.",
                            },
                            {
                                "effect": "future-thread",
                                "description": "The sergeant may hear of the bribe.",
                            },
                        ],
                    },
                    references=[
                        "actor.gate-guard",
                        "knowledge.winter-orders",
                        "procedure.reaction-roll",
                    ],
                ),
                record(
                    "situation.rockfall",
                    "situation",
                    {
                        "title": "Rockfall in the Gate Arch",
                        "perceived": "The arch cracks and stone comes down.",
                        "activation": {
                            "type": "triggered",
                            "condition": "The portcullis is forced.",
                        },
                        "repeat": {"mode": "once", "condition": None},
                        "stakes": ["The arch is the only way back out."],
                        "outcomes": ["The arch is blocked with rubble."],
                        "completion": ["The stone settles."],
                        "possible_effects": [
                            {
                                "effect": "topology-state",
                                "target": "map.area-1",
                                "description": "The gate arch may become blocked.",
                                "condition": "Nobody shores the arch.",
                            }
                        ],
                    },
                    references=["map.area-1"],
                ),
                record(
                    "situation.patrol",
                    "situation",
                    {
                        "title": "Wandering Patrol",
                        "perceived": "Lanterns bob along the wall walk.",
                        "activation": {
                            "type": "random",
                            "condition": "Check once per watch, 1 in 6.",
                        },
                        "repeat": {
                            "mode": "repeatable",
                            "condition": "Once per watch while the gate is held.",
                        },
                        "participants": [
                            {
                                "actor_id": "actor.yard-guard",
                                "role": "Leads the patrol.",
                            }
                        ],
                        "stakes": ["The patrol raises the yard if it sees intruders."],
                        "outcomes": ["The patrol passes or gives chase."],
                        "completion": ["The patrol leaves the yard."],
                        "possible_effects": [
                            {
                                "effect": "activate-situation",
                                "target": "situation.parley",
                                "description": "The patrol may force a parley.",
                            }
                        ],
                    },
                    references=["actor.yard-guard", "situation.parley"],
                ),
                record(
                    "situation.vigil",
                    "situation",
                    {
                        "title": "Crypt Vigil",
                        "perceived": "Candles burn in front of a sealed niche.",
                        "activation": {
                            "type": "ongoing",
                            "condition": "The crypt is entered.",
                        },
                        "repeat": {"mode": "repeatable", "condition": None},
                        "completion": ["The candles are put out."],
                    },
                ),
                record(
                    "knowledge.winter-orders",
                    "knowledge",
                    {
                        "title": "The Winter Orders",
                        "text": "A sealed order admits the Winter courier at any hour.",
                    },
                ),
                record(
                    "procedure.reaction-roll",
                    "procedure",
                    {
                        "title": "Reaction Roll",
                        "trigger": "The party opens with a demand.",
                        "steps": ["Roll 2d6 and consult the reaction table."],
                    },
                ),
            ]
            map_response = {
                "schema": MAP_SCHEMA,
                "source_sha256": source["sha256"],
                "pack_id": "map.v2.001",
                "nodes": [
                    {
                        "id": "map.area-1",
                        "label": "1",
                        "title": "Gatehouse",
                        "classification": "place",
                        "source_pages": [2],
                        "confidence": "high",
                    },
                    {
                        "id": "map.area-2",
                        "label": "2",
                        "title": "Yard",
                        "classification": "place",
                        "source_pages": [2],
                        "confidence": "high",
                    },
                    {
                        "id": "map.area-3",
                        "label": "3",
                        "title": "Crypt",
                        "classification": "place",
                        "source_pages": [2],
                        "confidence": "high",
                    },
                ],
                "passages": [
                    _passage("gate-arch", "map.area-1", "map.area-2"),
                    _passage("crypt-stair", "map.area-2", "map.area-3"),
                ],
                "uncertainties": [],
            }
            for pack_id, response in (
                (
                    "content.001",
                    {
                        **content_response(records),
                        "source_sha256": source["sha256"],
                    },
                ),
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

            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(io.StringIO()):
                cli_module.command_run(
                    argparse.Namespace(
                        pdf=None, slug=None, title=None, workspace_root=str(root)
                    )
                )
            self.assertIn("Release assembled", output.getvalue())
            self.assertIn(
                "## Actor and situation decisions",
                (root / "_exchange" / "codex-task.md").read_text(encoding="utf-8"),
            )

            module = root / "module"
            audit = load_json(module / "audit" / "module.json")
            validate_rendered_module(module, audit)
            self.assertEqual(audit["record_errors"], [])
            by_title = {
                item["fields"]["title"]: item for item in audit["records"]
            }

            # An actor shared by two places is one record and one card.
            guards = [
                item
                for item in audit["records"]
                if item["record_type"] == "actor"
            ]
            self.assertEqual(len(guards), 2)
            self.assertEqual(len(set(item["id"] for item in guards)), 2)
            self.assertEqual(
                sorted(item["fields"]["role"] for item in guards),
                [
                    "Commands the yard patrol.",
                    "Holds the gate against strangers.",
                ],
            )
            gate_guard = next(
                item
                for item in guards
                if item["fields"]["role"].startswith("Holds")
            )
            actor_cards = sorted(
                path.name for path in (module / "cards" / "actors").iterdir()
            )
            self.assertEqual(len(actor_cards), 2)
            gatehouse = by_title["Area 1: Gatehouse"]
            yard = by_title["Area 2: Yard"]
            for place in (gatehouse, yard):
                self.assertIn(gate_guard["id"], place["references"])

            actor_text = (
                module / "cards" / "actors" / f"{gate_guard['id']}.md"
            ).read_text(encoding="utf-8")
            for heading in (
                "Appearance",
                "Role",
                "Goals",
                "Behavior and reactions",
                "Relationships",
                "Capabilities and mechanics",
                "Starting state",
                "Knowledge",
                "Hidden",
            ):
                self.assertIn(f"## {heading}", actor_text)
            behavior_section = actor_text.split("## Behavior and reactions")[1]
            behavior_section = behavior_section.split("## Relationships")[0]
            self.assertIn("Challenges anyone who approaches the gate.", behavior_section)
            self.assertNotIn("Winter courier", behavior_section)
            hidden_section = actor_text.split("## Hidden")[1]
            self.assertIn("Winter courier", hidden_section)
            self.assertIn("Begins the adventure posted at the gate.", actor_text)
            self.assertNotIn("attitude:", actor_text)
            # Both places appear on the single shared actor card.
            for place in (gatehouse, yard):
                self.assertIn(f"cards/places/{place['id']}.md", actor_text)

            parley = by_title["Parley at the Gate"]
            situation_cards = sorted(
                path.name for path in (module / "cards" / "situations").iterdir()
            )
            self.assertEqual(len(situation_cards), 4)
            self.assertEqual(
                sum(name == f"{parley['id']}.md" for name in situation_cards), 1
            )
            index = load_json(module / "index.json")
            self.assertEqual(
                sum(
                    item["id"] == parley["id"] for item in index["records"]
                ),
                1,
            )
            situation_text = (
                module / "cards" / "situations" / f"{parley['id']}.md"
            ).read_text(encoding="utf-8")
            for heading in (
                "What the players perceive",
                "Pressure and stakes",
                "Likely approaches",
                "Actor reactions",
                "Consequences",
                "Completion conditions",
            ):
                self.assertIn(f"## {heading}", situation_text)
            self.assertIn('"type": "chosen"', situation_text)
            self.assertIn("Possible effects", situation_text)
            self.assertIn("never applies these", situation_text)
            self.assertIn("reveal-knowledge", situation_text)
            self.assertIn(gate_guard["id"], situation_text)

            rockfall = by_title["Rockfall in the Gate Arch"]
            self.assertEqual(
                rockfall["fields"]["possible_effects"][0]["effect"],
                "topology-state",
            )
            self.assertIn(
                rockfall["fields"]["possible_effects"][0]["target"],
                {node["id"] for node in audit["topology"]["nodes"]},
            )
            patrol = by_title["Wandering Patrol"]
            self.assertEqual(patrol["fields"]["repeat"]["mode"], "repeatable")
            self.assertEqual(
                patrol["fields"]["activation"]["type"], "random"
            )
            self.assertEqual(
                patrol["fields"]["possible_effects"][0]["target"], parley["id"]
            )

            # Bounded scene loading: available situations, none active.
            scene = resolve_scene(module, gatehouse["id"])
            self.assertIsNone(scene["active_situation"])
            self.assertEqual(
                sorted(item["id"] for item in scene["available_situations"]),
                sorted([parley["id"], rockfall["id"]]),
            )
            vigil = by_title["Crypt Vigil"]
            paths = {item["path"] for item in scene["files"]}
            self.assertNotIn(f"cards/situations/{vigil['id']}.md", paths)
            self.assertNotIn(f"cards/situations/{patrol['id']}.md", paths)
            self.assertTrue(all(path.startswith("cards/") for path in paths))
            self.assertEqual(
                scene["total_bytes"],
                sum(item["bytes"] for item in scene["files"]),
            )

            # Selecting the active situation adds only its required actors.
            active = resolve_scene(module, gatehouse["id"], parley["id"])
            self.assertEqual(active["active_situation"]["id"], parley["id"])
            self.assertFalse(
                active["active_situation"]["possible_effects"]["applied"]
            )
            self.assertEqual(
                len(active["active_situation"]["possible_effects"]["effects"]), 2
            )
            active_paths = {item["path"] for item in active["files"]}
            orders = by_title["The Winter Orders"]
            reaction_roll = by_title["Reaction Roll"]
            self.assertIn(f"cards/actors/{gate_guard['id']}.md", active_paths)
            self.assertIn(f"cards/knowledge/{orders['id']}.md", active_paths)
            self.assertIn(f"cards/procedures/{reaction_roll['id']}.md", active_paths)
            self.assertNotIn(f"cards/situations/{vigil['id']}.md", active_paths)
            self.assertNotIn(f"cards/situations/{patrol['id']}.md", active_paths)
            self.assertGreater(active["total_bytes"], scene["total_bytes"])

            # A patrol effect that may activate a parley does not load it.
            yard_active = resolve_scene(module, yard["id"], patrol["id"])
            yard_paths = {item["path"] for item in yard_active["files"]}
            self.assertNotIn(f"cards/situations/{parley['id']}.md", yard_paths)
            self.assertEqual(
                yard_active["active_situation"]["possible_effects"]["effects"][0][
                    "target"
                ],
                parley["id"],
            )

            with self.assertRaisesRegex(ExtractorError, "not available at"):
                resolve_scene(module, gatehouse["id"], vigil["id"])

            status_output = io.StringIO()
            with redirect_stdout(status_output):
                cli_module.command_status(
                    argparse.Namespace(
                        workspace_root=str(root),
                        json=True,
                        scene=gatehouse["id"],
                        situation=parley["id"],
                    )
                )
            resolved = json.loads(status_output.getvalue())
            self.assertEqual(resolved["active_situation"]["id"], parley["id"])

            duplicate = root / "module-second"
            assemble(module_input, duplicate, profile="release")
            self.assertEqual(content_tree_hash(module), content_tree_hash(duplicate))

    def test_situation_selection_requires_a_scene(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ExtractorError, "requires --scene"):
                cli_module.command_status(
                    argparse.Namespace(
                        workspace_root=temporary,
                        json=True,
                        scene=None,
                        situation="situation.example",
                    )
                )

    def test_clean_source_without_actors_or_situations_stays_valid(self) -> None:
        records = validate_content_response(
            content_response(
                [
                    record(
                        "location.area-1-hall",
                        "location",
                        {
                            "title": "Area 1: Hall",
                            "first_impression": "An empty hall.",
                            "topology_node": None,
                        },
                    )
                ]
            ),
            CONTENT_PACK,
            SOURCE,
        )
        result = resolve_operational_records(reviewed(records))
        self.assertEqual(result["record_errors"], [])


if __name__ == "__main__":
    unittest.main()
