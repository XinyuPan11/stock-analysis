from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.analysis.price_analysis import calculate_return_summary
from stock_analysis.data.cache import FileDataFrameCache
from stock_analysis.data.providers.base import MarketDataProvider
from stock_analysis.data.schemas import MARKET_DATA_COLUMNS, normalize_market_data_frame
from stock_analysis.data.service import MarketDataService


class FakeProvider(MarketDataProvider):
    source = "fake"

    def __init__(self) -> None:
        self.stock_calls = 0
        self.index_calls = 0

    def get_stock_daily(self, symbol: str, start_date: str, end_date: str, adjusted: bool = True) -> pd.DataFrame:
        self.stock_calls += 1
        return pd.DataFrame(
            {
                "symbol": [symbol, symbol],
                "trade_date": ["2024-01-02", "2024-01-03"],
                "open": [10, 11],
                "high": [11, 12],
                "low": [9, 10],
                "close": [10.5, 11.5],
                "volume": [1000, 1200],
                "amount": [10000, 13200],
                "adj_close": [10.5, 11.5],
                "source": [self.source, self.source],
            }
        )

    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        self.index_calls += 1
        return self.get_stock_daily(index_code, start_date, end_date, adjusted=False)


class DataLayerTests(unittest.TestCase):
    def test_normalize_market_data_frame_outputs_required_schema(self) -> None:
        raw = pd.DataFrame(
            {
                "日期": ["20240102"],
                "开盘": ["10.0"],
                "最高": ["11.0"],
                "最低": ["9.0"],
                "收盘": ["10.5"],
                "成交量": ["1000"],
                "成交额": ["10000"],
            }
        )

        normalized = normalize_market_data_frame(
            raw,
            source="unit",
            symbol="000001",
            column_map={
                "trade_date": "日期",
                "open": "开盘",
                "high": "最高",
                "low": "最低",
                "close": "收盘",
                "volume": "成交量",
                "amount": "成交额",
                "adj_close": "收盘",
            },
        )

        self.assertEqual(list(normalized.columns), MARKET_DATA_COLUMNS)
        self.assertEqual(normalized.loc[0, "trade_date"], "2024-01-02")
        self.assertEqual(normalized.loc[0, "source"], "unit")

    def test_service_uses_cache_and_provider_independent_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FakeProvider()
            service = MarketDataService(provider=provider, cache=FileDataFrameCache(temp_dir, ttl_seconds=3600))

            first = service.get_stock_daily("000001", "2024-01-01", "2024-01-31")
            second = service.get_stock_daily("000001", "2024-01-01", "2024-01-31")

            self.assertEqual(provider.stock_calls, 1)
            self.assertTrue(first.equals(second))
            self.assertEqual(list(first.columns), MARKET_DATA_COLUMNS)

    def test_analysis_depends_on_normalized_schema_only(self) -> None:
        provider = FakeProvider()
        data = provider.get_stock_daily("000001", "2024-01-01", "2024-01-31")

        summary = calculate_return_summary(data)

        self.assertEqual(summary["rows"], 2)
        self.assertGreater(summary["total_return"], 0)


if __name__ == "__main__":
    unittest.main()
