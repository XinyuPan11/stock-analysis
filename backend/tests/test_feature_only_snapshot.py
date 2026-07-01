from __future__ import annotations

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

from stock_analysis.research.feature_only_snapshot import (
    FeatureOnlySnapshotError,
    build_feature_only_snapshot,
    load_member_snapshot,
    write_feature_only_snapshot_outputs,
)


AS_OF_DATE = "2026-03-31"


def test_outcome_columns_are_rejected_by_default() -> None:
    source = _snapshot()
    source["future_return"] = [0.1, -0.1, 0.2]
    source["winner"] = [True, False, True]

    with pytest.raises(FeatureOnlySnapshotError) as exc_info:
        _build(source)

    assert exc_info.value.status == "blocked_outcome_columns_present"
    assert exc_info.value.details["outcome_columns"] == [
        "future_return",
        "winner",
    ]


def test_explicit_drop_removes_and_records_outcome_columns() -> None:
    source = _snapshot()
    source["future_return"] = [0.1, -0.1, 0.2]
    source["benchmark_future_return"] = [0.02, 0.02, 0.02]
    source["benchmark_data_quality"] = ["ok", "ok", "ok"]
    source["outcome"] = ["winner", "loser", "winner"]

    result = _build(source, drop_outcome_columns=True)

    assert result.metadata["dropped_outcome_columns"] == [
        "benchmark_data_quality",
        "benchmark_future_return",
        "future_return",
        "outcome",
    ]
    assert result.metadata["drop_outcome_columns_requested"] is True
    assert not {
        "benchmark_data_quality",
        "benchmark_future_return",
        "future_return",
        "outcome",
    }.intersection(result.frame.columns)


def test_latest_input_date_after_as_of_fails_closed() -> None:
    source = _snapshot()
    source.loc[0, "latest_input_date"] = "2026-04-01"

    with pytest.raises(FeatureOnlySnapshotError) as exc_info:
        _build(source)

    assert exc_info.value.status == "blocked_point_in_time_violation"
    assert exc_info.value.details["column"] == "latest_input_date"


def test_feature_metadata_and_h1_h5_fields_are_preserved() -> None:
    result = _build(_snapshot())

    assert result.metadata["research_only"] is True
    assert result.metadata["feature_only"] is True
    assert result.metadata["labels_joined"] is False
    assert result.metadata["provider_access"] is False
    assert result.metadata["production_change"] is False
    assert result.metadata["as_of_date"] == AS_OF_DATE
    assert result.metadata["input_row_count"] == 3
    assert result.metadata["output_row_count"] == 2
    assert result.metadata["latest_input_date_max"] == AS_OF_DATE
    required = {
        "pre_5d_return",
        "pre_20d_return",
        "pre_60d_return",
        "technical_volatility_20d",
        "drawdown_60d",
        "amount_change_20d",
        "volume_change_20d",
        "distance_to_60d_high",
        "distance_to_60d_low",
        "recent_acceleration_proxy",
        "high_position_crowding_proxy",
    }
    assert required.issubset(result.frame.columns)


def test_rank_and_list_membership_context_are_preserved() -> None:
    source = _snapshot()
    result = _build(source)
    expected = source.loc[source["as_of_date"] == AS_OF_DATE]

    assert result.frame["symbol"].tolist() == expected["symbol"].tolist()
    assert result.frame["rank"].tolist() == expected["rank"].tolist()
    assert result.frame["captured_positive_lists"].tolist() == (
        expected["captured_positive_lists"].tolist()
    )
    assert result.frame["is_breakout_watch"].tolist() == (
        expected["is_breakout_watch"].tolist()
    )


def test_written_csv_and_json_contain_no_outcomes(tmp_path: Path) -> None:
    source = _snapshot()
    source["future_excess_return"] = [0.1, -0.1, 0.2]
    result = _build(source, drop_outcome_columns=True)

    paths = write_feature_only_snapshot_outputs(
        result,
        output_dir=tmp_path / "research" / "inputs",
    )
    csv_frame = pd.read_csv(paths["csv"])
    payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))

    assert Path(paths["csv"]).name == (
        f"member_level_asof_features_{AS_OF_DATE}.csv"
    )
    assert Path(paths["csv"]).parent.name == "inputs"
    assert payload["metadata"]["feature_only"] is True
    assert payload["metadata"]["labels_joined"] is False
    assert payload["metadata"]["provider_access"] is False
    assert payload["metadata"]["production_change"] is False
    assert payload["metadata"]["output_path"] == paths["csv"]
    for columns in (
        csv_frame.columns,
        payload["records"][0],
    ):
        lowered = {str(column).lower() for column in columns}
        assert "future_excess_return" not in lowered
        assert "future_return" not in lowered
        assert "outcome" not in lowered


def test_json_source_with_records_is_supported(tmp_path: Path) -> None:
    source_path = tmp_path / "snapshot.json"
    source_path.write_text(
        json.dumps({"records": _snapshot().to_dict(orient="records")}),
        encoding="utf-8",
    )

    loaded = load_member_snapshot(source_path)

    assert loaded["symbol"].tolist() == ["AAA", "BBB", "OLD"]


def test_cli_defaults_to_dry_run_and_requires_explicit_drop(
    tmp_path: Path,
) -> None:
    source = _snapshot()
    source["future_return"] = [0.1, -0.1, 0.2]
    snapshot_path = tmp_path / "snapshot.csv"
    output_dir = tmp_path / "research" / "inputs"
    source.to_csv(snapshot_path, index=False)
    command = [
        sys.executable,
        str(ROOT / "scripts" / "build_feature_only_member_snapshot.py"),
        "--snapshot-file",
        str(snapshot_path),
        "--as-of-date",
        AS_OF_DATE,
        "--outputs-dir",
        str(output_dir),
    ]

    blocked = subprocess.run(
        command,
        cwd=ROOT.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    completed = subprocess.run(
        [*command, "--drop-outcome-columns", "--dry-run"],
        cwd=ROOT.parent,
        capture_output=True,
        text=True,
        check=False,
    )

    assert blocked.returncode == 2
    assert json.loads(blocked.stdout)["status"] == (
        "blocked_outcome_columns_present"
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["dry_run"] is True
    assert payload["dropped_outcome_columns"] == ["future_return"]
    assert payload["provider_access"] is False
    assert not output_dir.exists()


def _build(
    source: pd.DataFrame,
    *,
    drop_outcome_columns: bool = False,
):
    return build_feature_only_snapshot(
        source,
        as_of_date=AS_OF_DATE,
        source_snapshot_path="outputs/experiments/member_snapshot.csv",
        drop_outcome_columns=drop_outcome_columns,
    )


def _snapshot() -> pd.DataFrame:
    rows = [
        _row("AAA", AS_OF_DATE, rank=2, breakout=True),
        _row("BBB", AS_OF_DATE, rank=5, breakout=False),
        _row("OLD", "2025-12-31", rank=1, breakout=True),
    ]
    return pd.DataFrame(rows)


def _row(
    symbol: str,
    as_of_date: str,
    *,
    rank: int,
    breakout: bool,
) -> dict[str, object]:
    return {
        "as_of_date": as_of_date,
        "symbol": symbol,
        "rank": rank,
        "captured_positive_lists": (
            "breakout_watch" if breakout else "long_term_stable"
        ),
        "captured_risk_lists": "",
        "is_high_confidence": False,
        "is_trend_leader": False,
        "is_long_term_stable": not breakout,
        "is_breakout_watch": breakout,
        "is_accumulation_watch": False,
        "is_rebound_watch": False,
        "is_high_risk_active": False,
        "latest_input_date": as_of_date,
        "max_raw_cache_date": "2026-06-24",
        "future_rows_excluded_count": 10,
        "leakage_guard_applied": True,
        "pre_5d_return": 0.02,
        "pre_20d_return": 0.04,
        "pre_60d_return": 0.08,
        "technical_volatility_20d": 0.03,
        "drawdown_60d": -0.10,
        "amount_change_20d": 0.12,
        "volume_change_20d": 0.10,
        "distance_to_60d_high": -0.05,
        "distance_to_60d_low": 0.20,
        "recent_acceleration_proxy": 0.01,
        "high_position_crowding_proxy": 0.30,
    }



