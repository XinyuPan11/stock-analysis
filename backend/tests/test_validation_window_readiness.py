from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.validation.window_readiness import (
    ValidationWindowReadinessConfig,
    check_validation_window_readiness,
)


class ValidationWindowReadinessTests(unittest.TestCase):
    def test_missing_symbols_file_reports_missing_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_plan(root / "outputs", "2024-07-31", 60)

            result = check_validation_window_readiness(
                _config(root, as_of_date="2024-07-31", horizon_days=60)
            )

            self.assertEqual(result["status"], "missing_symbols_file")
            self.assertEqual(result["execution_status"], "missing_symbols_file")
            self.assertEqual(result["quality_status"], "unknown")
            self.assertIn("symbols_file_missing", result["notes"])
            self.assertIn("generate_multi_asof_validation_plan.py", result["next_manual_command"])

    def test_deferred_window_stops_before_cache_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_plan(root / "outputs", "2024-07-31", 120, crosses_2025=True)

            result = check_validation_window_readiness(
                _config(root, as_of_date="2024-07-31", horizon_days=120)
            )

            self.assertEqual(result["status"], "deferred")
            self.assertEqual(result["execution_status"], "deferred")
            self.assertIn("deferred_crosses_2025", result["notes"])
            self.assertEqual(result["symbol_count"], None)

    def test_missing_as_of_outputs_recommends_daily_research_and_views(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_plan(
                root / "outputs",
                "2024-10-31",
                20,
                missing_as_of_outputs={"stock_labels": {"path": "missing", "exists": False}},
            )

            result = check_validation_window_readiness(
                _config(root, as_of_date="2024-10-31", horizon_days=20)
            )

            self.assertEqual(result["status"], "blocked_missing_as_of_outputs")
            self.assertEqual(result["execution_status"], "blocked_missing_as_of_outputs")
            self.assertIn("run_daily_research.py", result["next_manual_command"])
            self.assertIn("generate_research_views.py", result["next_manual_command"])

    def test_insufficient_cache_coverage_recommends_prewarm(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_plan(root / "outputs", "2024-07-31", 60)
            _write_symbols(root / "outputs", "2024-07-31", 60, ["AAA", "BBB"])

            result = check_validation_window_readiness(
                _config(root, as_of_date="2024-07-31", horizon_days=60)
            )

            self.assertEqual(result["status"], "missing_cache")
            self.assertEqual(result["execution_status"], "missing_cache")
            self.assertEqual(result["symbol_count"], 2)
            self.assertEqual(result["covered_count"], 0)
            self.assertIn("prewarm_market_cache.py", result["next_manual_command"])

    def test_low_valid_prediction_count_reports_low_quality(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_plan(root / "outputs", "2024-07-31", 60)
            _write_symbols(root / "outputs", "2024-07-31", 60, ["AAA", "BBB"])
            _write_price(root / "cache", "AAA", "2024-08-05")
            _write_price(root / "cache", "BBB", "2024-08-06")
            _write_validation_outputs(root / "outputs", "2024-07-31", 60, ["AAA", "BBB"])

            result = check_validation_window_readiness(
                _config(root, as_of_date="2024-07-31", horizon_days=60, min_valid_count=3)
            )

            self.assertEqual(result["status"], "low_quality")
            self.assertEqual(result["execution_status"], "executable_ready")
            self.assertEqual(result["quality_status"], "insufficient_valid_count")
            self.assertFalse(result["comparison_eligible"])
            self.assertFalse(result["high_quality_ready"])
            self.assertEqual(result["prediction_count"], 2)
            self.assertEqual(result["valid_prediction_count"], 2)
            self.assertIn("valid_prediction_count_below_threshold", result["notes"])

    def test_valid_window_reports_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_plan(root / "outputs", "2024-07-31", 60)
            _write_symbols(root / "outputs", "2024-07-31", 60, ["AAA", "BBB"])
            _write_price(root / "cache", "AAA", "2024-08-05")
            _write_price(root / "cache", "BBB", "2024-08-06")
            _write_validation_outputs(root / "outputs", "2024-07-31", 60, ["AAA", "BBB"])

            result = check_validation_window_readiness(
                _config(root, as_of_date="2024-07-31", horizon_days=60, min_valid_count=2)
            )

            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["execution_status"], "executable_ready")
            self.assertEqual(result["quality_status"], "high_quality")
            self.assertTrue(result["comparison_eligible"])
            self.assertTrue(result["high_quality_ready"])
            self.assertEqual(result["symbol_count"], 2)
            self.assertEqual(result["covered_count"], 2)
            self.assertEqual(result["valid_coverage_ratio"], 1.0)
            self.assertIn("summarize_multi_window_experiments.py", result["next_manual_command"])

    def test_low_coverage_remains_comparison_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            symbols = [f"S{i:03d}" for i in range(300)]
            _write_plan(root / "outputs", "2024-07-31", 60)
            _write_symbols(root / "outputs", "2024-07-31", 60, symbols)
            _write_cache_coverage(root / "outputs", "2024-07-31", 60, 300)
            _write_validation_outputs(
                root / "outputs",
                "2024-07-31",
                60,
                symbols,
                valid_prediction_count=55,
            )

            result = check_validation_window_readiness(
                _config(root, as_of_date="2024-07-31", horizon_days=60)
            )

            self.assertEqual(result["status"], "low_quality")
            self.assertEqual(result["execution_status"], "executable_ready")
            self.assertEqual(result["quality_status"], "low_coverage")
            self.assertEqual(result["prediction_count"], 300)
            self.assertEqual(result["valid_prediction_count"], 55)
            self.assertAlmostEqual(result["valid_coverage_ratio"], 55 / 300)
            self.assertTrue(result["comparison_eligible"])
            self.assertFalse(result["high_quality_ready"])

    def test_high_quality_prediction_coverage_reports_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            symbols = [f"S{i:03d}" for i in range(300)]
            _write_plan(root / "outputs", "2024-07-31", 60)
            _write_symbols(root / "outputs", "2024-07-31", 60, symbols)
            _write_cache_coverage(root / "outputs", "2024-07-31", 60, 300)
            _write_validation_outputs(
                root / "outputs",
                "2024-07-31",
                60,
                symbols,
                valid_prediction_count=250,
            )

            result = check_validation_window_readiness(
                _config(root, as_of_date="2024-07-31", horizon_days=60)
            )

            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["quality_status"], "high_quality")
            self.assertTrue(result["comparison_eligible"])
            self.assertTrue(result["high_quality_ready"])



def _config(
    root: Path,
    *,
    as_of_date: str,
    horizon_days: int,
    min_valid_count: int = 50,
) -> ValidationWindowReadinessConfig:
    return ValidationWindowReadinessConfig(
        as_of_date=as_of_date,
        horizon_days=horizon_days,
        outputs_dir=root / "outputs",
        cache_dir=root / "cache",
        limit=300,
        min_valid_count=min_valid_count,
        min_coverage_rate=0.7,
    )


def _write_plan(
    outputs_dir: Path,
    as_of_date: str,
    horizon_days: int,
    *,
    crosses_2025: bool = False,
    missing_as_of_outputs: dict[str, object] | None = None,
) -> None:
    suffix = f"{as_of_date}_{horizon_days}d"
    future_window = {
        "start_date": "2024-08-01",
        "end_date": "2025-03-28" if crosses_2025 else "2024-11-28",
    }
    plan = {
        "status": "plan_only",
        "provider_access": False,
        "prewarm_executed": False,
        "full_workflow_executed": False,
        "production_scoring_changed": False,
        "as_of_plan": [
            {
                "as_of_date": as_of_date,
                "horizons": [
                    {
                        "horizon_days": horizon_days,
                        "future_window": future_window,
                        "crosses_2025_boundary": crosses_2025,
                        "missing_as_of_outputs": missing_as_of_outputs or {},
                        "missing_outputs": {},
                        "ready_for_comparison": not crosses_2025 and not missing_as_of_outputs,
                        "cache_requirement_id": suffix,
                    }
                ],
            }
        ],
        "cache_requirements": [
            {
                "cache_requirement_id": suffix,
                "manual_prewarm_command": "python backend\\scripts\\prewarm_market_cache.py --provider baostock",
            }
        ],
    }
    path = outputs_dir / "experiments" / "multi_asof_validation_plan_2024.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan), encoding="utf-8")


def _write_symbols(
    outputs_dir: Path,
    as_of_date: str,
    horizon_days: int,
    symbols: list[str],
) -> None:
    path = outputs_dir / "cache_plans" / f"multi_asof_symbols_{as_of_date}_{horizon_days}d.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(symbols) + "\n", encoding="utf-8")


def _write_price(cache_dir: Path, symbol: str, trade_date: str) -> None:
    path = cache_dir / "baostock" / "stock_daily" / "adjusted" / f"{symbol}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [{"symbol": symbol, "trade_date": trade_date, "close": 10.0, "adj_close": 10.0}]
    ).to_csv(path, index=False, encoding="utf-8")


def _write_validation_outputs(
    outputs_dir: Path,
    as_of_date: str,
    horizon_days: int,
    symbols: list[str],
    *,
    valid_prediction_count: int | None = None,
) -> None:
    suffix = f"{as_of_date}_{horizon_days}d"
    validation_dir = outputs_dir / "validation"
    experiments_dir = outputs_dir / "experiments"
    validation_dir.mkdir(parents=True, exist_ok=True)
    experiments_dir.mkdir(parents=True, exist_ok=True)
    valid_prediction_count = (
        len(symbols) if valid_prediction_count is None else valid_prediction_count
    )
    pd.DataFrame(
        [
            {
                "symbol": symbol,
                "data_quality": "ok" if index < valid_prediction_count else "missing_price",
                "future_return": 0.1 if index < valid_prediction_count else None,
            }
            for index, symbol in enumerate(symbols)
        ]
    ).to_csv(validation_dir / f"walk_forward_predictions_{suffix}.csv", index=False)
    for path in [
        validation_dir / f"list_performance_{suffix}.json",
        validation_dir / f"factor_effectiveness_{suffix}.json",
        experiments_dir / f"strategy_family_experiments_{suffix}.json",
        experiments_dir / f"aggressive_filter_experiments_{suffix}.json",
    ]:
        path.write_text("{}", encoding="utf-8")


def _write_cache_coverage(
    outputs_dir: Path,
    as_of_date: str,
    horizon_days: int,
    symbol_count: int,
) -> None:
    suffix = f"{as_of_date}_{horizon_days}d"
    path = outputs_dir / "experiments" / f"cache_coverage_{suffix}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "provider_access": False,
                "date_range": {"start_date": "2024-08-01", "end_date": "2024-11-28"},
                "symbol_count": symbol_count,
                "covered_count": symbol_count,
                "missing_count": 0,
                "coverage_rate": 1.0,
            }
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
