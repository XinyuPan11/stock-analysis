"""Fail-closed Phase 4.1 production-candidate research foundation audit.

This module validates static manifests and registries only. It does not import
or invoke production scoring, build features or labels, access a provider,
train a model, or run a backtest.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping


BASELINE_SCHEMA_VERSION = "production-candidate-baseline-manifest-v1"
FOUNDATION_SCHEMA_VERSION = (
    "production-candidate-research-foundation-config-v1"
)
BASELINE_ID = "current-production-candidate-baseline"
BASELINE_VERSION = "production-candidate-baseline-v1"
FOUNDATION_ID = "production-candidate-research-foundation"
FOUNDATION_VERSION = "phase4.1-v1"
FEATURE_SCHEMA_VERSION = "production_candidate_feature_matrix.v1"
LABEL_SCHEMA_VERSION = "production_candidate_label_matrix.v1"
BENCHMARK = "CSI300"
SUPPORTED_HORIZONS = (5, 10, 20)

ALLOWED_FEATURE_STATUSES = frozenset(
    {
        "existing_production",
        "candidate_research_only",
        "risk_feature_research_only",
        "unavailable",
        "rejected_due_to_leakage",
        "requires_external_data",
    }
)
ALLOWED_RESULT_STATUSES = (
    "rejected",
    "research_only",
    "shadow_test_eligible",
    "production_design_eligible",
    "invalid_execution",
    "insufficient_data",
)
PRIVILEGED_LABEL_FEATURE_IDS = frozenset(
    {
        "winner",
        "loser",
        "right_tail",
        "severe_drawdown",
        "valid_label",
        "missing_label_reason",
    }
)
FORBIDDEN_FEATURE_PATTERNS = (
    "future_return",
    "benchmark_return",
    "excess_return",
    "max_upside",
    "future_window",
    "post_window_outcome",
    "validation_result_status",
    "answer_key_conclusion",
    "cohort_effectiveness",
    "production_decision_from_later_date",
)
ANSWER_KEY_WINDOWS = frozenset(
    {"2024-01-31", "2024-04-30", "2024-07-31", "2024-10-31"}
)
U1_WINDOWS = frozenset(
    {"2024-02-29", "2024-05-31", "2024-08-30", "2024-11-29"}
)
U2_WINDOWS = frozenset(
    {"2025-02-28", "2025-05-30", "2025-08-29", "2025-11-28"}
)
HISTORICAL_H1H5_WINDOWS = frozenset(
    {"2026-01-30", "2026-03-31", "2026-04-30"}
)
CONSUMED_WINDOWS = (
    ANSWER_KEY_WINDOWS | U1_WINDOWS | U2_WINDOWS | HISTORICAL_H1H5_WINDOWS
)
U3_WINDOWS = frozenset({"2026-09-30", "2026-12-31"})
U3_IDENTITY = "u3-prospective-2026-h2-v1"
EXPECTED_AUDIT_PATH = (
    "outputs/research/production_candidate_foundation_audit.json"
)
REQUIRED_FEATURE_FIELDS = frozenset(
    {
        "feature_id",
        "feature_family",
        "description",
        "source_fields",
        "lookback_requirement",
        "point_in_time_rule",
        "missing_value_policy",
        "expected_direction",
        "type",
        "production_status",
        "current_availability",
        "leakage_risk",
        "implementation_status",
    }
)
REQUIRED_FEATURE_IDENTITY_FIELDS = frozenset(
    {
        "dataset_version",
        "symbol",
        "as_of_date",
        "latest_input_date",
        "universe_id",
        "source_snapshot_id",
        "feature_schema_version",
        "production_baseline_version",
        "provider_access",
        "labels_joined",
        "leakage_guard_applied",
    }
)

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_BASELINE_PATH = (
    REPO_ROOT / "research" / "configs"
    / "production_candidate_baseline.v1.json"
)
DEFAULT_FOUNDATION_PATH = (
    REPO_ROOT / "research" / "configs"
    / "production_candidate_research_foundation.v1.json"
)


class ProductionCandidateFoundationError(ValueError):
    """Structured fail-closed audit error."""

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


def load_json_object(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProductionCandidateFoundationError(
            "invalid_execution",
            "Foundation input is missing or invalid JSON.",
            details={"path": str(source)},
        ) from exc
    if not isinstance(value, dict):
        _fail("invalid_execution", "Foundation input must be a JSON object.")
    return value


def load_baseline_manifest(
    path: str | Path = DEFAULT_BASELINE_PATH,
    *,
    repo_root: str | Path = REPO_ROOT,
) -> dict[str, Any]:
    payload = load_json_object(path)
    validate_baseline_manifest(payload, repo_root=repo_root)
    return payload


def load_foundation_config(
    path: str | Path = DEFAULT_FOUNDATION_PATH,
    *,
    repo_root: str | Path = REPO_ROOT,
) -> dict[str, Any]:
    payload = load_json_object(path)
    validate_foundation_config(payload, repo_root=repo_root)
    return payload


def validate_baseline_manifest(
    payload: Mapping[str, Any],
    *,
    repo_root: str | Path = REPO_ROOT,
) -> None:
    expected = {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "baseline_id": BASELINE_ID,
        "baseline_version": BASELINE_VERSION,
        "benchmark": BENCHMARK,
        "production_change": False,
    }
    _require_values(payload, expected, "Baseline identity or safety flag drifted.")
    commit = str(payload.get("captured_from_commit", ""))
    branch = str(payload.get("captured_on_branch", "")).strip()
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None or not branch:
        _fail(
            "invalid_execution",
            "Baseline manifest lacks immutable commit or branch provenance.",
        )

    root = Path(repo_root).resolve()
    referenced = []
    for key in (
        "scoring_module_paths",
        "candidate_module_paths",
        "workflow_module_paths",
    ):
        paths = payload.get(key)
        if not isinstance(paths, list) or not paths:
            _fail("invalid_execution", f"Baseline {key} must be non-empty.")
        referenced.extend(str(item) for item in paths)
    missing_paths = [
        path for path in referenced if not (root / path).is_file()
    ]
    if missing_paths:
        _fail(
            "invalid_execution",
            "Baseline references code paths that do not exist.",
            missing_paths=missing_paths,
        )

    scoring = _mapping(payload, "scoring_contract")
    components = scoring.get("components")
    if not isinstance(components, list) or not components:
        _fail("invalid_execution", "Baseline scoring components are missing.")
    component_ids = [str(item.get("factor_id", "")) for item in components]
    if len(component_ids) != len(set(component_ids)):
        _fail("invalid_execution", "Baseline factor identifiers are duplicated.")
    total_weight = sum(float(item.get("weight", 0.0)) for item in components)
    if abs(total_weight - 100.0) > 1e-9:
        _fail(
            "invalid_execution",
            "Baseline component weights must sum to 100.",
            total_weight=total_weight,
        )
    group_weights = _mapping(scoring, "group_weights")
    by_group: dict[str, float] = {}
    for item in components:
        group = str(item.get("group", ""))
        by_group[group] = by_group.get(group, 0.0) + float(
            item.get("weight", 0.0)
        )
    if {
        key: float(value) for key, value in group_weights.items()
    } != by_group:
        _fail(
            "invalid_execution",
            "Baseline group weights do not match component weights.",
        )

    required_lists = {
        "high_confidence_candidates",
        "trend_leaders",
        "long_term_stable",
        "breakout_watch",
        "accumulation_watch",
        "rebound_watch",
        "high_risk_active",
        "insufficient_data",
    }
    lists = _mapping(payload, "list_generation_rules")
    if set(lists) != required_lists:
        _fail(
            "invalid_execution",
            "Baseline list-generation registry is incomplete.",
        )


def validate_foundation_config(
    payload: Mapping[str, Any],
    *,
    repo_root: str | Path = REPO_ROOT,
) -> None:
    expected = {
        "schema_version": FOUNDATION_SCHEMA_VERSION,
        "foundation_id": FOUNDATION_ID,
        "foundation_version": FOUNDATION_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "label_schema_version": LABEL_SCHEMA_VERSION,
        "benchmark": BENCHMARK,
        "provider_access": False,
        "labels_joined": False,
        "production_change": False,
        "audit_output_path": EXPECTED_AUDIT_PATH,
    }
    _require_values(payload, expected, "Foundation identity or safety flag drifted.")
    if tuple(payload.get("supported_horizons", ())) != SUPPORTED_HORIZONS:
        _fail("invalid_execution", "Supported horizons must be 5D, 10D, 20D.")

    baseline_path = str(payload.get("baseline_manifest_path", ""))
    if baseline_path != "research/configs/production_candidate_baseline.v1.json":
        _fail("invalid_execution", "Baseline manifest path drifted.")
    if not (Path(repo_root).resolve() / baseline_path).is_file():
        _fail("invalid_execution", "Referenced baseline manifest does not exist.")

    identities = payload.get("feature_identity_fields")
    if not isinstance(identities, list) or set(identities) != (
        REQUIRED_FEATURE_IDENTITY_FIELDS
    ):
        _fail("invalid_execution", "Feature provenance fields are incomplete.")

    row_identities = _mapping(payload, "row_identities")
    if row_identities.get("feature_label_tables_separate") is not True:
        _fail(
            "invalid_execution",
            "Feature and label schemas must remain separate tables.",
        )
    if row_identities.get("feature_matrix") != ["symbol", "as_of_date"]:
        _fail("invalid_execution", "Feature row identity drifted.")
    if row_identities.get("label_matrix") != [
        "symbol",
        "as_of_date",
        "horizon_days",
    ]:
        _fail("invalid_execution", "Label row identity drifted.")

    features = payload.get("feature_registry")
    if not isinstance(features, list) or not features:
        _fail("invalid_execution", "Feature registry must be a non-empty list.")
    feature_ids: list[str] = []
    for index, feature in enumerate(features):
        if not isinstance(feature, Mapping):
            _fail("invalid_execution", "Every feature entry must be an object.")
        missing = sorted(REQUIRED_FEATURE_FIELDS - set(feature))
        if missing:
            _fail(
                "invalid_execution",
                "Feature definition lacks required provenance.",
                index=index,
                missing_fields=missing,
            )
        feature_id = str(feature.get("feature_id", "")).strip()
        if not feature_id:
            _fail("invalid_execution", "Feature ID cannot be empty.")
        feature_ids.append(feature_id)
        status = str(feature.get("production_status", ""))
        if status not in ALLOWED_FEATURE_STATUSES:
            _fail(
                "invalid_execution",
                "Unknown feature production status.",
                feature_id=feature_id,
                production_status=status,
            )
        _validate_feature_leakage(feature)
    duplicates = sorted(
        {item for item in feature_ids if feature_ids.count(item) > 1}
    )
    if duplicates:
        _fail(
            "invalid_execution",
            "Duplicate feature IDs are forbidden.",
            duplicate_feature_ids=duplicates,
        )

    label_matrix = _mapping(payload, "label_matrix")
    if label_matrix.get("schema_version") != LABEL_SCHEMA_VERSION:
        _fail("invalid_execution", "Label schema identity drifted.")
    if label_matrix.get("new_version_required") is not True:
        _fail(
            "invalid_execution",
            "Phase 4 labels must not overwrite the Phase 3.12 identity.",
        )
    if label_matrix.get("generation_in_phase4_1") is not False:
        _fail("invalid_execution", "Phase 4.1 cannot generate labels.")
    label_entries = [
        *list(label_matrix.get("continuous_labels", [])),
        *list(label_matrix.get("categorical_boolean_labels", [])),
    ]
    label_ids = {str(item.get("label_id", "")) for item in label_entries}
    if not label_ids or any(item.get("feature_eligible") is not False for item in label_entries):
        _fail(
            "invalid_execution",
            "Label entries must exist and be explicitly ineligible as features.",
        )

    _validate_data_roles(_mapping(payload, "data_roles"))

    statuses = payload.get("allowed_statuses")
    if statuses != list(ALLOWED_RESULT_STATUSES):
        _fail(
            "invalid_execution",
            "Unknown or missing production eligibility status.",
        )

    comparison = _mapping(payload, "comparison_output_contract")
    if comparison.get("production_change") is not False:
        _fail("invalid_execution", "Comparison contract cannot change production.")
    if comparison.get("generate_in_phase4_1") is not False:
        _fail("invalid_execution", "Phase 4.1 cannot generate comparisons.")

    governance = _mapping(payload, "production_governance")
    if governance.get("phase4_1_production_change_authorized") is not False:
        _fail("invalid_execution", "Phase 4.1 cannot authorize production change.")

    if set(payload.get("privileged_label_feature_ids", ())) != set(
        PRIVILEGED_LABEL_FEATURE_IDS
    ):
        _fail(
            "invalid_execution",
            "Privileged label-feature denylist drifted.",
        )
    if payload.get("forbidden_feature_patterns") != list(
        FORBIDDEN_FEATURE_PATTERNS
    ):
        _fail("invalid_execution", "Forbidden feature patterns drifted.")


def audit_production_candidate_foundation(
    *,
    repo_root: str | Path = REPO_ROOT,
    baseline_path: str | Path | None = None,
    foundation_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    baseline_source = Path(baseline_path) if baseline_path else (
        root / "research" / "configs"
        / "production_candidate_baseline.v1.json"
    )
    foundation_source = Path(foundation_path) if foundation_path else (
        root / "research" / "configs"
        / "production_candidate_research_foundation.v1.json"
    )
    baseline = load_baseline_manifest(baseline_source, repo_root=root)
    foundation = load_foundation_config(foundation_source, repo_root=root)
    return {
        "status": "safe",
        "foundation_id": foundation["foundation_id"],
        "foundation_version": foundation["foundation_version"],
        "baseline_id": baseline["baseline_id"],
        "baseline_version": baseline["baseline_version"],
        "captured_from_commit": baseline["captured_from_commit"],
        "feature_schema_version": foundation["feature_schema_version"],
        "label_schema_version": foundation["label_schema_version"],
        "feature_count": len(foundation["feature_registry"]),
        "consumed_window_count": len(
            foundation["data_roles"]["consumed_windows"]
        ),
        "reserved_window_count": len(
            foundation["data_roles"]["reserved_windows"]
        ),
        "provider_access": False,
        "labels_generated": False,
        "features_generated": False,
        "model_trained": False,
        "backtest_run": False,
        "production_modules_invoked": False,
        "production_change": False,
        "u3_changed": False,
        "dry_run": True,
        "outputs_written": False,
    }


def write_foundation_audit(
    report: Mapping[str, Any],
    *,
    outputs_dir: str | Path,
) -> str:
    output_root = Path(outputs_dir).resolve()
    research_dir = output_root / "research"
    research_dir.mkdir(parents=True, exist_ok=True)
    path = research_dir / "production_candidate_foundation_audit.json"
    payload = dict(report)
    payload["dry_run"] = False
    payload["outputs_written"] = True
    payload["output_path"] = str(path)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return str(path)


def _validate_feature_leakage(feature: Mapping[str, Any]) -> None:
    feature_id = str(feature.get("feature_id", "")).strip().lower()
    if feature_id in PRIVILEGED_LABEL_FEATURE_IDS:
        _fail(
            "invalid_execution",
            "Privileged outcome label cannot be an input feature.",
            feature_id=feature_id,
        )
    searchable = [feature_id]
    source_fields = feature.get("source_fields")
    if not isinstance(source_fields, list) or not source_fields:
        _fail(
            "invalid_execution",
            "Feature source_fields must be a non-empty list.",
            feature_id=feature_id,
        )
    searchable.extend(str(item).strip().lower() for item in source_fields)
    found = sorted(
        {
            pattern
            for value in searchable
            for pattern in FORBIDDEN_FEATURE_PATTERNS
            if pattern in value
        }
    )
    if found:
        _fail(
            "invalid_execution",
            "Future or outcome-derived input feature is forbidden.",
            feature_id=feature_id,
            forbidden_patterns=found,
        )
    rule = str(feature.get("point_in_time_rule", "")).strip()
    if "<= as_of_date" not in rule or "> as_of_date" in rule:
        _fail(
            "invalid_execution",
            "Feature dependency is not point-in-time safe.",
            feature_id=feature_id,
            point_in_time_rule=rule,
        )


def _validate_data_roles(data_roles: Mapping[str, Any]) -> None:
    consumed = data_roles.get("consumed_windows")
    if not isinstance(consumed, list):
        _fail("invalid_execution", "Consumed-window registry is missing.")
    consumed_dates = {str(item.get("as_of_date", "")) for item in consumed}
    if consumed_dates != CONSUMED_WINDOWS:
        _fail(
            "invalid_execution",
            "Consumed-window registry drifted.",
            missing=sorted(CONSUMED_WINDOWS - consumed_dates),
            unexpected=sorted(consumed_dates - CONSUMED_WINDOWS),
        )
    invalid_roles = [
        item
        for item in consumed
        if item.get("role") != "consumed_diagnostic_only"
    ]
    if invalid_roles:
        _fail(
            "invalid_execution",
            "Consumed windows cannot be described as fresh unseen evidence.",
        )

    reserved = data_roles.get("reserved_windows")
    if not isinstance(reserved, list):
        _fail("invalid_execution", "Reserved-window registry is missing.")
    reserved_dates = {str(item.get("as_of_date", "")) for item in reserved}
    if reserved_dates != U3_WINDOWS:
        _fail("invalid_execution", "U3 reserved dates were reassigned or changed.")
    for item in reserved:
        if (
            item.get("source_identity") != U3_IDENTITY
            or item.get("role") != "reserved_prospective_other_identity"
            or item.get("reassignable_to_phase4") is not False
        ):
            _fail(
                "invalid_execution",
                "U3 identity or reservation was reassigned.",
            )

    holdout = _mapping(data_roles, "phase4_future_holdout")
    if holdout.get("status") != "not_selected" or holdout.get(
        "selected_windows"
    ) != []:
        _fail(
            "invalid_execution",
            "Phase 4.1 must not select a future Phase 4 holdout.",
        )


def _mapping(parent: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = parent.get(key)
    if not isinstance(value, Mapping):
        _fail("invalid_execution", f"Section {key} must be an object.")
    return value


def _require_values(
    actual: Mapping[str, Any],
    expected: Mapping[str, Any],
    message: str,
) -> None:
    mismatches = {
        key: {"expected": value, "actual": actual.get(key)}
        for key, value in expected.items()
        if actual.get(key) != value
    }
    if mismatches:
        _fail("invalid_execution", message, mismatches=mismatches)


def _fail(status: str, message: str, **details: Any) -> None:
    raise ProductionCandidateFoundationError(
        status,
        message,
        details=details,
    )
