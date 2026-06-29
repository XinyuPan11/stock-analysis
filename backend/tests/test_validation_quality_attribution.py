from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.validation.validation_quality_attribution import (
    ValidationQualityAttributionConfig,
    build_validation_quality_attribution,
    render_validation_quality_attribution_markdown,
    write_validation_quality_attribution_outputs,
    _sign_consistency,
)


def test_attribution_summarizes_list_factor_and_risk_stability(
    tmp_path: Path,
) -> None:
    outputs = tmp_path / "outputs"
    _write_window(outputs, "2024-01-31", 20, high_risk_excess=-0.10, score_spread=0.04)
    _write_window(outputs, "2024-04-30", 20, high_risk_excess=-0.06, score_spread=-0.02)

    report = build_validation_quality_attribution(
        ValidationQualityAttributionConfig(
            outputs_dir=outputs,
            windows=(("2024-01-31", 20), ("2024-04-30", 20)),
        )
    )

    assert report["summary"]["provider_access"] is False
    assert report["summary"]["labels_recomputed"] is False
    high_risk = next(
        row
        for row in report["list_attribution"]
        if row["list_id"] == "high_risk_active"
    )
    assert high_risk["excess_sign_consistency"] == "consistently_negative"
    assert high_risk["valid_window_count"] == 2
    total_score = next(
        row
        for row in report["factor_attribution"]
        if row["factor_name"] == "total_score"
    )
    assert total_score["spread_sign_consistency"] == "mixed_or_neutral"
    assert total_score["positive_spread_window_count"] == 1
    assert report["risk_profile_attribution"]["high_risk_active"]["list_id"] == "high_risk_active"


def test_attribution_distinguishes_mostly_negative_from_consistently_negative() -> None:
    assert _sign_consistency([-0.14, 0.02, -0.06, -0.03]) == "mostly_negative"
    assert _sign_consistency([-0.14, -0.02, -0.06, -0.03]) == "consistently_negative"
    assert _sign_consistency([0.04, -0.02, 0.03, -0.01]) == "mixed_or_neutral"


def test_attribution_reports_prediction_quality_and_missing_windows(
    tmp_path: Path,
) -> None:
    outputs = tmp_path / "outputs"
    _write_window(outputs, "2024-01-31", 20, high_risk_excess=-0.10, score_spread=0.04)

    report = build_validation_quality_attribution(
        ValidationQualityAttributionConfig(
            outputs_dir=outputs,
            windows=(("2024-01-31", 20), ("2024-07-31", 20)),
        )
    )

    window = report["included_windows"][0]
    assert window["prediction_count"] == 3
    assert window["valid_prediction_count"] == 2
    assert window["data_quality_counts"] == {"missing_price": 1, "ok": 2}
    assert report["summary"]["excluded_window_count"] == 1
    assert report["excluded_windows"][0]["status"] == "missing_required_outputs"


def test_attribution_writes_research_only_json_and_markdown(
    tmp_path: Path,
) -> None:
    outputs = tmp_path / "outputs"
    _write_window(outputs, "2024-01-31", 20, high_risk_excess=-0.10, score_spread=0.04)
    report = build_validation_quality_attribution(
        ValidationQualityAttributionConfig(
            outputs_dir=outputs,
            windows=(("2024-01-31", 20),),
        )
    )

    paths = write_validation_quality_attribution_outputs(report, outputs)

    assert Path(paths["json"]).exists()
    markdown = Path(paths["markdown"]).read_text(encoding="utf-8")
    assert markdown.startswith("# Controlled Validation Quality Attribution\n")
    assert "Research-only" in markdown
    assert "production scoring" in markdown
    assert "industry_sector_market_cap" in markdown
    assert render_validation_quality_attribution_markdown(report) == markdown


def _write_window(
    outputs: Path,
    as_of_date: str,
    horizon_days: int,
    *,
    high_risk_excess: float,
    score_spread: float,
) -> None:
    validation = outputs / "validation"
    validation.mkdir(parents=True, exist_ok=True)
    suffix = f"{as_of_date}_{horizon_days}d"
    pd.DataFrame(
        [
            {
                "symbol": "sh.600000",
                "future_return": 0.10,
                "future_excess_return": 0.05,
                "outperformed_benchmark": True,
                "max_drawdown_during_holding": -0.03,
                "data_quality": "ok",
            },
            {
                "symbol": "sh.600001",
                "future_return": -0.05,
                "future_excess_return": -0.08,
                "outperformed_benchmark": False,
                "max_drawdown_during_holding": -0.12,
                "data_quality": "ok",
            },
            {
                "symbol": "sh.600002",
                "future_return": None,
                "future_excess_return": None,
                "outperformed_benchmark": None,
                "max_drawdown_during_holding": None,
                "data_quality": "missing_price",
            },
        ]
    ).to_csv(
        validation / f"walk_forward_predictions_{suffix}.csv", index=False
    )
    (validation / f"list_performance_{suffix}.json").write_text(
        json.dumps(
            [
                {
                    "list_id": "high_confidence_candidates",
                    "valid_future_count": 20,
                    "average_future_return": 0.04,
                    "average_excess_return": 0.02,
                    "win_rate": 0.60,
                    "outperform_rate": 0.55,
                    "max_drawdown_average": -0.08,
                },
                {
                    "list_id": "high_risk_active",
                    "valid_future_count": 8,
                    "average_future_return": high_risk_excess + 0.01,
                    "average_excess_return": high_risk_excess,
                    "win_rate": 0.25,
                    "outperform_rate": 0.20,
                    "max_drawdown_average": -0.20,
                },
            ]
        ),
        encoding="utf-8",
    )
    (validation / f"factor_effectiveness_{suffix}.json").write_text(
        json.dumps(
            [
                {
                    "factor_name": "total_score",
                    "correlation_with_future_return": score_spread / 2,
                    "top_quantile_average_return": 0.03,
                    "bottom_quantile_average_return": 0.03 - score_spread,
                    "spread": score_spread,
                    "top_quantile_outperform_rate": 0.55,
                },
                {
                    "factor_name": "volatility",
                    "correlation_with_future_return": -0.10,
                    "top_quantile_average_return": -0.02,
                    "bottom_quantile_average_return": 0.03,
                    "spread": -0.05,
                    "top_quantile_outperform_rate": 0.30,
                },
            ]
        ),
        encoding="utf-8",
    )
