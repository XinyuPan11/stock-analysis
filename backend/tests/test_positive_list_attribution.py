from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.validation.positive_list_attribution import (
    PositiveListAttributionConfig,
    build_positive_list_attribution,
    render_positive_list_attribution_markdown,
    write_positive_list_attribution_outputs,
)


def test_positive_list_overlap_and_high_risk_exclusion_attribution(
    tmp_path: Path,
) -> None:
    outputs = tmp_path / "outputs"
    _write_window(outputs, "2024-01-31", include_member_factors=True)

    report = build_positive_list_attribution(
        PositiveListAttributionConfig(
            outputs_dir=outputs,
            windows=(("2024-01-31", 20),),
            list_ids=("high_confidence_candidates",),
            min_variant_sample=1,
        )
    )

    list_row = report["window_attribution"][0]["lists"][0]
    assert list_row["high_risk_overlap_count"] == 1
    original = _variant(list_row, "original")
    filtered = _variant(list_row, "exclude_high_risk_active")
    assert original["sample_count"] == 3
    assert filtered["sample_count"] == 2
    assert filtered["average_excess_return"] > original["average_excess_return"]
    assert filtered["delta_vs_original"]["average_excess_return"] > 0


def test_member_factor_exclusions_are_available_when_columns_exist(
    tmp_path: Path,
) -> None:
    outputs = tmp_path / "outputs"
    _write_window(outputs, "2024-01-31", include_member_factors=True)
    report = build_positive_list_attribution(
        PositiveListAttributionConfig(
            outputs_dir=outputs,
            windows=(("2024-01-31", 20),),
            list_ids=("high_confidence_candidates",),
            min_variant_sample=1,
        )
    )

    list_row = report["window_attribution"][0]["lists"][0]
    assert _variant(list_row, "exclude_high_volatility")["status"] == "ok"
    assert _variant(list_row, "exclude_drawdown_warning")["status"] == "ok"
    assert _variant(list_row, "exclude_low_risk_score_warning")["status"] == "ok"
    assert report["member_factor_availability"]["volatility"] == "available_all_windows"


def test_missing_member_factor_columns_are_reported_without_invention(
    tmp_path: Path,
) -> None:
    outputs = tmp_path / "outputs"
    _write_window(outputs, "2024-01-31", include_member_factors=False)
    report = build_positive_list_attribution(
        PositiveListAttributionConfig(
            outputs_dir=outputs,
            windows=(("2024-01-31", 20),),
            list_ids=("high_confidence_candidates",),
            min_variant_sample=1,
        )
    )

    list_row = report["window_attribution"][0]["lists"][0]
    assert (
        _variant(list_row, "exclude_high_volatility")["status"]
        == "unavailable_missing_member_factor_columns"
    )
    assert (
        report["member_factor_availability"]["volatility"] == "unavailable"
    )
    assert _variant(list_row, "exclude_high_risk_active")["status"] == "ok"


def test_report_uses_research_only_non_action_language(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    _write_window(outputs, "2024-01-31", include_member_factors=True)
    report = build_positive_list_attribution(
        PositiveListAttributionConfig(
            outputs_dir=outputs,
            windows=(("2024-01-31", 20),),
            list_ids=("high_confidence_candidates",),
            min_variant_sample=1,
        )
    )
    paths = write_positive_list_attribution_outputs(report, outputs)
    markdown = Path(paths["markdown"]).read_text(encoding="utf-8")
    lower = markdown.lower()

    assert markdown.startswith("# Controlled Positive-List Weakness Attribution\n")
    assert "Research-only" in markdown
    assert "buy" not in lower
    assert "sell" not in lower
    assert "short recommendation" not in lower
    assert render_positive_list_attribution_markdown(report) == markdown


def _variant(list_row: dict[str, object], variant_id: str) -> dict[str, object]:
    return next(
        row for row in list_row["variants"] if row["variant_id"] == variant_id
    )


def _write_window(
    outputs: Path,
    as_of_date: str,
    *,
    include_member_factors: bool,
) -> None:
    validation = outputs / "validation"
    lists = outputs / "lists"
    validation.mkdir(parents=True, exist_ok=True)
    lists.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            _prediction("A", -0.20, -0.22, -0.30),
            _prediction("B", 0.08, 0.05, -0.05),
            _prediction("C", 0.06, 0.03, -0.04),
            _prediction("D", 0.02, 0.01, -0.03),
        ]
    ).to_csv(
        validation / f"walk_forward_predictions_{as_of_date}_20d.csv",
        index=False,
    )
    _write_list(
        lists / f"high_confidence_candidates_{as_of_date}.json",
        "high_confidence_candidates",
        ["A", "B", "C"],
    )
    _write_list(
        lists / f"high_risk_active_{as_of_date}.json",
        "high_risk_active",
        ["A"],
    )
    (validation / f"factor_effectiveness_{as_of_date}_20d.json").write_text(
        json.dumps(
            [
                {"factor_name": "total_score", "spread": -0.02},
                {"factor_name": "volatility", "spread": -0.05},
            ]
        ),
        encoding="utf-8",
    )
    if include_member_factors:
        daily = outputs / "daily"
        labels = outputs / "labels"
        daily.mkdir(parents=True, exist_ok=True)
        labels.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            [
                _factor("A", 0.50, -0.40, 100.0, 50.0),
                _factor("B", 0.10, -0.05, 200.0, 100.0),
                _factor("C", 0.08, -0.04, 180.0, 90.0),
                _factor("D", 0.05, -0.03, 150.0, 80.0),
            ]
        ).to_csv(daily / f"factors_{as_of_date}.csv", index=False)
        pd.DataFrame(
            [
                _label("A", 80.0, 5.0, 50.0),
                _label("B", 70.0, 80.0, 60.0),
                _label("C", 65.0, 70.0, 55.0),
                _label("D", 60.0, 60.0, 45.0),
            ]
        ).to_csv(labels / f"stock_labels_{as_of_date}.csv", index=False)


def _prediction(
    symbol: str,
    future_return: float,
    excess: float,
    drawdown: float,
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "future_return": future_return,
        "future_excess_return": excess,
        "benchmark_return": 0.03,
        "outperformed_benchmark": excess > 0,
        "max_drawdown_during_holding": drawdown,
        "data_quality": "ok",
    }


def _factor(
    symbol: str,
    volatility: float,
    drawdown: float,
    amount: float,
    volume: float,
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "volatility_20d": volatility,
        "max_drawdown_20d": drawdown,
        "avg_amount_20d": amount,
        "avg_volume_20d": volume,
    }


def _label(
    symbol: str,
    total_score: float,
    risk_score: float,
    liquidity_score: float,
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "total_score": total_score,
        "risk_score": risk_score,
        "liquidity_score": liquidity_score,
    }


def _write_list(
    path: Path,
    list_id: str,
    symbols: list[str],
) -> None:
    path.write_text(
        json.dumps(
            {
                "list_id": list_id,
                "items": [{"symbol": symbol} for symbol in symbols],
            }
        ),
        encoding="utf-8",
    )
