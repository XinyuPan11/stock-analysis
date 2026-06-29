from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.research.factors import (
    FACTOR_OUTPUT_COLUMNS,
    calculate_liquidity_factors,
    calculate_momentum_factors,
    calculate_relative_strength,
    calculate_risk_factors,
    calculate_stock_factors,
    calculate_trend_factors,
)


class FactorTests(unittest.TestCase):
    def test_momentum_20_60_120_day_returns_are_correct(self) -> None:
        prices = [100 + index for index in range(130)]
        frame = _market_frame("000001", prices)

        result = calculate_momentum_factors(frame)

        self.assertAlmostEqual(result.values["momentum_20d"], prices[-1] / prices[-21] - 1)
        self.assertAlmostEqual(result.values["momentum_60d"], prices[-1] / prices[-61] - 1)
        self.assertAlmostEqual(result.values["momentum_120d"], prices[-1] / prices[-121] - 1)

    def test_trend_moving_averages_and_bullish_alignment_are_correct(self) -> None:
        prices = [100 + index for index in range(80)]
        frame = _market_frame("000001", prices)

        result = calculate_trend_factors(frame)

        self.assertAlmostEqual(result.values["ma5"], sum(prices[-5:]) / 5)
        self.assertAlmostEqual(result.values["ma20"], sum(prices[-20:]) / 20)
        self.assertAlmostEqual(result.values["ma60"], sum(prices[-60:]) / 60)
        self.assertTrue(result.values["above_ma20"])
        self.assertTrue(result.values["above_ma60"])
        self.assertTrue(result.values["ma_bullish_alignment"])

    def test_relative_strength_is_stock_return_minus_benchmark_return(self) -> None:
        stock_prices = [100 + index for index in range(130)]
        benchmark_prices = [100 + index * 0.5 for index in range(130)]

        result = calculate_relative_strength(
            _market_frame("000001", stock_prices),
            _market_frame("CSI300", benchmark_prices),
        )

        expected_stock_20 = stock_prices[-1] / stock_prices[-21] - 1
        expected_benchmark_20 = benchmark_prices[-1] / benchmark_prices[-21] - 1
        expected_stock_60 = stock_prices[-1] / stock_prices[-61] - 1
        expected_benchmark_60 = benchmark_prices[-1] / benchmark_prices[-61] - 1
        expected_stock_120 = stock_prices[-1] / stock_prices[-121] - 1
        expected_benchmark_120 = benchmark_prices[-1] / benchmark_prices[-121] - 1

        self.assertAlmostEqual(result.values["rs_20d"], expected_stock_20 - expected_benchmark_20)
        self.assertAlmostEqual(result.values["rs_60d"], expected_stock_60 - expected_benchmark_60)
        self.assertAlmostEqual(result.values["rs_120d"], expected_stock_120 - expected_benchmark_120)

    def test_risk_volatility_and_drawdowns_are_correct(self) -> None:
        prices = [100, 105, 95, 110, 100] + [101 + index for index in range(70)]
        frame = _market_frame("000001", prices)
        price_series = pd.Series(prices, dtype="float64")
        returns = price_series.pct_change().dropna()

        result = calculate_risk_factors(frame)

        self.assertAlmostEqual(result.values["volatility_20d"], returns.tail(20).std())
        self.assertAlmostEqual(result.values["volatility_60d"], returns.tail(60).std())
        self.assertAlmostEqual(result.values["max_drawdown"], (price_series / price_series.cummax() - 1).min())
        self.assertAlmostEqual(
            result.values["max_drawdown_20d"],
            (price_series.tail(20) / price_series.tail(20).cummax() - 1).min(),
        )
        self.assertAlmostEqual(
            result.values["max_drawdown_60d"],
            (price_series.tail(60) / price_series.tail(60).cummax() - 1).min(),
        )

    def test_liquidity_averages_are_correct(self) -> None:
        prices = [100 + index for index in range(80)]
        amounts = [1_000_000 + index for index in range(80)]
        volumes = [10_000 + index for index in range(80)]
        frame = _market_frame("000001", prices, amounts=amounts, volumes=volumes)

        result = calculate_liquidity_factors(frame)

        self.assertAlmostEqual(result.values["avg_amount_20d"], sum(amounts[-20:]) / 20)
        self.assertAlmostEqual(result.values["avg_amount_60d"], sum(amounts[-60:]) / 60)
        self.assertAlmostEqual(result.values["avg_volume_20d"], sum(volumes[-20:]) / 20)
        self.assertAlmostEqual(result.values["avg_volume_60d"], sum(volumes[-60:]) / 60)

    def test_insufficient_120d_history_warns_without_crashing(self) -> None:
        frame = _market_frame("000001", [100 + index for index in range(80)])

        result = calculate_stock_factors(frame)
        row = result.iloc[0]

        self.assertTrue(pd.isna(row["momentum_120d"]))
        self.assertIn("insufficient_120d_history", row["warnings"])

    def test_missing_adj_close_falls_back_to_close_with_warning(self) -> None:
        prices = [100 + index for index in range(130)]
        frame = _market_frame("000001", prices)
        frame["adj_close"] = None

        result = calculate_stock_factors(frame)
        row = result.iloc[0]

        self.assertAlmostEqual(row["momentum_20d"], prices[-1] / prices[-21] - 1)
        self.assertIn("missing_adj_close_fallback_to_close", row["warnings"])

    def test_unsorted_dates_are_sorted_before_factor_calculation(self) -> None:
        prices = [100 + index for index in range(130)]
        sorted_frame = _market_frame("000001", prices)
        shuffled = sorted_frame.sample(frac=1, random_state=7).reset_index(drop=True)

        sorted_result = calculate_stock_factors(sorted_frame).iloc[0]
        shuffled_result = calculate_stock_factors(shuffled).iloc[0]

        self.assertAlmostEqual(shuffled_result["momentum_60d"], sorted_result["momentum_60d"])
        self.assertEqual(shuffled_result["as_of_date"], sorted_result["as_of_date"])


    def test_future_rows_do_not_change_as_of_factor_values(self) -> None:
        historical = _market_frame("000001", [100 + index for index in range(130)])
        as_of_date = str(historical["trade_date"].max())
        future = historical.tail(1).copy()
        future["trade_date"] = (pd.Timestamp(as_of_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        future[["open", "high", "low", "close", "adj_close"]] = 10000.0
        with_future = pd.concat([historical, future], ignore_index=True)

        expected = calculate_stock_factors(historical, as_of_date=as_of_date).iloc[0]
        guarded = calculate_stock_factors(with_future, as_of_date=as_of_date).iloc[0]

        self.assertEqual(guarded["as_of_date"], as_of_date)
        self.assertEqual(guarded["data_points"], len(historical))
        self.assertAlmostEqual(guarded["momentum_20d"], expected["momentum_20d"])
        self.assertAlmostEqual(guarded["ma20"], expected["ma20"])

    def test_empty_input_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "price data is empty"):
            calculate_stock_factors(pd.DataFrame())

    def test_stock_factor_output_schema_is_stable(self) -> None:
        result = calculate_stock_factors(_market_frame("000001", [100 + index for index in range(130)]))

        self.assertEqual(list(result.columns), FACTOR_OUTPUT_COLUMNS)
        self.assertEqual(result.loc[0, "symbol"], "000001")
        self.assertEqual(result.loc[0, "data_points"], 130)

    def test_missing_benchmark_data_warns_and_returns_empty_rs(self) -> None:
        result = calculate_stock_factors(_market_frame("000001", [100 + index for index in range(130)]))
        row = result.iloc[0]

        self.assertTrue(pd.isna(row["rs_20d"]))
        self.assertIn("missing_benchmark_data", row["warnings"])


def _market_frame(
    symbol: str,
    prices: list[float],
    *,
    amounts: list[float] | None = None,
    volumes: list[float] | None = None,
) -> pd.DataFrame:
    count = len(prices)
    dates = pd.date_range("2023-01-01", periods=count, freq="D").strftime("%Y-%m-%d").tolist()
    amounts = amounts or [50_000_000] * count
    volumes = volumes or [1_000_000] * count
    return pd.DataFrame(
        {
            "symbol": [symbol] * count,
            "trade_date": dates,
            "open": prices,
            "high": [price + 1 for price in prices],
            "low": [price - 1 for price in prices],
            "close": prices,
            "volume": volumes,
            "amount": amounts,
            "adj_close": prices,
            "source": ["unit"] * count,
        }
    )


if __name__ == "__main__":
    unittest.main()
