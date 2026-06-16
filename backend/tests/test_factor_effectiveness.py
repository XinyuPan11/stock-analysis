from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.validation.factor_effectiveness import evaluate_factor_effectiveness
from stock_analysis.validation.walk_forward import load_factor_rows_for_validation


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

    def test_factor_rows_can_merge_scores_from_labels_and_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outputs = root / "outputs"
            (outputs / "labels").mkdir(parents=True)
            (outputs / "daily").mkdir(parents=True)
            (outputs / "lists").mkdir(parents=True)
            _write_json(outputs / "labels" / "stock_labels_2024-01-31.json", [{"symbol": "AAA", "total_score": 90, "score_breakdown": {"momentum_score": 80}}])
            _write_json(outputs / "daily" / "candidates_2024-01-31.json", [{"symbol": "AAA", "trend_score": 70, "relative_strength_score": 60}])
            _write_json(outputs / "daily" / "factors_2024-01-31.json", [{"symbol": "AAA", "volatility_20d": 0.2, "max_drawdown": -0.1, "avg_amount_20d": 1000}])
            _write_json(outputs / "lists" / "multi_lists_2024-01-31.json", {"lists": [{"items": [{"symbol": "AAA", "risk_score": 50, "liquidity_score": 40}]}]})

            rows = load_factor_rows_for_validation(outputs, "2024-01-31", pd.DataFrame([{"symbol": "AAA"}]))

        self.assertIn("total_score", rows.columns)
        self.assertIn("momentum_score", rows.columns)
        self.assertIn("trend_score", rows.columns)
        self.assertIn("volatility", rows.columns)
        self.assertEqual(float(rows.iloc[0]["total_score"]), 90)


def _write_json(path: Path, payload: object) -> None:
    import json

    path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
