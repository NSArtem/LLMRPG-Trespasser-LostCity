from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPOSITORY_ROOT / "scripts" / "validate_repo.py"
SPEC = importlib.util.spec_from_file_location("campaign_validator", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class CampaignBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.patch = mock.patch.object(validator, "REPO_ROOT", self.root)
        self.patch.start()

    def tearDown(self) -> None:
        self.patch.stop()
        self.temporary.cleanup()

    def write(self, relative: str, text: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def current(
        self,
        *,
        status: str = "active",
        module_id: str | None = "tiny-module",
        module_place_id: str | None = "place.entry",
    ) -> Path:
        checkpoint = "" if status == "preparation" else "cp-0001"
        scene = "" if status == "preparation" else "scene-0001"
        journal = "" if status == "preparation" else "journal.entry-0001"
        return self.write(
            "CURRENT.md",
            "---\n"
            f"checkpoint_id: {checkpoint}\n"
            f"active_scene_id: {scene}\n"
            f"active_journal_id: {journal}\n"
            f"campaign_status: {status}\n"
            "last_activity_at:\n"
            f"module_id: {module_id or ''}\n"
            f"module_place_id: {module_place_id or ''}\n"
            "---\n",
        )

    def tiny_module(
        self,
        *,
        record_type: str = "place",
        with_card: bool = True,
        marker_module_id: str = "tiny-module",
        play_contract: str = "module-play/v1",
        verification: str = "verified",
    ) -> None:
        self.write(
            "module/GENERATED_OUTPUT.json",
            json.dumps(
                {
                    "play_contract": play_contract,
                    "verification": verification,
                    "module_id": marker_module_id,
                }
            ),
        )
        self.write("module/MODULE.md", "# Tiny module\n")
        self.write(
            "module/index.json",
            json.dumps(
                {
                    "records": [
                        {
                            "id": "place.entry",
                            "type": record_type,
                            "path": "cards/places/place.entry.md",
                        }
                    ]
                }
            ),
        )
        if with_card:
            self.write("module/cards/places/place.entry.md", "# Entry\n")

    def checkpoint(self, module_place_id: str | None = "place.entry") -> Path:
        value = module_place_id if module_place_id is not None else "null"
        return self.write(
            "checkpoints/cp-0001.yaml",
            "current_scene:\n"
            "  location: location.entry\n"
            f"  module_place_id: {value}\n",
        )

    def location(self, module_ref: str | None = "place.entry") -> Path:
        value = module_ref if module_ref is not None else "null"
        return self.write(
            "locations/entry.md",
            "---\n"
            "id: location.entry\n"
            "type: location\n"
            "name: Entry\n"
            f"module_ref: {value}\n"
            "---\n",
        )

    def module_with_override_targets(self) -> None:
        self.tiny_module()
        self.write(
            "module/index.json",
            json.dumps(
                {
                    "records": [
                        {
                            "id": "place.entry",
                            "type": "place",
                            "path": "cards/places/place.entry.md",
                        },
                        {
                            "id": "actor.guard",
                            "type": "actor",
                            "path": "cards/actors/actor.guard.md",
                        },
                    ]
                }
            ),
        )
        self.write(
            "module/topology.yaml",
            json.dumps(
                {
                    "nodes": [
                        {"id": "place.entry"},
                        {"id": "place.next"},
                    ],
                    "passages": [
                        {
                            "id": "edge.entry-next",
                            "from": "place.entry",
                            "to": "place.next",
                        }
                    ],
                }
            ),
        )

    def overrides(self, rows: str) -> Path:
        return self.write(
            "gm/module-overrides.md",
            "# Overrides\n\n"
            "| ID | Object / place | New canonical state | Reason | Checkpoint | Related files |\n"
            "| --- | --- | --- | --- | --- | --- |\n"
            f"{rows}\n",
        )

    def validate(self, paths: list[Path]) -> list[str]:
        texts = {
            path: path.read_text(encoding="utf-8")
            for path in paths
            if path.is_file() and path.suffix in {".md", ".yaml"}
        }
        errors: list[str] = []
        validator.check_module_campaign_binding(texts, errors)
        validator.check_module_override_targets(texts, errors)
        return errors

    def bound_paths(self) -> list[Path]:
        current = self.current()
        self.tiny_module()
        checkpoint = self.checkpoint()
        location = self.location()
        return [current, checkpoint, location]

    def test_preparation_state_allows_empty_module_fields(self) -> None:
        current = self.current(
            status="preparation", module_id=None, module_place_id=None
        )
        self.assertEqual(self.validate([current]), [])

    def test_preparation_state_rejects_populated_module_fields(self) -> None:
        current = self.current(status="preparation")
        errors = self.validate([current])
        self.assertTrue(any("состоянии preparation" in item for item in errors))

    def test_active_module_free_campaign_is_valid(self) -> None:
        current = self.current(module_id=None, module_place_id=None)
        self.assertEqual(self.validate([current]), [])

    def test_checkpoint_binding_cannot_be_dropped_from_current(self) -> None:
        current = self.current(module_id=None, module_place_id=None)
        checkpoint = self.checkpoint()
        errors = self.validate([current, checkpoint])
        self.assertTrue(any("CURRENT.module_id" in item for item in errors))

    def test_valid_module_and_place_binding(self) -> None:
        self.assertEqual(self.validate(self.bound_paths()), [])

    def test_unknown_module_place_id_is_rejected(self) -> None:
        paths = self.bound_paths()
        paths[0] = self.current(module_place_id="place.unknown")
        errors = self.validate(paths)
        self.assertTrue(any("не найден в module/index.json" in item for item in errors))

    def test_non_place_record_is_rejected(self) -> None:
        paths = self.bound_paths()
        self.tiny_module(record_type="actor")
        errors = self.validate(paths)
        self.assertTrue(any("ожидался place" in item for item in errors))

    def test_missing_place_card_is_rejected(self) -> None:
        paths = self.bound_paths()
        (self.root / "module/cards/places/place.entry.md").unlink()
        errors = self.validate(paths)
        self.assertTrue(any("карточка места" in item for item in errors))

    def test_module_identity_mismatch_is_rejected(self) -> None:
        paths = self.bound_paths()
        self.tiny_module(marker_module_id="other-module")
        errors = self.validate(paths)
        self.assertTrue(any("не совпадает с module/GENERATED_OUTPUT" in item for item in errors))

    def test_location_module_ref_mismatch_is_rejected(self) -> None:
        paths = self.bound_paths()
        paths[-1] = self.location("place.other")
        errors = self.validate(paths)
        self.assertTrue(any("module_ref" in item for item in errors))

    def test_checkpoint_movement_must_update_current(self) -> None:
        paths = self.bound_paths()
        paths[1] = self.checkpoint("place.next")
        errors = self.validate(paths)
        self.assertTrue(
            any("current_scene.module_place_id" in item for item in errors)
        )

    def test_incompatible_or_unverified_output_is_rejected(self) -> None:
        paths = self.bound_paths()
        self.tiny_module(play_contract="module-play/v2", verification="unverified")
        errors = self.validate(paths)
        self.assertTrue(any("play_contract" in item for item in errors))
        self.assertTrue(any("verification" in item for item in errors))

    def test_override_record_node_and_edge_ids_are_validated(self) -> None:
        paths = self.bound_paths()
        self.module_with_override_targets()
        override = self.overrides(
            "| `actor.guard` | Guard | Dead | Combat | `cp-0001` | `npcs/guard.md` |\n"
            "| `place.next` | Next room | Flooded | Spell | `cp-0001` | — |\n"
            "| `edge.entry-next` | Passage | Open | Forced entry | `cp-0001` | — |"
        )
        errors = self.validate(paths + [override])
        self.assertEqual(errors, [])

    def test_invalid_override_target_is_reported(self) -> None:
        paths = self.bound_paths()
        self.module_with_override_targets()
        override = self.overrides(
            "| `actor.missing` | Missing | Gone | Test | `cp-0001` | — |"
        )
        errors = self.validate(paths + [override])
        self.assertTrue(any("invalid target ID 'actor.missing'" in item for item in errors))

    def test_populated_overrides_without_module_binding_are_rejected(self) -> None:
        current = self.current(module_id=None, module_place_id=None)
        override = self.overrides(
            "| `actor.missing` | Missing | Gone | Test | `cp-0001` | — |"
        )
        errors = self.validate([current, override])
        self.assertTrue(any("without CURRENT.module_id" in item for item in errors))

    def test_root_and_template_contracts_are_synchronized(self) -> None:
        for relative in (
            "CURRENT.md",
            "checkpoints/checkpoint-template.yaml",
            "checkpoints/README.md",
            "locations/location-template.md",
            "npcs/npc-template.md",
            "rules/precedence.md",
            "gm/module-overrides.md",
        ):
            self.assertEqual(
                (REPOSITORY_ROOT / relative).read_text(encoding="utf-8"),
                (REPOSITORY_ROOT / "templates" / relative).read_text(
                    encoding="utf-8"
                ),
                relative,
            )

    def test_play_instructions_use_only_the_stable_readiness_contract(
        self,
    ) -> None:
        for relative in (
            "MANIFEST.md",
            "chatgpt-project/SETUP_AND_PROMPTS.md",
            "rules/precedence.md",
        ):
            text = (REPOSITORY_ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("module-play/v1", text, relative)
            self.assertIn("module/MODULE.md", text, relative)
            self.assertIn("module/index.json", text, relative)
            self.assertNotIn(
                "module-extractor-generated-output/v", text, relative
            )


if __name__ == "__main__":
    unittest.main()
