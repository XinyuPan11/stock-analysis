from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.validation.cache_plan import recommended_target_end_date
from stock_analysis.validation.multi_asof_validation import (
    DEFAULT_AS_OF_DATES,
    DEFAULT_HORIZONS,
    MultiAsOfValidationConfig,
    build_multi_asof_validation_plan,
    future_window_for,
    write_multi_asof_outputs,
)


class MultiAsOfValidationTests(unittest.TestCase):
    def test_plan_generates_controlled_as_of_dates_and_horizons(self) -> None:
        plan = build_multi_asof_validation_plan(MultiAsOfValidationConfig(outputs_dir="outputs", cache_dir="cache"))

        self.assertEqual(plan["provider_access"], False)
        self.assertEqual(plan["prewarm_executed"], False)
        self.assertEqual(plan["full_workflow_executed"], False)
        self.assertEqual(plan["production_scoring_changed"], False)
        self.assertEqual(plan["as_of_dates"], list(DEFAULT_AS_OF_DATES))
        self.assertEqual(plan["horizons"], list(DEFAULT_HORIZONS))
        self.assertEqual(len(plan["cache_requirements"]), len(DEFAULT_AS_OF_DATES) * len(DEFAULT_HORIZONS))
        self.assertIn("right_tail_preservation_ratio", plan["comparison_metrics"])
        self.assertIn("cooldown", plan["dynamic_state_history_plan"]["states"])

    def test_future_windows_use_validation_cache_plan_target_end_date(self) -> None:
        window = future_window_for("2024-01-31", 120)

        self.assertEqual(window["start_date"], "2024-02-01")
        self.assertEqual(window["end_date"], recommended_target_end_date("2024-01-31", 120))
        self.assertEqual(window["end_date"], "2024-09-27")
        self.assertEqual(window["target_end_date_source"], "validation.cache_plan.recommended_target_end_date")

    def test_plan_defers_windows_that_require_2025_data(self) -> None:
        plan = build_multi_asof_validation_plan(
            MultiAsOfValidationConfig(outputs_dir="outputs", cache_dir="cache", as_of_dates=("2024-10-31",), horizons=(120,))
        )

        horizon = plan["as_of_plan"][0]["horizons"][0]
        requirement = plan["cache_requirements"][0]
        self.assertTrue(horizon["crosses_2025_boundary"])
        self.assertTrue(horizon["deferred_until_2025_allowed"])
        self.assertFalse(horizon["ready_for_comparison"])
        self.assertEqual(horizon["manual_validation_commands"]["strategy_family"], "not_generated_2025_boundary")
        self.assertIn(requirement["manual_prewarm_command"], {"not_generated_2025_boundary", "unavailable_missing_as_of_outputs"})
        self.assertIn(requirement["manual_cache_coverage_command"], {"not_generated_2025_boundary", "unavailable_missing_as_of_outputs"})

    def test_missing_as_of_outputs_block_cache_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plan = build_multi_asof_validation_plan(
                MultiAsOfValidationConfig(outputs_dir=root / "outputs", cache_dir=root / "cache", as_of_dates=("2024-04-30",), horizons=(20,))
            )

            horizon = plan["as_of_plan"][0]["horizons"][0]
            requirement = plan["cache_requirements"][0]
            self.assertFalse(horizon["ready_for_comparison"])
            self.assertIn("stock_labels", horizon["missing_as_of_outputs"])
            self.assertEqual(requirement["status"], "blocked_missing_as_of_outputs")
            self.assertEqual(requirement["symbol_count"], 0)
            self.assertEqual(requirement["covered_count"], 0)
            self.assertEqual(requirement["missing_count"], 0)
            self.assertEqual(requirement["manual_prewarm_command"], "unavailable_missing_as_of_outputs")
            self.assertEqual(requirement["manual_cache_coverage_command"], "unavailable_missing_as_of_outputs")
            self.assertIn("generate_as_of_labels_lists_first", requirement["notes"])

    def test_plan_checks_existing_outputs_and_cache_without_provider_access(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outputs = root / "outputs"
            cache = root / "cache"
            _write_as_of_outputs(outputs, "2024-01-31", 20)
            _write_required_as_of_outputs(outputs, "2024-01-31", ["AAA", "BBB"])
            _write_walk_forward_predictions(outputs, "2024-01-31", 20, ["AAA", "BBB"])
            _write_price(cache / "baostock" / "stock_daily" / "adjusted" / "AAA.csv", "AAA", [("2024-02-01", 10.0)])

            plan = build_multi_asof_validation_plan(
                MultiAsOfValidationConfig(
                    outputs_dir=outputs,
                    cache_dir=cache,
                    as_of_dates=("2024-01-31",),
                    horizons=(20,),
                    recommended_limit=2,
                )
            )

            horizon = plan["as_of_plan"][0]["horizons"][0]
            cache_requirement = plan["cache_requirements"][0]
            self.assertTrue(horizon["ready_for_comparison"])
            self.assertEqual(horizon["missing_outputs"], {})
            self.assertEqual(horizon["missing_as_of_outputs"], {})
            self.assertEqual(cache_requirement["status"], "evaluated")
            self.assertEqual(cache_requirement["symbol_count"], 2)
            self.assertEqual(cache_requirement["covered_count"], 1)
            self.assertEqual(cache_requirement["missing_symbols"], ["BBB"])
            self.assertFalse(cache_requirement["provider_access"])

    def test_write_outputs_creates_symbols_files_for_eligible_non_deferred_windows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outputs = root / "outputs"
            cache = root / "cache"
            _write_as_of_outputs(outputs, "2024-07-31", 20)
            _write_walk_forward_predictions(outputs, "2024-07-31", 60, ["CCC", "DDD", "EEE"])
            _write_required_as_of_outputs(outputs, "2024-07-31", ["AAA", "BBB", "CCC"] )

            plan = build_multi_asof_validation_plan(
                MultiAsOfValidationConfig(
                    outputs_dir=outputs,
                    cache_dir=cache,
                    as_of_dates=("2024-07-31",),
                    horizons=(20, 60, 120),
                    recommended_limit=2,
                )
            )
            paths = write_multi_asof_outputs(plan, outputs)

            written = {Path(path).name for path in paths["symbols_files"]}
            self.assertIn("multi_asof_symbols_2024-07-31_20d.txt", written)
            self.assertIn("multi_asof_symbols_2024-07-31_60d.txt", written)
            self.assertNotIn("multi_asof_symbols_2024-07-31_120d.txt", written)
            symbols_60 = (outputs / "cache_plans" / "multi_asof_symbols_2024-07-31_60d.txt").read_text(encoding="utf-8").splitlines()
            self.assertEqual(symbols_60, ["CCC", "DDD", "EEE"])

            cache_payload = json.loads((outputs / "experiments" / "multi_asof_cache_plan_2024.json").read_text(encoding="utf-8"))
            by_id = {row["cache_requirement_id"]: row for row in cache_payload["cache_requirements"]}
            self.assertEqual(by_id["2024-07-31_60d"]["symbol_count"], 3)
            self.assertIn("multi_asof_symbols_2024-07-31_60d.txt", by_id["2024-07-31_60d"]["manual_cache_coverage_command"])
            self.assertIn("--limit 3", by_id["2024-07-31_60d"]["manual_cache_coverage_command"])
            self.assertEqual(by_id["2024-07-31_120d"]["symbols_file"], "not_generated_2025_boundary")

    def test_blocked_missing_as_of_outputs_do_not_create_symbols_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plan = build_multi_asof_validation_plan(
                MultiAsOfValidationConfig(outputs_dir=root / "outputs", cache_dir=root / "cache", as_of_dates=("2024-10-31",), horizons=(20,))
            )
            paths = write_multi_asof_outputs(plan, root / "outputs")

            self.assertEqual(paths["symbols_files"], [])
            self.assertFalse((root / "outputs" / "cache_plans" / "multi_asof_symbols_2024-10-31_20d.txt").exists())

    def test_write_outputs_creates_required_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plan = build_multi_asof_validation_plan(
                MultiAsOfValidationConfig(outputs_dir=root / "outputs", cache_dir=root / "cache", as_of_dates=("2024-01-31",), horizons=(20,))
            )

            paths = write_multi_asof_outputs(plan, root / "outputs")

            validation_path = Path(paths["validation_plan"])
            cache_path = Path(paths["cache_plan"])
            summary_path = Path(paths["summary_md"])
            self.assertTrue(validation_path.exists())
            self.assertTrue(cache_path.exists())
            self.assertTrue(summary_path.exists())
            self.assertEqual(validation_path.name, "multi_asof_validation_plan_2024.json")
            self.assertEqual(cache_path.name, "multi_asof_cache_plan_2024.json")
            self.assertEqual(summary_path.name, "multi_asof_validation_summary_2024.md")
            markdown = summary_path.read_text(encoding="utf-8")
            self.assertIn("Anti-leakage", markdown)
            self.assertIn("Ready validations", markdown)
            self.assertIn("Missing experiment outputs only", markdown)
            self.assertIn("Blocked because as-of outputs are missing", markdown)
            self.assertIn("Deferred because crosses 2025", markdown)
            self.assertIn("generate as-of labels", markdown.lower())
            self.assertIn("Do not access BaoStock automatically", markdown)
            self.assertIn("cooldown", markdown)

    def test_cli_generates_plan_without_running_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            script = Path(__file__).resolve().parents[1] / "scripts" / "generate_multi_asof_validation_plan.py"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--outputs-dir",
                    str(root / "outputs"),
                    "--cache-dir",
                    str(root / "cache"),
                    "--as-of-dates",
                    "2024-01-31,2024-04-30",
                    "--horizons",
                    "20,60",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn('"provider_access": false', completed.stdout)
            self.assertIn('"prewarm_executed": false', completed.stdout)
            self.assertIn('"full_workflow_executed": false', completed.stdout)
            self.assertTrue((root / "outputs" / "experiments" / "multi_asof_validation_plan_2024.json").exists())


def _write_walk_forward_predictions(outputs: Path, as_of_date: str, horizon: int, symbols: list[str]) -> None:
    path = outputs / "validation" / f"walk_forward_predictions_{as_of_date}_{horizon}d.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {"symbol": symbol, "future_return": 0.1, "data_quality": "ok"}
            for symbol in symbols
        ]
    ).to_csv(path, index=False, encoding="utf-8")


def _write_as_of_outputs(outputs: Path, as_of_date: str, horizon: int) -> None:
    (outputs / "validation").mkdir(parents=True, exist_ok=True)
    (outputs / "experiments").mkdir(parents=True, exist_ok=True)
    suffix = f"{as_of_date}_{horizon}d"
    pd.DataFrame([{"symbol": "AAA", "future_return": 0.1, "data_quality": "ok"}]).to_csv(
        outputs / "validation" / f"walk_forward_predictions_{suffix}.csv",
        index=False,
        encoding="utf-8",
    )
    for path in [
        outputs / "validation" / f"list_performance_{suffix}.json",
        outputs / "validation" / f"factor_effectiveness_{suffix}.json",
        outputs / "experiments" / f"strategy_family_experiments_{suffix}.json",
        outputs / "experiments" / f"aggressive_filter_experiments_{suffix}.json",
    ]:
        path.write_text("[]", encoding="utf-8")


def _write_required_as_of_outputs(outputs: Path, as_of_date: str, symbols: list[str]) -> None:
    _write_labels(outputs, as_of_date, symbols)
    factors = outputs / "daily" / f"factors_{as_of_date}.csv"
    factors.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"symbol": symbol, "total_score": 1.0} for symbol in symbols]).to_csv(factors, index=False, encoding="utf-8")
    list_path = outputs / "lists" / f"high_confidence_candidates_{as_of_date}.json"
    list_path.parent.mkdir(parents=True, exist_ok=True)
    list_path.write_text(json.dumps({"items": [{"symbol": symbol} for symbol in symbols]}), encoding="utf-8")


def _write_labels(outputs: Path, as_of_date: str, symbols: list[str]) -> None:
    path = outputs / "labels" / f"stock_labels_{as_of_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([{"symbol": symbol} for symbol in symbols]), encoding="utf-8")


def _write_price(path: Path, symbol: str, rows: list[tuple[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "symbol": [symbol] * len(rows),
            "trade_date": [row[0] for row in rows],
            "close": [row[1] for row in rows],
            "adj_close": [row[1] for row in rows],
        }
    ).to_csv(path, index=False, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

