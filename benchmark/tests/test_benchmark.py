from __future__ import annotations

import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from benchmark.benchmark import (  # noqa: E402
    OllamaClient,
    ProgressDisplay,
    TIER_MODELS,
    _aggregate_metrics,
    build_parser,
    cmd_install,
    fixture_prompt,
    load_fixtures,
    recovery_prompt,
    run_benchmark,
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
    def test_run_with_no_available_models_writes_no_results(self) -> None:
        args = build_parser().parse_args(
            [
                "run",
                "--models",
                "qwen3:8b",
                "--skip-unavailable",
                "--output",
                "/tmp/benchmark-test-empty-run",
            ]
        )
        technical_info = {
            "platform": {"system": "TestOS", "release": "1", "machine": "test"},
            "memory": {"physical_bytes": None},
            "cpu": {"logical_count": None},
            "gpu": [],
        }

        class EmptyClient:
            def __init__(self, base_url: str, timeout: float) -> None:
                pass

            def inventory(self):
                return []

        with tempfile.TemporaryDirectory() as temp_dir:
            args.output = str(Path(temp_dir) / "run")
            with patch("benchmark.benchmark.collect_technical_info", return_value=technical_info), \
                patch("benchmark.benchmark.OllamaClient", EmptyClient), \
                redirect_stdout(StringIO()):
                output = run_benchmark(args)

            self.assertIsNone(output)
            self.assertFalse(Path(args.output).exists())

    def test_budget_metrics_include_retry_durations(self) -> None:
        validation = {
            "row_count": 1,
            "valid_row_count": 1,
            "entirely_clean": True,
            "failure_kinds": [],
            "unit_markers": [{"id": "p16"}],
            "structural_errors": [],
            "s1_valid": True,
            "s2_valid": True,
        }
        fixture_result = {
            "fixture": "p16",
            "source_bytes": 1,
            "final_s1_valid": True,
            "final_s2_valid": True,
            "recall": {
                "atoms_total": 1,
                "atoms_matched": 1,
                "records_total": 1,
                "records_matched": 1,
            },
            "contamination": {"status": "manual_review_required"},
            "attempts": [
                {
                    "wall_clock_s": 40.0,
                    "generated_tokens": 10,
                    "tokens_per_second": 1.0,
                    "time_to_first_token_s": 0.1,
                    "validation": validation,
                },
                {"wall_clock_s": 30.0, "validation": validation},
            ],
        }

        metrics = _aggregate_metrics([fixture_result], budget_s=60.0)

        self.assertEqual(metrics["elapsed_s"], 70.0)
        self.assertTrue(metrics["budget_exceeded"])

        unlimited = _aggregate_metrics([fixture_result], budget_s=None)
        self.assertEqual(unlimited["elapsed_s"], 70.0)
        self.assertFalse(unlimited["budget_exceeded"])

    def test_progress_display_shows_live_generation_separately(self) -> None:
        display = ProgressDisplay("qwen3:8b", "quick", 3)
        with redirect_stdout(StringIO()):
            display.begin_fixture(1, "p16")
            display.begin_attempt(1, 2)
            display.stream(96)

        rendered = display._text()
        self.assertIn("fixtures 0/3", rendered)
        self.assertIn("0/3", rendered)
        self.assertIn("p16 attempt 1/2", rendered)
        self.assertIn("output 96 chars", rendered)
        self.assertIn("96 chars", rendered)
        self.assertIn("streaming", rendered)

        with redirect_stdout(StringIO()):
            display.complete_fixture(1, "S1=PASS S2=PASS")
        completed = display._text()
        self.assertIn("fixtures 1/3", completed)
        self.assertIn("1/3", completed)
        self.assertNotIn("fixtures [", completed)

    def test_committed_fixtures_match_the_manifest(self) -> None:
        fixtures, manifest = load_fixtures(ROOT)
        self.assertEqual(set(fixtures), {item["id"] for item in manifest["fixtures"]})
        self.assertEqual(sum(item.source_bytes for item in fixtures.values()), 16550)
        self.assertEqual(manifest["suites"]["smoke"]["fixtures"], ["p31"])

    def test_smoke_is_a_supported_run_suite(self) -> None:
        args = build_parser().parse_args(["run", "--suite", "smoke"])
        self.assertEqual(args.suite, "smoke")

    def test_install_parser_accepts_a_model_tier(self) -> None:
        args = build_parser().parse_args(["install", "--tier", "tier2"])
        self.assertEqual(args.command, "install")
        self.assertEqual(args.tier, "tier2")

    def test_install_pulls_every_model_in_the_selected_tier(self) -> None:
        args = build_parser().parse_args(["install", "--tier", "tier1"])
        pulled: list[str] = []

        class FakeClient:
            def __init__(self, base_url: str, timeout: float) -> None:
                self.base_url = base_url
                self.timeout = timeout

            def pull(self, model: str, on_progress=None):
                pulled.append(model)
                if on_progress is not None:
                    on_progress({"status": "success"})
                return {"status": "success"}

        with patch("benchmark.benchmark.OllamaClient", FakeClient), redirect_stdout(StringIO()):
            self.assertEqual(cmd_install(args), 0)
        self.assertEqual(pulled, list(TIER_MODELS["tier1"]))

    def test_pull_consumes_ollama_stream_and_posts_the_model(self) -> None:
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def __iter__(self):
                return iter(
                    [
                        b'{"status":"pulling manifest"}\n',
                        b'{"status":"success"}\n',
                    ]
                )

        events: list[dict[str, str]] = []
        with patch("benchmark.benchmark.urllib.request.urlopen", return_value=FakeResponse()) as urlopen:
            result = OllamaClient("http://ollama.test").pull("qwen3:8b", events.append)

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://ollama.test/api/pull")
        self.assertEqual(json.loads(request.data.decode("utf-8")), {"model": "qwen3:8b", "stream": True})
        self.assertEqual(events[-1], {"status": "success"})
        self.assertEqual(result, {"status": "success"})

    def test_prompt_is_shared_and_contains_the_fixture_source(self) -> None:
        fixtures, _ = load_fixtures(ROOT)
        prompt = fixture_prompt(fixtures["p31"])
        self.assertIn("Return ONLY the\nrows", prompt)
        self.assertIn("24 CRUSH HALLWAY", prompt)
        self.assertIn("#unit,p31,pages,31", prompt)
        self.assertIn("The last form is the normal fact row", prompt)
        self.assertIn("Never use a numeric slot such as 0", prompt)
        self.assertIn("`white-temple` is valid", prompt)
        self.assertIn("`white_temple` is", prompt)
        self.assertIn("`description`", prompt)
        self.assertIn("`history` are invalid predicate names", prompt)
        self.assertIn("The fourth field is never quoted", prompt)
        self.assertIn("Before returning, silently verify", prompt)

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
        self.assertIn("Replace `white_temple` with `white-temple`", prompt)
        self.assertIn("Use `text` instead of the invalid predicate `description` or `history`", prompt)
        self.assertIn("declared-before-use order", prompt)

    def test_invalid_id_error_explains_the_repair(self) -> None:
        result = validate_response(
            "#unit,p16,pages,16\n#entity,white_temple,actor,White Temple",
            "p16",
        )
        self.assertIn("underscores", " ".join(result["structural_errors"]))

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
