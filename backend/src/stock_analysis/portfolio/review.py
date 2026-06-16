from __future__ import annotations

import pandas as pd


def generate_portfolio_review(
    portfolio_performance: list[dict[str, object]],
    holdings_by_portfolio: dict[str, list[dict[str, object]]],
) -> dict[str, object]:
    success_cases: list[dict[str, object]] = []
    failure_cases: list[dict[str, object]] = []
    risk_warning_cases: list[dict[str, object]] = []
    for performance in portfolio_performance:
        portfolio_id = str(performance.get("portfolio_id", ""))
        holdings = {str(row.get("symbol", "")): row for row in holdings_by_portfolio.get(portfolio_id, [])}
        for case in _unique_cases(performance):
            if isinstance(case, dict):
                holding = holdings.get(str(case.get("symbol", "")), {})
                if _is_success_case(case):
                    success_cases.append(_review_case(case, holding, portfolio_id, case_type="success", performance=performance))
                if _is_failure_case(case):
                    failure_cases.append(_review_case(case, holding, portfolio_id, case_type="failure", performance=performance))
                if _is_risk_warning_case(case):
                    risk_warning_cases.append(_review_case(case, holding, portfolio_id, case_type="risk_warning", performance=performance))
    return {
        "disclaimer": "This is a research-only simulated portfolio validation. It is not investment advice.",
        "success_cases": success_cases,
        "failure_cases": failure_cases,
        "risk_warning_cases": risk_warning_cases,
        "improvement_suggestions": improvement_suggestions(portfolio_performance),
    }


def improvement_suggestions(portfolio_performance: list[dict[str, object]]) -> dict[str, list[dict[str, str]]]:
    weak = [row for row in portfolio_performance if _numeric(row.get("average_excess_return")) is not None and _numeric(row.get("average_excess_return")) < 0]
    observation = [row for row in portfolio_performance if row.get("observation_only")]
    return {
        "list_rule_improvements": [
            {
                "status": "hypothesis / next experiment",
                "suggestion": "Compare top 10 versus top 20 list depth before changing list thresholds.",
            },
            {
                "status": "hypothesis / next experiment",
                "suggestion": "Keep high risk active lists as observation-only unless separate validation supports promotion.",
            },
            {
                "status": "hypothesis / next experiment",
                "suggestion": "If weak excess returns persist, test stricter drawdown and volatility filters for affected lists.",
            },
        ],
        "factor_feature_improvements": [
            {
                "status": "hypothesis / next experiment",
                "suggestion": "Add momentum deceleration features to detect fading momentum.",
            },
            {
                "status": "hypothesis / next experiment",
                "suggestion": "Add recent drawdown recovery and volatility regime features using price-only data.",
            },
        ],
        "portfolio_construction_improvements": [
            {
                "status": "hypothesis / next experiment",
                "suggestion": "Test mixed portfolio ratios against single-list baselines on larger walk-forward samples.",
            },
            {
                "status": "hypothesis / next experiment",
                "suggestion": "Add maximum drawdown filters and list concentration checks in later experiments.",
            },
        ],
        "diagnostics": [
            {"status": "hypothesis / next experiment", "suggestion": f"Portfolios with negative average excess return in this run: {len(weak)}."},
            {"status": "hypothesis / next experiment", "suggestion": f"Observation-only portfolios in this run: {len(observation)}."},
        ],
    }


def markdown_review_report(review: object) -> str:
    payload = review if isinstance(review, dict) else {}
    lines = [
        "# Phase 2.7.3 Portfolio Review",
        "",
        str(payload.get("disclaimer", "This is a research-only simulated portfolio validation. It is not investment advice.")),
        "",
        "## Success Cases",
    ]
    for case in payload.get("success_cases", [])[:10]:
        lines.append(f"- {case.get('portfolio_id')} {case.get('symbol')}: return={case.get('future_return')}, reasons={case.get('success_reason_candidates')}")
    lines.append("")
    lines.append("## Failure Cases")
    for case in payload.get("failure_cases", [])[:10]:
        lines.append(f"- {case.get('portfolio_id')} {case.get('symbol')}: return={case.get('future_return')}, reasons={case.get('failure_reason_candidates')}")
    lines.append("")
    lines.append("## Risk Warning Cases")
    for case in payload.get("risk_warning_cases", [])[:10]:
        lines.append(f"- {case.get('portfolio_id')} {case.get('symbol')}: return={case.get('future_return')}, drawdown={case.get('max_drawdown_during_holding')}, reasons={case.get('risk_warning_reason_candidates')}")
    lines.append("")
    lines.append("## Improvement Suggestions")
    for category, suggestions in payload.get("improvement_suggestions", {}).items():
        lines.append(f"### {category}")
        for item in suggestions:
            lines.append(f"- {item.get('status')}: {item.get('suggestion')}")
    return "\n".join(lines) + "\n"


def _review_case(case: dict[str, object], holding: dict[str, object], portfolio_id: str, *, case_type: str, performance: dict[str, object]) -> dict[str, object]:
    payload = {
        "symbol": case.get("symbol"),
        "name": holding.get("name", case.get("name", "")),
        "portfolio_id": portfolio_id,
        "as_of_date": performance.get("as_of_date"),
        "horizon_days": performance.get("horizon_days"),
        "future_return": case.get("future_return"),
        "benchmark_return": case.get("benchmark_return"),
        "future_excess_return": case.get("future_excess_return"),
        "outperformed_benchmark": case.get("outperformed_benchmark"),
        "max_drawdown_during_holding": case.get("max_drawdown_during_holding"),
        "entry_rank": holding.get("entry_rank", case.get("entry_rank")),
        "entry_score": holding.get("entry_score", case.get("entry_score")),
        "primary_type": holding.get("primary_type", case.get("primary_type", "")),
        "secondary_tags": holding.get("secondary_tags", case.get("secondary_tags", [])),
    }
    if case_type == "success":
        payload["success_reason_candidates"] = _success_reasons(case, holding)
    elif case_type == "failure":
        payload["failure_reason_candidates"] = _failure_reasons(case, holding)
    else:
        payload["risk_warning_reason_candidates"] = _risk_warning_reasons(case, holding)
    return payload


def _success_reasons(case: dict[str, object], holding: dict[str, object]) -> list[str]:
    reasons = []
    if _numeric(case.get("future_return")) is not None and _numeric(case.get("future_return")) > 0:
        reasons.append("trend continuation")
    if _numeric(case.get("future_excess_return")) is not None and _numeric(case.get("future_excess_return")) > 0:
        reasons.append("relative strength held")
    if _numeric(case.get("max_drawdown_during_holding")) is not None and _numeric(case.get("max_drawdown_during_holding")) > -0.1:
        reasons.append("drawdown controlled")
    if _numeric(holding.get("entry_score")) is not None and _numeric(holding.get("entry_score")) >= 80:
        reasons.append("strong entry score")
    return reasons or ["price-only positive outcome; needs larger validation"]


def _failure_reasons(case: dict[str, object], holding: dict[str, object]) -> list[str]:
    reasons = []
    if _numeric(case.get("future_return")) is not None and _numeric(case.get("future_return")) < 0:
        reasons.append("post-entry pullback")
    if _numeric(case.get("future_excess_return")) is not None and _numeric(case.get("future_excess_return")) < 0:
        reasons.append("relative strength weakened")
    if holding.get("observation_only"):
        reasons.append("risk observation list should remain separate from stable candidate portfolios")
    return reasons or ["price-only weak outcome; needs larger validation"]


def _risk_warning_reasons(case: dict[str, object], holding: dict[str, object]) -> list[str]:
    reasons = []
    if _numeric(case.get("max_drawdown_during_holding")) is not None and _numeric(case.get("max_drawdown_during_holding")) < -0.15:
        reasons.append("positive return with large drawdown")
    if holding.get("observation_only"):
        reasons.append("risk observation list should remain separate from stable candidate portfolios")
    return reasons or ["price-only risk warning; needs larger validation"]


def _unique_cases(performance: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for bucket in ["best_cases", "worst_cases"]:
        for case in performance.get(bucket, []) if isinstance(performance.get(bucket), list) else []:
            if not isinstance(case, dict):
                continue
            key = str(case.get("symbol", ""))
            if key and key not in seen:
                seen.add(key)
                rows.append(case)
    return rows


def _is_success_case(case: dict[str, object]) -> bool:
    future_return = _numeric(case.get("future_return"))
    future_excess = _numeric(case.get("future_excess_return"))
    return future_return is not None and future_return > 0 and (future_excess is None or future_excess >= 0)


def _is_failure_case(case: dict[str, object]) -> bool:
    future_return = _numeric(case.get("future_return"))
    future_excess = _numeric(case.get("future_excess_return"))
    return (future_return is not None and future_return < 0) or (future_excess is not None and future_excess < 0)


def _is_risk_warning_case(case: dict[str, object]) -> bool:
    future_return = _numeric(case.get("future_return"))
    drawdown = _numeric(case.get("max_drawdown_during_holding"))
    return future_return is not None and future_return > 0 and drawdown is not None and drawdown < -0.15


def _numeric(value: object) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
