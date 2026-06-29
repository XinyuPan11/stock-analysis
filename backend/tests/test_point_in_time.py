from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.data.point_in_time import slice_daily_as_of, split_daily_point_in_time
from stock_analysis.research.factors import calculate_stock_factors


class PointInTimeTests(unittest.TestCase):
    def test_slice_excludes_future_rows_and_preserves_input_order(self) -> None:
        frame = pd.DataFrame(
            {
                "trade_date": ["2024-01-03", "2024-02-01", "2024-01-02"],
                "value": [3, 99, 2],
            }
        )

        result = slice_daily_as_of(frame, "2024-01-31")

        self.assertEqual(result.frame["value"].tolist(), [3, 2])
        self.assertEqual(result.as_of_date, "2024-01-31")
        self.assertEqual(result.latest_input_date, "2024-01-03")
        self.assertEqual(result.max_raw_cache_date, "2024-02-01")
        self.assertEqual(result.future_rows_excluded_count, 1)
        self.assertTrue(result.leakage_guard_applied)

    def test_split_separates_feature_and_future_label_windows(self) -> None:
        frame = pd.DataFrame(
            {
                "trade_date": ["2024-01-30", "2024-01-31", "2024-02-01"],
                "value": [1, 2, 3],
            }
        )

        result = split_daily_point_in_time(frame, "2024-01-31")

        self.assertEqual(result.feature_frame["value"].tolist(), [1, 2])
        self.assertEqual(result.future_frame["value"].tolist(), [3])

    def test_malformed_trade_dates_fail_clearly(self) -> None:
        frame = pd.DataFrame({"trade_date": ["2024-01-31", "not-a-date"], "value": [1, 2]})

        with self.assertRaisesRegex(ValueError, "malformed trade_date"):
            slice_daily_as_of(frame, "2024-01-31")

    def test_factor_input_loaded_from_csv_excludes_future_rows(self) -> None:
        dates = pd.date_range("2024-01-01", periods=65, freq="D")
        prices = [100.0 + index for index in range(len(dates))]
        historical = pd.DataFrame(
            {
                "symbol": ["sh.600000"] * len(dates),
                "trade_date": dates.strftime("%Y-%m-%d"),
                "open": prices,
                "high": [price + 1 for price in prices],
                "low": [price - 1 for price in prices],
                "close": prices,
                "volume": [1_000_000] * len(dates),
                "amount": [50_000_000] * len(dates),
                "adj_close": prices,
                "source": ["unit"] * len(dates),
            }
        )
        as_of_date = str(historical.iloc[-1]["trade_date"])
        future = historical.tail(1).copy()
        future["trade_date"] = (pd.Timestamp(as_of_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        future[["open", "high", "low", "close", "adj_close"]] = 10000.0

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir, "sh.600000.csv")
            pd.concat([historical, future], ignore_index=True).to_csv(csv_path, index=False)
            loaded = pd.read_csv(csv_path, dtype={"symbol": str, "trade_date": str, "source": str})

        guard = slice_daily_as_of(loaded, as_of_date)
        factors = calculate_stock_factors(loaded, as_of_date=as_of_date).iloc[0]

        self.assertEqual(guard.latest_input_date, as_of_date)
        self.assertEqual(guard.max_raw_cache_date, future.iloc[0]["trade_date"])
        self.assertEqual(guard.future_rows_excluded_count, 1)
        self.assertLessEqual(guard.latest_input_date, as_of_date)
        self.assertEqual(factors["data_points"], len(historical))


if __name__ == "__main__":
    unittest.main()
