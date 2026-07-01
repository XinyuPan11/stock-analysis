"""Fail-closed U3 H1-H5 execution readiness checks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from stock_analysis.research.feature_only_snapshot import (
    FeatureOnlySnapshotError,
    build_feature_only_snapshot,
    load_member_snapshot,
)
from stock_analysis.research.opportunity_cohorts import (
    COHORT_PARAMETERS,
    COHORT_ROLES,
    OpportunityCohortBuildError,
    load_opportunity_cohort_config,
    validate_opportunity_cohort_config,
)


U3_HOLDOUT_ID = "u3-prospective-2026-h2-v1"
U3_SOURCE_CONFIG_VERSION = "phase3.1-smoke-v1"
U3_WINDOWS: tuple[str, ...] = ("2026-09-30", "2026-12-31")
U3_CONFIG_FILENAMES = {
    date: f"opportunity_cohorts.u3_{date}.json"
    for date in U3_WINDOWS
}
SOURCE_CONFIG_FILENAME = "opportunity_cohorts.phase3_1_smoke.json"


def parameter_block(config: Mapping[str, Any]) -> dict[str, Any]:
    cohorts = config.get("cohorts")
    if not isinstance(cohorts, Mapping):
        raise ValueError("Config does not contain a cohort mapping.")
    block: dict[str, Any] = {}
    for cohort_id in COHORT_ROLES:
        cohort = cohorts.get(cohort_id)
        if not isinstance(cohort, Mapping):
            raise ValueError(f"Missing cohort: {cohort_id}.")
        parameters = cohort.get("parameters")
        expected = COHORT_PARAMETERS[cohort_id]
        if not isinstance(parameters, Mapping) or set(parameters) != set(
            expected
        ):
            raise ValueError(f"Invalid parameter block: {cohort_id}.")
        block[cohort_id] = {
            name: parameters[name] for name in expected
        }
    return block


def parameter_digest(config: Mapping[str, Any]) -> str:
    return _digest(parameter_block(config))


def frozen_logic_digest(config: Mapping[str, Any]) -> str:
    cohorts = config.get("cohorts")
    if not isinstance(cohorts, Mapping):
        raise ValueError("Config does not contain a cohort mapping.")
    logic = {
        "feature_bindings": config.get("feature_bindings"),
        "cohorts": {
            cohort_id: {
                "role": cohorts[cohort_id].get("role"),
                "parameters": parameter_block(config)[cohort_id],
            }
            for cohort_id in COHORT_ROLES
        },
    }
    return _digest(logic)


def parameter_count(config: Mapping[str, Any]) -> int:
    return sum(len(values) for values in parameter_block(config).values())


def check_u3_window_readiness(
    *,
    expected_as_of_date: str,
    source_config_path: str | Path,
    u3_config_path: str | Path,
    feature_only_snapshot_path: str | Path | None,
) -> dict[str, Any]:
    source_path = Path(source_config_path)
    config_path = Path(u3_config_path)
    snapshot_path = (
        Path(feature_only_snapshot_path)
        if feature_only_snapshot_path is not None
        else None
    )
    base = {
        "ready": False,
        "research_only": True,
        "provider_access": False,
        "labels_joined": False,
        "production_change": False,
        "validation_run": False,
        "future_labels_joined": False,
        "expected_as_of_date": expected_as_of_date,
        "source_config_path": str(source_path),
        "u3_config_path": str(config_path),
        "feature_only_snapshot_path": (
            str(snapshot_path) if snapshot_path is not None else None
        ),
        "holdout_id": U3_HOLDOUT_ID,
    }

    if expected_as_of_date not in U3_WINDOWS:
        return _blocked(
            base,
            "blocked_unknown_u3_window",
            "Expected as_of_date is not a preregistered U3 window.",
        )
    if not source_path.exists():
        return _blocked(
            base,
            "blocked_missing_source_config",
            "Phase 3.1 source config is missing.",
        )
    if not config_path.exists():
        return _blocked(
            base,
            "blocked_missing_u3_config",
            "Date-bound U3 config is missing.",
        )

    try:
        source_config = load_opportunity_cohort_config(source_path)
        u3_config = load_opportunity_cohort_config(config_path)
    except OpportunityCohortBuildError as exc:
        return _blocked(
            base,
            "blocked_invalid_config_file",
            exc.message,
            details={"config_status": exc.status},
        )

    if str(u3_config.get("as_of_date")) != expected_as_of_date:
        return _blocked(
            base,
            "blocked_wrong_as_of_date",
            "U3 config as_of_date does not match its preregistered window.",
            details={"actual_as_of_date": u3_config.get("as_of_date")},
        )

    metadata_error = _date_binding_metadata_error(u3_config)
    if metadata_error:
        return _blocked(
            base,
            metadata_error[0],
            metadata_error[1],
        )

    source_holdout = (
        source_config.get("preregistration", {})
        .get("intended_future_validation_holdout")
    )
    u3_holdout = (
        u3_config.get("preregistration", {})
        .get("intended_future_validation_holdout")
    )
    if (
        u3_config.get("holdout_id") != U3_HOLDOUT_ID
        or not isinstance(u3_holdout, Mapping)
        or u3_holdout.get("holdout_id") != U3_HOLDOUT_ID
        or u3_holdout != source_holdout
    ):
        return _blocked(
            base,
            "blocked_holdout_contract_mismatch",
            "U3 holdout contract does not match Phase 3.3.",
        )

    try:
        validate_opportunity_cohort_config(
            source_config,
            as_of_date=str(source_config.get("as_of_date")),
            mode="execution",
        )
        validate_opportunity_cohort_config(
            u3_config,
            as_of_date=expected_as_of_date,
            mode="execution",
        )
    except OpportunityCohortBuildError as exc:
        return _blocked(
            base,
            "blocked_invalid_execution_config",
            exc.message,
            details={"config_status": exc.status},
        )

    try:
        source_parameter_digest = parameter_digest(source_config)
        config_parameter_digest = parameter_digest(u3_config)
        source_logic_digest = frozen_logic_digest(source_config)
        config_logic_digest = frozen_logic_digest(u3_config)
        count = parameter_count(u3_config)
    except (KeyError, TypeError, ValueError) as exc:
        return _blocked(
            base,
            "blocked_invalid_parameter_block",
            str(exc),
        )

    digest_metadata = {
        "parameter_count": count,
        "source_parameter_digest": source_parameter_digest,
        "config_parameter_digest": config_parameter_digest,
        "source_frozen_logic_digest": source_logic_digest,
        "config_frozen_logic_digest": config_logic_digest,
    }
    if count != 18 or source_parameter_digest != config_parameter_digest:
        return _blocked(
            {**base, **digest_metadata},
            "blocked_parameter_checksum_mismatch",
            "U3 parameter block differs from phase3.1-smoke-v1.",
        )
    if source_logic_digest != config_logic_digest:
        return _blocked(
            {**base, **digest_metadata},
            "blocked_frozen_logic_checksum_mismatch",
            "U3 roles or feature bindings differ from the frozen source.",
        )
    if u3_config.get("parameter_documentation") != source_config.get(
        "parameter_documentation"
    ):
        return _blocked(
            {**base, **digest_metadata},
            "blocked_parameter_documentation_mismatch",
            "U3 parameter documentation differs from the frozen source.",
        )

    if snapshot_path is None or not snapshot_path.exists():
        return _blocked(
            {**base, **digest_metadata},
            "blocked_missing_feature_only_snapshot",
            "U3 feature-only snapshot is missing; provider access is forbidden.",
        )

    try:
        snapshot = load_member_snapshot(snapshot_path)
        checked_snapshot = build_feature_only_snapshot(
            snapshot,
            as_of_date=expected_as_of_date,
            source_snapshot_path=snapshot_path,
            drop_outcome_columns=False,
        )
    except FeatureOnlySnapshotError as exc:
        return _blocked(
            {**base, **digest_metadata},
            "blocked_invalid_feature_only_snapshot",
            exc.message,
            details={"snapshot_status": exc.status, **exc.details},
        )

    minimum_rows = int(u3_holdout["minimum_valid_sample_per_window"])
    row_count = int(checked_snapshot.metadata["output_row_count"])
    if row_count < minimum_rows:
        return _blocked(
            {
                **base,
                **digest_metadata,
                "feature_only_row_count": row_count,
                "minimum_valid_sample_per_window": minimum_rows,
            },
            "blocked_insufficient_feature_only_sample",
            "Feature-only universe is below the preregistered sample gate.",
        )

    return {
        **base,
        **digest_metadata,
        "status": "ready",
        "message": (
            "Config, checksum, and feature-only snapshot are ready for a "
            "separate label-free builder dry-run."
        ),
        "ready": True,
        "feature_only": True,
        "feature_only_row_count": row_count,
        "minimum_valid_sample_per_window": minimum_rows,
        "leakage_guard_applied": True,
    }


def check_u3_readiness(
    repo_root: str | Path,
    *,
    snapshot_dir: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    config_dir = root / "research" / "configs"
    resolved_snapshot_dir = (
        Path(snapshot_dir).resolve()
        if snapshot_dir is not None
        else root / "research" / "inputs"
    )
    source_path = config_dir / SOURCE_CONFIG_FILENAME
    windows = [
        check_u3_window_readiness(
            expected_as_of_date=date,
            source_config_path=source_path,
            u3_config_path=config_dir / U3_CONFIG_FILENAMES[date],
            feature_only_snapshot_path=(
                resolved_snapshot_dir
                / f"member_level_asof_features_{date}.csv"
            ),
        )
        for date in U3_WINDOWS
    ]
    all_ready = all(window["ready"] for window in windows)
    digests = {
        window.get("source_parameter_digest")
        for window in windows
        if window.get("source_parameter_digest")
    }
    return {
        "status": "ready" if all_ready else "blocked",
        "ready": all_ready,
        "research_only": True,
        "provider_access": False,
        "labels_joined": False,
        "production_change": False,
        "validation_run": False,
        "future_labels_joined": False,
        "holdout_id": U3_HOLDOUT_ID,
        "source_config_version": U3_SOURCE_CONFIG_VERSION,
        "parameter_digest": next(iter(digests)) if len(digests) == 1 else None,
        "window_count": len(windows),
        "ready_window_count": sum(window["ready"] for window in windows),
        "blocked_window_count": sum(not window["ready"] for window in windows),
        "windows": windows,
    }


def _date_binding_metadata_error(
    config: Mapping[str, Any],
) -> tuple[str, str] | None:
    checks = (
        (
            config.get("research_only") is True,
            "blocked_not_research_only",
            "U3 config must declare research_only=true.",
        ),
        (
            config.get("provider_access") is False,
            "blocked_provider_access_not_false",
            "U3 config must declare provider_access=false.",
        ),
        (
            config.get("labels_joined") is False,
            "blocked_labels_joined",
            "U3 config must declare labels_joined=false.",
        ),
        (
            config.get("production_change") is False,
            "blocked_production_change",
            "U3 config must declare production_change=false.",
        ),
        (
            config.get("copied_from") == U3_SOURCE_CONFIG_VERSION,
            "blocked_invalid_copied_from",
            "U3 config must identify phase3.1-smoke-v1 as its source.",
        ),
        (
            config.get("parameter_change") is False,
            "blocked_parameter_change",
            "U3 config must declare parameter_change=false.",
        ),
        (
            config.get("tuning_change") is False,
            "blocked_tuning_change",
            "U3 config must declare tuning_change=false.",
        ),
        (
            config.get("date_binding_only_change") is True,
            "blocked_not_date_binding_only",
            "U3 config must declare date_binding_only_change=true.",
        ),
    )
    for passed, status, message in checks:
        if not passed:
            return status, message
    return None


def _blocked(
    base: Mapping[str, Any],
    status: str,
    message: str,
    *,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        **base,
        "status": status,
        "message": message,
        "details": dict(details or {}),
    }


def _digest(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
