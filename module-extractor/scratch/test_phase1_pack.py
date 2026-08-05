#!/usr/bin/env python3
"""Tests for T1.1. Reads the committed unit table; no PDF and no model."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))

import phase1_pack  # noqa: E402
from phase1_pack import (EXAMPLE_UNIT, SCHEMA, UNITS, _load_units,  # noqa: E402
                         _manifest, _unit_file, build)


class ManifestTests(unittest.TestCase):
    """The header and the rows must describe the same columns."""

    def setUp(self) -> None:
        self.units = [_load_units()[unit_id] for unit_id in UNITS]
        self.lines = _manifest(self.units).splitlines()

    def test_every_row_has_the_columns_its_header_promises(self) -> None:
        """The T1.1 defect: pages and labels were written transposed.

        ``labels`` is empty until T2.4, so the swap filed each unit's pages
        under ``labels`` and left ``pages`` blank -- in a pack whose prompt
        requires the model to emit ``#unit,<id>,pages,<page-list>``.
        """
        header = self.lines[0].split(",")
        self.assertEqual(header,
                         ["unit_id", "pages", "labels", "text_bytes", "heading"])
        for row, unit in zip(self.lines[1:], self.units):
            fields = row.split(",", len(header) - 1)
            self.assertEqual(len(fields), len(header), row)
            values = dict(zip(header, fields))
            self.assertEqual(values["unit_id"], unit["unit_id"])
            self.assertEqual(values["pages"],
                             ";".join(str(page) for page in unit["pages"]))
            self.assertEqual(values["text_bytes"], str(unit["text_bytes"]))
            self.assertEqual(values["heading"], unit["heading"])

    def test_pages_are_never_empty(self) -> None:
        for row in self.lines[1:]:
            self.assertTrue(row.split(",")[1], row)

    def test_free_text_is_last_so_a_comma_needs_no_quoting(self) -> None:
        unit = dict(self.units[0], heading="Area 3, the vestibule")
        row = _manifest([unit]).splitlines()[1]
        self.assertEqual(row.split(",", 4)[4], "Area 3, the vestibule")


class UnitFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.table = _load_units()

    def test_the_header_never_opens_a_line_with_a_hash(self) -> None:
        """``#`` opens a structural row in the very format being taught."""
        for unit_id in UNITS:
            text = _unit_file(self.table[unit_id])
            for line in text.split("---", 1)[0].splitlines():
                self.assertFalse(line.startswith("#"), (unit_id, line))

    def test_the_heading_path_travels_with_the_unit(self) -> None:
        """Two tables on page 18 share a heading; only the path separates them."""
        text = _unit_file(self.table["p18.active-encounters-2"])
        self.assertIn("section: ", text)
        self.assertIn("Encounter Table (Lamb Dead)", text)

    def test_the_body_is_the_unit_text_verbatim(self) -> None:
        for unit_id in UNITS:
            unit = self.table[unit_id]
            body = _unit_file(unit).split("---\n", 1)[1]
            self.assertEqual(body.rstrip("\n"), unit["text"].rstrip())

    def test_no_classification_is_leaked_to_the_model(self) -> None:
        """Concerns are Stage 3 output; Stage 5 is not asked to agree with them."""
        for unit_id in UNITS:
            self.assertNotIn("label", _unit_file(self.table[unit_id]))


class SelectionTests(unittest.TestCase):
    def test_every_selected_unit_exists(self) -> None:
        table = _load_units()
        for unit_id in (*UNITS, EXAMPLE_UNIT):
            self.assertIn(unit_id, table)

    def test_the_worked_example_is_not_in_the_pack(self) -> None:
        """Otherwise T1.3 measures the model's copying, not its compliance."""
        self.assertNotIn(EXAMPLE_UNIT, UNITS)

    def test_the_selection_covers_the_material_t1_1_asks_for(self) -> None:
        table = _load_units()
        selected = [table[unit_id] for unit_id in UNITS]
        self.assertTrue(any(unit["keyed_area"] for unit in selected), "keyed room")
        self.assertGreaterEqual(len(selected), 5)
        self.assertLessEqual(len(selected), 8)

    def test_no_selected_unit_is_a_stub(self) -> None:
        """A truncated unit cannot tell a format failure from an empty one."""
        table = _load_units()
        for unit_id in UNITS:
            self.assertGreater(table[unit_id]["text_bytes"], 100, unit_id)


class SchemaTests(unittest.TestCase):
    def test_visibility_is_not_also_a_predicate(self) -> None:
        """A fact hidden two ways can be hidden inconsistently."""
        table = SCHEMA.split("## Predicates", 1)[1]
        predicates = {row.split("|")[1].strip().strip("`")
                      for row in table.splitlines() if row.startswith("| `")}
        self.assertNotIn("hidden", predicates)
        self.assertNotIn("public", predicates)
        self.assertNotIn("discoverable", predicates)

    def test_option_slots_are_not_predicates(self) -> None:
        table = SCHEMA.split("## Predicates", 1)[1]
        predicates = {row.split("|")[1].strip().strip("`")
                      for row in table.splitlines() if row.startswith("| `")}
        self.assertNotIn("option", predicates)
        self.assertNotIn("result", predicates)

    def test_every_predicate_declares_arity_and_value_kind(self) -> None:
        table = SCHEMA.split("## Predicates", 1)[1].split("## Structured", 1)[0]
        rows = [row for row in table.splitlines() if row.startswith("| `")]
        self.assertTrue(rows)
        for row in rows:
            cells = [cell.strip() for cell in row.strip("|").split("|")]
            self.assertIn(cells[2], {"scalar", "list"}, row)
            self.assertIn(cells[3], {"text", "**JSON**"}, row)

    def test_every_structured_predicate_declares_its_key_set(self) -> None:
        table = SCHEMA.split("## Predicates", 1)[1].split("## Structured", 1)[0]
        structured = {row.strip("|").split("|")[0].strip().strip("`")
                      for row in table.splitlines()
                      if row.startswith("| `") and "**JSON**" in row}
        keys = SCHEMA.split("## Structured values", 1)[1]
        for predicate in structured:
            self.assertRegex(keys, rf"(?m)^{predicate}\s+\{{", predicate)


class PackTests(unittest.TestCase):
    def test_the_pack_is_byte_identical_across_builds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = build(Path(tmp) / "a.zip")
            second = build(Path(tmp) / "b.zip")
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_the_pack_carries_everything_the_model_needs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(build(Path(tmp) / "a.zip")) as archive:
                names = set(archive.namelist())
        self.assertEqual(
            names,
            {"README.md", "prompt.md", "schema.md", "units.csv"}
            | {f"units/{unit_id}.txt" for unit_id in UNITS},
        )

    def test_a_missing_unit_stops_the_build(self) -> None:
        original = phase1_pack.UNITS
        phase1_pack.UNITS = ("p99.does-not-exist",)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(SystemExit):
                    build(Path(tmp) / "a.zip")
        finally:
            phase1_pack.UNITS = original


if __name__ == "__main__":
    unittest.main()
