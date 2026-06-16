from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ListAllocation:
    list_id: str
    weight: float


@dataclass(frozen=True)
class PortfolioRule:
    portfolio_id: str
    source_list_id: str | None = None
    top_n: int = 10
    allocations: tuple[ListAllocation, ...] = field(default_factory=tuple)
    observation_only: bool = False
    description: str = ""


DEFAULT_PORTFOLIO_RULES: tuple[PortfolioRule, ...] = (
    PortfolioRule("high_confidence_top10", source_list_id="high_confidence_candidates", top_n=10, description="High confidence candidate list, top 10, equal weight."),
    PortfolioRule("high_confidence_top20", source_list_id="high_confidence_candidates", top_n=20, description="High confidence candidate list, top 20, equal weight."),
    PortfolioRule("trend_leaders_top10", source_list_id="trend_leaders", top_n=10, description="Trend leaders list, top 10, equal weight."),
    PortfolioRule("accumulation_watch_top10", source_list_id="accumulation_watch", top_n=10, description="Accumulation watch list, top 10, equal weight."),
    PortfolioRule("long_term_stable_top10", source_list_id="long_term_stable", top_n=10, description="Long-term stable list, top 10, equal weight."),
    PortfolioRule("breakout_watch_top10", source_list_id="breakout_watch", top_n=10, description="Breakout watch list, top 10, equal weight."),
    PortfolioRule(
        "mixed_baseline",
        top_n=10,
        allocations=(
            ListAllocation("trend_leaders", 0.4),
            ListAllocation("accumulation_watch", 0.3),
            ListAllocation("long_term_stable", 0.3),
        ),
        description="Mixed research baseline: trend leaders 40%, accumulation watch 30%, long-term stable 30%.",
    ),
    PortfolioRule(
        "high_risk_active_observation",
        source_list_id="high_risk_active",
        top_n=10,
        observation_only=True,
        description="Risk observation only; not a stable candidate portfolio.",
    ),
)


def get_default_portfolio_rules() -> tuple[PortfolioRule, ...]:
    return DEFAULT_PORTFOLIO_RULES


def select_portfolio_rules(portfolio_ids: tuple[str, ...] | list[str] | None = None) -> tuple[PortfolioRule, ...]:
    rules = get_default_portfolio_rules()
    if not portfolio_ids:
        return rules
    wanted = {str(item).strip() for item in portfolio_ids if str(item).strip()}
    return tuple(rule for rule in rules if rule.portfolio_id in wanted)


def allocation_counts(rule: PortfolioRule) -> dict[str, int]:
    if not rule.allocations:
        return {}
    counts: dict[str, int] = {}
    remaining = rule.top_n
    for index, allocation in enumerate(rule.allocations):
        if index == len(rule.allocations) - 1:
            count = remaining
        else:
            count = int(round(rule.top_n * allocation.weight))
            remaining -= count
        counts[allocation.list_id] = max(count, 0)
    return counts

