from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.portfolio.portfolio_rules import allocation_counts, get_default_portfolio_rules
from stock_analysis.portfolio.simulator import PortfolioValidationConfig, build_portfolio_holdings, load_list_payloads, run_portfolio_validation


class PortfolioSimulatorTests(unittest.TestCase):
    def test_equal_weight_top_10_portfolio_builds_correctly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_portfolio_fixture(root)
            rule = next(rule for rule in get_default_portfolio_rules() if rule.portfolio_id == "high_confidence_top10")
            payloads = load_list_payloads(root / "outputs", "2024-01-31", [rule])

            holdings = build_portfolio_holdings(rule, payloads)

            self.assertEqual(len(holdings), 10)
            self.assertAlmostEqual(sum(float(row["portfolio_weight"]) for row in holdings), 1.0)
            self.assertEqual(holdings[0]["symbol"], "AAA01")

    def test_top_20_portfolio_uses_twenty_items_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_portfolio_fixture(root)
            rule = next(rule for rule in get_default_portfolio_rules() if rule.portfolio_id == "high_confidence_top20")
            payloads = load_list_payloads(root / "outputs", "2024-01-31", [rule])

            holdings = build_portfolio_holdings(rule, payloads)

            self.assertEqual(len(holdings), 20)

    def test_mixed_baseline_allocation_counts(self) -> None:
        rule = next(rule for rule in get_default_portfolio_rules() if rule.portfolio_id == "mixed_baseline")

        self.assertEqual(allocation_counts(rule), {"trend_leaders": 4, "accumulation_watch": 3, "long_term_stable": 3})

    def test_high_risk_active_is_observation_only(self) -> None:
        rule = next(rule for rule in get_default_portfolio_rules() if rule.portfolio_id == "high_risk_active_observation")

        self.assertTrue(rule.observation_only)

    def test_run_portfolio_validation_dry_run_writes_no_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_portfolio_fixture(root)

            result = run_portfolio_validation(
                PortfolioValidationConfig(
                    as_of_date="2024-01-31",
                    horizon_days=60,
                    outputs_dir=root / "outputs",
                    portfolio_ids=("high_confidence_top10",),
                    dry_run=True,
                )
            )

            self.assertEqual(result["summary"]["status"], "dry_run")
            self.assertTrue(result["summary"]["no_future_leakage"])
            self.assertEqual(result["outputs"], {})
            self.assertFalse((root / "outputs" / "portfolios").exists())

    def test_future_labels_align_with_actual_holdings_not_csv_head(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_portfolio_fixture(root)
            predictions = root / "outputs" / "validation" / "walk_forward_predictions_2024-01-31_60d.csv"
            unrelated = [
                {"symbol": f"ZZZ{index:02d}", "future_return": 0.0, "future_excess_return": 0.0, "outperformed_benchmark": False, "max_drawdown_during_holding": 0.0, "data_quality": "ok"}
                for index in range(1, 51)
            ]
            aligned = [
                {"symbol": f"AAA{index:02d}", "future_return": 0.1, "future_excess_return": 0.02, "outperformed_benchmark": True, "max_drawdown_during_holding": -0.03, "data_quality": "ok"}
                for index in range(1, 11)
            ]
            pd.DataFrame(unrelated + aligned).to_csv(predictions, index=False, encoding="utf-8")

            result = run_portfolio_validation(
                PortfolioValidationConfig(
                    as_of_date="2024-01-31",
                    horizon_days=60,
                    outputs_dir=root / "outputs",
                    portfolio_ids=("high_confidence_top10",),
                    limit=10,
                    dry_run=True,
                )
            )

            portfolio = result["portfolio_performance"][0]
            self.assertEqual(portfolio["holding_count"], 10)
            self.assertEqual(portfolio["valid_future_count"], 10)
            self.assertEqual(portfolio["data_quality_counts"]["ok"], 10)
            self.assertNotIn("missing_future_label", portfolio["data_quality_counts"])

    def test_cache_recomputes_missing_excess_return_for_holdings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outputs = root / "outputs"
            (outputs / "lists").mkdir(parents=True)
            (outputs / "validation").mkdir(parents=True)
            _write_json(
                outputs / "lists" / "high_confidence_candidates_2024-01-31.json",
                {"list_id": "high_confidence_candidates", "as_of_date": "2024-01-31", "items": [_item("AAA01", 1)]},
            )
            pd.DataFrame(
                [{"symbol": "AAA01", "future_return": 0.1, "future_excess_return": None, "benchmark_return": None, "outperformed_benchmark": None, "data_quality": "ok"}]
            ).to_csv(outputs / "validation" / "walk_forward_predictions_2024-01-31_60d.csv", index=False, encoding="utf-8")
            _write_price(root / "cache" / "baostock" / "stock_daily" / "adjusted" / "AAA01.csv", "AAA01", [("2024-01-31", 100), ("2024-02-01", 110)])
            _write_price(root / "cache" / "baostock" / "index_daily" / "raw" / "sh.000300.csv", "sh.000300", [("2024-01-31", 1000), ("2024-02-01", 1010)])

            result = run_portfolio_validation(
                PortfolioValidationConfig(
                    as_of_date="2024-01-31",
                    horizon_days=1,
                    outputs_dir=outputs,
                    cache_dir=root / "cache",
                    portfolio_ids=("high_confidence_top10",),
                    limit=1,
                    dry_run=True,
                )
            )

            portfolio = result["portfolio_performance"][0]
            self.assertAlmostEqual(portfolio["average_excess_return"], 0.09)
            self.assertAlmostEqual(portfolio["outperform_rate"], 1.0)
            self.assertAlmostEqual(portfolio["best_cases"][0]["benchmark_return"], 0.01)
            self.assertEqual(portfolio["best_cases"][0]["outperformed_benchmark"], True)
            self.assertEqual(result["summary"]["benchmark_symbol"], "sh.000300")
            self.assertEqual(result["summary"]["benchmark_data_quality"], "ok")

    def test_cache_recomputes_excess_return_from_csi300_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outputs = root / "outputs"
            (outputs / "lists").mkdir(parents=True)
            (outputs / "validation").mkdir(parents=True)
            _write_json(
                outputs / "lists" / "high_confidence_candidates_2024-01-31.json",
                {"list_id": "high_confidence_candidates", "as_of_date": "2024-01-31", "items": [_item("AAA01", 1)]},
            )
            pd.DataFrame(
                [{"symbol": "AAA01", "future_return": 0.1, "future_excess_return": None, "benchmark_return": None, "outperformed_benchmark": None, "data_quality": "ok"}]
            ).to_csv(outputs / "validation" / "walk_forward_predictions_2024-01-31_60d.csv", index=False, encoding="utf-8")
            _write_price(root / "cache" / "baostock" / "stock_daily" / "adjusted" / "AAA01.csv", "AAA01", [("2024-01-31", 100), ("2024-02-01", 110)])
            _write_price(root / "cache" / "baostock" / "index_daily" / "raw" / "CSI300.csv", "CSI300", [("2024-01-31", 1000), ("2024-02-01", 1020)])

            result = run_portfolio_validation(
                PortfolioValidationConfig(
                    as_of_date="2024-01-31",
                    horizon_days=1,
                    outputs_dir=outputs,
                    cache_dir=root / "cache",
                    benchmark="CSI300",
                    portfolio_ids=("high_confidence_top10",),
                    limit=1,
                    dry_run=True,
                )
            )

            portfolio = result["portfolio_performance"][0]
            self.assertAlmostEqual(portfolio["average_excess_return"], 0.08)
            self.assertAlmostEqual(portfolio["outperform_rate"], 1.0)
            self.assertAlmostEqual(portfolio["best_cases"][0]["benchmark_return"], 0.02)
            self.assertAlmostEqual(portfolio["best_cases"][0]["future_excess_return"], 0.08)
            self.assertEqual(portfolio["best_cases"][0]["outperformed_benchmark"], True)
            self.assertEqual(result["summary"]["benchmark_symbol"], "CSI300")
            self.assertEqual(result["summary"]["benchmark_data_quality"], "ok")

    def test_benchmark_future_window_gap_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outputs = root / "outputs"
            (outputs / "lists").mkdir(parents=True)
            (outputs / "validation").mkdir(parents=True)
            _write_json(
                outputs / "lists" / "high_confidence_candidates_2024-01-31.json",
                {"list_id": "high_confidence_candidates", "as_of_date": "2024-01-31", "items": [_item("AAA01", 1)]},
            )
            pd.DataFrame(
                [{"symbol": "AAA01", "future_return": 0.1, "future_excess_return": None, "benchmark_return": None, "outperformed_benchmark": None, "data_quality": "ok"}]
            ).to_csv(outputs / "validation" / "walk_forward_predictions_2024-01-31_60d.csv", index=False, encoding="utf-8")
            _write_price(root / "cache" / "baostock" / "stock_daily" / "adjusted" / "AAA01.csv", "AAA01", [("2024-01-31", 100), ("2024-02-01", 110)])
            _write_price(root / "cache" / "baostock" / "index_daily" / "raw" / "CSI300.csv", "CSI300", [("2024-01-31", 1000)])

            result = run_portfolio_validation(
                PortfolioValidationConfig(
                    as_of_date="2024-01-31",
                    horizon_days=1,
                    outputs_dir=outputs,
                    cache_dir=root / "cache",
                    benchmark="CSI300",
                    portfolio_ids=("high_confidence_top10",),
                    limit=1,
                    dry_run=False,
                )
            )

            portfolio = result["portfolio_performance"][0]
            self.assertIsNone(portfolio["average_excess_return"])
            self.assertIn("benchmark_missing", portfolio["notes"])
            self.assertEqual(result["summary"]["benchmark_data_quality"], "benchmark_insufficient_future_window")
            cache_plan = (outputs / "portfolios" / "portfolio_cache_plan_2024-01-31_1d_limit1.txt").read_text(encoding="utf-8")
            self.assertIn("Benchmark data quality is benchmark_insufficient_future_window", cache_plan)

    def test_chinese_names_and_labels_are_written_as_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outputs = root / "outputs"
            (outputs / "lists").mkdir(parents=True)
            (outputs / "validation").mkdir(parents=True)
            _write_json(
                outputs / "lists" / "high_confidence_candidates_2024-01-31.json",
                {
                    "list_id": "high_confidence_candidates",
                    "as_of_date": "2024-01-31",
                    "items": [{"symbol": "AAA01", "name": "保利发展", "rank": 1, "total_score": 90, "primary_type": "趋势龙头型", "secondary_tags": ["潜力蓄势型"]}],
                },
            )
            pd.DataFrame([{"symbol": "AAA01", "future_return": 0.1, "future_excess_return": 0.02, "outperformed_benchmark": True, "max_drawdown_during_holding": -0.03, "data_quality": "ok"}]).to_csv(
                outputs / "validation" / "walk_forward_predictions_2024-01-31_60d.csv",
                index=False,
                encoding="utf-8",
            )

            run_portfolio_validation(
                PortfolioValidationConfig(as_of_date="2024-01-31", horizon_days=60, outputs_dir=outputs, portfolio_ids=("high_confidence_top10",), dry_run=False)
            )

            holdings_text = (outputs / "portfolios" / "portfolio_holdings_2024-01-31_60d.csv").read_text(encoding="utf-8")
            review_text = (outputs / "reviews" / "portfolio_review_2024-01-31_60d.json").read_text(encoding="utf-8")
            summary_text = (outputs / "portfolios" / "portfolio_summary_2024-01-31_60d.json").read_text(encoding="utf-8")
            self.assertIn("保利发展", holdings_text)
            self.assertIn("趋势龙头型", holdings_text)
            self.assertIn("潜力蓄势型", holdings_text)
            self.assertIn("保利发展", review_text)
            self.assertIn("保利发展", summary_text)


def write_portfolio_fixture(root: Path) -> None:
    outputs = root / "outputs"
    (outputs / "lists").mkdir(parents=True)
    (outputs / "validation").mkdir(parents=True)
    for list_id, prefix, count in [
        ("high_confidence_candidates", "AAA", 25),
        ("trend_leaders", "TRD", 12),
        ("accumulation_watch", "ACC", 12),
        ("long_term_stable", "LTS", 12),
        ("breakout_watch", "BRK", 12),
        ("high_risk_active", "RSK", 12),
    ]:
        _write_json(
            outputs / "lists" / f"{list_id}_2024-01-31.json",
            {
                "list_id": list_id,
                "as_of_date": "2024-01-31",
                "items": [_item(f"{prefix}{index:02d}", index) for index in range(1, count + 1)],
            },
        )
    _write_json(outputs / "lists" / "rebound_watch_2024-01-31.json", {"list_id": "rebound_watch", "as_of_date": "2024-01-31", "items": []})
    rows = []
    for symbol in [f"AAA{index:02d}" for index in range(1, 26)] + [f"TRD{index:02d}" for index in range(1, 13)] + [f"ACC{index:02d}" for index in range(1, 13)] + [f"LTS{index:02d}" for index in range(1, 13)] + [f"BRK{index:02d}" for index in range(1, 13)] + [f"RSK{index:02d}" for index in range(1, 13)]:
        rows.append(
            {
                "symbol": symbol,
                "as_of_date": "2024-01-31",
                "horizon_days": 60,
                "future_return": 0.1 if not symbol.endswith("02") else -0.05,
                "future_excess_return": 0.02 if not symbol.endswith("02") else -0.08,
                "outperformed_benchmark": not symbol.endswith("02"),
                "max_drawdown_during_holding": -0.04 if not symbol.endswith("02") else -0.2,
                "data_quality": "ok",
            }
        )
    pd.DataFrame(rows).to_csv(outputs / "validation" / "walk_forward_predictions_2024-01-31_60d.csv", index=False, encoding="utf-8")


def _item(symbol: str, rank: int) -> dict[str, object]:
    return {
        "symbol": symbol,
        "name": f"Name {symbol}",
        "rank": rank,
        "total_score": 100 - rank,
        "primary_type": "technical_candidate",
        "secondary_tags": ["trend", "liquidity"],
    }


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_price(path: Path, symbol: str, rows: list[tuple[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "symbol": [symbol] * len(rows),
            "trade_date": [row[0] for row in rows],
            "close": [row[1] for row in rows],
            "adj_close": [row[1] for row in rows],
            "source": ["unit"] * len(rows),
        }
    ).to_csv(path, index=False, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
