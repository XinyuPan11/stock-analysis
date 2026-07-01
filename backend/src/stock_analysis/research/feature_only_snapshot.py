"""Safe feature-only exports from an existing member-level as-of snapshot."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Any

import pandas as pd


REQUIRED_COLUMNS: tuple[str, ...] = (
    "as_of_date",
    "symbol",
    "leakage_guard_applied",
    "pre_5d_return",
    "pre_20d_return",
    "pre_60d_return",
    "drawdown_60d",
    "amount_change_20d",
    "volume_change_20d",
    "distance_to_60d_high",
    "distance_to_60d_low",
    "recent_acceleration_proxy",
    "high_position_crowding_proxy",
    "is_breakout_watch",
    "is_accumulation_watch",
)

VOLATILITY_COLUMNS: tuple[str, ...] = (
    "technical_volatility_20d",
    "volatility_20d",
)

ALLOWED_FUTURE_DIAGNOSTIC_COLUMNS: frozenset[str] = frozenset(
    {"future_rows_excluded_count"}
)

OUTCOME_EXACT_COLUMNS: frozenset[str] = frozenset(
    {
        "label",
        "winner",
        "loser",
        "target",
        "outcome",
        "future_return",
        "future_excess_return",
        "realized_return",
        "benchmark_return",
        "benchmark_future_return",
        "benchmark_data_quality",
        "excess_return",
        "outperformed_benchmark",
        "future_top_quantile",
        "max_drawdown_during_holding",
        "max_future",
        "min_future",
        "future_high",
        "future_low",
    }
)

OUTCOME_COLUMN_PATTERN = re.compile(
    r"(^|_)(future|forward|realized|winner|loser|outcome|target)(_|$)"
    r"|(^|_)label($|_)"
    r"|(^|_)excess_return($|_)"
    r"|^(max_future|min_future|next_)",
    re.IGNORECASE,
)

DATE_COLUMNS_EXEMPT_FROM_AS_OF_CUTOFF: frozenset[str] = frozenset(
    {
        # This records the physical cache extent, not feature input usage.
        "max_raw_cache_date",
    }
)


class FeatureOnlySnapshotError(ValueError):
    def __init__(
        self,
        status: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.details = dict(details or {})


@dataclass
class FeatureOnlySnapshotResult:
    frame: pd.DataFrame
    metadata: dict[str, Any]


def load_member_snapshot(path: str | Path) -> pd.DataFrame:
    source = Path(path)
    if not source.exists():
        raise FeatureOnlySnapshotError(
            "blocked_missing_source_snapshot",
            f"Source snapshot not found: {source}",
        )
    if source.suffix.lower() == ".csv":
        return pd.read_csv(source, dtype={"symbol": str})
    if source.suffix.lower() == ".json":
        try:
            payload = json.loads(source.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FeatureOnlySnapshotError(
                "blocked_invalid_source_snapshot",
                f"Source snapshot is not valid JSON: {source}",
            ) from exc
        if isinstance(payload, list):
            records = payload
        elif isinstance(payload, dict) and isinstance(payload.get("records"), list):
            records = payload["records"]
        else:
            raise FeatureOnlySnapshotError(
                "blocked_invalid_source_snapshot",
                "JSON snapshot must be a record list or contain records.",
            )
        return pd.DataFrame(records)
    raise FeatureOnlySnapshotError(
        "blocked_invalid_source_snapshot",
        "Source snapshot must be CSV or JSON.",
    )


def build_feature_only_snapshot(
    source: pd.DataFrame,
    *,
    as_of_date: str,
    source_snapshot_path: str | Path,
    drop_outcome_columns: bool = False,
) -> FeatureOnlySnapshotResult:
    cutoff = _parse_as_of_date(as_of_date)
    outcome_columns = find_outcome_columns(source.columns)
    if outcome_columns and not drop_outcome_columns:
        raise FeatureOnlySnapshotError(
            "blocked_outcome_columns_present",
            (
                "Source snapshot contains future/outcome columns. "
                "Use --drop-outcome-columns only for an explicit audited export."
            ),
            details={"outcome_columns": outcome_columns},
        )

    frame = source.drop(columns=outcome_columns).copy()
    missing_columns = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    if not any(column in frame.columns for column in VOLATILITY_COLUMNS):
        missing_columns.append("technical_volatility_20d|volatility_20d")
    if missing_columns:
        raise FeatureOnlySnapshotError(
            "blocked_missing_required_feature",
            "Source snapshot is missing fields required by H1-H5.",
            details={"missing_columns": missing_columns},
        )

    selected = frame.loc[
        frame["as_of_date"].astype(str).str.strip() == as_of_date
    ].copy()
    if selected.empty:
        raise FeatureOnlySnapshotError(
            "blocked_missing_as_of_rows",
            f"Source snapshot contains no rows for as_of_date={as_of_date}.",
        )
    _validate_symbols(selected)
    _validate_leakage_guard(selected)
    _validate_point_in_time_dates(selected, cutoff)

    selected = selected.reset_index(drop=True)
    if find_outcome_columns(selected.columns):
        raise FeatureOnlySnapshotError(
            "blocked_outcome_columns_present",
            "Feature-only output still contains an outcome column.",
        )

    metadata = {
        "status": "ok",
        "research_only": True,
        "feature_only": True,
        "labels_joined": False,
        "provider_access": False,
        "production_change": False,
        "as_of_date": as_of_date,
        "source_snapshot_path": str(Path(source_snapshot_path)),
        "output_path": None,
        "input_row_count": int(len(source)),
        "output_row_count": int(len(selected)),
        "dropped_outcome_columns": outcome_columns,
        "drop_outcome_columns_requested": bool(drop_outcome_columns),
        "latest_input_date_max": _latest_date(selected, "latest_input_date"),
        "leakage_guard_applied": True,
    }
    return FeatureOnlySnapshotResult(frame=selected, metadata=metadata)


def write_feature_only_snapshot_outputs(
    result: FeatureOnlySnapshotResult,
    *,
    output_dir: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, str]:
    csv_path = (
        Path(output_path)
        if output_path is not None
        else Path(output_dir)
        / f"member_level_asof_features_{result.metadata['as_of_date']}.csv"
    )
    if csv_path.suffix.lower() != ".csv":
        raise FeatureOnlySnapshotError(
            "blocked_invalid_output_path",
            "--output-path must name a CSV file.",
        )
    json_path = csv_path.with_suffix(".json")
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    result.frame.to_csv(csv_path, index=False, encoding="utf-8-sig")
    paths = {"csv": str(csv_path), "json": str(json_path)}
    result.metadata["output_path"] = str(csv_path)
    result.metadata["output_paths"] = paths
    payload = {
        "metadata": _json_safe(result.metadata),
        "records": _json_safe(result.frame.to_dict(orient="records")),
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return paths


def find_outcome_columns(columns: Any) -> list[str]:
    return sorted(
        str(column)
        for column in columns
        if _is_outcome_column(str(column))
    )


def _is_outcome_column(column: str) -> bool:
    normalized = column.strip().lower()
    if normalized in ALLOWED_FUTURE_DIAGNOSTIC_COLUMNS:
        return False
    return (
        normalized in OUTCOME_EXACT_COLUMNS
        or bool(OUTCOME_COLUMN_PATTERN.search(normalized))
    )


def _parse_as_of_date(value: str) -> pd.Timestamp:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise FeatureOnlySnapshotError(
            "blocked_invalid_as_of_date",
            f"Invalid as_of_date: {value}",
        )
    return pd.Timestamp(parsed).normalize()


def _validate_symbols(frame: pd.DataFrame) -> None:
    symbols = frame["symbol"].astype(str).str.strip()
    if (symbols == "").any():
        raise FeatureOnlySnapshotError(
            "blocked_invalid_symbol",
            "Feature-only rows require a non-empty symbol.",
        )


def _validate_leakage_guard(frame: pd.DataFrame) -> None:
    values = frame["leakage_guard_applied"].map(_as_bool)
    if values.isna().any() or not values.all():
        raise FeatureOnlySnapshotError(
            "blocked_unverified_leakage_guard",
            "Every exported row must have leakage_guard_applied=true.",
        )


def _validate_point_in_time_dates(
    frame: pd.DataFrame,
    cutoff: pd.Timestamp,
) -> None:
    for column in frame.columns:
        normalized = str(column).strip().lower()
        if normalized in DATE_COLUMNS_EXEMPT_FROM_AS_OF_CUTOFF:
            continue
        if normalized != "as_of_date" and not normalized.endswith("_date"):
            continue
        present = frame[column].notna() & (
            frame[column].astype(str).str.strip() != ""
        )
        parsed = pd.to_datetime(frame.loc[present, column], errors="coerce")
        if parsed.isna().any():
            raise FeatureOnlySnapshotError(
                "blocked_point_in_time_violation",
                f"{column} contains malformed dates.",
                details={"column": str(column)},
            )
        if (parsed.dt.normalize() > cutoff).any():
            symbols = frame.loc[present].loc[
                parsed.dt.normalize() > cutoff, "symbol"
            ]
            raise FeatureOnlySnapshotError(
                "blocked_point_in_time_violation",
                f"{column} exceeds as_of_date.",
                details={
                    "column": str(column),
                    "symbols": sorted(symbols.astype(str).tolist()),
                },
            )


def _latest_date(frame: pd.DataFrame, column: str) -> str | None:
    if column not in frame.columns:
        return None
    values = pd.to_datetime(frame[column], errors="coerce").dropna()
    if values.empty:
        return None
    return values.max().strftime("%Y-%m-%d")


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not pd.isna(value):
        if float(value) == 1.0:
            return True
        if float(value) == 0.0:
            return False
    normalized = str(value).strip().lower()
    if normalized in {"true", "yes", "1"}:
        return True
    if normalized in {"false", "no", "0"}:
        return False
    return None


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if hasattr(value, "item"):
        return _json_safe(value.item())
    return value


