from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.data.cache import LocalCsvCache
from stock_analysis.data import cache_prewarm
from stock_analysis.data.cache_prewarm import CachePrewarmConfig, load_symbols_file, run_cache_prewarm


class FakePrewarmService:
    def __init__(self, cache: LocalCsvCache, failing_symbols: set[str] | None = None) -> None:
        self.cache = cache
        self.provider = type("Provider", (), {"source": "unit"})()
        self.failing_symbols = failing_symbols or set()
        self.provider_fetch_calls: list[str] = []
        self.service_calls: list[str] = []

    def get_stock_universe(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "symbol": ["AAA", "BBB", "CCC", "DDD"],
                "name": ["A", "B", "C", "D"],
                "exchange": ["SSE"] * 4,
                "listing_status": ["listed"] * 4,
                "listing_date": ["2020-01-01"] * 4,
                "delisting_date": [""] * 4,
                "is_st": [""] * 4,
                "source": ["unit"] * 4,
            }
        )

    def get_stock_daily(self, symbol: str, start_date: str, end_date: str, adjusted: bool = True) -> pd.DataFrame:
        self.service_calls.append(symbol)
        return self.cache.get_market_data(
            provider="unit",
            dataset="stock_daily",
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjusted=adjusted,
            fetcher=lambda fetch_start, fetch_end: self._fetch(symbol, fetch_start, fetch_end),
        )

    def _fetch(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        self.provider_fetch_calls.append(symbol)
        if symbol in self.failing_symbols:
            raise RuntimeError("Numeric market data columns contain missing or non-numeric values.")
        return _prices(symbol, start_date, end_date)


class CachePrewarmTests(unittest.TestCase):
    def test_cache_hit_does_not_repeat_provider_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = LocalCsvCache(temp_dir)
            service = FakePrewarmService(cache)
            config = _config(cache_dir=temp_dir, output_dir=temp_dir, limit=1)

            first = run_cache_prewarm(service, config)
            second = run_cache_prewarm(service, config)

            self.assertEqual(first.summary["success_count"], 1)
            self.assertEqual(second.summary["cache_hit_count"], 1)
            self.assertEqual(service.provider_fetch_calls.count("AAA"), 1)

    def test_single_failure_continues_and_writes_summary_and_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = FakePrewarmService(LocalCsvCache(temp_dir), failing_symbols={"BBB"})

            result = run_cache_prewarm(service, _config(cache_dir=temp_dir, output_dir=temp_dir, limit=3, retry=1))

            self.assertEqual(result.summary["attempted_count"], 3)
            self.assertEqual(result.summary["error_count"], 1)
            self.assertEqual(result.errors.iloc[0]["symbol"], "BBB")
            self.assertEqual(result.errors.iloc[0]["attempt_count"], 2)
            self.assertEqual(result.errors.iloc[0]["error_type"], "non_numeric_market_data")
            self.assertTrue(Path(result.output_paths["summary_json"]).exists())
            self.assertTrue(Path(result.output_paths["errors_csv"]).exists())

    def test_offset_and_limit_select_expected_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = FakePrewarmService(LocalCsvCache(temp_dir))

            run_cache_prewarm(service, _config(cache_dir=temp_dir, output_dir=temp_dir, offset=1, limit=2))

            self.assertEqual(service.provider_fetch_calls, ["BBB", "CCC"])

    def test_resume_skips_cached_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = LocalCsvCache(temp_dir)
            service = FakePrewarmService(cache)
            run_cache_prewarm(service, _config(cache_dir=temp_dir, output_dir=temp_dir, limit=1))

            result = run_cache_prewarm(service, _config(cache_dir=temp_dir, output_dir=temp_dir, limit=1, resume=True))

            self.assertEqual(result.summary["cache_hit_count"], 1)
            self.assertEqual(result.summary["skipped_count"], 1)
            self.assertEqual(service.service_calls.count("AAA"), 1)

    def test_failed_symbols_file_can_be_used_for_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = FakePrewarmService(LocalCsvCache(temp_dir), failing_symbols={"BBB"})
            failed = run_cache_prewarm(service, _config(cache_dir=temp_dir, output_dir=temp_dir, offset=1, limit=1))
            symbols = load_symbols_file(failed.output_paths["errors_csv"])
            retry_service = FakePrewarmService(LocalCsvCache(temp_dir))

            rerun = run_cache_prewarm(
                retry_service,
                _config(cache_dir=temp_dir, output_dir=temp_dir, symbols=symbols, limit=1),
            )

            self.assertEqual(symbols, ("BBB",))
            self.assertEqual(rerun.summary["success_count"], 1)
            self.assertEqual(rerun.summary["error_count"], 0)

    def test_prewarm_summary_has_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_cache_prewarm(FakePrewarmService(LocalCsvCache(temp_dir)), _config(cache_dir=temp_dir, output_dir=temp_dir))
            required = {
                "provider",
                "requested_start_date",
                "effective_start_date",
                "start_date",
                "end_date",
                "include_lookback_days",
                "limit",
                "offset",
                "batch_size",
                "total_symbols",
                "attempted_count",
                "cache_hit_count",
                "success_count",
                "error_count",
                "skipped_count",
                "elapsed_seconds",
                "cache_dir",
                "errors_path",
                "error_type_counts",
            }
            self.assertTrue(required.issubset(result.summary))

    def test_include_lookback_days_extends_effective_start_date(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_cache_prewarm(
                FakePrewarmService(LocalCsvCache(temp_dir)),
                _config(cache_dir=temp_dir, output_dir=temp_dir, include_lookback_days=120),
            )

            self.assertEqual(result.summary["requested_start_date"], "2024-01-01")
            self.assertEqual(result.summary["effective_start_date"], "2023-09-03")
            self.assertEqual(result.summary["include_lookback_days"], 120)

    def test_error_type_counts_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_cache_prewarm(
                FakePrewarmService(LocalCsvCache(temp_dir), failing_symbols={"AAA", "BBB"}),
                _config(cache_dir=temp_dir, output_dir=temp_dir, limit=2),
            )

            self.assertEqual(result.summary["error_type_counts"], {"non_numeric_market_data": 2})

    def test_symbol_timeout_records_failed_symbol_and_stops_after_cap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = FakePrewarmService(LocalCsvCache(temp_dir))
            failed_path = Path(temp_dir) / "failed_symbols.csv"
            progress_path = Path(temp_dir) / "progress.jsonl"
            original = cache_prewarm._fetch_with_symbol_timeout

            def fake_timeout(item: dict[str, str], config: CachePrewarmConfig) -> tuple[bool, dict[str, object]]:
                return False, cache_prewarm._error_row(
                    item,
                    config,
                    "symbol_timeout",
                    "Symbol fetch timed out after 1 seconds during provider_fetch.",
                    1,
                )

            cache_prewarm._fetch_with_symbol_timeout = fake_timeout
            try:
                result = run_cache_prewarm(
                    service,
                    _config(
                        cache_dir=temp_dir,
                        output_dir=temp_dir,
                        limit=3,
                        symbol_timeout_seconds=1,
                        max_consecutive_symbol_timeouts=2,
                        failed_symbols_output=failed_path,
                        progress_log=progress_path,
                    ),
                )
            finally:
                cache_prewarm._fetch_with_symbol_timeout = original

            self.assertEqual(result.summary["timeout_count"], 2)
            self.assertTrue(result.summary["stopped_early"])
            self.assertEqual(result.summary["stop_reason"], "max_consecutive_symbol_timeouts")
            self.assertEqual(result.output_paths["errors_csv"], str(failed_path.resolve()))
            failed = pd.read_csv(failed_path)
            self.assertEqual(failed["error_type"].tolist(), ["symbol_timeout", "symbol_timeout"])
            self.assertEqual(failed["stage"].tolist(), ["provider_fetch", "provider_fetch"])
            self.assertTrue(progress_path.exists())

    def test_resume_progress_skips_already_covered_symbol(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = LocalCsvCache(temp_dir)
            service = FakePrewarmService(cache)
            run_cache_prewarm(service, _config(cache_dir=temp_dir, output_dir=temp_dir, limit=1))
            progress_path = Path(temp_dir) / "progress.jsonl"

            result = run_cache_prewarm(
                service,
                _config(cache_dir=temp_dir, output_dir=temp_dir, limit=1, resume=True, progress_log=progress_path),
            )

            self.assertEqual(result.summary["skipped_count"], 1)
            lines = progress_path.read_text(encoding="utf-8").splitlines()
            self.assertTrue(any('"status": "cache_hit_skipped"' in line for line in lines))



def _config(
    *,
    cache_dir: str,
    output_dir: str,
    limit: int = 2,
    offset: int = 0,
    retry: int = 0,
    resume: bool = False,
    symbols: tuple[str, ...] = (),
    include_lookback_days: int = 0,
    symbol_timeout_seconds: float | None = None,
    max_consecutive_symbol_timeouts: int | None = None,
    failed_symbols_output: str | Path | None = None,
    progress_log: str | Path | None = None,
) -> CachePrewarmConfig:
    return CachePrewarmConfig(
        provider="unit",
        start_date="2024-01-01",
        end_date="2024-01-05",
        requested_start_date="2024-01-01",
        include_lookback_days=include_lookback_days,
        limit=limit,
        offset=offset,
        batch_size=2,
        cache_dir=cache_dir,
        output_dir=output_dir,
        resume=resume,
        retry=retry,
        symbols=symbols,
        symbol_timeout_seconds=symbol_timeout_seconds,
        max_consecutive_symbol_timeouts=max_consecutive_symbol_timeouts,
        failed_symbols_output=failed_symbols_output,
        progress_log=progress_log,
    )


def _prices(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    dates = pd.date_range(start_date, end_date, freq="B").strftime("%Y-%m-%d").tolist()
    prices = [10.0 + index for index in range(len(dates))]
    return pd.DataFrame(
        {
            "symbol": [symbol] * len(dates),
            "trade_date": dates,
            "open": prices,
            "high": [price + 0.5 for price in prices],
            "low": [price - 0.5 for price in prices],
            "close": prices,
            "volume": [1000] * len(dates),
            "amount": [100_000] * len(dates),
            "adj_close": prices,
            "source": ["unit"] * len(dates),
        }
    )


if __name__ == "__main__":
    unittest.main()
