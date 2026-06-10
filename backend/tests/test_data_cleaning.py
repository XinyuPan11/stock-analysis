from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.data.data_cleaning import MarketDataQualityError, clean_market_data_frame


class DataCleaningTests(unittest.TestCase):
    def test_numeric_strings_convert_successfully(self) -> None:
        frame = clean_market_data_frame(_raw(open_value="10.5", amount="1,000"), source="unit", symbol="AAA")

        self.assertEqual(float(frame["open"].iloc[0]), 10.5)
        self.assertEqual(float(frame["amount"].iloc[0]), 1000.0)

    def test_non_numeric_price_field_is_classified(self) -> None:
        with self.assertRaisesRegex(MarketDataQualityError, "non_numeric_market_data"):
            clean_market_data_frame(_raw(close_value="bad"), source="unit", symbol="AAA")

    def test_empty_market_data_is_classified(self) -> None:
        with self.assertRaisesRegex(MarketDataQualityError, "empty_market_data"):
            clean_market_data_frame(pd.DataFrame(), source="unit", symbol="AAA")

    def test_missing_required_columns_are_classified(self) -> None:
        raw = _raw().drop(columns=["open"])

        with self.assertRaisesRegex(MarketDataQualityError, "missing_required_columns"):
            clean_market_data_frame(raw, source="unit", symbol="AAA")

    def test_invalid_price_data_is_classified(self) -> None:
        with self.assertRaisesRegex(MarketDataQualityError, "invalid_price_data"):
            clean_market_data_frame(_raw(high="9", low="11"), source="unit", symbol="AAA")

    def test_missing_liquidity_data_warns_and_fills_zero(self) -> None:
        raw = _raw().drop(columns=["volume", "amount"])

        frame = clean_market_data_frame(raw, source="unit", symbol="AAA")

        self.assertEqual(float(frame["volume"].iloc[0]), 0.0)
        self.assertEqual(float(frame["amount"].iloc[0]), 0.0)
        self.assertIn("missing_liquidity_data", frame.attrs["warnings"])


def _raw(
    *,
    open_value: object = "10",
    close_value: object = "10.2",
    high: object = "10.5",
    low: object = "9.8",
    amount: object = "100000",
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "trade_date": ["2024-01-02"],
            "open": [open_value],
            "high": [high],
            "low": [low],
            "close": [close_value],
            "volume": ["1000"],
            "amount": [amount],
            "adj_close": [close_value],
        }
    )


if __name__ == "__main__":
    unittest.main()
