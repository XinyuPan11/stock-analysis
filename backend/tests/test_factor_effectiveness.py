from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.validation.factor_effectiveness import evaluate_factor_effectiveness


class FactorEffectivenessTests(unittest.TestCase):
    def test_factor_effectiveness_calculates_spread(self) -> None:
        factors = pd.DataFrame(
            [
                {"symbol": "AAA", "total_score": 90},
                {"symbol": "BBB", "total_score": 70},
                {"symbol": "CCC", "total_score": 30},
            ]
        )
        labels = pd.DataFrame(
            [
                {"symbol": "AAA", "future_return": 0.10, "outperformed_benchmark": True, "data_quality": "ok"},
                {"symbol": "BBB", "future_return": 0.03, "outperformed_benchmark": True, "data_quality": "ok"},
                {"symbol": "CCC", "future_return": -0.02, "outperformed_benchmark": False, "data_quality": "ok"},
            ]
        )

        result = evaluate_factor_effectiveness(factors, labels, as_of_date="2024-01-31", horizon_days=20, factor_names=["total_score"])

        self.assertEqual(result[0]["notes"], [])
        self.assertGreater(result[0]["spread"], 0)
        self.assertGreater(result[0]["correlation_with_future_return"], 0)

    def test_missing_factor_is_reported(self) -> None:
        result = evaluate_factor_effectiveness(
            [{"symbol": "AAA", "total_score": 90}],
            [{"symbol": "AAA", "future_return": 0.1, "data_quality": "ok"}],
            as_of_date="2024-01-31",
            horizon_days=20,
            factor_names=["not_present"],
        )

        self.assertIn("missing_factor", result[0]["notes"])


if __name__ == "__main__":
    unittest.main()

