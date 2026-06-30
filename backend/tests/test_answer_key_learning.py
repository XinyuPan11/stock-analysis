from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.validation.answer_key_learning import (
    ALL_LIST_IDS,
    AnswerKeyLearningConfig,
    build_answer_key_learning_report,
    render_answer_key_learning_markdown,
    write_answer_key_learning_outputs,
)


def test_case_membership_fills_capture_and_mistake_fields(
    tmp_path: Path,
) -> None:
    case_path, outputs = _fixture(tmp_path, filled_archetypes=True)
    report = build_answer_key_learning_report(
        AnswerKeyLearningConfig(case_study_file=case_path, outputs_dir=outputs)
    )

    cases = {row["symbol"]: row for row in report["cases"]}
    assert cases["A"]["captured_by_system"] is True
    assert cases["A"]["captured_lists"] == ["high_confidence_candidates"]
    assert cases["A"]["winner_missed"] is False
    assert cases["C"]["winner_missed"] is True
    assert cases["B"]["loser_incorrectly_captured"] is True
    assert cases["B"]["captured_as_risk_warning"] is True
    assert cases["B"]["captured_positive_lists"] == [
        "high_confidence_candidates"
    ]
    assert cases["B"]["captured_risk_lists"] == ["high_risk_active"]
    assert cases["C"]["membership_notes"] == "missed_winner"
    assert report["capture_summary"]["winner_missed_count"] == 1
    assert report["capture_summary"]["loser_incorrectly_captured_count"] == 1


def test_blank_manual_research_is_reported_without_invented_archetypes(
    tmp_path: Path,
) -> None:
    case_path, outputs = _fixture(tmp_path, filled_archetypes=False)
    report = build_answer_key_learning_report(
        AnswerKeyLearningConfig(case_study_file=case_path, outputs_dir=outputs)
    )

    assert (
        report["summary"]["status"]
        == "membership_matched_manual_research_incomplete"
    )
    assert report["archetype_summary"]["available"] is False
    assert report["archetype_summary"]["all_cases"] == {}
    assert (
        report["known_answer_key_hypotheses"]["evidence_status"]
        == "task_context_only_until_filled_case_study_is_supplied"
    )


def test_answer_key_report_writes_research_only_outputs(
    tmp_path: Path,
) -> None:
    case_path, outputs = _fixture(tmp_path, filled_archetypes=True)
    report = build_answer_key_learning_report(
        AnswerKeyLearningConfig(case_study_file=case_path, outputs_dir=outputs)
    )
    paths = write_answer_key_learning_outputs(report, outputs)
    assert Path(paths["membership_csv"]).exists()
    membership = pd.read_csv(paths["membership_csv"])
    assert "captured_positive_lists" in membership.columns
    assert "missed_winner" in membership.columns
    markdown = Path(paths["markdown"]).read_text(encoding="utf-8")
    lower = markdown.lower()

    assert markdown.startswith("# Controlled Answer-Key Case Study Learning\n")
    assert "Research-only" in markdown
    assert "buy" not in lower
    assert "sell" not in lower
    assert "short recommendation" not in lower
    assert "answer-key post-mortem" in lower
    assert "not blind validation" in lower
    assert "not evidence of production improvement" in lower
    assert "must be tested on unseen windows" in lower
    assert "do not hard-code the 2024 winners" in lower
    assert report["summary"]["in_sample_post_mortem"] is True
    assert report["summary"]["production_improvement_evidence"] is False
    assert report["summary"]["production_candidate_selection_changed"] is False
    assert render_answer_key_learning_markdown(report) == markdown


def test_filled_case_patterns_separate_missed_and_captured_winners(
    tmp_path: Path,
) -> None:
    case_path, outputs = _fixture(tmp_path, filled_archetypes=True)
    frame = pd.read_csv(case_path, dtype=str).fillna("")
    frame.loc[frame["symbol"] == "A", "is_fundamental_improvement"] = "是"
    frame.loc[frame["symbol"] == "C", "is_theme_catalyst"] = "是"
    frame.loc[frame["symbol"] == "C", "is_high_vol_right_tail"] = "是"
    frame.to_csv(case_path, index=False, encoding="utf-8-sig")
    report = build_answer_key_learning_report(
        AnswerKeyLearningConfig(case_study_file=case_path, outputs_dir=outputs)
    )

    patterns = report["case_pattern_summary"]
    assert patterns["missed_winner_patterns"]["case_count"] == 1
    assert (
        patterns["missed_winner_patterns"]["non_traditional_pattern_count"]
        == 1
    )
    assert patterns["captured_winner_patterns"]["case_count"] == 1
    assert patterns["winner_archetype_tokens"]["stable_trend"] == 1
    assert patterns["winner_archetype_tokens"][
        "theme_or_policy_catalyst"
    ] == 1


def _fixture(
    tmp_path: Path,
    *,
    filled_archetypes: bool,
) -> tuple[Path, Path]:
    outputs = tmp_path / "outputs"
    validation = outputs / "validation"
    lists = outputs / "lists"
    validation.mkdir(parents=True)
    lists.mkdir(parents=True)
    case_path = tmp_path / "cases.csv"
    pd.DataFrame(
        [
            _case("A", "winner", "stable_trend" if filled_archetypes else ""),
            _case(
                "B",
                "loser",
                "high_position_crowding_reversal"
                if filled_archetypes
                else "",
            ),
            _case(
                "C",
                "winner",
                "theme_or_policy_catalyst" if filled_archetypes else "",
            ),
        ]
    ).to_csv(case_path, index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [
            {"symbol": "A", "future_return": 0.20, "future_excess_return": 0.15},
            {"symbol": "B", "future_return": -0.20, "future_excess_return": -0.25},
            {"symbol": "C", "future_return": 0.30, "future_excess_return": 0.25},
        ]
    ).to_csv(
        validation / "walk_forward_predictions_2024-01-31_20d.csv",
        index=False,
    )
    for list_id in ALL_LIST_IDS:
        members = []
        if list_id == "high_confidence_candidates":
            members = ["A", "B"]
        elif list_id == "high_risk_active":
            members = ["B"]
        (lists / f"{list_id}_2024-01-31.json").write_text(
            json.dumps(
                {
                    "list_id": list_id,
                    "items": [{"symbol": symbol} for symbol in members],
                }
            ),
            encoding="utf-8",
        )
    return case_path, outputs


def _case(symbol: str, outcome: str, archetype: str) -> dict[str, object]:
    return {
        "symbol": symbol,
        "as_of_date": "2024-01-31",
        "horizon_days": 20,
        "future_return": 0.0,
        "future_excess_return": 0.0,
        "winner_or_loser": outcome,
        "company_name": symbol if archetype else "",
        "price_stage_before_move": "test" if archetype else "",
        "catalyst_summary": "test" if archetype else "",
        "archetype": archetype,
        "research_notes": "test" if archetype else "",
        "is_theme_catalyst": "",
        "is_event_driven": "",
        "is_low_position_reversal": "",
        "is_high_vol_right_tail": "",
        "is_fundamental_improvement": "",
        "is_loss_or_risk_company": "",
    }
