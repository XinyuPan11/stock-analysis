from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.research.opportunity_cohorts import (
    load_opportunity_cohort_config,
    validate_opportunity_cohort_config,
)
from stock_analysis.research.u3_readiness import (
    U3_HOLDOUT_ID,
    U3_WINDOWS,
    check_u3_readiness,
    check_u3_window_readiness,
    frozen_logic_digest,
    parameter_count,
    parameter_digest,
)


REPO_ROOT = ROOT.parent
CONFIG_DIR = REPO_ROOT / "research" / "configs"
SOURCE_CONFIG_PATH = (
    CONFIG_DIR / "opportunity_cohorts.phase3_1_smoke.json"
)


@pytest.mark.parametrize("as_of_date", U3_WINDOWS)
def test_u3_configs_pass_execution_schema(as_of_date: str) -> None:
    config = _u3_config(as_of_date)

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
    assert validated["parameter_change"] is False
    assert validated["tuning_change"] is False
    assert validated["date_binding_only_change"] is True
    assert validated["holdout_id"] == U3_HOLDOUT_ID


def test_u3_parameter_and_logic_checksums_match_phase3_1() -> None:
    source = load_opportunity_cohort_config(SOURCE_CONFIG_PATH)
    source_parameter_digest = parameter_digest(source)
    source_logic_digest = frozen_logic_digest(source)

    assert parameter_count(source) == 18
    for as_of_date in U3_WINDOWS:
        config = _u3_config(as_of_date)
        assert parameter_count(config) == 18
        assert parameter_digest(config) == source_parameter_digest
        assert frozen_logic_digest(config) == source_logic_digest
        assert (
            config["preregistration"]["intended_future_validation_holdout"]
            == source["preregistration"][
                "intended_future_validation_holdout"
            ]
        )


def test_changing_one_parameter_changes_digest_and_blocks_readiness(
    tmp_path: Path,
) -> None:
    source = load_opportunity_cohort_config(SOURCE_CONFIG_PATH)
    changed = deepcopy(_u3_config(U3_WINDOWS[0]))
    changed["cohorts"]["right_tail_opportunity_watch"]["parameters"][
        "min_volatility_20d"
    ] += 0.001
    changed_path = _write_config(tmp_path / "changed.json", changed)

    result = check_u3_window_readiness(
        expected_as_of_date=U3_WINDOWS[0],
        source_config_path=SOURCE_CONFIG_PATH,
        u3_config_path=changed_path,
        feature_only_snapshot_path=tmp_path / "missing.csv",
    )

    assert parameter_digest(changed) != parameter_digest(source)
    assert result["status"] == "blocked_parameter_checksum_mismatch"


def test_wrong_as_of_date_fails_readiness(tmp_path: Path) -> None:
    config = deepcopy(_u3_config(U3_WINDOWS[0]))
    config["as_of_date"] = U3_WINDOWS[1]
    config_path = _write_config(tmp_path / "wrong-date.json", config)

    result = check_u3_window_readiness(
        expected_as_of_date=U3_WINDOWS[0],
        source_config_path=SOURCE_CONFIG_PATH,
        u3_config_path=config_path,
        feature_only_snapshot_path=tmp_path / "missing.csv",
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
    config = deepcopy(_u3_config(U3_WINDOWS[0]))
    config[field] = value
    config_path = _write_config(tmp_path / f"{field}.json", config)

    result = check_u3_window_readiness(
        expected_as_of_date=U3_WINDOWS[0],
        source_config_path=SOURCE_CONFIG_PATH,
        u3_config_path=config_path,
        feature_only_snapshot_path=tmp_path / "missing.csv",
    )

    assert result["status"] == status


def test_missing_u3_snapshots_block_without_provider_access() -> None:
    def forbidden_network(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"Unexpected network access: {args} {kwargs}")

    with patch.object(socket, "create_connection", forbidden_network):
        result = check_u3_readiness(REPO_ROOT)

    assert result["status"] == "blocked"
    assert result["ready"] is False
    assert result["provider_access"] is False
    assert result["validation_run"] is False
    assert result["future_labels_joined"] is False
    assert [window["status"] for window in result["windows"]] == [
        "blocked_missing_feature_only_snapshot",
        "blocked_missing_feature_only_snapshot",
    ]


@pytest.mark.parametrize("as_of_date", U3_WINDOWS)
def test_valid_local_feature_snapshot_passes_readiness(
    tmp_path: Path,
    as_of_date: str,
) -> None:
    snapshot_path = tmp_path / f"features-{as_of_date}.csv"
    _feature_only_snapshot(as_of_date).to_csv(
        snapshot_path,
        index=False,
    )

    result = check_u3_window_readiness(
        expected_as_of_date=as_of_date,
        source_config_path=SOURCE_CONFIG_PATH,
        u3_config_path=_u3_config_path(as_of_date),
        feature_only_snapshot_path=snapshot_path,
    )

    assert result["status"] == "ready"
    assert result["ready"] is True
    assert result["provider_access"] is False
    assert result["labels_joined"] is False
    assert result["production_change"] is False
    assert result["feature_only_row_count"] == 100
    assert result["parameter_count"] == 18


def _u3_config_path(as_of_date: str) -> Path:
    return (
        CONFIG_DIR
        / f"opportunity_cohorts.u3_{as_of_date}.json"
    )


def _u3_config(as_of_date: str) -> dict[str, object]:
    return load_opportunity_cohort_config(_u3_config_path(as_of_date))


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
