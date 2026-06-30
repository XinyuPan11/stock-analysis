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

from stock_analysis.validation.winner_loser_feature_attribution import (
    WinnerLoserAttributionConfig,
    build_winner_loser_feature_attribution,
    render_winner_loser_feature_attribution_markdown,
    write_winner_loser_feature_attribution_outputs,
)


def test_tail_groups_are_constructed_within_each_window(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot(tmp_path)
    report = build_winner_loser_feature_attribution(
        WinnerLoserAttributionConfig(
            snapshot_file=snapshot,
            tail_fraction=0.25,
            min_group_size=1,
        )
    )

    counts = _group_counts(report)
    assert report["summary"]["window_count"] == 2
    assert counts["top_future_return_winners"] == 4
    assert counts["top_future_excess_return_winners"] == 4
    assert counts["winner_union"] == 6
    assert counts["bottom_future_return_losers"] == 4
    assert counts["bottom_future_excess_return_losers"] == 4
    assert counts["loser_union"] == 6
    assert all(
        row["tail_count_per_label"] == 2
        for row in report["group_window_counts"]
    )


def test_captured_and_missed_winner_groups_use_existing_membership(
    tmp_path: Path,
) -> None:
    report = build_winner_loser_feature_attribution(
        WinnerLoserAttributionConfig(
            snapshot_file=_snapshot(tmp_path),
            tail_fraction=0.25,
            min_group_size=1,
        )
    )

    counts = _group_counts(report)
    assert counts["winner_union_captured_positive"] == 2
    assert counts["winner_union_missed_positive"] == 4
    assert counts["loser_union_captured_positive"] == 2
    captured = _group(report, "winner_union_captured_positive")
    missed = _group(report, "winner_union_missed_positive")
    assert captured["positive_list_member_count"] == 2
    assert missed["positive_list_member_count"] == 0


def test_feature_summaries_are_descriptive_and_handle_missing_values(
    tmp_path: Path,
) -> None:
    report = build_winner_loser_feature_attribution(
        WinnerLoserAttributionConfig(
            snapshot_file=_snapshot(tmp_path),
            tail_fraction=0.25,
            min_group_size=1,
        )
    )

    winners = _group(report, "winner_union")
    losers = _group(report, "loser_union")
    assert winners["features"]["pre_5d_return"]["median"] > (
        losers["features"]["pre_5d_return"]["median"]
    )
    amount = winners["features"]["amount_change_20d"]
    assert amount["missing_count"] == 2
    assert amount["valid_count"] == 4
    comparison = _comparison(report, "winner_vs_loser_union")
    assert comparison["features"]["pre_5d_return"]["median_delta"] > 0
    assert all(
        row["status"] == "descriptive_only"
        for row in report["pattern_attribution"]
    )
    findings = report["key_descriptive_findings"]
    assert len(findings) == 5
    assert all(row["status"] == "descriptive_only" for row in findings)
    assert "captured 2 of 6" in findings[0]["text"]


def test_missing_requested_feature_is_reported_without_invention(
    tmp_path: Path,
) -> None:
    report = build_winner_loser_feature_attribution(
        WinnerLoserAttributionConfig(
            snapshot_file=_snapshot(tmp_path),
            tail_fraction=0.25,
            min_group_size=1,
            feature_fields=("pre_5d_return", "not_available"),
        )
    )

    availability = report["feature_availability"]
    assert availability["available_features"] == ["pre_5d_return"]
    assert availability["unavailable_features"] == ["not_available"]
    missing = next(
        row
        for row in availability["missingness"]
        if row["feature"] == "not_available"
    )
    assert missing["status"] == "column_unavailable"
    assert missing["missing_rate"] == 1.0


def test_report_guardrails_reject_production_interpretation(
    tmp_path: Path,
) -> None:
    outputs = tmp_path / "outputs"
    report = build_winner_loser_feature_attribution(
        WinnerLoserAttributionConfig(
            snapshot_file=_snapshot(tmp_path),
            tail_fraction=0.25,
            min_group_size=1,
        )
    )
    paths = write_winner_loser_feature_attribution_outputs(
        report,
        outputs,
    )
    markdown = Path(paths["markdown"]).read_text(encoding="utf-8")
    payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    lower = markdown.lower()

    assert "not blind validation" in lower
    assert "not evidence of production improvement" in lower
    assert "unseen windows" in lower
    assert "## key descriptive findings" in lower
    assert payload["summary"]["thresholds_tuned"] is False
    assert payload["summary"]["production_lists_created"] is False
    assert "buy" not in lower
    assert "sell" not in lower
    assert render_winner_loser_feature_attribution_markdown(report) == markdown


def test_missing_window_identity_requires_snapshot_regeneration(
    tmp_path: Path,
) -> None:
    path = _snapshot(tmp_path)
    frame = pd.read_csv(path)
    frame["as_of_date"] = None
    frame.to_csv(path, index=False)

    with pytest.raises(ValueError, match="regenerate"):
        build_winner_loser_feature_attribution(
            WinnerLoserAttributionConfig(snapshot_file=path)
        )


def _snapshot(tmp_path: Path) -> Path:
    path = tmp_path / "snapshot.csv"
    rows = []
    for window_index, as_of_date in enumerate(
        ("2024-01-31", "2024-04-30")
    ):
        returns = [0.50, 0.40, 0.30, 0.10, -0.10, -0.30, -0.40, -0.50]
        excess = [0.10, 0.60, 0.50, 0.05, -0.05, -0.50, -0.60, -0.10]
        for index, symbol in enumerate("ABCDEFGH"):
            positive = symbol in {"A", "F"}
            row = {
                "as_of_date": as_of_date,
                "horizon_days": 20,
                "symbol": f"{symbol}{window_index}",
                "data_quality": "ok",
                "captured_positive_lists": (
                    "high_confidence_candidates" if positive else ""
                ),
                "is_high_risk_active": symbol in {"G", "H"},
                "future_return": returns[index],
                "future_excess_return": excess[index],
                "pre_5d_return": 0.20 - index * 0.05,
                "pre_20d_return": 0.15 - index * 0.04,
                "pre_60d_return": -0.20 + index * 0.03,
                "volatility_20d": 0.02 + index * 0.01,
                "technical_volatility_20d": 0.02 + index * 0.01,
                "drawdown_60d": -0.05 - index * 0.03,
                "amount_change_20d": (
                    None if symbol == "C" else 0.30 - index * 0.04
                ),
                "volume_change_20d": 0.25 - index * 0.03,
                "distance_to_60d_high": -0.20 + index * 0.02,
                "distance_to_60d_low": 0.10 + index * 0.02,
                "recent_acceleration_proxy": 0.10 - index * 0.02,
                "high_position_crowding_proxy": index * 0.01,
                "total_score": 80 - index,
                "momentum_score": 20 - index,
                "trend_score": 18 - index,
                "relative_strength_score": 16 - index,
                "risk_score": 15 - index,
                "liquidity_score": 14 - index,
                "momentum_20d": 0.15 - index * 0.03,
                "momentum_60d": 0.10 - index * 0.02,
                "momentum_120d": 0.05 - index * 0.01,
                "rs_20d": 0.10 - index * 0.02,
                "rs_60d": 0.08 - index * 0.01,
                "rs_120d": 0.04 - index * 0.01,
                "max_drawdown_20d": -0.02 - index * 0.01,
                "max_drawdown_60d": -0.04 - index * 0.02,
                "avg_amount_20d": 100 + index,
                "avg_amount_60d": 90 + index,
                "avg_volume_20d": 80 + index,
                "avg_volume_60d": 70 + index,
            }
            rows.append(row)
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _group_counts(report: dict[str, object]) -> dict[str, int]:
    return {
        row["group_id"]: row["row_count"]
        for row in report["group_feature_summaries"]
    }


def _group(report: dict[str, object], group_id: str) -> dict[str, object]:
    return next(
        row
        for row in report["group_feature_summaries"]
        if row["group_id"] == group_id
    )


def _comparison(
    report: dict[str, object],
    comparison_id: str,
) -> dict[str, object]:
    return next(
        row
        for row in report["comparisons"]
        if row["comparison_id"] == comparison_id
    )
