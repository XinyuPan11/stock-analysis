from __future__ import annotations

from typing import Iterable

import pandas as pd

from stock_analysis.portfolio.portfolio_rules import PortfolioRule


def evaluate_portfolios(
    holdings_by_portfolio: dict[str, list[dict[str, object]]],
    future_labels: pd.DataFrame | Iterable[dict[str, object]],
    *,
    rules: Iterable[PortfolioRule],
    as_of_date: str,
    horizon_days: int,
    transaction_cost_bps: float,
) -> list[dict[str, object]]:
    rule_map = {rule.portfolio_id: rule for rule in rules}
    labels = _to_frame(future_labels)
    return [
        evaluate_portfolio_performance(
            portfolio_id,
            holdings,
            labels,
            rule=rule_map.get(portfolio_id),
            as_of_date=as_of_date,
            horizon_days=horizon_days,
            transaction_cost_bps=transaction_cost_bps,
        )
        for portfolio_id, holdings in holdings_by_portfolio.items()
    ]


def evaluate_portfolio_performance(
    portfolio_id: str,
    holdings: list[dict[str, object]],
    future_labels: pd.DataFrame | Iterable[dict[str, object]],
    *,
    rule: PortfolioRule | None = None,
    as_of_date: str,
    horizon_days: int,
    transaction_cost_bps: float = 10.0,
) -> dict[str, object]:
    labels = _to_frame(future_labels)
    base = {
        "portfolio_id": portfolio_id,
        "as_of_date": as_of_date,
        "horizon_days": horizon_days,
        "holding_count": len(holdings),
        "valid_future_count": 0,
        "average_future_return": None,
        "average_excess_return": None,
        "median_future_return": None,
        "win_rate": None,
        "outperform_rate": None,
        "average_max_drawdown": None,
        "best_cases": [],
        "worst_cases": [],
        "turnover_placeholder": "Turnover requires multiple rebalance dates and will be fully evaluated in later runs.",
        "transaction_cost_bps": transaction_cost_bps,
        "net_average_return": None,
        "observation_only": bool(rule.observation_only) if rule else False,
        "notes": [],
    }
    if not holdings:
        return {**base, "notes": ["empty_portfolio"]}
    if labels.empty or "symbol" not in labels.columns:
        return {**base, "notes": ["missing_future_labels"]}

    holding_frame = pd.DataFrame(holdings)
    rows = holding_frame.merge(labels, on="symbol", how="left", suffixes=("", "_future"))
    if "data_quality" not in rows.columns:
        return {**base, "notes": ["missing_data_quality"]}
    valid = rows[rows["data_quality"] == "ok"].copy()
    for column in ["future_return", "future_excess_return", "max_drawdown_during_holding"]:
        if column in valid.columns:
            valid[column] = pd.to_numeric(valid[column], errors="coerce")
    valid = valid.dropna(subset=["future_return"])
    if valid.empty:
        counts = rows["data_quality"].fillna("missing_future_label").value_counts().to_dict()
        return {**base, "data_quality_counts": counts, "notes": ["no_valid_future_labels"]}

    cost = transaction_cost_bps / 10000.0
    returns = valid["future_return"]
    excess = valid["future_excess_return"] if "future_excess_return" in valid.columns else pd.Series(dtype=float)
    drawdown = valid["max_drawdown_during_holding"] if "max_drawdown_during_holding" in valid.columns else pd.Series(dtype=float)
    return {
        **base,
        "valid_future_count": int(len(valid)),
        "average_future_return": float(returns.mean()),
        "average_excess_return": _mean_or_none(excess),
        "median_future_return": float(returns.median()),
        "win_rate": float((returns > 0).mean()),
        "outperform_rate": _outperform_rate(valid),
        "average_max_drawdown": _mean_or_none(drawdown),
        "best_cases": _case_rows(valid.sort_values("future_return", ascending=False).head(5)),
        "worst_cases": _case_rows(valid.sort_values("future_return", ascending=True).head(5)),
        "net_average_return": float(returns.mean() - cost),
        "data_quality_counts": rows["data_quality"].fillna("missing_future_label").value_counts().to_dict(),
        "notes": ["risk_observation_only"] if rule and rule.observation_only else [],
    }


def _outperform_rate(frame: pd.DataFrame) -> float | None:
    if "outperformed_benchmark" not in frame.columns:
        return None
    valid = frame["outperformed_benchmark"].dropna()
    if valid.empty:
        return None
    return float(valid.astype(bool).mean())


def _mean_or_none(series: pd.Series) -> float | None:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return None
    return float(numeric.mean())


def _case_rows(frame: pd.DataFrame) -> list[dict[str, object]]:
    columns = [
        "symbol",
        "name",
        "future_return",
        "future_excess_return",
        "max_drawdown_during_holding",
        "entry_rank",
        "entry_score",
        "primary_type",
        "secondary_tags",
        "data_quality",
    ]
    existing = [column for column in columns if column in frame.columns]
    return [_clean_record(row) for row in frame.loc[:, existing].to_dict(orient="records")]


def _clean_record(row: dict[str, object]) -> dict[str, object]:
    cleaned: dict[str, object] = {}
    for key, value in row.items():
        if isinstance(value, float) and pd.isna(value):
            cleaned[key] = None
        else:
            cleaned[key] = value
    return cleaned


def _to_frame(value: pd.DataFrame | Iterable[dict[str, object]]) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    return pd.DataFrame(list(value))

