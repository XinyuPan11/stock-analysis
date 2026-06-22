from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.validation.strategy_family_experiment import StrategyFamilyExperimentConfig, run_strategy_family_experiments


class StrategyFamilyExperimentTests(unittest.TestCase):
    def test_aggressive_family_calculates_right_tail_and_failure_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_strategy_family_fixture(root)

            result = run_strategy_family_experiments(
                StrategyFamilyExperimentConfig(
                    as_of_date="2024-01-31",
                    horizon_days=120,
                    outputs_dir=root / "outputs",
                    profile_ids=("momentum_breakout",),
                    dry_run=True,
                )
            )

            row = result["strategy_family_results"][0]
            self.assertEqual(row["profile_id"], "momentum_breakout")
            self.assertEqual(row["valid_future_count"], 6)
            self.assertAlmostEqual(row["hit_rate"], 4 / 6)
            self.assertAlmostEqual(row["top_decile_average_return"], 0.50)
            self.assertAlmostEqual(row["bottom_decile_average_return"], -0.30)
            self.assertAlmostEqual(row["top_5_average_return"], (0.50 + 0.30 + 0.20 + 0.05 - 0.12) / 5)
            self.assertAlmostEqual(row["payoff_ratio"], 0.2625 / 0.21)
            self.assertAlmostEqual(row["right_tail_ratio"], 0.50 / 0.30)
            self.assertAlmostEqual(row["failure_rate_below_minus_10pct"], 2 / 6)
            self.assertAlmostEqual(row["failure_rate_below_minus_20pct"], 1 / 6)

    def test_conservative_family_calculates_stability_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_strategy_family_fixture(root)

            result = run_strategy_family_experiments(
                StrategyFamilyExperimentConfig(
                    as_of_date="2024-01-31",
                    horizon_days=120,
                    outputs_dir=root / "outputs",
                    profile_ids=("long_term_stable",),
                    dry_run=True,
                )
            )

            row = result["strategy_family_results"][0]
            self.assertEqual(row["family_type"], "conservative")
            self.assertEqual(row["valid_future_count"], 3)
            self.assertAlmostEqual(row["average_excess_return"], (0.06 + 0.02 - 0.03) / 3)
            self.assertAlmostEqual(row["outperform_rate"], 2 / 3)
            self.assertAlmostEqual(row["negative_return_rate"], 1 / 3)
            self.assertIsNotNone(row["stability_score"])

    def test_missing_predictions_returns_safe_notes_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outputs = root / "outputs"
            (outputs / "lists").mkdir(parents=True)
            _write_json(outputs / "lists" / "long_term_stable_2024-01-31.json", {"list_id": "long_term_stable", "as_of_date": "2024-01-31", "items": [{"symbol": "AAA"}]})

            result = run_strategy_family_experiments(
                StrategyFamilyExperimentConfig(
                    as_of_date="2024-01-31",
                    horizon_days=120,
                    outputs_dir=outputs,
                    profile_ids=("long_term_stable",),
                    dry_run=True,
                )
            )

            row = result["strategy_family_results"][0]
            self.assertEqual(row["valid_future_count"], 0)
            self.assertIn("missing_future_labels", row["notes"])
            self.assertEqual(result["outputs"], {})

    def test_write_output_creates_json_and_markdown_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_strategy_family_fixture(root)

            result = run_strategy_family_experiments(
                StrategyFamilyExperimentConfig(
                    as_of_date="2024-01-31",
                    horizon_days=120,
                    outputs_dir=root / "outputs",
                    profile_ids=("long_term_stable", "right_tail_hunter"),
                    dry_run=False,
                )
            )

            json_path = Path(result["outputs"]["json"])
            md_path = Path(result["outputs"]["report_md"])
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            self.assertIn("Research-only experiment", md_path.read_text(encoding="utf-8"))
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["status"], "ok")
            self.assertTrue(payload["summary"]["no_future_leakage"])


def write_strategy_family_fixture(root: Path) -> None:
    outputs = root / "outputs"
    (outputs / "lists").mkdir(parents=True)
    (outputs / "validation").mkdir(parents=True)
    (outputs / "portfolios").mkdir(parents=True)
    _write_json(
        outputs / "lists" / "long_term_stable_2024-01-31.json",
        {"list_id": "long_term_stable", "as_of_date": "2024-01-31", "items": [{"symbol": "LTS1"}, {"symbol": "LTS2"}, {"symbol": "LTS3"}]},
    )
    _write_json(
        outputs / "lists" / "trend_leaders_2024-01-31.json",
        {"list_id": "trend_leaders", "as_of_date": "2024-01-31", "items": [{"symbol": "TRD1"}, {"symbol": "TRD2"}, {"symbol": "TRD3"}]},
    )
    _write_json(
        outputs / "lists" / "breakout_watch_2024-01-31.json",
        {"list_id": "breakout_watch", "as_of_date": "2024-01-31", "items": [{"symbol": "BRK1"}, {"symbol": "BRK2"}, {"symbol": "BRK3"}]},
    )
    _write_json(
        outputs / "lists" / "accumulation_watch_2024-01-31.json",
        {"list_id": "accumulation_watch", "as_of_date": "2024-01-31", "items": [{"symbol": "ACC1"}]},
    )
    _write_json(
        outputs / "lists" / "high_risk_active_2024-01-31.json",
        {"list_id": "high_risk_active", "as_of_date": "2024-01-31", "items": [{"symbol": "BRK3"}]},
    )
    _write_json(outputs / "validation" / "list_performance_2024-01-31_120d.json", [{"list_id": "long_term_stable"}])
    _write_json(outputs / "validation" / "factor_effectiveness_2024-01-31_120d.json", [{"factor_name": "risk_score"}])
    _write_json(outputs / "portfolios" / "portfolio_summary_2024-01-31_120d.json", {"summary": {"status": "ok", "benchmark_symbol": "sh.000300"}, "portfolios": []})
    rows = [
        _prediction("LTS1", 0.10, 0.06, True, -0.03),
        _prediction("LTS2", 0.04, 0.02, True, -0.05),
        _prediction("LTS3", -0.02, -0.03, False, -0.08),
        _prediction("TRD1", 0.50, 0.45, True, -0.11),
        _prediction("TRD2", 0.30, 0.25, True, -0.09),
        _prediction("TRD3", -0.12, -0.17, False, -0.22),
        _prediction("BRK1", 0.20, 0.15, True, -0.14),
        _prediction("BRK2", 0.05, 0.00, False, -0.12),
        _prediction("BRK3", -0.30, -0.35, False, -0.40),
        _prediction("ACC1", 0.15, 0.10, True, -0.10),
    ]
    pd.DataFrame(rows).to_csv(outputs / "validation" / "walk_forward_predictions_2024-01-31_120d.csv", index=False, encoding="utf-8")


def _prediction(symbol: str, future_return: float, excess: float, outperformed: bool, drawdown: float) -> dict[str, object]:
    return {
        "symbol": symbol,
        "as_of_date": "2024-01-31",
        "horizon_days": 120,
        "future_return": future_return,
        "future_excess_return": excess,
        "outperformed_benchmark": outperformed,
        "max_drawdown_during_holding": drawdown,
        "data_quality": "ok",
    }


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

