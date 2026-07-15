from __future__ import annotations

import hashlib
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

from stock_analysis.research.historical_h1h5_label_source_readiness import (
    HistoricalH1H5LabelReadinessError,
    check_historical_h1h5_label_source_readiness,
    check_historical_h1h5_label_source_window,
)


PRIMARY_DATES = ("2026-01-30", "2026-03-31", "2026-04-30")
COHORT_ROLES = {
    "low_position_revaluation_watch": "opportunity_observation",
    "trend_acceleration_with_crowding_guard": "opportunity_observation",
    "right_tail_opportunity_watch": "opportunity_observation",
    "high_position_crowding_risk": "risk_annotation",
    "false_breakout_risk": "risk_annotation",
}
SYMBOLS = ("sh.600000", "sh.600001", "sh.600002")


@pytest.fixture
def ready_fixture(tmp_path: Path) -> dict[str, object]:
    repo = tmp_path / "repo"
    outputs = repo / "outputs"
    cache = repo / "data" / "cache" / "daily-use"
    research = outputs / "research"
    research.mkdir(parents=True)
    digests: dict[str, dict[str, str]] = {}
    for as_of_date in PRIMARY_DATES:
        payload = _cohort_payload(as_of_date)
        json_path = research / f"opportunity_cohorts_{as_of_date}.json"
        csv_path = research / f"opportunity_cohorts_{as_of_date}.csv"
        _write_json(json_path, payload)
        pd.DataFrame(payload["records"]).to_csv(csv_path, index=False)
        digests[as_of_date] = {
            "json": _sha256(json_path),
            "csv": _sha256(csv_path),
        }
    dates = pd.bdate_range("2026-01-01", "2026-06-30")
    _write_dates(
        cache
        / "baostock"
        / "stock_daily"
        / "adjusted"
        / "sh.000300.csv",
        dates,
    )
    for symbol in SYMBOLS:
        _write_dates(
            cache
            / "baostock"
            / "stock_daily"
            / "adjusted"
            / f"{symbol}.csv",
            dates,
        )
    return {
        "repo": repo,
        "outputs": outputs,
        "cache": cache,
        "digests": digests,
    }


def test_readiness_detects_frozen_cohorts_and_sufficient_cache(
    ready_fixture: dict[str, object],
) -> None:
    report = _check(ready_fixture)

    assert report["status"] == "ready_to_build_label_sources"
    assert report["ready"] is True
    assert report["ready_to_build_count"] == 3
    assert report["blocked_window_count"] == 0
    for window in report["windows"]:
        assert window["status"] == "ready_to_build_label_sources"
        assert window["cohort_symbol_count"] == 3
        assert window["stock_cache"][
            "temporally_covered_symbol_count"
        ] == 3
        assert window["benchmark_cache"]["status"] == "covered"
        assert window["required_future_end"]
        assert window["frozen_cohort_mutated"] is False
        assert window["no_provider_access_needed"] is True


def test_digest_mismatch_blocks_readiness(
    ready_fixture: dict[str, object],
) -> None:
    digests = deepcopy_digests(ready_fixture["digests"])
    digests[PRIMARY_DATES[0]]["json"] = "0" * 64

    report = _check(ready_fixture, digests=digests)

    assert report["status"] == "blocked"
    assert report["windows"][0]["status"] == (
        "blocked_frozen_digest_mismatch"
    )


def test_missing_local_future_cache_blocks_readiness(
    ready_fixture: dict[str, object],
) -> None:
    missing = (
        Path(ready_fixture["cache"])
        / "baostock"
        / "stock_daily"
        / "adjusted"
        / f"{SYMBOLS[0]}.csv"
    )
    missing.unlink()

    report = _check(ready_fixture)

    assert report["status"] == "blocked"
    assert all(
        window["status"] == "blocked_missing_local_future_cache"
        for window in report["windows"]
    )
    assert report["windows"][0]["stock_cache"]["missing_cache_count"] == 1


def test_existing_validation_output_blocks_readiness(
    ready_fixture: dict[str, object],
) -> None:
    path = (
        Path(ready_fixture["outputs"])
        / "validation"
        / f"walk_forward_predictions_{PRIMARY_DATES[1]}_20d.csv"
    )
    path.parent.mkdir()
    path.write_text("symbol,future_return\nTEST,0.1\n", encoding="utf-8")

    report = _check(ready_fixture)

    assert report["status"] == "blocked"
    assert report["windows"][1]["status"] == (
        "blocked_existing_validation_output"
    )
    assert str(path) in report["windows"][1][
        "existing_validation_outputs"
    ]


def test_explicit_missing_label_source_blocks(
    ready_fixture: dict[str, object],
) -> None:
    report = _check(
        ready_fixture,
        label_sources={
            PRIMARY_DATES[0]: Path(ready_fixture["repo"]) / "missing.json"
        },
    )

    assert report["status"] == "blocked"
    assert report["windows"][0]["status"] == "blocked_missing_label_source"


def test_safe_explicit_label_source_is_ready_for_evaluator(
    ready_fixture: dict[str, object],
) -> None:
    as_of_date = PRIMARY_DATES[0]
    window_without_labels = check_historical_h1h5_label_source_window(
        repo_root=ready_fixture["repo"],
        cache_dir=ready_fixture["cache"],
        outputs_dir=ready_fixture["outputs"],
        as_of_date=as_of_date,
        label_source_path=None,
        expected_digests=ready_fixture["digests"][as_of_date],
    )
    label_path = (
        Path(ready_fixture["outputs"])
        / "experiments"
        / f"historical_h1h5_label_source_{as_of_date}_20d.json"
    )
    _write_json(
        label_path,
        _label_payload(
            as_of_date,
            required_future_end=window_without_labels[
                "required_future_end"
            ],
        ),
    )

    window = check_historical_h1h5_label_source_window(
        repo_root=ready_fixture["repo"],
        cache_dir=ready_fixture["cache"],
        outputs_dir=ready_fixture["outputs"],
        as_of_date=as_of_date,
        label_source_path=label_path,
        expected_digests=ready_fixture["digests"][as_of_date],
    )

    assert window["status"] == "ready_for_evaluator_dry_run"
    assert window["label_source_schema_status"] == "safe"
    assert window["label_source"]["row_count"] == 3
    assert window["label_source"]["missing_label_count"] == 1
    assert window["evaluator_run"] is False
    assert window["final_validation_outputs_written"] is False


def test_readiness_never_calls_provider(
    ready_fixture: dict[str, object],
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"Unexpected network call: {args} {kwargs}")

    with patch.object(socket, "create_connection", forbidden):
        report = _check(ready_fixture)

    assert report["provider_access"] is False
    assert report["cache_prewarm_executed"] is False


@pytest.mark.parametrize("as_of_date", ["2026-09-30", "2026-12-31"])
def test_u3_windows_are_rejected(
    ready_fixture: dict[str, object],
    as_of_date: str,
) -> None:
    with pytest.raises(HistoricalH1H5LabelReadinessError) as exc_info:
        check_historical_h1h5_label_source_window(
            repo_root=ready_fixture["repo"],
            cache_dir=ready_fixture["cache"],
            outputs_dir=ready_fixture["outputs"],
            as_of_date=as_of_date,
            label_source_path=None,
            expected_digests={"csv": "0" * 64, "json": "0" * 64},
        )

    assert exc_info.value.status == "blocked_excluded_window"


def _check(
    fixture: dict[str, object],
    *,
    digests: dict[str, dict[str, str]] | None = None,
    label_sources: dict[str, Path] | None = None,
):
    return check_historical_h1h5_label_source_readiness(
        fixture["repo"],
        cache_dir=fixture["cache"],
        outputs_dir=fixture["outputs"],
        expected_digests=digests or fixture["digests"],
        label_sources=label_sources,
    )


def _cohort_payload(as_of_date: str) -> dict[str, object]:
    records = []
    summaries = []
    for cohort_id, role in COHORT_ROLES.items():
        summaries.append(
            {
                "cohort_id": cohort_id,
                "cohort_role": role,
                "member_count": 1,
            }
        )
        for index, symbol in enumerate(SYMBOLS):
            records.append(
                {
                    "as_of_date": as_of_date,
                    "symbol": symbol,
                    "cohort_id": cohort_id,
                    "cohort_role": role,
                    "cohort_member": index == 0,
                    "research_only": True,
                    "future_rows_excluded_count": 10,
                }
            )
    return {
        "metadata": {
            "research_only": True,
            "provider_access": False,
            "labels_joined": False,
            "production_change": False,
            "validation_id": "h1h5-historical-sealed-v1",
            "as_of_date": as_of_date,
        },
        "cohorts": summaries,
        "records": records,
    }


def _label_payload(
    as_of_date: str,
    *,
    required_future_end: str,
) -> dict[str, object]:
    records = []
    for index, symbol in enumerate(SYMBOLS):
        valid = index < 2
        future_return = 0.10 if valid else None
        records.append(
            {
                "validation_id": "h1h5-historical-sealed-v1",
                "evidence_level": "historical_sealed_not_prospective",
                "as_of_date": as_of_date,
                "horizon_days": 20,
                "benchmark": "CSI300",
                "symbol": symbol,
                "valid_label": valid,
                "missing_label_reason": "" if valid else "missing_symbol_cache",
                "as_of_close": 100.0 if valid else None,
                "future_end_close": 110.0 if valid else None,
                "future_return_20d": future_return,
                "benchmark_return_20d": 0.05 if valid else None,
                "excess_return_20d": 0.05 if valid else None,
                "max_future_close_20d": 110.0 if valid else None,
                "min_future_close_20d": 100.0 if valid else None,
                "max_upside_20d": 0.10 if valid else None,
                "max_drawdown_20d": -0.10 if valid else None,
                "winner": index == 0 if valid else None,
                "loser": index == 1 if valid else None,
                "severe_drawdown": False if valid else None,
                "right_tail": index == 0 if valid else None,
                "label_future_rows_used_count": 20 if valid else 0,
                "label_window_start_date": "2026-02-02",
                "label_window_end_date": required_future_end,
                "price_field": "adj_close",
            }
        )
    return {
        "metadata": {
            "validation_id": "h1h5-historical-sealed-v1",
            "evidence_level": "historical_sealed_not_prospective",
            "as_of_date": as_of_date,
            "horizon_days": 20,
            "benchmark": "CSI300",
            "label_window_complete": True,
            "label_definition_sha256": (
                "98282FC01C3F2CE73C97A3A5F66CE62B8C927D27631852B15108A83499245BAF"
            ),
            "provider_access": False,
            "production_change": False,
            "required_future_end": required_future_end,
            "cache_coverage": {"source": "synthetic_local_cache"},
        },
        "records": records,
    }


def _write_dates(path: Path, dates: pd.DatetimeIndex) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {"trade_date": dates.strftime("%Y-%m-%d")}
    ).to_csv(path, index=False)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def deepcopy_digests(value: object) -> dict[str, dict[str, str]]:
    return json.loads(json.dumps(value))
