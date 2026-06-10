from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.research.ashare_filters import (
    FilterConfig,
    filter_by_listing_age,
    filter_by_liquidity,
    filter_by_price_history_quality,
    filter_by_stock_status,
    filter_universe,
)


class AShareFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = FilterConfig(
            as_of_date="2024-01-31",
            min_listing_days=180,
            history_window_days=60,
            min_valid_trading_days=20,
            liquidity_window_days=20,
            min_avg_amount_20d=20_000_000,
            max_missing_ratio=0.2,
        )

    def test_st_stock_is_filtered(self) -> None:
        decision = filter_by_stock_status(_stock("000001", name="ST Sample"))

        self.assertIn("stock_status_risk", decision.reasons)

    def test_delisted_or_non_normal_status_is_filtered(self) -> None:
        decision = filter_by_stock_status(_stock("000002", listing_status="delisted", delisting_date="2024-01-01"))

        self.assertIn("non_normal_listing_status", decision.reasons)
        self.assertIn("delisted_or_out_date_present", decision.reasons)

    def test_recent_listing_is_filtered(self) -> None:
        decision = filter_by_listing_age(_stock("000003", listing_date="2023-12-15"), as_of_date="2024-01-31")

        self.assertEqual(decision.reasons, ("listed_less_than_180_days",))

    def test_low_recent_amount_is_filtered(self) -> None:
        history = _prices("000004", amount=1_000_000)

        decision = filter_by_liquidity("000004", history, min_avg_amount_20d=20_000_000)

        self.assertEqual(decision.reasons, ("low_20d_average_amount",))

    def test_severe_missing_daily_data_is_filtered(self) -> None:
        history = _prices("000005", amount=50_000_000)
        history.loc[:9, "close"] = None

        decision = filter_by_price_history_quality(
            "000005",
            history,
            as_of_date="2024-01-31",
            max_missing_ratio=0.2,
        )

        self.assertIn("severe_missing_price_data", decision.reasons)

    def test_normal_stock_passes_universe_filter(self) -> None:
        universe = pd.DataFrame([_stock("000006")])
        result = filter_universe(universe, _prices("000006", amount=50_000_000), config=self.config)

        self.assertEqual(result.passed_universe["symbol"].tolist(), ["000006"])
        self.assertTrue(result.filtered_stocks.empty)

    def test_multiple_filter_reasons_are_recorded(self) -> None:
        universe = pd.DataFrame([_stock("000007", name="*ST Multi")])
        history = _prices("000007", amount=1_000_000)
        history.loc[0, "high"] = 8

        result = filter_universe(universe, history, config=self.config)
        reasons = result.filtered_stocks.loc[0, "reasons"]

        self.assertIn("stock_status_risk", reasons)
        self.assertIn("low_20d_average_amount", reasons)
        self.assertIn("close_outside_high_low", reasons)

    def test_missing_listing_date_returns_warning_without_silent_skip(self) -> None:
        stock = _stock("000008", listing_date="")

        decision = filter_by_listing_age(stock, as_of_date="2024-01-31")

        self.assertEqual(decision.reasons, ())
        self.assertEqual(decision.warnings, ("listing_date_missing",))

    def test_missing_listing_date_warning_surfaces_in_filter_result(self) -> None:
        universe = pd.DataFrame([_stock("000009", listing_date="")])
        result = filter_universe(universe, _prices("000009", amount=50_000_000), config=self.config)

        self.assertEqual(result.passed_universe["symbol"].tolist(), ["000009"])
        self.assertIn("listing_date_missing", result.warnings)
        self.assertEqual(result.stats["warning_count"], 1)


def _stock(
    symbol: str,
    *,
    name: str = "Normal Stock",
    listing_status: str = "listed",
    listing_date: str = "2020-01-01",
    delisting_date: str = "",
    is_st: str = "",
) -> dict[str, str]:
    return {
        "symbol": symbol,
        "name": name,
        "exchange": "SZSE" if symbol.startswith(("0", "3")) else "SSE",
        "listing_status": listing_status,
        "listing_date": listing_date,
        "delisting_date": delisting_date,
        "is_st": is_st,
        "source": "unit",
    }


def _prices(symbol: str, *, amount: float) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", "2024-01-31", freq="B").strftime("%Y-%m-%d").tolist()
    return pd.DataFrame(
        {
            "symbol": [symbol] * len(dates),
            "trade_date": dates,
            "open": [10.0] * len(dates),
            "high": [11.0] * len(dates),
            "low": [9.0] * len(dates),
            "close": [10.5] * len(dates),
            "volume": [1_000_000] * len(dates),
            "amount": [amount] * len(dates),
            "adj_close": [10.5] * len(dates),
            "source": ["unit"] * len(dates),
        }
    )


if __name__ == "__main__":
    unittest.main()
