from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
import zipfile


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "poc.py"
POC_FIXTURE = SCRIPT.parents[1] / "work" / "lair-of-the-lamb"
SPEC = importlib.util.spec_from_file_location("module_extractor_poc", SCRIPT)
assert SPEC and SPEC.loader
poc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(poc)


def save_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def valid_classification(page_count: int, digest: str) -> dict:
    return {
        "source_sha256": digest,
        "pages": [
            {
                "pdf_page": page,
                "classification": "none",
                "confidence": "high",
                "notes": "",
            }
            for page in range(1, page_count + 1)
        ],
    }


def map_response(digest: str = "a" * 64, pack_id: str = "map-001") -> dict:
    return {
        "kind": "map-evidence",
        "source_sha256": digest,
        "pack_id": pack_id,
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
                "confidence": "medium",
            },
        ],
        "edges": [
            {
                "from": "area-1",
                "to": "area-2",
                "type": "door",
                "direction": "both",
                "source_pages": [1],
                "confidence": "high",
            }
        ],
        "uncertainties": [
            {
                "object_id": "area-2",
                "description": "Label is faint.",
                "source_pages": [1],
            }
        ],
        "summary": {"nodes": 2, "edges": 1, "uncertainties": 1},
    }


def text_response(digest: str = "a" * 64, pack_id: str = "text-001") -> dict:
    return {
        "kind": "text-evidence",
        "source_sha256": digest,
        "pack_id": pack_id,
        "places": [
            {
                "id": "place.area-1",
                "title": "First Room",
                "description": "A bare chamber.",
                "occupants": ["actor.guard"],
                "hazards": [],
                "resources": ["A brass key"],
                "exits": ["area-2"],
                "topology_node": "area-1",
                "source_pages": [2],
            }
        ],
        "actors": [
            {
                "id": "actor.guard",
                "title": "Guard",
                "role": "Watches the room.",
                "goals": ["Raise the alarm"],
                "reactions": ["Questions strangers"],
                "mechanics": ["Armor 2"],
                "knowledge": ["fact.key"],
                "source_pages": [2],
            }
        ],
        "situations": [
            {
                "id": "situation.entry",
                "title": "Unexpected entry",
                "trigger": "The party opens the door.",
                "participants": ["actor.guard"],
                "stakes": ["An alarm"],
                "approaches": ["Talk", "Sneak"],
                "consequences": ["The guard runs"],
                "references": ["place.area-1"],
                "source_pages": [2],
            }
        ],
        "procedures": [
            {
                "id": "procedure.alarm",
                "title": "Alarm",
                "trigger": "A guard escapes.",
                "steps": ["Mark one alarm.", "Check reinforcements."],
                "state": {"alarm": 0},
                "source_pages": [2],
            }
        ],
        "knowledge": [
            {
                "id": "fact.key",
                "kind": "fact",
                "text": "The key opens the north door.",
                "truth_status": "confirmed",
                "subjects": ["place.area-1"],
                "source_pages": [2],
            }
        ],
        "uncertainties": [
            {
                "object_id": "actor.guard",
                "description": "Exact morale is unstated.",
                "source_pages": [2],
            }
        ],
        "summary": {
            "places": 1,
            "actors": 1,
            "situations": 1,
            "procedures": 1,
            "knowledge": 1,
            "uncertainties": 1,
        },
    }


class ParsingTests(unittest.TestCase):
    def test_pdfinfo_parser(self) -> None:
        parsed = poc.parse_pdfinfo("Title: Lair\nPages: 54\nEncrypted: no\n")
        self.assertEqual(parsed, {"pdf_title": "Lair", "pdf_pages": 54})
        with self.assertRaises(poc.PocError):
            poc.parse_pdfinfo("Title: broken\n")

    def test_pdfimages_list_parser(self) -> None:
        listing = """\
page   num  type   width height color comp bpc  enc interp  object ID x-ppi y-ppi size ratio
--------------------------------------------------------------------------------------------
   1     0 image     640   480  rgb     3   8  jpeg   no        12  0   72   72 10K 1.1%
   3     1 smask     100   200  gray    1   8  image  no        20  0  300  300 20K 2.0%
"""
        rows = poc.parse_pdfimages_list(listing)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["pdf_page"], 1)
        self.assertEqual(rows[1]["height"], 200)
        self.assertEqual(rows[1]["type"], "smask")

    def test_physical_page_split_and_consistency(self) -> None:
        self.assertEqual(poc.split_physical_pages("one\f\ftwo\f", 3), ["one", "", "two"])
        with self.assertRaisesRegex(poc.PocError, "page count mismatch"):
            poc.split_physical_pages("one\ftwo\f", 3)

    def test_dependency_check_lists_missing_tools(self) -> None:
        with mock.patch.object(
            poc.shutil, "which", side_effect=lambda name: None if name == "pdfimages" else name
        ):
            with self.assertRaisesRegex(poc.PocError, "pdfimages"):
                poc.require_tools()

    def test_corrupt_pdf_failure_is_user_facing(self) -> None:
        timings: list[dict] = []
        completed = subprocess.CompletedProcess(
            ["pdfinfo"], 1, stdout="", stderr="Syntax Error: May not be a PDF file"
        )
        with mock.patch.object(poc.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(poc.PocError, "May not be a PDF"):
                poc.run_command(("pdfinfo", "bad.bin"), timings, label="pdfinfo")

    def test_invalid_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(poc.PocError, "cannot read JSON"):
                poc.load_json(path)


class DeterministicArtifactTests(unittest.TestCase):
    def test_contact_sheet_and_zip_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            thumbnails = []
            for page, color in ((1, b"\xff\x00\x00"), (2, b"\x00\xff\x00")):
                path = root / f"page-{page}.png"
                path.write_bytes(poc.png_bytes(2, 3, color * 6))
                thumbnails.append((page, path))
            first = poc.make_contact_sheets(thumbnails, root / "one")[0].read_bytes()
            second = poc.make_contact_sheets(thumbnails, root / "two")[0].read_bytes()
            self.assertEqual(first, second)

            entries = {"b.txt": b"two", "a.txt": b"one"}
            poc.deterministic_zip(root / "a.zip", entries)
            poc.deterministic_zip(root / "b.zip", dict(reversed(list(entries.items()))))
            self.assertEqual((root / "a.zip").read_bytes(), (root / "b.zip").read_bytes())
            with zipfile.ZipFile(root / "a.zip") as archive:
                self.assertEqual(archive.namelist(), ["a.txt", "b.txt"])
                self.assertTrue(all(item.date_time == poc.ZIP_TIMESTAMP for item in archive.infolist()))

    def test_prepare_zip_contents_and_determinism(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work_root = root / "work"
            source = root / "input.pdf"
            source.write_bytes(b"%PDF-fake")

            def fake_run(arguments, timings, *, label):
                args = list(arguments)
                timings.append({"command": label, "seconds": 0.0, "returncode": 0})
                if label == "pdfinfo":
                    return subprocess.CompletedProcess(args, 0, "Title: Fake\nPages: 2\n", "")
                if label == "pdftotext":
                    Path(args[-1]).write_text("first\fsecond\f", encoding="utf-8")
                elif label == "pdfimages-list":
                    output = (
                        "page num type width height color comp bpc enc interp object ID x-ppi y-ppi\n"
                        "1 0 image 10 20 rgb 3 8 image no 1 0 72 72\n"
                    )
                    return subprocess.CompletedProcess(args, 0, output, "")
                elif label == "pdfimages-extract":
                    Path(args[-1] + "-000.ppm").write_bytes(b"P6\n1 1\n255\n\x00\x00\x00")
                elif label == "pdftoppm-thumbnails":
                    prefix = Path(args[-1])
                    for page in (1, 2):
                        Path(f"{prefix}-{page}.ppm").write_bytes(
                            b"P6\n2 2\n255\n" + bytes([page * 50, 0, 0]) * 4
                        )
                return subprocess.CompletedProcess(args, 0, "", "")

            arguments = argparse.Namespace(
                pdf=str(source), slug="fake-module", title="Fake Module"
            )
            with (
                mock.patch.object(poc, "WORK_ROOT", work_root),
                mock.patch.object(poc, "require_tools"),
                mock.patch.object(poc, "run_command", side_effect=fake_run),
            ):
                poc.prepare(arguments)
                first = (work_root / "fake-module" / "classification-pack.zip").read_bytes()
                (work_root / "fake-module" / "focused-packs").mkdir()
                (work_root / "fake-module" / "focus-manifest.json").write_text("{}")
                (work_root / "fake-module" / "focus-timings.json").write_text("{}")
                poc.prepare(arguments)
                second = (work_root / "fake-module" / "classification-pack.zip").read_bytes()

            self.assertEqual(first, second)
            self.assertFalse((work_root / "fake-module" / "focused-packs").exists())
            self.assertFalse((work_root / "fake-module" / "focus-manifest.json").exists())
            self.assertFalse((work_root / "fake-module" / "focus-timings.json").exists())
            with zipfile.ZipFile(work_root / "fake-module" / "classification-pack.zip") as archive:
                names = set(archive.namelist())
                self.assertIn("source.json", names)
                self.assertIn("signals.json", names)
                self.assertIn("image-inventory.json", names)
                self.assertIn("prompt.txt", names)
                self.assertIn("response-template.json", names)
                self.assertIn("thumbnails/page-0001.png", names)
                self.assertIn("contact-sheets/contact-sheet-001.png", names)
                self.assertNotIn("source.pdf", names)
                prompt = archive.read("prompt.txt").decode("utf-8")
                self.assertIn("downloadable file named classification.json", prompt)
                self.assertIn("no Markdown code fence", " ".join(prompt.split()))
                source_manifest = json.loads(archive.read("source.json"))
                self.assertNotIn(str(root), json.dumps(source_manifest))
            self.assertTrue((work_root / "fake-module" / "timings.json").is_file())


class ClassificationAndFocusTests(unittest.TestCase):
    def test_classification_missing_duplicate_range_and_hash(self) -> None:
        identity = {"sha256": "a" * 64, "pdf_pages": 3}
        good = valid_classification(3, identity["sha256"])
        self.assertEqual(len(poc.validate_classification(good, identity)), 3)

        cases = []
        missing = valid_classification(3, identity["sha256"])
        missing["pages"].pop()
        cases.append(missing)
        duplicate = valid_classification(3, identity["sha256"])
        duplicate["pages"][2]["pdf_page"] = 2
        cases.append(duplicate)
        out_of_range = valid_classification(3, identity["sha256"])
        out_of_range["pages"][2]["pdf_page"] = 4
        cases.append(out_of_range)
        mismatch = valid_classification(3, "b" * 64)
        cases.append(mismatch)
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(poc.PocError):
                    poc.validate_classification(case, identity)

    def test_recall_first_selection_and_pack_partitioning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work_root = root / "work"
            work = work_root / "slice"
            source = work / "source.pdf"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"fake-pdf")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            identity = {
                "filename": "slice.pdf",
                "sha256": digest,
                "title": "Slice",
                "pdf_title": "",
                "pdf_pages": 25,
            }
            save_json(work / "prepare-manifest.json", {"source": identity})
            save_json(work / "images" / "inventory.json", {"images": []})
            for page in range(1, 26):
                text = work / "text" / "pages" / f"page-{page:04d}.txt"
                text.parent.mkdir(parents=True, exist_ok=True)
                text.write_text(f"Page {page}", encoding="utf-8")
                thumb = work / "thumbnails" / f"page-{page:04d}.png"
                thumb.parent.mkdir(parents=True, exist_ok=True)
                thumb.write_bytes(b"thumbnail")
            classification = valid_classification(25, digest)
            for page in range(1, 12):
                classification["pages"][page - 1]["classification"] = "topology_map"
            classification["pages"][11]["classification"] = "mixed"
            classification["pages"][12]["classification"] = "uncertain"
            classification["pages"][13]["classification"] = "illustration"
            classification_path = root / "classification.json"
            save_json(classification_path, classification)

            def fake_run(arguments, timings, *, label):
                output = Path(list(arguments)[-1] + ".png")
                output.write_bytes(b"render")
                return subprocess.CompletedProcess(arguments, 0, "", "")

            args = argparse.Namespace(
                slug="slice",
                classification=str(classification_path),
                text_pages="1,2,3,4,5,6,7,8,9",
            )
            with (
                mock.patch.object(poc, "WORK_ROOT", work_root),
                mock.patch.object(poc, "require_tools"),
                mock.patch.object(poc, "run_command", side_effect=fake_run),
            ):
                poc.focus(args)

            manifest = json.loads((work / "focus-manifest.json").read_text())
            self.assertEqual(manifest["classified_map_pages"], list(range(1, 14)))
            map_packs = [pack for pack in manifest["packs"] if pack["kind"] == "map-evidence"]
            text_packs = [pack for pack in manifest["packs"] if pack["kind"] == "text-evidence"]
            self.assertEqual([len(pack["physical_pages"]) for pack in map_packs], [10, 3])
            self.assertEqual([len(pack["physical_pages"]) for pack in text_packs], [8, 1])
            self.assertTrue(all(len(pack["physical_pages"]) <= 10 for pack in map_packs))
            self.assertTrue(all(len(pack["physical_pages"]) <= 8 for pack in text_packs))
            with zipfile.ZipFile(work / "focused-packs" / "map-001.zip") as archive:
                prompt = archive.read("prompt.txt").decode("utf-8")
                normalized = " ".join(prompt.split())
                self.assertIn("downloadable file named map-001.json", normalized)
                self.assertIn("no Markdown code fence", normalized)


class EvidenceValidationTests(unittest.TestCase):
    identity = {"sha256": "a" * 64, "pdf_pages": 3}
    map_pack = {"pack_id": "map-001", "kind": "map-evidence", "physical_pages": [1]}
    text_pack = {"pack_id": "text-001", "kind": "text-evidence", "physical_pages": [2]}

    def test_map_edges_must_reference_nodes(self) -> None:
        value = map_response()
        value["edges"][0]["to"] = "area-99"
        with self.assertRaisesRegex(poc.PocError, "missing node"):
            poc.validate_map_response(value, self.map_pack, self.identity)

    def test_map_uncertainties_can_reference_legacy_or_explicit_edge_ids(self) -> None:
        legacy = map_response()
        legacy["uncertainties"][0]["object_id"] = "edge-area-1-area-2"
        validated = poc.validate_map_response(legacy, self.map_pack, self.identity)
        self.assertEqual(validated["edges"][0]["id"], "edge-area-1-area-2")
        self.assertEqual(validated["uncertainties"][0]["object_kind"], "edge")
        self.assertEqual(
            validated["uncertainties"][0]["observation_id"],
            "map-001.edge.edge-area-1-area-2",
        )
        self.assertEqual(
            validated["uncertainties"][0]["source_object_id"],
            "edge-area-1-area-2",
        )

        explicit = map_response()
        explicit["edges"][0]["id"] = "edge-main-door"
        explicit["uncertainties"][0]["object_id"] = "edge-main-door"
        validated = poc.validate_map_response(explicit, self.map_pack, self.identity)
        self.assertEqual(validated["edges"][0]["id"], "edge-area-1-area-2")
        self.assertEqual(validated["edges"][0]["source_id"], "edge-main-door")
        self.assertEqual(
            validated["uncertainties"][0]["object_id"], "edge-area-1-area-2"
        )

        unknown = map_response()
        unknown["uncertainties"][0]["object_id"] = "edge-missing"
        with self.assertRaisesRegex(poc.PocError, "unknown object"):
            poc.validate_map_response(unknown, self.map_pack, self.identity)

    def test_unsafe_and_duplicate_ids_are_rejected(self) -> None:
        unsafe = text_response()
        unsafe["places"][0]["id"] = "../escape"
        with self.assertRaisesRegex(poc.PocError, "unsafe"):
            poc.validate_text_response(unsafe, self.text_pack, self.identity)

        duplicate = text_response()
        duplicate["actors"][0]["id"] = "place.area-1"
        duplicate["uncertainties"][0]["object_id"] = "place.area-1"
        with self.assertRaisesRegex(poc.PocError, "duplicate object ID"):
            poc.validate_text_response(duplicate, self.text_pack, self.identity)

    def test_source_pages_must_be_physical_and_in_pack(self) -> None:
        value = text_response()
        value["places"][0]["source_pages"] = [3]
        with self.assertRaisesRegex(poc.PocError, "outside its focused pack"):
            poc.validate_text_response(value, self.text_pack, self.identity)

    def test_procedure_state_is_optional(self) -> None:
        value = text_response()
        del value["procedures"][0]["state"]
        validated = poc.validate_text_response(value, self.text_pack, self.identity)
        self.assertNotIn("state", validated["procedures"][0])


class AssemblyTests(unittest.TestCase):
    def make_fixture(self, root: Path) -> tuple[Path, Path, Path]:
        work_root = root / "work"
        work = work_root / "slice"
        identity = {
            "filename": "source.pdf",
            "sha256": "a" * 64,
            "title": "Test Module",
            "pdf_title": "Original Test Title",
            "pdf_pages": 3,
        }
        focus = {
            "source": identity,
            "selected_text_pages": [2],
            "classified_map_pages": [1],
            "classified_pages": [],
            "packs": [
                {"pack_id": "map-001", "kind": "map-evidence", "physical_pages": [1]},
                {"pack_id": "text-001", "kind": "text-evidence", "physical_pages": [2]},
            ],
        }
        save_json(work / "focus-manifest.json", focus)
        map_path = root / "map.json"
        text_path = root / "text.json"
        save_json(map_path, map_response())
        save_json(text_path, text_response())
        return work_root, map_path, text_path

    def run_assemble(
        self, work_root: Path, evidence: list[Path], output: Path
    ) -> None:
        args = argparse.Namespace(
            slug="slice", evidence=[str(path) for path in evidence], output=str(output)
        )
        with mock.patch.object(poc, "WORK_ROOT", work_root):
            poc.assemble(args)

    def test_missing_unknown_duplicate_pack_and_hash_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work_root, map_path, text_path = self.make_fixture(root)
            with self.assertRaisesRegex(poc.PocError, "missing evidence"):
                self.run_assemble(work_root, [map_path], root / "missing")

            unknown = root / "unknown.json"
            value = text_response(pack_id="text-999")
            save_json(unknown, value)
            with self.assertRaisesRegex(poc.PocError, "unknown pack_id"):
                self.run_assemble(work_root, [map_path, unknown], root / "unknown-out")

            duplicate = root / "duplicate.json"
            save_json(duplicate, map_response())
            with self.assertRaisesRegex(poc.PocError, "duplicate evidence"):
                self.run_assemble(
                    work_root, [map_path, duplicate, text_path], root / "duplicate-out"
                )

            mismatch = root / "mismatch.json"
            save_json(mismatch, text_response(digest="b" * 64))
            with self.assertRaisesRegex(poc.PocError, "source_sha256"):
                self.run_assemble(work_root, [map_path, mismatch], root / "mismatch-out")

    def test_deterministic_rendering_and_overwrite_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work_root, map_path, text_path = self.make_fixture(root)
            first = root / "module-one"
            second = root / "module-two"
            self.run_assemble(work_root, [text_path, map_path], first)
            self.run_assemble(work_root, [map_path, text_path], second)

            def snapshot(directory: Path) -> dict[str, bytes]:
                return {
                    str(path.relative_to(directory)): path.read_bytes()
                    for path in sorted(directory.rglob("*"))
                    if path.is_file()
                }

            self.assertEqual(snapshot(first), snapshot(second))
            manifest = (first / "manifest.yaml").read_text(encoding="utf-8")
            self.assertIn("experiment: true", manifest)
            self.assertIn("incomplete: true", manifest)
            self.assertTrue((first / "places" / "place.area-1.md").is_file())
            self.assertTrue((first / "actors" / "actor.guard.md").is_file())
            self.assertTrue((first / "situations" / "situation.entry.md").is_file())
            self.assertTrue((first / "procedures" / "procedure.alarm.yaml").is_file())
            self.assertTrue((first / "knowledge" / "facts.yaml").is_file())
            self.assertTrue((first / "topology" / "graph.yaml").is_file())

            with self.assertRaisesRegex(poc.PocError, "refusing to overwrite"):
                self.run_assemble(work_root, [map_path, text_path], first)

    def test_map_reconciliation_preserves_variants_and_provenance(self) -> None:
        identity = {"sha256": "a" * 64, "pdf_pages": 3}
        first_pack = {
            "pack_id": "map-001",
            "kind": "map-evidence",
            "physical_pages": [1],
        }
        second_pack = {
            "pack_id": "map-002",
            "kind": "map-evidence",
            "physical_pages": [3],
        }
        first_response = map_response()
        second_response = map_response(pack_id="map-002")
        for node in second_response["nodes"]:
            node["source_pages"] = [3]
            node["label"] += " detail"
        second_response["edges"][0].update(
            {
                "id": "edge-detailed-door",
                "from": "area-2",
                "to": "area-1",
                "source_pages": [3],
            }
        )
        second_response["uncertainties"][0].update(
            {"object_id": "edge-area-2-area-1", "source_pages": [3]}
        )
        maps = [
            poc.validate_map_response(first_response, first_pack, identity),
            poc.validate_map_response(second_response, second_pack, identity),
        ]
        topology = poc.reconcile_map_observations(maps)
        self.assertEqual(topology, poc.reconcile_map_observations(list(reversed(maps))))
        area_one = next(node for node in topology["nodes"] if node["id"] == "area-1")
        self.assertEqual(area_one["labels"], ["1", "1 detail"])
        self.assertEqual(len(area_one["observations"]), 2)
        self.assertEqual(area_one["source_pages"], [1, 3])
        self.assertEqual(len(topology["edges"]), 1)
        self.assertEqual(topology["edges"][0]["status"], "consistent")
        self.assertEqual(len(topology["edges"][0]["variants"]), 1)
        self.assertEqual(
            len(topology["edges"][0]["variants"][0]["observations"]), 2
        )
        self.assertEqual(
            {
                item["source_id"]
                for item in topology["edges"][0]["variants"][0]["observations"]
            },
            {"edge-area-1-area-2", "edge-detailed-door"},
        )
        detailed_observation = next(
            item
            for item in topology["edges"][0]["variants"][0]["observations"]
            if item["pack_id"] == "map-002"
        )
        self.assertEqual(
            (detailed_observation["from"], detailed_observation["to"]),
            ("area-2", "area-1"),
        )
        self.assertEqual(
            topology["uncertainties"][1]["source_object_id"],
            "edge-area-2-area-1",
        )
        self.assertEqual(topology["uncertainties"][1]["object_kind"], "edge")

        second_response["edges"][0].update(
            {"from": "area-1", "to": "area-2", "type": "corridor", "direction": "unknown"}
        )
        maps[1] = poc.validate_map_response(
            second_response, second_pack, identity
        )
        topology = poc.reconcile_map_observations(maps)
        self.assertEqual(topology["edges"][0]["status"], "conflict")
        self.assertEqual(
            topology["edges"][0]["conflict_fields"], ["type", "direction"]
        )
        self.assertEqual(
            topology["conflicts"],
            [
                {
                    "edge_id": "edge-area-1-area-2",
                    "endpoints": ["area-1", "area-2"],
                    "fields": ["type", "direction"],
                }
            ],
        )

    @unittest.skipUnless(
        (POC_FIXTURE / "focus-manifest.json").is_file(),
        "optional Lair v0 fixture is not installed",
    )
    def test_completed_poc_responses_are_assembly_regression_fixtures(self) -> None:
        work = POC_FIXTURE
        focus = json.loads((work / "focus-manifest.json").read_text(encoding="utf-8"))
        classification_path = work / "responses" / "classification.json"
        self.assertEqual(
            focus["classification_response_sha256"],
            poc.sha256_file(classification_path),
        )
        responses = {
            path.stem: json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((work / "responses").glob("*.json"))
            if path.stem != "classification"
        }
        maps = []
        for pack in focus["packs"]:
            if pack["kind"] == "map-evidence":
                maps.append(
                    poc.validate_map_response(
                        responses[pack["pack_id"]], pack, focus["source"]
                    )
                )
        topology = poc.reconcile_map_observations(maps)
        self.assertEqual(len(topology["nodes"]), 64)
        self.assertEqual(
            sum(len(node["observations"]) for node in topology["nodes"]), 103
        )
        self.assertEqual(len(topology["edges"]), 76)
        self.assertEqual(
            sum(
                len(variant["observations"])
                for edge in topology["edges"]
                for variant in edge["variants"]
            ),
            118,
        )
        self.assertEqual(len(topology["conflicts"]), 13)
        area_nine = next(node for node in topology["nodes"] if node["id"] == "area-9")
        self.assertEqual(area_nine["labels"], ["9", "9 FOUNTAIN"])
        conflict = next(
            item
            for item in topology["conflicts"]
            if item["edge_id"] == "edge-area-44-area-45"
        )
        self.assertEqual(conflict["fields"], ["type"])
        edge_uncertainties = [
            item
            for item in topology["uncertainties"]
            if item["object_kind"] == "edge"
        ]
        self.assertEqual(len(edge_uncertainties), 3)

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "module"
            args = argparse.Namespace(
                slug="lair-of-the-lamb",
                evidence=[
                    str(work / "responses" / "map-001.json"),
                    str(work / "responses" / "map-002.json"),
                    str(work / "responses" / "text-001.json"),
                ],
                output=str(output),
            )
            poc.assemble(args)
            manifest = (output / "manifest.yaml").read_text(encoding="utf-8")
            graph = (output / "topology" / "graph.yaml").read_text(encoding="utf-8")
            self.assertIn("node_observations: 103", manifest)
            self.assertIn("edge_observations: 118", manifest)
            self.assertIn("conflicts: 13", manifest)
            self.assertIn('observation_id: "map-002.node.area-9"', graph)
            self.assertIn('edge_id: "edge-area-44-area-45"', graph)
            self.assertIn('object_kind: "edge"', graph)


if __name__ == "__main__":
    unittest.main()
