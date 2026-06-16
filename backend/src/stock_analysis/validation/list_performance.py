from __future__ import annotations

from typing import Iterable

import pandas as pd


SUPPORTED_LIST_IDS = [
    "high_confidence_candidates",
    "trend_leaders",
    "long_term_stable",
    "breakout_watch",
    "accumulation_watch",
    "rebound_watch",
    "high_risk_active",
]


def evaluate_list_performance(
    list_payload: dict[str, object],
    future_labels: pd.DataFrame | Iterable[dict[str, object]],
    *,
    horizon_days: int,
) -> dict[str, object]:
    labels = _to_frame(future_labels)
    items = list_payload.get("items", [])
    item_rows = items if isinstance(items, list) else []
    symbols = [str(item.get("symbol", "")) for item in item_rows if isinstance(item, dict) and item.get("symbol")]
    list_id = str(list_payload.get("list_id", ""))
    as_of_date = str(list_payload.get("as_of_date", ""))

    base = {
        "list_id": list_id,
        "as_of_date": as_of_date,
        "horizon_days": horizon_days,
        "item_count": len(symbols),
        "valid_future_count": 0,
        "average_future_return": None,
        "average_excess_return": None,
        "median_future_return": None,
        "win_rate": None,
        "outperform_rate": None,
        "top_10_average_return": None,
        "top_20_average_return": None,
        "max_drawdown_average": None,
        "best_cases": [],
        "worst_cases": [],
        "notes": [],
    }
    if not symbols:
        return {**base, "notes": ["empty_list"]}
    if labels.empty or "symbol" not in labels.columns:
        return {**base, "notes": ["missing_future_labels"]}

    rows = labels[labels["symbol"].astype(str).isin(symbols)].copy()
    if "data_quality" not in rows.columns:
        return {**base, "notes": ["missing_data_quality"]}
    valid = rows[rows["data_quality"] == "ok"].copy()
    for column in ["future_return", "future_excess_return", "max_drawdown_during_holding"]:
        if column in valid.columns:
            valid[column] = pd.to_numeric(valid[column], errors="coerce")
    valid = valid.dropna(subset=["future_return"])
    if valid.empty:
        return {**base, "notes": ["no_valid_future_labels"]}

    returns = valid["future_return"]
    excess = valid["future_excess_return"] if "future_excess_return" in valid.columns else pd.Series(dtype=float)
    drawdown = valid["max_drawdown_during_holding"] if "max_drawdown_during_holding" in valid.columns else pd.Series(dtype=float)
    ranked = _with_list_order(valid, symbols)
    return {
        **base,
        "valid_future_count": int(len(valid)),
        "average_future_return": float(returns.mean()),
        "average_excess_return": _mean_or_none(excess),
        "median_future_return": float(returns.median()),
        "win_rate": float((returns > 0).mean()),
        "outperform_rate": _outperform_rate(valid),
        "top_10_average_return": _top_n_average(ranked, 10),
        "top_20_average_return": _top_n_average(ranked, 20),
        "max_drawdown_average": _mean_or_none(drawdown),
        "best_cases": _case_rows(valid.sort_values("future_return", ascending=False).head(5)),
        "worst_cases": _case_rows(valid.sort_values("future_return", ascending=True).head(5)),
        "notes": [],
    }


def evaluate_lists_performance(
    list_payloads: Iterable[dict[str, object]],
    future_labels: pd.DataFrame | Iterable[dict[str, object]],
    *,
    horizon_days: int,
) -> list[dict[str, object]]:
    return [evaluate_list_performance(payload, future_labels, horizon_days=horizon_days) for payload in list_payloads]


def _with_list_order(frame: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    order = {symbol: index for index, symbol in enumerate(symbols)}
    result = frame.copy()
    result["list_order"] = result["symbol"].astype(str).map(order).fillna(len(symbols)).astype(int)
    return result.sort_values("list_order")


def _top_n_average(frame: pd.DataFrame, n: int) -> float | None:
    if frame.empty:
        return None
    return float(frame.head(n)["future_return"].mean())


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
    columns = ["symbol", "future_return", "future_excess_return", "max_drawdown_during_holding", "data_quality"]
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
