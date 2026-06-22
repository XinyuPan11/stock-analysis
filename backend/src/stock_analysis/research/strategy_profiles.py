from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class StrategyFamilyProfile:
    profile_id: str
    family_type: str
    objective: str
    source_list_ids: tuple[str, ...]
    primary_metrics: tuple[str, ...]
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["source_list_ids"] = list(self.source_list_ids)
        payload["primary_metrics"] = list(self.primary_metrics)
        payload["notes"] = list(self.notes)
        return payload


CONSERVATIVE_METRICS = (
    "average_excess_return",
    "outperform_rate",
    "win_rate",
    "max_drawdown_average",
    "negative_return_rate",
    "stability_score",
)

AGGRESSIVE_METRICS = (
    "hit_rate",
    "average_future_return",
    "average_excess_return",
    "outperform_rate",
    "top_decile_average_return",
    "top_5_average_return",
    "best_case_return",
    "worst_case_return",
    "payoff_ratio",
    "right_tail_ratio",
    "max_drawdown_average",
    "failure_rate_below_minus_10pct",
    "failure_rate_below_minus_20pct",
)


DEFAULT_STRATEGY_FAMILY_PROFILES: tuple[StrategyFamilyProfile, ...] = (
    StrategyFamilyProfile(
        profile_id="conservative_quality",
        family_type="conservative",
        objective="Stable excess return, high outperform rate, and controlled drawdown.",
        source_list_ids=("high_confidence_candidates", "long_term_stable"),
        primary_metrics=CONSERVATIVE_METRICS,
    ),
    StrategyFamilyProfile(
        profile_id="long_term_stable",
        family_type="conservative",
        objective="Lower volatility, lower drawdown, and persistent positive return.",
        source_list_ids=("long_term_stable",),
        primary_metrics=CONSERVATIVE_METRICS,
    ),
    StrategyFamilyProfile(
        profile_id="momentum_breakout",
        family_type="aggressive",
        objective="Capture strong trend continuation while measuring fake-breakout failure risk.",
        source_list_ids=("trend_leaders", "breakout_watch"),
        primary_metrics=AGGRESSIVE_METRICS,
        notes=("Do not evaluate this family only by average excess return.",),
    ),
    StrategyFamilyProfile(
        profile_id="volatility_expansion",
        family_type="aggressive",
        objective="Capture upside from volatility expansion while separating it from pure noisy high volatility.",
        source_list_ids=("accumulation_watch", "rebound_watch", "high_risk_active"),
        primary_metrics=AGGRESSIVE_METRICS,
        notes=("Right-tail and failure-rate metrics are required for interpretation.",),
    ),
    StrategyFamilyProfile(
        profile_id="right_tail_hunter",
        family_type="right_tail",
        objective="Accept a lower hit rate only when successful cases have much larger upside and failures are bounded.",
        source_list_ids=("breakout_watch", "accumulation_watch", "high_risk_active"),
        primary_metrics=AGGRESSIVE_METRICS,
        notes=("This is an opportunity-family experiment, not a production recommendation.",),
    ),
    StrategyFamilyProfile(
        profile_id="anti_high_risk_filter",
        family_type="risk_filter",
        objective="Identify names that should remain excluded or observation-only in research workflows.",
        source_list_ids=("high_risk_active",),
        primary_metrics=(
            "average_future_return",
            "average_excess_return",
            "outperform_rate",
            "max_drawdown_average",
            "failure_rate_below_minus_10pct",
            "failure_rate_below_minus_20pct",
            "worst_case_return",
        ),
        notes=("Observation-only risk filter; not a selection model.",),
    ),
)


def get_default_strategy_family_profiles() -> list[StrategyFamilyProfile]:
    return list(DEFAULT_STRATEGY_FAMILY_PROFILES)

