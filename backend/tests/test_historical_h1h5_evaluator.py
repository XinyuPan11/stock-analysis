from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
from unittest.mock import patch

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.research.historical_h1h5_evaluator import (
    COHORT_ROLES,
    REQUIRED_OUTPUT_FIELDS,
    HistoricalH1H5EvaluatorError,
    evaluate_historical_h1h5_cohorts,
    evaluator_schema_contract,
    load_explicit_label_source,
    load_frozen_cohort_output,
    write_historical_h1h5_evaluation_outputs,
)


AS_OF_DATE = "2026-03-31"


def test_evaluator_accepts_safe_synthetic_inputs_and_schema(
    tmp_path: Path,
) -> None:
    frozen = _frozen(tmp_path, _cohort_payload())
    labels_path = _write_json(tmp_path / "labels.json", _label_payload())
    labels = load_explicit_label_source(labels_path)

    result = _evaluate(frozen, labels, labels_path)

    assert len(result.frame) == 5
    assert set(REQUIRED_OUTPUT_FIELDS).issubset(result.frame.columns)
    assert set(result.frame["cohort_name"]) == set(COHORT_ROLES)
    assert set(result.frame["result_status"]).issubset(
        {"underpowered", "mixed_research_only"}
    )
    metadata = result.report["metadata"]
    assert metadata["cohort_digest_verified"] is True
    assert metadata["labels_joined_by_evaluator"] is True
    assert metadata["builder_labels_joined"] is False
    assert metadata["provider_access"] is False
    assert metadata["production_change"] is False


@pytest.mark.parametrize(
    "field",
    [
        "future_return",
        "outcome",
        "label",
        "winner",
        "loser",
        "realized_return",
        "holding_period",
        "max_future_price",
        "min_future_price",
        "benchmark_future_return",
        "excess_return",
    ],
)
def test_evaluator_rejects_prejoined_label_or_outcome_fields(
    tmp_path: Path,
    field: str,
) -> None:
    payload = _cohort_payload()
    payload["records"][0][field] = 0

    with pytest.raises(HistoricalH1H5EvaluatorError) as exc_info:
        _frozen(tmp_path, payload)

    assert exc_info.value.status == "blocked_prejoined_outcome_fields"
    assert field in exc_info.value.details["forbidden_fields"]


@pytest.mark.parametrize(
    ("field", "value", "expected_status"),
    [
        ("labels_joined", True, "blocked_unsafe_labels_joined"),
        ("provider_access", True, "blocked_unsafe_provider_access"),
        ("production_change", True, "blocked_unsafe_production_change"),
    ],
)
def test_evaluator_rejects_unsafe_cohort_metadata(
    tmp_path: Path,
    field: str,
    value: bool,
    expected_status: str,
) -> None:
    payload = _cohort_payload()
    payload["metadata"][field] = value

    with pytest.raises(HistoricalH1H5EvaluatorError) as exc_info:
        _frozen(tmp_path, payload)

    assert exc_info.value.status == expected_status


@pytest.mark.parametrize(
    "as_of_date",
    [
        "2024-01-31",
        "2024-02-29",
        "2025-02-28",
        "2026-09-30",
        "2026-12-31",
    ],
)
def test_evaluator_rejects_consumed_and_u3_dates(
    tmp_path: Path,
    as_of_date: str,
) -> None:
    payload = _cohort_payload(as_of_date=as_of_date)
    path = _write_json(tmp_path / "cohorts.json", payload)

    with pytest.raises(HistoricalH1H5EvaluatorError) as exc_info:
        load_frozen_cohort_output(
            path,
            as_of_date=as_of_date,
            expected_sha256=_sha256(path),
        )

    assert exc_info.value.status == "blocked_excluded_window"


def test_evaluator_rejects_digest_mismatch_before_labels(
    tmp_path: Path,
) -> None:
    path = _write_json(tmp_path / "cohorts.json", _cohort_payload())

    with pytest.raises(HistoricalH1H5EvaluatorError) as exc_info:
        load_frozen_cohort_output(
            path,
            as_of_date=AS_OF_DATE,
            expected_sha256="0" * 64,
        )

    assert exc_info.value.status == "blocked_frozen_digest_mismatch"


def test_evaluator_rejects_unknown_cohort(tmp_path: Path) -> None:
    payload = _cohort_payload()
    payload["records"][0]["cohort_id"] = "unknown_h6"

    with pytest.raises(HistoricalH1H5EvaluatorError) as exc_info:
        _frozen(tmp_path, payload)

    assert exc_info.value.status == "blocked_unknown_cohort"


@pytest.mark.parametrize("identity", [None, "wrong-validation-id"])
def test_evaluator_rejects_missing_or_mismatched_validation_id(
    tmp_path: Path,
    identity: str | None,
) -> None:
    payload = _cohort_payload()
    if identity is None:
        del payload["metadata"]["validation_id"]
    else:
        payload["metadata"]["validation_id"] = identity

    with pytest.raises(HistoricalH1H5EvaluatorError) as exc_info:
        _frozen(tmp_path, payload)

    assert exc_info.value.status in {
        "blocked_missing_validation_id",
        "blocked_validation_id_mismatch",
    }


def test_empty_and_underpowered_cohorts_remain_visible(
    tmp_path: Path,
) -> None:
    frozen = _frozen(tmp_path, _cohort_payload())
    labels_path = _write_json(tmp_path / "labels.json", _label_payload())
    result = _evaluate(
        frozen,
        load_explicit_label_source(labels_path),
        labels_path,
    )
    by_id = result.frame.set_index("cohort_name")

    assert len(by_id) == 5
    assert by_id.loc["right_tail_opportunity_watch", "member_count"] == 0
    assert bool(
        by_id.loc["right_tail_opportunity_watch", "underpowered"]
    )
    assert by_id.loc[
        "right_tail_opportunity_watch",
        "result_status",
    ] == "underpowered"
    assert by_id.loc[
        "trend_acceleration_with_crowding_guard",
        "valid_label_count",
    ] == 23
    assert not bool(
        by_id.loc[
            "trend_acceleration_with_crowding_guard",
            "underpowered",
        ]
    )
    assert by_id["empty_cohort_rate"].eq(0.4).all()


def test_missing_labels_are_counted_and_membership_is_not_mutated(
    tmp_path: Path,
) -> None:
    cohort_payload = _cohort_payload()
    frozen = _frozen(tmp_path, cohort_payload)
    before = deepcopy(frozen.payload)
    labels = _label_payload()
    labels["records"] = labels["records"][1:]
    labels_path = _write_json(tmp_path / "labels.json", labels)

    result = _evaluate(
        frozen,
        load_explicit_label_source(labels_path),
        labels_path,
    )

    assert frozen.payload == before
    h2 = result.frame.loc[
        result.frame["cohort_name"]
        == "trend_acceleration_with_crowding_guard"
    ].iloc[0]
    assert h2["member_count"] == 25
    assert h2["valid_label_count"] == 22
    assert h2["missing_label_count"] == 3
    assert result.report["metadata"]["cohort_membership_mutated"] is False
    assert result.report["metadata"]["missing_labels_counted"] is True


def test_incomplete_valid_label_horizon_is_rejected(
    tmp_path: Path,
) -> None:
    frozen = _frozen(tmp_path, _cohort_payload())
    labels = _label_payload()
    labels["records"][0]["label_future_rows_used_count"] = 19

    with pytest.raises(HistoricalH1H5EvaluatorError) as exc_info:
        _evaluate(frozen, labels, tmp_path / "labels.json")

    assert exc_info.value.status == "blocked_incomplete_label_horizon"


@pytest.mark.parametrize(
    "field",
    ["cohort_member", "rank", "is_breakout_watch"],
)
def test_label_source_cannot_carry_builder_membership_fields(
    tmp_path: Path,
    field: str,
) -> None:
    frozen = _frozen(tmp_path, _cohort_payload())
    labels = _label_payload()
    labels["records"][0][field] = True

    with pytest.raises(HistoricalH1H5EvaluatorError) as exc_info:
        _evaluate(frozen, labels, tmp_path / "labels.json")

    assert exc_info.value.status == (
        "blocked_label_source_membership_fields"
    )
    assert field in exc_info.value.details["forbidden_fields"]


@pytest.mark.parametrize(
    ("horizon_days", "benchmark", "expected_status"),
    [
        (19, "CSI300", "blocked_horizon_mismatch"),
        (20, "csi300", "blocked_benchmark_mismatch"),
    ],
)
def test_execution_identity_is_exact(
    tmp_path: Path,
    horizon_days: int,
    benchmark: str,
    expected_status: str,
) -> None:
    frozen = _frozen(tmp_path, _cohort_payload())
    labels = _label_payload()

    with pytest.raises(HistoricalH1H5EvaluatorError) as exc_info:
        evaluate_historical_h1h5_cohorts(
            frozen,
            labels,
            as_of_date=AS_OF_DATE,
            horizon_days=horizon_days,
            benchmark=benchmark,
            label_source_path=tmp_path / "labels.json",
        )

    assert exc_info.value.status == expected_status


def test_evaluator_does_not_call_provider_or_builder(
    tmp_path: Path,
) -> None:
    frozen = _frozen(tmp_path, _cohort_payload())
    labels_path = _write_json(tmp_path / "labels.json", _label_payload())

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"Forbidden call: {args} {kwargs}")

    with patch.object(socket, "create_connection", forbidden):
        with patch(
            "stock_analysis.research.opportunity_cohorts."
            "build_research_opportunity_cohorts",
            forbidden,
        ):
            result = _evaluate(
                frozen,
                load_explicit_label_source(labels_path),
                labels_path,
            )

    assert result.report["metadata"]["provider_access"] is False


def test_cli_dry_run_writes_no_files(tmp_path: Path) -> None:
    cohort_path = _write_json(
        tmp_path / "cohorts.json",
        _cohort_payload(),
    )
    labels_path = _write_json(tmp_path / "labels.json", _label_payload())
    outputs_dir = tmp_path / "outputs"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "evaluate_historical_h1h5_cohorts.py"),
            "--cohort-output",
            str(cohort_path),
            "--as-of-date",
            AS_OF_DATE,
            "--horizon-days",
            "20",
            "--benchmark",
            "CSI300",
            "--label-source",
            str(labels_path),
            "--expected-cohort-sha256",
            _sha256(cohort_path),
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
    assert payload["outputs_written"] is False
    assert payload["labels_joined_by_evaluator"] is True
    assert payload["builder_labels_joined"] is False
    assert payload["provider_access"] is False
    assert not outputs_dir.exists()


def test_schema_check_only_needs_no_real_inputs(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "evaluate_historical_h1h5_cohorts.py"),
            "--schema-check-only",
        ],
        cwd=ROOT.parent,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload == evaluator_schema_contract()
    assert payload["snapshot_loaded"] is False
    assert payload["label_source_loaded"] is False
    assert payload["outputs_written"] is False
    assert not list(tmp_path.rglob("*"))


def test_synthetic_writer_uses_future_output_pattern(
    tmp_path: Path,
) -> None:
    frozen = _frozen(tmp_path, _cohort_payload())
    labels_path = _write_json(tmp_path / "labels.json", _label_payload())
    result = _evaluate(
        frozen,
        load_explicit_label_source(labels_path),
        labels_path,
    )

    paths = write_historical_h1h5_evaluation_outputs(
        result,
        outputs_dir=tmp_path / "synthetic",
    )

    assert Path(paths["csv"]).name == (
        f"historical_h1h5_evaluation_{AS_OF_DATE}_20d.csv"
    )
    assert Path(paths["json"]).name == (
        f"historical_h1h5_evaluation_{AS_OF_DATE}_20d.json"
    )
    csv_frame = pd.read_csv(paths["csv"])
    assert set(REQUIRED_OUTPUT_FIELDS).issubset(csv_frame.columns)


def _evaluate(
    frozen,
    labels: dict[str, object],
    labels_path: Path,
):
    return evaluate_historical_h1h5_cohorts(
        frozen,
        labels,
        as_of_date=AS_OF_DATE,
        horizon_days=20,
        benchmark="CSI300",
        label_source_path=labels_path,
    )


def _frozen(
    tmp_path: Path,
    payload: dict[str, object],
):
    path = _write_json(tmp_path / "cohorts.json", payload)
    return load_frozen_cohort_output(
        path,
        as_of_date=AS_OF_DATE,
        expected_sha256=_sha256(path),
    )


def _cohort_payload(
    *,
    as_of_date: str = AS_OF_DATE,
) -> dict[str, object]:
    symbols = [f"TEST{index:03d}" for index in range(25)]
    summaries = []
    records = []
    for cohort_index, (cohort_id, role) in enumerate(COHORT_ROLES.items()):
        member_count = {0: 3, 1: 25, 2: 0, 3: 0, 4: 5}[cohort_index]
        summaries.append(
            {
                "cohort_id": cohort_id,
                "cohort_role": role,
                "research_only": True,
                "input_row_count": len(symbols),
                "member_count": member_count,
                "blocked_row_count": 0,
            }
        )
        for index, symbol in enumerate(symbols):
            records.append(
                {
                    "as_of_date": as_of_date,
                    "symbol": symbol,
                    "cohort_id": cohort_id,
                    "cohort_role": role,
                    "cohort_member": index < member_count,
                    "annotation_status": (
                        "included"
                        if index < member_count
                        else "not_in_cohort"
                    ),
                    "research_only": True,
                    "future_rows_excluded_count": 10,
                }
            )
    return {
        "metadata": {
            "status": "ok",
            "research_only": True,
            "provider_access": False,
            "labels_joined": False,
            "production_change": False,
            "validation_id": "h1h5-historical-sealed-v1",
            "as_of_date": as_of_date,
            "input_row_count": len(symbols),
            "output_record_count": len(records),
        },
        "cohorts": summaries,
        "records": records,
    }


def _label_payload() -> dict[str, object]:
    rows = []
    for index in range(25):
        valid = index < 23
        winner = valid and index % 5 == 0
        loser = valid and index % 5 == 1
        rows.append(
            {
                "symbol": f"TEST{index:03d}",
                "as_of_date": AS_OF_DATE,
                "horizon_days": 20,
                "benchmark": "CSI300",
                "data_quality": "ok" if valid else "missing_price",
                "future_return": 0.10 + index / 100 if valid else None,
                "benchmark_future_return": 0.05 if valid else None,
                "excess_return": 0.05 + index / 100 if valid else None,
                "winner": winner if valid else None,
                "loser": loser if valid else None,
                "severe_drawdown": (
                    index % 4 == 0 if valid else None
                ),
                "right_tail": winner if valid else None,
                "max_drawdown_during_holding": (
                    -0.05 - index / 100 if valid else None
                ),
                "label_future_rows_used_count": 20 if valid else 0,
            }
        )
    return {
        "metadata": {
            "validation_id": "h1h5-historical-sealed-v1",
            "evidence_level": "historical_sealed_not_prospective",
            "as_of_date": AS_OF_DATE,
            "horizon_days": 20,
            "benchmark": "CSI300",
            "label_window_complete": True,
            "provider_access": False,
            "production_change": False,
        },
        "records": rows,
    }


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()
