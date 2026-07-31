from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from benchmark.benchmark import (  # noqa: E402
    fixture_prompt,
    load_fixtures,
    recovery_prompt,
    score_recall,
    validate_response,
)


class ContractTests(unittest.TestCase):
    def test_commas_are_allowed_in_the_fourth_field(self) -> None:
        response = "\n".join(
            [
                "#unit,p31,pages,31",
                "#entity,a24,place,24 CRUSH HALLWAY",
                "a24,visible,public,wood shards, splinters, and furniture",
            ]
        )
        result = validate_response(response, "p31")
        self.assertTrue(result["s1_valid"])
        self.assertTrue(result["s2_valid"])
        self.assertEqual(result["facts"][0]["value"], "wood shards, splinters, and furniture")

    def test_structured_values_are_checked_without_csv_escaping(self) -> None:
        response = "\n".join(
            [
                "#unit,p31,pages,31",
                "#entity,ceil,mechanism,descending ceiling",
                'ceil,cycle,,{"fall_ft":10,"fall_s":10}',
            ]
        )
        self.assertTrue(validate_response(response, "p31")["s1_valid"])
        invalid = response.replace('{"fall_ft":10,"fall_s":10}', "fall_ft=10")
        result = validate_response(invalid, "p31")
        self.assertFalse(result["s1_valid"])
        self.assertIn("invalid_json", result["failure_kinds"])

    def test_wrappers_are_scored_but_deterministically_unwrapped(self) -> None:
        inner = "#unit,p16,pages,16\n#entity,a,actor,The Lamb\na,title,,The Lamb"
        result = validate_response(f"```text\n{inner}\n```", "p16")
        self.assertTrue(result["s1_valid"])
        self.assertTrue(result["s2_valid"])
        self.assertFalse(result["entirely_clean"])
        self.assertEqual(result["failure_kinds"], ["wrapped_in_fence"])

    def test_structural_order_and_vocabulary_are_enforced(self) -> None:
        response = "\n".join(
            [
                "#unit,p16,pages,16",
                "a,title,,The White Temple",
                "#entity,a,actor,The White Temple",
            ]
        )
        result = validate_response(response, "p16")
        self.assertFalse(result["s2_valid"])
        self.assertIn("not declared first", " ".join(result["structural_errors"]))

        unknown = "#unit,p16,pages,16\n#entity,a,actor,The White Temple\na,not_a_predicate,,x"
        result = validate_response(unknown, "p16")
        self.assertFalse(result["s1_valid"])
        self.assertIn("unknown_vocabulary", result["failure_kinds"])


class FixtureTests(unittest.TestCase):
    def test_committed_fixtures_match_the_manifest(self) -> None:
        fixtures, manifest = load_fixtures(ROOT)
        self.assertEqual(set(fixtures), {item["id"] for item in manifest["fixtures"]})
        self.assertEqual(sum(item.source_bytes for item in fixtures.values()), 16550)

    def test_prompt_is_shared_and_contains_the_fixture_source(self) -> None:
        fixtures, _ = load_fixtures(ROOT)
        prompt = fixture_prompt(fixtures["p31"])
        self.assertIn("Return ONLY the\nrows", prompt)
        self.assertIn("24 CRUSH HALLWAY", prompt)
        self.assertIn("#unit,p31,pages,31", prompt)
        self.assertIn("The last form is the normal fact row", prompt)
        self.assertIn("Never use a numeric slot such as 0", prompt)

    def test_recovery_prompt_shows_the_valid_option_shape(self) -> None:
        fixtures, _ = load_fixtures(ROOT)
        prompt = recovery_prompt(
            fixtures["p16"],
            "#option,a8,0,wrong",
            ["unknown option slot '0'", "unit has no facts"],
        )
        self.assertIn("#option,<id>,0,... is invalid", prompt)
        self.assertIn("thing,visible,public,An ordinary source-supported fact", prompt)
        self.assertIn("unknown option slot '0'", prompt)

    def test_recall_reports_reference_records_and_atoms(self) -> None:
        fixtures, _ = load_fixtures(ROOT)
        response = "\n".join(
            [
                "#unit,p16,pages,16",
                "#entity,white,actor,The White Temple",
                "white,role,,A temple that keeps the Lamb as a secret",
            ]
        )
        result = score_recall(fixtures["p16"], validate_response(response, "p16"))
        self.assertEqual(result["records_total"], 8)
        self.assertGreaterEqual(result["atoms_total"], 8)
        self.assertEqual(result["method"], "lexical-semantic proxy with optional human review overrides")


if __name__ == "__main__":
    unittest.main()
