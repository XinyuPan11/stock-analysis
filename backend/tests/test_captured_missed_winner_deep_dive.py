from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.validation.captured_missed_winner_deep_dive import (
    CapturedMissedDeepDiveConfig,
    build_captured_missed_winner_deep_dive,
    render_captured_missed_winner_deep_dive_markdown,
    write_captured_missed_winner_deep_dive_outputs,
)


def test_captured_and_missed_winner_groups_reuse_phase215_settings(
    tmp_path: Path,
) -> None:
    snapshot, attribution, cases = _fixture(tmp_path)
    report = build_captured_missed_winner_deep_dive(
        CapturedMissedDeepDiveConfig(
            snapshot_file=snapshot,
            attribution_file=attribution,
            case_study_file=cases,
        )
    )

    summary = report["summary"]
    assert summary["tail_fraction_reused"] == 0.25
    assert summary["min_group_size_reused"] == 1
    assert summary["winner_tail_count"] == 3
    assert summary["captured_winner_count"] == 1
    assert summary["missed_winner_count"] == 2
    comparison = report["comparisons"]["captured_vs_missed_winners"]
    assert comparison["total_score"]["left_median"] == 90.0
    assert comparison["total_score"]["right_median"] == 75.0


def test_positive_list_winner_loser_and_list_contamination_summaries(
    tmp_path: Path,
) -> None:
    snapshot, attribution, cases = _fixture(tmp_path)
    report = build_captured_missed_winner_deep_dive(
        CapturedMissedDeepDiveConfig(
            snapshot_file=snapshot,
            attribution_file=attribution,
            case_study_file=cases,
        )
    )

    assert report["summary"]["positive_list_loser_count"] == 1
    lists = {
        row["list_id"]: row
        for row in report["list_specific_summaries"]
    }
    assert lists["high_confidence_candidates"]["winner_tail_count"] == 1
    assert lists["high_confidence_candidates"]["loser_tail_count"] == 0
    assert lists["breakout_watch"]["winner_tail_count"] == 0
    assert lists["breakout_watch"]["loser_tail_count"] == 1
    assert lists["breakout_watch"]["tail_contamination_rate"] == 1.0
    comparison = report["comparisons"][
        "positive_list_winners_vs_losers"
    ]
    assert (
        comparison["high_position_crowding_proxy"]["median_delta"] < 0
    )


def test_missing_feature_flags_and_case_study_are_explicit(
    tmp_path: Path,
) -> None:
    snapshot, attribution, cases = _fixture(tmp_path)
    report = build_captured_missed_winner_deep_dive(
        CapturedMissedDeepDiveConfig(
            snapshot_file=snapshot,
            attribution_file=attribution,
            case_study_file=cases,
        )
    )

    flags = report["missing_feature_flag_summary"]["missed_winners"]
    assert flags["rows_with_flags"] == 1
    assert flags["top_flags"][0] == {
        "flag": "insufficient_history:pre_60d_return",
        "count": 1,
    }
    case_summary = report["case_study_alignment"]
    assert case_summary["available"] is True
    assert case_summary["matched_case_count"] == 3
    assert case_summary["winner_tail_match_count"] == 2
    assert case_summary["captured_winner_archetypes"][0] == {
        "archetype": "stable_trend",
        "count": 1,
    }


def test_missing_optional_case_study_is_safe(tmp_path: Path) -> None:
    snapshot, attribution, _ = _fixture(tmp_path)
    report = build_captured_missed_winner_deep_dive(
        CapturedMissedDeepDiveConfig(
            snapshot_file=snapshot,
            attribution_file=attribution,
            case_study_file=tmp_path / "missing.csv",
        )
    )

    case_summary = report["case_study_alignment"]
    assert case_summary["available"] is False
    assert case_summary["reason"] == "file_not_found"


def test_report_guardrails_are_non_production(tmp_path: Path) -> None:
    snapshot, attribution, cases = _fixture(tmp_path)
    outputs = tmp_path / "outputs"
    report = build_captured_missed_winner_deep_dive(
        CapturedMissedDeepDiveConfig(
            snapshot_file=snapshot,
            attribution_file=attribution,
            case_study_file=cases,
        )
    )
    paths = write_captured_missed_winner_deep_dive_outputs(
        report,
        outputs,
    )
    markdown = Path(paths["markdown"]).read_text(encoding="utf-8")
    payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    lower = markdown.lower()

    assert "answer-key" in lower
    assert "not blind validation" in lower
    assert "not evidence of production improvement" in lower
    assert "unseen-window testing" in lower
    assert payload["summary"]["thresholds_tuned"] is False
    assert payload["summary"]["production_lists_created"] is False
    assert "buy" not in lower
    assert "sell" not in lower
    assert render_captured_missed_winner_deep_dive_markdown(report) == markdown


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    snapshot_path = tmp_path / "snapshot.csv"
    attribution_path = tmp_path / "attribution.json"
    case_path = tmp_path / "cases.csv"
    returns = [0.50, 0.40, 0.30, 0.10, -0.10, -0.30, -0.40, -0.50]
    excess = [0.10, 0.60, 0.50, 0.05, -0.05, -0.50, -0.60, -0.10]
    rows = []
    for index, symbol in enumerate("ABCDEFGH"):
        captured_lists = ""
        if symbol == "A":
            captured_lists = "high_confidence_candidates"
        elif symbol == "H":
            captured_lists = "breakout_watch"
        rows.append(
            {
                "as_of_date": "2024-01-31",
                "horizon_days": 20,
                "symbol": symbol,
                "data_quality": "ok",
                "captured_positive_lists": captured_lists,
                "captured_risk_lists": (
                    "high_risk_active" if symbol == "G" else ""
                ),
                "is_high_confidence": symbol == "A",
                "is_trend_leader": False,
                "is_long_term_stable": False,
                "is_breakout_watch": symbol == "H",
                "is_accumulation_watch": False,
                "is_rebound_watch": False,
                "is_high_risk_active": symbol == "G",
                "future_return": returns[index],
                "future_excess_return": excess[index],
                "total_score": 90 - index * 10,
                "momentum_score": 20 - index,
                "trend_score": 18 - index,
                "relative_strength_score": 17 - index,
                "risk_score": 16 - index,
                "liquidity_score": 15 - index,
                "pre_20d_return": 0.20 - index * 0.04,
                "pre_60d_return": 0.10 - index * 0.03,
                "volatility_20d": 0.02 + index * 0.01,
                "technical_volatility_20d": 0.02 + index * 0.01,
                "drawdown_60d": -0.05 - index * 0.02,
                "amount_change_20d": 0.30 - index * 0.03,
                "volume_change_20d": 0.25 - index * 0.02,
                "distance_to_60d_high": -0.10 + index * 0.01,
                "distance_to_60d_low": 0.10 + index * 0.02,
                "recent_acceleration_proxy": 0.08 - index * 0.01,
                "high_position_crowding_proxy": index * 0.02,
                "missing_feature_flags": (
                    "insufficient_history:pre_60d_return"
                    if symbol == "C"
                    else ""
                ),
            }
        )
    pd.DataFrame(rows).to_csv(snapshot_path, index=False)
    attribution_path.write_text(
        json.dumps(
            {
                "summary": {
                    "tail_fraction": 0.25,
                    "min_group_size": 1,
                }
            }
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "symbol": "A",
                "as_of_date": "2024-01-31",
                "horizon_days": 20,
                "winner_or_loser": "winner",
                "captured_as_positive_candidate": "True",
                "archetype": "stable_trend",
            },
            {
                "symbol": "B",
                "as_of_date": "2024-01-31",
                "horizon_days": 20,
                "winner_or_loser": "winner",
                "captured_as_positive_candidate": "False",
                "archetype": "theme_catalyst;right_tail",
            },
            {
                "symbol": "H",
                "as_of_date": "2024-01-31",
                "horizon_days": 20,
                "winner_or_loser": "loser",
                "captured_as_positive_candidate": "True",
                "archetype": "false_breakout",
            },
        ]
    ).to_csv(case_path, index=False, encoding="utf-8-sig")
    return snapshot_path, attribution_path, case_path
