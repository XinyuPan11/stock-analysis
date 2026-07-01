from __future__ import annotations

import json
from pathlib import Path
import shutil
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

from stock_analysis.research.feature_only_snapshot import (
    build_feature_only_snapshot,
    find_outcome_columns,
)
from stock_analysis.research.historical_source_snapshot_builder import (
    HISTORICAL_EVIDENCE_LEVEL,
    HISTORICAL_VALIDATION_ID,
    TECHNICAL_FEATURE_FIELDS,
    HistoricalSourceSnapshotError,
    build_historical_source_snapshot,
    write_historical_source_snapshot_outputs,
)


AS_OF_DATE = "2026-01-30"


@pytest.fixture(scope="module")
def safe_artifacts(
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("historical-source-safe")
    factors_path = root / "safe_factors.csv"
    membership_path = root / "safe_membership.csv"
    cache_dir = root / "cache"
    symbols = [f"sh.60{index:04d}" for index in range(100)]
    pd.DataFrame(
        [
            {
                "symbol": symbol,
                "as_of_date": AS_OF_DATE,
                "momentum_20d": 0.02,
                "momentum_60d": 0.05,
                "volatility_20d": 0.01,
                "max_drawdown_60d": -0.08,
                "source": "synthetic_safe_test",
            }
            for symbol in symbols
        ]
    ).to_csv(factors_path, index=False)
    pd.DataFrame(
        [
            {
                "symbol": symbol,
                "as_of_date": AS_OF_DATE,
                "rank": index + 1,
                "total_score": 80.0 - index / 10,
                "is_breakout_watch": index % 2 == 0,
                "is_accumulation_watch": index % 3 == 0,
                "is_high_confidence": index < 10,
            }
            for index, symbol in enumerate(symbols)
        ]
    ).to_csv(membership_path, index=False)
    for index, symbol in enumerate(symbols):
        _write_daily_cache(
            cache_dir,
            symbol,
            price_offset=float(index),
        )
    return {
        "root": root,
        "factors": factors_path,
        "membership": membership_path,
        "cache": cache_dir,
    }


def test_builder_rejects_non_preregistered_date(
    safe_artifacts: dict[str, Path],
) -> None:
    with pytest.raises(HistoricalSourceSnapshotError) as exc_info:
        _build(safe_artifacts, as_of_date="2026-06-30")

    assert exc_info.value.status == "blocked_unknown_historical_window"


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
def test_builder_rejects_consumed_and_u3_dates(
    safe_artifacts: dict[str, Path],
    as_of_date: str,
) -> None:
    with pytest.raises(HistoricalSourceSnapshotError) as exc_info:
        _build(safe_artifacts, as_of_date=as_of_date)

    assert exc_info.value.status == "blocked_excluded_window"


def test_builder_rejects_validation_prediction_input(
    safe_artifacts: dict[str, Path],
    tmp_path: Path,
) -> None:
    forbidden = (
        tmp_path
        / "outputs"
        / "validation"
        / f"walk_forward_predictions_{AS_OF_DATE}_20d.csv"
    )
    forbidden.parent.mkdir(parents=True)
    shutil.copyfile(safe_artifacts["factors"], forbidden)

    with pytest.raises(HistoricalSourceSnapshotError) as exc_info:
        build_historical_source_snapshot(
            as_of_date=AS_OF_DATE,
            factors_file=forbidden,
            membership_file=safe_artifacts["membership"],
            cache_dir=safe_artifacts["cache"],
        )

    assert exc_info.value.status == "blocked_forbidden_input_artifact"


@pytest.mark.parametrize(
    ("role", "column"),
    [
        ("factors", "future_return"),
        ("factors", "label"),
        ("membership", "winner"),
        ("membership", "label_reason"),
    ],
)
def test_builder_rejects_outcome_or_label_columns(
    safe_artifacts: dict[str, Path],
    tmp_path: Path,
    role: str,
    column: str,
) -> None:
    path = tmp_path / f"unsafe-{role}-{column}.csv"
    frame = pd.read_csv(safe_artifacts[role])
    frame[column] = 0
    frame.to_csv(path, index=False)
    factors = path if role == "factors" else safe_artifacts["factors"]
    membership = (
        path if role == "membership" else safe_artifacts["membership"]
    )

    with pytest.raises(HistoricalSourceSnapshotError) as exc_info:
        build_historical_source_snapshot(
            as_of_date=AS_OF_DATE,
            factors_file=factors,
            membership_file=membership,
            cache_dir=safe_artifacts["cache"],
        )

    assert exc_info.value.status == "blocked_forbidden_input_columns"
    assert column in exc_info.value.details["forbidden_columns"]


def test_builder_rejects_latest_input_date_after_as_of(
    safe_artifacts: dict[str, Path],
    tmp_path: Path,
) -> None:
    path = tmp_path / "future-input-date.csv"
    factors = pd.read_csv(safe_artifacts["factors"])
    factors["latest_input_date"] = "2026-02-02"
    factors.to_csv(path, index=False)

    with pytest.raises(HistoricalSourceSnapshotError) as exc_info:
        build_historical_source_snapshot(
            as_of_date=AS_OF_DATE,
            factors_file=path,
            membership_file=safe_artifacts["membership"],
            cache_dir=safe_artifacts["cache"],
        )

    assert exc_info.value.status == "blocked_point_in_time_violation"


def test_builder_fails_when_required_artifact_is_missing(
    safe_artifacts: dict[str, Path],
    tmp_path: Path,
) -> None:
    with pytest.raises(HistoricalSourceSnapshotError) as exc_info:
        build_historical_source_snapshot(
            as_of_date=AS_OF_DATE,
            factors_file=tmp_path / "missing-factors.csv",
            membership_file=safe_artifacts["membership"],
            cache_dir=safe_artifacts["cache"],
        )

    assert exc_info.value.status == "blocked_missing_as_of_artifact"


def test_builder_produces_feature_exporter_compatible_label_free_snapshot(
    safe_artifacts: dict[str, Path],
) -> None:
    result = _build(safe_artifacts)

    assert len(result.frame) == 100
    assert set(TECHNICAL_FEATURE_FIELDS).issubset(result.frame.columns)
    assert {
        "is_breakout_watch",
        "is_accumulation_watch",
        "rank",
        "total_score",
    }.issubset(result.frame.columns)
    assert find_outcome_columns(result.frame.columns) == []
    assert result.frame["leakage_guard_applied"].all()
    assert result.frame["provider_access"].eq(False).all()
    assert result.frame["labels_joined"].eq(False).all()
    assert result.frame["production_change"].eq(False).all()
    assert result.metadata["validation_id"] == HISTORICAL_VALIDATION_ID
    assert result.metadata["evidence_level"] == HISTORICAL_EVIDENCE_LEVEL
    assert result.metadata["provider_access"] is False
    assert result.metadata["labels_joined"] is False
    assert result.metadata["production_change"] is False

    exported = build_feature_only_snapshot(
        result.frame,
        as_of_date=AS_OF_DATE,
        source_snapshot_path="synthetic-safe-source.csv",
        drop_outcome_columns=False,
    )
    assert exported.metadata["status"] == "ok"
    assert exported.metadata["output_row_count"] == 100


def test_builder_blocks_universe_below_100(
    safe_artifacts: dict[str, Path],
    tmp_path: Path,
) -> None:
    factors_path = tmp_path / "small-factors.csv"
    membership_path = tmp_path / "small-membership.csv"
    pd.read_csv(safe_artifacts["factors"]).iloc[:99].to_csv(
        factors_path,
        index=False,
    )
    pd.read_csv(safe_artifacts["membership"]).iloc[:99].to_csv(
        membership_path,
        index=False,
    )

    with pytest.raises(HistoricalSourceSnapshotError) as exc_info:
        build_historical_source_snapshot(
            as_of_date=AS_OF_DATE,
            factors_file=factors_path,
            membership_file=membership_path,
            cache_dir=safe_artifacts["cache"],
        )

    assert exc_info.value.status == "blocked_insufficient_source_universe"


def test_missing_cache_blocks_without_provider_access(
    safe_artifacts: dict[str, Path],
    tmp_path: Path,
) -> None:
    def forbidden_network(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"Unexpected network access: {args} {kwargs}")

    with patch.object(socket, "create_connection", forbidden_network):
        with pytest.raises(HistoricalSourceSnapshotError) as exc_info:
            build_historical_source_snapshot(
                as_of_date=AS_OF_DATE,
                factors_file=safe_artifacts["factors"],
                membership_file=safe_artifacts["membership"],
                cache_dir=tmp_path / "empty-cache",
            )

    assert exc_info.value.status == "blocked_required_features_unavailable"


def test_default_cli_dry_run_writes_no_files(
    safe_artifacts: dict[str, Path],
    tmp_path: Path,
) -> None:
    outputs_dir = tmp_path / "outputs"
    completed = _run_cli(safe_artifacts, outputs_dir)

    payload = json.loads(completed.stdout)
    assert completed.returncode == 0, completed.stderr
    assert payload["dry_run"] is True
    assert payload["outputs_written"] is False
    assert payload["provider_access"] is False
    assert payload["labels_joined"] is False
    assert payload["validation_run"] is False
    assert payload["h1h5_cohort_builder_called"] is False
    assert not outputs_dir.exists()


def test_write_output_writes_only_source_csv_and_json(
    safe_artifacts: dict[str, Path],
    tmp_path: Path,
) -> None:
    outputs_dir = tmp_path / "outputs"
    completed = _run_cli(
        safe_artifacts,
        outputs_dir,
        write_output=True,
    )

    payload = json.loads(completed.stdout)
    files = sorted(
        path.relative_to(outputs_dir).as_posix()
        for path in outputs_dir.rglob("*")
        if path.is_file()
    )
    assert completed.returncode == 0, completed.stderr
    assert payload["outputs_written"] is True
    assert files == [
        f"experiments/historical_h1h5_source_snapshot_{AS_OF_DATE}.csv",
        f"experiments/historical_h1h5_source_snapshot_{AS_OF_DATE}.json",
    ]
    csv_frame = pd.read_csv(payload["outputs"]["csv"])
    json_payload = json.loads(
        Path(payload["outputs"]["json"]).read_text(encoding="utf-8")
    )
    assert find_outcome_columns(csv_frame.columns) == []
    assert json_payload["metadata"]["labels_joined"] is False
    assert json_payload["metadata"]["provider_access"] is False
    assert json_payload["metadata"]["validation_outputs_read"] is False


def test_direct_writer_writes_source_files_only(
    safe_artifacts: dict[str, Path],
    tmp_path: Path,
) -> None:
    result = _build(safe_artifacts)

    paths = write_historical_source_snapshot_outputs(
        result,
        outputs_dir=tmp_path,
    )

    assert set(paths) == {"csv", "json"}
    assert Path(paths["csv"]).name.startswith(
        "historical_h1h5_source_snapshot_"
    )


def _build(
    artifacts: dict[str, Path],
    *,
    as_of_date: str = AS_OF_DATE,
):
    return build_historical_source_snapshot(
        as_of_date=as_of_date,
        factors_file=artifacts["factors"],
        membership_file=artifacts["membership"],
        cache_dir=artifacts["cache"],
    )


def _run_cli(
    artifacts: dict[str, Path],
    outputs_dir: Path,
    *,
    write_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "build_historical_h1h5_source_snapshot.py"),
        "--as-of-date",
        AS_OF_DATE,
        "--factors-file",
        str(artifacts["factors"]),
        "--membership-file",
        str(artifacts["membership"]),
        "--cache-dir",
        str(artifacts["cache"]),
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


def _write_daily_cache(
    cache_dir: Path,
    symbol: str,
    *,
    price_offset: float,
) -> None:
    path = (
        cache_dir
        / "baostock"
        / "stock_daily"
        / "adjusted"
        / f"{symbol}.csv"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    dates = list(pd.bdate_range(end=AS_OF_DATE, periods=70))
    dates.extend(pd.bdate_range(start="2026-02-02", periods=2))
    rows = []
    for index, trade_date in enumerate(dates):
        price = 10.0 + price_offset / 100 + index * 0.02
        rows.append(
            {
                "symbol": symbol,
                "trade_date": trade_date.strftime("%Y-%m-%d"),
                "close": price,
                "adj_close": price,
                "amount": 1_000_000 + index * 10_000,
                "volume": 100_000 + index * 1_000,
                "source": "synthetic_safe_test",
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)
