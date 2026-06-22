from __future__ import annotations

from dataclasses import asdict, dataclass, field


FORBIDDEN_FEATURE_COLUMNS = frozenset(
    {
        "future_return",
        "future_excess_return",
        "benchmark_return",
        "outperformed_benchmark",
        "max_drawdown_during_holding",
        "data_quality",
        "best_case_return",
        "worst_case_return",
    }
)

VALIDATION_STATUS_EXPLORATORY = "exploratory_same_period"
VALIDATION_STATUS_PREREGISTERED = "pre_registered_same_period"
VALIDATION_STATUS_HOLDOUT = "holdout_validated"
VALIDATION_STATUS_INSUFFICIENT = "insufficient_data"


@dataclass(frozen=True)
class FilterCriterion:
    feature: str
    operator: str
    value: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AggressiveFilterProfile:
    experiment_id: str
    filter_id: str
    description: str
    criteria: tuple[FilterCriterion, ...] = field(default_factory=tuple)
    validation_status: str = VALIDATION_STATUS_EXPLORATORY
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def feature_columns(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(criterion.feature for criterion in self.criteria))

    def to_dict(self) -> dict[str, object]:
        return {
            "experiment_id": self.experiment_id,
            "filter_id": self.filter_id,
            "description": self.description,
            "feature_columns": list(self.feature_columns),
            "criteria": [criterion.to_dict() for criterion in self.criteria],
            "validation_status": self.validation_status,
            "notes": list(self.notes),
        }


DEFAULT_AGGRESSIVE_FILTER_PROFILES: tuple[AggressiveFilterProfile, ...] = (
    AggressiveFilterProfile(
        experiment_id="baseline_aggressive",
        filter_id="none",
        description="Unfiltered aggressive strategy-family baseline.",
        criteria=(),
        notes=("Baseline comparison row; no filter is applied.",),
    ),
    AggressiveFilterProfile(
        experiment_id="aggressive_volatility_cap",
        filter_id="volatility_cap_filter",
        description="Cap noisy volatility while keeping baseline trend candidates eligible.",
        criteria=(
            FilterCriterion("volatility", "<=", 0.06),
            FilterCriterion("risk_score", ">=", 6.0),
            FilterCriterion("total_score", ">=", 50.0),
        ),
    ),
    AggressiveFilterProfile(
        experiment_id="aggressive_drawdown_control",
        filter_id="drawdown_control_filter",
        description="Require tolerable as-of drawdown and enough trend/risk support.",
        criteria=(
            FilterCriterion("drawdown", "abs<=", 0.35),
            FilterCriterion("risk_score", ">=", 6.0),
            FilterCriterion("trend_score", ">=", 8.0),
        ),
    ),
    AggressiveFilterProfile(
        experiment_id="aggressive_momentum_quality",
        filter_id="momentum_quality_filter",
        description="Require momentum to be supported by trend, relative strength, and total score.",
        criteria=(
            FilterCriterion("momentum_score", ">=", 10.0),
            FilterCriterion("trend_score", ">=", 8.0),
            FilterCriterion("relative_strength_score", ">=", 6.0),
            FilterCriterion("total_score", ">=", 55.0),
        ),
    ),
    AggressiveFilterProfile(
        experiment_id="aggressive_liquidity_sanity",
        filter_id="liquidity_sanity_filter",
        description="Avoid thin-liquidity candidates using only as-of liquidity and activity fields.",
        criteria=(
            FilterCriterion("liquidity_score", ">=", 5.0),
            FilterCriterion("amount", ">=", 50000000.0),
            FilterCriterion("volume", ">=", 1000000.0),
        ),
    ),
    AggressiveFilterProfile(
        experiment_id="aggressive_anti_lottery",
        filter_id="anti_lottery_filter",
        description="Reduce lottery-like noise with volatility, drawdown, and optional extreme-move proxies.",
        criteria=(
            FilterCriterion("volatility", "<=", 0.08),
            FilterCriterion("drawdown", "abs<=", 0.40),
            FilterCriterion("recent_extreme_move_proxy", "<=", 0.20),
            FilterCriterion("amount_abnormality", "<=", 3.0),
        ),
        notes=("Optional proxy features may be unavailable; missing features are reported, not invented.",),
    ),
    AggressiveFilterProfile(
        experiment_id="aggressive_combined_quality",
        filter_id="combined_aggressive_quality_filter",
        description="Combine momentum/trend support with risk, volatility, and drawdown controls.",
        criteria=(
            FilterCriterion("momentum_score", ">=", 10.0),
            FilterCriterion("trend_score", ">=", 8.0),
            FilterCriterion("risk_score", ">=", 6.0),
            FilterCriterion("volatility", "<=", 0.07),
            FilterCriterion("drawdown", "abs<=", 0.35),
        ),
    ),
)


AGGRESSIVE_SOURCE_FAMILIES = ("momentum_breakout", "volatility_expansion", "right_tail_hunter")


def get_default_aggressive_filter_profiles() -> list[AggressiveFilterProfile]:
    _validate_profiles(DEFAULT_AGGRESSIVE_FILTER_PROFILES)
    return list(DEFAULT_AGGRESSIVE_FILTER_PROFILES)


def all_filter_feature_columns(profiles: tuple[AggressiveFilterProfile, ...] | list[AggressiveFilterProfile] | None = None) -> set[str]:
    selected = DEFAULT_AGGRESSIVE_FILTER_PROFILES if profiles is None else tuple(profiles)
    return {feature for profile in selected for feature in profile.feature_columns}


def _validate_profiles(profiles: tuple[AggressiveFilterProfile, ...]) -> None:
    forbidden = all_filter_feature_columns(list(profiles)) & FORBIDDEN_FEATURE_COLUMNS
    if forbidden:
        raise ValueError(f"Aggressive filter profiles cannot use future/evaluation columns: {sorted(forbidden)}")
