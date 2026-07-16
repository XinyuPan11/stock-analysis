"""Transparent research-only Phase 4.2 challenger scoring."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from stock_analysis.research.production_candidate_feature_matrix import (
    FEATURE_CONFIG_ID,
    FEATURE_CONFIG_VERSION,
    FEATURE_SCHEMA_VERSION,
    ProductionCandidateFeatureMatrixError,
    load_feature_config,
    sha256_file,
)


CHALLENGER_CONFIG_SCHEMA = "production-candidate-challengers-config-v1"
CHALLENGER_CONFIG_ID = "production-candidate-challengers"
CHALLENGER_CONFIG_VERSION = "phase4.2-v1"
EXPECTED_CHALLENGER_CONFIG_SHA256 = (
    "D8558C3031BC567C3D6CB5F43EC358E22E842B306653C7B578F95D684BE44353"
)
FOUNDATION_ID = "production-candidate-research-foundation"
BASELINE_ID = "current-production-candidate-baseline"
FORBIDDEN_LABEL_COLUMNS = {
    "winner",
    "loser",
    "right_tail",
    "severe_drawdown",
    "valid_label",
    "missing_label_reason",
}
FORBIDDEN_COLUMN_PATTERNS = (
    "future_return",
    "future_end",
    "future_window",
    "benchmark_return",
    "excess_return",
    "max_future",
    "validation_result_status",
    "future_list_performance",
    "cohort_effectiveness",
)
OUTPUT_COLUMNS = [
    "symbol",
    "as_of_date",
    "baseline_total_score",
    "challenger_id",
    "challenger_score",
    "challenger_rank",
    "eligibility_status",
    "missing_component_count",
    "missing_component_ids",
    "research_status",
    "effectiveness_status",
    "provider_access",
    "labels_joined",
    "production_change",
    "results_are_effectiveness_evidence",
]


class ProductionCandidateChallengerError(ValueError):
    """Structured challenger config or input error."""

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
class ChallengerResult:
    frame: pd.DataFrame
    report: dict[str, Any]


def load_challenger_config(
    path: str | Path,
    *,
    feature_config_path: str | Path,
) -> dict[str, Any]:
    payload = _read_json_object(path)
    actual_challenger_sha = sha256_file(path)
    if actual_challenger_sha != EXPECTED_CHALLENGER_CONFIG_SHA256:
        _fail(
            "invalid_execution",
            "Challenger config digest mismatch.",
            expected=EXPECTED_CHALLENGER_CONFIG_SHA256,
            actual=actual_challenger_sha,
        )

    feature_config = load_feature_config(feature_config_path)
    validate_challenger_config(
        payload,
        feature_config=feature_config,
        feature_config_sha256=sha256_file(feature_config_path),
    )
    return payload


def validate_challenger_config(
    payload: Mapping[str, Any],
    *,
    feature_config: Mapping[str, Any],
    feature_config_sha256: str,
) -> None:
    expected = {
        "schema_version": CHALLENGER_CONFIG_SCHEMA,
        "challenger_config_id": CHALLENGER_CONFIG_ID,
        "challenger_config_version": CHALLENGER_CONFIG_VERSION,
        "foundation_id": FOUNDATION_ID,
        "production_baseline_id": BASELINE_ID,
        "feature_config_id": FEATURE_CONFIG_ID,
        "feature_config_version": FEATURE_CONFIG_VERSION,
        "feature_config_sha256": feature_config_sha256,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "provider_access": False,
        "labels_joined": False,
        "production_change": False,
        "effectiveness_status": "not_evaluated",
        "parameters_tuned_on_outcomes": False,
        "results_are_effectiveness_evidence": False,
    }
    _require_values(payload, expected, "Challenger identity, digest, or safety drifted.")
    configured = payload.get("challengers")
    if not isinstance(configured, list) or not configured:
        _fail("invalid_execution", "Challenger registry must be non-empty.")
    known_features = {
        item["feature_id"] for item in feature_config["feature_definitions"]
    }
    ids: list[str] = []
    for challenger in configured:
        if not isinstance(challenger, Mapping):
            _fail("invalid_execution", "Challenger definition must be an object.")
        challenger_id = str(challenger.get("challenger_id", "")).strip()
        ids.append(challenger_id)
        required = {
            "challenger_version",
            "challenger_family",
            "research_status",
            "effectiveness_status",
            "components",
            "combination_formula",
            "missing_feature_behavior",
            "eligibility_prerequisites",
            "tie_breaking",
            "candidate_output_behavior",
            "production_change",
            "inherited_evidence",
            "parameters_tuned_on_outcomes",
        }
        missing = sorted(required - set(challenger))
        if not challenger_id or missing:
            _fail(
                "invalid_execution",
                "Challenger definition is incomplete.",
                challenger_id=challenger_id,
                missing_fields=missing,
            )
        if (
            challenger["research_status"] != "research_only"
            or challenger["effectiveness_status"] != "not_evaluated"
            or challenger["production_change"] is not False
            or challenger["inherited_evidence"] is not False
            or challenger["parameters_tuned_on_outcomes"] is not False
        ):
            _fail(
                "invalid_execution",
                "Challenger claims effectiveness, inherited evidence, tuning, or production use.",
                challenger_id=challenger_id,
            )
        components = challenger["components"]
        if not isinstance(components, list) or not components:
            _fail("invalid_execution", "Challenger components must be non-empty.")
        weights = 0.0
        for component in components:
            feature_id = str(component.get("feature_id", ""))
            if feature_id not in known_features:
                _fail(
                    "invalid_execution",
                    "Challenger references unknown feature.",
                    challenger_id=challenger_id,
                    feature_id=feature_id,
                )
            if component.get("sign") not in {-1, 1}:
                _fail("invalid_execution", "Component sign must be -1 or 1.")
            weight = component.get("weight")
            if isinstance(weight, bool) or not isinstance(weight, (int, float)) or weight <= 0:
                _fail("invalid_execution", "Component weight must be positive.")
            weights += float(weight)
            if component.get("transform") != "same_date_percentile":
                _fail("invalid_execution", "Only same-date percentile transform is allowed.")
        if abs(weights - 1.0) > 1e-9:
            _fail(
                "invalid_execution",
                "Challenger component weights must sum to one.",
                challenger_id=challenger_id,
                weight_sum=weights,
            )
        for prerequisite in challenger["eligibility_prerequisites"]:
            if prerequisite.get("feature_id") not in known_features:
                _fail("invalid_execution", "Prerequisite references unknown feature.")
            if prerequisite.get("operator") != "equals":
                _fail("invalid_execution", "Only deterministic equals prerequisite is allowed.")
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        _fail("invalid_execution", "Duplicate challenger IDs are forbidden.")
    if payload.get("output_columns") != OUTPUT_COLUMNS:
        _fail("invalid_execution", "Challenger output schema drifted.")


def build_challengers(
    *,
    feature_matrix_path: str | Path,
    feature_config_path: str | Path,
    challenger_config_path: str | Path,
) -> ChallengerResult:
    feature_config = load_feature_config(feature_config_path)
    config = load_challenger_config(
        challenger_config_path,
        feature_config_path=feature_config_path,
    )
    matrix = pd.read_csv(feature_matrix_path)
    _validate_feature_matrix(matrix, feature_config, feature_config_path)
    as_of = str(matrix["as_of_date"].iloc[0])
    rows: list[dict[str, Any]] = []
    for challenger in config["challengers"]:
        components = challenger["components"]
        transformed: dict[str, pd.Series] = {}
        for component in components:
            feature_id = component["feature_id"]
            numeric = pd.to_numeric(matrix[feature_id], errors="coerce")
            percentile = numeric.rank(
                method="average", pct=True, ascending=True
            )
            transformed[feature_id] = (
                percentile
                if component["sign"] == 1
                else 1.0 - percentile
            )
        for index, source in matrix.iterrows():
            missing_ids = [
                component["feature_id"]
                for component in components
                if pd.isna(source.get(component["feature_id"]))
            ]
            prerequisite_failures = [
                item["feature_id"]
                for item in challenger["eligibility_prerequisites"]
                if not _equals(source.get(item["feature_id"]), item.get("value"))
            ]
            all_missing = sorted(set([*missing_ids, *prerequisite_failures]))
            eligible = not all_missing
            score = (
                sum(
                    float(component["weight"])
                    * float(transformed[component["feature_id"]].iloc[index])
                    for component in components
                )
                * 100.0
                if eligible
                else np.nan
            )
            rows.append(
                {
                    "symbol": str(source["symbol"]),
                    "as_of_date": as_of,
                    "baseline_total_score": source.get("total_score"),
                    "challenger_id": challenger["challenger_id"],
                    "challenger_score": (
                        round(float(score), 6) if np.isfinite(score) else np.nan
                    ),
                    "challenger_rank": np.nan,
                    "eligibility_status": (
                        "eligible"
                        if eligible
                        else "ineligible_missing_or_prerequisite"
                    ),
                    "missing_component_count": len(all_missing),
                    "missing_component_ids": ";".join(all_missing),
                    "research_status": "research_only",
                    "effectiveness_status": "not_evaluated",
                    "provider_access": False,
                    "labels_joined": False,
                    "production_change": False,
                    "results_are_effectiveness_evidence": False,
                }
            )
    frame = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    ranked_parts = []
    for challenger_id, group in frame.groupby("challenger_id", sort=True):
        group = group.copy()
        eligible = group[group["eligibility_status"] == "eligible"].sort_values(
            ["challenger_score", "symbol"],
            ascending=[False, True],
            kind="mergesort",
        )
        group.loc[eligible.index, "challenger_rank"] = range(1, len(eligible) + 1)
        ranked_parts.append(group)
    frame = pd.concat(ranked_parts, ignore_index=True).sort_values(
        ["challenger_id", "challenger_rank", "symbol"],
        na_position="last",
        kind="mergesort",
    ).reset_index(drop=True)
    if frame.duplicated(["symbol", "as_of_date", "challenger_id"]).any():
        _fail("invalid_execution", "Duplicate challenger output identity.")
    counts = {}
    for challenger_id, group in frame.groupby("challenger_id", sort=True):
        counts[challenger_id] = {
            "row_count": int(len(group)),
            "eligible_count": int((group["eligibility_status"] == "eligible").sum()),
            "ineligible_count": int((group["eligibility_status"] != "eligible").sum()),
        }
    report = {
        "status": "safe",
        "as_of_date": as_of,
        "input_symbol_count": int(matrix["symbol"].nunique()),
        "challenger_count": len(config["challengers"]),
        "challenger_row_count": len(frame),
        "challenger_counts": counts,
        "duplicate_count": 0,
        "boolean_cohort_truncation": False,
        "top_n_preview_is_effectiveness_evidence": False,
        "provider_access": False,
        "labels_joined": False,
        "production_change": False,
        "results_are_effectiveness_evidence": False,
        "dry_run": True,
        "outputs_written": False,
    }
    return ChallengerResult(frame=frame, report=report)


def write_challenger_outputs(
    result: ChallengerResult,
    *,
    outputs_dir: str | Path,
) -> dict[str, str]:
    root = Path(outputs_dir)
    if root.name.lower() in {"daily", "lists", "validation", "labels"}:
        _fail("invalid_execution", "Cannot overwrite production or validation output paths.")
    research = root / "research"
    research.mkdir(parents=True, exist_ok=True)
    as_of = result.report["as_of_date"]
    csv_path = research / f"production_candidate_challengers_{as_of}.csv"
    json_path = research / f"production_candidate_challengers_{as_of}.json"
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


def _validate_feature_matrix(
    matrix: pd.DataFrame,
    feature_config: Mapping[str, Any],
    feature_config_path: str | Path,
) -> None:
    if matrix.empty:
        _fail("insufficient_data", "Feature matrix is empty.")
    columns = {str(column).lower() for column in matrix.columns}
    forbidden_exact = sorted(columns & FORBIDDEN_LABEL_COLUMNS)
    forbidden_patterns = sorted(
        {
            pattern
            for column in columns
            for pattern in FORBIDDEN_COLUMN_PATTERNS
            if pattern in column
        }
    )
    if forbidden_exact or forbidden_patterns:
        _fail(
            "invalid_execution",
            "Feature matrix contains label or future-outcome columns.",
            forbidden_columns=forbidden_exact,
            forbidden_patterns=forbidden_patterns,
        )
    required = {
        "symbol",
        "as_of_date",
        "feature_schema_version",
        "feature_config_sha256",
        "provider_access",
        "labels_joined",
        "production_change",
    }
    missing = sorted(required - set(matrix.columns))
    if missing:
        _fail("invalid_execution", "Feature matrix provenance is incomplete.")
    if matrix["as_of_date"].astype(str).nunique() != 1:
        _fail("invalid_execution", "Mixed as-of dates require unsupported multi-date mode.")
    if set(matrix["feature_schema_version"].astype(str)) != {FEATURE_SCHEMA_VERSION}:
        _fail("invalid_execution", "Feature schema version mismatch.")
    if set(matrix["feature_config_sha256"].astype(str)) != {
        sha256_file(feature_config_path)
    }:
        _fail("invalid_execution", "Feature config digest mismatch.")
    if matrix.duplicated(["symbol", "as_of_date"]).any():
        _fail("invalid_execution", "Duplicate feature row identity.")
    if not _all_false(matrix["provider_access"]):
        _fail("invalid_execution", "Provider access is forbidden.")
    if not _all_false(matrix["labels_joined"]):
        _fail("invalid_execution", "labels_joined must be false.")
    if not _all_false(matrix["production_change"]):
        _fail("invalid_execution", "production_change must be false.")
    registered = set(feature_config["output_feature_columns"])
    allowed = set(feature_config["output_identity_columns"]) | registered
    unexpected = sorted(set(matrix.columns) - allowed)
    if unexpected:
        _fail(
            "invalid_execution",
            "Feature matrix contains unregistered columns.",
            unexpected_columns=unexpected,
        )


def _equals(actual: Any, expected: Any) -> bool:
    if isinstance(expected, bool):
        if isinstance(actual, bool):
            return actual is expected
        return str(actual).strip().lower() == str(expected).lower()
    return str(actual) == str(expected)


def _all_false(series: pd.Series) -> bool:
    return series.map(
        lambda value: value is False
        or str(value).strip().lower() in {"false", "0"}
    ).all()


def _read_json_object(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProductionCandidateChallengerError(
            "invalid_execution",
            "Challenger config is missing or invalid JSON.",
        ) from exc
    if not isinstance(value, dict):
        _fail("invalid_execution", "Challenger config must be a JSON object.")
    return value


def _json_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return frame.astype(object).where(pd.notna(frame), None).to_dict(orient="records")


def _require_values(actual: Mapping[str, Any], expected: Mapping[str, Any], message: str) -> None:
    mismatches = {
        key: {"expected": value, "actual": actual.get(key)}
        for key, value in expected.items()
        if actual.get(key) != value
    }
    if mismatches:
        _fail("invalid_execution", message, mismatches=mismatches)


def _fail(status: str, message: str, **details: Any) -> None:
    raise ProductionCandidateChallengerError(status, message, details=details)
