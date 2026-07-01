from __future__ import annotations

import csv
import json
from pathlib import Path
import socket
import subprocess
import sys
from unittest.mock import patch

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.research.feature_only_snapshot import (
    REQUIRED_COLUMNS,
)
from stock_analysis.research.historical_snapshot_inventory import (
    classify_inventory_window,
    inventory_historical_source_snapshots,
)


AS_OF_DATE = "2026-01-30"


def test_missing_source_snapshot_is_reported_without_provider_access(
    tmp_path: Path,
) -> None:
    def forbidden_network(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"Unexpected network access: {args} {kwargs}")

    repo_root = _empty_repo(tmp_path)
    with patch.object(socket, "create_connection", forbidden_network):
        report = inventory_historical_source_snapshots(repo_root)

    window = _window(report, AS_OF_DATE)
    assert report["provider_access"] is False
    assert report["cache_prewarm_executed"] is False
    assert report["validation_run"] is False
    assert report["validation_outputs_read"] is False
    assert window["source_snapshot_exists"] is False
    assert window["phase3_7_readiness_status"] == (
        "blocked_missing_source_snapshot"
    )


def test_existing_safe_source_snapshot_is_detected(
    tmp_path: Path,
) -> None:
    repo_root = _empty_repo(tmp_path)
    source_path = (
        repo_root
        / "outputs"
        / "experiments"
        / f"historical_h1h5_source_snapshot_{AS_OF_DATE}.csv"
    )
    _write_source_snapshot(source_path, AS_OF_DATE, row_count=100)

    report = inventory_historical_source_snapshots(repo_root)
    window = _window(report, AS_OF_DATE)

    assert window["source_snapshot_exists"] is True
    assert window["source_snapshot_format_status"] == "safe_header"
    assert window["source_snapshot_row_count"] == 100
    assert window["source_snapshot_forbidden_columns"] == []


def test_source_snapshot_with_outcome_header_is_unsafe(
    tmp_path: Path,
) -> None:
    repo_root = _empty_repo(tmp_path)
    source_path = (
        repo_root
        / "outputs"
        / "experiments"
        / f"historical_h1h5_source_snapshot_{AS_OF_DATE}.csv"
    )
    _write_source_snapshot(
        source_path,
        AS_OF_DATE,
        row_count=100,
        extra_columns=["future_return"],
    )

    report = inventory_historical_source_snapshots(repo_root)
    window = _window(report, AS_OF_DATE)

    assert window["source_snapshot_format_status"] == "unsafe_header"
    assert window["source_snapshot_forbidden_columns"] == [
        "future_return"
    ]
    assert window["inventory_blocker"] == (
        "blocked_unsafe_or_underpowered_source_snapshot"
    )


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
def test_consumed_and_u3_windows_are_not_eligible(
    as_of_date: str,
) -> None:
    result = classify_inventory_window(as_of_date)

    assert result["eligible"] is False
    assert result["status"] == "excluded_consumed_or_u3_window"


def test_inventory_contains_no_outcome_values_or_performance_results(
    tmp_path: Path,
) -> None:
    report = inventory_historical_source_snapshots(_empty_repo(tmp_path))

    assert report["outcome_values_read"] is False
    assert report["future_labels_generated"] is False
    assert report["future_returns_computed"] is False
    assert report["evaluator_called"] is False
    assert report["h1h5_cohort_outputs_generated"] is False
    for forbidden_key in (
        "future_return",
        "future_excess_return",
        "benchmark_return",
        "winner",
        "loser",
    ):
        assert forbidden_key not in report


def test_cli_prints_only_and_creates_no_inventory_file(
    tmp_path: Path,
) -> None:
    repo_root = _empty_repo(tmp_path)
    before = sorted(
        path.relative_to(repo_root)
        for path in repo_root.rglob("*")
        if path.is_file()
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "scripts"
                / "inventory_historical_h1h5_source_snapshots.py"
            ),
            "--repo-root",
            str(repo_root),
        ],
        cwd=ROOT.parent,
        capture_output=True,
        text=True,
        check=False,
    )

    after = sorted(
        path.relative_to(repo_root)
        for path in repo_root.rglob("*")
        if path.is_file()
    )
    payload = json.loads(completed.stdout)
    assert completed.returncode == 0, completed.stderr
    assert payload["inventory_only"] is True
    assert payload["provider_access"] is False
    assert before == after


def _empty_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "outputs" / "experiments").mkdir(parents=True)
    (root / "data" / "cache" / "daily-use" / "baostock").mkdir(
        parents=True
    )
    return root


def _window(report: dict[str, object], as_of_date: str) -> dict[str, object]:
    return next(
        item
        for item in report["windows"]
        if item["as_of_date"] == as_of_date
    )


def _write_source_snapshot(
    path: Path,
    as_of_date: str,
    *,
    row_count: int,
    extra_columns: list[str] | None = None,
) -> None:
    columns = [
        *REQUIRED_COLUMNS,
        "technical_volatility_20d",
        "latest_input_date",
        *(extra_columns or []),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for index in range(row_count):
            row = {column: 0 for column in columns}
            row.update(
                {
                    "as_of_date": as_of_date,
                    "symbol": f"TEST{index:03d}",
                    "leakage_guard_applied": True,
                    "latest_input_date": as_of_date,
                }
            )
            writer.writerow(row)
