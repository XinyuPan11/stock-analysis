from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.validation.future_returns import calculate_future_return_label, calculate_future_return_labels


class FutureReturnTests(unittest.TestCase):
    def test_future_return_and_benchmark_excess_are_calculated(self) -> None:
        stock = _price_frame("AAA", [("2024-01-31", 100), ("2024-02-01", 105), ("2024-02-02", 110)])
        benchmark = _price_frame("CSI300", [("2024-01-31", 200), ("2024-02-01", 201), ("2024-02-02", 202)])

        label = calculate_future_return_label("AAA", stock, as_of_date="2024-01-31", horizon_days=2, benchmark_history=benchmark)

        self.assertEqual(label["data_quality"], "ok")
        self.assertEqual(label["benchmark_data_quality"], "ok")
        self.assertAlmostEqual(label["future_return"], 0.10)
        self.assertAlmostEqual(label["benchmark_return"], 0.01)
        self.assertAlmostEqual(label["future_excess_return"], 0.09)
        self.assertTrue(label["outperformed_benchmark"])

    def test_benchmark_missing_is_explicitly_marked(self) -> None:
        stock = _price_frame("AAA", [("2024-01-31", 100), ("2024-02-01", 105)])

        label = calculate_future_return_label("AAA", stock, as_of_date="2024-01-31", horizon_days=1, benchmark_history=None)

        self.assertEqual(label["data_quality"], "ok")
        self.assertEqual(label["benchmark_data_quality"], "benchmark_missing")
        self.assertIsNone(label["future_excess_return"])

    def test_insufficient_future_window_is_reported(self) -> None:
        stock = _price_frame("AAA", [("2024-01-31", 100), ("2024-02-01", 105)])

        label = calculate_future_return_label("AAA", stock, as_of_date="2024-01-31", horizon_days=2)

        self.assertEqual(label["data_quality"], "insufficient_future_window")
        self.assertIsNone(label["future_return"])

    def test_missing_price_does_not_break_batch(self) -> None:
        labels = calculate_future_return_labels(
            ["AAA", "MISSING"],
            {"AAA": _price_frame("AAA", [("2024-01-31", 100), ("2024-02-01", 103)])},
            as_of_date="2024-01-31",
            horizon_days=1,
        )

        by_symbol = {row["symbol"]: row for row in labels}
        self.assertEqual(by_symbol["AAA"]["data_quality"], "ok")
        self.assertEqual(by_symbol["MISSING"]["data_quality"], "missing_price")

    def test_top_quantile_flag_is_assigned_after_batch(self) -> None:
        labels = calculate_future_return_labels(
            ["AAA", "BBB", "CCC"],
            {
                "AAA": _price_frame("AAA", [("2024-01-31", 100), ("2024-02-01", 120)]),
                "BBB": _price_frame("BBB", [("2024-01-31", 100), ("2024-02-01", 105)]),
                "CCC": _price_frame("CCC", [("2024-01-31", 100), ("2024-02-01", 90)]),
            },
            as_of_date="2024-01-31",
            horizon_days=1,
            top_quantile=0.34,
        )

        by_symbol = {row["symbol"]: row for row in labels}
        self.assertTrue(by_symbol["AAA"]["future_top_quantile"])
        self.assertFalse(by_symbol["CCC"]["future_top_quantile"])


def _price_frame(symbol: str, rows: list[tuple[str, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": [symbol] * len(rows),
            "trade_date": [row[0] for row in rows],
            "open": [row[1] for row in rows],
            "high": [row[1] for row in rows],
            "low": [row[1] for row in rows],
            "close": [row[1] for row in rows],
            "volume": [1000] * len(rows),
            "amount": [10000] * len(rows),
            "adj_close": [row[1] for row in rows],
            "source": ["unit"] * len(rows),
        }
    )


if __name__ == "__main__":
    unittest.main()
