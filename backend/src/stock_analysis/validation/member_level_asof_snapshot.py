"""Read-only member-level point-in-time feature snapshots for attribution."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from stock_analysis.data.point_in_time import slice_daily_as_of
from stock_analysis.data.raw_cache_catchup import stock_daily_adjusted_cache_path


DEFAULT_WINDOWS: tuple[tuple[str, int], ...] = (
    ("2024-01-31", 20),
    ("2024-04-30", 20),
    ("2024-07-31", 20),
    ("2024-10-31", 20),
)
SUMMARY_CSV_NAME = "member_level_asof_snapshot_2024.csv"
SUMMARY_JSON_NAME = "member_level_asof_snapshot_2024.json"
SUMMARY_MARKDOWN_NAME = "member_level_asof_snapshot_2024.md"

LIST_FIELD_MAP: dict[str, str] = {
    "high_confidence_candidates": "is_high_confidence",
    "trend_leaders": "is_trend_leader",
    "long_term_stable": "is_long_term_stable",
    "breakout_watch": "is_breakout_watch",
    "accumulation_watch": "is_accumulation_watch",
    "rebound_watch": "is_rebound_watch",
    "high_risk_active": "is_high_risk_active",
}
POSITIVE_LIST_IDS: tuple[str, ...] = tuple(
    item for item in LIST_FIELD_MAP if item != "high_risk_active"
)
RISK_LIST_IDS: tuple[str, ...] = ("high_risk_active",)

SCORE_FIELDS: tuple[str, ...] = (
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
)
FACTOR_FIELDS: tuple[str, ...] = (
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
)
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
FUTURE_LABEL_FIELDS: tuple[str, ...] = (
    "future_return",
    "benchmark_return",
    "future_excess_return",
    "outperformed_benchmark",
    "future_top_quantile",
    "max_drawdown_during_holding",
    "benchmark_data_quality",
)
UNAVAILABLE_EXTERNAL_FIELDS: tuple[str, ...] = (
    "theme_or_policy_catalyst",
    "restructuring_or_control_change_event",
    "fundamental_improvement",
    "industry_or_sector_attribution",
    "historical_listing_st_suspension_status",
)
DISCLAIMER = (
    "Research-only member-level as-of snapshot. Features use information "
    "available on or before each as-of date; future labels are attached only "
    "for explicit evaluation. This is not evidence of production improvement "
    "and changes no production logic."
)


@dataclass(frozen=True)
class MemberLevelSnapshotConfig:
    outputs_dir: str | Path = "outputs"
    cache_dir: str | Path = "data/cache/daily-use"
    provider: str = "baostock"
    windows: tuple[tuple[str, int], ...] = DEFAULT_WINDOWS


@dataclass
class MemberLevelSnapshotResult:
    frame: pd.DataFrame
    report: dict[str, Any]


def build_member_level_asof_snapshot(
    config: MemberLevelSnapshotConfig,
) -> MemberLevelSnapshotResult:
    outputs_dir = Path(config.outputs_dir)
    cache_path = stock_daily_adjusted_cache_path(
        config.cache_dir,
        config.provider,
    )
    frames: list[pd.DataFrame] = []
    windows: list[dict[str, Any]] = []
    excluded_windows: list[dict[str, Any]] = []
    source_files: set[str] = set()

    for as_of_date, horizon_days in config.windows:
        predictions_path = (
            outputs_dir
            / "validation"
            / f"walk_forward_predictions_{as_of_date}_{horizon_days}d.csv"
        )
        if not predictions_path.exists():
            excluded_windows.append(
                {
                    "as_of_date": as_of_date,
                    "horizon_days": horizon_days,
                    "status": "missing_predictions",
                    "missing_file": str(predictions_path),
                }
            )
            continue
        predictions = pd.read_csv(
            predictions_path,
            dtype={"symbol": str},
        )
        if "symbol" not in predictions.columns:
            excluded_windows.append(
                {
                    "as_of_date": as_of_date,
                    "horizon_days": horizon_days,
                    "status": "predictions_missing_symbol",
                    "missing_file": str(predictions_path),
                }
            )
            continue

        frame, window_status, paths = _build_window_frame(
            predictions,
            outputs_dir=outputs_dir,
            cache_path=cache_path,
            as_of_date=as_of_date,
            horizon_days=horizon_days,
        )
        frames.append(frame)
        windows.append(window_status)
        source_files.update(str(path) for path in paths)
        source_files.add(str(predictions_path))

    combined = (
        pd.concat(frames, ignore_index=True, sort=False)
        if frames
        else pd.DataFrame(columns=_snapshot_columns())
    )
    combined = _ordered_frame(combined)
    status = "ok"
    if combined.empty:
        status = "insufficient_data"
    elif excluded_windows or any(
        row["missing_daily_cache_count"] > 0 for row in windows
    ):
        status = "partial"

    report = _json_safe(
        {
            "summary": {
                "status": status,
                "research_only": True,
                "provider_access": False,
                "cache_fetch_executed": False,
                "labels_recomputed": False,
                "production_scoring_changed": False,
                "production_ranking_changed": False,
                "production_candidate_selection_changed": False,
                "production_recommendations_changed": False,
                "row_count": int(len(combined)),
                "included_window_count": len(windows),
                "excluded_window_count": len(excluded_windows),
                "local_cache_features_used": any(
                    row["technical_feature_row_count"] > 0 for row in windows
                ),
                "disclaimer": DISCLAIMER,
            },
            "schema": {
                "identity_fields": [
                    "as_of_date",
                    "horizon_days",
                    "symbol",
                    "data_quality",
                ],
                "point_in_time_metadata_fields": list(POINT_IN_TIME_FIELDS),
                "membership_fields": [
                    "captured_positive_lists",
                    "captured_risk_lists",
                    *LIST_FIELD_MAP.values(),
                ],
                "existing_score_fields": list(SCORE_FIELDS),
                "existing_factor_fields": list(FACTOR_FIELDS),
                "as_of_technical_feature_fields": list(
                    TECHNICAL_FEATURE_FIELDS
                ),
                "future_label_fields": list(FUTURE_LABEL_FIELDS),
                "missing_feature_field": "missing_feature_flags",
                "feature_label_boundary": (
                    "As-of features are computed first from rows with "
                    "trade_date <= as_of_date. Future labels are copied from "
                    "existing validation predictions only after feature "
                    "materialization."
                ),
            },
            "window_summary": windows,
            "excluded_windows": excluded_windows,
            "unavailable_external_fields": list(
                UNAVAILABLE_EXTERNAL_FIELDS
            ),
            "guardrails": [
                "No provider access, prewarm, workflow, or label recomputation.",
                "No future-return field is used to calculate an as-of feature.",
                "The 2024 answer-key cases must not be used to tune thresholds.",
                "Any future candidate hypothesis must be tested on unseen windows.",
                "No production scoring, ranking, candidate-list, or recommendation logic changed.",
            ],
            "source_files": sorted(source_files),
            "outputs": {},
        }
    )
    return MemberLevelSnapshotResult(frame=combined, report=report)


def write_member_level_asof_snapshot_outputs(
    result: MemberLevelSnapshotResult,
    outputs_dir: str | Path,
) -> dict[str, str]:
    experiments_dir = Path(outputs_dir) / "experiments"
    experiments_dir.mkdir(parents=True, exist_ok=True)
    csv_path = experiments_dir / SUMMARY_CSV_NAME
    json_path = experiments_dir / SUMMARY_JSON_NAME
    markdown_path = experiments_dir / SUMMARY_MARKDOWN_NAME
    paths = {
        "csv": str(csv_path),
        "json": str(json_path),
        "markdown": str(markdown_path),
    }
    result.frame.to_csv(csv_path, index=False, encoding="utf-8-sig")
    result.report["outputs"] = paths
    payload = {
        **result.report,
        "records": _json_safe(result.frame.to_dict(orient="records")),
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_member_level_asof_snapshot_markdown(result.report),
        encoding="utf-8",
    )
    return paths


def render_member_level_asof_snapshot_markdown(
    report: dict[str, Any],
) -> str:
    summary = report["summary"]
    lines = [
        "# Controlled Member-Level As-Of Feature Snapshot",
        "",
        str(summary["disclaimer"]),
        "",
        "## Guardrails",
        "",
    ]
    for item in report.get("guardrails", []):
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Window Coverage",
            "",
            "| As-of | Horizon | Predictions | Rows | Cache features | Missing cache | Future rows excluded |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in report.get("window_summary", []):
        lines.append(
            f"| {row['as_of_date']} | {row['horizon_days']} | "
            f"{row['prediction_count']} | {row['snapshot_row_count']} | "
            f"{row['technical_feature_row_count']} | "
            f"{row['missing_daily_cache_count']} | "
            f"{row['future_rows_excluded_count']} |"
        )
    schema = report["schema"]
    lines.extend(
        [
            "",
            "## Feature And Label Boundary",
            "",
            str(schema["feature_label_boundary"]),
            "",
            "### As-of technical features",
            "",
        ]
    )
    for field in schema["as_of_technical_feature_fields"]:
        lines.append(f"- `{field}`")
    lines.extend(["", "### Explicit future labels", ""])
    for field in schema["future_label_fields"]:
        lines.append(f"- `{field}`")
    lines.extend(["", "## Unavailable External Fields", ""])
    for field in report.get("unavailable_external_fields", []):
        lines.append(f"- `{field}`")
    lines.extend(
        [
            "",
            "## Interpretation Boundary",
            "",
            "- Snapshot fields support attribution and hypothesis design only.",
            "- They do not create or alter production candidate lists.",
            "- Same-period 2024 labels cannot establish improvement.",
            "- Future experiments require frozen definitions and unseen-window validation.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_window_frame(
    predictions: pd.DataFrame,
    *,
    outputs_dir: Path,
    cache_path: Path,
    as_of_date: str,
    horizon_days: int,
) -> tuple[pd.DataFrame, dict[str, Any], list[Path]]:
    base = predictions.drop_duplicates(subset=["symbol"], keep="first").copy()
    base["symbol"] = base["symbol"].astype(str)
    identity = pd.DataFrame(
        {
            "as_of_date": as_of_date,
            "horizon_days": horizon_days,
            "symbol": base["symbol"],
            "data_quality": _column_or_none(base, "data_quality"),
        }
    )

    labels = pd.DataFrame({"symbol": base["symbol"]})
    for field in FUTURE_LABEL_FIELDS:
        labels[field] = _column_or_none(base, field)

    factor_path = outputs_dir / "daily" / f"factors_{as_of_date}.csv"
    score_path = outputs_dir / "labels" / f"stock_labels_{as_of_date}.csv"
    feature_frame = identity.copy()
    feature_frame = _merge_available_columns(
        feature_frame,
        factor_path,
        FACTOR_FIELDS,
    )
    feature_frame = _merge_available_columns(
        feature_frame,
        score_path,
        SCORE_FIELDS,
    )

    membership, list_paths = _load_membership(
        outputs_dir,
        as_of_date,
    )
    membership_rows = [
        _membership_row(symbol, membership) for symbol in base["symbol"]
    ]
    feature_frame = pd.concat(
        [
            feature_frame.reset_index(drop=True),
            pd.DataFrame(membership_rows).reset_index(drop=True),
        ],
        axis=1,
    )

    technical_rows = [
        _technical_feature_row(
            cache_path / f"{symbol}.csv",
            symbol=symbol,
            as_of_date=as_of_date,
        )
        for symbol in base["symbol"]
    ]
    technical = pd.DataFrame(technical_rows)
    feature_frame = feature_frame.merge(
        technical,
        on="symbol",
        how="left",
        validate="one_to_one",
    )
    feature_frame["missing_feature_flags"] = feature_frame.apply(
        lambda row: _row_missing_flags(row, membership),
        axis=1,
    )

    # Labels are attached only after every as-of feature has been materialized.
    result = feature_frame.merge(
        labels,
        on="symbol",
        how="left",
        validate="one_to_one",
    )
    paths = [
        path
        for path in (factor_path, score_path, *list_paths)
        if path.exists()
    ]
    technical_count = int(
        result["latest_input_date"].notna().sum()
        if "latest_input_date" in result
        else 0
    )
    missing_cache_count = int(len(result) - technical_count)
    guard_values = result.loc[
        result["latest_input_date"].notna(),
        "leakage_guard_applied",
    ].tolist()
    return (
        result,
        {
            "as_of_date": as_of_date,
            "horizon_days": horizon_days,
            "prediction_count": int(len(base)),
            "snapshot_row_count": int(len(result)),
            "technical_feature_row_count": technical_count,
            "missing_daily_cache_count": missing_cache_count,
            "future_rows_excluded_count": int(
                pd.to_numeric(
                    result["future_rows_excluded_count"],
                    errors="coerce",
                )
                .fillna(0)
                .sum()
            ),
            "latest_input_date_max": _date_max(
                result["latest_input_date"]
            ),
            "leakage_guard_applied": (
                technical_count > 0
                and all(value is True for value in guard_values)
            ),
            "missing_membership_files": [
                str(path)
                for list_id, path in zip(LIST_FIELD_MAP, list_paths)
                if membership[list_id] is None
            ],
        },
        paths,
    )


def _merge_available_columns(
    frame: pd.DataFrame,
    path: Path,
    fields: tuple[str, ...],
) -> pd.DataFrame:
    result = frame.copy()
    if not path.exists():
        for field in fields:
            result[field] = None
        return result
    source = pd.read_csv(path, dtype={"symbol": str})
    if "symbol" not in source.columns:
        for field in fields:
            result[field] = None
        return result
    selected = ["symbol", *[field for field in fields if field in source]]
    source = source.loc[:, selected].drop_duplicates("symbol", keep="first")
    result = result.merge(source, on="symbol", how="left")
    for field in fields:
        if field not in result:
            result[field] = None
    return result


def _load_membership(
    outputs_dir: Path,
    as_of_date: str,
) -> tuple[dict[str, set[str] | None], list[Path]]:
    membership: dict[str, set[str] | None] = {}
    paths: list[Path] = []
    for list_id in LIST_FIELD_MAP:
        path = outputs_dir / "lists" / f"{list_id}_{as_of_date}.json"
        paths.append(path)
        if not path.exists():
            membership[list_id] = None
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            items = payload.get("items", []) if isinstance(payload, dict) else []
            membership[list_id] = {
                str(item.get("symbol", "")).strip()
                for item in items
                if isinstance(item, dict)
                and str(item.get("symbol", "")).strip()
            }
        except (OSError, ValueError):
            membership[list_id] = None
    return membership, paths


def _membership_row(
    symbol: str,
    membership: dict[str, set[str] | None],
) -> dict[str, Any]:
    row: dict[str, Any] = {}
    captured_positive: list[str] = []
    captured_risk: list[str] = []
    for list_id, field in LIST_FIELD_MAP.items():
        members = membership[list_id]
        row[field] = None if members is None else symbol in members
        if members is not None and symbol in members:
            if list_id in RISK_LIST_IDS:
                captured_risk.append(list_id)
            else:
                captured_positive.append(list_id)
    row["captured_positive_lists"] = ";".join(captured_positive)
    row["captured_risk_lists"] = ";".join(captured_risk)
    return row


def _technical_feature_row(
    csv_path: Path,
    *,
    symbol: str,
    as_of_date: str,
) -> dict[str, Any]:
    empty = {
        "symbol": symbol,
        **{field: None for field in TECHNICAL_FEATURE_FIELDS},
        **{field: None for field in POINT_IN_TIME_FIELDS},
        "_technical_missing_flags": [],
    }
    if not csv_path.exists():
        empty["_technical_missing_flags"] = ["missing_daily_cache"]
        return empty
    try:
        raw = pd.read_csv(csv_path, dtype={"symbol": str})
        sliced = slice_daily_as_of(raw, as_of_date)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        empty["_technical_missing_flags"] = [
            f"daily_cache_error:{type(exc).__name__}"
        ]
        return empty
    frame = sliced.frame.copy()
    if frame.empty:
        empty.update(_technical_diagnostics(sliced))
        empty["_technical_missing_flags"] = ["no_rows_on_or_before_as_of"]
        return empty
    frame["trade_date"] = pd.to_datetime(
        frame["trade_date"],
        errors="coerce",
    )
    frame = frame.sort_values("trade_date")
    price_column = "adj_close" if "adj_close" in frame else "close"
    if price_column not in frame:
        empty.update(_technical_diagnostics(sliced))
        empty["_technical_missing_flags"] = ["missing_price_column"]
        return empty
    price = pd.to_numeric(frame[price_column], errors="coerce").dropna()
    amount = pd.to_numeric(
        frame.get("amount", pd.Series(dtype=float)),
        errors="coerce",
    ).dropna()
    volume = pd.to_numeric(
        frame.get("volume", pd.Series(dtype=float)),
        errors="coerce",
    ).dropna()

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
    missing = [
        f"insufficient_history:{field}"
        for field, value in values.items()
        if value is None
    ]
    return {
        "symbol": symbol,
        **values,
        **_technical_diagnostics(sliced),
        "_technical_missing_flags": missing,
    }


def _technical_diagnostics(sliced: Any) -> dict[str, Any]:
    diagnostics = sliced.diagnostics()
    return {
        field: diagnostics.get(field) for field in POINT_IN_TIME_FIELDS
    }


def _row_missing_flags(
    row: pd.Series,
    membership: dict[str, set[str] | None],
) -> str:
    flags = list(row.get("_technical_missing_flags") or [])
    for list_id, members in membership.items():
        if members is None:
            flags.append(f"missing_list_membership:{list_id}")
    for field in SCORE_FIELDS:
        if _is_missing(row.get(field)):
            flags.append(f"missing_score:{field}")
    for field in FACTOR_FIELDS:
        if _is_missing(row.get(field)):
            flags.append(f"missing_factor:{field}")
    return ";".join(sorted(set(flags)))


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


def _snapshot_columns() -> list[str]:
    return [
        "as_of_date",
        "horizon_days",
        "symbol",
        "data_quality",
        *POINT_IN_TIME_FIELDS,
        "captured_positive_lists",
        "captured_risk_lists",
        *LIST_FIELD_MAP.values(),
        *SCORE_FIELDS,
        *FACTOR_FIELDS,
        *TECHNICAL_FEATURE_FIELDS,
        "missing_feature_flags",
        *FUTURE_LABEL_FIELDS,
    ]


def _ordered_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if "_technical_missing_flags" in result:
        result = result.drop(columns=["_technical_missing_flags"])
    for column in _snapshot_columns():
        if column not in result:
            result[column] = None
    return result.loc[:, _snapshot_columns()].sort_values(
        ["as_of_date", "symbol"],
        kind="stable",
    ).reset_index(drop=True)


def _column_or_none(frame: pd.DataFrame, field: str) -> pd.Series:
    if field in frame:
        return frame[field].reset_index(drop=True)
    return pd.Series([None] * len(frame), dtype=object)


def _date_max(series: pd.Series) -> str | None:
    values = pd.to_datetime(series, errors="coerce").dropna()
    if values.empty:
        return None
    return values.max().strftime("%Y-%m-%d")


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


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
