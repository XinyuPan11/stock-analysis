from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

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
            self.assertTrue(Path(result.output_paths["csv"]).exists())
            self.assertTrue(Path(result.output_paths["json"]).exists())
            self.assertEqual(result.summary["output_path"], result.output_paths["csv"])

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


def _config(top_n: int = 2, limit: int = 3, output_dir: str | None = None) -> ResearchPipelineConfig:
    return ResearchPipelineConfig(
        start_date="2023-01-01",
        end_date="2024-01-31",
        benchmark="CSI300",
        top_n=top_n,
        limit=limit,
        output_dir=output_dir,
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
