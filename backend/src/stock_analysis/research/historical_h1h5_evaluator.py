"""Fail-closed evaluator framework for frozen historical H1-H5 cohorts.

This module does not generate labels, fetch provider data, build cohorts, or
open any implicit validation source. A caller must provide a digest-verified
label-free cohort JSON and an explicit precomputed label JSON.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping

import pandas as pd


VALIDATION_ID = "h1h5-historical-sealed-v1"
EVIDENCE_LEVEL = "historical_sealed_not_prospective"
EXPECTED_HORIZON_DAYS = 20
EXPECTED_BENCHMARK = "CSI300"
MINIMUM_VALID_LABELS_PER_COHORT = 20
PRIMARY_WINDOWS: tuple[str, ...] = (
    "2026-01-30",
    "2026-03-31",
    "2026-04-30",
)
EXCLUDED_WINDOWS: frozenset[str] = frozenset(
    {
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
        "2026-09-30",
        "2026-12-31",
    }
)
COHORT_ROLES: dict[str, str] = {
    "low_position_revaluation_watch": "opportunity_observation",
    "trend_acceleration_with_crowding_guard": "opportunity_observation",
    "right_tail_opportunity_watch": "opportunity_observation",
    "high_position_crowding_risk": "risk_annotation",
    "false_breakout_risk": "risk_annotation",
}
RESULT_STATUSES: tuple[str, ...] = (
    "supported_research_only",
    "mixed_research_only",
    "not_confirmed",
    "underpowered",
    "invalid_execution",
)
REQUIRED_OUTPUT_FIELDS: tuple[str, ...] = (
    "validation_id",
    "evidence_level",
    "as_of_date",
    "horizon",
    "benchmark",
    "cohort_name",
    "member_count",
    "valid_label_count",
    "winner_count",
    "loser_count",
    "winner_capture",
    "loser_contamination",
    "severe_drawdown_incidence",
    "benchmark_excess_return",
    "right_tail_retention",
    "false_warning_rate",
    "coverage",
    "empty_cohort_rate",
    "underpowered",
    "result_status",
    "caveats",
    "labels_joined_by_evaluator",
    "builder_labels_joined",
    "production_change",
)
REQUIRED_LABEL_FIELDS: tuple[str, ...] = (
    "symbol",
    "as_of_date",
    "horizon_days",
    "benchmark",
    "data_quality",
    "future_return",
    "benchmark_future_return",
    "excess_return",
    "winner",
    "loser",
    "severe_drawdown",
    "right_tail",
    "max_drawdown_during_holding",
    "label_future_rows_used_count",
)
LABEL_SOURCE_FORBIDDEN_MEMBERSHIP_FIELDS: frozenset[str] = frozenset(
    {
        "cohort_id",
        "cohort_role",
        "cohort_member",
        "annotation_status",
        "membership_reason",
        "rank",
        "captured_positive_lists",
        "captured_risk_lists",
        "is_breakout_watch",
        "is_accumulation_watch",
        "is_high_confidence",
        "is_trend_leader",
        "is_long_term_stable",
        "is_rebound_watch",
        "is_high_risk_active",
    }
)
ALLOWED_PREJOIN_FUTURE_DIAGNOSTICS: frozenset[str] = frozenset(
    {"future_rows_excluded_count"}
)
PREJOIN_FORBIDDEN_EXACT: frozenset[str] = frozenset(
    {
        "label",
        "winner",
        "loser",
        "target",
        "outcome",
        "future_return",
        "benchmark_future_return",
        "future_excess_return",
        "excess_return",
        "realized_return",
        "holding_period",
        "max_drawdown_during_holding",
        "max_future",
        "min_future",
    }
)
PREJOIN_FORBIDDEN_PATTERN = re.compile(
    r"(^|_)(future|forward|realized|winner|loser|outcome|target)(_|$)"
    r"|(^|_)label($|_)"
    r"|(^|_)holding(_|$)"
    r"|(^|_)excess_return($|_)"
    r"|^(max_future|min_future|next_)",
    re.IGNORECASE,
)


class HistoricalH1H5EvaluatorError(ValueError):
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
class FrozenCohortInput:
    payload: dict[str, Any]
    source_path: Path
    sha256: str


@dataclass
class HistoricalH1H5EvaluationResult:
    frame: pd.DataFrame
    report: dict[str, Any]


def evaluator_schema_contract() -> dict[str, Any]:
    """Return the file-free evaluator contract for schema-check-only."""

    return {
        "status": "schema_valid",
        "runnable": False,
        "research_only": True,
        "provider_access": False,
        "production_change": False,
        "validation_id": VALIDATION_ID,
        "evidence_level": EVIDENCE_LEVEL,
        "primary_windows": list(PRIMARY_WINDOWS),
        "horizon_days": EXPECTED_HORIZON_DAYS,
        "benchmark": EXPECTED_BENCHMARK,
        "minimum_valid_labels_per_cohort": (
            MINIMUM_VALID_LABELS_PER_COHORT
        ),
        "cohort_ids": list(COHORT_ROLES),
        "result_statuses": list(RESULT_STATUSES),
        "required_label_fields": list(REQUIRED_LABEL_FIELDS),
        "required_output_fields": list(REQUIRED_OUTPUT_FIELDS),
        "output_path_patterns": {
            "window_json": (
                "outputs/validation/"
                "historical_h1h5_evaluation_<as_of_date>_20d.json"
            ),
            "window_csv": (
                "outputs/validation/"
                "historical_h1h5_evaluation_<as_of_date>_20d.csv"
            ),
            "summary_json": (
                "outputs/validation/historical_h1h5_summary_"
                "h1h5-historical-sealed-v1.json"
            ),
        },
        "cohort_digest_required_before_label_load": True,
        "explicit_label_source_required": True,
        "labels_generated": False,
        "snapshot_loaded": False,
        "label_source_loaded": False,
        "outputs_written": False,
    }


def load_frozen_cohort_output(
    path: str | Path,
    *,
    as_of_date: str,
    expected_sha256: str,
) -> FrozenCohortInput:
    """Verify a frozen digest before parsing a label-free cohort JSON."""

    _validate_primary_date(as_of_date)
    source = Path(path)
    if not source.exists():
        raise HistoricalH1H5EvaluatorError(
            "blocked_missing_frozen_cohort",
            "Frozen cohort output is missing.",
            details={"path": str(source)},
        )
    if source.suffix.lower() != ".json":
        raise HistoricalH1H5EvaluatorError(
            "blocked_invalid_cohort_format",
            "Frozen cohort input must be the metadata-bearing JSON output.",
        )
    normalized_digest = _normalize_sha256(expected_sha256)
    actual_digest = _sha256(source)
    if actual_digest != normalized_digest:
        raise HistoricalH1H5EvaluatorError(
            "blocked_frozen_digest_mismatch",
            "Frozen cohort digest does not match the explicit expected value.",
            details={
                "expected_sha256": normalized_digest,
                "actual_sha256": actual_digest,
            },
        )
    payload = _read_json_object(
        source,
        status="blocked_invalid_cohort_output",
    )
    _validate_cohort_payload(payload, as_of_date=as_of_date)
    return FrozenCohortInput(
        payload=payload,
        source_path=source,
        sha256=actual_digest,
    )


def load_explicit_label_source(path: str | Path) -> dict[str, Any]:
    """Load an explicit precomputed label JSON without provider fallback."""

    source = Path(path)
    if not source.exists():
        raise HistoricalH1H5EvaluatorError(
            "blocked_missing_label_source",
            "Explicit label source is missing.",
            details={"path": str(source)},
        )
    if source.suffix.lower() != ".json":
        raise HistoricalH1H5EvaluatorError(
            "blocked_invalid_label_source",
            "Label source must be a metadata-bearing JSON file.",
        )
    return _read_json_object(
        source,
        status="blocked_invalid_label_source",
    )


def validate_explicit_label_source(
    payload: Mapping[str, Any],
    *,
    as_of_date: str,
    horizon_days: int,
    benchmark: str,
) -> dict[str, Any]:
    """Validate an explicit label source without joining cohort membership."""

    _validate_execution_identity(
        as_of_date=as_of_date,
        horizon_days=horizon_days,
        benchmark=benchmark,
    )
    frame = _validate_label_source(
        payload,
        as_of_date=as_of_date,
        horizon_days=horizon_days,
        benchmark=benchmark,
    )
    valid_count = int(frame["_valid_label"].sum())
    return {
        "status": "safe_label_source",
        "validation_id": VALIDATION_ID,
        "evidence_level": EVIDENCE_LEVEL,
        "as_of_date": as_of_date,
        "horizon_days": horizon_days,
        "benchmark": benchmark,
        "row_count": int(len(frame)),
        "valid_label_count": valid_count,
        "missing_label_count": int(len(frame) - valid_count),
        "provider_access": False,
        "production_change": False,
        "label_window_complete": True,
        "membership_joined": False,
        "outputs_written": False,
    }


def evaluate_historical_h1h5_cohorts(
    frozen: FrozenCohortInput,
    label_source: Mapping[str, Any],
    *,
    as_of_date: str,
    horizon_days: int,
    benchmark: str,
    label_source_path: str | Path,
) -> HistoricalH1H5EvaluationResult:
    """Join explicit labels after digest validation and calculate metrics."""

    _validate_execution_identity(
        as_of_date=as_of_date,
        horizon_days=horizon_days,
        benchmark=benchmark,
    )
    current_digest = _sha256(frozen.source_path)
    if current_digest != frozen.sha256:
        raise HistoricalH1H5EvaluatorError(
            "blocked_frozen_digest_mismatch",
            "Frozen cohort changed after its digest was verified.",
            details={
                "verified_sha256": frozen.sha256,
                "current_sha256": current_digest,
            },
        )
    _validate_cohort_payload(frozen.payload, as_of_date=as_of_date)
    labels = _validate_label_source(
        label_source,
        as_of_date=as_of_date,
        horizon_days=horizon_days,
        benchmark=benchmark,
    )
    records = pd.DataFrame(frozen.payload["records"])
    original_membership = records.loc[
        :,
        ["symbol", "cohort_id", "cohort_role", "cohort_member"],
    ].copy(deep=True)
    records["symbol"] = records["symbol"].astype(str).str.strip()
    universe_symbols = sorted(records["symbol"].unique())
    extra_labels = sorted(set(labels["symbol"]) - set(universe_symbols))
    if extra_labels:
        raise HistoricalH1H5EvaluatorError(
            "blocked_label_universe_mismatch",
            "Label source contains symbols outside the frozen universe.",
            details={"extra_symbols": extra_labels[:50]},
        )

    joined = records.merge(
        labels,
        on="symbol",
        how="left",
        validate="many_to_one",
        suffixes=("", "_label"),
        indicator=True,
    )
    _assert_membership_unchanged(original_membership, joined)
    valid_universe = labels.loc[labels["_valid_label"]].copy()
    total_winners = int(valid_universe["winner"].sum())
    total_right_tail = int(valid_universe["right_tail"].sum())
    empty_cohort_count = 0
    rows: list[dict[str, Any]] = []
    for cohort_id, role in COHORT_ROLES.items():
        cohort = joined.loc[joined["cohort_id"] == cohort_id].copy()
        members = cohort.loc[cohort["cohort_member"].map(_as_bool) == True]
        member_count = int(len(members))
        if member_count == 0:
            empty_cohort_count += 1
        valid = members.loc[members["_valid_label"].eq(True)].copy()
        valid_label_count = int(len(valid))
        winner_count = int(valid["winner"].sum()) if not valid.empty else 0
        loser_count = int(valid["loser"].sum()) if not valid.empty else 0
        severe_count = (
            int(valid["severe_drawdown"].sum()) if not valid.empty else 0
        )
        right_tail_count = (
            int(valid["right_tail"].sum()) if not valid.empty else 0
        )
        warning_success_count = (
            int((valid["winner"] | valid["right_tail"]).sum())
            if not valid.empty
            else 0
        )
        underpowered = (
            valid_label_count < MINIMUM_VALID_LABELS_PER_COHORT
        )
        rows.append(
            {
                "validation_id": VALIDATION_ID,
                "evidence_level": EVIDENCE_LEVEL,
                "as_of_date": as_of_date,
                "horizon": horizon_days,
                "benchmark": benchmark,
                "cohort_name": cohort_id,
                "cohort_role": role,
                "member_count": member_count,
                "valid_label_count": valid_label_count,
                "missing_label_count": member_count - valid_label_count,
                "winner_count": winner_count,
                "loser_count": loser_count,
                "winner_capture": _ratio(winner_count, total_winners),
                "loser_contamination": _ratio(
                    loser_count,
                    valid_label_count,
                ),
                "severe_drawdown_incidence": _ratio(
                    severe_count,
                    valid_label_count,
                ),
                "benchmark_excess_return": _mean(
                    valid.get("excess_return")
                ),
                "benchmark_excess_return_median": _median(
                    valid.get("excess_return")
                ),
                "right_tail_retention": _ratio(
                    right_tail_count,
                    total_right_tail,
                ),
                "false_warning_rate": (
                    _ratio(warning_success_count, valid_label_count)
                    if role == "risk_annotation"
                    else None
                ),
                "coverage": _ratio(valid_label_count, member_count),
                "empty_cohort_rate": None,
                "underpowered": underpowered,
                "result_status": (
                    "underpowered"
                    if underpowered
                    else "mixed_research_only"
                ),
                "caveats": _cohort_caveats(
                    cohort_id,
                    member_count=member_count,
                    underpowered=underpowered,
                ),
                "labels_joined_by_evaluator": True,
                "builder_labels_joined": False,
                "production_change": False,
            }
        )
    empty_cohort_rate = empty_cohort_count / len(COHORT_ROLES)
    for row in rows:
        row["empty_cohort_rate"] = empty_cohort_rate

    output = pd.DataFrame(rows)
    missing_output_fields = sorted(
        set(REQUIRED_OUTPUT_FIELDS) - set(output.columns)
    )
    if missing_output_fields:
        raise HistoricalH1H5EvaluatorError(
            "invalid_execution",
            "Evaluator output schema is incomplete.",
            details={"missing_fields": missing_output_fields},
        )
    report = {
        "metadata": {
            "status": "evaluation_complete",
            "validation_id": VALIDATION_ID,
            "evidence_level": EVIDENCE_LEVEL,
            "as_of_date": as_of_date,
            "horizon": horizon_days,
            "benchmark": benchmark,
            "research_only": True,
            "provider_access": False,
            "labels_joined_by_evaluator": True,
            "builder_labels_joined": False,
            "production_change": False,
            "cohort_digest_verified": True,
            "frozen_cohort_sha256": frozen.sha256,
            "frozen_cohort_path": str(frozen.source_path),
            "label_source_path": str(Path(label_source_path)),
            "cohort_membership_mutated": False,
            "missing_labels_counted": True,
            "minimum_valid_labels_per_cohort": (
                MINIMUM_VALID_LABELS_PER_COHORT
            ),
            "cohort_count": len(COHORT_ROLES),
            "universe_symbol_count": len(universe_symbols),
            "label_row_count": int(len(labels)),
            "empty_cohort_count": empty_cohort_count,
            "empty_cohort_rate": empty_cohort_rate,
            "result_statuses": list(RESULT_STATUSES),
        },
        "cohorts": _json_safe(rows),
        "guardrails": [
            "Frozen cohort digest is verified before label source loading.",
            "Labels are joined by symbol outside the cohort builder.",
            "Missing labels and empty cohorts remain visible.",
            "Cohort membership is never rewritten.",
            "No provider, builder, production, or recommendation path exists.",
        ],
    }
    return HistoricalH1H5EvaluationResult(frame=output, report=report)


def write_historical_h1h5_evaluation_outputs(
    result: HistoricalH1H5EvaluationResult,
    *,
    outputs_dir: str | Path,
) -> dict[str, str]:
    """Write one explicitly authorized evaluation result in future phases."""

    metadata = result.report["metadata"]
    as_of_date = str(metadata["as_of_date"])
    horizon = int(metadata["horizon"])
    validation_dir = Path(outputs_dir) / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)
    stem = f"historical_h1h5_evaluation_{as_of_date}_{horizon}d"
    csv_path = validation_dir / f"{stem}.csv"
    json_path = validation_dir / f"{stem}.json"
    result.frame.to_csv(csv_path, index=False, encoding="utf-8-sig")
    json_path.write_text(
        json.dumps(_json_safe(result.report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"csv": str(csv_path), "json": str(json_path)}


def _validate_execution_identity(
    *,
    as_of_date: str,
    horizon_days: int,
    benchmark: str,
) -> None:
    _validate_primary_date(as_of_date)
    if horizon_days != EXPECTED_HORIZON_DAYS:
        raise HistoricalH1H5EvaluatorError(
            "blocked_horizon_mismatch",
            "Historical sealed evaluator requires exactly 20 trading days.",
        )
    if str(benchmark).strip() != EXPECTED_BENCHMARK:
        raise HistoricalH1H5EvaluatorError(
            "blocked_benchmark_mismatch",
            "Historical sealed evaluator requires benchmark=CSI300.",
        )


def _validate_primary_date(as_of_date: str) -> None:
    if as_of_date in EXCLUDED_WINDOWS:
        raise HistoricalH1H5EvaluatorError(
            "blocked_excluded_window",
            "Date is consumed evidence or reserved for prospective U3.",
        )
    if as_of_date not in PRIMARY_WINDOWS:
        raise HistoricalH1H5EvaluatorError(
            "blocked_non_primary_window",
            "Phase 3.10 evaluator accepts historical primary windows only.",
        )


def _validate_cohort_payload(
    payload: Mapping[str, Any],
    *,
    as_of_date: str,
) -> None:
    metadata = payload.get("metadata")
    records = payload.get("records")
    summaries = payload.get("cohorts")
    if not isinstance(metadata, Mapping):
        raise HistoricalH1H5EvaluatorError(
            "blocked_invalid_cohort_output",
            "Frozen cohort output is missing metadata.",
        )
    for field, expected in (
        ("research_only", True),
        ("provider_access", False),
        ("labels_joined", False),
        ("production_change", False),
    ):
        if metadata.get(field) is not expected:
            raise HistoricalH1H5EvaluatorError(
                f"blocked_unsafe_{field}",
                f"Frozen cohort metadata requires {field}={expected}.",
            )
    if str(metadata.get("as_of_date", "")).strip() != as_of_date:
        raise HistoricalH1H5EvaluatorError(
            "blocked_cohort_as_of_mismatch",
            "Frozen cohort as_of_date does not match.",
        )
    identity = metadata.get("validation_id")
    if identity is not None and identity != VALIDATION_ID:
        raise HistoricalH1H5EvaluatorError(
            "blocked_validation_id_mismatch",
            "Frozen cohort validation_id does not match.",
        )
    holdout_id = metadata.get("holdout_id")
    if holdout_id is not None and holdout_id != VALIDATION_ID:
        raise HistoricalH1H5EvaluatorError(
            "blocked_validation_id_mismatch",
            "Frozen cohort holdout_id does not match validation identity.",
        )
    if identity is None and holdout_id is None:
        raise HistoricalH1H5EvaluatorError(
            "blocked_missing_validation_id",
            "Frozen cohort output lacks validation identity metadata.",
        )
    if not isinstance(records, list) or not records or any(
        not isinstance(record, Mapping) for record in records
    ):
        raise HistoricalH1H5EvaluatorError(
            "blocked_invalid_cohort_output",
            "Frozen cohort records must be a non-empty object list.",
        )
    if not isinstance(summaries, list) or any(
        not isinstance(summary, Mapping) for summary in summaries
    ):
        raise HistoricalH1H5EvaluatorError(
            "blocked_invalid_cohort_output",
            "Frozen cohort summaries must be an object list.",
        )
    forbidden = _find_prejoin_forbidden_fields(
        _mapping_keys({"records": records, "cohorts": summaries})
    )
    if forbidden:
        raise HistoricalH1H5EvaluatorError(
            "blocked_prejoined_outcome_fields",
            "Frozen cohort output already contains label or outcome fields.",
            details={"forbidden_fields": forbidden},
        )
    frame = pd.DataFrame(records)
    required = {
        "symbol",
        "as_of_date",
        "cohort_id",
        "cohort_role",
        "cohort_member",
        "research_only",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise HistoricalH1H5EvaluatorError(
            "blocked_invalid_cohort_output",
            "Frozen cohort records are missing required fields.",
            details={"missing_fields": missing},
        )
    ids = set(frame["cohort_id"].astype(str))
    summary_ids = {
        str(summary.get("cohort_id")) for summary in summaries
    }
    if ids != set(COHORT_ROLES) or summary_ids != set(COHORT_ROLES):
        raise HistoricalH1H5EvaluatorError(
            "blocked_unknown_cohort",
            "Frozen output must contain exactly the frozen H1-H5 cohorts.",
        )
    for cohort_id, role in COHORT_ROLES.items():
        roles = set(
            frame.loc[
                frame["cohort_id"].astype(str) == cohort_id,
                "cohort_role",
            ].astype(str)
        )
        if roles != {role}:
            raise HistoricalH1H5EvaluatorError(
                "blocked_cohort_role_mismatch",
                "Frozen cohort role differs from the H1-H5 contract.",
                details={"cohort_id": cohort_id},
            )
    if not frame["as_of_date"].astype(str).eq(as_of_date).all():
        raise HistoricalH1H5EvaluatorError(
            "blocked_cohort_as_of_mismatch",
            "Frozen cohort records contain a wrong or mixed as-of date.",
        )
    if not frame["research_only"].map(_as_bool).eq(True).all():
        raise HistoricalH1H5EvaluatorError(
            "blocked_unsafe_research_only",
            "Every frozen cohort record must be research_only=true.",
        )
    duplicate_keys = frame.duplicated(["symbol", "cohort_id"])
    if duplicate_keys.any():
        raise HistoricalH1H5EvaluatorError(
            "blocked_duplicate_cohort_member",
            "Frozen output must contain one symbol row per cohort.",
        )
    per_cohort = frame.groupby("cohort_id")["symbol"].nunique()
    if per_cohort.nunique() != 1:
        raise HistoricalH1H5EvaluatorError(
            "blocked_incomplete_cohort_universe",
            "Every H1-H5 cohort must evaluate the same frozen universe.",
        )


def _validate_label_source(
    payload: Mapping[str, Any],
    *,
    as_of_date: str,
    horizon_days: int,
    benchmark: str,
) -> pd.DataFrame:
    metadata = payload.get("metadata")
    records = payload.get("records")
    if not isinstance(metadata, Mapping) or not isinstance(records, list):
        raise HistoricalH1H5EvaluatorError(
            "blocked_invalid_label_source",
            "Label source requires metadata and a records list.",
        )
    expected = {
        "validation_id": VALIDATION_ID,
        "evidence_level": EVIDENCE_LEVEL,
        "as_of_date": as_of_date,
        "horizon_days": horizon_days,
        "benchmark": benchmark,
        "label_window_complete": True,
        "provider_access": False,
        "production_change": False,
    }
    mismatches = {
        field: {"expected": value, "actual": metadata.get(field)}
        for field, value in expected.items()
        if metadata.get(field) != value
    }
    if mismatches:
        raise HistoricalH1H5EvaluatorError(
            "blocked_label_source_metadata_mismatch",
            "Explicit label source metadata does not match the contract.",
            details={"mismatches": mismatches},
        )
    frame = pd.DataFrame(records)
    missing = sorted(set(REQUIRED_LABEL_FIELDS) - set(frame.columns))
    if missing:
        raise HistoricalH1H5EvaluatorError(
            "blocked_missing_label_fields",
            "Label source is missing required fields.",
            details={"missing_fields": missing},
        )
    forbidden_membership = sorted(
        set(frame.columns) & LABEL_SOURCE_FORBIDDEN_MEMBERSHIP_FIELDS
    )
    if forbidden_membership:
        raise HistoricalH1H5EvaluatorError(
            "blocked_label_source_membership_fields",
            (
                "Label source must not carry builder-side membership "
                "or ranking fields."
            ),
            details={"forbidden_fields": forbidden_membership},
        )
    frame = frame.loc[:, list(REQUIRED_LABEL_FIELDS)].copy()
    frame["symbol"] = frame["symbol"].astype(str).str.strip()
    if frame["symbol"].eq("").any() or frame["symbol"].duplicated().any():
        raise HistoricalH1H5EvaluatorError(
            "blocked_invalid_label_symbols",
            "Label source requires unique non-empty symbols.",
        )
    if not frame["as_of_date"].astype(str).eq(as_of_date).all():
        raise HistoricalH1H5EvaluatorError(
            "blocked_label_as_of_mismatch",
            "Label source contains a wrong or mixed as-of date.",
        )
    if not pd.to_numeric(
        frame["horizon_days"],
        errors="coerce",
    ).eq(horizon_days).all():
        raise HistoricalH1H5EvaluatorError(
            "blocked_label_horizon_mismatch",
            "Label rows do not match the explicit 20D horizon.",
        )
    if not frame["benchmark"].astype(str).eq(benchmark).all():
        raise HistoricalH1H5EvaluatorError(
            "blocked_label_benchmark_mismatch",
            "Label rows do not match the explicit benchmark.",
        )
    frame["_valid_label"] = frame["data_quality"].astype(str).eq("ok")
    valid = frame.loc[frame["_valid_label"]]
    future_rows = pd.to_numeric(
        valid["label_future_rows_used_count"],
        errors="coerce",
    )
    if not future_rows.eq(horizon_days).all():
        raise HistoricalH1H5EvaluatorError(
            "blocked_incomplete_label_horizon",
            "Every valid label must use the complete 20 trading-day horizon.",
        )
    for field in (
        "future_return",
        "benchmark_future_return",
        "excess_return",
        "max_drawdown_during_holding",
    ):
        numeric = pd.to_numeric(valid[field], errors="coerce")
        if numeric.isna().any() or not numeric.map(math.isfinite).all():
            raise HistoricalH1H5EvaluatorError(
                "blocked_invalid_label_values",
                f"Valid labels require finite {field}.",
            )
        frame.loc[valid.index, field] = numeric
    for field in ("winner", "loser", "severe_drawdown", "right_tail"):
        converted = valid[field].map(_as_bool)
        if converted.isna().any():
            raise HistoricalH1H5EvaluatorError(
                "blocked_invalid_label_values",
                f"Valid labels require boolean {field}.",
            )
        frame.loc[valid.index, field] = converted
    if (
        frame.loc[valid.index, "winner"].astype(bool)
        & frame.loc[valid.index, "loser"].astype(bool)
    ).any():
        raise HistoricalH1H5EvaluatorError(
            "blocked_contradictory_labels",
            "A valid label cannot be both winner and loser.",
        )
    return frame


def _assert_membership_unchanged(
    original: pd.DataFrame,
    joined: pd.DataFrame,
) -> None:
    current = joined.loc[
        :,
        ["symbol", "cohort_id", "cohort_role", "cohort_member"],
    ].copy()
    if not original.reset_index(drop=True).equals(
        current.reset_index(drop=True)
    ):
        raise HistoricalH1H5EvaluatorError(
            "invalid_execution",
            "Label join changed frozen cohort membership.",
        )


def _cohort_caveats(
    cohort_id: str,
    *,
    member_count: int,
    underpowered: bool,
) -> list[str]:
    caveats = [
        "Historical sealed research evidence is not prospective U3 proof.",
        "No result authorizes production or recommendation changes.",
    ]
    if member_count == 0:
        caveats.append("Empty cohort remains visible.")
    if underpowered:
        caveats.append(
            "Valid label count is below the frozen 20-member gate."
        )
    if COHORT_ROLES[cohort_id] == "risk_annotation":
        caveats.append("Risk annotation is non-blocking.")
    return caveats


def _find_prejoin_forbidden_fields(fields: list[str]) -> list[str]:
    result = []
    for field in fields:
        normalized = str(field).strip().lower()
        if normalized in ALLOWED_PREJOIN_FUTURE_DIAGNOSTICS:
            continue
        if (
            normalized in PREJOIN_FORBIDDEN_EXACT
            or PREJOIN_FORBIDDEN_PATTERN.search(normalized)
        ):
            result.append(str(field))
    return sorted(set(result))


def _mapping_keys(value: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            keys.append(str(key))
            keys.extend(_mapping_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.extend(_mapping_keys(child))
    return keys


def _read_json_object(path: Path, *, status: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HistoricalH1H5EvaluatorError(
            status,
            "Input file is not valid JSON.",
            details={"path": str(path)},
        ) from exc
    if not isinstance(payload, dict):
        raise HistoricalH1H5EvaluatorError(
            status,
            "Input JSON must be an object.",
            details={"path": str(path)},
        )
    return payload


def _normalize_sha256(value: str) -> str:
    normalized = str(value).strip().upper()
    if not re.fullmatch(r"[0-9A-F]{64}", normalized):
        raise HistoricalH1H5EvaluatorError(
            "blocked_invalid_expected_digest",
            "Expected frozen cohort digest must be a SHA-256 hex string.",
        )
    return normalized


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _mean(values: pd.Series | None) -> float | None:
    if values is None or values.empty:
        return None
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    return float(numeric.mean()) if not numeric.empty else None


def _median(values: pd.Series | None) -> float | None:
    if values is None or values.empty:
        return None
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    return float(numeric.median()) if not numeric.empty else None


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
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    if hasattr(value, "item"):
        return _json_safe(value.item())
    return value
