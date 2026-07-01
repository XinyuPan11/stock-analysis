"""Label-free historical H1-H5 source snapshots from local as-of artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable

import pandas as pd

from stock_analysis.data.point_in_time import slice_daily_as_of
from stock_analysis.research.feature_only_snapshot import (
    find_outcome_columns,
)
from stock_analysis.research.historical_h1h5_readiness import (
    HISTORICAL_EXCLUDED_WINDOWS,
    HISTORICAL_VALIDATION_ID,
    HISTORICAL_WINDOWS,
    MINIMUM_VALID_UNIVERSE_ROWS,
)


HISTORICAL_EVIDENCE_LEVEL = "historical_sealed_not_prospective"
PROVIDER = "baostock"
TECHNICAL_FEATURE_FIELDS: tuple[str, ...] = (
    "pre_5d_return",
    "pre_20d_return",
    "pre_60d_return",
    "technical_volatility_20d",
    "drawdown_60d",
    "amount_change_20d",
    "volume_change_20d",
    "distance_to_60d_high",
    "distance_to_60d_low",
    "recent_acceleration_proxy",
    "high_position_crowding_proxy",
)
POINT_IN_TIME_FIELDS: tuple[str, ...] = (
    "latest_input_date",
    "max_raw_cache_date",
    "future_rows_excluded_count",
    "leakage_guard_applied",
)
FACTOR_CONTEXT_FIELDS: tuple[str, ...] = (
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
)
MEMBERSHIP_CONTEXT_FIELDS: tuple[str, ...] = (
    "rank",
    "total_score",
    "momentum_score",
    "trend_score",
    "relative_strength_score",
    "risk_score",
    "liquidity_score",
    "primary_type",
    "research_status",
    "risk_level",
    "captured_positive_lists",
    "captured_risk_lists",
    "is_high_confidence",
    "is_trend_leader",
    "is_long_term_stable",
    "is_breakout_watch",
    "is_accumulation_watch",
    "is_rebound_watch",
    "is_high_risk_active",
)
REQUIRED_MEMBERSHIP_FIELDS: tuple[str, ...] = (
    "is_breakout_watch",
    "is_accumulation_watch",
)
BOOLEAN_MEMBERSHIP_FIELDS: frozenset[str] = frozenset(
    field
    for field in MEMBERSHIP_CONTEXT_FIELDS
    if field.startswith("is_")
)
FORBIDDEN_INPUT_PATH_PATTERN = re.compile(
    r"(^|[\\/_.-])("
    r"validation|walk_forward_predictions|list_performance|"
    r"factor_effectiveness|strategy_experiments|future_labels?"
    r")([\\/_.-]|$)",
    re.IGNORECASE,
)


class HistoricalSourceSnapshotError(ValueError):
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
class HistoricalSourceSnapshotResult:
    frame: pd.DataFrame
    metadata: dict[str, Any]


def build_historical_source_snapshot(
    *,
    as_of_date: str,
    factors_file: str | Path,
    membership_file: str | Path,
    cache_dir: str | Path,
) -> HistoricalSourceSnapshotResult:
    _validate_historical_date(as_of_date)
    factors_path = _validate_input_path(factors_file, role="factors")
    membership_path = _validate_input_path(
        membership_file,
        role="membership",
    )
    resolved_cache_dir = Path(cache_dir)
    factors = _load_safe_csv(
        factors_path,
        role="factors",
        as_of_date=as_of_date,
        required_columns=("symbol", "as_of_date"),
    )
    membership = _load_safe_csv(
        membership_path,
        role="membership",
        as_of_date=as_of_date,
        required_columns=(
            "symbol",
            "as_of_date",
            *REQUIRED_MEMBERSHIP_FIELDS,
        ),
    )
    _validate_unique_symbols(factors, role="factors")
    _validate_unique_symbols(membership, role="membership")

    if len(factors) < MINIMUM_VALID_UNIVERSE_ROWS:
        raise HistoricalSourceSnapshotError(
            "blocked_insufficient_source_universe",
            "Factors artifact is below the 100-row historical universe gate.",
            details={
                "row_count": int(len(factors)),
                "minimum_row_count": MINIMUM_VALID_UNIVERSE_ROWS,
            },
        )

    factor_symbols = factors["symbol"].astype(str).tolist()
    membership_by_symbol = membership.set_index("symbol", drop=False)
    missing_membership = sorted(
        symbol
        for symbol in factor_symbols
        if symbol not in membership_by_symbol.index
    )
    if missing_membership:
        raise HistoricalSourceSnapshotError(
            "blocked_missing_membership_context",
            "Membership artifact does not cover the factors universe.",
            details={"missing_symbols": missing_membership},
        )

    selected_membership = membership_by_symbol.loc[
        factor_symbols
    ].reset_index(drop=True)
    _normalize_membership_booleans(selected_membership)
    technical = pd.DataFrame(
        [
            _technical_feature_row(
                _cache_path(resolved_cache_dir, symbol),
                symbol=symbol,
                as_of_date=as_of_date,
            )
            for symbol in factor_symbols
        ]
    )
    blocked = technical.loc[
        technical["_blocked_status"].notna(),
        ["symbol", "_blocked_status", "_blocked_details"],
    ]
    if not blocked.empty:
        raise HistoricalSourceSnapshotError(
            "blocked_required_features_unavailable",
            "Required as-of H1-H5 features could not be produced.",
            details={
                "blocked_count": int(len(blocked)),
                "blocked_rows": blocked.head(50).to_dict(orient="records"),
            },
        )
    technical = technical.drop(
        columns=["_blocked_status", "_blocked_details"]
    )

    factor_columns = [
        field for field in FACTOR_CONTEXT_FIELDS if field in factors
    ]
    membership_columns = [
        field
        for field in MEMBERSHIP_CONTEXT_FIELDS
        if field in selected_membership
    ]
    output = pd.DataFrame(
        {
            "as_of_date": [as_of_date] * len(factors),
            "symbol": factor_symbols,
        }
    )
    if factor_columns:
        output = output.merge(
            factors.loc[:, ["symbol", *factor_columns]],
            on="symbol",
            how="left",
            validate="one_to_one",
        )
    if membership_columns:
        output = output.merge(
            selected_membership.loc[
                :,
                ["symbol", *membership_columns],
            ],
            on="symbol",
            how="left",
            validate="one_to_one",
        )
    output = output.merge(
        technical,
        on="symbol",
        how="left",
        validate="one_to_one",
    )
    output["research_only"] = True
    output["provider_access"] = False
    output["labels_joined"] = False
    output["production_change"] = False
    output["validation_id"] = HISTORICAL_VALIDATION_ID
    output["evidence_level"] = HISTORICAL_EVIDENCE_LEVEL
    output["source_factors_path"] = str(factors_path)
    output["source_membership_path"] = str(membership_path)
    output["source_cache_dir"] = str(resolved_cache_dir)

    _validate_output(output, as_of_date=as_of_date)
    metadata = {
        "status": "ok",
        "research_only": True,
        "label_free_source": True,
        "provider_access": False,
        "provider_fallback_available": False,
        "labels_joined": False,
        "production_change": False,
        "validation_run": False,
        "validation_outputs_read": False,
        "evaluator_called": False,
        "future_labels_generated": False,
        "future_returns_computed": False,
        "h1h5_cohort_builder_called": False,
        "validation_id": HISTORICAL_VALIDATION_ID,
        "evidence_level": HISTORICAL_EVIDENCE_LEVEL,
        "as_of_date": as_of_date,
        "input_row_count": int(len(factors)),
        "output_row_count": int(len(output)),
        "source_factors_path": str(factors_path),
        "source_membership_path": str(membership_path),
        "source_cache_dir": str(resolved_cache_dir),
        "latest_input_date_max": _latest_date(
            output["latest_input_date"]
        ),
        "max_raw_cache_date_max": _latest_date(
            output["max_raw_cache_date"]
        ),
        "future_rows_excluded_count": int(
            pd.to_numeric(
                output["future_rows_excluded_count"],
                errors="coerce",
            )
            .fillna(0)
            .sum()
        ),
        "leakage_guard_applied": True,
        "required_technical_features": list(TECHNICAL_FEATURE_FIELDS),
        "output_paths": {},
    }
    return HistoricalSourceSnapshotResult(
        frame=_ordered_output(output),
        metadata=metadata,
    )


def write_historical_source_snapshot_outputs(
    result: HistoricalSourceSnapshotResult,
    *,
    outputs_dir: str | Path,
) -> dict[str, str]:
    experiments_dir = Path(outputs_dir) / "experiments"
    experiments_dir.mkdir(parents=True, exist_ok=True)
    as_of_date = str(result.metadata["as_of_date"])
    csv_path = (
        experiments_dir
        / f"historical_h1h5_source_snapshot_{as_of_date}.csv"
    )
    json_path = csv_path.with_suffix(".json")
    _validate_output(result.frame, as_of_date=as_of_date)
    result.frame.to_csv(csv_path, index=False, encoding="utf-8-sig")
    paths = {"csv": str(csv_path), "json": str(json_path)}
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


def _validate_historical_date(as_of_date: str) -> None:
    if as_of_date in HISTORICAL_EXCLUDED_WINDOWS:
        raise HistoricalSourceSnapshotError(
            "blocked_excluded_window",
            "The date is consumed evidence or reserved for prospective U3.",
        )
    if as_of_date not in HISTORICAL_WINDOWS:
        raise HistoricalSourceSnapshotError(
            "blocked_unknown_historical_window",
            "The date is not preregistered for historical sealed validation.",
        )


def _validate_input_path(
    value: str | Path,
    *,
    role: str,
) -> Path:
    path = Path(value)
    normalized = str(path).replace("\\", "/")
    if FORBIDDEN_INPUT_PATH_PATTERN.search(normalized):
        raise HistoricalSourceSnapshotError(
            "blocked_forbidden_input_artifact",
            f"{role} input path names a forbidden validation/outcome artifact.",
            details={"path": str(path), "role": role},
        )
    if not path.exists():
        raise HistoricalSourceSnapshotError(
            "blocked_missing_as_of_artifact",
            f"Required {role} artifact is missing.",
            details={"path": str(path), "role": role},
        )
    if path.suffix.lower() != ".csv":
        raise HistoricalSourceSnapshotError(
            "blocked_invalid_as_of_artifact",
            f"{role} input must be an explicit CSV artifact.",
            details={"path": str(path), "role": role},
        )
    return path


def _load_safe_csv(
    path: Path,
    *,
    role: str,
    as_of_date: str,
    required_columns: Iterable[str],
) -> pd.DataFrame:
    try:
        columns = list(pd.read_csv(path, nrows=0).columns)
    except (OSError, pd.errors.ParserError, UnicodeError) as exc:
        raise HistoricalSourceSnapshotError(
            "blocked_invalid_as_of_artifact",
            f"{role} artifact header cannot be read.",
            details={"path": str(path), "role": role},
        ) from exc
    forbidden = find_outcome_columns(columns)
    if forbidden:
        raise HistoricalSourceSnapshotError(
            "blocked_forbidden_input_columns",
            f"{role} artifact contains forbidden outcome/label columns.",
            details={
                "path": str(path),
                "role": role,
                "forbidden_columns": forbidden,
            },
        )
    missing = sorted(set(required_columns) - set(columns))
    if missing:
        raise HistoricalSourceSnapshotError(
            "blocked_missing_as_of_columns",
            f"{role} artifact is missing required as-of columns.",
            details={"path": str(path), "role": role, "missing_columns": missing},
        )
    try:
        frame = pd.read_csv(path, dtype={"symbol": str})
    except (OSError, pd.errors.ParserError, UnicodeError) as exc:
        raise HistoricalSourceSnapshotError(
            "blocked_invalid_as_of_artifact",
            f"{role} artifact cannot be read.",
            details={"path": str(path), "role": role},
        ) from exc
    dates = frame["as_of_date"].astype(str).str.strip()
    if frame.empty or not dates.eq(as_of_date).all():
        raise HistoricalSourceSnapshotError(
            "blocked_artifact_as_of_mismatch",
            f"{role} artifact must contain only the requested as-of date.",
            details={"path": str(path), "role": role},
        )
    for column in frame.columns:
        normalized = str(column).strip().lower()
        if normalized != "latest_input_date" and not (
            normalized.endswith("_input_date")
        ):
            continue
        present = frame[column].notna() & (
            frame[column].astype(str).str.strip() != ""
        )
        values = frame.loc[present, column].astype(str).str.strip()
        if values.gt(as_of_date).any():
            raise HistoricalSourceSnapshotError(
                "blocked_point_in_time_violation",
                f"{role} artifact contains an input date after as_of_date.",
                details={"path": str(path), "role": role, "column": column},
            )
    return frame


def _validate_unique_symbols(frame: pd.DataFrame, *, role: str) -> None:
    frame["symbol"] = frame["symbol"].astype(str).str.strip()
    if frame["symbol"].eq("").any():
        raise HistoricalSourceSnapshotError(
            "blocked_invalid_symbol",
            f"{role} artifact contains an empty symbol.",
        )
    duplicates = sorted(
        frame.loc[frame["symbol"].duplicated(), "symbol"].unique()
    )
    if duplicates:
        raise HistoricalSourceSnapshotError(
            "blocked_duplicate_symbol",
            f"{role} artifact must contain one row per symbol.",
            details={"role": role, "duplicate_symbols": duplicates},
        )


def _normalize_membership_booleans(frame: pd.DataFrame) -> None:
    for field in BOOLEAN_MEMBERSHIP_FIELDS.intersection(frame.columns):
        parsed = frame[field].map(_as_bool)
        if parsed.isna().any():
            raise HistoricalSourceSnapshotError(
                "blocked_invalid_membership_value",
                f"Membership field must be boolean: {field}.",
                details={"field": field},
            )
        frame[field] = parsed.astype(bool)


def _cache_path(cache_dir: Path, symbol: str) -> Path:
    return (
        cache_dir
        / PROVIDER
        / "stock_daily"
        / "adjusted"
        / f"{symbol}.csv"
    )


def _technical_feature_row(
    path: Path,
    *,
    symbol: str,
    as_of_date: str,
) -> dict[str, Any]:
    base = {
        "symbol": symbol,
        **{field: None for field in TECHNICAL_FEATURE_FIELDS},
        **{field: None for field in POINT_IN_TIME_FIELDS},
        "_blocked_status": None,
        "_blocked_details": None,
    }
    if not path.exists():
        return {
            **base,
            "_blocked_status": "missing_daily_cache",
            "_blocked_details": str(path),
        }
    try:
        header = list(pd.read_csv(path, nrows=0).columns)
    except (OSError, pd.errors.ParserError, UnicodeError):
        return {
            **base,
            "_blocked_status": "invalid_daily_cache",
            "_blocked_details": str(path),
        }
    forbidden = find_outcome_columns(header)
    if forbidden:
        return {
            **base,
            "_blocked_status": "forbidden_daily_cache_columns",
            "_blocked_details": ",".join(forbidden),
        }
    try:
        raw = pd.read_csv(path, dtype={"symbol": str, "trade_date": str})
        sliced = slice_daily_as_of(raw, as_of_date)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        return {
            **base,
            "_blocked_status": "invalid_daily_cache",
            "_blocked_details": type(exc).__name__,
        }
    frame = sliced.frame.copy()
    if frame.empty:
        return {
            **base,
            **_pit_diagnostics(sliced),
            "_blocked_status": "no_rows_on_or_before_as_of",
            "_blocked_details": str(path),
        }
    frame["trade_date"] = pd.to_datetime(
        frame["trade_date"],
        errors="coerce",
    )
    if frame["trade_date"].isna().any():
        return {
            **base,
            "_blocked_status": "malformed_trade_date",
            "_blocked_details": str(path),
        }
    frame = frame.sort_values("trade_date")
    price_column = "adj_close" if "adj_close" in frame else "close"
    required_raw = {price_column, "amount", "volume"}
    missing_raw = sorted(required_raw - set(frame.columns))
    if price_column not in {"adj_close", "close"} or missing_raw:
        return {
            **base,
            **_pit_diagnostics(sliced),
            "_blocked_status": "missing_daily_cache_columns",
            "_blocked_details": ",".join(missing_raw or ["close|adj_close"]),
        }
    price = pd.to_numeric(frame[price_column], errors="coerce").dropna()
    amount = pd.to_numeric(frame["amount"], errors="coerce").dropna()
    volume = pd.to_numeric(frame["volume"], errors="coerce").dropna()
    pre_5d = _period_return(price, 5)
    pre_20d = _period_return(price, 20)
    pre_60d = _period_return(price, 60)
    volatility = _volatility(price, 20)
    drawdown = _drawdown(price, 60)
    distance_high, distance_low, position = _range_position(price, 60)
    values = {
        "pre_5d_return": pre_5d,
        "pre_20d_return": pre_20d,
        "pre_60d_return": pre_60d,
        "technical_volatility_20d": volatility,
        "drawdown_60d": drawdown,
        "amount_change_20d": _recent_vs_prior_change(amount),
        "volume_change_20d": _recent_vs_prior_change(volume),
        "distance_to_60d_high": distance_high,
        "distance_to_60d_low": distance_low,
        "recent_acceleration_proxy": (
            pre_5d - pre_20d / 4.0
            if pre_5d is not None and pre_20d is not None
            else None
        ),
        "high_position_crowding_proxy": (
            position * max(pre_20d, 0.0) * volatility
            if position is not None
            and pre_20d is not None
            and volatility is not None
            else None
        ),
    }
    missing_features = [
        field for field, value in values.items() if value is None
    ]
    return {
        **base,
        **values,
        **_pit_diagnostics(sliced),
        "_blocked_status": (
            "insufficient_as_of_history" if missing_features else None
        ),
        "_blocked_details": (
            ",".join(missing_features) if missing_features else None
        ),
    }


def _pit_diagnostics(sliced: Any) -> dict[str, Any]:
    diagnostics = sliced.diagnostics()
    return {
        field: diagnostics.get(field) for field in POINT_IN_TIME_FIELDS
    }


def _validate_output(frame: pd.DataFrame, *, as_of_date: str) -> None:
    forbidden = find_outcome_columns(frame.columns)
    if forbidden:
        raise HistoricalSourceSnapshotError(
            "blocked_forbidden_output_columns",
            "Source snapshot contains forbidden outcome/label columns.",
            details={"forbidden_columns": forbidden},
        )
    required = {
        "as_of_date",
        "symbol",
        *TECHNICAL_FEATURE_FIELDS,
        *POINT_IN_TIME_FIELDS,
        *REQUIRED_MEMBERSHIP_FIELDS,
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise HistoricalSourceSnapshotError(
            "blocked_missing_output_columns",
            "Source snapshot is missing required H1-H5 columns.",
            details={"missing_columns": missing},
        )
    if len(frame) < MINIMUM_VALID_UNIVERSE_ROWS:
        raise HistoricalSourceSnapshotError(
            "blocked_insufficient_source_universe",
            "Source snapshot is below the 100-row gate.",
        )
    if not frame["as_of_date"].astype(str).eq(as_of_date).all():
        raise HistoricalSourceSnapshotError(
            "blocked_output_as_of_mismatch",
            "Source snapshot contains the wrong as-of date.",
        )
    guard = frame["leakage_guard_applied"].map(_as_bool)
    if guard.isna().any() or not guard.all():
        raise HistoricalSourceSnapshotError(
            "blocked_unverified_leakage_guard",
            "Every source row must have leakage_guard_applied=true.",
        )
    latest = pd.to_datetime(
        frame["latest_input_date"],
        errors="coerce",
    )
    if latest.isna().any() or (latest > pd.Timestamp(as_of_date)).any():
        raise HistoricalSourceSnapshotError(
            "blocked_point_in_time_violation",
            "latest_input_date must be present and on or before as_of_date.",
        )
    for field in TECHNICAL_FEATURE_FIELDS:
        numeric = pd.to_numeric(frame[field], errors="coerce")
        if numeric.isna().any() or not numeric.map(math.isfinite).all():
            raise HistoricalSourceSnapshotError(
                "blocked_invalid_required_feature",
                f"Required feature must be finite: {field}.",
            )


def _ordered_output(frame: pd.DataFrame) -> pd.DataFrame:
    leading = [
        "as_of_date",
        "symbol",
        *POINT_IN_TIME_FIELDS,
        *TECHNICAL_FEATURE_FIELDS,
        *REQUIRED_MEMBERSHIP_FIELDS,
    ]
    remaining = [column for column in frame.columns if column not in leading]
    return frame.loc[:, [*leading, *remaining]].reset_index(drop=True)


def _period_return(series: pd.Series, periods: int) -> float | None:
    if len(series) <= periods:
        return None
    start = float(series.iloc[-periods - 1])
    end = float(series.iloc[-1])
    if not math.isfinite(start) or not math.isfinite(end) or start == 0:
        return None
    return end / start - 1.0


def _volatility(series: pd.Series, periods: int) -> float | None:
    returns = series.pct_change().dropna()
    if len(returns) < periods:
        return None
    value = float(returns.tail(periods).std(ddof=0))
    return value if math.isfinite(value) else None


def _drawdown(series: pd.Series, periods: int) -> float | None:
    if len(series) < periods:
        return None
    window = series.tail(periods).astype(float)
    drawdowns = window / window.cummax() - 1.0
    value = float(drawdowns.min())
    return value if math.isfinite(value) else None


def _range_position(
    series: pd.Series,
    periods: int,
) -> tuple[float | None, float | None, float | None]:
    if len(series) < periods:
        return None, None, None
    window = series.tail(periods).astype(float)
    latest = float(window.iloc[-1])
    high = float(window.max())
    low = float(window.min())
    if not all(math.isfinite(item) for item in (latest, high, low)):
        return None, None, None
    distance_high = latest / high - 1.0 if high != 0 else None
    distance_low = latest / low - 1.0 if low != 0 else None
    position = (latest - low) / (high - low) if high != low else 0.5
    return distance_high, distance_low, position


def _recent_vs_prior_change(
    series: pd.Series,
    *,
    total_periods: int = 20,
    recent_periods: int = 5,
) -> float | None:
    if len(series) < total_periods:
        return None
    window = series.tail(total_periods).astype(float)
    recent = float(window.tail(recent_periods).mean())
    prior = float(window.iloc[:-recent_periods].mean())
    if not math.isfinite(recent) or not math.isfinite(prior) or prior == 0:
        return None
    return recent / prior - 1.0


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


def _latest_date(series: pd.Series) -> str | None:
    values = pd.to_datetime(series, errors="coerce").dropna()
    if values.empty:
        return None
    return values.max().strftime("%Y-%m-%d")


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
