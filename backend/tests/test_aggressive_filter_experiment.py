from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.research.aggressive_filter_profiles import FORBIDDEN_FEATURE_COLUMNS, all_filter_feature_columns
from stock_analysis.validation.aggressive_filter_experiment import (
    AggressiveFilterExperimentConfig,
    apply_aggressive_filter,
    render_aggressive_filter_experiment_report,
    run_aggressive_filter_experiments,
)


class AggressiveFilterExperimentTests(unittest.TestCase):
    def test_filter_profiles_do_not_use_future_label_columns(self) -> None:
        self.assertFalse(all_filter_feature_columns() & FORBIDDEN_FEATURE_COLUMNS)

    def test_filters_only_consume_as_of_feature_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_aggressive_filter_fixture(root)

            result = run_aggressive_filter_experiments(
                AggressiveFilterExperimentConfig(
                    as_of_date="2024-01-31",
                    horizon_days=120,
                    outputs_dir=root / "outputs",
                    source_family_ids=("momentum_breakout",),
                    filter_ids=("aggressive_volatility_cap",),
                    dry_run=True,
                )
            )

            used = set(result["summary"]["feature_columns_used"])
            self.assertFalse(used & FORBIDDEN_FEATURE_COLUMNS)
            row = result["aggressive_filter_results"][0]
            self.assertEqual(row["source_strategy_family"], "momentum_breakout")

    def test_same_period_results_are_marked_exploratory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_aggressive_filter_fixture(root)

            result = run_aggressive_filter_experiments(
                AggressiveFilterExperimentConfig(
                    as_of_date="2024-01-31",
                    horizon_days=120,
                    outputs_dir=root / "outputs",
                    source_family_ids=("momentum_breakout",),
                    filter_ids=("aggressive_volatility_cap",),
                    dry_run=True,
                )
            )

            statuses = {row["validation_status"] for row in result["aggressive_filter_results"]}
            self.assertEqual(statuses, {"exploratory_same_period"})

    def test_tail_preservation_and_left_tail_reduction_ratios(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_aggressive_filter_fixture(root)

            result = run_aggressive_filter_experiments(
                AggressiveFilterExperimentConfig(
                    as_of_date="2024-01-31",
                    horizon_days=120,
                    outputs_dir=root / "outputs",
                    source_family_ids=("momentum_breakout",),
                    filter_ids=("baseline_aggressive", "aggressive_volatility_cap"),
                    dry_run=True,
                )
            )

            rows = result["aggressive_filter_results"]
            baseline = next(row for row in rows if row["filter_id"] == "none")
            filtered = next(row for row in rows if row["filter_id"] == "volatility_cap_filter")
            self.assertAlmostEqual(baseline["right_tail_preservation_ratio"], 1.0)
            self.assertAlmostEqual(filtered["right_tail_preservation_ratio"], filtered["top_decile_average_return"] / baseline["top_decile_average_return"])
            self.assertAlmostEqual(
                filtered["left_tail_reduction_ratio"],
                filtered["failure_rate_below_minus_20pct"] / baseline["failure_rate_below_minus_20pct"],
            )

    def test_missing_features_do_not_crash_and_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_aggressive_filter_fixture(root)

            result = run_aggressive_filter_experiments(
                AggressiveFilterExperimentConfig(
                    as_of_date="2024-01-31",
                    horizon_days=120,
                    outputs_dir=root / "outputs",
                    source_family_ids=("momentum_breakout",),
                    filter_ids=("aggressive_anti_lottery",),
                    dry_run=True,
                )
            )

            row = result["aggressive_filter_results"][0]
            self.assertIn("missing_feature:recent_extreme_move_proxy", row["notes"])
            self.assertIn("missing_feature:amount_abnormality", row["notes"])

    def test_report_includes_anti_leakage_disclaimer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_aggressive_filter_fixture(root)

            result = run_aggressive_filter_experiments(
                AggressiveFilterExperimentConfig(
                    as_of_date="2024-01-31",
                    horizon_days=120,
                    outputs_dir=root / "outputs",
                    source_family_ids=("momentum_breakout",),
                    filter_ids=("baseline_aggressive",),
                    dry_run=True,
                )
            )

            report = render_aggressive_filter_experiment_report(result)
            self.assertIn("Anti-leakage statement", report)
            self.assertIn("Research-only experiment", report)
            self.assertIn("does not replace production scoring", report)

    def test_apply_filter_reports_missing_as_of_features_safely(self) -> None:
        symbols = ["AAA", "BBB"]
        result, notes = apply_aggressive_filter(symbols, pd.DataFrame(), _first_non_baseline_filter())
        self.assertEqual(result, [])
        self.assertIn("missing_as_of_features", notes)


def write_aggressive_filter_fixture(root: Path) -> None:
    outputs = root / "outputs"
    (outputs / "lists").mkdir(parents=True)
    (outputs / "validation").mkdir(parents=True)
    (outputs / "daily").mkdir(parents=True)
    (outputs / "experiments").mkdir(parents=True)
    (outputs / "portfolios").mkdir(parents=True)
    _write_json(
        outputs / "lists" / "trend_leaders_2024-01-31.json",
        {"list_id": "trend_leaders", "as_of_date": "2024-01-31", "items": [{"symbol": "AAA"}, {"symbol": "BBB"}, {"symbol": "CCC"}]},
    )
    _write_json(
        outputs / "lists" / "breakout_watch_2024-01-31.json",
        {"list_id": "breakout_watch", "as_of_date": "2024-01-31", "items": [{"symbol": "DDD"}]},
    )
    _write_json(outputs / "validation" / "list_performance_2024-01-31_120d.json", [{"list_id": "trend_leaders"}])
    _write_json(outputs / "validation" / "factor_effectiveness_2024-01-31_120d.json", [{"factor_name": "volatility"}])
    _write_json(outputs / "portfolios" / "portfolio_summary_2024-01-31_120d.json", {"summary": {"status": "ok"}})
    _write_json(outputs / "experiments" / "strategy_family_experiments_2024-01-31_120d.json", {"strategy_family_results": []})
    pd.DataFrame(
        [
            {"symbol": "AAA", "volatility_20d": 0.03, "max_drawdown": -0.10, "avg_amount_20d": 100000000, "avg_volume_20d": 2000000},
            {"symbol": "BBB", "volatility_20d": 0.04, "max_drawdown": -0.12, "avg_amount_20d": 90000000, "avg_volume_20d": 1800000},
            {"symbol": "CCC", "volatility_20d": 0.03, "max_drawdown": -0.08, "avg_amount_20d": 80000000, "avg_volume_20d": 1600000},
            {"symbol": "DDD", "volatility_20d": 0.10, "max_drawdown": -0.50, "avg_amount_20d": 70000000, "avg_volume_20d": 1400000},
        ]
    ).to_csv(outputs / "daily" / "factors_2024-01-31.csv", index=False, encoding="utf-8")
    pd.DataFrame(
        [
            _prediction("AAA", 0.50, 0.45, True, -0.05),
            _prediction("BBB", 0.20, 0.15, True, -0.05),
            _prediction("CCC", -0.20, -0.25, False, -0.22),
            _prediction("DDD", -0.30, -0.35, False, -0.40),
        ]
    ).to_csv(outputs / "validation" / "walk_forward_predictions_2024-01-31_120d.csv", index=False, encoding="utf-8")


def _prediction(symbol: str, future_return: float, excess: float, outperformed: bool, drawdown: float) -> dict[str, object]:
    return {
        "symbol": symbol,
        "future_return": future_return,
        "future_excess_return": excess,
        "outperformed_benchmark": outperformed,
        "max_drawdown_during_holding": drawdown,
        "data_quality": "ok",
    }


def _first_non_baseline_filter():
    from stock_analysis.research.aggressive_filter_profiles import get_default_aggressive_filter_profiles

    return next(profile for profile in get_default_aggressive_filter_profiles() if profile.filter_id != "none")


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

