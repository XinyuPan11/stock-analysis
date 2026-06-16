from __future__ import annotations

from typing import Iterable

import pandas as pd


DEFAULT_FACTOR_NAMES = [
    "total_score",
    "momentum_score",
    "trend_score",
    "relative_strength_score",
    "risk_score",
    "liquidity_score",
    "volatility",
    "drawdown",
    "amount",
    "volume",
]


def evaluate_factor_effectiveness(
    factor_rows: pd.DataFrame | Iterable[dict[str, object]],
    future_labels: pd.DataFrame | Iterable[dict[str, object]],
    *,
    as_of_date: str,
    horizon_days: int,
    factor_names: Iterable[str] | None = None,
    quantile: float = 0.2,
) -> list[dict[str, object]]:
    factors = _to_frame(factor_rows)
    labels = _to_frame(future_labels)
    names = list(factor_names or DEFAULT_FACTOR_NAMES)
    if factors.empty or labels.empty or "symbol" not in factors.columns or "symbol" not in labels.columns:
        return [_missing_factor(name, as_of_date, horizon_days, "missing_input") for name in names]

    merged = factors.merge(labels, on="symbol", how="inner", suffixes=("", "_future"))
    if "future_return" in merged.columns:
        merged["future_return"] = pd.to_numeric(merged["future_return"], errors="coerce")
    if "data_quality" not in merged.columns or "future_return" not in merged.columns:
        return [_missing_factor(name, as_of_date, horizon_days, "missing_future_labels") for name in names]
    valid = merged[(merged["data_quality"] == "ok") & merged["future_return"].notna()].copy()
    return [_evaluate_one_factor(valid, name, as_of_date=as_of_date, horizon_days=horizon_days, quantile=quantile) for name in names]


def _evaluate_one_factor(
    frame: pd.DataFrame,
    factor_name: str,
    *,
    as_of_date: str,
    horizon_days: int,
    quantile: float,
) -> dict[str, object]:
    base = {
        "factor_name": factor_name,
        "as_of_date": as_of_date,
        "horizon_days": horizon_days,
        "correlation_with_future_return": None,
        "top_quantile_average_return": None,
        "bottom_quantile_average_return": None,
        "spread": None,
        "top_quantile_outperform_rate": None,
        "notes": [],
    }
    if factor_name not in frame.columns:
        return {**base, "notes": ["missing_factor"]}
    working = frame.loc[:, ["symbol", factor_name, "future_return", "outperformed_benchmark"] if "outperformed_benchmark" in frame.columns else ["symbol", factor_name, "future_return"]].copy()
    working[factor_name] = pd.to_numeric(working[factor_name], errors="coerce")
    working["future_return"] = pd.to_numeric(working["future_return"], errors="coerce")
    working = working.dropna(subset=[factor_name, "future_return"])
    if len(working) < 2:
        return {**base, "notes": ["insufficient_valid_rows"]}

    top_count = max(1, int(len(working) * quantile))
    ranked = working.sort_values(factor_name, ascending=False)
    top = ranked.head(top_count)
    bottom = ranked.tail(top_count)
    top_avg = float(top["future_return"].mean())
    bottom_avg = float(bottom["future_return"].mean())
    return {
        **base,
        "correlation_with_future_return": _corr_or_none(working[factor_name], working["future_return"]),
        "top_quantile_average_return": top_avg,
        "bottom_quantile_average_return": bottom_avg,
        "spread": top_avg - bottom_avg,
        "top_quantile_outperform_rate": _outperform_rate(top),
        "notes": [],
    }


def _missing_factor(factor_name: str, as_of_date: str, horizon_days: int, note: str) -> dict[str, object]:
    return {
        "factor_name": factor_name,
        "as_of_date": as_of_date,
        "horizon_days": horizon_days,
        "correlation_with_future_return": None,
        "top_quantile_average_return": None,
        "bottom_quantile_average_return": None,
        "spread": None,
        "top_quantile_outperform_rate": None,
        "notes": [note],
    }


def _corr_or_none(left: pd.Series, right: pd.Series) -> float | None:
    if left.nunique(dropna=True) < 2 or right.nunique(dropna=True) < 2:
        return None
    value = left.corr(right)
    return None if pd.isna(value) else float(value)


def _outperform_rate(frame: pd.DataFrame) -> float | None:
    if "outperformed_benchmark" not in frame.columns:
        return None
    valid = frame["outperformed_benchmark"].dropna()
    if valid.empty:
        return None
    return float(valid.astype(bool).mean())


def _to_frame(value: pd.DataFrame | Iterable[dict[str, object]]) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    return pd.DataFrame(list(value))
