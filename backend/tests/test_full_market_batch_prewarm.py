from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.data.cache import LocalCsvCache


def _load_script_module(script_name: str):
    path = Path(__file__).resolve().parents[1] / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(f"test_{Path(script_name).stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load script module: {script_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


batch_prewarm = _load_script_module("prewarm_full_market_batches.py")


class FakeBatchPrewarmService:
    def __init__(self, cache: LocalCsvCache) -> None:
        self.cache = cache
        self.provider = type("Provider", (), {"source": "unit"})()
        self.provider_fetch_calls: list[str] = []

    def get_stock_universe(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "symbol": ["AAA", "BBB", "CCC", "DDD", "EEE"],
                "name": ["A", "B", "C", "D", "E"],
                "exchange": ["SSE"] * 5,
                "listing_status": ["listed"] * 5,
                "listing_date": ["2020-01-01"] * 5,
                "delisting_date": [""] * 5,
                "is_st": [""] * 5,
                "source": ["unit"] * 5,
            }
        )

    def get_stock_daily(self, symbol: str, start_date: str, end_date: str, adjusted: bool = True) -> pd.DataFrame:
        self.provider_fetch_calls.append(symbol)
        return self.cache.get_market_data(
            provider="unit",
            dataset="stock_daily",
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjusted=adjusted,
            fetcher=lambda fetch_start, fetch_end: _prices(symbol, fetch_start, fetch_end),
        )


class FullMarketBatchPrewarmTests(unittest.TestCase):
    def test_build_batch_specs_generates_expected_offsets_and_limits(self) -> None:
        specs = batch_prewarm.build_batch_specs(total_symbols=1200, batch_limit=500)

        self.assertEqual([(item.offset, item.limit) for item in specs], [(0, 500), (500, 500), (1000, 200)])

    def test_single_batch_offset_and_limit_are_supported(self) -> None:
        specs = batch_prewarm.build_batch_specs(total_symbols=2000, batch_limit=500, offset=1500, limit=500)

        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].offset, 1500)
        self.assertEqual(specs[0].limit, 500)

    def test_resume_skips_completed_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            first_service = FakeBatchPrewarmService(LocalCsvCache(temp_dir))
            config = _config(temp_dir, max_batches=1)
            first = batch_prewarm.run_full_market_batch_prewarm(first_service, config)

            second_service = FakeBatchPrewarmService(LocalCsvCache(temp_dir))
            second = batch_prewarm.run_full_market_batch_prewarm(second_service, _config(temp_dir, max_batches=1, resume=True))

        self.assertEqual(first["completed_batches"], 1)
        self.assertEqual(second["batches"][0]["status"], "skipped")
        self.assertEqual(second_service.provider_fetch_calls, [])

    def test_failed_batch_is_recorded_and_stops_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = FakeBatchPrewarmService(LocalCsvCache(temp_dir))

            def failing_runner(service: object, config: object) -> object:
                raise RuntimeError("provider stalled")

            summary = batch_prewarm.run_full_market_batch_prewarm(
                service,
                _config(temp_dir, max_batches=2),
                prewarm_runner=failing_runner,
            )

            output_json = Path(temp_dir, "full_market_prewarm_batches_2024-01-05.json")
            saved = json.loads(output_json.read_text(encoding="utf-8"))

        self.assertEqual(summary["failed_batches"], 1)
        self.assertEqual(summary["completed_batches"], 0)
        self.assertEqual(summary["next_offset"], 0)
        self.assertEqual(len(summary["batches"]), 1)
        self.assertEqual(summary["batches"][0]["status"], "failed")
        self.assertIn("provider stalled", summary["batches"][0]["error_summary"])
        self.assertEqual(saved["failed_batches"], 1)

    def test_summary_files_have_expected_structure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = FakeBatchPrewarmService(LocalCsvCache(temp_dir))
            summary = batch_prewarm.run_full_market_batch_prewarm(service, _config(temp_dir, batch_limit=2))
            output_json = Path(temp_dir, "full_market_prewarm_batches_2024-01-05.json")
            output_csv = Path(temp_dir, "full_market_prewarm_batches_2024-01-05.csv")
            output_log = Path(temp_dir, "full_market_prewarm_batches_2024-01-05.log")
            saved = json.loads(output_json.read_text(encoding="utf-8"))
            csv_exists = output_csv.exists()
            log_exists = output_log.exists()

        required = {
            "provider",
            "start_date",
            "end_date",
            "include_lookback_days",
            "batch_limit",
            "batch_size",
            "resume",
            "total_symbols",
            "planned_batches",
            "completed_batches",
            "failed_batches",
            "full_market_prewarm_complete",
            "total_attempted",
            "total_success",
            "total_failed",
            "last_completed_offset",
            "next_offset",
            "batches",
            "output_paths",
        }
        self.assertTrue(required.issubset(summary))
        self.assertTrue(required.issubset(saved))
        self.assertTrue(csv_exists)
        self.assertTrue(log_exists)
        self.assertEqual(summary["planned_batches"], 3)
        self.assertEqual(summary["completed_batches"], 3)
        self.assertEqual(summary["failed_batches"], 0)
        self.assertTrue(summary["full_market_prewarm_complete"])
        self.assertEqual(summary["next_offset"], 5)


def _config(
    output_dir: str,
    *,
    batch_limit: int = 2,
    max_batches: int | None = None,
    resume: bool = False,
):
    return batch_prewarm.FullMarketBatchPrewarmConfig(
        provider="unit",
        start_date="2024-01-01",
        end_date="2024-01-05",
        include_lookback_days=0,
        cache_dir=output_dir,
        output_dir=output_dir,
        batch_limit=batch_limit,
        batch_size=2,
        sleep_seconds=0.0,
        retry=0,
        resume=resume,
        max_batches=max_batches,
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
