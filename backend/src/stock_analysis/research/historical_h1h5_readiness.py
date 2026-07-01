"""Fail-closed readiness for historical sealed H1-H5 research windows."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from stock_analysis.research.feature_only_snapshot import (
    FeatureOnlySnapshotError,
    build_feature_only_snapshot,
    load_member_snapshot,
)
from stock_analysis.research.opportunity_cohorts import (
    OpportunityCohortBuildError,
    load_opportunity_cohort_config,
    validate_opportunity_cohort_config,
)
from stock_analysis.research.u3_readiness import (
    frozen_logic_digest,
    parameter_count,
    parameter_digest,
)


HISTORICAL_VALIDATION_ID = "h1h5-historical-sealed-v1"
HISTORICAL_EVIDENCE_LEVEL = "historical_sealed_not_prospective"
HISTORICAL_SOURCE_CONFIG_VERSION = "phase3.1-smoke-v1"
HISTORICAL_PRIMARY_WINDOWS: tuple[str, ...] = (
    "2026-01-30",
    "2026-03-31",
    "2026-04-30",
)
HISTORICAL_BACKUP_WINDOWS: tuple[str, ...] = (
    "2026-02-27",
    "2026-05-29",
)
HISTORICAL_WINDOWS: tuple[str, ...] = (
    *HISTORICAL_PRIMARY_WINDOWS,
    *HISTORICAL_BACKUP_WINDOWS,
)
HISTORICAL_WINDOW_IDS: tuple[str, ...] = tuple(
    f"historical_{date}_20d" for date in HISTORICAL_WINDOWS
)
HISTORICAL_CONFIG_FILENAMES = {
    date: f"opportunity_cohorts.historical_{date}.json"
    for date in HISTORICAL_WINDOWS
}
HISTORICAL_EXCLUDED_WINDOWS: frozenset[str] = frozenset(
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
SOURCE_CONFIG_FILENAME = "opportunity_cohorts.phase3_1_smoke.json"
MINIMUM_VALID_UNIVERSE_ROWS = 100


def check_historical_window_readiness(
    *,
    expected_as_of_date: str,
    source_config_path: str | Path,
    historical_config_path: str | Path,
    source_snapshot_path: str | Path | None,
    feature_only_snapshot_path: str | Path | None,
) -> dict[str, Any]:
    source_config = Path(source_config_path)
    historical_config = Path(historical_config_path)
    source_snapshot = (
        Path(source_snapshot_path) if source_snapshot_path is not None else None
    )
    feature_snapshot = (
        Path(feature_only_snapshot_path)
        if feature_only_snapshot_path is not None
        else None
    )
    window_kind = (
        "primary"
        if expected_as_of_date in HISTORICAL_PRIMARY_WINDOWS
        else "backup"
        if expected_as_of_date in HISTORICAL_BACKUP_WINDOWS
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
        "validation_outputs_read": False,
        "validation_id": HISTORICAL_VALIDATION_ID,
        "evidence_level": HISTORICAL_EVIDENCE_LEVEL,
        "expected_as_of_date": expected_as_of_date,
        "window_kind": window_kind,
        "source_config_path": str(source_config),
        "historical_config_path": str(historical_config),
        "source_snapshot_path": (
            str(source_snapshot) if source_snapshot is not None else None
        ),
        "feature_only_snapshot_path": (
            str(feature_snapshot) if feature_snapshot is not None else None
        ),
        "backup_activation_required": window_kind == "backup",
        "requires_complete_20d_future_coverage_without_provider_fetch": (
            expected_as_of_date == "2026-05-29"
        ),
    }

    if expected_as_of_date in HISTORICAL_EXCLUDED_WINDOWS:
        return _blocked(
            base,
            "blocked_excluded_window",
            "The date is consumed evidence or reserved for prospective U3.",
        )
    if expected_as_of_date not in HISTORICAL_WINDOWS:
        return _blocked(
            base,
            "blocked_unknown_historical_window",
            "The date is not preregistered for historical sealed validation.",
        )
    if not source_config.exists():
        return _blocked(
            base,
            "blocked_missing_source_config",
            "The phase3.1-smoke-v1 source config is missing.",
        )
    if not historical_config.exists():
        return _blocked(
            base,
            "blocked_missing_historical_config",
            "The date-bound historical config is missing.",
        )

    try:
        frozen_source = load_opportunity_cohort_config(source_config)
        config = load_opportunity_cohort_config(historical_config)
    except OpportunityCohortBuildError as exc:
        return _blocked(
            base,
            "blocked_invalid_config_file",
            exc.message,
            details={"config_status": exc.status},
        )

    if str(config.get("as_of_date")) != expected_as_of_date:
        return _blocked(
            base,
            "blocked_wrong_as_of_date",
            "Historical config as_of_date does not match the requested window.",
            details={"actual_as_of_date": config.get("as_of_date")},
        )

    metadata_error = _historical_metadata_error(config)
    if metadata_error:
        return _blocked(base, metadata_error[0], metadata_error[1])

    holdout_error = _historical_holdout_error(config)
    if holdout_error:
        return _blocked(base, holdout_error[0], holdout_error[1])

    try:
        validate_opportunity_cohort_config(
            frozen_source,
            as_of_date=str(frozen_source.get("as_of_date")),
            mode="execution",
        )
        validate_opportunity_cohort_config(
            config,
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
        source_parameter_digest = parameter_digest(frozen_source)
        config_parameter_digest = parameter_digest(config)
        source_logic_digest = frozen_logic_digest(frozen_source)
        config_logic_digest = frozen_logic_digest(config)
        count = parameter_count(config)
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
            "Historical parameter block differs from phase3.1-smoke-v1.",
        )
    if source_logic_digest != config_logic_digest:
        return _blocked(
            {**base, **digest_metadata},
            "blocked_frozen_logic_checksum_mismatch",
            "Historical roles or feature bindings differ from the source.",
        )
    if config.get("parameter_documentation") != frozen_source.get(
        "parameter_documentation"
    ):
        return _blocked(
            {**base, **digest_metadata},
            "blocked_parameter_documentation_mismatch",
            "Historical parameter documentation differs from the source.",
        )

    if source_snapshot is None or not source_snapshot.exists():
        return _blocked(
            {**base, **digest_metadata},
            "blocked_missing_source_snapshot",
            "Local source snapshot is missing; provider access is forbidden.",
        )
    if feature_snapshot is None or not feature_snapshot.exists():
        return _blocked(
            {**base, **digest_metadata},
            "blocked_missing_feature_only_snapshot",
            "Feature-only snapshot is missing; no file is generated by readiness.",
        )

    try:
        snapshot = load_member_snapshot(feature_snapshot)
        checked_snapshot = build_feature_only_snapshot(
            snapshot,
            as_of_date=expected_as_of_date,
            source_snapshot_path=feature_snapshot,
            drop_outcome_columns=False,
        )
    except FeatureOnlySnapshotError as exc:
        return _blocked(
            {**base, **digest_metadata},
            "blocked_invalid_feature_only_snapshot",
            exc.message,
            details={"snapshot_status": exc.status, **exc.details},
        )

    row_count = int(checked_snapshot.metadata["output_row_count"])
    if row_count < MINIMUM_VALID_UNIVERSE_ROWS:
        return _blocked(
            {
                **base,
                **digest_metadata,
                "feature_only_row_count": row_count,
                "minimum_valid_universe_rows": MINIMUM_VALID_UNIVERSE_ROWS,
            },
            "blocked_insufficient_feature_only_sample",
            "Feature-only universe is below the preregistered 100-row gate.",
        )

    return {
        **base,
        **digest_metadata,
        "status": "ready",
        "message": (
            "Config, checksums, and feature-only snapshot are ready for a "
            "separately approved label-free builder dry-run."
        ),
        "ready": True,
        "feature_only": True,
        "feature_only_row_count": row_count,
        "minimum_valid_universe_rows": MINIMUM_VALID_UNIVERSE_ROWS,
        "leakage_guard_applied": True,
    }


def check_historical_readiness(
    repo_root: str | Path,
    *,
    source_snapshot_paths: Mapping[str, str | Path] | None = None,
    feature_snapshot_dir: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    config_dir = root / "research" / "configs"
    resolved_feature_dir = (
        Path(feature_snapshot_dir).resolve()
        if feature_snapshot_dir is not None
        else root / "research" / "inputs"
    )
    supplied_sources = dict(source_snapshot_paths or {})
    source_config = config_dir / SOURCE_CONFIG_FILENAME
    windows: list[dict[str, Any]] = []
    for date in HISTORICAL_WINDOWS:
        source_snapshot = supplied_sources.get(
            date,
            root
            / "outputs"
            / "experiments"
            / f"member_level_asof_snapshot_{date}.csv",
        )
        windows.append(
            check_historical_window_readiness(
                expected_as_of_date=date,
                source_config_path=source_config,
                historical_config_path=(
                    config_dir / HISTORICAL_CONFIG_FILENAMES[date]
                ),
                source_snapshot_path=source_snapshot,
                feature_only_snapshot_path=(
                    resolved_feature_dir
                    / f"member_level_asof_features_{date}.csv"
                ),
            )
        )

    primary_windows = [
        window
        for window in windows
        if window["expected_as_of_date"] in HISTORICAL_PRIMARY_WINDOWS
    ]
    backup_windows = [
        window
        for window in windows
        if window["expected_as_of_date"] in HISTORICAL_BACKUP_WINDOWS
    ]
    primary_ready = all(window["ready"] for window in primary_windows)
    digests = {
        window.get("source_parameter_digest")
        for window in windows
        if window.get("source_parameter_digest")
    }
    return {
        "status": "ready" if primary_ready else "blocked",
        "ready": primary_ready,
        "research_only": True,
        "provider_access": False,
        "labels_joined": False,
        "production_change": False,
        "validation_run": False,
        "future_labels_joined": False,
        "validation_outputs_read": False,
        "validation_id": HISTORICAL_VALIDATION_ID,
        "evidence_level": HISTORICAL_EVIDENCE_LEVEL,
        "source_config_version": HISTORICAL_SOURCE_CONFIG_VERSION,
        "parameter_digest": next(iter(digests)) if len(digests) == 1 else None,
        "window_count": len(windows),
        "primary_window_count": len(primary_windows),
        "ready_primary_window_count": sum(
            window["ready"] for window in primary_windows
        ),
        "backup_window_count": len(backup_windows),
        "ready_backup_window_count": sum(
            window["ready"] for window in backup_windows
        ),
        "windows": windows,
    }


def _historical_metadata_error(
    config: Mapping[str, Any],
) -> tuple[str, str] | None:
    checks = (
        (
            config.get("research_only") is True,
            "blocked_not_research_only",
            "Historical config must declare research_only=true.",
        ),
        (
            config.get("provider_access") is False,
            "blocked_provider_access_not_false",
            "Historical config must declare provider_access=false.",
        ),
        (
            config.get("labels_joined") is False,
            "blocked_labels_joined",
            "Historical config must declare labels_joined=false.",
        ),
        (
            config.get("production_change") is False,
            "blocked_production_change",
            "Historical config must declare production_change=false.",
        ),
        (
            config.get("copied_from") == HISTORICAL_SOURCE_CONFIG_VERSION,
            "blocked_invalid_copied_from",
            "Historical config must identify phase3.1-smoke-v1 as its source.",
        ),
        (
            config.get("validation_id") == HISTORICAL_VALIDATION_ID,
            "blocked_validation_id_mismatch",
            "Historical validation_id does not match Phase 3.6.",
        ),
        (
            config.get("evidence_level") == HISTORICAL_EVIDENCE_LEVEL,
            "blocked_evidence_level_mismatch",
            "Historical evidence_level does not match Phase 3.6.",
        ),
        (
            config.get("parameter_change") is False,
            "blocked_parameter_change",
            "Historical config must declare parameter_change=false.",
        ),
        (
            config.get("tuning_change") is False,
            "blocked_tuning_change",
            "Historical config must declare tuning_change=false.",
        ),
        (
            config.get("date_binding_only_change") is True,
            "blocked_not_date_binding_only",
            "Historical config must declare date_binding_only_change=true.",
        ),
    )
    for passed, status, message in checks:
        if not passed:
            return status, message
    return None


def _historical_holdout_error(
    config: Mapping[str, Any],
) -> tuple[str, str] | None:
    holdout = (
        config.get("preregistration", {})
        .get("intended_future_validation_holdout")
    )
    if not isinstance(holdout, Mapping):
        return (
            "blocked_historical_contract_mismatch",
            "Historical config is missing its sealed validation contract.",
        )
    checks = (
        holdout.get("holdout_id") == HISTORICAL_VALIDATION_ID,
        config.get("holdout_id") == HISTORICAL_VALIDATION_ID,
        holdout.get("benchmark") == "CSI300",
        holdout.get("horizon_days") == 20,
        holdout.get("minimum_valid_sample_per_window")
        == MINIMUM_VALID_UNIVERSE_ROWS,
        holdout.get("minimum_valid_sample_per_cohort") == 20,
        tuple(holdout.get("window_ids", ())) == HISTORICAL_WINDOW_IDS,
    )
    if not all(checks):
        return (
            "blocked_historical_contract_mismatch",
            "Historical sealed contract differs from Phase 3.6.",
        )
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
