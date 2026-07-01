from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.research.opportunity_cohorts import (
    COHORT_ROLES,
    OpportunityCohortBuildError,
    build_research_opportunity_cohorts,
    load_opportunity_cohort_config,
    write_research_opportunity_cohort_outputs,
)


AS_OF_DATE = "2026-03-31"


def test_builder_metadata_roles_and_source_fields_are_preserved(
    tmp_path: Path,
) -> None:
    source = _snapshot()
    original = source.copy(deep=True)
    result = _build(source, _config())

    metadata = result.report["metadata"]
    assert metadata["research_only"] is True
    assert metadata["provider_access"] is False
    assert metadata["labels_joined"] is False
    assert metadata["production_change"] is False
    assert metadata["as_of_date"] == AS_OF_DATE
    assert metadata["cohort_count"] == 5
    assert metadata["input_row_count"] == 3
    assert set(result.frame["cohort_role"]) == {
        "opportunity_observation",
        "risk_annotation",
    }
    roles = {
        row["cohort_id"]: row["cohort_role"]
        for row in result.report["cohorts"]
    }
    assert roles == COHORT_ROLES
    assert source.equals(original)
    for _, group in result.frame.groupby("cohort_id"):
        assert group["symbol"].tolist() == source["symbol"].tolist()
        assert group["rank"].tolist() == source["rank"].tolist()
        assert group["is_breakout_watch"].tolist() == (
            source["is_breakout_watch"].tolist()
        )
        assert group["is_accumulation_watch"].tolist() == (
            source["is_accumulation_watch"].tolist()
        )


def test_expected_cohorts_emit_observations_and_non_blocking_annotations() -> None:
    result = _build(_snapshot(), _config())

    by_cohort = {
        cohort_id: group
        for cohort_id, group in result.frame.groupby("cohort_id")
    }
    assert by_cohort["low_position_revaluation_watch"][
        "cohort_member"
    ].any()
    assert by_cohort["trend_acceleration_with_crowding_guard"][
        "cohort_member"
    ].any()
    assert by_cohort["right_tail_opportunity_watch"][
        "cohort_member"
    ].any()
    assert by_cohort["high_position_crowding_risk"][
        "cohort_member"
    ].any()
    assert by_cohort["false_breakout_risk"]["cohort_member"].any()
    assert set(
        result.frame.loc[
            result.frame["cohort_id"].isin(
                [
                    "low_position_revaluation_watch",
                    "trend_acceleration_with_crowding_guard",
                    "right_tail_opportunity_watch",
                ]
            ),
            "cohort_role",
        ]
    ) == {"opportunity_observation"}
    assert set(
        result.frame.loc[
            result.frame["cohort_id"].isin(
                ["high_position_crowding_risk", "false_breakout_risk"]
            ),
            "cohort_role",
        ]
    ) == {"risk_annotation"}


def test_missing_config_and_missing_parameters_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(OpportunityCohortBuildError) as missing:
        _build(_snapshot(), None)
    assert missing.value.status == "blocked_missing_config"

    config = _config()
    del config["cohorts"]["right_tail_opportunity_watch"]["parameters"][
        "min_volatility_20d"
    ]
    with pytest.raises(OpportunityCohortBuildError) as incomplete:
        _build(_snapshot(), config)
    assert incomplete.value.status == "blocked_missing_frozen_parameter"

    with pytest.raises(OpportunityCohortBuildError) as missing_file:
        load_opportunity_cohort_config(tmp_path / "missing.json")
    assert missing_file.value.status == "blocked_missing_config"


@pytest.mark.parametrize(
    "column",
    [
        "future_return",
        "future_excess_return",
        "label",
        "realized_return",
        "max_future_price",
        "min_future_price",
        "winner",
        "loser",
    ],
)
def test_future_or_realized_outcome_columns_are_rejected(column: str) -> None:
    snapshot = _snapshot()
    snapshot[column] = 1

    with pytest.raises(OpportunityCohortBuildError) as exc_info:
        _build(snapshot, _config())

    assert exc_info.value.status == "blocked_future_outcome_columns"
    assert column in exc_info.value.details["forbidden_columns"]


def test_point_in_time_violation_and_unverified_guard_fail_closed() -> None:
    future_input = _snapshot()
    future_input.loc[0, "latest_input_date"] = "2026-04-01"
    with pytest.raises(OpportunityCohortBuildError) as future:
        _build(future_input, _config())
    assert future.value.status == "blocked_point_in_time_violation"

    unguarded = _snapshot()
    unguarded.loc[0, "leakage_guard_applied"] = False
    with pytest.raises(OpportunityCohortBuildError) as guard:
        _build(unguarded, _config())
    assert guard.value.status == "blocked_unverified_leakage_guard"


def test_missing_required_column_fails_closed() -> None:
    snapshot = _snapshot().drop(columns=["distance_to_60d_low"])

    with pytest.raises(OpportunityCohortBuildError) as exc_info:
        _build(snapshot, _config())

    assert exc_info.value.status == "blocked_missing_required_feature"
    assert "distance_to_60d_low" in exc_info.value.details["missing_columns"]


def test_output_contains_no_future_labels_and_uses_research_paths(
    tmp_path: Path,
) -> None:
    result = _build(_snapshot(), _config())
    paths = write_research_opportunity_cohort_outputs(result, tmp_path)
    csv_frame = pd.read_csv(paths["csv"])
    payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))

    assert Path(paths["json"]).name == (
        f"opportunity_cohorts_{AS_OF_DATE}.json"
    )
    assert Path(paths["csv"]).name == (
        f"opportunity_cohorts_{AS_OF_DATE}.csv"
    )
    assert Path(paths["json"]).parent.name == "research"
    assert payload["metadata"]["provider_access"] is False
    assert payload["metadata"]["labels_joined"] is False
    assert payload["metadata"]["production_change"] is False
    for columns in (result.frame.columns, csv_frame.columns, payload["records"][0]):
        lowered = {str(column).lower() for column in columns}
        assert "future_return" not in lowered
        assert "future_excess_return" not in lowered
        assert "winner" not in lowered
        assert "loser" not in lowered


def test_cli_dry_run_writes_no_outputs(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "features.csv"
    config_path = tmp_path / "config.json"
    outputs_dir = tmp_path / "outputs"
    _snapshot().to_csv(snapshot_path, index=False)
    config_path.write_text(
        json.dumps(_config(), ensure_ascii=False),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "build_research_opportunity_cohorts.py"),
            "--snapshot-file",
            str(snapshot_path),
            "--as-of-date",
            AS_OF_DATE,
            "--config",
            str(config_path),
            "--outputs-dir",
            str(outputs_dir),
            "--dry-run",
        ],
        cwd=ROOT.parent,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["dry_run"] is True
    assert payload["provider_access"] is False
    assert payload["labels_joined"] is False
    assert payload["production_change"] is False
    assert not outputs_dir.exists()


def _build(
    snapshot: pd.DataFrame,
    config: dict[str, object] | None,
):
    return build_research_opportunity_cohorts(
        snapshot,
        config,
        as_of_date=AS_OF_DATE,
        source_snapshot_path="feature_only_snapshot.csv",
        config_path="preregistered_config.json",
    )


def _snapshot() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _row(
                "AAA",
                rank=7,
                pre_5d=0.05,
                pre_20d=-0.05,
                pre_60d=-0.20,
                volatility=0.08,
                drawdown=-0.30,
                amount=0.50,
                volume=0.40,
                distance_high=-0.25,
                distance_low=0.05,
                acceleration=0.06,
                crowding=0.20,
                breakout=False,
                accumulation=True,
            ),
            _row(
                "BBB",
                rank=3,
                pre_5d=0.10,
                pre_20d=0.15,
                pre_60d=0.20,
                volatility=0.20,
                drawdown=-0.05,
                amount=0.45,
                volume=0.35,
                distance_high=-0.02,
                distance_low=0.50,
                acceleration=0.07,
                crowding=0.85,
                breakout=True,
                accumulation=False,
            ),
            _row(
                "CCC",
                rank=11,
                pre_5d=-0.03,
                pre_20d=0.12,
                pre_60d=0.18,
                volatility=0.18,
                drawdown=-0.15,
                amount=0.50,
                volume=0.55,
                distance_high=-0.01,
                distance_low=0.60,
                acceleration=-0.02,
                crowding=0.75,
                breakout=True,
                accumulation=True,
            ),
        ]
    )


def _row(
    symbol: str,
    *,
    rank: int,
    pre_5d: float,
    pre_20d: float,
    pre_60d: float,
    volatility: float,
    drawdown: float,
    amount: float,
    volume: float,
    distance_high: float,
    distance_low: float,
    acceleration: float,
    crowding: float,
    breakout: bool,
    accumulation: bool,
) -> dict[str, object]:
    return {
        "as_of_date": AS_OF_DATE,
        "symbol": symbol,
        "rank": rank,
        "data_quality": "ok",
        "latest_input_date": AS_OF_DATE,
        "max_raw_cache_date": "2026-06-24",
        "future_rows_excluded_count": 10,
        "leakage_guard_applied": True,
        "pre_5d_return": pre_5d,
        "pre_20d_return": pre_20d,
        "pre_60d_return": pre_60d,
        "technical_volatility_20d": volatility,
        "drawdown_60d": drawdown,
        "amount_change_20d": amount,
        "volume_change_20d": volume,
        "distance_to_60d_high": distance_high,
        "distance_to_60d_low": distance_low,
        "recent_acceleration_proxy": acceleration,
        "high_position_crowding_proxy": crowding,
        "is_breakout_watch": breakout,
        "is_accumulation_watch": accumulation,
        "is_high_confidence": symbol == "BBB",
        "is_trend_leader": symbol == "BBB",
        "is_long_term_stable": False,
        "is_rebound_watch": False,
        "is_high_risk_active": symbol == "CCC",
    }


def _config() -> dict[str, object]:
    return {
        "research_only": True,
        "config_version": "unit-test-v1",
        "as_of_date": AS_OF_DATE,
        "parameter_source": "synthetic_test_fixture",
        "feature_bindings": {
            "volatility_20d": "technical_volatility_20d",
        },
        "cohorts": {
            "low_position_revaluation_watch": {
                "role": "opportunity_observation",
                "parameters": {
                    "max_distance_to_60d_low": 0.10,
                    "max_drawdown_60d": -0.20,
                    "min_recent_acceleration_proxy": 0.02,
                    "min_activity_change_20d": 0.30,
                },
            },
            "trend_acceleration_with_crowding_guard": {
                "role": "opportunity_observation",
                "parameters": {
                    "min_recent_acceleration_proxy": 0.03,
                    "min_pre_20d_return": 0.05,
                    "min_crowding_proxy": 0.70,
                    "min_distance_to_60d_high": -0.05,
                },
            },
            "right_tail_opportunity_watch": {
                "role": "opportunity_observation",
                "parameters": {
                    "min_volatility_20d": 0.15,
                    "min_recent_acceleration_proxy": 0.03,
                    "min_activity_change_20d": 0.30,
                },
            },
            "high_position_crowding_risk": {
                "role": "risk_annotation",
                "parameters": {
                    "min_distance_to_60d_high": -0.05,
                    "min_crowding_proxy": 0.70,
                    "min_volatility_20d": 0.15,
                },
            },
            "false_breakout_risk": {
                "role": "risk_annotation",
                "parameters": {
                    "min_distance_to_60d_high": -0.05,
                    "max_recent_acceleration_proxy": 0.00,
                    "max_drawdown_60d": -0.10,
                    "min_activity_change_20d": 0.30,
                },
            },
        },
    }
