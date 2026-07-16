"""Point-in-time, local-cache-only Phase 4.2 feature matrix builder."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from stock_analysis.research.production_candidate_foundation import (
    load_baseline_manifest,
)


FEATURE_CONFIG_SCHEMA = "production-candidate-features-config-v1"
FEATURE_CONFIG_ID = "production-candidate-features"
FEATURE_CONFIG_VERSION = "phase4.2-v1"
FEATURE_SCHEMA_VERSION = "production_candidate_feature_matrix.v1"
FOUNDATION_ID = "production-candidate-research-foundation"
BASELINE_ID = "current-production-candidate-baseline"
BASELINE_VERSION = "production-candidate-baseline-v1"
BENCHMARK = "CSI300"
U3_DATES = {"2026-09-30", "2026-12-31"}
ALLOWED_RESEARCH_STATUSES = {
    "existing_production",
    "candidate_research_only",
    "risk_feature_research_only",
    "unavailable",
    "requires_external_data",
    "rejected_due_to_leakage",
}
PRIVILEGED_FEATURE_NAMES = {
    "winner",
    "loser",
    "right_tail",
    "severe_drawdown",
    "valid_label",
    "missing_label_reason",
}
CONSUMED_DATES = {
    "2024-01-31",
    "2024-04-30",
    "2024-07-31",
    "2024-10-31",
    "2024-02-29",
    "2024-05-31",
    "2024-08-30",
    "2024-11-29",
    "2025-02-28",
    "2025-05-30",
    "2025-08-29",
    "2025-11-28",
    "2026-01-30",
    "2026-03-31",
    "2026-04-30",
}
REQUIRED_CACHE_FIELDS = {
    "symbol",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "adj_close",
    "source",
}
IDENTITY_COLUMNS = [
    "dataset_version",
    "feature_schema_version",
    "feature_config_sha256",
    "foundation_id",
    "production_baseline_id",
    "symbol",
    "as_of_date",
    "latest_input_date",
    "source_snapshot_id",
    "universe_id",
    "benchmark",
    "data_role",
    "provider_access",
    "labels_joined",
    "leakage_guard_applied",
    "production_change",
    "limit_used",
    "observation_count",
    "row_status",
    "missing_reason",
]
BASELINE_FACTOR_IDS = [
    "momentum_20d",
    "momentum_60d",
    "momentum_120d",
    "above_ma20",
    "above_ma60",
    "ma_bullish_alignment",
    "rs_20d",
    "rs_60d",
    "rs_120d",
    "volatility_20d",
    "volatility_60d",
    "max_drawdown_20d",
    "max_drawdown_60d",
    "avg_amount_20d",
    "avg_amount_60d",
    "avg_volume_20d",
    "avg_volume_60d",
]
BASELINE_OUTPUT_IDS = [
    "total_score",
    "momentum_score",
    "trend_score",
    "relative_strength_score",
    "risk_score",
    "liquidity_score",
    "confidence",
    "risk_flags",
    "warnings",
]
COMPOSITE_FEATURES = {
    "mean_reversion_opportunity_score",
    "left_tail_risk_score",
    "right_tail_activity_score",
    "low_position_revaluation_score",
    "trend_acceleration_score",
    "crowding_risk_score",
    "right_tail_opportunity_score",
    "false_breakout_risk_score",
}


class ProductionCandidateFeatureMatrixError(ValueError):
    """Structured fail-closed feature builder error."""

    def __init__(
        self,
        status: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.details = dict(details or {})


@dataclass(frozen=True)
class FeatureMatrixResult:
    frame: pd.DataFrame
    report: dict[str, Any]


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_feature_config(path: str | Path) -> dict[str, Any]:
    payload = _read_json_object(path)
    validate_feature_config(payload)
    return payload


def validate_feature_config(payload: Mapping[str, Any]) -> None:
    expected = {
        "schema_version": FEATURE_CONFIG_SCHEMA,
        "feature_config_id": FEATURE_CONFIG_ID,
        "feature_config_version": FEATURE_CONFIG_VERSION,
        "foundation_id": FOUNDATION_ID,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "production_baseline_id": BASELINE_ID,
        "production_baseline_version": BASELINE_VERSION,
        "benchmark": BENCHMARK,
        "adjusted_price_required": True,
        "close_fallback_allowed": False,
        "provider_access": False,
        "labels_joined": False,
        "production_change": False,
        "effectiveness_status": "not_evaluated",
        "results_are_effectiveness_evidence": False,
    }
    _require_values(payload, expected, "Feature config identity or safety drifted.")
    definitions = payload.get("feature_definitions")
    if not isinstance(definitions, list) or not definitions:
        _fail("invalid_execution", "Feature definitions must be non-empty.")
    ids: list[str] = []
    required = {
        "feature_id",
        "feature_family",
        "source_fields",
        "minimum_observation_count",
        "formula_reference",
        "point_in_time_rule",
        "missing_value_policy",
        "direction_hypothesis",
        "data_type",
        "cross_sectional_transform",
        "research_status",
        "implementation_status",
        "leakage_risk",
        "inherited_evidence",
    }
    forbidden_patterns = [
        str(item).lower() for item in payload.get("forbidden_feature_patterns", [])
    ]
    forbidden_cohorts = {
        str(item).lower()
        for item in payload.get("forbidden_h1h5_boolean_inputs", [])
    }
    for definition in definitions:
        if not isinstance(definition, Mapping):
            _fail("invalid_execution", "Feature definition must be an object.")
        missing = sorted(required - set(definition))
        if missing:
            _fail(
                "invalid_execution",
                "Feature definition is incomplete.",
                missing_fields=missing,
            )
        feature_id = str(definition["feature_id"]).strip()
        ids.append(feature_id)
        status = str(definition["research_status"])
        if status not in ALLOWED_RESEARCH_STATUSES:
            _fail("invalid_execution", "Unknown feature research status.")
        if (
            status != "existing_production"
            and definition.get("inherited_evidence") is not False
        ):
            _fail(
                "invalid_execution",
                "New Phase 4 feature cannot inherit effectiveness evidence.",
                feature_id=feature_id,
            )
        searchable = [
            feature_id.lower(),
            *[str(item).lower() for item in definition["source_fields"]],
        ]
        if feature_id.lower() in PRIVILEGED_FEATURE_NAMES:
            _fail(
                "invalid_execution",
                "Outcome label cannot be a feature.",
                feature_id=feature_id,
            )
        found = sorted(
            {
                pattern
                for value in searchable
                for pattern in forbidden_patterns
                if pattern in value
            }
        )
        cohort_found = sorted(set(searchable) & forbidden_cohorts)
        if found or cohort_found:
            _fail(
                "invalid_execution",
                "Feature declares future, outcome, label, or H1-H5 membership input.",
                feature_id=feature_id,
                forbidden_patterns=found,
                forbidden_cohort_inputs=cohort_found,
            )
        if "<= as_of_date" not in str(definition["point_in_time_rule"]):
            _fail(
                "invalid_execution",
                "Feature point-in-time rule is incomplete.",
                feature_id=feature_id,
            )
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        _fail(
            "invalid_execution",
            "Duplicate feature IDs are forbidden.",
            duplicate_feature_ids=duplicates,
        )
    if payload.get("output_feature_columns") != ids:
        _fail(
            "invalid_execution",
            "Output feature columns must exactly follow registry order.",
        )
    if payload.get("output_identity_columns") != IDENTITY_COLUMNS:
        _fail("invalid_execution", "Output identity columns drifted.")


def build_feature_matrix(
    *,
    as_of_date: str,
    cache_dir: str | Path,
    feature_config_path: str | Path,
    baseline_config_path: str | Path,
    baseline_snapshot_dir: str | Path | None = None,
    limit: int | None = None,
) -> FeatureMatrixResult:
    as_of = _normalize_date(as_of_date)
    if as_of in U3_DATES:
        _fail("invalid_execution", "Prospective U3 dates are protected.")
    if limit is not None and limit <= 0:
        _fail("invalid_execution", "limit must be positive.")

    config = load_feature_config(feature_config_path)
    baseline = load_baseline_manifest(baseline_config_path)
    baseline_sha = sha256_file(baseline_config_path)
    if baseline_sha != config.get("production_baseline_sha256"):
        _fail("invalid_execution", "Baseline config digest mismatch.")
    if baseline["baseline_id"] != config["production_baseline_id"]:
        _fail("invalid_execution", "Baseline identity mismatch.")
    feature_sha = sha256_file(feature_config_path)

    stock_dir = _resolve_stock_cache_dir(cache_dir)
    benchmark = _load_benchmark(cache_dir, as_of)
    benchmark_dates = benchmark["trade_date"].tolist()
    cache_files = [
        path
        for path in sorted(stock_dir.glob("*.csv"), key=lambda item: item.name)
        if path.stem not in {"sh.000300", "sz.399300"}
    ]
    if not cache_files:
        _fail("invalid_execution", "No local adjusted stock cache files found.")
    selected = cache_files[:limit] if limit is not None else cache_files

    factor_map, candidate_map = _load_baseline_snapshots(
        baseline_snapshot_dir, as_of
    )
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for path in selected:
        row = _build_symbol_row(
            path,
            as_of=as_of,
            benchmark=benchmark,
            benchmark_dates=benchmark_dates,
            config=config,
            feature_sha=feature_sha,
            limit=limit,
            factor_map=factor_map,
            candidate_map=candidate_map,
            universe_id=(
                f"local-adjusted-cache-sorted-limit-{limit}"
                if limit is not None
                else "local-adjusted-cache-all"
            ),
        )
        key = (str(row["symbol"]), as_of)
        if key in seen:
            _fail(
                "invalid_execution",
                "Duplicate symbol/as_of_date row detected.",
                row_identity=key,
            )
        seen.add(key)
        rows.append(row)

    frame = pd.DataFrame(rows)
    if frame.empty:
        _fail("insufficient_data", "Feature matrix is empty.")
    if frame["as_of_date"].nunique() != 1:
        _fail(
            "invalid_execution",
            "Cross-sectional transforms require exactly one as-of date.",
        )
    frame = _add_cross_sectional_composites(frame)
    output_columns = [*IDENTITY_COLUMNS, *config["output_feature_columns"]]
    unexpected = sorted(set(frame.columns) - set(output_columns))
    missing = sorted(set(output_columns) - set(frame.columns))
    if unexpected or missing:
        _fail(
            "invalid_execution",
            "Output contains unregistered or missing feature columns.",
            unexpected_columns=unexpected,
            missing_columns=missing,
        )
    frame = frame.loc[:, output_columns].sort_values(
        ["symbol", "as_of_date"], kind="mergesort"
    ).reset_index(drop=True)
    if frame.duplicated(["symbol", "as_of_date"]).any():
        _fail("invalid_execution", "Duplicate output row identity detected.")
    parsed_latest = pd.to_datetime(frame["latest_input_date"], errors="coerce")
    if (parsed_latest > pd.Timestamp(as_of)).any():
        _fail("invalid_execution", "latest_input_date exceeds as_of_date.")

    feature_columns = config["output_feature_columns"]
    missing_counts = {
        column: int(frame[column].isna().sum())
        for column in feature_columns
    }
    family_by_id = {
        item["feature_id"]: item["feature_family"]
        for item in config["feature_definitions"]
    }
    family_coverage = {}
    for family in config["feature_families"]:
        columns = [
            feature_id
            for feature_id, assigned in family_by_id.items()
            if assigned == family
        ]
        total = len(frame) * len(columns)
        present = sum(int(frame[column].notna().sum()) for column in columns)
        family_coverage[family] = (
            None if total == 0 else round(present / total, 6)
        )
    report = {
        "status": "safe",
        "as_of_date": as_of,
        "data_role": _data_role(as_of),
        "input_symbol_count": len(selected),
        "output_feature_row_count": len(frame),
        "implemented_feature_count": len(feature_columns),
        "duplicate_count": 0,
        "latest_input_date_max": str(frame["latest_input_date"].max()),
        "limit_used": limit is not None,
        "limit": limit,
        "missing_value_counts": missing_counts,
        "feature_family_coverage": family_coverage,
        "provider_access": False,
        "labels_joined": False,
        "production_change": False,
        "results_are_effectiveness_evidence": False,
        "dry_run": True,
        "outputs_written": False,
    }
    return FeatureMatrixResult(frame=frame, report=report)


def write_feature_matrix(
    result: FeatureMatrixResult,
    *,
    outputs_dir: str | Path,
) -> dict[str, str]:
    output_dir = Path(outputs_dir)
    lower_parts = {part.lower() for part in output_dir.parts}
    if "daily" in lower_parts or "validation" in lower_parts or "lists" in lower_parts:
        _fail("invalid_execution", "Feature output cannot target production or validation paths.")
    output_dir.mkdir(parents=True, exist_ok=True)
    as_of = str(result.report["as_of_date"])
    csv_path = output_dir / f"production_candidate_features_{as_of}.csv"
    json_path = output_dir / f"production_candidate_features_{as_of}.json"
    result.frame.to_csv(csv_path, index=False, encoding="utf-8")
    payload = {
        "metadata": {
            **result.report,
            "dry_run": False,
            "outputs_written": True,
        },
        "records": _json_records(result.frame),
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"csv": str(csv_path), "json": str(json_path)}


def _build_symbol_row(
    path: Path,
    *,
    as_of: str,
    benchmark: pd.DataFrame,
    benchmark_dates: list[str],
    config: Mapping[str, Any],
    feature_sha: str,
    limit: int | None,
    factor_map: Mapping[str, Mapping[str, Any]],
    candidate_map: Mapping[str, Mapping[str, Any]],
    universe_id: str,
) -> dict[str, Any]:
    frame = pd.read_csv(path)
    missing_fields = sorted(REQUIRED_CACHE_FIELDS - set(frame.columns))
    if missing_fields:
        _fail(
            "invalid_execution",
            "Adjusted cache schema is incomplete.",
            path=str(path),
            missing_fields=missing_fields,
        )
    frame = frame.loc[:, list(config["required_local_cache_fields"])].copy()
    symbols = set(frame["symbol"].dropna().astype(str))
    if len(symbols) != 1:
        _fail("invalid_execution", "Cache file must contain exactly one symbol.")
    symbol = next(iter(symbols))
    frame["trade_date"] = pd.to_datetime(
        frame["trade_date"], errors="coerce"
    )
    if frame["trade_date"].isna().any():
        _fail("invalid_execution", "Cache contains malformed trade_date.")
    if frame.duplicated(["symbol", "trade_date"]).any():
        _fail("invalid_execution", "Duplicate cache symbol/date rows detected.")
    frame = frame[frame["trade_date"] <= pd.Timestamp(as_of)].sort_values(
        "trade_date"
    )
    for column in ["open", "high", "low", "close", "volume", "amount", "adj_close"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    latest = "" if frame.empty else frame["trade_date"].iloc[-1].strftime("%Y-%m-%d")
    base = {
        "dataset_version": config["dataset_version"],
        "feature_schema_version": config["feature_schema_version"],
        "feature_config_sha256": feature_sha,
        "foundation_id": config["foundation_id"],
        "production_baseline_id": config["production_baseline_id"],
        "symbol": symbol,
        "as_of_date": as_of,
        "latest_input_date": latest,
        "source_snapshot_id": f"local-adjusted-cache:{path.name}:{as_of}",
        "universe_id": universe_id,
        "benchmark": config["benchmark"],
        "data_role": _data_role(as_of),
        "provider_access": False,
        "labels_joined": False,
        "leakage_guard_applied": True,
        "production_change": False,
        "limit_used": limit is not None,
        "observation_count": int(len(frame)),
        "row_status": "ok",
        "missing_reason": "",
    }
    values = {feature_id: np.nan for feature_id in config["output_feature_columns"]}
    values.update(_calculate_raw_features(frame, benchmark, benchmark_dates))
    factor = factor_map.get(symbol, {})
    candidate = candidate_map.get(symbol, {})
    for feature_id in BASELINE_FACTOR_IDS:
        if feature_id in factor and not pd.isna(factor[feature_id]):
            values[feature_id] = factor[feature_id]
    for feature_id in BASELINE_OUTPUT_IDS:
        if feature_id in candidate and not pd.isna(candidate[feature_id]):
            values[feature_id] = candidate[feature_id]
    values["eligibility_status"] = (
        "production_factor_snapshot_present"
        if factor
        else "baseline_snapshot_not_available_for_symbol"
    )

    if frame.empty:
        base["row_status"] = "insufficient_data"
        base["missing_reason"] = "no_rows_on_or_before_as_of_date"
        values["tradability_status"] = "no_local_rows"
        values["data_quality_status"] = "insufficient"
    elif frame["adj_close"].isna().any() or (frame["adj_close"] <= 0).any():
        base["row_status"] = "invalid_data"
        base["missing_reason"] = "invalid_adjusted_price"
        values["tradability_status"] = "invalid_adjusted_price"
        values["data_quality_status"] = "invalid_adjusted_price"
    elif len(frame) < 121:
        base["row_status"] = "partial"
        base["missing_reason"] = "insufficient_maximum_121_bar_lookback"
        values["tradability_status"] = "price_data_available"
        values["data_quality_status"] = "insufficient_lookback"
    else:
        values["tradability_status"] = "price_data_available"
        values["data_quality_status"] = "ok"
    return {**base, **values}


def _calculate_raw_features(
    frame: pd.DataFrame,
    benchmark: pd.DataFrame,
    benchmark_dates: list[str],
) -> dict[str, Any]:
    if frame.empty:
        return {}
    price = frame["adj_close"].astype(float)
    volume = frame["volume"].astype(float)
    amount = frame["amount"].astype(float)
    returns = price.pct_change()
    result: dict[str, Any] = {}

    def enough(n: int) -> bool:
        return len(frame) >= n

    def ret(intervals: int) -> float:
        return float(price.iloc[-1] / price.iloc[-intervals - 1] - 1) if enough(intervals + 1) else np.nan

    def mean(series: pd.Series, n: int) -> float:
        return float(series.tail(n).mean()) if enough(n) else np.nan

    def volatility(n: int) -> float:
        return float(returns.tail(n).std(ddof=1)) if enough(n + 1) else np.nan

    def max_dd(n: int) -> float:
        if not enough(n):
            return np.nan
        sample = price.tail(n)
        return float((sample / sample.cummax() - 1).min())

    result.update(
        {
            "return_5d": ret(5),
            "return_20d": ret(20),
            "return_60d": ret(60),
            "momentum_20d": ret(20),
            "momentum_60d": ret(60),
            "momentum_120d": ret(120),
            "realized_volatility_20": volatility(20),
            "realized_volatility_60": volatility(60),
            "volatility_20d": volatility(20),
            "volatility_60d": volatility(60),
            "max_drawdown_20d": max_dd(20),
            "max_drawdown_60d": max_dd(60),
            "avg_amount_20d": mean(amount, 20),
            "avg_amount_60d": mean(amount, 60),
            "avg_volume_20d": mean(volume, 20),
            "avg_volume_60d": mean(volume, 60),
            "average_amount_5": mean(amount, 5),
            "average_amount_20": mean(amount, 20),
        }
    )
    for n in [5, 20, 60]:
        ma = mean(price, n)
        result[f"deviation_from_ma{n}"] = (
            float(price.iloc[-1] / ma - 1) if np.isfinite(ma) and ma > 0 else np.nan
        )
    result["distance_to_ma20"] = result["deviation_from_ma20"]
    result["distance_to_ma60"] = result["deviation_from_ma60"]
    ma5, ma20, ma60 = mean(price, 5), mean(price, 20), mean(price, 60)
    result["above_ma20"] = bool(price.iloc[-1] > ma20) if np.isfinite(ma20) else np.nan
    result["above_ma60"] = bool(price.iloc[-1] > ma60) if np.isfinite(ma60) else np.nan
    result["ma_bullish_alignment"] = (
        bool(ma5 > ma20 > ma60)
        if all(np.isfinite(item) for item in [ma5, ma20, ma60])
        else np.nan
    )
    align_values = [result["above_ma20"], result["above_ma60"], result["ma_bullish_alignment"]]
    result["ma_alignment_score"] = (
        float(np.mean(align_values))
        if not any(pd.isna(item) for item in align_values)
        else np.nan
    )
    result["trend_slope_20"] = _log_slope(price, 20)
    result["trend_slope_60"] = _log_slope(price, 60)
    result["trend_acceleration"] = (
        float(price.iloc[-1] / price.iloc[-21] - 1 - (price.iloc[-21] / price.iloc[-41] - 1))
        if enough(41)
        else np.nan
    )
    result["trend_persistence_20"] = (
        float((returns.tail(20) > 0).mean()) if enough(21) else np.nan
    )
    result["trend_smoothness_20"] = _smoothness(price, 20)
    result["relative_volume_5_20"] = _safe_ratio(mean(volume, 5), mean(volume, 20))
    result["relative_amount_5_20"] = _safe_ratio(mean(amount, 5), mean(amount, 20))
    result["volume_persistence_20"] = (
        float((volume.tail(20) > volume.iloc[-40:-20].mean()).mean())
        if enough(40)
        else np.nan
    )
    result["amount_expansion"] = (
        _safe_ratio(mean(amount, 5), float(amount.iloc[-25:-5].mean())) - 1
        if enough(25)
        else np.nan
    )
    if enough(21):
        vol_change = volume.pct_change().tail(20)
        result["price_volume_agreement"] = float(
            (np.sign(returns.tail(20)) * np.sign(vol_change)).mean()
        )
    else:
        result["price_volume_agreement"] = np.nan
    result["abnormal_volume_without_price_confirmation"] = (
        max(float(result["relative_volume_5_20"]) - 1, 0)
        * float(result["return_5d"] <= 0)
        if np.isfinite(result["relative_volume_5_20"])
        and np.isfinite(result["return_5d"])
        else np.nan
    )
    for n in [20, 60]:
        if enough(n):
            sample = price.tail(n)
            high = float(sample.max())
            low = float(sample.min())
            result[f"distance_from_high_{n}"] = float(price.iloc[-1] / high - 1)
            result[f"distance_from_low_{n}"] = float(price.iloc[-1] / low - 1)
            result[f"drawdown_{n}"] = result[f"distance_from_high_{n}"]
        else:
            for prefix in ["distance_from_high", "distance_from_low", "drawdown"]:
                result[f"{prefix}_{n}"] = np.nan
    result["recovery_strength_5"] = (
        float(price.iloc[-1] / price.tail(20).min() - 1) if enough(20) else np.nan
    )
    result["recovery_strength_20"] = (
        float(price.iloc[-1] / price.tail(60).min() - 1) if enough(60) else np.nan
    )
    if enough(60):
        sample = price.tail(60)
        span = float(sample.max() - sample.min())
        position = 0.5 if span == 0 else float((price.iloc[-1] - sample.min()) / span)
        result["low_position_score"] = float(np.clip(1 - position, 0, 1))
    else:
        result["low_position_score"] = np.nan
    result["return_zscore_20"] = _latest_zscore(returns, 20)
    result["return_zscore_60"] = _latest_zscore(returns, 60)
    result["volatility_adjusted_deviation_20"] = _safe_ratio(
        result["deviation_from_ma20"], result["realized_volatility_20"]
    )
    result["recent_drawdown_score"] = (
        -float(result["drawdown_20"]) if np.isfinite(result["drawdown_20"]) else np.nan
    )
    result["oversold_proxy"] = (
        max(-float(result["return_zscore_20"]), 0)
        if np.isfinite(result["return_zscore_20"])
        else np.nan
    )
    result["rebound_confirmation"] = (
        max(float(result["return_5d"]), 0)
        * float(np.clip(result["relative_volume_5_20"], 0, 2))
        if np.isfinite(result["return_5d"])
        and np.isfinite(result["relative_volume_5_20"])
        else np.nan
    )
    neg = returns.tail(20)
    neg = neg[neg < 0]
    result["downside_volatility_20"] = (
        float(neg.std(ddof=1)) if len(neg) >= 2 else (0.0 if enough(21) else np.nan)
    )
    trailing_std = returns.tail(60).std(ddof=1) if enough(61) else np.nan
    result["large_down_move_frequency_20"] = (
        float((returns.tail(20) < -2 * trailing_std).mean())
        if np.isfinite(trailing_std) and trailing_std > 0
        else np.nan
    )
    result["large_up_move_frequency_20"] = (
        float((returns.tail(20) > 2 * trailing_std).mean())
        if np.isfinite(trailing_std) and trailing_std > 0
        else np.nan
    )
    result["amount_stability"] = _stability(amount, 20)
    result["non_positive_price_warning"] = bool(
        (frame[["open", "high", "low", "close", "adj_close"]] <= 0).any().any()
    )
    result["low_liquidity_warning"] = (
        bool(result["average_amount_20"] < 20_000_000)
        if np.isfinite(result["average_amount_20"])
        else np.nan
    )
    observed = set(frame["trade_date"].dt.strftime("%Y-%m-%d"))
    relevant = benchmark_dates[-60:]
    result["missing_bar_rate"] = (
        float(1 - len(observed.intersection(relevant)) / len(relevant))
        if relevant
        else np.nan
    )
    result.update(_relative_strength_features(price, frame, benchmark))
    return result


def _add_cross_sectional_composites(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    rank = lambda column, higher=True: pd.to_numeric(
        result[column], errors="coerce"
    ).rank(method="average", pct=True, ascending=higher)
    result["mean_reversion_opportunity_score"] = pd.concat(
        [
            rank("oversold_proxy"),
            rank("recent_drawdown_score"),
            rank("rebound_confirmation"),
            rank("average_amount_20"),
        ],
        axis=1,
    ).mean(axis=1, skipna=False)
    result["left_tail_risk_score"] = pd.concat(
        [rank("downside_volatility_20"), rank("large_down_move_frequency_20")],
        axis=1,
    ).mean(axis=1, skipna=False)
    result["right_tail_activity_score"] = pd.concat(
        [rank("large_up_move_frequency_20"), rank("return_20d")],
        axis=1,
    ).mean(axis=1, skipna=False)
    result["low_position_revaluation_score"] = pd.concat(
        [rank("low_position_score"), rank("recovery_strength_20"), rank("relative_amount_5_20")],
        axis=1,
    ).mean(axis=1, skipna=False)
    result["trend_acceleration_score"] = pd.concat(
        [rank("trend_acceleration"), rank("trend_persistence_20"), rank("trend_smoothness_20")],
        axis=1,
    ).mean(axis=1, skipna=False)
    result["crowding_risk_score"] = pd.concat(
        [rank("distance_from_high_60"), rank("relative_volume_5_20"), rank("realized_volatility_20")],
        axis=1,
    ).mean(axis=1, skipna=False)
    result["right_tail_opportunity_score"] = pd.concat(
        [rank("right_tail_activity_score"), rank("trend_acceleration_score"), rank("amount_expansion")],
        axis=1,
    ).mean(axis=1, skipna=False)
    result["false_breakout_risk_score"] = pd.concat(
        [
            rank("distance_from_high_60"),
            rank("abnormal_volume_without_price_confirmation"),
            rank("trend_acceleration", higher=False),
        ],
        axis=1,
    ).mean(axis=1, skipna=False)
    return result


def _relative_strength_features(
    price: pd.Series,
    stock: pd.DataFrame,
    benchmark: pd.DataFrame,
) -> dict[str, float]:
    result = {}
    stock_by_date = pd.Series(
        price.values,
        index=stock["trade_date"].dt.strftime("%Y-%m-%d"),
    )
    benchmark_by_date = benchmark.set_index("trade_date")["adj_close"]
    common = pd.concat(
        [stock_by_date.rename("stock"), benchmark_by_date.rename("benchmark")],
        axis=1,
        join="inner",
    ).dropna()
    for n in [20, 60, 120]:
        key = f"rs_{n}d"
        if len(common) >= n + 1:
            stock_ret = common["stock"].iloc[-1] / common["stock"].iloc[-n - 1] - 1
            bench_ret = common["benchmark"].iloc[-1] / common["benchmark"].iloc[-n - 1] - 1
            result[key] = float(stock_ret - bench_ret)
        else:
            result[key] = np.nan
    return result


def _load_benchmark(cache_dir: str | Path, as_of: str) -> pd.DataFrame:
    root = Path(cache_dir)
    candidates = [
        root / "baostock" / "stock_daily" / "adjusted" / "sz.399300.csv",
        root / "baostock" / "stock_daily" / "adjusted" / "sh.000300.csv",
        root / "baostock" / "index_daily" / "raw" / "CSI300.csv",
    ]
    path = next((item for item in candidates if item.is_file()), None)
    if path is None:
        _fail("invalid_execution", "CSI300 local cache is missing.")
    frame = pd.read_csv(path)
    if "trade_date" not in frame or "adj_close" not in frame:
        _fail("invalid_execution", "CSI300 cache schema is incomplete.")
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce")
    frame["adj_close"] = pd.to_numeric(frame["adj_close"], errors="coerce")
    frame = frame.dropna(subset=["trade_date", "adj_close"]).sort_values("trade_date")
    if frame.empty or pd.Timestamp(as_of) > frame["trade_date"].max():
        _fail(
            "invalid_execution",
            "as_of_date is later than local benchmark cache coverage.",
        )
    frame = frame[frame["trade_date"] <= pd.Timestamp(as_of)].copy()
    frame["trade_date"] = frame["trade_date"].dt.strftime("%Y-%m-%d")
    return frame.loc[:, ["trade_date", "adj_close"]].drop_duplicates("trade_date")


def _resolve_stock_cache_dir(cache_dir: str | Path) -> Path:
    root = Path(cache_dir)
    candidate = root / "baostock" / "stock_daily" / "adjusted"
    if candidate.is_dir():
        return candidate
    if root.is_dir() and any(root.glob("*.csv")):
        return root
    _fail("invalid_execution", "Adjusted stock cache directory is missing.")


def _load_baseline_snapshots(
    directory: str | Path | None,
    as_of: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    if directory is None:
        return {}, {}
    root = Path(directory)
    factors = _read_optional_rows(root / f"factors_{as_of}.csv")
    candidates = _read_optional_rows(root / f"candidates_{as_of}.csv")
    return _index_records(factors), _index_records(candidates)


def _read_optional_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    frame = pd.read_csv(path)
    if "as_of_date" in frame and set(frame["as_of_date"].astype(str)) != {path.stem[-10:]}:
        _fail("invalid_execution", "Baseline snapshot contains mixed or wrong date.")
    return frame.to_dict(orient="records")


def _index_records(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {}
    for row in records:
        symbol = str(row.get("symbol", ""))
        if symbol in result:
            _fail("invalid_execution", "Duplicate baseline snapshot symbol.")
        result[symbol] = row
    return result


def _log_slope(price: pd.Series, n: int) -> float:
    if len(price) < n or (price.tail(n) <= 0).any():
        return np.nan
    values = np.log(price.tail(n).to_numpy(dtype=float))
    return float(np.polyfit(np.arange(n, dtype=float), values, 1)[0])


def _smoothness(price: pd.Series, n: int) -> float:
    if len(price) < n + 1:
        return np.nan
    sample = price.tail(n + 1)
    denominator = float(sample.diff().abs().sum())
    return 0.0 if denominator == 0 else float(abs(sample.iloc[-1] - sample.iloc[0]) / denominator)


def _latest_zscore(returns: pd.Series, n: int) -> float:
    if len(returns.dropna()) < n:
        return np.nan
    sample = returns.dropna().tail(n)
    std = float(sample.std(ddof=1))
    return 0.0 if std == 0 else float((sample.iloc[-1] - sample.mean()) / std)


def _stability(series: pd.Series, n: int) -> float:
    if len(series) < n:
        return np.nan
    sample = series.tail(n)
    mean = float(sample.mean())
    if mean == 0 or not np.isfinite(mean):
        return np.nan
    return float(np.clip(1 - float(sample.std(ddof=1)) / abs(mean), 0, 1))


def _safe_ratio(numerator: Any, denominator: Any) -> float:
    try:
        a, b = float(numerator), float(denominator)
    except (TypeError, ValueError):
        return np.nan
    return np.nan if not np.isfinite(a) or not np.isfinite(b) or b == 0 else float(a / b)


def _data_role(as_of: str) -> str:
    return "consumed_development_smoke_only" if as_of in CONSUMED_DATES else "research_only_unclassified_not_holdout"


def _normalize_date(value: str) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        _fail("invalid_execution", "as_of_date is invalid.")
    return parsed.strftime("%Y-%m-%d")


def _read_json_object(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProductionCandidateFeatureMatrixError(
            "invalid_execution",
            "Feature config is missing or invalid JSON.",
        ) from exc
    if not isinstance(value, dict):
        _fail("invalid_execution", "Feature config must be a JSON object.")
    return value


def _json_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    clean = frame.astype(object).where(pd.notna(frame), None)
    return clean.to_dict(orient="records")


def _require_values(actual: Mapping[str, Any], expected: Mapping[str, Any], message: str) -> None:
    mismatches = {
        key: {"expected": value, "actual": actual.get(key)}
        for key, value in expected.items()
        if actual.get(key) != value
    }
    if mismatches:
        _fail("invalid_execution", message, mismatches=mismatches)


def _fail(status: str, message: str, **details: Any) -> None:
    raise ProductionCandidateFeatureMatrixError(status, message, details=details)
