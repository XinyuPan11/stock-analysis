from __future__ import annotations

from math import sqrt

import pandas as pd


def calculate_max_drawdown(values: pd.Series) -> float | None:
    """Return max drawdown from an equity curve as a negative decimal."""

    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if len(numeric) < 2:
        return None
    running_max = numeric.cummax()
    drawdowns = numeric / running_max - 1.0
    return float(drawdowns.min())


def calculate_backtest_metrics(
    equity_curve: pd.DataFrame,
    rebalance_log: pd.DataFrame,
    *,
    transaction_cost: float = 0.0,
) -> tuple[dict[str, float | int | None], list[str]]:
    """Calculate core backtest metrics from daily equity and rebalance logs."""

    warnings: list[str] = []
    if equity_curve is None or equity_curve.empty:
        return _empty_metrics(transaction_cost), ["empty_equity_curve"]

    frame = equity_curve.copy().sort_values("trade_date").reset_index(drop=True)
    required = ["portfolio_value", "benchmark_value", "net_portfolio_value", "net_portfolio_return", "benchmark_return"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Equity curve missing required columns: {missing}")

    for column in required:
        if column != "benchmark_return":
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["benchmark_return"] = pd.to_numeric(frame["benchmark_return"], errors="coerce")

    total_return = _last_return(frame["portfolio_value"])
    net_total_return = _last_return(frame["net_portfolio_value"])
    benchmark_total_return = _last_return(frame["benchmark_value"])
    excess_return = _subtract_optional(net_total_return, benchmark_total_return)
    annualized_return = _annualized_return(frame["net_portfolio_value"], frame["trade_date"])
    if annualized_return is None:
        warnings.append("insufficient_period_for_annualized_return")

    daily_returns = pd.to_numeric(frame["net_portfolio_return"], errors="coerce").dropna()
    volatility = float(daily_returns.std() * sqrt(252)) if len(daily_returns) >= 2 else None
    if volatility is None:
        warnings.append("insufficient_returns_for_volatility")
    sharpe_ratio = _sharpe_ratio(daily_returns)
    if sharpe_ratio is None:
        warnings.append("insufficient_or_zero_volatility_for_sharpe")

    win_rate = _win_rate(frame)
    if win_rate is None:
        warnings.append("insufficient_returns_for_win_rate")

    turnover = _average_turnover(rebalance_log)
    number_of_rebalances = _number_of_rebalances(rebalance_log)
    average_holdings = _average_holdings(rebalance_log)

    metrics = {
        "total_return": total_return,
        "annualized_return": annualized_return,
        "benchmark_total_return": benchmark_total_return,
        "excess_return": excess_return,
        "max_drawdown": calculate_max_drawdown(frame["net_portfolio_value"]),
        "benchmark_max_drawdown": calculate_max_drawdown(frame["benchmark_value"]),
        "sharpe_ratio": sharpe_ratio,
        "volatility": volatility,
        "win_rate": win_rate,
        "turnover": turnover,
        "number_of_rebalances": number_of_rebalances,
        "average_holdings": average_holdings,
        "transaction_cost": float(transaction_cost),
        "net_total_return_after_cost": net_total_return,
    }
    return metrics, warnings


def _empty_metrics(transaction_cost: float) -> dict[str, float | int | None]:
    return {
        "total_return": None,
        "annualized_return": None,
        "benchmark_total_return": None,
        "excess_return": None,
        "max_drawdown": None,
        "benchmark_max_drawdown": None,
        "sharpe_ratio": None,
        "volatility": None,
        "win_rate": None,
        "turnover": None,
        "number_of_rebalances": 0,
        "average_holdings": 0.0,
        "transaction_cost": float(transaction_cost),
        "net_total_return_after_cost": None,
    }


def _last_return(series: pd.Series) -> float | None:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return None
    return float(numeric.iloc[-1] - 1.0)


def _annualized_return(values: pd.Series, dates: pd.Series) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    parsed_dates = pd.to_datetime(dates, errors="coerce").dropna()
    if len(numeric) < 2 or len(parsed_dates) < 2:
        return None
    days = int((parsed_dates.iloc[-1] - parsed_dates.iloc[0]).days)
    if days <= 0:
        return None
    total = float(numeric.iloc[-1] / numeric.iloc[0])
    if total <= 0:
        return None
    return float(total ** (365.0 / days) - 1.0)


def _sharpe_ratio(daily_returns: pd.Series) -> float | None:
    if len(daily_returns) < 2:
        return None
    std = float(daily_returns.std())
    if std == 0:
        return None
    return float(daily_returns.mean() / std * sqrt(252))


def _win_rate(frame: pd.DataFrame) -> float | None:
    returns = frame[["net_portfolio_return", "benchmark_return"]].dropna()
    if returns.empty:
        return None
    return float((returns["net_portfolio_return"] > returns["benchmark_return"]).mean())


def _average_turnover(rebalance_log: pd.DataFrame) -> float:
    if rebalance_log is None or rebalance_log.empty or "turnover" not in rebalance_log.columns:
        return 0.0
    by_date = rebalance_log.drop_duplicates("rebalance_date")
    return float(pd.to_numeric(by_date["turnover"], errors="coerce").fillna(0.0).mean())


def _number_of_rebalances(rebalance_log: pd.DataFrame) -> int:
    if rebalance_log is None or rebalance_log.empty or "rebalance_date" not in rebalance_log.columns:
        return 0
    return int(rebalance_log["rebalance_date"].nunique())


def _average_holdings(rebalance_log: pd.DataFrame) -> float:
    if rebalance_log is None or rebalance_log.empty or "rebalance_date" not in rebalance_log.columns:
        return 0.0
    holdings = rebalance_log.groupby("rebalance_date")["symbol"].nunique()
    return float(holdings.mean()) if not holdings.empty else 0.0


def _subtract_optional(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return float(left) - float(right)

