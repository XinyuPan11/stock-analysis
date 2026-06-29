from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class PointInTimeSplitResult:
    feature_frame: pd.DataFrame
    future_frame: pd.DataFrame
    as_of_date: str
    latest_input_date: str | None
    max_raw_cache_date: str | None
    future_rows_excluded_count: int
    leakage_guard_applied: bool = True

    def diagnostics(self) -> dict[str, Any]:
        return {
            "as_of_date": self.as_of_date,
            "latest_input_date": self.latest_input_date,
            "max_raw_cache_date": self.max_raw_cache_date,
            "future_rows_excluded_count": self.future_rows_excluded_count,
            "leakage_guard_applied": self.leakage_guard_applied,
        }


@dataclass(frozen=True)
class PointInTimeSliceResult:
    frame: pd.DataFrame
    as_of_date: str
    latest_input_date: str | None
    max_raw_cache_date: str | None
    future_rows_excluded_count: int
    leakage_guard_applied: bool = True

    def diagnostics(self) -> dict[str, Any]:
        return {
            "as_of_date": self.as_of_date,
            "latest_input_date": self.latest_input_date,
            "max_raw_cache_date": self.max_raw_cache_date,
            "future_rows_excluded_count": self.future_rows_excluded_count,
            "leakage_guard_applied": self.leakage_guard_applied,
        }


def slice_daily_as_of(
    frame: pd.DataFrame | None,
    as_of_date: str,
    *,
    date_column: str = "trade_date",
) -> PointInTimeSliceResult:
    """Return rows dated on or before as_of_date, preserving input row order."""

    split = split_daily_point_in_time(frame, as_of_date, date_column=date_column)
    return PointInTimeSliceResult(
        frame=split.feature_frame,
        as_of_date=split.as_of_date,
        latest_input_date=split.latest_input_date,
        max_raw_cache_date=split.max_raw_cache_date,
        future_rows_excluded_count=split.future_rows_excluded_count,
        leakage_guard_applied=True,
    )


def split_daily_point_in_time(
    frame: pd.DataFrame | None,
    as_of_date: str,
    *,
    date_column: str = "trade_date",
) -> PointInTimeSplitResult:
    """Split daily rows into feature (<= as-of) and future-label (> as-of) windows."""

    normalized_as_of = _normalize_date(as_of_date, field_name="as_of_date")
    if frame is None or frame.empty:
        empty = pd.DataFrame() if frame is None else frame.copy()
        return PointInTimeSplitResult(
            feature_frame=empty.copy(),
            future_frame=empty.copy(),
            as_of_date=normalized_as_of,
            latest_input_date=None,
            max_raw_cache_date=None,
            future_rows_excluded_count=0,
        )
    if date_column not in frame.columns:
        raise ValueError(f"Point-in-time guard requires date column: {date_column}")

    result = frame.copy()
    raw_values = result[date_column].astype(str)
    parsed_dates = pd.to_datetime(raw_values, errors="coerce")
    invalid_mask = parsed_dates.isna()
    if invalid_mask.any():
        examples = raw_values.loc[invalid_mask].head(3).tolist()
        raise ValueError(
            f"Point-in-time guard found {int(invalid_mask.sum())} malformed {date_column} values: {examples}"
        )

    as_of_timestamp = pd.Timestamp(normalized_as_of)
    feature_mask = parsed_dates <= as_of_timestamp
    feature_frame = result.loc[feature_mask].copy()
    future_frame = result.loc[~feature_mask].copy()
    latest_input = _format_max_date(parsed_dates.loc[feature_mask])
    max_raw = _format_max_date(parsed_dates)
    return PointInTimeSplitResult(
        feature_frame=feature_frame,
        future_frame=future_frame,
        as_of_date=normalized_as_of,
        latest_input_date=latest_input,
        max_raw_cache_date=max_raw,
        future_rows_excluded_count=int((~feature_mask).sum()),
    )


def _normalize_date(value: str, *, field_name: str) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"Invalid {field_name}: {value}")
    return parsed.strftime("%Y-%m-%d")


def _format_max_date(values: pd.Series) -> str | None:
    if values.empty:
        return None
    value = values.max()
    if pd.isna(value):
        return None
    return pd.Timestamp(value).strftime("%Y-%m-%d")
