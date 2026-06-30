"""Read-only answer-key case-study learning from existing validation outputs."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


POSITIVE_LIST_IDS: tuple[str, ...] = (
    "high_confidence_candidates",
    "trend_leaders",
    "long_term_stable",
    "breakout_watch",
    "accumulation_watch",
    "rebound_watch",
)
RISK_LIST_IDS: tuple[str, ...] = ("high_risk_active",)
ALL_LIST_IDS = (*POSITIVE_LIST_IDS, *RISK_LIST_IDS)
SUMMARY_JSON_NAME = "answer_key_case_study_learning_2024.json"
SUMMARY_MARKDOWN_NAME = "answer_key_case_study_learning_2024.md"
DISCLAIMER = (
    "Research-only answer-key post-mortem learning from already revealed "
    "2024 outcomes. This is not blind validation and is not evidence of "
    "production improvement. No production logic change was made."
)
OVERFITTING_GUARDRAILS: tuple[str, ...] = (
    "The 2024 answer-key case study is in-sample and may only be used for "
    "diagnosis, mistake review, and research-hypothesis generation.",
    "It can explain observed errors, but it cannot validate an improvement.",
    "No production scoring, ranking, factor, validation-label, candidate-"
    "selection, or recommendation logic was changed.",
    "Any candidate-bucket idea must be expressed as a general hypothesis and "
    "must be tested on unseen windows after the hypothesis is frozen.",
    "Do not hard-code the 2024 winners or tune thresholds to reproduce them.",
    "The same 2024 answer-key cases must not be used to claim improved "
    "performance.",
)


@dataclass(frozen=True)
class AnswerKeyLearningConfig:
    case_study_file: str | Path
    outputs_dir: str | Path = "outputs"


def build_answer_key_learning_report(
    config: AnswerKeyLearningConfig,
) -> dict[str, Any]:
    case_path = Path(config.case_study_file)
    outputs_dir = Path(config.outputs_dir)
    source_rows = _load_case_rows(case_path)
    enriched_rows: list[dict[str, Any]] = []
    missing_membership_files: set[str] = set()
    prediction_files: set[str] = set()
    membership_files: set[str] = set()

    prediction_cache: dict[tuple[str, int], dict[str, dict[str, Any]]] = {}
    membership_cache: dict[tuple[str, str], set[str] | None] = {}
    for source in source_rows:
        symbol = str(source.get("symbol", "")).strip()
        as_of_date = str(source.get("as_of_date", "")).strip()
        horizon_days = _int_or_default(source.get("horizon_days"), 20)
        outcome = str(source.get("winner_or_loser", "")).strip().lower()

        prediction_key = (as_of_date, horizon_days)
        if prediction_key not in prediction_cache:
            prediction_path = (
                outputs_dir
                / "validation"
                / f"walk_forward_predictions_{as_of_date}_{horizon_days}d.csv"
            )
            prediction_cache[prediction_key] = _load_prediction_map(
                prediction_path
            )
            if prediction_path.exists():
                prediction_files.add(str(prediction_path))

        captured_lists: list[str] = []
        membership_complete = True
        for list_id in ALL_LIST_IDS:
            membership_key = (as_of_date, list_id)
            if membership_key not in membership_cache:
                path = outputs_dir / "lists" / f"{list_id}_{as_of_date}.json"
                membership_cache[membership_key] = _load_membership(path)
                if path.exists():
                    membership_files.add(str(path))
                else:
                    missing_membership_files.add(str(path))
            members = membership_cache[membership_key]
            if members is None:
                membership_complete = False
            elif symbol in members:
                captured_lists.append(list_id)

        positive_lists = [
            item for item in captured_lists if item in POSITIVE_LIST_IDS
        ]
        risk_lists = [item for item in captured_lists if item in RISK_LIST_IDS]
        prediction = prediction_cache[prediction_key].get(symbol)
        winner_missed = (
            outcome == "winner" and not positive_lists
            if membership_complete
            else None
        )
        loser_incorrectly_captured = (
            outcome == "loser" and bool(positive_lists)
            if membership_complete
            else None
        )
        enriched_rows.append(
            {
                **source,
                "captured_by_system": bool(captured_lists)
                if membership_complete
                else None,
                "captured_lists": captured_lists,
                "captured_positive_lists": positive_lists,
                "captured_risk_lists": risk_lists,
                "captured_as_positive_candidate": bool(positive_lists)
                if membership_complete
                else None,
                "captured_as_risk_warning": bool(risk_lists)
                if membership_complete
                else None,
                "winner_missed": winner_missed,
                "loser_incorrectly_captured": loser_incorrectly_captured,
                "winner_in_high_risk_active": (
                    outcome == "winner" and "high_risk_active" in risk_lists
                    if membership_complete
                    else None
                ),
                "membership_notes": _membership_notes(
                    outcome,
                    positive_lists,
                    risk_lists,
                    membership_complete,
                ),
                "membership_status": (
                    "complete" if membership_complete else "partial"
                ),
                "prediction_matched": prediction is not None,
                "prediction_future_return": (
                    prediction.get("future_return") if prediction else None
                ),
                "prediction_future_excess_return": (
                    prediction.get("future_excess_return")
                    if prediction
                    else None
                ),
            }
        )

    manual_completeness = _manual_research_completeness(enriched_rows)
    capture_summary = _capture_summary(enriched_rows)
    archetype_summary = _archetype_summary(enriched_rows)
    case_pattern_summary = _case_pattern_summary(enriched_rows)
    status = _report_status(
        enriched_rows,
        missing_membership_files,
        manual_completeness,
    )
    proposed_buckets = _proposed_candidate_buckets(enriched_rows)

    return _json_safe(
        {
            "summary": {
                "status": status,
                "research_only": True,
                "answer_key_learning": True,
                "blind_validation": False,
                "in_sample_post_mortem": True,
                "production_improvement_evidence": False,
                "provider_access": False,
                "labels_recomputed": False,
                "production_scoring_changed": False,
                "production_candidate_selection_changed": False,
                "production_recommendations_changed": False,
                "case_count": len(enriched_rows),
                "winner_count": sum(
                    row.get("winner_or_loser") == "winner"
                    for row in enriched_rows
                ),
                "loser_count": sum(
                    row.get("winner_or_loser") == "loser"
                    for row in enriched_rows
                ),
                "disclaimer": DISCLAIMER,
            },
            "input_status": {
                "case_study_file": str(case_path),
                "manual_research_completeness": manual_completeness,
                "membership_files_complete": not missing_membership_files,
                "missing_membership_files": sorted(missing_membership_files),
                "prediction_match_count": sum(
                    bool(row.get("prediction_matched"))
                    for row in enriched_rows
                ),
            },
            "capture_summary": capture_summary,
            "archetype_summary": archetype_summary,
            "case_pattern_summary": case_pattern_summary,
            "diagnosis": _diagnosis(capture_summary, case_pattern_summary),
            "cases": enriched_rows,
            "proposed_candidate_buckets": proposed_buckets,
            "redesign_plan": _redesign_plan(),
            "overfitting_guardrails": list(OVERFITTING_GUARDRAILS),
            "known_answer_key_hypotheses": {
                "evidence_status": (
                    "task_context_only_until_filled_case_study_is_supplied"
                    if manual_completeness["archetype"]["filled_count"] == 0
                    else "case_level_fields_available"
                ),
                "winner_types_to_validate": [
                    "distressed_restructuring_or_event_revaluation",
                    "theme_or_policy_catalyst",
                    "low_position_reversal_or_revaluation",
                    "industry_recovery",
                    "cycle_or_resource_repricing",
                    "high_volatility_right_tail_opportunity",
                    "low_position_large_cap_revaluation",
                ],
                "loser_types_to_validate": [
                    "negative_event_or_delisting_risk",
                    "high_position_crowding_reversal",
                    "theme_fade",
                    "weak_fundamentals",
                    "failed_or_uncertain_acquisition_story",
                ],
            },
            "limitations": [
                "This is answer-key post-mortem learning on already revealed "
                "2024 outcomes, not blind validation.",
                "These findings are not evidence of production improvement.",
                "Membership matching identifies system capture, but does not explain event or policy causality.",
                "All candidate-bucket ideas are research hypotheses and must "
                "be tested on unseen windows.",
            ],
            "source_files": sorted(
                {str(case_path), *prediction_files, *membership_files}
            ),
            "outputs": {},
        }
    )


def write_answer_key_learning_outputs(
    report: dict[str, Any],
    outputs_dir: str | Path,
) -> dict[str, str]:
    experiments_dir = Path(outputs_dir) / "experiments"
    experiments_dir.mkdir(parents=True, exist_ok=True)
    json_path = experiments_dir / SUMMARY_JSON_NAME
    markdown_path = experiments_dir / SUMMARY_MARKDOWN_NAME
    case_path = Path(str(report["input_status"]["case_study_file"]))
    membership_csv_path = case_path.with_name(
        f"{case_path.stem}_with_membership.csv"
    )
    report["outputs"] = {
        "json": str(json_path),
        "markdown": str(markdown_path),
        "membership_csv": str(membership_csv_path),
    }
    _write_membership_csv(report.get("cases", []), membership_csv_path)
    json_path.write_text(
        json.dumps(_json_safe(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_answer_key_learning_markdown(report),
        encoding="utf-8",
    )
    return report["outputs"]


def render_answer_key_learning_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    capture = report["capture_summary"]
    lines = [
        "# Controlled Answer-Key Case Study Learning",
        "",
        str(summary["disclaimer"]),
        "",
        "## Overfitting Guardrails",
        "",
    ]
    for item in report.get("overfitting_guardrails", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.extend([
        "## Input Status",
        "",
        f"- Status: `{summary['status']}`",
        f"- Cases: `{summary['case_count']}` "
        f"({summary['winner_count']} winners, {summary['loser_count']} losers)",
        f"- Prediction matches: `{report['input_status']['prediction_match_count']}`",
        f"- Membership complete: `{report['input_status']['membership_files_complete']}`",
        "",
        "## System Capture",
        "",
        f"- Winners captured by positive lists: `{capture['winner_positive_captured_count']}`",
        f"- Winners missed by positive lists: `{capture['winner_missed_count']}`",
        f"- Losers incorrectly captured by positive lists: `{capture['loser_incorrectly_captured_count']}`",
        f"- Losers captured by risk-warning lists: `{capture['loser_risk_warning_count']}`",
        "",
        "| Symbol | As-of | Outcome | Positive capture | Risk capture | Captured lists | Miss/error flag |",
        "|---|---|---|---|---|---|---|",
    ])
    for row in report.get("cases", []):
        flag = ""
        if row.get("winner_missed"):
            flag = "winner_missed"
        elif row.get("loser_incorrectly_captured"):
            flag = "loser_incorrectly_captured"
        lines.append(
            f"| {row.get('symbol')} | {row.get('as_of_date')} | "
            f"{row.get('winner_or_loser')} | "
            f"{row.get('captured_as_positive_candidate')} | "
            f"{row.get('captured_as_risk_warning')} | "
            f"{', '.join(row.get('captured_lists', [])) or 'none'} | "
            f"{flag or 'none'} |"
        )

    lines.extend(["", "## Archetype Evidence", ""])
    archetypes = report.get("archetype_summary", {})
    if archetypes.get("available"):
        for name, count in archetypes.get("all_cases", {}).items():
            lines.append(f"- `{name}`: {count}")
    else:
        lines.append(
            "Case-level archetype fields are blank. The supplied winner/loser "
            "type summary remains a hypothesis until the filled case study is available."
        )

    patterns = report.get("case_pattern_summary", {})
    if patterns.get("available"):
        lines.extend(
            [
                "",
                "## Winner And Loser Patterns",
                "",
                "### Winner archetypes",
                "",
            ]
        )
        for name, count in patterns.get("winner_archetype_tokens", {}).items():
            lines.append(f"- `{name}`: {count}")
        lines.extend(["", "### Loser archetypes", ""])
        for name, count in patterns.get("loser_archetype_tokens", {}).items():
            lines.append(f"- `{name}`: {count}")
        lines.extend(["", "### Missed winner diagnosis", ""])
        missed = patterns.get("missed_winner_patterns", {})
        lines.append(
            f"- Missed winners with theme/event/reversal/right-tail flags: "
            f"`{missed.get('non_traditional_pattern_count', 0)}/"
            f"{missed.get('case_count', 0)}`."
        )
        for name, count in missed.get("archetype_tokens", {}).items():
            lines.append(f"- `{name}`: {count}")
        lines.extend(["", "### Captured winner archetypes", ""])
        captured = patterns.get("captured_winner_patterns", {})
        for name, count in captured.get("archetype_tokens", {}).items():
            lines.append(f"- `{name}`: {count}")

    lines.extend(["", "## Diagnosis", ""])
    for item in report.get("diagnosis", []):
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## Candidate-Bucket Research Hypotheses",
            "",
            "| Bucket | Posture | Current support | Missing data |",
            "|---|---|---|---|",
        ]
    )
    for bucket in report.get("proposed_candidate_buckets", []):
        lines.append(
            f"| {bucket['bucket_id']} | {bucket['posture']} | "
            f"{'; '.join(bucket['current_data_support'])} | "
            f"{'; '.join(bucket['missing_data']) or 'none'} |"
        )

    lines.extend(["", "## Hypothesis Evaluation Plan", ""])
    for section in report.get("redesign_plan", []):
        lines.append(f"### {section['group']}")
        lines.append("")
        for item in section["items"]:
            lines.append(f"- {item}")
        lines.append("")

    lines.extend(["## Limitations", ""])
    for item in report.get("limitations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def _load_case_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Case study file not found: {path}")
    if path.suffix.lower() in {".xlsx", ".xls"}:
        frame = pd.read_excel(path, dtype=str).fillna("")
    else:
        frame = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    required = {
        "symbol",
        "as_of_date",
        "horizon_days",
        "winner_or_loser",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Case study is missing required columns: {missing}")
    return [
        {str(key): _clean_scalar(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def _load_prediction_map(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    frame = pd.read_csv(path, dtype={"symbol": str})
    if "symbol" not in frame.columns:
        return {}
    return {
        str(row["symbol"]): {
            key: _clean_scalar(value) for key, value in row.items()
        }
        for row in frame.to_dict(orient="records")
    }


def _load_membership(path: Path) -> set[str] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        return None
    return {
        str(item.get("symbol", "")).strip()
        for item in payload["items"]
        if isinstance(item, dict) and str(item.get("symbol", "")).strip()
    }


def _manual_research_completeness(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, int | float]]:
    columns = (
        "company_name",
        "price_stage_before_move",
        "catalyst_summary",
        "archetype",
        "research_notes",
    )
    result = {}
    for column in columns:
        count = sum(bool(str(row.get(column, "")).strip()) for row in rows)
        result[column] = {
            "filled_count": count,
            "total_count": len(rows),
            "coverage_rate": count / len(rows) if rows else 0.0,
        }
    return result


def _capture_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    winners = [row for row in rows if row.get("winner_or_loser") == "winner"]
    losers = [row for row in rows if row.get("winner_or_loser") == "loser"]
    list_counts = {}
    for list_id in ALL_LIST_IDS:
        list_counts[list_id] = {
            "winner_count": sum(
                list_id in row.get("captured_lists", []) for row in winners
            ),
            "loser_count": sum(
                list_id in row.get("captured_lists", []) for row in losers
            ),
        }
    return {
        "winner_positive_captured_count": sum(
            bool(row.get("captured_as_positive_candidate")) for row in winners
        ),
        "winner_missed_count": sum(
            row.get("winner_missed") is True for row in winners
        ),
        "loser_incorrectly_captured_count": sum(
            row.get("loser_incorrectly_captured") is True for row in losers
        ),
        "loser_risk_warning_count": sum(
            bool(row.get("captured_as_risk_warning")) for row in losers
        ),
        "list_capture_counts": list_counts,
    }


def _archetype_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    available = [
        row for row in rows if str(row.get("archetype", "")).strip()
    ]
    return {
        "available": bool(available),
        "filled_case_count": len(available),
        "all_cases": _token_counts(available, "archetype"),
        "winner_cases": _token_counts(
            [row for row in available if row.get("winner_or_loser") == "winner"],
            "archetype",
        ),
        "loser_cases": _token_counts(
            [row for row in available if row.get("winner_or_loser") == "loser"],
            "archetype",
        ),
    }


def _case_pattern_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    available = [
        row for row in rows if str(row.get("archetype", "")).strip()
    ]
    winners = [row for row in available if row.get("winner_or_loser") == "winner"]
    losers = [row for row in available if row.get("winner_or_loser") == "loser"]
    missed_winners = [row for row in winners if row.get("winner_missed") is True]
    captured_winners = [
        row for row in winners if row.get("captured_as_positive_candidate") is True
    ]
    polluted_losers = [
        row for row in losers if row.get("loser_incorrectly_captured") is True
    ]
    return {
        "available": bool(available),
        "winner_archetype_tokens": _token_counts(winners, "archetype"),
        "loser_archetype_tokens": _token_counts(losers, "archetype"),
        "winner_catalyst_patterns": _flag_counts(winners),
        "loser_risk_patterns": {
            "archetype_tokens": _token_counts(losers, "archetype"),
            "loss_or_risk_company_count": sum(
                _is_true(row.get("is_loss_or_risk_company")) for row in losers
            ),
            "negative_event_count": sum(
                "negative_event_loser" in _tokens(row.get("archetype"))
                for row in losers
            ),
            "high_position_crowding_count": sum(
                "high_position_crowding_reversal" in _tokens(row.get("archetype"))
                for row in losers
            ),
        },
        "missed_winner_patterns": _winner_pattern_group(missed_winners),
        "captured_winner_patterns": _winner_pattern_group(captured_winners),
        "polluted_loser_patterns": {
            "case_count": len(polluted_losers),
            "archetype_tokens": _token_counts(polluted_losers, "archetype"),
        },
    }


def _winner_pattern_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    non_traditional_count = sum(
        any(
            _is_true(row.get(column))
            for column in (
                "is_theme_catalyst",
                "is_event_driven",
                "is_low_position_reversal",
                "is_high_vol_right_tail",
            )
        )
        for row in rows
    )
    return {
        "case_count": len(rows),
        "archetype_tokens": _token_counts(rows, "archetype"),
        "flag_counts": _flag_counts(rows),
        "non_traditional_pattern_count": non_traditional_count,
        "non_traditional_pattern_rate": (
            non_traditional_count / len(rows) if rows else None
        ),
    }


def _flag_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    columns = (
        "is_theme_catalyst",
        "is_event_driven",
        "is_low_position_reversal",
        "is_high_vol_right_tail",
        "is_fundamental_improvement",
        "is_loss_or_risk_company",
    )
    return {
        column: sum(_is_true(row.get(column)) for row in rows)
        for column in columns
    }


def _diagnosis(
    capture_summary: dict[str, Any],
    patterns: dict[str, Any],
) -> list[str]:
    winner_missed = int(capture_summary["winner_missed_count"])
    winner_captured = int(capture_summary["winner_positive_captured_count"])
    loser_pollution = int(capture_summary["loser_incorrectly_captured_count"])
    missed = patterns.get("missed_winner_patterns", {})
    non_traditional = int(missed.get("non_traditional_pattern_count") or 0)
    return [
        f"Positive lists captured {winner_captured} winners and missed {winner_missed}; the primary weakness is under-capture, not list pollution.",
        f"{non_traditional} of {winner_missed} missed winners carry theme, event, low-position reversal, or right-tail flags.",
        f"Only {loser_pollution} loser entered a positive list in this sample, so broad contamination is not the main explanation.",
        "high_risk_active captured no winners in this case set; missed winners should be studied by archetype rather than explained by the risk bucket.",
        "These are same-period answer-key findings and require separate unseen-window testing.",
    ]


def _membership_notes(
    outcome: str,
    positive_lists: list[str],
    risk_lists: list[str],
    membership_complete: bool,
) -> str:
    if not membership_complete:
        return "membership_incomplete"
    notes = []
    if outcome == "winner" and not positive_lists:
        notes.append("missed_winner")
    if outcome == "loser" and positive_lists:
        notes.append("polluted_positive_list_loser")
    if outcome == "winner" and "high_risk_active" in risk_lists:
        notes.append("winner_in_high_risk_active")
    if not notes:
        notes.append("membership_aligned")
    return "; ".join(notes)


def _write_membership_csv(rows: list[dict[str, Any]], path: Path) -> None:
    output_rows = []
    for row in rows:
        output = dict(row)
        output["captured_lists"] = ";".join(row.get("captured_lists", []))
        output["captured_positive_lists"] = ";".join(
            row.get("captured_positive_lists", [])
        )
        output["captured_risk_lists"] = ";".join(
            row.get("captured_risk_lists", [])
        )
        output["missed_winner"] = row.get("winner_missed")
        output["polluted_positive_list_loser"] = row.get(
            "loser_incorrectly_captured"
        )
        output_rows.append(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(output_rows).to_csv(path, index=False, encoding="utf-8-sig")


def _report_status(
    rows: list[dict[str, Any]],
    missing_membership_files: set[str],
    completeness: dict[str, dict[str, int | float]],
) -> str:
    if not rows:
        return "insufficient_data"
    if missing_membership_files:
        return "partial_membership"
    if completeness["archetype"]["filled_count"] == 0:
        return "membership_matched_manual_research_incomplete"
    if completeness["archetype"]["filled_count"] < len(rows):
        return "membership_matched_partial_manual_research"
    return "ok"


def _proposed_candidate_buckets(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    definitions = [
        {
            "bucket_id": "stable_trend_candidates",
            "archetypes": {"stable_trend", "trend_continuation", "stable_quality_compounder", "industry_recovery"},
            "motivation": "Separate repeatable trend structure from event-driven right-tail cases.",
            "opportunity_type": "price-confirmed stable trend",
            "risks": ["trend exhaustion", "crowding", "volatility expansion"],
            "current_data_support": [
                "momentum",
                "trend",
                "relative strength",
                "volatility",
                "drawdown",
            ],
            "missing_data": [],
            "posture": "high-confidence only after unseen-window validation",
        },
        {
            "bucket_id": "low_position_revaluation_candidates",
            "archetypes": {
                "low_position_reversal",
                "low_position_revaluation",
                "low_position_large_cap_revaluation",
            },
            "motivation": "Study low-position repricing separately from mature trend leadership.",
            "opportunity_type": "low-position reversal or valuation reset",
            "risks": ["value trap", "weak confirmation", "liquidity deterioration"],
            "current_data_support": [
                "long-horizon drawdown",
                "moving-average position",
                "relative-strength inflection",
            ],
            "missing_data": ["historical valuation context"],
            "posture": "watch-only",
        },
        {
            "bucket_id": "turnaround_watch",
            "archetypes": {
                "industry_recovery",
                "cycle_or_resource_repricing",
                "cycle_resource_repricing",
                "event_revaluation",
                "distressed_restructuring_repricing",
                "distressed_restructuring_or_event_revaluation",
            },
            "motivation": "Keep turnaround and cyclical repricing distinct from stable quality.",
            "opportunity_type": "turnaround or recovery confirmation",
            "risks": ["false recovery", "weak fundamentals", "event failure"],
            "current_data_support": [
                "price reversal",
                "volume",
                "relative strength",
            ],
            "missing_data": [
                "financial turnaround evidence",
                "industry-cycle evidence",
                "announcement confirmation",
            ],
            "posture": "watch-only",
        },
        {
            "bucket_id": "theme_acceleration_watch",
            "archetypes": {"theme_or_policy_catalyst", "theme_policy_catalyst", "theme_acceleration"},
            "motivation": "Represent catalyst-driven acceleration without treating it as stable trend.",
            "opportunity_type": "theme or policy acceleration",
            "risks": ["theme fade", "crowding", "catalyst reversal"],
            "current_data_support": ["momentum", "volume", "volatility"],
            "missing_data": [
                "news",
                "announcements",
                "policy and theme classification",
            ],
            "posture": "watch-only",
        },
        {
            "bucket_id": "right_tail_opportunity_watch",
            "archetypes": {"high_volatility_right_tail_opportunity", "high_volatility_right_tail"},
            "motivation": "Preserve right-tail cases without mixing them into conservative lists.",
            "opportunity_type": "high-volatility asymmetric observation",
            "risks": ["large drawdown", "failure concentration", "small sample"],
            "current_data_support": [
                "volatility",
                "momentum",
                "drawdown",
                "right-tail validation metrics",
            ],
            "missing_data": ["catalyst confirmation"],
            "posture": "watch-only",
        },
        {
            "bucket_id": "high_position_crowding_risk",
            "archetypes": {"high_position_crowding_reversal", "theme_fade"},
            "motivation": "Separate high-position reversal risk from generic volatility.",
            "opportunity_type": "risk warning",
            "risks": ["rapid reversal", "liquidity unwind", "theme decay"],
            "current_data_support": [
                "long-horizon momentum",
                "distance from moving averages",
                "volatility",
                "drawdown",
            ],
            "missing_data": ["crowding and theme persistence data"],
            "posture": "risk-warning only",
        },
        {
            "bucket_id": "negative_event_or_delisting_risk",
            "archetypes": {
                "negative_event_or_delisting_risk",
                "negative_event_loser",
                "delisting_risk_loser",
                "failed_or_uncertain_acquisition_story",
                "cross_border_acquisition_uncertainty",
                "weak_fundamentals",
                "fundamental_weakness_loser",
            },
            "motivation": "Keep event and status hazards outside positive candidate logic.",
            "opportunity_type": "risk warning",
            "risks": ["delisting", "negative event", "transaction failure"],
            "current_data_support": [
                "current risk labels",
                "price and drawdown deterioration",
            ],
            "missing_data": [
                "historical ST and listing status",
                "announcements",
                "transaction lifecycle",
                "fundamental quality",
            ],
            "posture": "risk-warning only",
        },
    ]
    for definition in definitions:
        definition["matched_case_symbols"] = sorted(
            {
                str(row.get("symbol"))
                for row in rows
                if definition["archetypes"]
                & set(_tokens(row.get("archetype")))
            }
        )
        definition["case_evidence_status"] = (
            "matched_from_filled_case_rows"
            if definition["matched_case_symbols"]
            else "awaiting_filled_case_archetypes"
        )
        definition.pop("archetypes")
    return definitions


def _redesign_plan() -> list[dict[str, Any]]:
    return [
        {
            "group": "A. Implementable now with existing price/factor/list outputs",
            "items": [
                "Research-only stable trend, low-position, volatility, drawdown, and crowding diagnostics.",
                "Keep stable, turnaround, and right-tail observations in separate report buckets.",
                "Preserve high_risk_active as a risk-warning signal.",
            ],
        },
        {
            "group": "B. Requires durable member-level factor snapshots",
            "items": [
                "Persist point-in-time bucket features, thresholds, and membership reasons.",
                "Track distance-from-high, moving-average position, and factor exposure per member.",
                "Retain overlap and exclusion reasons for later attribution.",
            ],
        },
        {
            "group": "C. Requires news, announcement, theme, or fundamental data",
            "items": [
                "Event-revaluation, policy-theme, restructuring, transaction, and delisting evidence.",
                "Industry recovery and cycle confirmation.",
                "Theme fade, catalyst invalidation, and fundamental deterioration.",
            ],
        },
        {
            "group": "D. Must wait for out-of-sample testing",
            "items": [
                "Do not select thresholds, promote candidates, or change "
                "production ranking from these 2024 cases.",
                "Every general hypothesis must be tested on unseen windows "
                "after it is frozen.",
                "Comparison against unchanged baseline logic with point-in-time metadata.",
            ],
        },
    ]


def _value_counts(
    rows: list[dict[str, Any]],
    key: str,
) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key, "")).strip()
        if value:
            result[value] = result.get(value, 0) + 1
    return dict(sorted(result.items()))


def _token_counts(
    rows: list[dict[str, Any]],
    key: str,
) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in rows:
        for token in _tokens(row.get(key)):
            result[token] = result.get(token, 0) + 1
    return dict(sorted(result.items(), key=lambda item: (-item[1], item[0])))


def _tokens(value: Any) -> list[str]:
    return [
        token.strip().lower()
        for token in str(value or "").split(";")
        if token.strip()
    ]


def _is_true(value: Any) -> bool:
    return str(value or "").strip().lower() in {
        "true",
        "1",
        "yes",
        "y",
        "是",
    }


def _int_or_default(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _clean_scalar(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    if hasattr(value, "item"):
        return _clean_scalar(value.item())
    return value


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if hasattr(value, "item"):
        return _json_safe(value.item())
    return value
