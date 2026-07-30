from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


EXTRACTOR_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXTRACTOR_ROOT))

from module_extractor.errors import ExtractorError  # noqa: E402
from module_extractor.scene import resolve_scene  # noqa: E402


class BoundedSceneLoadingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.module = Path(self.temporary.name) / "module"
        self._build_module()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write(self, relative: str, content: str) -> None:
        path = self.module / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _build_module(self) -> None:
        self.write(
            "GENERATED_OUTPUT.json",
            json.dumps(
                {
                    "play_contract": "module-play/v1",
                    "verification": "verified",
                    "module_id": "synthetic-module",
                }
            ),
        )
        self.write("MODULE.md", "# Synthetic module\n")
        self.write("audit/should-not-load.md", "audit\n")
        self.write("source.pdf", "pdf\n")

        cards = {
            "cards/places/entry.md": "entry place\n",
            "cards/places/next.md": "next place\n",
            "cards/actors/guard.md": "guard\n",
            "cards/actors/unrelated.md": "unrelated\n",
            "cards/situations/challenge.md": "challenge\n",
            "cards/procedures/entry.md": "procedure\n",
            "cards/knowledge/secret.md": "knowledge\n",
        }
        for path, content in cards.items():
            self.write(path, content)

        def place(
            identifier: str,
            path: str,
            node: str,
            load_with: dict[str, list[str]],
        ) -> dict:
            return {
                "id": identifier,
                "type": "place",
                "path": path,
                "topology_node": node,
                "load_with": load_with,
            }

        empty = {"actors": [], "situations": [], "procedures": [], "knowledge": []}
        self.write(
            "index.json",
            json.dumps(
                {
                    "records": [
                        place(
                            "place.entry",
                            "cards/places/entry.md",
                            "node.entry",
                            {
                                "actors": ["cards/actors/guard.md"],
                                "situations": ["cards/situations/challenge.md"],
                                "procedures": ["cards/procedures/entry.md"],
                                "knowledge": ["cards/knowledge/secret.md"],
                            },
                        ),
                        place("place.next", "cards/places/next.md", "node.next", empty),
                        {
                            "id": "actor.guard",
                            "type": "actor",
                            "path": "cards/actors/guard.md",
                        },
                        {
                            "id": "actor.unrelated",
                            "type": "actor",
                            "path": "cards/actors/unrelated.md",
                        },
                        {
                            "id": "situation.challenge",
                            "type": "situation",
                            "path": "cards/situations/challenge.md",
                            "load_with": {
                                "actors": ["cards/actors/guard.md"],
                                "procedures": ["cards/procedures/entry.md"],
                                "knowledge": ["cards/knowledge/secret.md"],
                            },
                        },
                        {
                            "id": "procedure.entry",
                            "type": "procedure",
                            "path": "cards/procedures/entry.md",
                        },
                        {
                            "id": "knowledge.secret",
                            "type": "knowledge",
                            "path": "cards/knowledge/secret.md",
                        },
                    ]
                }
            ),
        )
        self.write(
            "topology.yaml",
            json.dumps(
                {
                    "nodes": [{"id": "node.entry"}, {"id": "node.next"}],
                    "passages": [
                        {
                            "id": "edge.entry-next",
                            "from": "node.entry",
                            "to": "node.next",
                        }
                    ],
                }
            ),
        )

    def test_cold_start_is_one_bounded_direct_scene_bundle(self) -> None:
        scene = resolve_scene(self.module, "place.entry")
        self.assertEqual(scene["place_id"], "place.entry")
        self.assertEqual(
            {item["path"] for item in scene["files"]},
            {
                "cards/places/entry.md",
                "cards/actors/guard.md",
                "cards/situations/challenge.md",
                "cards/procedures/entry.md",
                "cards/knowledge/secret.md",
            },
        )
        self.assertEqual(
            scene["topology"]["adjacent_edges"][0]["id"], "edge.entry-next"
        )
        self.assertNotIn("cards/actors/unrelated.md", {item["path"] for item in scene["files"]})
        self.assertFalse(any(item["path"].startswith("audit/") for item in scene["files"]))
        self.assertFalse(any(item["path"].endswith(".pdf") for item in scene["files"]))

    def test_place_change_changes_the_next_bundle(self) -> None:
        scene = resolve_scene(self.module, "place.next")
        self.assertEqual(scene["place_id"], "place.next")
        self.assertEqual(
            [item["path"] for item in scene["files"]],
            ["cards/places/next.md"],
        )

    def test_unknown_place_and_unready_module_stop_loading(self) -> None:
        with self.assertRaisesRegex(ExtractorError, "unknown place ID"):
            resolve_scene(self.module, "place.unknown")

        marker = json.loads(
            (self.module / "GENERATED_OUTPUT.json").read_text(encoding="utf-8")
        )
        marker["verification"] = "unverified"
        (self.module / "GENERATED_OUTPUT.json").write_text(
            json.dumps(marker), encoding="utf-8"
        )
        with self.assertRaisesRegex(ExtractorError, "not play-ready"):
            resolve_scene(self.module, "place.entry")


if __name__ == "__main__":
    unittest.main()
