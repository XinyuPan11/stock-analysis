from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.validation.risk_bucket_attribution import (
    RiskBucketAttributionConfig,
    build_risk_bucket_attribution,
    render_risk_bucket_attribution_markdown,
    write_risk_bucket_attribution_outputs,
)


def test_disjoint_cohorts_are_constructed_from_membership(
    tmp_path: Path,
) -> None:
    outputs = tmp_path / "outputs"
    _write_window(outputs, "2024-01-31", high_excess=-0.10)

    report = build_risk_bucket_attribution(
        RiskBucketAttributionConfig(
            outputs_dir=outputs,
            windows=(("2024-01-31", 20),),
        )
    )

    window = report["window_attribution"][0]
    assert window["disjoint_check_passed"] is True
    assert window["disjoint_overlap_count"] == 0
    assert window["cohorts"]["high_risk_active"]["sample_count"] == 2
    assert window["cohorts"]["non_high_risk_disjoint"]["sample_count"] == 2
    assert window["matched_high_risk_count"] == 2


def test_missing_membership_reports_insufficient_data(
    tmp_path: Path,
) -> None:
    outputs = tmp_path / "outputs"
    _write_predictions(outputs, "2024-01-31", high_excess=-0.10)

    report = build_risk_bucket_attribution(
        RiskBucketAttributionConfig(
            outputs_dir=outputs,
            windows=(("2024-01-31", 20),),
        )
    )

    assert report["summary"]["status"] == "insufficient_data"
    assert report["summary"]["classification"] == "insufficient_sample"
    assert report["summary"]["disjoint_attribution_available"] is False
    assert report["excluded_windows"][0]["status"] == "missing_membership"


def test_stable_negative_bucket_classification(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    windows = (
        ("2024-01-31", 20),
        ("2024-04-30", 20),
        ("2024-07-31", 20),
        ("2024-10-31", 20),
    )
    for index, (date, _) in enumerate(windows):
        _write_window(
            outputs,
            date,
            high_excess=0.01 if index == 1 else -0.10,
        )

    report = build_risk_bucket_attribution(
        RiskBucketAttributionConfig(
            outputs_dir=outputs,
            windows=windows,
            min_bucket_sample=2,
        )
    )

    high_risk = report["cohort_summary"]["high_risk_active"]
    assert report["summary"]["classification"] == "stable_negative_risk_bucket"
    assert high_risk["negative_excess_window_count"] == 3
    assert high_risk["excess_sign_consistency"] == "mostly_negative"


def test_output_uses_research_only_non_action_language(
    tmp_path: Path,
) -> None:
    outputs = tmp_path / "outputs"
    _write_window(outputs, "2024-01-31", high_excess=-0.10)
    report = build_risk_bucket_attribution(
        RiskBucketAttributionConfig(
            outputs_dir=outputs,
            windows=(("2024-01-31", 20),),
        )
    )
    paths = write_risk_bucket_attribution_outputs(report, outputs)
    markdown = Path(paths["markdown"]).read_text(encoding="utf-8")
    lower = markdown.lower()

    assert markdown.startswith("# Controlled Disjoint Risk-Bucket Attribution\n")
    assert "Research-only" in markdown
    assert "buy" not in lower
    assert "sell" not in lower
    assert "short recommendation" not in lower
    assert render_risk_bucket_attribution_markdown(report) == markdown


def _write_window(
    outputs: Path,
    as_of_date: str,
    *,
    high_excess: float,
) -> None:
    _write_predictions(outputs, as_of_date, high_excess=high_excess)
    lists_dir = outputs / "lists"
    lists_dir.mkdir(parents=True, exist_ok=True)
    (lists_dir / f"high_risk_active_{as_of_date}.json").write_text(
        json.dumps(
            {
                "list_id": "high_risk_active",
                "items": [{"symbol": "A"}, {"symbol": "B"}],
            }
        ),
        encoding="utf-8",
    )
    (lists_dir / f"high_confidence_candidates_{as_of_date}.json").write_text(
        json.dumps(
            {
                "list_id": "high_confidence_candidates",
                "items": [{"symbol": "B"}, {"symbol": "C"}],
            }
        ),
        encoding="utf-8",
    )
    validation = outputs / "validation"
    (validation / f"list_performance_{as_of_date}_20d.json").write_text(
        json.dumps(
            [
                {"list_id": "high_risk_active"},
                {"list_id": "high_confidence_candidates"},
            ]
        ),
        encoding="utf-8",
    )


def _write_predictions(
    outputs: Path,
    as_of_date: str,
    *,
    high_excess: float,
) -> None:
    validation = outputs / "validation"
    validation.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            _row("A", high_excess - 0.01, high_excess, -0.20),
            _row("B", high_excess + 0.01, high_excess, -0.15),
            _row("C", 0.08, 0.05, -0.04),
            _row("D", 0.04, 0.02, -0.03),
        ]
    ).to_csv(
        validation / f"walk_forward_predictions_{as_of_date}_20d.csv",
        index=False,
    )


def _row(
    symbol: str,
    future_return: float,
    excess: float,
    drawdown: float,
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "future_return": future_return,
        "future_excess_return": excess,
        "outperformed_benchmark": excess > 0,
        "max_drawdown_during_holding": drawdown,
        "data_quality": "ok",
    }
