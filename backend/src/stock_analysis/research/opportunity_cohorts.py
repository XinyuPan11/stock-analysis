"""Research-only H1-H5 cohort annotations from point-in-time snapshots."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping

import pandas as pd


COHORT_ROLES: dict[str, str] = {
    "low_position_revaluation_watch": "opportunity_observation",
    "trend_acceleration_with_crowding_guard": "opportunity_observation",
    "right_tail_opportunity_watch": "opportunity_observation",
    "high_position_crowding_risk": "risk_annotation",
    "false_breakout_risk": "risk_annotation",
}

COHORT_PARAMETERS: dict[str, tuple[str, ...]] = {
    "low_position_revaluation_watch": (
        "max_distance_to_60d_low",
        "max_drawdown_60d",
        "min_recent_acceleration_proxy",
        "min_activity_change_20d",
    ),
    "trend_acceleration_with_crowding_guard": (
        "min_recent_acceleration_proxy",
        "min_pre_20d_return",
        "min_crowding_proxy",
        "min_distance_to_60d_high",
    ),
    "right_tail_opportunity_watch": (
        "min_volatility_20d",
        "min_recent_acceleration_proxy",
        "min_activity_change_20d",
    ),
    "high_position_crowding_risk": (
        "min_distance_to_60d_high",
        "min_crowding_proxy",
        "min_volatility_20d",
    ),
    "false_breakout_risk": (
        "min_distance_to_60d_high",
        "max_recent_acceleration_proxy",
        "max_drawdown_60d",
        "min_activity_change_20d",
    ),
}

BASE_REQUIRED_COLUMNS: tuple[str, ...] = (
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

ALLOWED_VOLATILITY_BINDINGS = {
    "technical_volatility_20d",
    "volatility_20d",
}

FORBIDDEN_EXACT_COLUMNS = {
    "label",
    "winner",
    "loser",
    "realized_return",
    "benchmark_return",
    "outperformed_benchmark",
    "max_drawdown_during_holding",
}

ALLOWED_DIAGNOSTIC_COLUMNS = {
    "future_rows_excluded_count",
}


FORBIDDEN_COLUMN_PATTERN = re.compile(
    r"(^|_)(future|forward|realized|winner|loser|outcome)(_|$)"
    r"|^(max_future|min_future|next_)",
    re.IGNORECASE,
)

COHORT_CAVEATS: dict[str, str] = {
    "low_position_revaluation_watch": (
        "Low position is not quality; temporary rebounds and unresolved risk "
        "remain possible."
    ),
    "trend_acceleration_with_crowding_guard": (
        "Acceleration may be mature, and the price-only crowding warning can "
        "flag legitimate consolidation."
    ),
    "right_tail_opportunity_watch": (
        "This high-variance observation can include speculative spikes, false "
        "breakouts, and severe downside."
    ),
    "high_position_crowding_risk": (
        "This is a non-blocking price-structure warning, not actual holder "
        "crowding or an action signal."
    ),
    "false_breakout_risk": (
        "A pause or volatile retest may later continue; this annotation does "
        "not change source-list membership."
    ),
}


class OpportunityCohortBuildError(ValueError):
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


@dataclass
class OpportunityCohortBuildResult:
    frame: pd.DataFrame
    report: dict[str, Any]


def load_opportunity_snapshot(path: str | Path) -> pd.DataFrame:
    source = Path(path)
    if not source.exists():
        raise OpportunityCohortBuildError(
            "blocked_missing_snapshot",
            f"Snapshot file not found: {source}",
        )
    if source.suffix.lower() == ".csv":
        return pd.read_csv(source)
    if source.suffix.lower() == ".json":
        payload = json.loads(source.read_text(encoding="utf-8-sig"))
        if isinstance(payload, list):
            records = payload
        elif isinstance(payload, dict) and isinstance(payload.get("records"), list):
            records = payload["records"]
        else:
            raise OpportunityCohortBuildError(
                "blocked_invalid_snapshot",
                "JSON snapshot must be a record list or contain records.",
            )
        return pd.DataFrame(records)
    raise OpportunityCohortBuildError(
        "blocked_invalid_snapshot",
        "Snapshot file must be CSV or JSON.",
    )


def load_opportunity_cohort_config(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        raise OpportunityCohortBuildError(
            "blocked_missing_config",
            f"Explicit research config not found: {source}",
        )
    try:
        payload = json.loads(source.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OpportunityCohortBuildError(
            "blocked_invalid_config",
            f"Research config is not valid JSON: {source}",
        ) from exc
    if not isinstance(payload, dict):
        raise OpportunityCohortBuildError(
            "blocked_invalid_config",
            "Research config must be a JSON object.",
        )
    return payload


def build_research_opportunity_cohorts(
    snapshot: pd.DataFrame,
    config: Mapping[str, Any] | None,
    *,
    as_of_date: str,
    source_snapshot_path: str | Path,
    config_path: str | Path,
) -> OpportunityCohortBuildResult:
    resolved_config = _validate_config(config, as_of_date)
    volatility_field = str(
        resolved_config["feature_bindings"]["volatility_20d"]
    )
    _reject_forbidden_columns(snapshot.columns)
    required_columns = set(BASE_REQUIRED_COLUMNS) | {volatility_field}
    missing_columns = sorted(required_columns - set(snapshot.columns))
    if missing_columns:
        raise OpportunityCohortBuildError(
            "blocked_missing_required_feature",
            "Snapshot is missing required as-of fields.",
            details={"missing_columns": missing_columns},
        )

    selected = snapshot.loc[
        snapshot["as_of_date"].astype(str) == as_of_date
    ].copy()
    if selected.empty:
        raise OpportunityCohortBuildError(
            "blocked_missing_as_of_rows",
            f"Snapshot contains no rows for as_of_date={as_of_date}.",
        )
    selected["symbol"] = selected["symbol"].astype(str)
    duplicate_symbols = sorted(
        selected.loc[selected["symbol"].duplicated(), "symbol"].unique()
    )
    if duplicate_symbols:
        raise OpportunityCohortBuildError(
            "blocked_duplicate_symbol",
            "Snapshot must contain one row per as_of_date and symbol.",
            details={"duplicate_symbols": duplicate_symbols},
        )

    _validate_point_in_time(selected, as_of_date)
    original = selected.copy(deep=True)
    parameters = {
        cohort_id: dict(resolved_config["cohorts"][cohort_id]["parameters"])
        for cohort_id in COHORT_ROLES
    }

    records: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for cohort_id, role in COHORT_ROLES.items():
        cohort_records: list[dict[str, Any]] = []
        for _, row in selected.iterrows():
            evaluated = _evaluate_cohort(
                cohort_id,
                row,
                parameters[cohort_id],
                volatility_field,
            )
            base = row.to_dict()
            base.update(
                {
                    "cohort_id": cohort_id,
                    "cohort_role": role,
                    "cohort_member": evaluated["included"],
                    "annotation_status": evaluated["status"],
                    "crowding_warning": evaluated.get(
                        "crowding_warning",
                        False,
                    ),
                    "evidence_fields": json.dumps(
                        evaluated["evidence_fields"],
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    "counter_evidence_fields": json.dumps(
                        evaluated["counter_evidence_fields"],
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    "missing_required_fields": json.dumps(
                        evaluated["missing_required_fields"],
                        ensure_ascii=False,
                    ),
                    "membership_reason": evaluated["membership_reason"],
                    "research_caveat": COHORT_CAVEATS[cohort_id],
                    "research_only": True,
                }
            )
            cohort_records.append(base)
            records.append(base)
        member_count = sum(
            bool(item["cohort_member"]) for item in cohort_records
        )
        blocked_count = sum(
            item["annotation_status"] == "excluded_missing_required_fields"
            for item in cohort_records
        )
        summaries.append(
            {
                "cohort_id": cohort_id,
                "cohort_role": role,
                "research_only": True,
                "input_row_count": len(cohort_records),
                "member_count": member_count,
                "blocked_row_count": blocked_count,
                "caveat": COHORT_CAVEATS[cohort_id],
            }
        )

    output = pd.DataFrame(records)
    _reject_forbidden_columns(output.columns)
    if not selected.equals(original):
        raise OpportunityCohortBuildError(
            "blocked_source_mutation",
            "Source snapshot changed while building research annotations.",
        )
    blocked_rows = int(
        (output["annotation_status"] == "excluded_missing_required_fields").sum()
    )
    report = {
        "metadata": {
            "status": "partial_missing_features" if blocked_rows else "ok",
            "research_only": True,
            "provider_access": False,
            "labels_joined": False,
            "production_change": False,
            "as_of_date": as_of_date,
            "source_snapshot_path": str(Path(source_snapshot_path)),
            "config_path": str(Path(config_path)),
            "config_version": str(resolved_config["config_version"]),
            "parameter_source": str(resolved_config["parameter_source"]),
            "cohort_count": len(COHORT_ROLES),
            "input_row_count": len(selected),
            "output_record_count": len(output),
            "volatility_field": volatility_field,
            "leakage_guard_applied": True,
        },
        "cohorts": summaries,
        "guardrails": [
            "Features and memberships use only the explicit as-of snapshot.",
            "Future outcome columns are rejected before cohort evaluation.",
            "H1-H3 are opportunity observations; H4-H5 are risk annotations.",
            "Existing list membership and rank fields are copied unchanged.",
            "No provider access, label join, or production change is allowed.",
        ],
    }
    return OpportunityCohortBuildResult(frame=output, report=report)


def write_research_opportunity_cohort_outputs(
    result: OpportunityCohortBuildResult,
    outputs_dir: str | Path,
) -> dict[str, str]:
    as_of_date = str(result.report["metadata"]["as_of_date"])
    research_dir = Path(outputs_dir) / "research"
    research_dir.mkdir(parents=True, exist_ok=True)
    json_path = research_dir / f"opportunity_cohorts_{as_of_date}.json"
    csv_path = research_dir / f"opportunity_cohorts_{as_of_date}.csv"
    _reject_forbidden_columns(result.frame.columns)
    result.frame.to_csv(csv_path, index=False, encoding="utf-8-sig")
    payload = {
        **result.report,
        "records": json.loads(
            result.frame.to_json(
                orient="records",
                force_ascii=False,
                date_format="iso",
            )
        ),
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "json": str(json_path),
        "csv": str(csv_path),
    }


def _validate_config(
    config: Mapping[str, Any] | None,
    as_of_date: str,
) -> dict[str, Any]:
    if not isinstance(config, Mapping):
        raise OpportunityCohortBuildError(
            "blocked_missing_config",
            "An explicit research-only config is required.",
        )
    if config.get("research_only") is not True:
        raise OpportunityCohortBuildError(
            "blocked_invalid_config",
            "Config must declare research_only=true.",
        )
    for field in ("config_version", "parameter_source", "as_of_date"):
        if not str(config.get(field, "")).strip():
            raise OpportunityCohortBuildError(
                "blocked_invalid_config",
                f"Config is missing required field: {field}.",
            )
    if str(config["as_of_date"]) != as_of_date:
        raise OpportunityCohortBuildError(
            "blocked_config_as_of_mismatch",
            "Config as_of_date does not match the requested as_of_date.",
        )
    feature_bindings = config.get("feature_bindings")
    if not isinstance(feature_bindings, Mapping):
        raise OpportunityCohortBuildError(
            "blocked_invalid_config",
            "Config must define feature_bindings.",
        )
    volatility_field = feature_bindings.get("volatility_20d")
    if volatility_field not in ALLOWED_VOLATILITY_BINDINGS:
        raise OpportunityCohortBuildError(
            "blocked_invalid_config",
            "volatility_20d must bind to an allowed as-of field.",
        )
    cohorts = config.get("cohorts")
    if not isinstance(cohorts, Mapping) or set(cohorts) != set(COHORT_ROLES):
        raise OpportunityCohortBuildError(
            "blocked_invalid_config",
            "Config must define exactly the frozen H1-H5 cohorts.",
        )
    for cohort_id, expected_role in COHORT_ROLES.items():
        cohort = cohorts.get(cohort_id)
        if not isinstance(cohort, Mapping):
            raise OpportunityCohortBuildError(
                "blocked_invalid_config",
                f"Invalid cohort config: {cohort_id}.",
            )
        if cohort.get("role") != expected_role:
            raise OpportunityCohortBuildError(
                "blocked_invalid_config",
                f"Invalid role for cohort: {cohort_id}.",
            )
        parameters = cohort.get("parameters")
        expected_parameters = set(COHORT_PARAMETERS[cohort_id])
        if not isinstance(parameters, Mapping) or set(parameters) != expected_parameters:
            raise OpportunityCohortBuildError(
                "blocked_missing_frozen_parameter",
                f"Config parameters are incomplete for cohort: {cohort_id}.",
            )
        for name, value in parameters.items():
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
            ):
                raise OpportunityCohortBuildError(
                    "blocked_missing_frozen_parameter",
                    f"Parameter must be an explicit finite number: "
                    f"{cohort_id}.{name}.",
                )
    return dict(config)


def _reject_forbidden_columns(columns: Any) -> None:
    forbidden = sorted(
        str(column)
        for column in columns
        if _is_forbidden_column(str(column))
    )
    if forbidden:
        raise OpportunityCohortBuildError(
            "blocked_future_outcome_columns",
            "Snapshot contains future or realized outcome columns.",
            details={"forbidden_columns": forbidden},
        )


def _is_forbidden_column(column: str) -> bool:
    normalized = column.strip().lower()
    if normalized in ALLOWED_DIAGNOSTIC_COLUMNS:
        return False
    return (
        normalized in FORBIDDEN_EXACT_COLUMNS
        or bool(FORBIDDEN_COLUMN_PATTERN.search(normalized))
    )


def _validate_point_in_time(frame: pd.DataFrame, as_of_date: str) -> None:
    guard_values = frame["leakage_guard_applied"].map(_as_bool)
    if guard_values.isna().any() or not guard_values.all():
        raise OpportunityCohortBuildError(
            "blocked_unverified_leakage_guard",
            "Every row must have leakage_guard_applied=true.",
        )
    if "latest_input_date" not in frame.columns:
        return
    present = frame["latest_input_date"].notna() & (
        frame["latest_input_date"].astype(str).str.strip() != ""
    )
    parsed = pd.to_datetime(frame.loc[present, "latest_input_date"], errors="coerce")
    if parsed.isna().any():
        raise OpportunityCohortBuildError(
            "blocked_point_in_time_violation",
            "latest_input_date contains malformed values.",
        )
    cutoff = pd.Timestamp(as_of_date)
    if (parsed > cutoff).any():
        symbols = frame.loc[present].loc[parsed > cutoff, "symbol"].astype(str)
        raise OpportunityCohortBuildError(
            "blocked_point_in_time_violation",
            "latest_input_date exceeds as_of_date.",
            details={"symbols": sorted(symbols.tolist())},
        )


def _evaluate_cohort(
    cohort_id: str,
    row: pd.Series,
    parameters: Mapping[str, float],
    volatility_field: str,
) -> dict[str, Any]:
    required_fields = _cohort_required_fields(cohort_id, volatility_field)
    missing_fields = [
        field for field in required_fields if _missing(row.get(field))
    ]
    if missing_fields:
        return {
            "included": False,
            "status": "excluded_missing_required_fields",
            "crowding_warning": False,
            "evidence_fields": {},
            "counter_evidence_fields": {},
            "missing_required_fields": missing_fields,
            "membership_reason": "Required as-of evidence is incomplete.",
        }

    values = {
        field: _numeric(row[field])
        for field in required_fields
        if field not in {"is_breakout_watch", "is_accumulation_watch"}
    }
    activity = (
        max(values["amount_change_20d"], values["volume_change_20d"])
        if "amount_change_20d" in values
        and "volume_change_20d" in values
        else None
    )
    evidence: dict[str, Any] = {}
    counter: dict[str, Any] = {}
    crowding_warning = False

    if cohort_id == "low_position_revaluation_watch":
        conditions = {
            "low_position": values["distance_to_60d_low"]
            <= parameters["max_distance_to_60d_low"],
            "prior_drawdown": values["drawdown_60d"]
            <= parameters["max_drawdown_60d"],
            "recovery_acceleration": values["recent_acceleration_proxy"]
            >= parameters["min_recent_acceleration_proxy"],
            "activity_confirmation": activity
            is not None
            and activity >= parameters["min_activity_change_20d"],
        }
    elif cohort_id == "trend_acceleration_with_crowding_guard":
        conditions = {
            "acceleration": values["recent_acceleration_proxy"]
            >= parameters["min_recent_acceleration_proxy"],
            "trend_support": values["pre_20d_return"]
            >= parameters["min_pre_20d_return"],
        }
        crowding_warning = (
            values["high_position_crowding_proxy"]
            >= parameters["min_crowding_proxy"]
            and values["distance_to_60d_high"]
            >= parameters["min_distance_to_60d_high"]
        )
        evidence["crowding_warning_evaluated"] = True
        evidence["crowding_warning"] = crowding_warning
    elif cohort_id == "right_tail_opportunity_watch":
        conditions = {
            "volatility_context": values[volatility_field]
            >= parameters["min_volatility_20d"],
            "positive_acceleration": values["recent_acceleration_proxy"]
            >= parameters["min_recent_acceleration_proxy"],
            "activity_confirmation": activity
            is not None
            and activity >= parameters["min_activity_change_20d"],
        }
        counter["right_tail_structure_proxy_limited"] = True
    elif cohort_id == "high_position_crowding_risk":
        conditions = {
            "high_position": values["distance_to_60d_high"]
            >= parameters["min_distance_to_60d_high"],
            "crowding_context": values["high_position_crowding_proxy"]
            >= parameters["min_crowding_proxy"],
            "volatility_context": values[volatility_field]
            >= parameters["min_volatility_20d"],
        }
    elif cohort_id == "false_breakout_risk":
        source_member = _as_bool(row["is_breakout_watch"]) is True or _as_bool(
            row["is_accumulation_watch"]
        ) is True
        weakness = (
            values["recent_acceleration_proxy"]
            <= parameters["max_recent_acceleration_proxy"]
            or values["drawdown_60d"] <= parameters["max_drawdown_60d"]
        )
        conditions = {
            "source_list_membership": source_member,
            "high_position": values["distance_to_60d_high"]
            >= parameters["min_distance_to_60d_high"],
            "activity_present": activity
            is not None
            and activity >= parameters["min_activity_change_20d"],
            "as_of_weakness": weakness,
        }
    else:
        raise OpportunityCohortBuildError(
            "blocked_invalid_config",
            f"Unknown frozen cohort: {cohort_id}.",
        )

    included = all(conditions.values())
    evidence.update(
        {name: True for name, matched in conditions.items() if matched}
    )
    counter.update(
        {name: False for name, matched in conditions.items() if not matched}
    )
    return {
        "included": included,
        "status": "included" if included else "not_in_cohort",
        "crowding_warning": crowding_warning,
        "evidence_fields": evidence,
        "counter_evidence_fields": counter,
        "missing_required_fields": [],
        "membership_reason": (
            "Frozen as-of cohort conditions matched."
            if included
            else "One or more frozen as-of cohort conditions did not match."
        ),
    }


def _cohort_required_fields(
    cohort_id: str,
    volatility_field: str,
) -> tuple[str, ...]:
    shared_activity = ("amount_change_20d", "volume_change_20d")
    mapping = {
        "low_position_revaluation_watch": (
            "distance_to_60d_low",
            "drawdown_60d",
            "recent_acceleration_proxy",
            *shared_activity,
        ),
        "trend_acceleration_with_crowding_guard": (
            "recent_acceleration_proxy",
            "pre_20d_return",
            "high_position_crowding_proxy",
            "distance_to_60d_high",
        ),
        "right_tail_opportunity_watch": (
            volatility_field,
            "recent_acceleration_proxy",
            *shared_activity,
        ),
        "high_position_crowding_risk": (
            "distance_to_60d_high",
            "high_position_crowding_proxy",
            volatility_field,
        ),
        "false_breakout_risk": (
            "is_breakout_watch",
            "is_accumulation_watch",
            "distance_to_60d_high",
            "recent_acceleration_proxy",
            "drawdown_60d",
            *shared_activity,
        ),
    }
    return mapping[cohort_id]


def _missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _numeric(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise OpportunityCohortBuildError(
            "blocked_invalid_feature_value",
            f"Feature value is not numeric: {value!r}.",
        ) from exc
    if not math.isfinite(parsed):
        raise OpportunityCohortBuildError(
            "blocked_invalid_feature_value",
            "Feature value must be finite.",
        )
    return parsed


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
