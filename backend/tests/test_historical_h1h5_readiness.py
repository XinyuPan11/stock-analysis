from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil
import socket
import sys
from unittest.mock import patch

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.research.historical_h1h5_readiness import (
    HISTORICAL_BACKUP_WINDOWS,
    HISTORICAL_CONFIG_FILENAMES,
    HISTORICAL_EVIDENCE_LEVEL,
    HISTORICAL_EXCLUDED_WINDOWS,
    HISTORICAL_PRIMARY_WINDOWS,
    HISTORICAL_VALIDATION_ID,
    HISTORICAL_WINDOWS,
    check_historical_readiness,
    check_historical_window_readiness,
)
from stock_analysis.research.opportunity_cohorts import (
    load_opportunity_cohort_config,
    validate_opportunity_cohort_config,
)
from stock_analysis.research.u3_readiness import (
    frozen_logic_digest,
    parameter_count,
    parameter_digest,
)


REPO_ROOT = ROOT.parent
CONFIG_DIR = REPO_ROOT / "research" / "configs"
SOURCE_CONFIG_PATH = (
    CONFIG_DIR / "opportunity_cohorts.phase3_1_smoke.json"
)


@pytest.mark.parametrize("as_of_date", HISTORICAL_WINDOWS)
def test_historical_configs_pass_execution_schema(as_of_date: str) -> None:
    config = _historical_config(as_of_date)

    validated = validate_opportunity_cohort_config(
        config,
        as_of_date=as_of_date,
        mode="execution",
    )

    assert validated["as_of_date"] == as_of_date
    assert validated["research_only"] is True
    assert validated["provider_access"] is False
    assert validated["labels_joined"] is False
    assert validated["production_change"] is False
    assert validated["copied_from"] == "phase3.1-smoke-v1"
    assert validated["validation_id"] == HISTORICAL_VALIDATION_ID
    assert validated["evidence_level"] == HISTORICAL_EVIDENCE_LEVEL
    assert validated["parameter_change"] is False
    assert validated["tuning_change"] is False
    assert validated["date_binding_only_change"] is True


def test_historical_parameter_and_logic_digests_match_phase3_1() -> None:
    source = load_opportunity_cohort_config(SOURCE_CONFIG_PATH)
    source_parameter_digest = parameter_digest(source)
    source_logic_digest = frozen_logic_digest(source)

    assert parameter_count(source) == 18
    for as_of_date in HISTORICAL_WINDOWS:
        config = _historical_config(as_of_date)
        assert parameter_count(config) == 18
        assert parameter_digest(config) == source_parameter_digest
        assert frozen_logic_digest(config) == source_logic_digest
        assert (
            config["parameter_documentation"]
            == source["parameter_documentation"]
        )


def test_changing_one_parameter_changes_digest_and_blocks_readiness(
    tmp_path: Path,
) -> None:
    as_of_date = HISTORICAL_PRIMARY_WINDOWS[0]
    source = load_opportunity_cohort_config(SOURCE_CONFIG_PATH)
    changed = deepcopy(_historical_config(as_of_date))
    changed["cohorts"]["right_tail_opportunity_watch"]["parameters"][
        "min_volatility_20d"
    ] += 0.001
    config_path = _write_config(tmp_path / "changed.json", changed)

    result = _check(
        as_of_date,
        config_path=config_path,
        source_snapshot=tmp_path / "missing-source.csv",
        feature_snapshot=tmp_path / "missing-features.csv",
    )

    assert parameter_digest(changed) != parameter_digest(source)
    assert result["status"] == "blocked_parameter_checksum_mismatch"


@pytest.mark.parametrize(
    "as_of_date",
    sorted(HISTORICAL_EXCLUDED_WINDOWS),
)
def test_consumed_and_u3_windows_are_rejected(as_of_date: str) -> None:
    result = check_historical_window_readiness(
        expected_as_of_date=as_of_date,
        source_config_path=SOURCE_CONFIG_PATH,
        historical_config_path=CONFIG_DIR / "must-not-be-loaded.json",
        source_snapshot_path=None,
        feature_only_snapshot_path=None,
    )

    assert result["status"] == "blocked_excluded_window"
    assert result["provider_access"] is False
    assert result["validation_run"] is False


def test_wrong_as_of_date_fails_readiness(tmp_path: Path) -> None:
    expected = HISTORICAL_PRIMARY_WINDOWS[0]
    config = deepcopy(_historical_config(expected))
    config["as_of_date"] = HISTORICAL_PRIMARY_WINDOWS[1]
    config_path = _write_config(tmp_path / "wrong-date.json", config)

    result = _check(
        expected,
        config_path=config_path,
        source_snapshot=tmp_path / "missing-source.csv",
        feature_snapshot=tmp_path / "missing-features.csv",
    )

    assert result["status"] == "blocked_wrong_as_of_date"


@pytest.mark.parametrize(
    ("field", "value", "status"),
    [
        ("labels_joined", True, "blocked_labels_joined"),
        ("production_change", True, "blocked_production_change"),
    ],
)
def test_unsafe_flags_fail_readiness(
    tmp_path: Path,
    field: str,
    value: bool,
    status: str,
) -> None:
    as_of_date = HISTORICAL_PRIMARY_WINDOWS[0]
    config = deepcopy(_historical_config(as_of_date))
    config[field] = value
    config_path = _write_config(tmp_path / f"{field}.json", config)

    result = _check(
        as_of_date,
        config_path=config_path,
        source_snapshot=tmp_path / "missing-source.csv",
        feature_snapshot=tmp_path / "missing-features.csv",
    )

    assert result["status"] == status


def test_missing_source_snapshot_blocks_without_provider_access(
    tmp_path: Path,
) -> None:
    def forbidden_network(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"Unexpected network access: {args} {kwargs}")

    isolated_repo = tmp_path / "repo"
    isolated_configs = isolated_repo / "research" / "configs"
    isolated_configs.mkdir(parents=True)
    shutil.copyfile(
        SOURCE_CONFIG_PATH,
        isolated_configs / SOURCE_CONFIG_PATH.name,
    )
    for filename in HISTORICAL_CONFIG_FILENAMES.values():
        shutil.copyfile(CONFIG_DIR / filename, isolated_configs / filename)

    with patch.object(socket, "create_connection", forbidden_network):
        result = check_historical_readiness(isolated_repo)

    assert result["status"] == "blocked"
    assert result["ready"] is False
    assert result["provider_access"] is False
    assert result["validation_run"] is False
    assert result["validation_outputs_read"] is False
    assert [window["status"] for window in result["windows"]] == [
        "blocked_missing_source_snapshot",
    ] * len(HISTORICAL_WINDOWS)


def test_missing_feature_only_snapshot_blocks_after_source_exists(
    tmp_path: Path,
) -> None:
    as_of_date = HISTORICAL_PRIMARY_WINDOWS[0]
    source_snapshot = tmp_path / "source.csv"
    source_snapshot.touch()

    result = _check(
        as_of_date,
        source_snapshot=source_snapshot,
        feature_snapshot=tmp_path / "missing-features.csv",
    )

    assert result["status"] == "blocked_missing_feature_only_snapshot"
    assert result["provider_access"] is False


def test_feature_only_snapshot_with_outcome_column_is_rejected(
    tmp_path: Path,
) -> None:
    as_of_date = HISTORICAL_PRIMARY_WINDOWS[0]
    source_snapshot = tmp_path / "source.csv"
    feature_snapshot = tmp_path / "features.csv"
    source_snapshot.touch()
    frame = _feature_only_snapshot(as_of_date)
    frame["future_return"] = 0.1
    frame.to_csv(feature_snapshot, index=False)

    result = _check(
        as_of_date,
        source_snapshot=source_snapshot,
        feature_snapshot=feature_snapshot,
    )

    assert result["status"] == "blocked_invalid_feature_only_snapshot"
    assert result["details"]["snapshot_status"] == (
        "blocked_outcome_columns_present"
    )


@pytest.mark.parametrize(
    "as_of_date",
    (*HISTORICAL_PRIMARY_WINDOWS, *HISTORICAL_BACKUP_WINDOWS),
)
def test_valid_local_feature_snapshot_passes_window_readiness(
    tmp_path: Path,
    as_of_date: str,
) -> None:
    source_snapshot = tmp_path / f"source-{as_of_date}.csv"
    feature_snapshot = tmp_path / f"features-{as_of_date}.csv"
    source_snapshot.touch()
    _feature_only_snapshot(as_of_date).to_csv(
        feature_snapshot,
        index=False,
    )

    result = _check(
        as_of_date,
        source_snapshot=source_snapshot,
        feature_snapshot=feature_snapshot,
    )

    assert result["status"] == "ready"
    assert result["ready"] is True
    assert result["feature_only_row_count"] == 100
    assert result["parameter_count"] == 18
    assert result["provider_access"] is False
    assert result["labels_joined"] is False
    assert result["production_change"] is False


def test_historical_readiness_does_not_require_u3_configs(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    config_dir = repo_root / "research" / "configs"
    config_dir.mkdir(parents=True)
    shutil.copyfile(
        SOURCE_CONFIG_PATH,
        config_dir / SOURCE_CONFIG_PATH.name,
    )
    for as_of_date in HISTORICAL_WINDOWS:
        source = _historical_config_path(as_of_date)
        shutil.copyfile(source, config_dir / source.name)

    result = check_historical_readiness(repo_root)

    assert result["status"] == "blocked"
    assert all(
        window["status"] == "blocked_missing_source_snapshot"
        for window in result["windows"]
    )
    assert not list(config_dir.glob("opportunity_cohorts.u3_*.json"))


def _check(
    as_of_date: str,
    *,
    config_path: Path | None = None,
    source_snapshot: Path | None,
    feature_snapshot: Path | None,
) -> dict[str, object]:
    return check_historical_window_readiness(
        expected_as_of_date=as_of_date,
        source_config_path=SOURCE_CONFIG_PATH,
        historical_config_path=(
            config_path or _historical_config_path(as_of_date)
        ),
        source_snapshot_path=source_snapshot,
        feature_only_snapshot_path=feature_snapshot,
    )


def _historical_config_path(as_of_date: str) -> Path:
    return CONFIG_DIR / HISTORICAL_CONFIG_FILENAMES[as_of_date]


def _historical_config(as_of_date: str) -> dict[str, object]:
    return load_opportunity_cohort_config(
        _historical_config_path(as_of_date)
    )


def _write_config(path: Path, config: dict[str, object]) -> Path:
    path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _feature_only_snapshot(as_of_date: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "as_of_date": as_of_date,
                "symbol": f"TEST{index:03d}",
                "latest_input_date": as_of_date,
                "max_raw_cache_date": as_of_date,
                "future_rows_excluded_count": 0,
                "leakage_guard_applied": True,
                "pre_5d_return": 0.01,
                "pre_20d_return": 0.02,
                "pre_60d_return": 0.03,
                "technical_volatility_20d": 0.02,
                "drawdown_60d": -0.05,
                "amount_change_20d": 0.01,
                "volume_change_20d": 0.01,
                "distance_to_60d_high": -0.05,
                "distance_to_60d_low": 0.10,
                "recent_acceleration_proxy": 0.0,
                "high_position_crowding_proxy": 0.0,
                "is_breakout_watch": False,
                "is_accumulation_watch": False,
            }
            for index in range(100)
        ]
    )
