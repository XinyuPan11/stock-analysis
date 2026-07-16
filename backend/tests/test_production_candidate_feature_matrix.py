from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
SRC = BACKEND_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.research.production_candidate_feature_matrix import (
    IDENTITY_COLUMNS,
    ProductionCandidateFeatureMatrixError,
    build_feature_matrix,
    load_feature_config,
    validate_feature_config,
    write_feature_matrix,
)


FEATURE_CONFIG = (
    REPO_ROOT / "research" / "configs" / "production_candidate_features.v1.json"
)
BASELINE_CONFIG = (
    REPO_ROOT / "research" / "configs" / "production_candidate_baseline.v1.json"
)
CLI = BACKEND_ROOT / "scripts" / "build_production_candidate_feature_matrix.py"
AS_OF = "2024-10-31"


def _cache(tmp_path: Path, *, short_symbol: bool = False) -> Path:
    root = tmp_path / "cache"
    stock_dir = root / "baostock" / "stock_daily" / "adjusted"
    stock_dir.mkdir(parents=True)
    dates = pd.bdate_range(end=AS_OF, periods=140)
    for index, symbol in enumerate(["sh.600001", "sh.600002", "sh.600003"]):
        use_dates = dates[-30:] if short_symbol and index == 2 else dates
        steps = np.arange(len(use_dates), dtype=float)
        adj = 10.0 + index + steps * (0.01 + index * 0.001)
        frame = pd.DataFrame(
            {
                "symbol": symbol,
                "trade_date": use_dates.strftime("%Y-%m-%d"),
                "open": adj * 0.995,
                "high": adj * 1.01,
                "low": adj * 0.99,
                "close": adj * 1.003,
                "volume": 1_000_000 + steps * 10_000 + index * 100,
                "amount": 50_000_000 + steps * 100_000 + index * 1_000,
                "adj_close": adj,
                "source": "synthetic_local_cache",
            }
        )
        frame.to_csv(stock_dir / f"{symbol}.csv", index=False)
    benchmark = pd.DataFrame(
        {
            "symbol": "sz.399300",
            "trade_date": dates.strftime("%Y-%m-%d"),
            "open": 100 + np.arange(len(dates)) * 0.02,
            "high": 101 + np.arange(len(dates)) * 0.02,
            "low": 99 + np.arange(len(dates)) * 0.02,
            "close": 100 + np.arange(len(dates)) * 0.02,
            "volume": 1,
            "amount": 1,
            "adj_close": 100 + np.arange(len(dates)) * 0.02,
            "source": "synthetic_local_cache",
        }
    )
    benchmark.to_csv(stock_dir / "sz.399300.csv", index=False)
    return root


def _build(tmp_path: Path, *, short_symbol: bool = False):
    return build_feature_matrix(
        as_of_date=AS_OF,
        cache_dir=_cache(tmp_path, short_symbol=short_symbol),
        feature_config_path=FEATURE_CONFIG,
        baseline_config_path=BASELINE_CONFIG,
        baseline_snapshot_dir=None,
    )


def test_valid_local_cache_only_build_and_exact_identity(tmp_path: Path) -> None:
    result = _build(tmp_path)

    assert len(result.frame) == 3
    assert not result.frame.duplicated(["symbol", "as_of_date"]).any()
    assert result.frame["symbol"].tolist() == sorted(result.frame["symbol"])
    assert set(result.frame["as_of_date"]) == {AS_OF}
    assert result.report["provider_access"] is False
    assert result.report["labels_joined"] is False
    assert result.report["results_are_effectiveness_evidence"] is False


def test_deterministic_column_order_and_registered_output(tmp_path: Path) -> None:
    config = load_feature_config(FEATURE_CONFIG)
    result = _build(tmp_path)

    assert result.frame.columns.tolist() == [
        *IDENTITY_COLUMNS,
        *config["output_feature_columns"],
    ]


def test_adjusted_price_is_used_without_close_fallback(tmp_path: Path) -> None:
    cache = _cache(tmp_path)
    path = (
        cache
        / "baostock"
        / "stock_daily"
        / "adjusted"
        / "sh.600001.csv"
    )
    frame = pd.read_csv(path)
    frame["close"] = frame["adj_close"] * 100
    frame.to_csv(path, index=False)

    result = build_feature_matrix(
        as_of_date=AS_OF,
        cache_dir=cache,
        feature_config_path=FEATURE_CONFIG,
        baseline_config_path=BASELINE_CONFIG,
    )

    row = result.frame.set_index("symbol").loc["sh.600001"]
    assert row["return_5d"] < 0.1


def test_missing_adjusted_price_column_fails(tmp_path: Path) -> None:
    cache = _cache(tmp_path)
    path = (
        cache
        / "baostock"
        / "stock_daily"
        / "adjusted"
        / "sh.600001.csv"
    )
    frame = pd.read_csv(path).drop(columns=["adj_close"])
    frame.to_csv(path, index=False)

    with pytest.raises(
        ProductionCandidateFeatureMatrixError,
        match="schema is incomplete",
    ):
        build_feature_matrix(
            as_of_date=AS_OF,
            cache_dir=cache,
            feature_config_path=FEATURE_CONFIG,
            baseline_config_path=BASELINE_CONFIG,
        )


def test_latest_input_date_never_exceeds_as_of(tmp_path: Path) -> None:
    result = _build(tmp_path)

    assert (pd.to_datetime(result.frame["latest_input_date"]) <= pd.Timestamp(AS_OF)).all()


def test_insufficient_lookback_is_preserved_without_symbol_drop(
    tmp_path: Path,
) -> None:
    result = _build(tmp_path, short_symbol=True)
    row = result.frame.set_index("symbol").loc["sh.600003"]

    assert len(result.frame) == 3
    assert row["row_status"] == "partial"
    assert row["missing_reason"] == "insufficient_maximum_121_bar_lookback"
    assert pd.isna(row["momentum_120d"])


@pytest.mark.parametrize(
    "feature_id",
    [
        "future_return_20d",
        "winner",
        "loser",
        "right_tail",
        "severe_drawdown",
    ],
)
def test_future_and_label_feature_ids_are_rejected(feature_id: str) -> None:
    config = load_feature_config(FEATURE_CONFIG)
    changed = copy.deepcopy(config)
    changed["feature_definitions"][0]["feature_id"] = feature_id
    changed["output_feature_columns"][0] = feature_id

    with pytest.raises(
        ProductionCandidateFeatureMatrixError,
        match="Outcome label|future, outcome, label",
    ):
        validate_feature_config(changed)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("labels_joined", True),
        ("provider_access", True),
        ("production_change", True),
    ],
)
def test_unsafe_feature_config_flags_fail(field: str, value: bool) -> None:
    config = load_feature_config(FEATURE_CONFIG)
    changed = copy.deepcopy(config)
    changed[field] = value

    with pytest.raises(
        ProductionCandidateFeatureMatrixError,
        match="identity or safety",
    ):
        validate_feature_config(changed)


def test_duplicate_feature_id_fails() -> None:
    config = load_feature_config(FEATURE_CONFIG)
    changed = copy.deepcopy(config)
    changed["feature_definitions"].append(
        copy.deepcopy(changed["feature_definitions"][0])
    )
    changed["output_feature_columns"].append(
        changed["output_feature_columns"][0]
    )

    with pytest.raises(
        ProductionCandidateFeatureMatrixError,
        match="Duplicate feature IDs",
    ):
        validate_feature_config(changed)


def test_duplicate_cache_row_fails(tmp_path: Path) -> None:
    cache = _cache(tmp_path)
    path = (
        cache
        / "baostock"
        / "stock_daily"
        / "adjusted"
        / "sh.600001.csv"
    )
    frame = pd.read_csv(path)
    pd.concat([frame, frame.tail(1)], ignore_index=True).to_csv(path, index=False)

    with pytest.raises(
        ProductionCandidateFeatureMatrixError,
        match="Duplicate cache",
    ):
        build_feature_matrix(
            as_of_date=AS_OF,
            cache_dir=cache,
            feature_config_path=FEATURE_CONFIG,
            baseline_config_path=BASELINE_CONFIG,
        )


@pytest.mark.parametrize("as_of", ["2026-09-30", "2026-12-31"])
def test_u3_dates_are_rejected(tmp_path: Path, as_of: str) -> None:
    with pytest.raises(
        ProductionCandidateFeatureMatrixError,
        match="U3 dates are protected",
    ):
        build_feature_matrix(
            as_of_date=as_of,
            cache_dir=_cache(tmp_path),
            feature_config_path=FEATURE_CONFIG,
            baseline_config_path=BASELINE_CONFIG,
        )


def test_as_of_later_than_cache_coverage_fails(tmp_path: Path) -> None:
    with pytest.raises(
        ProductionCandidateFeatureMatrixError,
        match="later than local benchmark",
    ):
        build_feature_matrix(
            as_of_date="2026-01-30",
            cache_dir=_cache(tmp_path),
            feature_config_path=FEATURE_CONFIG,
            baseline_config_path=BASELINE_CONFIG,
        )


def test_trend_volume_drawdown_and_mean_reversion_formulas(
    tmp_path: Path,
) -> None:
    row = _build(tmp_path).frame.set_index("symbol").loc["sh.600001"]

    assert row["return_5d"] == pytest.approx(
        (10 + 139 * 0.01) / (10 + 134 * 0.01) - 1
    )
    assert row["relative_volume_5_20"] > 1
    assert row["drawdown_60"] == pytest.approx(0)
    assert row["distance_from_low_60"] > 0
    assert np.isfinite(row["mean_reversion_opportunity_score"])
    assert np.isfinite(row["low_position_revaluation_score"])


def test_zero_variance_handling_is_finite_or_explicit_null(
    tmp_path: Path,
) -> None:
    cache = _cache(tmp_path)
    path = (
        cache
        / "baostock"
        / "stock_daily"
        / "adjusted"
        / "sh.600001.csv"
    )
    frame = pd.read_csv(path)
    frame["adj_close"] = 10.0
    frame.to_csv(path, index=False)

    result = build_feature_matrix(
        as_of_date=AS_OF,
        cache_dir=cache,
        feature_config_path=FEATURE_CONFIG,
        baseline_config_path=BASELINE_CONFIG,
    )
    row = result.frame.set_index("symbol").loc["sh.600001"]

    assert row["return_zscore_20"] == 0
    assert not np.isinf(pd.to_numeric(result.frame.select_dtypes(include="number").stack(), errors="coerce")).any()


def test_dry_run_cli_writes_nothing(tmp_path: Path) -> None:
    cache = _cache(tmp_path)
    outputs = tmp_path / "inputs"
    completed = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--as-of-date",
            AS_OF,
            "--cache-dir",
            str(cache),
            "--feature-config",
            str(FEATURE_CONFIG),
            "--baseline-config",
            str(BASELINE_CONFIG),
            "--outputs-dir",
            str(outputs),
            "--dry-run",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout
    assert not outputs.exists()


def test_write_output_writes_only_research_input_csv_json(
    tmp_path: Path,
) -> None:
    result = _build(tmp_path)
    outputs = tmp_path / "research_inputs"
    paths = write_feature_matrix(result, outputs_dir=outputs)

    assert sorted(path.name for path in outputs.iterdir()) == [
        f"production_candidate_features_{AS_OF}.csv",
        f"production_candidate_features_{AS_OF}.json",
    ]
    payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert payload["metadata"]["labels_joined"] is False
    assert payload["metadata"]["production_change"] is False
