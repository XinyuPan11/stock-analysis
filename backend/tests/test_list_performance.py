from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.validation.list_performance import evaluate_list_performance


class ListPerformanceTests(unittest.TestCase):
    def test_list_performance_calculates_average_and_outperform_rate(self) -> None:
        payload = {"list_id": "trend_leaders", "as_of_date": "2024-01-31", "items": [{"symbol": "AAA"}, {"symbol": "BBB"}]}
        labels = pd.DataFrame(
            [
                {"symbol": "AAA", "future_return": 0.10, "future_excess_return": 0.08, "outperformed_benchmark": True, "max_drawdown_during_holding": -0.02, "data_quality": "ok"},
                {"symbol": "BBB", "future_return": -0.02, "future_excess_return": -0.04, "outperformed_benchmark": False, "max_drawdown_during_holding": -0.05, "data_quality": "ok"},
            ]
        )

        result = evaluate_list_performance(payload, labels, horizon_days=20)

        self.assertEqual(result["valid_future_count"], 2)
        self.assertAlmostEqual(result["average_future_return"], 0.04)
        self.assertAlmostEqual(result["outperform_rate"], 0.5)
        self.assertEqual(result["notes"], [])

    def test_empty_list_returns_note_without_error(self) -> None:
        result = evaluate_list_performance({"list_id": "rebound_watch", "as_of_date": "2024-01-31", "items": []}, [], horizon_days=20)

        self.assertEqual(result["item_count"], 0)
        self.assertIn("empty_list", result["notes"])


if __name__ == "__main__":
    unittest.main()

