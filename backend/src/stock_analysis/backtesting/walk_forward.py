from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Protocol

import pandas as pd

from stock_analysis.backtesting.backtest_report import generate_backtest_report
from stock_analysis.backtesting.metrics import calculate_backtest_metrics
from stock_analysis.data.schemas import MARKET_DATA_COLUMNS
from stock_analysis.research.ashare_filters import FilterConfig, filter_universe
from stock_analysis.research.factors import FACTOR_OUTPUT_COLUMNS, calculate_stock_factors
from stock_analysis.research.pipeline import CANDIDATE_OUTPUT_COLUMNS
from stock_analysis.research.recommendation_engine import rank_candidates


EQUITY_CURVE_COLUMNS = [
    "trade_date",
    "rebalance_date",
    "portfolio_return",
    "net_portfolio_return",
    "benchmark_return",
    "portfolio_value",
    "net_portfolio_value",
    "benchmark_value",
    "excess_return",
    "holdings_count",
]

REBALANCE_LOG_COLUMNS = [
    "rebalance_date",
    "hold_start_date",
    "hold_end_date",
    "symbol",
    "rank",
    "total_score",
    "label",
    "confidence",
    "weight",
    "turnover",
    "transaction_cost",
    "warnings",
]


class BacktestMarketDataServiceLike(Protocol):
    def get_stock_universe(self) -> pd.DataFrame:
        ...

    def get_stock_daily(self, symbol: str, start_date: str, end_date: str, adjusted: bool = True) -> pd.DataFrame:
        ...

    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        ...


@dataclass(frozen=True)
class WalkForwardConfig:
    start_date: str
    end_date: str
    lookback_days: int = 120
    rebalance_frequency: str = "monthly"
    top_n: int = 10
    benchmark: str = "CSI300"
    limit: int = 50
    offset: int = 0
    batch_id: str = ""
    retry: int = 0
    transaction_cost_bps: float = 10.0
    cache_dir: str | Path | None = None
    output_dir: str | Path | None = None
    error_output_dir: str | Path | None = None
    provider: str = ""
    adjusted: bool = True
    filter_config: FilterConfig | None = None


@dataclass(frozen=True)
class WalkForwardBacktestResult:
    summary: dict[str, object]
    equity_curve: pd.DataFrame
    rebalance_log: pd.DataFrame
    skipped_symbols: list[dict[str, str]]
    fetch_errors: list[dict[str, str]]
    output_paths: dict[str, str] = field(default_factory=dict)


def run_walk_forward_backtest(
    service: BacktestMarketDataServiceLike,
    config: WalkForwardConfig,
) -> WalkForwardBacktestResult:
    """Run an interpretable Top N walk-forward backtest without future factor data."""

    _validate_config(config)
    history_start = _history_start(config.start_date, config.lookback_days)
    full_universe = service.get_stock_universe()
    universe = full_universe.iloc[config.offset : config.offset + config.limit].reset_index(drop=True)
    fetch_errors: list[dict[str, str]] = []
    skipped_symbols: list[dict[str, str]] = []

    benchmark = _fetch_benchmark(service, config, history_start, fetch_errors)
    rebalance_dates = _rebalance_dates(benchmark, config.start_date, config.end_date, config.rebalance_frequency)
    if universe.empty or benchmark.empty or not rebalance_dates:
        return _empty_result(config, universe_count=len(full_universe), fetch_errors=fetch_errors, warnings=["empty_universe_or_benchmark"])

    all_daily = _fetch_stock_histories(service, universe, history_start, config, fetch_errors)
    if all_daily.empty:
        return _empty_result(config, universe_count=len(full_universe), fetch_errors=fetch_errors, warnings=["empty_stock_price_history"])

    equity_rows: list[dict[str, object]] = []
    rebalance_rows: list[dict[str, object]] = []
    gross_value = 1.0
    net_value = 1.0
    benchmark_value = 1.0
    previous_weights: dict[str, float] = {}
    total_transaction_cost = 0.0
    warnings: list[str] = []

    for index, rebalance_date in enumerate(rebalance_dates):
        period_end = rebalance_dates[index + 1] if index + 1 < len(rebalance_dates) else config.end_date
        period_dates = _period_dates(benchmark, rebalance_date, period_end)
        if not period_dates:
            warnings.append(f"empty_holding_period:{rebalance_date}")
            continue

        candidates, period_skips, period_warnings = _candidates_on_rebalance(
            universe,
            all_daily,
            benchmark,
            config,
            rebalance_date,
        )
        skipped_symbols.extend(period_skips)
        warnings.extend(period_warnings)
        if candidates.empty:
            warnings.append(f"empty_candidates:{rebalance_date}")
            previous_weights = {}
            continue

        weights = {str(row["symbol"]): 1.0 / len(candidates) for _, row in candidates.iterrows()}
        turnover = _turnover(previous_weights, weights)
        transaction_cost = turnover * float(config.transaction_cost_bps) / 10_000.0
        total_transaction_cost += transaction_cost
        hold_start = period_dates[0]
        hold_end = period_dates[-1]
        rebalance_rows.extend(_rebalance_rows(candidates, rebalance_date, hold_start, hold_end, weights, turnover, transaction_cost))

        period_returns, holding_skips = _portfolio_period_returns(all_daily, weights, rebalance_date, period_dates)
        skipped_symbols.extend(holding_skips)
        benchmark_returns = _benchmark_period_returns(benchmark, rebalance_date, period_dates)
        for row_index, trade_date in enumerate(period_dates):
            portfolio_return = float(period_returns.get(trade_date, 0.0))
            net_return = portfolio_return - (transaction_cost if row_index == 0 else 0.0)
            benchmark_return = float(benchmark_returns.get(trade_date, 0.0))
            gross_value *= 1.0 + portfolio_return
            net_value *= 1.0 + net_return
            benchmark_value *= 1.0 + benchmark_return
            equity_rows.append(
                {
                    "trade_date": trade_date,
                    "rebalance_date": rebalance_date,
                    "portfolio_return": portfolio_return,
                    "net_portfolio_return": net_return,
                    "benchmark_return": benchmark_return,
                    "portfolio_value": gross_value,
                    "net_portfolio_value": net_value,
                    "benchmark_value": benchmark_value,
                    "excess_return": net_value / benchmark_value - 1.0 if benchmark_value else None,
                    "holdings_count": len(weights),
                }
            )
        previous_weights = weights

    equity_curve = pd.DataFrame(equity_rows, columns=EQUITY_CURVE_COLUMNS)
    rebalance_log = pd.DataFrame(rebalance_rows, columns=REBALANCE_LOG_COLUMNS)
    metrics, metric_warnings = calculate_backtest_metrics(
        equity_curve,
        rebalance_log,
        transaction_cost=total_transaction_cost,
    )
    warnings.extend(metric_warnings)
    summary = _summary(config, len(full_universe), metrics, fetch_errors, skipped_symbols, warnings)
    output_paths = _write_outputs(summary, equity_curve, rebalance_log, config) if config.output_dir else {}
    if config.error_output_dir and fetch_errors:
        output_paths["failed_symbols_csv"] = _write_fetch_errors(fetch_errors, config.error_output_dir, config)
        summary["output_paths"] = output_paths
        if output_paths.get("summary_json"):
            Path(output_paths["summary_json"]).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_paths:
        summary["output_paths"] = output_paths
    return WalkForwardBacktestResult(
        summary=summary,
        equity_curve=equity_curve,
        rebalance_log=rebalance_log,
        skipped_symbols=skipped_symbols,
        fetch_errors=fetch_errors,
        output_paths=output_paths,
    )


def _candidates_on_rebalance(
    universe: pd.DataFrame,
    all_daily: pd.DataFrame,
    benchmark: pd.DataFrame,
    config: WalkForwardConfig,
    rebalance_date: str,
) -> tuple[pd.DataFrame, list[dict[str, str]], list[str]]:
    history = all_daily[all_daily["trade_date"] <= rebalance_date].copy()
    benchmark_history = benchmark[benchmark["trade_date"] <= rebalance_date].copy()
    filter_config = config.filter_config or FilterConfig(as_of_date=rebalance_date)
    filter_result = filter_universe(
        universe,
        history,
        config=filter_config,
        benchmark_dates=benchmark_history["trade_date"].tolist() if not benchmark_history.empty else None,
    )
    warnings = [f"{rebalance_date}:{warning}" for warning in filter_result.warnings]
    if filter_result.passed_universe.empty:
        return pd.DataFrame(columns=CANDIDATE_OUTPUT_COLUMNS), [], warnings

    passed_symbols = set(filter_result.passed_universe["symbol"].astype(str))
    rows: list[pd.DataFrame] = []
    skipped: list[dict[str, str]] = []
    for symbol, stock_history in history.groupby("symbol", sort=True):
        if str(symbol) not in passed_symbols:
            continue
        try:
            rows.append(calculate_stock_factors(stock_history, benchmark_history, as_of_date=rebalance_date))
        except Exception as exc:
            skipped.append({"symbol": str(symbol), "date": rebalance_date, "reason": f"factor_calculation_failed:{exc}"})
    if not rows:
        return pd.DataFrame(columns=CANDIDATE_OUTPUT_COLUMNS), skipped, warnings

    factors = pd.concat(rows, ignore_index=True).loc[:, FACTOR_OUTPUT_COLUMNS]
    ranked = rank_candidates(factors, top_n=config.top_n)
    return ranked.loc[:, [column for column in CANDIDATE_OUTPUT_COLUMNS if column in ranked.columns]], skipped, warnings


def _fetch_stock_histories(
    service: BacktestMarketDataServiceLike,
    universe: pd.DataFrame,
    history_start: str,
    config: WalkForwardConfig,
    fetch_errors: list[dict[str, str]],
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for symbol in universe["symbol"].astype(str).tolist():
        frame, error = _fetch_stock_daily_with_retry(service, symbol, history_start, config)
        if error:
            fetch_errors.append(error)
        elif frame is not None:
            frames.append(_safe_market_frame(frame))
    if not frames:
        return pd.DataFrame(columns=MARKET_DATA_COLUMNS)
    return pd.concat(frames, ignore_index=True).sort_values(["symbol", "trade_date"]).reset_index(drop=True)


def _fetch_benchmark(
    service: BacktestMarketDataServiceLike,
    config: WalkForwardConfig,
    history_start: str,
    fetch_errors: list[dict[str, str]],
) -> pd.DataFrame:
    try:
        return _safe_market_frame(service.get_index_daily(config.benchmark, history_start, config.end_date))
    except Exception as exc:
        fetch_errors.append({"symbol": config.benchmark, "stage": "benchmark_daily", "error_type": _classify_error(str(exc)), "error": str(exc), "attempts": "1"})
        return pd.DataFrame(columns=MARKET_DATA_COLUMNS)


def _fetch_stock_daily_with_retry(
    service: BacktestMarketDataServiceLike,
    symbol: str,
    history_start: str,
    config: WalkForwardConfig,
) -> tuple[pd.DataFrame | None, dict[str, str] | None]:
    attempts = max(1, int(config.retry) + 1)
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            frame = service.get_stock_daily(symbol, history_start, config.end_date, adjusted=config.adjusted)
            if frame is None or frame.empty:
                raise ValueError("empty price history")
            return frame, None
        except Exception as exc:
            last_error = exc
    error_text = str(last_error) if last_error else "unknown error"
    return None, {
        "symbol": symbol,
        "stage": "stock_daily",
        "error_type": _classify_error(error_text),
        "error": error_text,
        "attempts": str(attempts),
    }


def _rebalance_dates(benchmark: pd.DataFrame, start_date: str, end_date: str, frequency: str) -> list[str]:
    if benchmark.empty:
        return []
    frame = benchmark.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce")
    frame = frame[(frame["trade_date"] >= pd.Timestamp(start_date)) & (frame["trade_date"] <= pd.Timestamp(end_date))]
    if frame.empty:
        return []
    if frequency == "weekly":
        grouped = frame.groupby(frame["trade_date"].dt.to_period("W-MON"))
    elif frequency == "monthly":
        grouped = frame.groupby(frame["trade_date"].dt.to_period("M"))
    else:
        raise ValueError("rebalance_frequency must be monthly or weekly.")
    return [group["trade_date"].min().strftime("%Y-%m-%d") for _, group in grouped]


def _period_dates(benchmark: pd.DataFrame, rebalance_date: str, period_end: str) -> list[str]:
    dates = pd.to_datetime(benchmark["trade_date"], errors="coerce")
    mask = (dates > pd.Timestamp(rebalance_date)) & (dates <= pd.Timestamp(period_end))
    return dates.loc[mask].dt.strftime("%Y-%m-%d").tolist()


def _portfolio_period_returns(
    all_daily: pd.DataFrame,
    weights: dict[str, float],
    rebalance_date: str,
    period_dates: list[str],
) -> tuple[dict[str, float], list[dict[str, str]]]:
    returns_by_symbol: list[pd.Series] = []
    skipped: list[dict[str, str]] = []
    for symbol, weight in weights.items():
        history = all_daily[all_daily["symbol"].astype(str) == symbol].copy()
        prices = _price_series_on_dates(history, rebalance_date, period_dates)
        if prices.empty or len(prices) < 2:
            skipped.append({"symbol": symbol, "date": rebalance_date, "reason": "missing_period_price_data"})
            continue
        returns_by_symbol.append(prices.pct_change().reindex(period_dates).fillna(0.0) * weight)
    if not returns_by_symbol:
        return {date: 0.0 for date in period_dates}, skipped
    combined = pd.concat(returns_by_symbol, axis=1).sum(axis=1)
    return {date: float(combined.get(date, 0.0)) for date in period_dates}, skipped


def _benchmark_period_returns(benchmark: pd.DataFrame, rebalance_date: str, period_dates: list[str]) -> dict[str, float]:
    prices = _price_series_on_dates(benchmark, rebalance_date, period_dates)
    if prices.empty or len(prices) < 2:
        return {date: 0.0 for date in period_dates}
    returns = prices.pct_change().reindex(period_dates).fillna(0.0)
    return {date: float(returns.get(date, 0.0)) for date in period_dates}


def _price_series_on_dates(history: pd.DataFrame, rebalance_date: str, period_dates: list[str]) -> pd.Series:
    if history.empty:
        return pd.Series(dtype=float)
    frame = history.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce")
    frame["price"] = pd.to_numeric(frame["adj_close"], errors="coerce").where(
        pd.to_numeric(frame["adj_close"], errors="coerce").notna(),
        pd.to_numeric(frame["close"], errors="coerce"),
    )
    frame = frame.dropna(subset=["trade_date", "price"]).sort_values("trade_date")
    baseline = frame[frame["trade_date"] <= pd.Timestamp(rebalance_date)].tail(1)
    if baseline.empty:
        return pd.Series(dtype=float)
    period = frame[frame["trade_date"].isin(pd.to_datetime(period_dates))].copy()
    baseline_date = pd.Timestamp(rebalance_date).strftime("%Y-%m-%d")
    series = pd.concat(
        [
            pd.Series({baseline_date: float(baseline["price"].iloc[0])}),
            pd.Series(period["price"].astype(float).values, index=period["trade_date"].dt.strftime("%Y-%m-%d")),
        ]
    )
    target_index = [baseline_date, *period_dates]
    return series[~series.index.duplicated(keep="last")].reindex(target_index).ffill().dropna()


def _rebalance_rows(
    candidates: pd.DataFrame,
    rebalance_date: str,
    hold_start: str,
    hold_end: str,
    weights: dict[str, float],
    turnover: float,
    transaction_cost: float,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for _, row in candidates.iterrows():
        symbol = str(row["symbol"])
        rows.append(
            {
                "rebalance_date": rebalance_date,
                "hold_start_date": hold_start,
                "hold_end_date": hold_end,
                "symbol": symbol,
                "rank": int(row.get("rank", 0)),
                "total_score": float(row.get("total_score", 0.0)),
                "label": str(row.get("label", "")),
                "confidence": float(row.get("confidence", 0.0)),
                "weight": float(weights[symbol]),
                "turnover": float(turnover),
                "transaction_cost": float(transaction_cost),
                "warnings": str(row.get("warnings", "")),
            }
        )
    return rows


def _turnover(previous_weights: dict[str, float], next_weights: dict[str, float]) -> float:
    symbols = set(previous_weights) | set(next_weights)
    return float(sum(abs(next_weights.get(symbol, 0.0) - previous_weights.get(symbol, 0.0)) for symbol in symbols))


def _write_outputs(
    summary: dict[str, object],
    equity_curve: pd.DataFrame,
    rebalance_log: pd.DataFrame,
    config: WalkForwardConfig,
) -> dict[str, str]:
    output_dir = Path(config.output_dir or ".")
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_date = pd.Timestamp(config.end_date).strftime("%Y-%m-%d")
    summary_path = output_dir / f"backtest_summary_{safe_date}.json"
    equity_path = output_dir / f"backtest_equity_curve_{safe_date}.csv"
    rebalance_path = output_dir / f"backtest_rebalance_log_{safe_date}.csv"
    equity_curve.to_csv(equity_path, index=False, encoding="utf-8-sig")
    rebalance_log.to_csv(rebalance_path, index=False, encoding="utf-8-sig")
    report_paths = generate_backtest_report(summary, equity_curve, rebalance_log, output_dir=output_dir, as_of_date=config.end_date)
    output_paths = {
        "summary_json": str(summary_path.resolve()),
        "equity_curve_csv": str(equity_path.resolve()),
        "rebalance_log_csv": str(rebalance_path.resolve()),
        "report_markdown": report_paths["markdown"],
        "report_html": report_paths["html"],
    }
    summary["output_paths"] = output_paths
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_paths


def _write_fetch_errors(fetch_errors: list[dict[str, str]], output_dir: str | Path, config: WalkForwardConfig) -> str:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    safe_date = pd.Timestamp(config.end_date).strftime("%Y-%m-%d")
    errors_path = path / f"failed_symbols_{safe_date}.csv"
    rows = [_error_output_row(error, config) for error in fetch_errors]
    pd.DataFrame(rows).to_csv(errors_path, index=False, encoding="utf-8-sig")
    return str(errors_path.resolve())


def _error_output_row(error: dict[str, str], config: WalkForwardConfig) -> dict[str, object]:
    error_type = error.get("error_type") or _classify_error(error.get("error", ""))
    return {
        "symbol": error.get("symbol", ""),
        "name": error.get("name", ""),
        "error_type": error_type,
        "error_message": error.get("error", ""),
        "provider": config.provider,
        "start_date": pd.Timestamp(config.start_date).strftime("%Y-%m-%d"),
        "end_date": pd.Timestamp(config.end_date).strftime("%Y-%m-%d"),
        "attempt_count": error.get("attempts", "1"),
        "last_attempt_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "can_retry": error_type in {"connection", "timeout", "empty_market_data", "non_numeric_market_data", "provider_error"},
    }


def _summary(
    config: WalkForwardConfig,
    universe_count: int,
    metrics: dict[str, float | int | None],
    fetch_errors: list[dict[str, str]],
    skipped_symbols: list[dict[str, str]],
    warnings: list[str],
) -> dict[str, object]:
    return {
        "as_of_date": pd.Timestamp(config.end_date).strftime("%Y-%m-%d"),
        "updated_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "provider": config.provider,
        "benchmark": config.benchmark,
        "start_date": pd.Timestamp(config.start_date).strftime("%Y-%m-%d"),
        "end_date": pd.Timestamp(config.end_date).strftime("%Y-%m-%d"),
        "offset": int(config.offset),
        "limit": int(config.limit),
        "batch_id": config.batch_id,
        "retry": int(config.retry),
        "universe_count": int(universe_count),
        "fetch_error_count": int(len(fetch_errors)),
        "skipped_symbol_count": int(len(skipped_symbols)),
        "fetch_errors": fetch_errors,
        "skipped_symbols": skipped_symbols,
        "warnings": sorted(set(warnings)),
        "parameters": {
            "lookback_days": int(config.lookback_days),
            "rebalance_frequency": config.rebalance_frequency,
            "top_n": int(config.top_n),
            "benchmark": config.benchmark,
            "limit": int(config.limit),
            "offset": int(config.offset),
            "batch_id": config.batch_id,
            "retry": int(config.retry),
            "transaction_cost_bps": float(config.transaction_cost_bps),
        },
        "metrics": metrics,
        "output_paths": {},
    }


def _empty_result(
    config: WalkForwardConfig,
    *,
    universe_count: int,
    fetch_errors: list[dict[str, str]],
    warnings: list[str],
) -> WalkForwardBacktestResult:
    equity_curve = pd.DataFrame(columns=EQUITY_CURVE_COLUMNS)
    rebalance_log = pd.DataFrame(columns=REBALANCE_LOG_COLUMNS)
    metrics, metric_warnings = calculate_backtest_metrics(equity_curve, rebalance_log, transaction_cost=0.0)
    summary = _summary(config, universe_count, metrics, fetch_errors, [], [*warnings, *metric_warnings])
    output_paths = _write_outputs(summary, equity_curve, rebalance_log, config) if config.output_dir else {}
    if config.error_output_dir and fetch_errors:
        output_paths["failed_symbols_csv"] = _write_fetch_errors(fetch_errors, config.error_output_dir, config)
        summary["output_paths"] = output_paths
        if output_paths.get("summary_json"):
            Path(output_paths["summary_json"]).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_paths:
        summary["output_paths"] = output_paths
    return WalkForwardBacktestResult(
        summary=summary,
        equity_curve=equity_curve,
        rebalance_log=rebalance_log,
        skipped_symbols=[],
        fetch_errors=fetch_errors,
        output_paths=output_paths,
    )


def _safe_market_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=MARKET_DATA_COLUMNS)
    missing = [column for column in MARKET_DATA_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Market data missing required columns: {missing}")
    result = frame.loc[:, MARKET_DATA_COLUMNS].copy()
    result["trade_date"] = pd.to_datetime(result["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    if result["trade_date"].isna().any():
        raise ValueError("Market data contains invalid trade_date values.")
    return result.drop_duplicates(["symbol", "trade_date"]).sort_values(["symbol", "trade_date"]).reset_index(drop=True)


def _history_start(start_date: str, lookback_days: int) -> str:
    parsed = pd.Timestamp(start_date)
    return (parsed - pd.Timedelta(days=lookback_days)).strftime("%Y-%m-%d")


def _validate_config(config: WalkForwardConfig) -> None:
    start = pd.to_datetime(config.start_date, errors="coerce")
    end = pd.to_datetime(config.end_date, errors="coerce")
    if pd.isna(start) or pd.isna(end):
        raise ValueError("start_date and end_date must be valid dates.")
    if start >= end:
        raise ValueError("start_date must be before end_date.")
    if config.lookback_days <= 0:
        raise ValueError("lookback_days must be positive.")
    if config.top_n <= 0:
        raise ValueError("top_n must be positive.")
    if config.limit <= 0:
        raise ValueError("limit must be positive.")
    if config.offset < 0:
        raise ValueError("offset cannot be negative.")
    if config.retry < 0:
        raise ValueError("retry cannot be negative.")
    if config.rebalance_frequency not in {"monthly", "weekly"}:
        raise ValueError("rebalance_frequency must be monthly or weekly.")
    if config.transaction_cost_bps < 0:
        raise ValueError("transaction_cost_bps cannot be negative.")


def _classify_error(error: str) -> str:
    text = str(error).lower()
    if "missing_required_columns" in text or "missing provider column" in text:
        return "missing_required_columns"
    if "invalid_price_data" in text or "ohlc" in text:
        return "invalid_price_data"
    if "numeric market data" in text or "non-numeric" in text:
        return "non_numeric_market_data"
    if "empty" in text or "no data" in text:
        return "empty_market_data"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "connection" in text or "reset" in text or "proxy" in text:
        return "connection"
    return "provider_error"
