from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd


PRICE_COLUMN_PREFERENCE = ["adj_close", "close"]


def calculate_future_return_label(
    symbol: str,
    price_history: pd.DataFrame,
    *,
    as_of_date: str,
    horizon_days: int,
    benchmark_history: pd.DataFrame | None = None,
) -> dict[str, object]:
    """Calculate a post-as-of future return label without using it for ranking.

    No future leakage: this label is for after-the-fact validation only. It must
    never be used to generate the as-of candidate list, factors, or scores.
    """

    base = _base_label(symbol, as_of_date, horizon_days)
    if horizon_days <= 0:
        return {**base, "data_quality": "invalid_horizon"}

    prices = _prepare_price_history(price_history)
    if prices.empty:
        return {**base, "data_quality": "missing_price"}

    entry = prices[prices["trade_date"] == as_of_date]
    if entry.empty:
        return {**base, "data_quality": "missing_price"}

    future_window = prices[prices["trade_date"] > as_of_date].head(horizon_days)
    if len(future_window) < horizon_days:
        entry_price = _safe_float(entry.iloc[-1]["validation_price"])
        return {**base, "entry_price": entry_price, "data_quality": "insufficient_future_window"}

    entry_price = _safe_float(entry.iloc[-1]["validation_price"])
    exit_price = _safe_float(future_window.iloc[-1]["validation_price"])
    if entry_price is None or entry_price <= 0 or exit_price is None:
        return {**base, "data_quality": "missing_price"}

    future_return = (exit_price / entry_price) - 1.0
    benchmark_return, benchmark_quality = _benchmark_return(benchmark_history, as_of_date=as_of_date, horizon_days=horizon_days)
    future_excess_return = None if benchmark_return is None else future_return - benchmark_return
    drawdown = _max_drawdown(entry_price, future_window["validation_price"])

    return {
        **base,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "future_return": future_return,
        "benchmark_return": benchmark_return,
        "future_excess_return": future_excess_return,
        "outperformed_benchmark": None if future_excess_return is None else future_excess_return > 0,
        "benchmark_data_quality": benchmark_quality,
        "future_top_quantile": False,
        "max_drawdown_during_holding": drawdown,
        "data_quality": "ok",
    }


def calculate_future_return_labels(
    symbols: Iterable[str],
    price_histories: dict[str, pd.DataFrame],
    *,
    as_of_date: str,
    horizon_days: int,
    benchmark_history: pd.DataFrame | None = None,
    top_quantile: float = 0.2,
) -> list[dict[str, object]]:
    labels = [
        calculate_future_return_label(
            str(symbol),
            price_histories.get(str(symbol), pd.DataFrame()),
            as_of_date=as_of_date,
            horizon_days=horizon_days,
            benchmark_history=benchmark_history,
        )
        for symbol in symbols
    ]
    _mark_top_quantile(labels, top_quantile=top_quantile)
    return labels


def load_cached_price_history(
    cache_dir: str | Path,
    *,
    provider: str,
    symbol: str,
    dataset: str = "stock_daily",
    adjusted: bool = True,
) -> pd.DataFrame:
    """Read one cached price CSV. This function never fetches provider data."""

    path = cached_price_path(cache_dir, provider=provider, symbol=symbol, dataset=dataset, adjusted=adjusted)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype={"symbol": str, "trade_date": str, "source": str})


def load_cached_benchmark_history(
    cache_dir: str | Path,
    *,
    provider: str,
    benchmark: str,
) -> tuple[pd.DataFrame, str, str]:
    """Read a cached benchmark using known aliases. This never fetches data."""

    aliases = benchmark_aliases(benchmark)
    for symbol in aliases:
        frame = load_cached_price_history(cache_dir, provider=provider, symbol=symbol, dataset="index_daily", adjusted=False)
        if not frame.empty:
            return frame, symbol, "ok"
    return pd.DataFrame(), aliases[0], "benchmark_missing"


def benchmark_aliases(benchmark: str) -> list[str]:
    value = str(benchmark or "").strip()
    upper = value.upper()
    aliases = {
        "CSI300": ["sh.000300", "CSI300", "000300.SH"],
        "沪深300": ["sh.000300", "CSI300", "000300.SH"],
        "000300": ["sh.000300", "CSI300", "000300.SH"],
        "SH.000300": ["sh.000300", "CSI300", "000300.SH"],
        "000300.SH": ["sh.000300", "CSI300", "000300.SH"],
    }.get(upper, [value])
    result: list[str] = []
    for alias in aliases:
        if alias and alias not in result:
            result.append(alias)
    return result or [value]


def cached_price_path(
    cache_dir: str | Path,
    *,
    provider: str,
    symbol: str,
    dataset: str = "stock_daily",
    adjusted: bool = True,
) -> Path:
    safe_symbol = str(symbol).replace("/", "_").replace("\\", "_").replace(":", "_")
    adjust_key = "adjusted" if adjusted else "raw"
    return Path(cache_dir) / provider / dataset / adjust_key / f"{safe_symbol}.csv"


def _base_label(symbol: str, as_of_date: str, horizon_days: int) -> dict[str, object]:
    return {
        "symbol": symbol,
        "as_of_date": as_of_date,
        "horizon_days": horizon_days,
        "entry_price": None,
        "exit_price": None,
        "future_return": None,
        "benchmark_return": None,
        "future_excess_return": None,
        "outperformed_benchmark": None,
        "benchmark_data_quality": "benchmark_missing",
        "future_top_quantile": False,
        "max_drawdown_during_holding": None,
        "data_quality": "missing_price",
    }


def _prepare_price_history(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None or frame.empty or "trade_date" not in frame.columns:
        return pd.DataFrame()
    price_column = next((column for column in PRICE_COLUMN_PREFERENCE if column in frame.columns), None)
    if price_column is None:
        return pd.DataFrame()
    result = frame.loc[:, ["trade_date", price_column]].copy()
    result["trade_date"] = pd.to_datetime(result["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    result["validation_price"] = pd.to_numeric(result[price_column], errors="coerce")
    result = result.dropna(subset=["trade_date", "validation_price"])
    result = result[result["validation_price"] > 0]
    return result.sort_values("trade_date").drop_duplicates("trade_date").reset_index(drop=True)


def _benchmark_return(benchmark_history: pd.DataFrame | None, *, as_of_date: str, horizon_days: int) -> tuple[float | None, str]:
    if benchmark_history is None or benchmark_history.empty:
        return None, "benchmark_missing"
    label = calculate_future_return_label(
        "benchmark",
        benchmark_history,
        as_of_date=as_of_date,
        horizon_days=horizon_days,
        benchmark_history=None,
    )
    value = label.get("future_return")
    if value is None:
        return None, f"benchmark_{label.get('data_quality', 'missing_price')}"
    return float(value), "ok"


def _max_drawdown(entry_price: float, prices: pd.Series) -> float | None:
    numeric = pd.to_numeric(prices, errors="coerce").dropna()
    if numeric.empty or entry_price <= 0:
        return None
    cumulative = pd.concat([pd.Series([entry_price]), numeric], ignore_index=True)
    running_max = cumulative.cummax()
    drawdowns = cumulative / running_max - 1.0
    return float(drawdowns.min())


def _mark_top_quantile(labels: list[dict[str, object]], *, top_quantile: float) -> None:
    valid_returns = [float(item["future_return"]) for item in labels if item.get("data_quality") == "ok" and item.get("future_return") is not None]
    if not valid_returns:
        return
    threshold = pd.Series(valid_returns).quantile(max(min(1.0 - top_quantile, 1.0), 0.0))
    for item in labels:
        value = item.get("future_return")
        item["future_top_quantile"] = bool(item.get("data_quality") == "ok" and value is not None and float(value) >= threshold)


def _safe_float(value: object) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
