from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.validation.asof_recovery import (  # noqa: E402
    ControlledAsOfRecoveryConfig,
    diagnose_controlled_2024_10_31_20d_recovery,
)


class ControlledAsOfRecoveryTests(unittest.TestCase):
    def test_missing_as_of_outputs_blocks_before_cache_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            result = diagnose_controlled_2024_10_31_20d_recovery(
                _config(root)
            )

            self.assertEqual(result["status"], "blocked_missing_as_of_outputs")
            self.assertEqual(result["root_cause"], "missing_as_of_outputs")
            self.assertEqual(result["as_of_date"], "2024-10-31")
            self.assertEqual(result["horizon_days"], 20)
            self.assertEqual(result["required_future_end_date"], "2024-12-10")
            self.assertTrue(result["future_window_recoverable_with_late_2024_cache"])
            self.assertFalse(result["as_of_result_recoverable_with_cache_through_late_2024_only"])
            self.assertEqual(result["candidate_count"], 0)
            self.assertEqual(result["valid_future_count"], 0)
            self.assertIn("stock_labels", result["missing_as_of_outputs"])
            self.assertIn("generate_as_of_outputs_before_cache_or_validation_recovery", result["notes"])
            self.assertTrue(
                any("run_daily_research.py" in command for command in result["next_manual_commands"])
            )

    def test_prediction_quality_counts_and_skipped_symbols_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outputs = root / "outputs"
            _write_as_of_outputs(outputs)
            _write_predictions(outputs)
            _write_symbols(outputs, ["AAA", "BBB", "CCC", "DDD"])
            _write_cache_prices(root / "cache", ["AAA", "BBB", "CCC", "DDD"])

            result = diagnose_controlled_2024_10_31_20d_recovery(
                _config(root, min_valid_count=2)
            )

            self.assertEqual(result["status"], "missing_validation_outputs")
            self.assertEqual(result["required_future_end_date"], "2024-12-10")
            self.assertTrue(result["as_of_result_recoverable_with_cache_through_late_2024_only"])
            self.assertEqual(result["candidate_count"], 4)
            self.assertEqual(result["prediction_count"], 4)
            self.assertEqual(result["valid_future_count"], 2)
            self.assertEqual(result["missing_price_count"], 1)
            self.assertEqual(result["insufficient_future_window_count"], 1)
            self.assertEqual(result["quality_status"], "low_coverage")
            self.assertTrue(result["comparison_eligible"])
            self.assertFalse(result["high_quality_ready"])
            skipped = {(row["symbol"], row["reason"]) for row in result["skipped_symbols"]}
            self.assertIn(("CCC", "missing_price"), skipped)
            self.assertIn(("DDD", "insufficient_future_window"), skipped)
            self.assertEqual(result["cache_coverage"]["covered_count"], 4)


def _config(
    root: Path,
    *,
    min_valid_count: int = 50,
) -> ControlledAsOfRecoveryConfig:
    return ControlledAsOfRecoveryConfig(
        outputs_dir=root / "outputs",
        cache_dir=root / "cache",
        limit=300,
        min_valid_count=min_valid_count,
        min_coverage_rate=0.7,
    )


def _write_as_of_outputs(outputs: Path) -> None:
    labels = outputs / "labels"
    daily = outputs / "daily"
    lists = outputs / "lists"
    labels.mkdir(parents=True, exist_ok=True)
    daily.mkdir(parents=True, exist_ok=True)
    lists.mkdir(parents=True, exist_ok=True)
    rows = [{"symbol": symbol, "total_score": 80 - index} for index, symbol in enumerate(["AAA", "BBB", "CCC", "DDD"])]
    (labels / "stock_labels_2024-10-31.json").write_text(json.dumps(rows), encoding="utf-8")
    pd.DataFrame(rows).to_csv(daily / "factors_2024-10-31.csv", index=False)
    (lists / "high_confidence_candidates_2024-10-31.json").write_text(
        json.dumps({"list_id": "high_confidence_candidates", "items": rows}),
        encoding="utf-8",
    )


def _write_predictions(outputs: Path) -> None:
    path = outputs / "validation" / "walk_forward_predictions_2024-10-31_20d.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {"symbol": "AAA", "future_return": 0.10, "data_quality": "ok"},
            {"symbol": "BBB", "future_return": 0.05, "data_quality": "ok"},
            {"symbol": "CCC", "future_return": None, "data_quality": "missing_price"},
            {"symbol": "DDD", "future_return": None, "data_quality": "insufficient_future_window"},
        ]
    ).to_csv(path, index=False)


def _write_symbols(outputs: Path, symbols: list[str]) -> None:
    path = outputs / "cache_plans" / "multi_asof_symbols_2024-10-31_20d.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(symbols) + "\n", encoding="utf-8")


def _write_cache_prices(cache: Path, symbols: list[str]) -> None:
    for symbol in symbols:
        path = cache / "baostock" / "stock_daily" / "adjusted" / f"{symbol}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            [
                {"symbol": symbol, "trade_date": "2024-10-31", "close": 10.0, "adj_close": 10.0},
                {"symbol": symbol, "trade_date": "2024-11-01", "close": 10.2, "adj_close": 10.2},
                {"symbol": symbol, "trade_date": "2024-12-10", "close": 10.5, "adj_close": 10.5},
            ]
        ).to_csv(path, index=False)


if __name__ == "__main__":
    unittest.main()
