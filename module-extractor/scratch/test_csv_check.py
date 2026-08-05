#!/usr/bin/env python3
"""Tests for the T1.3 compliance checker.

The compliance figures are only worth as much as the checker producing them, so
every violation category it can report has a test that provokes it and a test
that does not.
"""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from csv_check import check, clean, parse_schema  # noqa: E402
from phase1_pack import SCHEMA  # noqa: E402


SCHEMA_OBJECT = parse_schema(SCHEMA)
EXPECTED = ["u1"]

HEAD = "#unit,u1,pages,31\n#entity,a1,place,A ROOM\n"


def report(body: str, expected=EXPECTED):
    return check(HEAD + body, SCHEMA_OBJECT, expected, "test")


class SchemaParsingTests(unittest.TestCase):
    def test_the_pack_schema_yields_a_usable_vocabulary(self) -> None:
        self.assertIn("contents", SCHEMA_OBJECT.predicates)
        self.assertIn("place", SCHEMA_OBJECT.kinds)
        self.assertIn("discoverable", SCHEMA_OBJECT.visibilities)
        self.assertIn("", SCHEMA_OBJECT.visibilities)
        self.assertIn("action", SCHEMA_OBJECT.option_slots)

    def test_arity_and_value_kind_are_recovered(self) -> None:
        self.assertEqual(SCHEMA_OBJECT.predicates["contents"][0], "list")
        self.assertEqual(SCHEMA_OBJECT.predicates["dimensions"][0], "scalar")
        self.assertIn("exit", SCHEMA_OBJECT.json_predicates)
        self.assertNotIn("contents", SCHEMA_OBJECT.json_predicates)

    def test_structured_key_sets_are_recovered(self) -> None:
        self.assertEqual(SCHEMA_OBJECT.structured["cycle"],
                         {"fall_ft", "fall_s", "rest_s", "then"})


class CleanTests(unittest.TestCase):
    def test_a_fence_is_stripped_and_counted(self) -> None:
        lines, fences = clean("```csv\na,b,c,d\n```\n")
        self.assertEqual(lines, ["a,b,c,d"])
        self.assertEqual(fences, 2)

    def test_blank_lines_are_dropped_and_content_is_not(self) -> None:
        lines, _ = clean("a,b,c,d\n\n  \ne,f,g,h\n")
        self.assertEqual(lines, ["a,b,c,d", "e,f,g,h"])


class ViolationTests(unittest.TestCase):
    def test_a_clean_response_has_no_violations(self) -> None:
        result = report("a1,contents,public,A chair, a table, and a rug.\n")
        self.assertEqual(dict(result.counts), {})
        self.assertEqual(result.rows, 3)

    def test_a_comma_in_the_free_field_is_not_a_violation(self) -> None:
        """The whole point of splitting on the first three commas only."""
        result = report('a1,contents,public,Rope, 50\', and a lamp "borrowed".\n')
        self.assertEqual(dict(result.counts), {})

    def test_too_few_fields_is_counted(self) -> None:
        self.assertEqual(report("a1,contents,public\n").counts["field count"], 1)

    def test_an_unknown_predicate_is_counted(self) -> None:
        self.assertEqual(report("a1,smells,public,Damp.\n").counts["unknown predicate"], 1)

    def test_an_unknown_visibility_is_counted(self) -> None:
        self.assertEqual(report("a1,contents,secret,A chair.\n").counts["unknown visibility"], 1)

    def test_an_unknown_entity_kind_is_counted(self) -> None:
        body = "#entity,x1,widget,A widget\n"
        self.assertEqual(report(body).counts["entity kind"], 1)

    def test_an_unknown_option_slot_is_counted(self) -> None:
        self.assertEqual(report("#option,o1,outcome,Win.\n").counts["option slot"], 1)

    def test_an_undeclared_subject_is_counted(self) -> None:
        self.assertEqual(report("zz,contents,public,A chair.\n").counts["undeclared subject"], 1)

    def test_a_repeated_scalar_is_counted(self) -> None:
        body = "a1,dimensions,,90 ft\na1,dimensions,,100 ft\n"
        self.assertEqual(report(body).counts["scalar repeated"], 1)

    def test_a_repeated_list_predicate_is_not(self) -> None:
        body = "a1,contents,public,A chair.\na1,contents,public,A table.\n"
        self.assertEqual(dict(report(body).counts), {})

    def test_unparseable_json_is_counted(self) -> None:
        body = "a1,exit,,{to: north}\n"
        self.assertEqual(report(body).counts["json parse"], 1)

    def test_an_undeclared_json_key_is_counted(self) -> None:
        body = 'a1,exit,,{"to":"north","via":"door","locked":true}\n'
        self.assertEqual(report(body).counts["json key"], 1)

    def test_a_declared_json_key_set_passes(self) -> None:
        body = 'a1,exit,,{"to":"north","via":"door"}\n'
        self.assertEqual(dict(report(body).counts), {})

    def test_campaign_state_is_counted(self) -> None:
        body = "a1,contents,public,The chest has been looted.\n"
        self.assertEqual(report(body).counts["campaign state"], 1)

    def test_a_missing_unit_is_counted(self) -> None:
        result = report("a1,contents,public,A chair.\n", expected=["u1", "u2"])
        self.assertEqual(result.counts["unit missing"], 1)

    def test_a_duplicated_unit_is_counted(self) -> None:
        result = check(HEAD + HEAD, SCHEMA_OBJECT, EXPECTED, "test")
        self.assertEqual(result.counts["unit duplicated"], 1)

    def test_a_unit_that_was_never_packed_is_counted(self) -> None:
        result = check(HEAD + "#unit,u9,pages,9\n", SCHEMA_OBJECT, EXPECTED, "test")
        self.assertEqual(result.counts["unit unpacked"], 1)

    def test_a_fact_before_any_unit_marker_is_counted(self) -> None:
        result = check("a1,contents,public,A chair.\n", SCHEMA_OBJECT, EXPECTED, "test")
        self.assertEqual(result.counts["fact before unit"], 1)

    def test_a_malformed_unit_page_list_is_counted(self) -> None:
        result = check("#unit,u1,pages,thirty-one\n", SCHEMA_OBJECT, EXPECTED, "test")
        self.assertEqual(result.counts["unit pages"], 1)


class RealResponseTests(unittest.TestCase):
    """The measured response, so the report's figures cannot drift unnoticed."""

    RESPONSE = Path(__file__).resolve().parents[2] / "_exchange/pack-001.csv"

    def test_every_row_splits_into_four_fields(self) -> None:
        if not self.RESPONSE.is_file():
            self.skipTest("no pack response in _exchange/")
        lines = [line for line in self.RESPONSE.read_text(encoding="utf-8")
                 .splitlines() if line.strip()]
        for line in lines:
            self.assertEqual(len(line.split(",", 3)), 4, line[:60])


if __name__ == "__main__":
    unittest.main()
