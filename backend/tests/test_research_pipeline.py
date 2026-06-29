from __future__ import annotations

import sys
import tempfile
import unittest
import json
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.research import pipeline as pipeline_module
from stock_analysis.research.pipeline import (
    CANDIDATE_OUTPUT_COLUMNS,
    ResearchPipelineConfig,
    run_research_pipeline,
)


class FakeResearchService:
    def __init__(
        self,
        universe: pd.DataFrame,
        daily_by_symbol: dict[str, pd.DataFrame],
        benchmark: pd.DataFrame,
        failing_symbols: set[str] | None = None,
    ) -> None:
        self.universe = universe
        self.daily_by_symbol = daily_by_symbol
        self.benchmark = benchmark
        self.failing_symbols = failing_symbols or set()
        self.stock_calls: list[str] = []
        self.index_calls: list[str] = []

    def get_stock_universe(self) -> pd.DataFrame:
        return self.universe.copy()

    def get_stock_daily(self, symbol: str, start_date: str, end_date: str, adjusted: bool = True) -> pd.DataFrame:
        self.stock_calls.append(symbol)
        if symbol in self.failing_symbols:
            raise RuntimeError("simulated upstream failure")
        return self.daily_by_symbol.get(symbol, pd.DataFrame()).copy()

    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        self.index_calls.append(index_code)
        return self.benchmark.copy()


class FakeTimeoutProvider:
    source = "unit"


class FakeTimeoutCache:
    cache_dir = "unit-cache"

    def __init__(self, missing_symbols: set[str]) -> None:
        self.missing_symbols = missing_symbols

    def market_data_path(self, *, provider: str, dataset: str, symbol: str, adjusted: bool) -> Path:
        return Path("unit-cache", provider, dataset, "adjusted" if adjusted else "raw", f"{symbol}.csv")

    def has_market_data_coverage(
        self,
        *,
        provider: str,
        dataset: str,
        symbol: str,
        start_date: str,
        end_date: str,
        adjusted: bool,
    ) -> bool:
        return symbol not in self.missing_symbols

    def get_market_data(self, **kwargs) -> pd.DataFrame:
        raise AssertionError("timeout test should not call cache.get_market_data")


class FakeTimeoutEligibleService(FakeResearchService):
    def __init__(self, missing_symbols: set[str]) -> None:
        super().__init__(
            pd.DataFrame([_stock("AAA", "Alpha"), _stock("SLOW", "Slow")]),
            {"AAA": _prices("AAA", 1.5, amount=100_000_000, volume=10_000_000)},
            _prices("CSI300", 1.0, amount=500_000_000, volume=50_000_000),
        )
        self.provider = FakeTimeoutProvider()
        self.cache = FakeTimeoutCache(missing_symbols)


class FakeConsecutiveTimeoutService(FakeResearchService):
    def __init__(self) -> None:
        super().__init__(
            pd.DataFrame(
                [
                    _stock("AAA", "Alpha"),
                    _stock("SLOW1", "Slow One"),
                    _stock("SLOW2", "Slow Two"),
                    _stock("LATE", "Late"),
                ]
            ),
            {
                "AAA": _prices("AAA", 1.5, amount=100_000_000, volume=10_000_000),
                "LATE": _prices("LATE", 1.4, amount=100_000_000, volume=10_000_000),
            },
            _prices("CSI300", 1.0, amount=500_000_000, volume=50_000_000),
        )
        self.provider = FakeTimeoutProvider()
        self.cache = FakeTimeoutCache({"SLOW1", "SLOW2"})


class ResearchPipelineTests(unittest.TestCase):
    def test_pipeline_connects_universe_filter_factors_scoring_and_ranking(self) -> None:
        service = _service()

        result = run_research_pipeline(service, _config(top_n=2, limit=3))

        self.assertEqual(result.summary["attempted_count"], 3)
        self.assertEqual(result.summary["successful_factor_count"], 2)
        self.assertEqual(result.summary["scored_count"], 2)
        self.assertEqual(list(result.candidates.columns), CANDIDATE_OUTPUT_COLUMNS)
        self.assertEqual(result.candidates["rank"].tolist(), [1, 2])
        self.assertIn("AAA", set(result.candidates["symbol"]))
        self.assertIn("BBB", set(result.candidates["symbol"]))


    def test_pipeline_excludes_future_rows_before_filter_factor_and_scoring(self) -> None:
        baseline = _service()
        baseline_result = run_research_pipeline(baseline, _config(top_n=2, limit=3))
        service = _service()
        future_stock = service.daily_by_symbol["AAA"].tail(1).copy()
        future_stock["trade_date"] = "2024-02-01"
        future_stock[["open", "high", "low", "close", "adj_close"]] = 10000.0
        future_stock["amount"] = 900_000_000
        service.daily_by_symbol["AAA"] = pd.concat(
            [service.daily_by_symbol["AAA"], future_stock],
            ignore_index=True,
        )
        future_benchmark = service.benchmark.tail(1).copy()
        future_benchmark["trade_date"] = "2024-02-01"
        future_benchmark[["open", "high", "low", "close", "adj_close"]] = 10000.0
        service.benchmark = pd.concat([service.benchmark, future_benchmark], ignore_index=True)

        result = run_research_pipeline(service, _config(top_n=2, limit=3))

        expected = baseline_result.factor_frame.set_index("symbol").loc["AAA"]
        guarded = result.factor_frame.set_index("symbol").loc["AAA"]
        self.assertAlmostEqual(guarded["momentum_20d"], expected["momentum_20d"])
        self.assertEqual(result.summary["as_of_date"], "2024-01-31")
        self.assertLessEqual(result.summary["latest_input_date"], "2024-01-31")
        self.assertEqual(result.summary["max_raw_cache_date"], "2024-02-01")
        self.assertEqual(result.summary["future_rows_excluded_count"], 2)
        self.assertTrue(result.summary["leakage_guard_applied"])

    def test_filtered_stock_does_not_enter_factor_calculation(self) -> None:
        service = _service()

        result = run_research_pipeline(service, _config(top_n=5, limit=3))

        self.assertIn("ST1", set(result.filtered_stocks["symbol"]))
        self.assertNotIn("ST1", set(result.factor_frame["symbol"]))
        self.assertNotIn("ST1", set(result.candidates["symbol"]))

    def test_single_stock_fetch_failure_does_not_crash_pipeline(self) -> None:
        service = _service(failing_symbols={"BBB"})

        result = run_research_pipeline(service, _config(top_n=5, limit=3))

        self.assertEqual(result.summary["fetch_error_count"], 1)
        self.assertEqual(result.fetch_errors[0]["symbol"], "BBB")
        self.assertIn("AAA", set(result.candidates["symbol"]))

    def test_pipeline_outputs_top_n_and_files(self) -> None:
        service = _service()
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_research_pipeline(service, _config(top_n=1, limit=3, output_dir=temp_dir))

            self.assertEqual(len(result.candidates), 1)
            self.assertTrue(Path(result.output_paths["candidates_csv"]).exists())
            self.assertTrue(Path(result.output_paths["candidates_json"]).exists())
            self.assertEqual(result.summary["output_path"], result.output_paths["candidates_csv"])

    def test_pipeline_outputs_summary_factors_and_factor_explanations_files(self) -> None:
        service = _service()
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_research_pipeline(service, _config(top_n=2, limit=3, output_dir=temp_dir))

            for key in [
                "summary_json",
                "factors_csv",
                "factors_json",
                "factor_explanations_csv",
                "factor_explanations_json",
            ]:
                self.assertTrue(Path(result.output_paths[key]).exists(), key)
            self.assertFalse(result.factor_frame.empty)
            self.assertFalse(result.factor_explanations.empty)

            summary = json.loads(Path(result.output_paths["summary_json"]).read_text(encoding="utf-8"))
            self.assertEqual(summary["as_of_date"], "2024-01-31")
            self.assertEqual(summary["benchmark"], "CSI300")
            self.assertEqual(summary["successful_factor_count"], len(result.factor_frame))
            self.assertEqual(summary["output_paths"]["factor_explanations_json"], result.output_paths["factor_explanations_json"])

    def test_pipeline_supports_offset_limit_batch_and_retry_error_output(self) -> None:
        service = _service(failing_symbols={"BBB"})
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_research_pipeline(
                service,
                _config(top_n=2, limit=1, offset=1, retry=2, output_dir=temp_dir, error_output_dir=temp_dir),
            )

            self.assertTrue(result.candidates.empty)
            self.assertEqual(service.stock_calls, ["BBB", "BBB", "BBB"])
            self.assertEqual(result.summary["offset"], 1)
            self.assertEqual(result.summary["retry"], 2)
            self.assertEqual(result.fetch_errors[0]["attempts"], "3")
            self.assertTrue(Path(result.output_paths["failed_symbols_csv"]).exists())

    def test_empty_universe_returns_clear_empty_result(self) -> None:
        service = FakeResearchService(
            pd.DataFrame(columns=["symbol", "name", "exchange", "listing_status", "source"]),
            {},
            _prices("CSI300", 1.0),
        )

        result = run_research_pipeline(service, _config())

        self.assertTrue(result.candidates.empty)
        self.assertEqual(result.summary["universe_count"], 0)
        self.assertEqual(result.summary["attempted_count"], 0)

    def test_all_filtered_returns_empty_candidates_without_silent_failure(self) -> None:
        universe = pd.DataFrame(
            [
                _stock("ST1", "ST Sample"),
                _stock("ST2", "*ST Sample"),
            ]
        )
        service = FakeResearchService(
            universe,
            {"ST1": _prices("ST1", 1.0), "ST2": _prices("ST2", 1.0)},
            _prices("CSI300", 1.0),
        )

        result = run_research_pipeline(service, _config(limit=2))

        self.assertTrue(result.candidates.empty)
        self.assertEqual(result.summary["filtered_count"], 2)
        self.assertEqual(result.summary["successful_factor_count"], 0)

    def test_pipeline_writes_progress_log_for_major_stages(self) -> None:
        service = _service()
        with tempfile.TemporaryDirectory() as temp_dir:
            progress_log = Path(temp_dir, "daily_research_progress.log")

            run_research_pipeline(
                service,
                _config(limit=3, output_dir=temp_dir, progress_log_path=progress_log, progress_every=1),
            )

            log_text = progress_log.read_text(encoding="utf-8")

        self.assertIn("stock universe loaded", log_text)
        self.assertIn("cache coverage / loading start", log_text)
        self.assertIn("stock daily start", log_text)
        self.assertIn("stock daily cache state", log_text)
        self.assertIn("stock daily end", log_text)
        self.assertIn("stock daily progress", log_text)
        self.assertIn("filtering end", log_text)
        self.assertIn("factor calculation start", log_text)
        self.assertIn("factor calculation end", log_text)
        self.assertIn("scoring start", log_text)
        self.assertIn("scoring end", log_text)
        self.assertIn("top N candidate generation", log_text)
        self.assertIn("output writing start", log_text)
        self.assertIn("output writing end", log_text)

    def test_symbol_timeout_is_recorded_and_pipeline_continues(self) -> None:
        service = FakeTimeoutEligibleService(missing_symbols={"SLOW"})
        original = pipeline_module._fetch_stock_daily_with_provider_timeout

        def fake_timeout_fetch(*, service, symbol, config, timeout_metadata):
            return None, {
                "symbol": symbol,
                "stage": "provider_fetch",
                "error_type": "symbol_timeout",
                "error": "Symbol fetch timed out after 0.1s during provider_fetch.",
                "attempts": "1",
                "elapsed_seconds": "0.1",
            }

        pipeline_module._fetch_stock_daily_with_provider_timeout = fake_timeout_fetch
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                progress_log = Path(temp_dir, "daily_research_progress.log")
                result = run_research_pipeline(
                    service,
                    _config(
                        top_n=1,
                        limit=2,
                        output_dir=temp_dir,
                        error_output_dir=temp_dir,
                        progress_log_path=progress_log,
                        progress_every=1,
                        symbol_timeout_seconds=0.1,
                    ),
                )
                log_text = progress_log.read_text(encoding="utf-8")
        finally:
            pipeline_module._fetch_stock_daily_with_provider_timeout = original

        self.assertEqual(result.summary["fetch_error_count"], 1)
        self.assertEqual(result.fetch_errors[0]["symbol"], "SLOW")
        self.assertEqual(result.fetch_errors[0]["error_type"], "symbol_timeout")
        self.assertEqual(result.fetch_errors[0]["stage"], "provider_fetch")
        self.assertIn("AAA", set(result.candidates["symbol"]))
        self.assertIn("SYMBOL_TIMEOUT", log_text)

    def test_consecutive_symbol_timeouts_stop_early_and_report_partial_success(self) -> None:
        service = FakeConsecutiveTimeoutService()
        original = pipeline_module._fetch_stock_daily_with_provider_timeout

        def fake_timeout_fetch(*, service, symbol, config, timeout_metadata):
            return None, {
                "symbol": symbol,
                "stage": "provider_fetch",
                "error_type": "symbol_timeout",
                "error": "Symbol fetch timed out after 0.1s during provider_fetch.",
                "attempts": "1",
                "elapsed_seconds": "0.1",
            }

        pipeline_module._fetch_stock_daily_with_provider_timeout = fake_timeout_fetch
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                progress_log = Path(temp_dir, "daily_research_progress.log")
                result = run_research_pipeline(
                    service,
                    _config(
                        top_n=1,
                        limit=4,
                        output_dir=temp_dir,
                        error_output_dir=temp_dir,
                        progress_log_path=progress_log,
                        progress_every=1,
                        symbol_timeout_seconds=0.1,
                        max_consecutive_symbol_timeouts=2,
                        min_successful_factor_rows=1,
                    ),
                )
                log_text = progress_log.read_text(encoding="utf-8")
                failed_symbols_path = Path(result.summary["failed_symbols_path"])
                failed_symbols_exists = failed_symbols_path.exists()
                failed_symbols = pd.read_csv(failed_symbols_path)
        finally:
            pipeline_module._fetch_stock_daily_with_provider_timeout = original

        self.assertEqual(result.summary["status"], "partial_timeout_protected")
        self.assertEqual(result.summary["timeout_count"], 2)
        self.assertEqual(result.summary["skipped_count"], 1)
        self.assertTrue(result.summary["stopped_early"])
        self.assertEqual(result.summary["stop_reason"], "max_consecutive_symbol_timeouts")
        self.assertEqual(result.summary["valid_factor_rows"], 1)
        self.assertTrue(result.summary["partial_success"])
        self.assertTrue(failed_symbols_exists)
        self.assertEqual(failed_symbols["symbol"].tolist(), ["SLOW1", "SLOW2"])
        self.assertNotIn("LATE", service.stock_calls)
        self.assertIn("timeout protection stop", log_text)


def _config(
    top_n: int = 2,
    limit: int = 3,
    offset: int = 0,
    retry: int = 0,
    output_dir: str | None = None,
    error_output_dir: str | None = None,
    progress_log_path: str | Path | None = None,
    progress_every: int = 100,
    symbol_timeout_seconds: float | None = 60.0,
    max_consecutive_symbol_timeouts: int | None = None,
    min_successful_factor_rows: int = 1,
) -> ResearchPipelineConfig:
    return ResearchPipelineConfig(
        start_date="2023-01-01",
        end_date="2024-01-31",
        benchmark="CSI300",
        top_n=top_n,
        limit=limit,
        offset=offset,
        batch_id="unit-batch",
        retry=retry,
        output_dir=output_dir,
        error_output_dir=error_output_dir,
        progress_log_path=progress_log_path,
        progress_every=progress_every,
        symbol_timeout_seconds=symbol_timeout_seconds,
        max_consecutive_symbol_timeouts=max_consecutive_symbol_timeouts,
        min_successful_factor_rows=min_successful_factor_rows,
    )


def _service(failing_symbols: set[str] | None = None) -> FakeResearchService:
    universe = pd.DataFrame(
        [
            _stock("AAA", "Alpha"),
            _stock("BBB", "Beta"),
            _stock("ST1", "ST Risk"),
        ]
    )
    return FakeResearchService(
        universe,
        {
            "AAA": _prices("AAA", 1.5, amount=100_000_000, volume=10_000_000),
            "BBB": _prices("BBB", 1.1, amount=80_000_000, volume=8_000_000),
            "ST1": _prices("ST1", 1.2, amount=60_000_000, volume=6_000_000),
        },
        _prices("CSI300", 1.05, amount=500_000_000, volume=50_000_000),
        failing_symbols=failing_symbols,
    )


def _stock(symbol: str, name: str) -> dict[str, str]:
    return {
        "symbol": symbol,
        "name": name,
        "exchange": "SZSE",
        "listing_status": "listed",
        "listing_date": "2020-01-01",
        "delisting_date": "",
        "is_st": "",
        "source": "unit",
    }


def _prices(
    symbol: str,
    growth_multiplier: float,
    *,
    amount: float = 50_000_000,
    volume: float = 5_000_000,
) -> pd.DataFrame:
    dates = pd.date_range("2023-01-01", periods=280, freq="B").strftime("%Y-%m-%d").tolist()
    prices = [10.0 + growth_multiplier * index / 10 for index in range(len(dates))]
    return pd.DataFrame(
        {
            "symbol": [symbol] * len(dates),
            "trade_date": dates,
            "open": prices,
            "high": [price + 0.5 for price in prices],
            "low": [price - 0.5 for price in prices],
            "close": prices,
            "volume": [volume] * len(dates),
            "amount": [amount] * len(dates),
            "adj_close": prices,
            "source": ["unit"] * len(dates),
        }
    )


if __name__ == "__main__":
    unittest.main()
