from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.data.cache import LocalCsvCache
from stock_analysis.data.providers.akshare_provider import AkShareProvider
from stock_analysis.data.providers.baostock_provider import BaoStockProvider
from stock_analysis.data.providers.base import MarketDataProvider, ProviderDataError
from stock_analysis.data.schemas import (
    MARKET_DATA_COLUMNS,
    STOCK_UNIVERSE_COLUMNS,
    normalize_market_data_frame,
    normalize_stock_universe_frame,
)
from stock_analysis.data.service import MarketDataService


class FakeProvider(MarketDataProvider):
    source = "fake"

    def __init__(self) -> None:
        self.stock_calls: list[tuple[str, str, str, bool]] = []
        self.index_calls: list[tuple[str, str, str]] = []
        self.universe_calls = 0

    def get_stock_universe(self) -> pd.DataFrame:
        self.universe_calls += 1
        return pd.DataFrame(
            {
                "symbol": ["000001", "600000"],
                "name": ["Ping An Bank", "SPDB"],
                "exchange": ["SZSE", "SSE"],
                "listing_status": ["listed", "listed"],
                "source": [self.source, self.source],
            }
        )

    def get_stock_daily(self, symbol: str, start_date: str, end_date: str, adjusted: bool = True) -> pd.DataFrame:
        self.stock_calls.append((symbol, start_date, end_date, adjusted))
        dates = pd.date_range(start_date, end_date, freq="D").strftime("%Y-%m-%d").tolist()
        return _market_frame(symbol=symbol, dates=dates, source=self.source)

    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        self.index_calls.append((index_code, start_date, end_date))
        dates = pd.date_range(start_date, end_date, freq="D").strftime("%Y-%m-%d").tolist()
        return _market_frame(symbol=index_code, dates=dates, source=self.source)


class FailingProvider(FakeProvider):
    source = "failing"

    def get_stock_daily(self, symbol: str, start_date: str, end_date: str, adjusted: bool = True) -> pd.DataFrame:
        raise RuntimeError("upstream timeout")


class TradingDayProvider(FakeProvider):
    source = "trading-day"

    def get_stock_daily(self, symbol: str, start_date: str, end_date: str, adjusted: bool = True) -> pd.DataFrame:
        self.stock_calls.append((symbol, start_date, end_date, adjusted))
        dates = [
            value
            for value in pd.date_range(start_date, end_date, freq="D").strftime("%Y-%m-%d").tolist()
            if value != "2024-01-01"
        ]
        return _market_frame(symbol=symbol, dates=dates, source=self.source)


class FakeAkShareModule:
    def stock_info_a_code_name(self) -> pd.DataFrame:
        return pd.DataFrame({"code": ["000001", "600000"], "name": ["Ping An Bank", "SPDB"]})

    def stock_zh_a_hist(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "\u65e5\u671f": ["2024-01-02"],
                "\u5f00\u76d8": [10],
                "\u6700\u9ad8": [11],
                "\u6700\u4f4e": [9],
                "\u6536\u76d8": [10.5],
                "\u6210\u4ea4\u91cf": [1000],
                "\u6210\u4ea4\u989d": [10000],
            }
        )

    def stock_zh_index_daily(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "date": ["2024-01-02"],
                "open": [10],
                "high": [11],
                "low": [9],
                "close": [10.5],
                "volume": [1000],
                "amount": [10000],
            }
        )


class FakeBaoResult:
    error_code = "0"
    error_msg = "success"

    def __init__(self, fields: list[str], rows: list[list[str]]) -> None:
        self.fields = fields
        self.rows = rows
        self.index = -1

    def next(self) -> bool:
        self.index += 1
        return self.index < len(self.rows)

    def get_row_data(self) -> list[str]:
        return self.rows[self.index]


class FakeBaoLogin:
    error_code = "0"
    error_msg = "success"


class FakeBaoStockModule:
    def login(self) -> FakeBaoLogin:
        return FakeBaoLogin()

    def logout(self) -> None:
        return None

    def query_all_stock(self, day: str | None = None) -> FakeBaoResult:
        if not day:
            return FakeBaoResult(["code", "tradeStatus", "code_name"], [["sh.000001", "1", "SSE Index"]])
        return FakeBaoResult(
            ["code", "tradeStatus", "code_name"],
            [
                ["sh.000001", "1", "SSE Index"],
                ["sh.600000", "1", "SPDB"],
                ["sz.000001", "1", "Ping An Bank"],
            ],
        )

    def query_history_k_data_plus(self, *_: object, **__: object) -> FakeBaoResult:
        return FakeBaoResult(
            ["date", "code", "open", "high", "low", "close", "volume", "amount"],
            [["2024-01-02", "sz.000001", "10", "11", "9", "10.5", "1000", "10000"]],
        )


class DataLayerTests(unittest.TestCase):
    def test_normalize_market_data_frame_outputs_required_schema(self) -> None:
        raw = pd.DataFrame(
            {
                "date": ["20240102"],
                "open_raw": ["10.0"],
                "high_raw": ["11.0"],
                "low_raw": ["9.0"],
                "close_raw": ["10.5"],
                "volume_raw": ["1000"],
                "amount_raw": ["10000"],
            }
        )

        normalized = normalize_market_data_frame(
            raw,
            source="unit",
            symbol="000001",
            column_map={
                "trade_date": "date",
                "open": "open_raw",
                "high": "high_raw",
                "low": "low_raw",
                "close": "close_raw",
                "volume": "volume_raw",
                "amount": "amount_raw",
                "adj_close": "close_raw",
            },
        )

        self.assertEqual(list(normalized.columns), MARKET_DATA_COLUMNS)
        self.assertEqual(normalized.loc[0, "trade_date"], "2024-01-02")
        self.assertEqual(normalized.loc[0, "source"], "unit")

    def test_normalize_stock_universe_outputs_required_schema(self) -> None:
        raw = pd.DataFrame({"code": ["000001", "600000"], "name": ["Ping An Bank", "SPDB"]})

        normalized = normalize_stock_universe_frame(
            raw,
            source="unit",
            column_map={"symbol": "code", "name": "name"},
        )

        self.assertEqual(list(normalized.columns), STOCK_UNIVERSE_COLUMNS)
        self.assertEqual(normalized.loc[0, "exchange"], "SZSE")
        self.assertEqual(normalized.loc[1, "exchange"], "SSE")

    def test_akshare_provider_normalizes_stock_universe(self) -> None:
        provider = AkShareProvider(akshare_module=FakeAkShareModule())

        universe = provider.get_stock_universe()

        self.assertEqual(list(universe.columns), STOCK_UNIVERSE_COLUMNS)
        self.assertEqual(universe.loc[0, "symbol"], "000001")
        self.assertEqual(universe.loc[0, "exchange"], "SZSE")

    def test_baostock_provider_filters_indices_from_stock_universe(self) -> None:
        provider = BaoStockProvider(baostock_module=FakeBaoStockModule())

        universe = provider.get_stock_universe()

        self.assertEqual(list(universe.columns), STOCK_UNIVERSE_COLUMNS)
        self.assertEqual(set(universe["symbol"]), {"sh.600000", "sz.000001"})

    def test_cache_read_write_reuses_same_request(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FakeProvider()
            service = MarketDataService(provider=provider, cache=LocalCsvCache(temp_dir))

            first = service.get_stock_daily("000001", "2024-01-01", "2024-01-03")
            second = service.get_stock_daily("000001", "2024-01-01", "2024-01-03")

            self.assertEqual(len(provider.stock_calls), 1)
            self.assertTrue(first.equals(second))
            self.assertEqual(list(first.columns), MARKET_DATA_COLUMNS)

    def test_incremental_update_fetches_only_missing_tail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FakeProvider()
            service = MarketDataService(provider=provider, cache=LocalCsvCache(temp_dir))

            initial = service.get_stock_daily("000001", "2024-01-01", "2024-01-03")
            expanded = service.get_stock_daily("000001", "2024-01-01", "2024-01-05")

            self.assertEqual(len(initial), 3)
            self.assertEqual(len(expanded), 5)
            self.assertEqual(provider.stock_calls[0], ("000001", "2024-01-01", "2024-01-03", True))
            self.assertEqual(provider.stock_calls[1], ("000001", "2024-01-04", "2024-01-05", True))

    def test_cache_coverage_prevents_refetching_known_non_trading_day(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = TradingDayProvider()
            service = MarketDataService(provider=provider, cache=LocalCsvCache(temp_dir))

            first = service.get_stock_daily("000001", "2024-01-01", "2024-01-03")
            second = service.get_stock_daily("000001", "2024-01-01", "2024-01-03")

            self.assertEqual(len(first), 2)
            self.assertTrue(first.equals(second))
            self.assertEqual(len(provider.stock_calls), 1)

    def test_stock_universe_is_cached(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FakeProvider()
            service = MarketDataService(provider=provider, cache=LocalCsvCache(temp_dir))

            first = service.get_stock_universe()
            second = service.get_stock_universe()

            self.assertEqual(provider.universe_calls, 1)
            self.assertTrue(first.equals(second))
            self.assertEqual(list(first.columns), STOCK_UNIVERSE_COLUMNS)

    def test_service_wraps_provider_failure_with_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = MarketDataService(provider=FailingProvider(), cache=LocalCsvCache(temp_dir))

            with self.assertRaisesRegex(ProviderDataError, "failing failed during stock daily 000001"):
                service.get_stock_daily("000001", "2024-01-01", "2024-01-03")


def _market_frame(symbol: str, dates: list[str], source: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": [symbol] * len(dates),
            "trade_date": dates,
            "open": [10 + index for index, _ in enumerate(dates)],
            "high": [11 + index for index, _ in enumerate(dates)],
            "low": [9 + index for index, _ in enumerate(dates)],
            "close": [10.5 + index for index, _ in enumerate(dates)],
            "volume": [1000 + index for index, _ in enumerate(dates)],
            "amount": [10000 + index for index, _ in enumerate(dates)],
            "adj_close": [10.5 + index for index, _ in enumerate(dates)],
            "source": [source] * len(dates),
        }
    )


if __name__ == "__main__":
    unittest.main()
