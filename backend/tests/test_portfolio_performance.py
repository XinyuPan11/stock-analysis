from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.portfolio.performance import evaluate_portfolio_performance
from stock_analysis.portfolio.portfolio_rules import PortfolioRule


class PortfolioPerformanceTests(unittest.TestCase):
    def test_transaction_cost_adjusts_net_average_return(self) -> None:
        holdings = [{"symbol": "AAA"}, {"symbol": "BBB"}]
        labels = pd.DataFrame(
            [
                {"symbol": "AAA", "future_return": 0.10, "future_excess_return": 0.03, "outperformed_benchmark": True, "max_drawdown_during_holding": -0.05, "data_quality": "ok"},
                {"symbol": "BBB", "future_return": 0.00, "future_excess_return": -0.02, "outperformed_benchmark": False, "max_drawdown_during_holding": -0.10, "data_quality": "ok"},
            ]
        )

        result = evaluate_portfolio_performance("test", holdings, labels, rule=PortfolioRule("test"), as_of_date="2024-01-31", horizon_days=60, transaction_cost_bps=10)

        self.assertEqual(result["valid_future_count"], 2)
        self.assertAlmostEqual(result["average_future_return"], 0.05)
        self.assertAlmostEqual(result["net_average_return"], 0.049)
        self.assertAlmostEqual(result["win_rate"], 0.5)
        self.assertAlmostEqual(result["outperform_rate"], 0.5)

    def test_empty_portfolio_does_not_crash(self) -> None:
        result = evaluate_portfolio_performance("empty", [], pd.DataFrame(), rule=PortfolioRule("empty"), as_of_date="2024-01-31", horizon_days=60)

        self.assertEqual(result["holding_count"], 0)
        self.assertIn("empty_portfolio", result["notes"])

    def test_missing_future_labels_returns_clear_quality_note(self) -> None:
        holdings = [{"symbol": "AAA"}]
        labels = pd.DataFrame([{"symbol": "BBB", "data_quality": "ok", "future_return": 0.1}])

        result = evaluate_portfolio_performance("missing", holdings, labels, rule=PortfolioRule("missing"), as_of_date="2024-01-31", horizon_days=60)

        self.assertEqual(result["valid_future_count"], 0)
        self.assertIn("no_valid_future_labels", result["notes"])
        self.assertIn("low_future_label_coverage", result["notes"])
        self.assertIn("portfolio_result_not_reliable", result["notes"])
        self.assertIn("needs_portfolio_cache_prep", result["notes"])
        self.assertEqual(result["data_quality_counts"]["missing_future_label"], 1)

    def test_low_valid_future_count_triggers_coverage_warning(self) -> None:
        holdings = [{"symbol": "AAA"}, {"symbol": "BBB"}, {"symbol": "CCC"}]
        labels = pd.DataFrame(
            [
                {"symbol": "AAA", "future_return": 0.1, "future_excess_return": 0.02, "outperformed_benchmark": True, "data_quality": "ok"},
                {"symbol": "BBB", "data_quality": "missing_price"},
            ]
        )

        result = evaluate_portfolio_performance("low", holdings, labels, rule=PortfolioRule("low"), as_of_date="2024-01-31", horizon_days=60)

        self.assertEqual(result["valid_future_count"], 1)
        self.assertIn("low_future_label_coverage", result["notes"])
        self.assertNotIn("BBB", result["missing_future_label_symbols"])
        self.assertIn("CCC", result["missing_future_label_symbols"])
        self.assertIn("BBB", result["non_ok_future_label_symbols"])
        self.assertIn("CCC", result["non_ok_future_label_symbols"])


if __name__ == "__main__":
    unittest.main()
