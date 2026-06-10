from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.backtesting.backtest_report import generate_backtest_report
from stock_analysis.backtesting.metrics import calculate_backtest_metrics, calculate_max_drawdown
from stock_analysis.backtesting.walk_forward import WalkForwardConfig, run_walk_forward_backtest
from stock_analysis.research.ashare_filters import FilterConfig


class FakeBacktestService:
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
        self.stock_calls: list[tuple[str, str, str]] = []

    def get_stock_universe(self) -> pd.DataFrame:
        return self.universe.copy()

    def get_stock_daily(self, symbol: str, start_date: str, end_date: str, adjusted: bool = True) -> pd.DataFrame:
        self.stock_calls.append((symbol, start_date, end_date))
        if symbol in self.failing_symbols:
            raise RuntimeError("simulated price failure")
        frame = self.daily_by_symbol.get(symbol, pd.DataFrame()).copy()
        if frame.empty:
            return frame
        return frame[(frame["trade_date"] >= start_date) & (frame["trade_date"] <= end_date)].copy()

    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        return self.benchmark[(self.benchmark["trade_date"] >= start_date) & (self.benchmark["trade_date"] <= end_date)].copy()


class BacktestingTests(unittest.TestCase):
    def test_walk_forward_does_not_use_future_data_for_selection(self) -> None:
        service = _future_leak_service()

        result = run_walk_forward_backtest(service, _config(top_n=1, limit=2))

        first_date = result.rebalance_log["rebalance_date"].min()
        first_symbols = result.rebalance_log[result.rebalance_log["rebalance_date"] == first_date]["symbol"].tolist()
        self.assertEqual(first_symbols, ["PRE"])

    def test_top_n_selection_and_equal_weight_returns(self) -> None:
        service = _service()

        result = run_walk_forward_backtest(service, _config(top_n=2, limit=3))

        first_date = result.rebalance_log["rebalance_date"].min()
        first_weights = result.rebalance_log[result.rebalance_log["rebalance_date"] == first_date]["weight"].round(6).tolist()
        self.assertEqual(first_weights, [0.5, 0.5])
        self.assertLessEqual(result.rebalance_log.groupby("rebalance_date")["symbol"].nunique().max(), 2)
        self.assertFalse(result.equity_curve.empty)

    def test_benchmark_comparison_and_metrics_are_calculated(self) -> None:
        service = _service()

        result = run_walk_forward_backtest(service, _config(top_n=2, limit=3))
        metrics = result.summary["metrics"]

        self.assertIn("benchmark_total_return", metrics)
        self.assertIn("excess_return", metrics)
        self.assertIsNotNone(metrics["net_total_return_after_cost"])
        self.assertGreater(metrics["number_of_rebalances"], 0)

    def test_max_drawdown_calculation(self) -> None:
        self.assertAlmostEqual(calculate_max_drawdown(pd.Series([1.0, 1.2, 0.9, 1.1])), -0.25)

    def test_sharpe_volatility_and_win_rate(self) -> None:
        equity = pd.DataFrame(
            {
                "trade_date": ["2024-01-02", "2024-01-03", "2024-01-04"],
                "portfolio_value": [1.01, 1.02, 1.03],
                "net_portfolio_value": [1.01, 1.02, 1.03],
                "benchmark_value": [1.0, 1.005, 1.006],
                "net_portfolio_return": [0.01, 0.0099, 0.0098],
                "benchmark_return": [0.0, 0.005, 0.001],
            }
        )
        log = pd.DataFrame({"rebalance_date": ["2024-01-02"], "symbol": ["AAA"], "turnover": [1.0]})

        metrics, warnings = calculate_backtest_metrics(equity, log, transaction_cost=0.001)

        self.assertGreater(metrics["sharpe_ratio"], 0)
        self.assertGreater(metrics["volatility"], 0)
        self.assertEqual(metrics["win_rate"], 1.0)
        self.assertNotIn("empty_equity_curve", warnings)

    def test_transaction_cost_lowers_net_return(self) -> None:
        no_cost = run_walk_forward_backtest(_service(), _config(top_n=2, transaction_cost_bps=0))
        with_cost = run_walk_forward_backtest(_service(), _config(top_n=2, transaction_cost_bps=50))

        self.assertGreater(
            no_cost.summary["metrics"]["net_total_return_after_cost"],
            with_cost.summary["metrics"]["net_total_return_after_cost"],
        )

    def test_missing_symbol_data_is_skipped_and_recorded(self) -> None:
        service = _service(failing_symbols={"BBB"})

        result = run_walk_forward_backtest(service, _config(top_n=2, limit=3))

        self.assertEqual(result.summary["fetch_error_count"], 1)
        self.assertEqual(result.fetch_errors[0]["symbol"], "BBB")

    def test_backtest_supports_offset_retry_and_failed_symbols_output(self) -> None:
        service = _service(failing_symbols={"BBB"})
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _config(top_n=2, limit=1, offset=1, retry=2)
            config = replace(config, output_dir=temp_dir, error_output_dir=temp_dir)

            result = run_walk_forward_backtest(service, config)

            self.assertEqual([call[0] for call in service.stock_calls], ["BBB", "BBB", "BBB"])
            self.assertEqual(result.summary["offset"], 1)
            self.assertEqual(result.summary["retry"], 2)
            self.assertEqual(result.fetch_errors[0]["attempts"], "3")
            self.assertTrue(Path(result.output_paths["failed_symbols_csv"]).exists())

    def test_empty_candidates_returns_warning_without_crashing(self) -> None:
        universe = pd.DataFrame([_stock("ST1", "ST Sample")])
        service = FakeBacktestService(universe, {"ST1": _prices("ST1", 1.0)}, _prices("CSI300", 1.0))

        result = run_walk_forward_backtest(service, _config(top_n=1, limit=1))

        self.assertTrue(result.equity_curve.empty)
        self.assertIn("empty_equity_curve", result.summary["warnings"])

    def test_backtest_report_generates_markdown_and_html(self) -> None:
        service = _service()
        result = run_walk_forward_backtest(service, _config(top_n=2, limit=3))
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = generate_backtest_report(result.summary, result.equity_curve, result.rebalance_log, output_dir=temp_dir)

            markdown = Path(paths["markdown"]).read_text(encoding="utf-8")
            html = Path(paths["html"]).read_text(encoding="utf-8")
            self.assertIn("一、回测设置", markdown)
            self.assertIn("该回测仅用于个人研究和模型验证，不构成投资建议。", markdown)
            self.assertIn("<html", html)

    def test_backtest_writes_summary_curve_log_and_report_outputs(self) -> None:
        service = _service()
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _config(top_n=2, limit=3)
            config = replace(config, output_dir=temp_dir)

            result = run_walk_forward_backtest(service, config)

            for key in ["summary_json", "equity_curve_csv", "rebalance_log_csv", "report_markdown", "report_html"]:
                self.assertTrue(Path(result.output_paths[key]).exists(), key)
            summary_text = Path(result.output_paths["summary_json"]).read_text(encoding="utf-8")
            self.assertIn("output_paths", summary_text)
            self.assertIn("backtest_equity_curve_2023-09-29.csv", summary_text)


def _config(
    *,
    top_n: int = 2,
    limit: int = 3,
    offset: int = 0,
    retry: int = 0,
    transaction_cost_bps: float = 10.0,
) -> WalkForwardConfig:
    return WalkForwardConfig(
        start_date="2023-07-03",
        end_date="2023-09-29",
        lookback_days=80,
        rebalance_frequency="monthly",
        top_n=top_n,
        benchmark="CSI300",
        limit=limit,
        offset=offset,
        batch_id="unit-batch",
        retry=retry,
        transaction_cost_bps=transaction_cost_bps,
        provider="unit",
        filter_config=FilterConfig(
            min_listing_days=0,
            history_window_days=45,
            min_valid_trading_days=15,
            liquidity_window_days=10,
            min_avg_amount_20d=1.0,
        ),
    )


def _service(failing_symbols: set[str] | None = None) -> FakeBacktestService:
    universe = pd.DataFrame([_stock("AAA", "Alpha"), _stock("BBB", "Beta"), _stock("CCC", "Gamma")])
    return FakeBacktestService(
        universe,
        {
            "AAA": _prices("AAA", 1.45, amount=100_000_000, volume=10_000_000),
            "BBB": _prices("BBB", 1.25, amount=90_000_000, volume=9_000_000),
            "CCC": _prices("CCC", 0.95, amount=80_000_000, volume=8_000_000),
        },
        _prices("CSI300", 1.05, amount=500_000_000, volume=50_000_000),
        failing_symbols=failing_symbols,
    )


def _future_leak_service() -> FakeBacktestService:
    dates = pd.date_range("2023-01-02", "2023-09-29", freq="B").strftime("%Y-%m-%d").tolist()
    split = dates.index("2023-07-03")
    pre_prices = [10 + i * 0.06 for i in range(split + 1)] + [20 - i * 0.02 for i in range(len(dates) - split - 1)]
    future_prices = [10 - i * 0.01 for i in range(split + 1)] + [9 + i * 0.12 for i in range(len(dates) - split - 1)]
    universe = pd.DataFrame([_stock("PRE", "Past Winner"), _stock("FUT", "Future Winner")])
    return FakeBacktestService(
        universe,
        {
            "PRE": _frame_from_prices("PRE", dates, pre_prices),
            "FUT": _frame_from_prices("FUT", dates, future_prices),
        },
        _prices("CSI300", 1.02),
    )


def _stock(symbol: str, name: str) -> dict[str, str]:
    return {
        "symbol": symbol,
        "name": name,
        "exchange": "SSE",
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
    dates = pd.date_range("2023-01-02", "2023-09-29", freq="B").strftime("%Y-%m-%d").tolist()
    prices = [10.0 + growth_multiplier * index / 25 for index in range(len(dates))]
    return _frame_from_prices(symbol, dates, prices, amount=amount, volume=volume)


def _frame_from_prices(
    symbol: str,
    dates: list[str],
    prices: list[float],
    *,
    amount: float = 50_000_000,
    volume: float = 5_000_000,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": [symbol] * len(dates),
            "trade_date": dates,
            "open": prices,
            "high": [price + 0.2 for price in prices],
            "low": [max(0.01, price - 0.2) for price in prices],
            "close": prices,
            "volume": [volume] * len(dates),
            "amount": [amount] * len(dates),
            "adj_close": prices,
            "source": ["unit"] * len(dates),
        }
    )


if __name__ == "__main__":
    unittest.main()
