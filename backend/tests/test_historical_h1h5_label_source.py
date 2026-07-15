from __future__ import annotations

import hashlib
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

from stock_analysis.research.historical_h1h5_label_definitions import (
    FORBIDDEN_LABEL_SOURCE_COLUMNS,
    REQUIRED_LABEL_SOURCE_COLUMNS,
)
from stock_analysis.research.historical_h1h5_evaluator import (
    load_explicit_label_source,
    validate_explicit_label_source,
)
from stock_analysis.research.historical_h1h5_label_source import (
    HistoricalH1H5LabelSourceError,
    build_historical_h1h5_label_source,
    write_historical_h1h5_label_source_outputs,
)


AS_OF_DATE = "2026-03-31"
CONFIG = (
    ROOT.parent
    / "research"
    / "configs"
    / "historical_h1h5_label_definitions.v1.json"
)
COHORT_ROLES = {
    "low_position_revaluation_watch": "opportunity_observation",
    "trend_acceleration_with_crowding_guard": "opportunity_observation",
    "right_tail_opportunity_watch": "opportunity_observation",
    "high_position_crowding_risk": "risk_annotation",
    "false_breakout_risk": "risk_annotation",
}


@pytest.fixture
def source_fixture(tmp_path: Path) -> dict[str, object]:
    outputs = tmp_path / "outputs"
    cache = tmp_path / "cache"
    symbols = [f"TEST{index:03d}" for index in range(25)]
    cohort = outputs / "research" / f"opportunity_cohorts_{AS_OF_DATE}.json"
    _write_cohort(cohort, symbols)
    dates = pd.bdate_range(AS_OF_DATE, periods=21)
    benchmark_prices = [100.0 + 2.0 * index / 20 for index in range(21)]
    _write_prices(cache, "sh.000300", dates, benchmark_prices)
    for index, symbol in enumerate(symbols):
        end = 80.0 + 2.0 * index
        prices = [100.0 + (end - 100.0) * step / 20 for step in range(21)]
        if index == 0:
            prices[1] = 70.0
        _write_prices(cache, symbol, dates, prices)
    return {
        "outputs": outputs,
        "cache": cache,
        "cohort": cohort,
        "cohort_sha": _sha256(cohort),
        "symbols": symbols,
    }


def test_builder_computes_frozen_continuous_metrics(
    source_fixture: dict[str, object],
) -> None:
    result = _build(source_fixture)
    row = result.frame.set_index("symbol").loc["TEST024"]

    assert row["as_of_close"] == pytest.approx(100.0)
    assert row["future_end_close"] == pytest.approx(128.0)
    assert row["future_return_20d"] == pytest.approx(0.28)
    assert row["benchmark_return_20d"] == pytest.approx(0.02)
    assert row["excess_return_20d"] == pytest.approx(0.26)
    assert row["max_future_close_20d"] == pytest.approx(128.0)
    assert row["max_upside_20d"] == pytest.approx(0.28)
    assert row["max_drawdown_20d"] == pytest.approx(0.0)
    assert result.metadata["provider_access"] is False
    assert result.metadata["labels_joined"] is False


def test_builder_computes_frozen_boolean_labels(
    source_fixture: dict[str, object],
) -> None:
    frame = _build(source_fixture).frame

    assert int(frame["winner"].sum()) == 10
    assert int(frame["loser"].sum()) == 10
    assert int(frame["right_tail"].sum()) == 5
    assert bool(frame.set_index("symbol").loc["TEST000", "severe_drawdown"])
    assert not (frame["winner"].astype(bool) & frame["loser"].astype(bool)).any()


def test_label_definition_sha_mismatch_blocks_builder(
    source_fixture: dict[str, object],
    tmp_path: Path,
) -> None:
    changed = tmp_path / "changed.json"
    shutil.copyfile(CONFIG, changed)
    changed.write_text(changed.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(HistoricalH1H5LabelSourceError) as exc_info:
        _build(source_fixture, config=changed)

    assert exc_info.value.status == "blocked_label_definition_digest_mismatch"


@pytest.mark.parametrize(
    "as_of_date",
    ["2026-02-27", "2026-09-30", "2026-12-31", "2024-01-31", "2025-02-28"],
)
def test_builder_rejects_non_primary_u3_and_consumed_dates(
    source_fixture: dict[str, object],
    as_of_date: str,
) -> None:
    with pytest.raises(HistoricalH1H5LabelSourceError) as exc_info:
        _build(source_fixture, as_of_date=as_of_date)

    assert exc_info.value.status in {
        "blocked_non_primary_window",
        "blocked_prohibited_window",
    }


def test_builder_requires_adj_close_and_never_falls_back_to_close(
    source_fixture: dict[str, object],
) -> None:
    path = _cache_file(source_fixture, "TEST000")
    frame = pd.read_csv(path).drop(columns=["adj_close"])
    frame["close"] = 999.0
    frame.to_csv(path, index=False)

    result = _build(source_fixture)
    row = result.frame.set_index("symbol").loc["TEST000"]

    assert not bool(row["valid_label"])
    assert row["missing_label_reason"] == "price_field_ambiguity"
    assert pd.isna(row["future_return_20d"])


def test_builder_preserves_incomplete_symbol_horizon_as_missing_label(
    source_fixture: dict[str, object],
) -> None:
    path = _cache_file(source_fixture, "TEST001")
    pd.read_csv(path).iloc[:-1].to_csv(path, index=False)

    result = _build(source_fixture)
    row = result.frame.set_index("symbol").loc["TEST001"]

    assert len(result.frame) == 25
    assert not bool(row["valid_label"])
    assert row["missing_label_reason"] == "incomplete_20d_horizon"


def test_winner_loser_conflict_fails_closed_for_degenerate_universe(
    source_fixture: dict[str, object],
) -> None:
    cohort = Path(source_fixture["cohort"])
    _write_cohort(cohort, ["TEST000"])

    with pytest.raises(HistoricalH1H5LabelSourceError) as exc_info:
        _build(source_fixture, expected_cohort_sha256=_sha256(cohort))

    assert exc_info.value.status == "blocked_winner_loser_conflict"


def test_builder_is_dry_by_default_and_writer_writes_only_label_pair(
    source_fixture: dict[str, object],
) -> None:
    result = _build(source_fixture)
    experiments = Path(source_fixture["outputs"]) / "experiments"

    assert not experiments.exists()
    paths = write_historical_h1h5_label_source_outputs(
        result,
        outputs_dir=source_fixture["outputs"],
    )

    assert sorted(path.name for path in experiments.iterdir()) == [
        f"historical_h1h5_label_source_{AS_OF_DATE}_20d.csv",
        f"historical_h1h5_label_source_{AS_OF_DATE}_20d.json",
    ]
    csv = pd.read_csv(paths["csv"])
    payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert tuple(csv.columns) == REQUIRED_LABEL_SOURCE_COLUMNS
    assert not (set(csv.columns) & FORBIDDEN_LABEL_SOURCE_COLUMNS)
    assert payload["metadata"]["csv_sha256"] == _sha256(Path(paths["csv"]))
    assert not (Path(source_fixture["outputs"]) / "validation").exists()
    loaded_csv = load_explicit_label_source(paths["csv"])
    status = validate_explicit_label_source(
        loaded_csv,
        as_of_date=AS_OF_DATE,
        horizon_days=20,
        benchmark="CSI300",
    )
    assert status["status"] == "safe_label_source"
    assert status["row_count"] == 25
    assert "future_return" not in csv.columns
    assert "data_quality" not in csv.columns


def test_existing_final_evaluation_output_blocks_builder(
    source_fixture: dict[str, object],
) -> None:
    final = (
        Path(source_fixture["outputs"])
        / "validation"
        / f"historical_h1h5_evaluation_{AS_OF_DATE}_20d.json"
    )
    final.parent.mkdir(parents=True)
    final.write_text("{}", encoding="utf-8")

    with pytest.raises(HistoricalH1H5LabelSourceError) as exc_info:
        _build(source_fixture)

    assert exc_info.value.status == "blocked_existing_validation_output"


def test_builder_never_attempts_provider_or_network(
    source_fixture: dict[str, object],
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"Unexpected network call: {args} {kwargs}")

    with patch.object(socket, "create_connection", forbidden):
        result = _build(source_fixture)

    assert result.metadata["local_cache_only"] is True
    assert result.metadata["provider_access"] is False


def _build(
    fixture: dict[str, object],
    *,
    as_of_date: str = AS_OF_DATE,
    config: Path = CONFIG,
    expected_cohort_sha256: str | None = None,
):
    return build_historical_h1h5_label_source(
        as_of_date=as_of_date,
        horizon_days=20,
        benchmark="CSI300",
        label_definition_config=config,
        cache_dir=fixture["cache"],
        outputs_dir=fixture["outputs"],
        cohort_output=fixture["cohort"],
        expected_cohort_sha256=(
            expected_cohort_sha256 or str(fixture["cohort_sha"])
        ),
    )


def _write_cohort(path: Path, symbols: list[str]) -> None:
    records = []
    summaries = []
    for cohort_id, role in COHORT_ROLES.items():
        summaries.append({"cohort_id": cohort_id, "cohort_role": role, "member_count": 0})
        for symbol in symbols:
            records.append(
                {
                    "as_of_date": AS_OF_DATE,
                    "symbol": symbol,
                    "cohort_id": cohort_id,
                    "cohort_role": role,
                    "cohort_member": False,
                    "research_only": True,
                }
            )
    payload = {
        "metadata": {
            "as_of_date": AS_OF_DATE,
            "provider_access": False,
            "labels_joined": False,
            "production_change": False,
        },
        "cohorts": summaries,
        "records": records,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_prices(
    cache: Path,
    symbol: str,
    dates: pd.DatetimeIndex,
    prices: list[float],
) -> None:
    path = cache / "baostock" / "stock_daily" / "adjusted" / f"{symbol}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "symbol": symbol,
            "trade_date": dates.strftime("%Y-%m-%d"),
            "adj_close": prices,
        }
    ).to_csv(path, index=False)


def _cache_file(fixture: dict[str, object], symbol: str) -> Path:
    return (
        Path(fixture["cache"])
        / "baostock"
        / "stock_daily"
        / "adjusted"
        / f"{symbol}.csv"
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()
