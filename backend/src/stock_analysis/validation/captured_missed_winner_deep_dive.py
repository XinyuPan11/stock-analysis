"""Read-only captured-vs-missed winner attribution from existing snapshots."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from stock_analysis.validation.winner_loser_feature_attribution import (
    construct_winner_loser_groups,
    prepare_snapshot_for_attribution,
)


SUMMARY_JSON_NAME = "captured_vs_missed_winner_deep_dive_2024.json"
SUMMARY_MARKDOWN_NAME = "captured_vs_missed_winner_deep_dive_2024.md"
DEFAULT_SNAPSHOT_FILE = (
    "outputs/experiments/member_level_asof_snapshot_2024.csv"
)
DEFAULT_ATTRIBUTION_FILE = (
    "outputs/experiments/winner_loser_feature_attribution_2024.json"
)
DEFAULT_CASE_STUDY_FILE = (
    "research/case_studies/case_study_filled_2024_with_membership.csv"
)
LIST_FIELD_MAP: dict[str, str] = {
    "high_confidence_candidates": "is_high_confidence",
    "trend_leaders": "is_trend_leader",
    "long_term_stable": "is_long_term_stable",
    "breakout_watch": "is_breakout_watch",
    "accumulation_watch": "is_accumulation_watch",
    "rebound_watch": "is_rebound_watch",
}
FEATURE_FIELDS: tuple[str, ...] = (
    "total_score",
    "momentum_score",
    "trend_score",
    "relative_strength_score",
    "risk_score",
    "liquidity_score",
    "pre_20d_return",
    "pre_60d_return",
    "volatility_20d",
    "technical_volatility_20d",
    "drawdown_60d",
    "amount_change_20d",
    "volume_change_20d",
    "distance_to_60d_high",
    "distance_to_60d_low",
    "recent_acceleration_proxy",
    "high_position_crowding_proxy",
)
LIST_COMPARISON_FIELDS: tuple[str, ...] = (
    "total_score",
    "trend_score",
    "pre_20d_return",
    "pre_60d_return",
    "volatility_20d",
    "drawdown_60d",
    "distance_to_60d_high",
    "recent_acceleration_proxy",
    "high_position_crowding_proxy",
)
EXTERNAL_GAPS: tuple[str, ...] = (
    "theme_or_policy_catalyst",
    "restructuring_or_control_change_event",
    "fundamental_change",
    "industry_or_sector_attribution",
    "historical_listing_st_suspension_status",
)
DISCLAIMER = (
    "Research-only in-sample 2024 answer-key deep dive. This is not blind "
    "validation and is not evidence of production improvement. It changes no "
    "production scoring, ranking, factors, labels, candidate selection, "
    "lists, thresholds, or recommendations."
)


@dataclass(frozen=True)
class CapturedMissedDeepDiveConfig:
    snapshot_file: str | Path = DEFAULT_SNAPSHOT_FILE
    attribution_file: str | Path = DEFAULT_ATTRIBUTION_FILE
    case_study_file: str | Path | None = DEFAULT_CASE_STUDY_FILE


def build_captured_missed_winner_deep_dive(
    config: CapturedMissedDeepDiveConfig,
) -> dict[str, Any]:
    snapshot_path = Path(config.snapshot_file)
    attribution_path = Path(config.attribution_file)
    if not snapshot_path.exists():
        raise FileNotFoundError(f"Snapshot file not found: {snapshot_path}")
    if not attribution_path.exists():
        raise FileNotFoundError(
            f"Phase 2.15 attribution file not found: {attribution_path}"
        )
    snapshot = pd.read_csv(
        snapshot_path,
        dtype={"symbol": str, "as_of_date": str},
    )
    if snapshot.empty or snapshot["as_of_date"].isna().any():
        raise ValueError(
            "Snapshot window identity is missing; regenerate Phase 2.14."
        )
    attribution = json.loads(
        attribution_path.read_text(encoding="utf-8")
    )
    tail_fraction = float(attribution["summary"]["tail_fraction"])
    min_group_size = int(attribution["summary"]["min_group_size"])
    prepared = prepare_snapshot_for_attribution(snapshot)
    groups, group_windows = construct_winner_loser_groups(
        prepared,
        tail_fraction=tail_fraction,
        min_group_size=min_group_size,
    )

    captured_winners = groups["winner_union_captured_positive"]
    missed_winners = groups["winner_union_missed_positive"]
    positive_losers = groups["loser_union_captured_positive"]
    winner_union = groups["winner_union"]
    loser_union = groups["loser_union"]
    positive_members = prepared[prepared["_has_positive_list"]].copy()
    available_features = [
        field
        for field in FEATURE_FIELDS
        if field in prepared
        and pd.to_numeric(prepared[field], errors="coerce").notna().any()
    ]
    cohorts = {
        "captured_winners": _cohort_summary(
            captured_winners,
            available_features,
        ),
        "missed_winners": _cohort_summary(
            missed_winners,
            available_features,
        ),
        "positive_list_winners": _cohort_summary(
            captured_winners,
            available_features,
        ),
        "positive_list_losers": _cohort_summary(
            positive_losers,
            available_features,
        ),
        "all_positive_list_members": _cohort_summary(
            positive_members,
            available_features,
        ),
    }
    comparisons = {
        "captured_vs_missed_winners": _feature_comparison(
            cohorts["captured_winners"],
            cohorts["missed_winners"],
            available_features,
        ),
        "positive_list_winners_vs_losers": _feature_comparison(
            cohorts["positive_list_winners"],
            cohorts["positive_list_losers"],
            available_features,
        ),
    }
    list_summaries = _list_summaries(
        prepared,
        winner_union,
        loser_union,
        available_features,
    )
    layering = _list_layering_summary(
        captured_winners,
        positive_losers,
    )
    missing_flags = {
        "captured_winners": _missing_flag_summary(captured_winners),
        "missed_winners": _missing_flag_summary(missed_winners),
        "positive_list_losers": _missing_flag_summary(positive_losers),
    }
    case_study = _case_study_summary(
        config.case_study_file,
        winner_union,
        loser_union,
    )
    findings = _descriptive_findings(
        cohorts,
        comparisons,
        list_summaries,
        case_study,
    )
    source_files = [str(snapshot_path), str(attribution_path)]
    attribution_markdown = attribution_path.with_suffix(".md")
    if attribution_markdown.exists():
        source_files.append(str(attribution_markdown))
    if case_study.get("available"):
        source_files.append(str(config.case_study_file))

    return _json_safe(
        {
            "summary": {
                "status": "ok",
                "research_only": True,
                "in_sample_answer_key_attribution": True,
                "blind_validation": False,
                "production_improvement_evidence": False,
                "provider_access": False,
                "labels_recomputed": False,
                "production_scoring_changed": False,
                "production_ranking_changed": False,
                "factor_formulas_changed": False,
                "validation_math_changed": False,
                "production_candidate_selection_changed": False,
                "production_lists_created": False,
                "thresholds_tuned": False,
                "production_recommendations_changed": False,
                "snapshot_row_count": int(len(prepared)),
                "window_count": len(group_windows),
                "tail_fraction_reused": tail_fraction,
                "min_group_size_reused": min_group_size,
                "winner_tail_count": int(len(winner_union)),
                "captured_winner_count": int(len(captured_winners)),
                "missed_winner_count": int(len(missed_winners)),
                "loser_tail_count": int(len(loser_union)),
                "positive_list_loser_count": int(len(positive_losers)),
                "disclaimer": DISCLAIMER,
            },
            "group_construction": {
                "source": "Phase 2.15 frozen within-window tail settings",
                "window_counts": group_windows,
            },
            "cohort_summaries": cohorts,
            "comparisons": comparisons,
            "list_specific_summaries": list_summaries,
            "list_layering_summary": layering,
            "missing_feature_flag_summary": missing_flags,
            "case_study_alignment": case_study,
            "key_descriptive_findings": findings,
            "external_data_gaps": list(EXTERNAL_GAPS),
            "guardrails": [
                "This is an in-sample answer-key post-mortem, not blind validation.",
                "Phase 2.15 group settings are reused without tuning.",
                "List summaries describe existing memberships and do not rebuild lists.",
                "Any hypothesis must be frozen and tested on unseen windows.",
                "No production improvement is established by this report.",
            ],
            "source_files": source_files,
            "outputs": {},
        }
    )


def write_captured_missed_winner_deep_dive_outputs(
    report: dict[str, Any],
    outputs_dir: str | Path,
) -> dict[str, str]:
    experiments_dir = Path(outputs_dir) / "experiments"
    experiments_dir.mkdir(parents=True, exist_ok=True)
    json_path = experiments_dir / SUMMARY_JSON_NAME
    markdown_path = experiments_dir / SUMMARY_MARKDOWN_NAME
    paths = {"json": str(json_path), "markdown": str(markdown_path)}
    report["outputs"] = paths
    json_path.write_text(
        json.dumps(_json_safe(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_captured_missed_winner_deep_dive_markdown(report),
        encoding="utf-8",
    )
    return paths


def render_captured_missed_winner_deep_dive_markdown(
    report: dict[str, Any],
) -> str:
    summary = report["summary"]
    lines = [
        "# Controlled Captured-vs-Missed Winner Deep Dive",
        "",
        str(summary["disclaimer"]),
        "",
        "## Guardrails",
        "",
    ]
    for item in report["guardrails"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Cohorts",
            "",
            f"- Winner tail: `{summary['winner_tail_count']}`",
            f"- Captured winners: `{summary['captured_winner_count']}`",
            f"- Missed winners: `{summary['missed_winner_count']}`",
            f"- Loser tail: `{summary['loser_tail_count']}`",
            f"- Positive-list losers: `{summary['positive_list_loser_count']}`",
            "",
            "## Captured-vs-Missed Winner Features",
            "",
            "| Feature | Captured median | Missed median | Delta | Valid counts |",
            "|---|---:|---:|---:|---|",
        ]
    )
    captured_missed = report["comparisons"][
        "captured_vs_missed_winners"
    ]
    for field, row in captured_missed.items():
        lines.append(
            f"| {field} | {_fmt(row['left_median'])} | "
            f"{_fmt(row['right_median'])} | {_fmt(row['median_delta'])} | "
            f"{row['left_valid_count']}/{row['right_valid_count']} |"
        )
    lines.extend(
        [
            "",
            "## Positive-List Winners-vs-Losers",
            "",
            "| Feature | Winner median | Loser median | Delta | Valid counts |",
            "|---|---:|---:|---:|---|",
        ]
    )
    positive_comparison = report["comparisons"][
        "positive_list_winners_vs_losers"
    ]
    for field, row in positive_comparison.items():
        lines.append(
            f"| {field} | {_fmt(row['left_median'])} | "
            f"{_fmt(row['right_median'])} | {_fmt(row['median_delta'])} | "
            f"{row['left_valid_count']}/{row['right_valid_count']} |"
        )
    lines.extend(
        [
            "",
            "## List-Specific Tail Attribution",
            "",
            "| List | Members | Winner tail | Loser tail | Winner capture | Tail contamination |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in report["list_specific_summaries"]:
        lines.append(
            f"| {row['list_id']} | {row['member_count']} | "
            f"{row['winner_tail_count']} | {row['loser_tail_count']} | "
            f"{_fmt_percent(row['winner_tail_capture_rate'])} | "
            f"{_fmt_percent(row['tail_contamination_rate'])} |"
        )
    lines.extend(["", "## Key Descriptive Findings", ""])
    for finding in report["key_descriptive_findings"]:
        lines.append(f"- {finding['text']}")
    lines.extend(["", "## Missing Feature Flags", ""])
    for cohort_id, payload in report[
        "missing_feature_flag_summary"
    ].items():
        lines.append(
            f"- `{cohort_id}`: {payload['rows_with_flags']}/"
            f"{payload['row_count']} rows with flags."
        )
    case_study = report["case_study_alignment"]
    lines.extend(["", "## Filled Case-Study Alignment", ""])
    if case_study.get("available"):
        lines.append(
            f"- Matched cases: `{case_study['matched_case_count']}`."
        )
        lines.append(
            "- Winner archetypes remain supplemental answer-key evidence; "
            "they are not inferred for the full snapshot."
        )
    else:
        lines.append(
            f"- Unavailable: {case_study.get('reason', 'not supplied')}."
        )
    lines.extend(["", "## External-Data Gaps", ""])
    for field in report["external_data_gaps"]:
        lines.append(f"- `{field}`")
    lines.extend(
        [
            "",
            "## Interpretation Boundary",
            "",
            "- Existing list memberships are described, not redesigned.",
            "- Median differences do not establish causality.",
            "- The same 2024 labels cannot validate a future change.",
            "- Unseen-window testing is required after hypotheses are frozen.",
            "",
        ]
    )
    return "\n".join(lines)


def _cohort_summary(
    frame: pd.DataFrame,
    features: list[str],
) -> dict[str, Any]:
    return {
        "row_count": int(len(frame)),
        "window_count": int(
            frame[["as_of_date", "horizon_days"]]
            .drop_duplicates()
            .shape[0]
            if not frame.empty
            else 0
        ),
        "high_risk_count": int(
            frame["_is_high_risk"].sum() if not frame.empty else 0
        ),
        "future_return_mean": _mean(frame.get("future_return")),
        "future_excess_return_mean": _mean(
            frame.get("future_excess_return")
        ),
        "features": {
            field: _distribution(frame[field], len(frame))
            for field in features
        },
    }


def _feature_comparison(
    left: dict[str, Any],
    right: dict[str, Any],
    features: list[str],
) -> dict[str, Any]:
    rows = {}
    for field in features:
        left_values = left["features"][field]
        right_values = right["features"][field]
        rows[field] = {
            "left_median": left_values["median"],
            "right_median": right_values["median"],
            "median_delta": _subtract(
                left_values["median"],
                right_values["median"],
            ),
            "left_mean": left_values["mean"],
            "right_mean": right_values["mean"],
            "mean_delta": _subtract(
                left_values["mean"],
                right_values["mean"],
            ),
            "left_valid_count": left_values["valid_count"],
            "right_valid_count": right_values["valid_count"],
        }
    return rows


def _list_summaries(
    frame: pd.DataFrame,
    winner_union: pd.DataFrame,
    loser_union: pd.DataFrame,
    available_features: list[str],
) -> list[dict[str, Any]]:
    winner_indices = set(winner_union.index)
    loser_indices = set(loser_union.index)
    rows = []
    for list_id, field in LIST_FIELD_MAP.items():
        if field not in frame:
            rows.append(
                {
                    "list_id": list_id,
                    "status": "missing_membership_column",
                    "member_count": 0,
                    "winner_tail_count": 0,
                    "loser_tail_count": 0,
                    "winner_tail_capture_rate": None,
                    "tail_contamination_rate": None,
                    "winner_vs_loser_features": {},
                }
            )
            continue
        members = set(frame.index[_bool_series(frame[field])])
        winner_members = frame.loc[sorted(members & winner_indices)]
        loser_members = frame.loc[sorted(members & loser_indices)]
        tail_count = len(winner_members) + len(loser_members)
        comparison_fields = [
            item
            for item in LIST_COMPARISON_FIELDS
            if item in available_features
        ]
        rows.append(
            {
                "list_id": list_id,
                "status": "ok",
                "member_count": len(members),
                "winner_tail_count": int(len(winner_members)),
                "loser_tail_count": int(len(loser_members)),
                "winner_tail_capture_rate": (
                    len(winner_members) / len(winner_union)
                    if len(winner_union)
                    else None
                ),
                "loser_tail_capture_rate": (
                    len(loser_members) / len(loser_union)
                    if len(loser_union)
                    else None
                ),
                "tail_contamination_rate": (
                    len(loser_members) / tail_count
                    if tail_count
                    else None
                ),
                "winner_future_excess_mean": _mean(
                    winner_members.get("future_excess_return")
                ),
                "loser_future_excess_mean": _mean(
                    loser_members.get("future_excess_return")
                ),
                "winner_vs_loser_features": _frame_comparison(
                    winner_members,
                    loser_members,
                    comparison_fields,
                ),
            }
        )
    return rows


def _frame_comparison(
    left: pd.DataFrame,
    right: pd.DataFrame,
    fields: list[str],
) -> dict[str, Any]:
    return {
        field: {
            "winner_median": _median(left.get(field)),
            "loser_median": _median(right.get(field)),
            "median_delta": _subtract(
                _median(left.get(field)),
                _median(right.get(field)),
            ),
            "winner_valid_count": _valid_count(left.get(field)),
            "loser_valid_count": _valid_count(right.get(field)),
        }
        for field in fields
    }


def _list_layering_summary(
    captured_winners: pd.DataFrame,
    positive_losers: pd.DataFrame,
) -> dict[str, Any]:
    return {
        "captured_winner_membership_depth": _membership_depth(
            captured_winners
        ),
        "positive_loser_membership_depth": _membership_depth(
            positive_losers
        ),
        "captured_winner_top_combinations": _membership_combinations(
            captured_winners
        ),
        "positive_loser_top_combinations": _membership_combinations(
            positive_losers
        ),
    }


def _membership_depth(frame: pd.DataFrame) -> dict[str, int]:
    counts: Counter[int] = Counter()
    for value in frame.get(
        "captured_positive_lists",
        pd.Series(dtype=str),
    ).fillna(""):
        depth = len([item for item in str(value).split(";") if item])
        counts[depth] += 1
    return {str(key): value for key, value in sorted(counts.items())}


def _membership_combinations(
    frame: pd.DataFrame,
) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter(
        str(value) or "none"
        for value in frame.get(
            "captured_positive_lists",
            pd.Series(dtype=str),
        ).fillna("")
    )
    return [
        {"combination": key, "count": count}
        for key, count in counts.most_common(10)
    ]


def _missing_flag_summary(frame: pd.DataFrame) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    rows_with_flags = 0
    for value in frame.get(
        "missing_feature_flags",
        pd.Series(dtype=str),
    ).fillna(""):
        flags = [item for item in str(value).split(";") if item]
        if flags:
            rows_with_flags += 1
            counts.update(flags)
    return {
        "row_count": int(len(frame)),
        "rows_with_flags": rows_with_flags,
        "top_flags": [
            {"flag": flag, "count": count}
            for flag, count in counts.most_common(20)
        ],
    }


def _case_study_summary(
    case_study_file: str | Path | None,
    winner_union: pd.DataFrame,
    loser_union: pd.DataFrame,
) -> dict[str, Any]:
    if not case_study_file:
        return {"available": False, "reason": "not_supplied"}
    path = Path(case_study_file)
    if not path.exists():
        return {"available": False, "reason": "file_not_found"}
    cases = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    required = {"symbol", "as_of_date", "horizon_days", "winner_or_loser"}
    if not required.issubset(cases.columns):
        return {"available": False, "reason": "missing_required_columns"}
    winner_keys = _frame_keys(winner_union)
    loser_keys = _frame_keys(loser_union)
    matched = 0
    winner_tail_matches = 0
    loser_tail_matches = 0
    captured_winner_archetypes: Counter[str] = Counter()
    missed_winner_archetypes: Counter[str] = Counter()
    for row in cases.to_dict(orient="records"):
        key = (
            str(row.get("symbol", "")),
            str(row.get("as_of_date", "")),
            _int_or_none(row.get("horizon_days")),
        )
        in_winner = key in winner_keys
        in_loser = key in loser_keys
        if in_winner or in_loser:
            matched += 1
        if in_winner:
            winner_tail_matches += 1
            target = (
                captured_winner_archetypes
                if _truthy(row.get("captured_as_positive_candidate"))
                else missed_winner_archetypes
            )
            target.update(_tokens(row.get("archetype")))
        if in_loser:
            loser_tail_matches += 1
    return {
        "available": True,
        "case_count": int(len(cases)),
        "matched_case_count": matched,
        "winner_tail_match_count": winner_tail_matches,
        "loser_tail_match_count": loser_tail_matches,
        "captured_winner_archetypes": _counter_rows(
            captured_winner_archetypes
        ),
        "missed_winner_archetypes": _counter_rows(
            missed_winner_archetypes
        ),
        "interpretation": (
            "Supplemental answer-key evidence only; case-study archetypes "
            "must not be inferred for unmatched snapshot rows."
        ),
    }


def _descriptive_findings(
    cohorts: dict[str, dict[str, Any]],
    comparisons: dict[str, dict[str, Any]],
    list_summaries: list[dict[str, Any]],
    case_study: dict[str, Any],
) -> list[dict[str, str]]:
    captured = cohorts["captured_winners"]
    missed = cohorts["missed_winners"]
    positive_losers = cohorts["positive_list_losers"]
    captured_missed = comparisons["captured_vs_missed_winners"]
    positive_win_loss = comparisons["positive_list_winners_vs_losers"]
    ranked_lists = sorted(
        (row for row in list_summaries if row["status"] == "ok"),
        key=lambda row: (
            -row["winner_tail_count"],
            row["tail_contamination_rate"]
            if row["tail_contamination_rate"] is not None
            else 1.0,
        ),
    )
    top_list = ranked_lists[0] if ranked_lists else None
    return [
        {
            "finding_id": "narrow_winner_capture",
            "text": (
                f"Existing positive lists captured {captured['row_count']} "
                f"winner-tail rows and missed {missed['row_count']}; current "
                "capture remains a narrow subset of the winner tail."
            ),
        },
        {
            "finding_id": "established_profile_preference",
            "text": (
                "Captured-minus-missed winner median deltas were "
                f"{_fmt_signed(_delta(captured_missed, 'total_score'))} "
                "total-score points, "
                f"{_fmt_signed_percent(_delta(captured_missed, 'pre_60d_return'))} "
                "pre-60D return, and "
                f"{_fmt_signed(_delta(captured_missed, 'trend_score'))} "
                "trend-score points. This describes preference for "
                "established score/trend context."
            ),
        },
        {
            "finding_id": "positive_winner_loser_risk_difference",
            "text": (
                "Within positive lists, winner-minus-loser median deltas were "
                f"{_fmt_signed_percent(_delta(positive_win_loss, 'volatility_20d'))} "
                "for volatility, "
                f"{_fmt_signed_percent(_delta(positive_win_loss, 'drawdown_60d'))} "
                "for 60D drawdown, and "
                f"{_fmt_signed(_delta(positive_win_loss, 'high_position_crowding_proxy'))} "
                "for the crowding proxy. These are descriptive diagnostics, "
                "not exclusion thresholds."
            ),
        },
        {
            "finding_id": "list_specific_capture",
            "text": (
                (
                    f"`{top_list['list_id']}` had the largest winner-tail "
                    f"capture count ({top_list['winner_tail_count']}) among "
                    "existing positive lists."
                )
                if top_list
                else "List-specific capture was unavailable."
            ),
        },
        {
            "finding_id": "positive_list_loser_context",
            "text": (
                f"Positive lists contained {positive_losers['row_count']} "
                "loser-tail rows; list-specific tables retain sample counts "
                "and contamination rates rather than treating all lists as "
                "equivalent."
            ),
        },
        {
            "finding_id": "external_data_boundary",
            "text": (
                "Filled case-study archetypes are available for "
                f"{case_study.get('matched_case_count', 0)} matched cases, "
                "but theme, event, fundamental, and industry causes remain "
                "unavailable for the full snapshot."
            ),
        },
    ]


def _distribution(series: pd.Series, total_count: int) -> dict[str, Any]:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return {
            "valid_count": 0,
            "missing_count": total_count,
            "mean": None,
            "median": None,
            "q25": None,
            "q75": None,
        }
    return {
        "valid_count": int(len(values)),
        "missing_count": int(total_count - len(values)),
        "mean": float(values.mean()),
        "median": float(values.median()),
        "q25": float(values.quantile(0.25)),
        "q75": float(values.quantile(0.75)),
    }


def _frame_keys(frame: pd.DataFrame) -> set[tuple[str, str, int | None]]:
    return {
        (
            str(row["symbol"]),
            str(row["as_of_date"]),
            _int_or_none(row["horizon_days"]),
        )
        for row in frame.to_dict(orient="records")
    }


def _counter_rows(counter: Counter[str]) -> list[dict[str, Any]]:
    return [
        {"archetype": key, "count": value}
        for key, value in counter.most_common()
    ]


def _tokens(value: Any) -> list[str]:
    return [
        item.strip().lower()
        for item in str(value or "").split(";")
        if item.strip()
    ]


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {
        "true",
        "1",
        "yes",
        "y",
        "是",
    }


def _bool_series(series: pd.Series) -> pd.Series:
    return (
        series.fillna(False)
        .astype(str)
        .str.strip()
        .str.lower()
        .isin({"true", "1", "yes", "y"})
    )


def _valid_count(series: pd.Series | None) -> int:
    if series is None:
        return 0
    return int(pd.to_numeric(series, errors="coerce").notna().sum())


def _mean(series: pd.Series | None) -> float | None:
    if series is None:
        return None
    values = pd.to_numeric(series, errors="coerce").dropna()
    return float(values.mean()) if not values.empty else None


def _median(series: pd.Series | None) -> float | None:
    if series is None:
        return None
    values = pd.to_numeric(series, errors="coerce").dropna()
    return float(values.median()) if not values.empty else None


def _subtract(left: Any, right: Any) -> float | None:
    if left is None or right is None:
        return None
    return float(left) - float(right)


def _delta(comparison: dict[str, Any], field: str) -> float | None:
    return comparison.get(field, {}).get("median_delta")


def _int_or_none(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(number) or math.isinf(number):
        return "n/a"
    return f"{number:.4f}"


def _fmt_percent(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.1%}"


def _fmt_signed(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):+.2f}"


def _fmt_signed_percent(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):+.2%}"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if hasattr(value, "item"):
        return _json_safe(value.item())
    return value
