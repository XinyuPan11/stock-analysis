from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class StrategyExperiment:
    config_id: str
    created_at: str
    change_summary: str
    portfolio_rules: dict[str, object]
    list_weights: dict[str, float] = field(default_factory=dict)
    factor_weight_notes: str = ""
    risk_constraints: list[str] = field(default_factory=list)
    expected_effect: str = ""
    validation_result: str = "not_run"
    accepted_or_rejected: str = "pending"


def create_default_experiments(as_of_date: str, horizon_days: int) -> list[dict[str, object]]:
    experiments = [
        StrategyExperiment(
            config_id="baseline_strategy",
            created_at=as_of_date,
            change_summary="Current equal-weight simulated portfolio baselines.",
            portfolio_rules={"horizon_days": horizon_days, "weighting": "equal_weight"},
            expected_effect="Baseline for comparison only.",
        ),
        StrategyExperiment(
            config_id="experiment_v1",
            created_at=as_of_date,
            change_summary="Test stricter drawdown and volatility filters.",
            portfolio_rules={"candidate_filter": "price_only_risk_filter"},
            risk_constraints=["maximum drawdown filter", "volatility regime filter"],
            expected_effect="Reduce weak cases driven by large drawdowns.",
        ),
        StrategyExperiment(
            config_id="experiment_v2",
            created_at=as_of_date,
            change_summary="Test alternative mixed list allocation.",
            portfolio_rules={"mixed_baseline": "trend 50%, accumulation 25%, stable 25%"},
            list_weights={"trend_leaders": 0.5, "accumulation_watch": 0.25, "long_term_stable": 0.25},
            expected_effect="Compare list blend sensitivity.",
        ),
        StrategyExperiment(
            config_id="experiment_v3",
            created_at=as_of_date,
            change_summary="Add list membership stability feature in future validation.",
            portfolio_rules={"feature": "list_membership_stability"},
            factor_weight_notes="Hypothesis only; no factor weights changed in Phase 2.7.3.",
            expected_effect="Prefer names that persist across multiple as-of dates once multi-date data exists.",
        ),
    ]
    return [asdict(item) for item in experiments]

