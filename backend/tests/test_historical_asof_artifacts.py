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

from stock_analysis.research.feature_only_snapshot import find_outcome_columns
from stock_analysis.research.historical_asof_artifacts import (
    HistoricalAsOfArtifactError,
    build_historical_asof_artifacts,
    write_historical_asof_artifacts,
)


AS_OF_DATE = "2026-01-30"


@pytest.fixture
def asof_inputs(tmp_path: Path) -> dict[str, Path]:
    factors_path = tmp_path / "factors.csv"
    multi_list_path = tmp_path / "multi_lists.json"
    symbols = [f"sh.60{index:04d}" for index in range(100)]
    pd.DataFrame(
        [
            {
                "symbol": symbol,
                "as_of_date": AS_OF_DATE,
                "momentum_20d": 0.01 + index / 10000,
                "volatility_20d": 0.02,
                "source": "cache_only_test",
            }
            for index, symbol in enumerate(symbols)
        ]
    ).to_csv(factors_path, index=False)
    payload = {
        "as_of_date": AS_OF_DATE,
        "source_files": {"candidates": "outputs/daily/candidates.csv"},
        "lists": [
            _list_payload(
                "breakout_watch",
                "breakout",
                AS_OF_DATE,
                [
                    {
                        "symbol": symbols[0],
                        "rank": 2,
                        "total_score": 78.0,
                        "primary_type": "breakout",
                        "label_reason": "as-of research classification",
                    }
                ],
            ),
            _list_payload(
                "accumulation_watch",
                "accumulation",
                AS_OF_DATE,
                [
                    {
                        "symbol": symbols[0],
                        "rank": 1,
                        "total_score": 82.0,
                        "research_label": "as-of research classification",
                    },
                    {
                        "symbol": symbols[1],
                        "rank": 3,
                        "total_score": 75.0,
                    },
                ],
            ),
            _list_payload(
                "high_risk_active",
                "high risk",
                AS_OF_DATE,
                [{"symbol": symbols[2], "rank": 4, "risk_level": "high"}],
            ),
        ],
    }
    multi_list_path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    return {
        "root": tmp_path,
        "factors": factors_path,
        "multi_list": multi_list_path,
    }


@pytest.mark.parametrize(
    ("as_of_date", "expected_status"),
    [
        ("2026-02-27", "blocked_non_primary_window"),
        ("2026-05-29", "blocked_non_primary_window"),
        ("2026-06-30", "blocked_non_primary_window"),
        ("2024-01-31", "blocked_excluded_window"),
        ("2026-09-30", "blocked_excluded_window"),
        ("2026-12-31", "blocked_excluded_window"),
    ],
)
def test_exporter_accepts_primary_dates_only(
    asof_inputs: dict[str, Path],
    as_of_date: str,
    expected_status: str,
) -> None:
    with pytest.raises(HistoricalAsOfArtifactError) as exc_info:
        _build(asof_inputs, as_of_date=as_of_date)

    assert exc_info.value.status == expected_status


def test_exporter_projects_full_universe_and_audits_dropped_labels(
    asof_inputs: dict[str, Path],
) -> None:
    result = _build(asof_inputs)

    assert len(result.factors) == 100
    assert len(result.membership) == 100
    assert find_outcome_columns(result.factors.columns) == []
    assert find_outcome_columns(result.membership.columns) == []
    assert result.metadata["dropped_unsafe_fields"] == [
        "label_reason",
        "research_label",
    ]
    first = result.membership.iloc[0]
    assert bool(first["is_breakout_watch"]) is True
    assert bool(first["is_accumulation_watch"]) is True
    assert first["rank"] == 1
    assert first["total_score"] == 82.0
    assert first["captured_positive_lists"] == (
        "breakout_watch;accumulation_watch"
    )
    assert result.membership["provider_access"].eq(False).all()
    assert result.membership["labels_joined"].eq(False).all()


@pytest.mark.parametrize("field", ["future_return", "winner", "outcome"])
def test_exporter_rejects_non_droppable_outcome_keys(
    asof_inputs: dict[str, Path],
    field: str,
) -> None:
    payload = json.loads(
        asof_inputs["multi_list"].read_text(encoding="utf-8")
    )
    payload["lists"][0]["items"][0][field] = 1
    asof_inputs["multi_list"].write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    with pytest.raises(HistoricalAsOfArtifactError) as exc_info:
        _build(asof_inputs)

    assert exc_info.value.status == "blocked_unsafe_multi_list_fields"
    assert field in exc_info.value.details["forbidden_fields"]


def test_exporter_rejects_factor_label_column(
    asof_inputs: dict[str, Path],
) -> None:
    factors = pd.read_csv(asof_inputs["factors"])
    factors["label"] = "unsafe"
    factors.to_csv(asof_inputs["factors"], index=False)

    with pytest.raises(HistoricalAsOfArtifactError) as exc_info:
        _build(asof_inputs)

    assert exc_info.value.status == "blocked_unsafe_factors"


def test_exporter_rejects_validation_path(
    asof_inputs: dict[str, Path],
) -> None:
    forbidden = (
        asof_inputs["root"]
        / "validation"
        / "walk_forward_predictions.csv"
    )
    forbidden.parent.mkdir()
    forbidden.write_bytes(asof_inputs["factors"].read_bytes())

    with pytest.raises(HistoricalAsOfArtifactError) as exc_info:
        build_historical_asof_artifacts(
            as_of_date=AS_OF_DATE,
            factors_file=forbidden,
            multi_list_file=asof_inputs["multi_list"],
        )

    assert exc_info.value.status == "blocked_forbidden_input_artifact"


def test_default_cli_dry_run_writes_nothing(
    asof_inputs: dict[str, Path],
    tmp_path: Path,
) -> None:
    outputs_dir = tmp_path / "outputs"
    completed = _run_cli(asof_inputs, outputs_dir)
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0, completed.stderr
    assert payload["dry_run"] is True
    assert payload["outputs_written"] is False
    assert payload["provider_access"] is False
    assert payload["future_returns_computed"] is False
    assert not outputs_dir.exists()


def test_write_output_writes_only_two_safe_csvs(
    asof_inputs: dict[str, Path],
    tmp_path: Path,
) -> None:
    outputs_dir = tmp_path / "outputs"
    completed = _run_cli(asof_inputs, outputs_dir, write_output=True)
    payload = json.loads(completed.stdout)
    files = sorted(
        path.relative_to(outputs_dir).as_posix()
        for path in outputs_dir.rglob("*")
        if path.is_file()
    )

    assert completed.returncode == 0, completed.stderr
    assert payload["outputs_written"] is True
    assert files == [
        f"experiments/historical_h1h5_factors_{AS_OF_DATE}.csv",
        f"experiments/historical_h1h5_membership_{AS_OF_DATE}.csv",
    ]
    for path in payload["outputs"].values():
        assert find_outcome_columns(pd.read_csv(path).columns) == []


def test_direct_writer_has_fixed_output_roles(
    asof_inputs: dict[str, Path],
    tmp_path: Path,
) -> None:
    paths = write_historical_asof_artifacts(
        _build(asof_inputs),
        outputs_dir=tmp_path,
    )

    assert set(paths) == {"factors_csv", "membership_csv"}


def _list_payload(
    list_id: str,
    list_name: str,
    as_of_date: str,
    items: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "list_id": list_id,
        "list_name": list_name,
        "as_of_date": as_of_date,
        "items": items,
    }


def _build(
    inputs: dict[str, Path],
    *,
    as_of_date: str = AS_OF_DATE,
):
    return build_historical_asof_artifacts(
        as_of_date=as_of_date,
        factors_file=inputs["factors"],
        multi_list_file=inputs["multi_list"],
    )


def _run_cli(
    inputs: dict[str, Path],
    outputs_dir: Path,
    *,
    write_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "build_historical_h1h5_asof_artifacts.py"),
        "--as-of-date",
        AS_OF_DATE,
        "--factors-file",
        str(inputs["factors"]),
        "--multi-list-file",
        str(inputs["multi_list"]),
        "--outputs-dir",
        str(outputs_dir),
    ]
    if write_output:
        command.append("--write-output")
    return subprocess.run(
        command,
        cwd=ROOT.parent,
        capture_output=True,
        text=True,
        check=False,
    )
