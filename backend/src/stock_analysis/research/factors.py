from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import pandas as pd

from stock_analysis.data.point_in_time import slice_daily_as_of
from stock_analysis.data.schemas import MARKET_DATA_COLUMNS, NUMERIC_MARKET_COLUMNS


FACTOR_OUTPUT_COLUMNS = [
    "symbol",
    "as_of_date",
    "momentum_20d",
    "momentum_60d",
    "momentum_120d",
    "ma5",
    "ma20",
    "ma60",
    "above_ma20",
    "above_ma60",
    "ma_bullish_alignment",
    "rs_20d",
    "rs_60d",
    "rs_120d",
    "volatility_20d",
    "volatility_60d",
    "max_drawdown",
    "max_drawdown_20d",
    "max_drawdown_60d",
    "avg_amount_20d",
    "avg_amount_60d",
    "avg_volume_20d",
    "avg_volume_60d",
    "data_points",
    "source",
    "warnings",
]


@dataclass(frozen=True)
class FactorValues:
    values: dict[str, object]
    warnings: tuple[str, ...] = ()


def calculate_momentum_factors(price_df: pd.DataFrame) -> FactorValues:
    prices, warnings = _prepared_price_series(price_df)
    values = {
        "momentum_20d": _period_return(prices, 20),
        "momentum_60d": _period_return(prices, 60),
        "momentum_120d": _period_return(prices, 120),
    }
    return FactorValues(values=values, warnings=tuple(sorted(set(warnings + _history_warnings(prices, [20, 60, 120])))))


def calculate_trend_factors(price_df: pd.DataFrame) -> FactorValues:
    prices, warnings = _prepared_price_series(price_df)
    ma5 = _moving_average(prices, 5)
    ma20 = _moving_average(prices, 20)
    ma60 = _moving_average(prices, 60)
    latest = _latest_value(prices)
    values = {
        "ma5": ma5,
        "ma20": ma20,
        "ma60": ma60,
        "above_ma20": _is_above(latest, ma20),
        "above_ma60": _is_above(latest, ma60),
        "ma_bullish_alignment": _is_bullish_alignment(ma5, ma20, ma60),
    }
    return FactorValues(values=values, warnings=tuple(sorted(set(warnings + _window_warnings(prices, [5, 20, 60])))))


def calculate_relative_strength(stock_df: pd.DataFrame, benchmark_df: pd.DataFrame | None) -> FactorValues:
    stock_momentum = calculate_momentum_factors(stock_df)
    if benchmark_df is None or benchmark_df.empty:
        return FactorValues(
            values={"rs_20d": None, "rs_60d": None, "rs_120d": None},
            warnings=tuple(sorted(set((*stock_momentum.warnings, "missing_benchmark_data")))),
        )

    benchmark_momentum = calculate_momentum_factors(benchmark_df)
    values = {
        "rs_20d": _subtract_optional(stock_momentum.values["momentum_20d"], benchmark_momentum.values["momentum_20d"]),
        "rs_60d": _subtract_optional(stock_momentum.values["momentum_60d"], benchmark_momentum.values["momentum_60d"]),
        "rs_120d": _subtract_optional(stock_momentum.values["momentum_120d"], benchmark_momentum.values["momentum_120d"]),
    }
    warnings = tuple(
        sorted(
            set(
                stock_momentum.warnings
                + tuple(f"benchmark_{warning}" for warning in benchmark_momentum.warnings)
            )
        )
    )
    return FactorValues(values=values, warnings=warnings)


def calculate_risk_factors(price_df: pd.DataFrame, *, annualize_volatility: bool = False) -> FactorValues:
    prices, warnings = _prepared_price_series(price_df)
    daily_returns = prices.pct_change().dropna()
    volatility_scale = sqrt(252) if annualize_volatility else 1.0
    values = {
        "volatility_20d": _return_volatility(daily_returns, 20, volatility_scale),
        "volatility_60d": _return_volatility(daily_returns, 60, volatility_scale),
        "max_drawdown": _max_drawdown(prices),
        "max_drawdown_20d": _max_drawdown(prices.tail(20)),
        "max_drawdown_60d": _max_drawdown(prices.tail(60)),
    }
    if annualize_volatility:
        warnings = (*warnings, "volatility_annualized_sqrt_252")
    return FactorValues(values=values, warnings=tuple(sorted(set(warnings + _history_warnings(prices, [20, 60])))))


def calculate_liquidity_factors(price_df: pd.DataFrame) -> FactorValues:
    frame = _prepare_price_frame(price_df)
    values = {
        "avg_amount_20d": _tail_mean(frame["amount"], 20),
        "avg_amount_60d": _tail_mean(frame["amount"], 60),
        "avg_volume_20d": _tail_mean(frame["volume"], 20),
        "avg_volume_60d": _tail_mean(frame["volume"], 60),
    }
    return FactorValues(values=values, warnings=tuple(sorted(set(_window_warnings(frame["close"], [20, 60])))))


def calculate_stock_factors(
    stock_df: pd.DataFrame,
    benchmark_df: pd.DataFrame | None = None,
    *,
    as_of_date: str | None = None,
) -> pd.DataFrame:
    """Calculate Phase 1 factor rows from normalized daily market data only."""

    if as_of_date is not None:
        stock_guard = slice_daily_as_of(stock_df, as_of_date)
        frame = _prepare_price_frame(stock_guard.frame)
        if frame.empty:
            raise ValueError(f"No stock price data on or before as_of_date: {as_of_date}")
        as_of_date = stock_guard.as_of_date
    else:
        frame = _prepare_price_frame(stock_df)

    benchmark_prepared = _prepare_optional_benchmark(benchmark_df, as_of_date=as_of_date)
    rows = [
        _calculate_one_stock_factors(group, benchmark_prepared, as_of_date=as_of_date)
        for _, group in frame.groupby("symbol", sort=True)
    ]
    return pd.DataFrame(rows, columns=FACTOR_OUTPUT_COLUMNS)


def _calculate_one_stock_factors(
    stock_df: pd.DataFrame,
    benchmark_df: pd.DataFrame | None,
    *,
    as_of_date: str | None,
) -> dict[str, object]:
    frame = _prepare_price_frame(stock_df)
    effective_as_of = as_of_date or str(frame["trade_date"].max())
    frame = frame[frame["trade_date"] <= effective_as_of].copy()
    if frame.empty:
        raise ValueError(f"No stock price data on or before as_of_date: {effective_as_of}")
    benchmark_as_of = benchmark_df[benchmark_df["trade_date"] <= effective_as_of].copy() if benchmark_df is not None else None

    calculations = [
        calculate_momentum_factors(frame),
        calculate_trend_factors(frame),
        calculate_relative_strength(frame, benchmark_as_of),
        calculate_risk_factors(frame),
        calculate_liquidity_factors(frame),
    ]
    warnings = tuple(sorted({warning for calculation in calculations for warning in calculation.warnings}))
    values: dict[str, object] = {}
    for calculation in calculations:
        values.update(calculation.values)

    symbol = str(frame["symbol"].iloc[0])
    row = {
        "symbol": symbol,
        "as_of_date": effective_as_of,
        **values,
        "data_points": int(len(frame)),
        "source": ";".join(sorted(frame["source"].astype(str).unique())),
        "warnings": ";".join(warnings),
    }
    return {column: row.get(column) for column in FACTOR_OUTPUT_COLUMNS}


def _prepare_optional_benchmark(
    benchmark_df: pd.DataFrame | None,
    *,
    as_of_date: str | None = None,
) -> pd.DataFrame | None:
    if benchmark_df is None or benchmark_df.empty:
        return None
    guarded = slice_daily_as_of(benchmark_df, as_of_date).frame if as_of_date is not None else benchmark_df
    return _prepare_price_frame(guarded)


def _prepare_price_frame(price_df: pd.DataFrame) -> pd.DataFrame:
    if price_df is None or price_df.empty:
        raise ValueError("price data is empty.")

    missing_required = [column for column in MARKET_DATA_COLUMNS if column not in price_df.columns and column != "adj_close"]
    if missing_required:
        raise ValueError(f"Price data missing required columns: {missing_required}")

    frame = price_df.copy()
    if "adj_close" not in frame.columns:
        frame["adj_close"] = pd.NA
    frame = frame.loc[:, MARKET_DATA_COLUMNS].copy()
    parsed_dates = pd.to_datetime(frame["trade_date"].astype(str), errors="coerce")
    if parsed_dates.isna().any():
        raise ValueError("trade_date contains invalid date values.")
    frame["trade_date"] = parsed_dates.dt.strftime("%Y-%m-%d")
    for column in NUMERIC_MARKET_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame[["symbol", "trade_date", "source"]].isna().any().any():
        raise ValueError("symbol, trade_date, and source are required.")
    return frame.drop_duplicates(["symbol", "trade_date"]).sort_values(["symbol", "trade_date"]).reset_index(drop=True)


def _prepared_price_series(price_df: pd.DataFrame) -> tuple[pd.Series, tuple[str, ...]]:
    frame = _prepare_price_frame(price_df)
    warnings: list[str] = []
    if frame["adj_close"].isna().any():
        warnings.append("missing_adj_close_fallback_to_close")
    prices = frame["adj_close"].where(frame["adj_close"].notna(), frame["close"])
    prices = pd.to_numeric(prices, errors="coerce").dropna().reset_index(drop=True)
    if prices.empty:
        raise ValueError("price data has no usable close or adj_close values.")
    return prices, tuple(warnings)


def _period_return(prices: pd.Series, lookback: int) -> float | None:
    if len(prices) <= lookback:
        return None
    start = float(prices.iloc[-lookback - 1])
    end = float(prices.iloc[-1])
    if start == 0:
        return None
    return end / start - 1


def _moving_average(prices: pd.Series, window: int) -> float | None:
    if len(prices) < window:
        return None
    return float(prices.tail(window).mean())


def _latest_value(prices: pd.Series) -> float | None:
    if prices.empty:
        return None
    return float(prices.iloc[-1])


def _return_volatility(daily_returns: pd.Series, window: int, scale: float) -> float | None:
    if len(daily_returns) < window:
        return None
    return float(daily_returns.tail(window).std() * scale)


def _max_drawdown(prices: pd.Series) -> float | None:
    if len(prices) < 2:
        return None
    running_max = prices.cummax()
    drawdowns = prices / running_max - 1
    return float(drawdowns.min())


def _tail_mean(series: pd.Series, window: int) -> float | None:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if len(numeric) < window:
        return None
    return float(numeric.tail(window).mean())


def _history_warnings(series: pd.Series, lookbacks: list[int]) -> tuple[str, ...]:
    available = int(len(series.dropna()))
    warnings = [f"insufficient_{lookback}d_history" for lookback in lookbacks if available <= lookback]
    return tuple(warnings)


def _window_warnings(series: pd.Series, windows: list[int]) -> tuple[str, ...]:
    available = int(len(series.dropna()))
    warnings = [f"insufficient_{window}d_history" for window in windows if available < window]
    return tuple(warnings)


def _subtract_optional(left: object, right: object) -> float | None:
    if left is None or right is None:
        return None
    return float(left) - float(right)


def _is_above(left: float | None, right: float | None) -> bool | None:
    if left is None or right is None:
        return None
    return left > right


def _is_bullish_alignment(ma5: float | None, ma20: float | None, ma60: float | None) -> bool | None:
    if ma5 is None or ma20 is None or ma60 is None:
        return None
    return ma5 > ma20 > ma60
