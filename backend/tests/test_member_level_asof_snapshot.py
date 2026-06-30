from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.validation.member_level_asof_snapshot import (
    FACTOR_FIELDS,
    FUTURE_LABEL_FIELDS,
    LIST_FIELD_MAP,
    SCORE_FIELDS,
    TECHNICAL_FEATURE_FIELDS,
    MemberLevelSnapshotConfig,
    build_member_level_asof_snapshot,
    render_member_level_asof_snapshot_markdown,
    write_member_level_asof_snapshot_outputs,
)


AS_OF_DATE = "2024-03-10"


def test_asof_technical_features_exclude_future_cache_rows(
    tmp_path: Path,
) -> None:
    outputs, cache = _fixture(tmp_path, include_second_cache=False)
    result = build_member_level_asof_snapshot(
        MemberLevelSnapshotConfig(
            outputs_dir=outputs,
            cache_dir=cache,
            windows=((AS_OF_DATE, 20),),
        )
    )

    row = _row(result.frame, "A")
    assert row["as_of_date"] == AS_OF_DATE
    assert row["horizon_days"] == 20
    assert row["latest_input_date"] == AS_OF_DATE
    assert row["max_raw_cache_date"] == "2024-03-12"
    assert row["future_rows_excluded_count"] == 2
    assert bool(row["leakage_guard_applied"]) is True
    assert row["pre_5d_return"] == pytest.approx(70.0 / 65.0 - 1.0)
    assert row["pre_20d_return"] == pytest.approx(70.0 / 50.0 - 1.0)
    assert row["pre_60d_return"] == pytest.approx(70.0 / 10.0 - 1.0)
    assert row["pre_5d_return"] < 1.0


def test_list_membership_and_existing_fields_are_merged(
    tmp_path: Path,
) -> None:
    outputs, cache = _fixture(tmp_path, include_second_cache=True)
    result = build_member_level_asof_snapshot(
        MemberLevelSnapshotConfig(
            outputs_dir=outputs,
            cache_dir=cache,
            windows=((AS_OF_DATE, 20),),
        )
    )

    first = _row(result.frame, "A")
    second = _row(result.frame, "B")
    assert first["captured_positive_lists"] == (
        "high_confidence_candidates;trend_leaders"
    )
    assert bool(first["is_high_confidence"]) is True
    assert bool(first["is_trend_leader"]) is True
    assert bool(first["is_high_risk_active"]) is False
    assert second["captured_positive_lists"] == "accumulation_watch"
    assert second["captured_risk_lists"] == "high_risk_active"
    assert bool(second["is_high_risk_active"]) is True
    assert first["total_score"] == pytest.approx(80.0)
    assert first["momentum_20d"] == pytest.approx(0.20)
    assert first["future_return"] == pytest.approx(0.15)


def test_missing_cache_features_are_explicit_not_invented(
    tmp_path: Path,
) -> None:
    outputs, cache = _fixture(tmp_path, include_second_cache=False)
    result = build_member_level_asof_snapshot(
        MemberLevelSnapshotConfig(
            outputs_dir=outputs,
            cache_dir=cache,
            windows=((AS_OF_DATE, 20),),
        )
    )

    row = _row(result.frame, "B")
    assert pd.isna(row["pre_5d_return"])
    assert pd.isna(row["latest_input_date"])
    assert "missing_daily_cache" in row["missing_feature_flags"]
    assert result.report["summary"]["status"] == "partial"
    assert (
        result.report["window_summary"][0]["missing_daily_cache_count"] == 1
    )


def test_snapshot_schema_and_report_preserve_research_guardrails(
    tmp_path: Path,
) -> None:
    outputs, cache = _fixture(tmp_path, include_second_cache=True)
    result = build_member_level_asof_snapshot(
        MemberLevelSnapshotConfig(
            outputs_dir=outputs,
            cache_dir=cache,
            windows=((AS_OF_DATE, 20),),
        )
    )
    paths = write_member_level_asof_snapshot_outputs(result, outputs)
    markdown = Path(paths["markdown"]).read_text(encoding="utf-8")
    payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    lower = markdown.lower()

    assert set(TECHNICAL_FEATURE_FIELDS).issubset(result.frame.columns)
    assert set(FACTOR_FIELDS).issubset(result.frame.columns)
    assert set(SCORE_FIELDS).issubset(result.frame.columns)
    assert set(FUTURE_LABEL_FIELDS).issubset(result.frame.columns)
    assert set(LIST_FIELD_MAP.values()).issubset(result.frame.columns)
    assert payload["summary"]["provider_access"] is False
    assert payload["summary"]["labels_recomputed"] is False
    assert payload["summary"]["production_scoring_changed"] is False
    assert "trade_date <= as_of_date" in markdown
    assert "unseen-window validation" in markdown
    assert "not evidence of production improvement" in lower
    assert "buy" not in lower
    assert "sell" not in lower
    assert render_member_level_asof_snapshot_markdown(result.report) == markdown


def _fixture(
    tmp_path: Path,
    *,
    include_second_cache: bool,
) -> tuple[Path, Path]:
    outputs = tmp_path / "outputs"
    cache = tmp_path / "cache"
    validation = outputs / "validation"
    daily = outputs / "daily"
    labels = outputs / "labels"
    lists = outputs / "lists"
    adjusted = cache / "baostock" / "stock_daily" / "adjusted"
    for path in (validation, daily, labels, lists, adjusted):
        path.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            _prediction("A", 0.15, 0.10),
            _prediction("B", -0.10, -0.15),
        ]
    ).to_csv(
        validation / f"walk_forward_predictions_{AS_OF_DATE}_20d.csv",
        index=False,
    )
    pd.DataFrame(
        [
            _factor("A", 0.20, 0.05),
            _factor("B", -0.10, 0.08),
        ]
    ).to_csv(daily / f"factors_{AS_OF_DATE}.csv", index=False)
    pd.DataFrame(
        [
            _score("A", 80.0, 70.0),
            _score("B", 30.0, 10.0),
        ]
    ).to_csv(labels / f"stock_labels_{AS_OF_DATE}.csv", index=False)

    memberships = {
        "high_confidence_candidates": ["A"],
        "trend_leaders": ["A"],
        "long_term_stable": [],
        "breakout_watch": [],
        "accumulation_watch": ["B"],
        "rebound_watch": [],
        "high_risk_active": ["B"],
    }
    for list_id, symbols in memberships.items():
        (lists / f"{list_id}_{AS_OF_DATE}.json").write_text(
            json.dumps(
                {
                    "list_id": list_id,
                    "items": [
                        {"symbol": symbol} for symbol in symbols
                    ],
                }
            ),
            encoding="utf-8",
        )

    _write_cache(adjusted / "A.csv", multiplier=1.0)
    if include_second_cache:
        _write_cache(adjusted / "B.csv", multiplier=2.0)
    return outputs, cache


def _write_cache(path: Path, *, multiplier: float) -> None:
    dates = pd.date_range("2024-01-01", periods=72, freq="D")
    prices = [float(index + 1) * multiplier for index in range(70)]
    prices.extend([10000.0, 20000.0])
    pd.DataFrame(
        {
            "symbol": path.stem,
            "trade_date": dates.strftime("%Y-%m-%d"),
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "adj_close": prices,
            "volume": [1000.0 + index for index in range(72)],
            "amount": [10000.0 + index * 10 for index in range(72)],
            "source": "fixture",
        }
    ).to_csv(path, index=False)


def _prediction(
    symbol: str,
    future_return: float,
    excess: float,
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "as_of_date": AS_OF_DATE,
        "horizon_days": 20,
        "future_return": future_return,
        "benchmark_return": 0.05,
        "future_excess_return": excess,
        "outperformed_benchmark": excess > 0,
        "future_top_quantile": symbol == "A",
        "max_drawdown_during_holding": -0.10,
        "benchmark_data_quality": "ok",
        "data_quality": "ok",
    }


def _factor(
    symbol: str,
    momentum: float,
    volatility: float,
) -> dict[str, object]:
    row = {field: 1.0 for field in FACTOR_FIELDS}
    row.update(
        {
            "symbol": symbol,
            "momentum_20d": momentum,
            "volatility_20d": volatility,
        }
    )
    return row


def _score(
    symbol: str,
    total_score: float,
    risk_score: float,
) -> dict[str, object]:
    row = {field: 1.0 for field in SCORE_FIELDS}
    row.update(
        {
            "symbol": symbol,
            "total_score": total_score,
            "risk_score": risk_score,
            "primary_type": "fixture",
            "research_status": "fixture",
            "risk_level": "fixture",
        }
    )
    return row


def _row(frame: pd.DataFrame, symbol: str) -> pd.Series:
    return frame.loc[frame["symbol"] == symbol].iloc[0]
