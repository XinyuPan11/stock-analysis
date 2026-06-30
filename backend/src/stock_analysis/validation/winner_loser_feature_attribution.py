"""Read-only winner/loser attribution from an existing as-of snapshot."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


SUMMARY_JSON_NAME = "winner_loser_feature_attribution_2024.json"
SUMMARY_MARKDOWN_NAME = "winner_loser_feature_attribution_2024.md"
DEFAULT_SNAPSHOT_FILE = (
    "outputs/experiments/member_level_asof_snapshot_2024.csv"
)
DEFAULT_FEATURE_FIELDS: tuple[str, ...] = (
    "pre_5d_return",
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
    "total_score",
    "momentum_score",
    "trend_score",
    "relative_strength_score",
    "risk_score",
    "liquidity_score",
    "momentum_20d",
    "momentum_60d",
    "momentum_120d",
    "rs_20d",
    "rs_60d",
    "rs_120d",
    "max_drawdown_20d",
    "max_drawdown_60d",
    "avg_amount_20d",
    "avg_amount_60d",
    "avg_volume_20d",
    "avg_volume_60d",
)
EXTERNAL_DATA_GAPS: tuple[str, ...] = (
    "theme_or_policy_catalyst",
    "restructuring_or_control_change_event",
    "fundamental_change",
    "industry_or_sector_attribution",
    "historical_listing_st_suspension_status",
)
GROUP_ORDER: tuple[str, ...] = (
    "top_future_return_winners",
    "top_future_excess_return_winners",
    "winner_union",
    "winner_union_captured_positive",
    "winner_union_missed_positive",
    "bottom_future_return_losers",
    "bottom_future_excess_return_losers",
    "loser_union",
    "loser_union_captured_positive",
    "high_risk_active",
    "non_high_risk",
)
PATTERN_FEATURES: dict[str, tuple[str, ...]] = {
    "low_position_reversal_signature": (
        "pre_60d_return",
        "drawdown_60d",
        "distance_to_60d_high",
        "distance_to_60d_low",
        "recent_acceleration_proxy",
    ),
    "trend_acceleration_signature": (
        "pre_5d_return",
        "pre_20d_return",
        "recent_acceleration_proxy",
        "momentum_score",
        "trend_score",
    ),
    "volume_amount_expansion_signature": (
        "amount_change_20d",
        "volume_change_20d",
        "avg_amount_20d",
        "avg_volume_20d",
    ),
    "right_tail_volatility_signature": (
        "volatility_20d",
        "technical_volatility_20d",
        "pre_5d_return",
        "recent_acceleration_proxy",
    ),
    "high_position_crowding_false_breakout_signature": (
        "high_position_crowding_proxy",
        "distance_to_60d_high",
        "pre_20d_return",
        "volatility_20d",
        "drawdown_60d",
    ),
}
DISCLAIMER = (
    "Research-only in-sample 2024 answer-key attribution. This is not blind "
    "validation and is not evidence of production improvement. It changes no "
    "production scoring, ranking, factors, labels, candidate selection, "
    "lists, thresholds, or recommendations."
)


@dataclass(frozen=True)
class WinnerLoserAttributionConfig:
    snapshot_file: str | Path = DEFAULT_SNAPSHOT_FILE
    tail_fraction: float = 0.10
    min_group_size: int = 10
    feature_fields: tuple[str, ...] = DEFAULT_FEATURE_FIELDS


def build_winner_loser_feature_attribution(
    config: WinnerLoserAttributionConfig,
) -> dict[str, Any]:
    _validate_config(config)
    snapshot_path = Path(config.snapshot_file)
    if not snapshot_path.exists():
        raise FileNotFoundError(f"Snapshot file not found: {snapshot_path}")
    frame = pd.read_csv(
        snapshot_path,
        dtype={"symbol": str, "as_of_date": str},
    )
    _validate_snapshot(frame)
    prepared = _prepare_snapshot(frame)
    groups, group_windows = _construct_groups(
        prepared,
        tail_fraction=config.tail_fraction,
        min_group_size=config.min_group_size,
    )
    available_features = [
        field
        for field in config.feature_fields
        if field in prepared
        and pd.to_numeric(prepared[field], errors="coerce").notna().any()
    ]
    unavailable_features = [
        field for field in config.feature_fields if field not in available_features
    ]
    group_summaries = [
        _group_summary(
            group_id,
            groups[group_id],
            available_features,
        )
        for group_id in GROUP_ORDER
    ]
    summary_map = {row["group_id"]: row for row in group_summaries}
    comparisons = [
        _comparison(
            "winner_vs_loser_union",
            summary_map["winner_union"],
            summary_map["loser_union"],
            available_features,
        ),
        _comparison(
            "captured_vs_missed_winners",
            summary_map["winner_union_captured_positive"],
            summary_map["winner_union_missed_positive"],
            available_features,
        ),
        _comparison(
            "positive_list_losers_vs_all_losers",
            summary_map["loser_union_captured_positive"],
            summary_map["loser_union"],
            available_features,
        ),
        _comparison(
            "high_risk_vs_non_high_risk",
            summary_map["high_risk_active"],
            summary_map["non_high_risk"],
            available_features,
        ),
    ]
    comparison_map = {row["comparison_id"]: row for row in comparisons}
    pattern_attribution = _pattern_attribution(
        comparison_map,
        available_features,
    )
    descriptive_findings = _descriptive_findings(
        summary_map,
        comparison_map,
    )
    missingness = _feature_missingness(prepared, config.feature_fields)
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
                "window_count": int(
                    prepared[["as_of_date", "horizon_days"]]
                    .drop_duplicates()
                    .shape[0]
                ),
                "tail_fraction": config.tail_fraction,
                "min_group_size": config.min_group_size,
                "disclaimer": DISCLAIMER,
            },
            "group_definitions": _group_definitions(),
            "group_window_counts": group_windows,
            "group_feature_summaries": group_summaries,
            "comparisons": comparisons,
            "pattern_attribution": pattern_attribution,
            "key_descriptive_findings": descriptive_findings,
            "feature_availability": {
                "requested_feature_count": len(config.feature_fields),
                "available_features": available_features,
                "unavailable_features": unavailable_features,
                "missingness": missingness,
            },
            "external_data_gaps": list(EXTERNAL_DATA_GAPS),
            "interpretation": [
                "All winner and loser groups are defined within each as-of window using predeclared tail rules.",
                "Captured and missed groups use existing positive-list membership only.",
                "Feature summaries are descriptive distributions, not fitted thresholds.",
                "Theme, event, fundamental, industry, and historical-status causes remain unavailable.",
                "Any hypothesis inspired by this report must be frozen and tested on unseen windows.",
            ],
            "guardrails": [
                "This is an in-sample 2024 answer-key post-mortem, not blind validation.",
                "The same 2024 outcomes must not be used to claim production improvement.",
                "No production logic or threshold is changed by this report.",
            ],
            "source_files": [str(snapshot_path)],
            "outputs": {},
        }
    )


def write_winner_loser_feature_attribution_outputs(
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
        render_winner_loser_feature_attribution_markdown(report),
        encoding="utf-8",
    )
    return paths


def render_winner_loser_feature_attribution_markdown(
    report: dict[str, Any],
) -> str:
    summary = report["summary"]
    lines = [
        "# Controlled Winner / Loser Feature Attribution",
        "",
        str(summary["disclaimer"]),
        "",
        "## Guardrails",
        "",
    ]
    for item in report.get("guardrails", []):
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Group Construction",
            "",
            f"- Snapshot rows: `{summary['snapshot_row_count']}`",
            f"- Windows: `{summary['window_count']}`",
            f"- Tail fraction: `{summary['tail_fraction']:.0%}`",
            f"- Minimum group size per window: `{summary['min_group_size']}`",
            "",
            "| Group | Rows | Windows | Avg future return | Avg excess return | Positive-list members | High-risk members |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in report.get("group_feature_summaries", []):
        outcomes = row["outcomes"]
        lines.append(
            f"| {row['group_id']} | {row['row_count']} | "
            f"{row['window_count']} | "
            f"{_fmt(outcomes.get('future_return_mean'))} | "
            f"{_fmt(outcomes.get('future_excess_return_mean'))} | "
            f"{row['positive_list_member_count']} | "
            f"{row['high_risk_member_count']} |"
        )
    lines.extend(
        [
            "",
            "## Descriptive Pattern Attribution",
            "",
            "| Pattern | Feature | Winner vs loser median delta | Captured vs missed winner median delta |",
            "|---|---|---:|---:|",
        ]
    )
    for pattern in report.get("pattern_attribution", []):
        for feature in pattern["features"]:
            lines.append(
                f"| {pattern['pattern_id']} | {feature['feature']} | "
                f"{_fmt(feature.get('winner_vs_loser_median_delta'))} | "
                f"{_fmt(feature.get('captured_vs_missed_median_delta'))} |"
            )
    lines.extend(["", "## Key Descriptive Findings", ""])
    for finding in report.get("key_descriptive_findings", []):
        lines.append(f"- {finding['text']}")
    lines.extend(["", "## Feature Availability", ""])
    availability = report["feature_availability"]
    lines.append(
        f"- Available features: `{len(availability['available_features'])}`."
    )
    lines.append(
        "- Unavailable requested features: "
        + (", ".join(availability["unavailable_features"]) or "none")
        + "."
    )
    lines.extend(["", "## External-Data Gaps", ""])
    for field in report.get("external_data_gaps", []):
        lines.append(f"- `{field}`")
    lines.extend(["", "## Interpretation Boundary", ""])
    for item in report.get("interpretation", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def _validate_config(config: WinnerLoserAttributionConfig) -> None:
    if not 0 < config.tail_fraction < 0.5:
        raise ValueError("tail_fraction must be between 0 and 0.5")
    if config.min_group_size < 1:
        raise ValueError("min_group_size must be positive")


def _validate_snapshot(frame: pd.DataFrame) -> None:
    required = {
        "as_of_date",
        "horizon_days",
        "symbol",
        "future_return",
        "future_excess_return",
        "captured_positive_lists",
        "is_high_risk_active",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Snapshot is missing required columns: {missing}")
    if frame.empty:
        raise ValueError("Snapshot is empty")
    if frame["as_of_date"].isna().any():
        raise ValueError(
            "Snapshot contains missing as_of_date values; regenerate the "
            "Phase 2.14 snapshot before attribution."
        )


def _prepare_snapshot(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["as_of_date"] = result["as_of_date"].astype(str)
    result["horizon_days"] = pd.to_numeric(
        result["horizon_days"],
        errors="coerce",
    )
    result["future_return"] = pd.to_numeric(
        result["future_return"],
        errors="coerce",
    )
    result["future_excess_return"] = pd.to_numeric(
        result["future_excess_return"],
        errors="coerce",
    )
    result["_has_positive_list"] = (
        result["captured_positive_lists"].fillna("").astype(str).str.strip()
        != ""
    )
    result["_is_high_risk"] = _boolean_series(
        result["is_high_risk_active"]
    )
    return result


def _construct_groups(
    frame: pd.DataFrame,
    *,
    tail_fraction: float,
    min_group_size: int,
) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    group_indices: dict[str, set[int]] = {
        group_id: set() for group_id in GROUP_ORDER
    }
    window_rows: list[dict[str, Any]] = []
    grouped = frame.groupby(
        ["as_of_date", "horizon_days"],
        sort=True,
        dropna=False,
    )
    for (as_of_date, horizon_days), window in grouped:
        return_top = _tail_indices(
            window,
            "future_return",
            top=True,
            fraction=tail_fraction,
            min_count=min_group_size,
        )
        excess_top = _tail_indices(
            window,
            "future_excess_return",
            top=True,
            fraction=tail_fraction,
            min_count=min_group_size,
        )
        return_bottom = _tail_indices(
            window,
            "future_return",
            top=False,
            fraction=tail_fraction,
            min_count=min_group_size,
        )
        excess_bottom = _tail_indices(
            window,
            "future_excess_return",
            top=False,
            fraction=tail_fraction,
            min_count=min_group_size,
        )
        winners = return_top | excess_top
        losers = return_bottom | excess_bottom
        positive = set(
            window.index[window["_has_positive_list"]]
        )
        high_risk = set(window.index[window["_is_high_risk"]])
        all_indices = set(window.index)
        window_groups = {
            "top_future_return_winners": return_top,
            "top_future_excess_return_winners": excess_top,
            "winner_union": winners,
            "winner_union_captured_positive": winners & positive,
            "winner_union_missed_positive": winners - positive,
            "bottom_future_return_losers": return_bottom,
            "bottom_future_excess_return_losers": excess_bottom,
            "loser_union": losers,
            "loser_union_captured_positive": losers & positive,
            "high_risk_active": high_risk,
            "non_high_risk": all_indices - high_risk,
        }
        for group_id, indices in window_groups.items():
            group_indices[group_id].update(indices)
        window_rows.append(
            {
                "as_of_date": str(as_of_date),
                "horizon_days": int(horizon_days),
                "source_row_count": int(len(window)),
                "tail_count_per_label": int(len(return_top)),
                "group_counts": {
                    key: len(value) for key, value in window_groups.items()
                },
            }
        )
    return (
        {
            group_id: frame.loc[sorted(indices)].copy()
            for group_id, indices in group_indices.items()
        },
        window_rows,
    )


def _tail_indices(
    frame: pd.DataFrame,
    field: str,
    *,
    top: bool,
    fraction: float,
    min_count: int,
) -> set[int]:
    valid = frame.loc[
        pd.to_numeric(frame[field], errors="coerce").notna(),
        [field, "symbol"],
    ].copy()
    if valid.empty:
        return set()
    valid[field] = pd.to_numeric(valid[field], errors="coerce")
    count = max(min_count, int(math.ceil(len(valid) * fraction)))
    count = min(count, max(1, len(valid) // 2))
    valid = valid.sort_values(
        [field, "symbol"],
        ascending=[not top, True],
        kind="stable",
    )
    return set(valid.head(count).index)


def _group_summary(
    group_id: str,
    frame: pd.DataFrame,
    feature_fields: list[str],
) -> dict[str, Any]:
    feature_summary = {
        field: _distribution(frame[field], total_count=len(frame))
        for field in feature_fields
    }
    return {
        "group_id": group_id,
        "row_count": int(len(frame)),
        "window_count": int(
            frame[["as_of_date", "horizon_days"]]
            .drop_duplicates()
            .shape[0]
            if not frame.empty
            else 0
        ),
        "positive_list_member_count": int(
            frame["_has_positive_list"].sum() if not frame.empty else 0
        ),
        "high_risk_member_count": int(
            frame["_is_high_risk"].sum() if not frame.empty else 0
        ),
        "outcomes": {
            "future_return_mean": _mean(frame.get("future_return")),
            "future_return_median": _median(frame.get("future_return")),
            "future_excess_return_mean": _mean(
                frame.get("future_excess_return")
            ),
            "future_excess_return_median": _median(
                frame.get("future_excess_return")
            ),
        },
        "features": feature_summary,
    }


def _comparison(
    comparison_id: str,
    left: dict[str, Any],
    right: dict[str, Any],
    feature_fields: list[str],
) -> dict[str, Any]:
    features = {}
    for field in feature_fields:
        left_values = left["features"][field]
        right_values = right["features"][field]
        features[field] = {
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
    return {
        "comparison_id": comparison_id,
        "left_group": left["group_id"],
        "right_group": right["group_id"],
        "left_count": left["row_count"],
        "right_count": right["row_count"],
        "features": features,
    }


def _pattern_attribution(
    comparisons: dict[str, dict[str, Any]],
    available_features: list[str],
) -> list[dict[str, Any]]:
    winner_loser = comparisons["winner_vs_loser_union"]["features"]
    captured_missed = comparisons["captured_vs_missed_winners"]["features"]
    rows = []
    for pattern_id, fields in PATTERN_FEATURES.items():
        feature_rows = []
        for field in fields:
            if field not in available_features:
                continue
            feature_rows.append(
                {
                    "feature": field,
                    "winner_vs_loser_median_delta": winner_loser[field][
                        "median_delta"
                    ],
                    "captured_vs_missed_median_delta": captured_missed[field][
                        "median_delta"
                    ],
                    "winner_vs_loser_valid_counts": [
                        winner_loser[field]["left_valid_count"],
                        winner_loser[field]["right_valid_count"],
                    ],
                    "captured_vs_missed_valid_counts": [
                        captured_missed[field]["left_valid_count"],
                        captured_missed[field]["right_valid_count"],
                    ],
                }
            )
        rows.append(
            {
                "pattern_id": pattern_id,
                "status": "descriptive_only",
                "features": feature_rows,
                "causal_interpretation_allowed": False,
            }
        )
    return rows


def _descriptive_findings(
    groups: dict[str, dict[str, Any]],
    comparisons: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    winners = groups["winner_union"]
    captured = groups["winner_union_captured_positive"]
    missed = groups["winner_union_missed_positive"]
    high_risk = groups["high_risk_active"]
    non_high_risk = groups["non_high_risk"]
    winner_loser = comparisons["winner_vs_loser_union"]["features"]
    captured_missed = comparisons["captured_vs_missed_winners"]["features"]
    winner_count = int(winners["row_count"])
    captured_count = int(captured["row_count"])
    missed_count = int(missed["row_count"])
    capture_rate = (
        captured_count / winner_count if winner_count else None
    )
    total_score_delta = _comparison_delta(
        captured_missed,
        "total_score",
    )
    pre_60d_delta = _comparison_delta(
        captured_missed,
        "pre_60d_return",
    )
    pre_5d_delta = _comparison_delta(
        winner_loser,
        "pre_5d_return",
    )
    amount_delta = _comparison_delta(
        winner_loser,
        "amount_change_20d",
    )
    volume_delta = _comparison_delta(
        winner_loser,
        "volume_change_20d",
    )
    high_risk_excess = high_risk["outcomes"][
        "future_excess_return_mean"
    ]
    non_high_risk_excess = non_high_risk["outcomes"][
        "future_excess_return_mean"
    ]
    return [
        {
            "finding_id": "winner_under_capture",
            "status": "descriptive_only",
            "text": (
                f"Existing positive lists captured {captured_count} of "
                f"{winner_count} winner-tail rows "
                f"({_fmt_percent(capture_rate)}); {missed_count} were "
                "outside those lists."
            ),
        },
        {
            "finding_id": "captured_winners_favor_established_profiles",
            "status": "descriptive_only",
            "text": (
                "Captured winners had higher median existing total score "
                f"({_fmt_signed(total_score_delta)} points) and pre-60D "
                f"return ({_fmt_signed_percent(pre_60d_delta)}) than missed "
                "winners. This describes current-list preference for more "
                "established profiles; it is not a candidate rule."
            ),
        },
        {
            "finding_id": "broad_winner_tail_not_simple_expansion",
            "status": "descriptive_only",
            "text": (
                "Winner-tail rows versus loser-tail rows had median deltas "
                f"of {_fmt_signed_percent(pre_5d_delta)} for pre-5D return, "
                f"{_fmt_signed_percent(amount_delta)} for amount change, and "
                f"{_fmt_signed_percent(volume_delta)} for volume change. "
                "The broad winner tail was therefore not explained by a "
                "single stronger pre-move expansion signature."
            ),
        },
        {
            "finding_id": "high_risk_negative_outcome_context",
            "status": "descriptive_only",
            "text": (
                "Existing high_risk_active rows had mean future excess "
                f"return {_fmt_percent(high_risk_excess)}, versus "
                f"{_fmt_percent(non_high_risk_excess)} for the disjoint "
                "non-high-risk cohort. This preserves a risk-warning "
                "diagnostic only."
            ),
        },
        {
            "finding_id": "external_causality_unavailable",
            "status": "descriptive_only",
            "text": (
                "Theme, event, fundamental, industry, and historical-status "
                "causes remain unavailable; price/volume differences cannot "
                "identify those causes."
            ),
        },
    ]


def _comparison_delta(
    features: dict[str, dict[str, Any]],
    field: str,
) -> float | None:
    return features.get(field, {}).get("median_delta")


def _feature_missingness(
    frame: pd.DataFrame,
    fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    rows = []
    for field in fields:
        if field not in frame:
            rows.append(
                {
                    "feature": field,
                    "status": "column_unavailable",
                    "valid_count": 0,
                    "missing_count": int(len(frame)),
                    "missing_rate": 1.0,
                }
            )
            continue
        valid_count = int(
            pd.to_numeric(frame[field], errors="coerce").notna().sum()
        )
        rows.append(
            {
                "feature": field,
                "status": (
                    "available"
                    if valid_count == len(frame)
                    else "partially_available"
                ),
                "valid_count": valid_count,
                "missing_count": int(len(frame) - valid_count),
                "missing_rate": (
                    (len(frame) - valid_count) / len(frame)
                    if len(frame)
                    else None
                ),
            }
        )
    return rows


def _distribution(
    series: pd.Series,
    *,
    total_count: int,
) -> dict[str, Any]:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return {
            "valid_count": 0,
            "missing_count": total_count,
            "mean": None,
            "median": None,
            "q25": None,
            "q75": None,
            "minimum": None,
            "maximum": None,
        }
    return {
        "valid_count": int(len(values)),
        "missing_count": int(total_count - len(values)),
        "mean": float(values.mean()),
        "median": float(values.median()),
        "q25": float(values.quantile(0.25)),
        "q75": float(values.quantile(0.75)),
        "minimum": float(values.min()),
        "maximum": float(values.max()),
    }


def _group_definitions() -> list[dict[str, str]]:
    return [
        {
            "group_id": "top_future_return_winners",
            "definition": "Top predeclared tail of future_return within each window.",
        },
        {
            "group_id": "top_future_excess_return_winners",
            "definition": "Top predeclared tail of future_excess_return within each window.",
        },
        {
            "group_id": "winner_union",
            "definition": "Union of the two within-window winner tails.",
        },
        {
            "group_id": "winner_union_captured_positive",
            "definition": "Winner union with at least one existing positive-list membership.",
        },
        {
            "group_id": "winner_union_missed_positive",
            "definition": "Winner union with no existing positive-list membership.",
        },
        {
            "group_id": "bottom_future_return_losers",
            "definition": "Bottom predeclared tail of future_return within each window.",
        },
        {
            "group_id": "bottom_future_excess_return_losers",
            "definition": "Bottom predeclared tail of future_excess_return within each window.",
        },
        {
            "group_id": "loser_union",
            "definition": "Union of the two within-window loser tails.",
        },
        {
            "group_id": "loser_union_captured_positive",
            "definition": "Loser union with at least one existing positive-list membership.",
        },
        {
            "group_id": "high_risk_active",
            "definition": "Rows already in the existing high_risk_active list.",
        },
        {
            "group_id": "non_high_risk",
            "definition": "Disjoint complement of high_risk_active.",
        },
    ]


def _boolean_series(series: pd.Series) -> pd.Series:
    return (
        series.fillna(False)
        .astype(str)
        .str.strip()
        .str.lower()
        .isin({"true", "1", "yes", "y"})
    )


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
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if math.isnan(number) or math.isinf(number):
        return "n/a"
    return f"{number:.2%}"


def _fmt_signed(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):+.2f}"


def _fmt_signed_percent(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if math.isnan(number) or math.isinf(number):
        return "n/a"
    return f"{number:+.2%}"


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
