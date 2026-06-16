from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from stock_analysis.portfolio.experiments import create_default_experiments
from stock_analysis.portfolio.performance import evaluate_portfolios
from stock_analysis.portfolio.portfolio_rules import PortfolioRule, allocation_counts, get_default_portfolio_rules
from stock_analysis.portfolio.review import generate_portfolio_review, markdown_review_report
from stock_analysis.validation.walk_forward import sanitize_for_json


RESEARCH_ONLY_DISCLAIMER = "This is a research-only simulated portfolio validation. It is not investment advice."


@dataclass(frozen=True)
class PortfolioValidationConfig:
    as_of_date: str
    horizon_days: int = 60
    benchmark: str = "CSI300"
    outputs_dir: str | Path = "outputs"
    cache_dir: str | Path = "data/cache/daily-use"
    portfolio_ids: tuple[str, ...] = ()
    limit: int | None = 50
    transaction_cost_bps: float = 10.0
    dry_run: bool = True


def run_portfolio_validation(config: PortfolioValidationConfig) -> dict[str, object]:
    """Run research-only simulated portfolio validation from static outputs.

    No future leakage: portfolio membership is built only from as-of list
    outputs. Future return labels are loaded afterward for validation only.
    """

    outputs_dir = Path(config.outputs_dir)
    rules = _selected_rules(config.portfolio_ids)
    list_payloads = load_list_payloads(outputs_dir, config.as_of_date, rules)
    holdings_by_portfolio = {
        rule.portfolio_id: build_portfolio_holdings(rule, list_payloads)
        for rule in rules
    }
    future_labels = load_future_labels(outputs_dir, config.as_of_date, config.horizon_days, limit=config.limit)
    performance = evaluate_portfolios(
        holdings_by_portfolio,
        future_labels,
        rules=rules,
        as_of_date=config.as_of_date,
        horizon_days=config.horizon_days,
        transaction_cost_bps=config.transaction_cost_bps,
    )
    review = generate_portfolio_review(performance, holdings_by_portfolio)
    experiments = create_default_experiments(config.as_of_date, config.horizon_days)
    summary = {
        "status": "dry_run" if config.dry_run else "ok",
        "as_of_date": config.as_of_date,
        "horizon_days": config.horizon_days,
        "benchmark": config.benchmark,
        "dry_run": config.dry_run,
        "no_future_leakage": True,
        "research_only": True,
        "disclaimer": RESEARCH_ONLY_DISCLAIMER,
        "portfolio_count": len(performance),
        "future_label_count": int(len(future_labels)),
        "transaction_cost_bps": config.transaction_cost_bps,
    }
    result: dict[str, object] = {
        "summary": summary,
        "portfolio_performance": performance,
        "holdings": _flatten_holdings(holdings_by_portfolio),
        "review": review,
        "experiments": experiments,
        "outputs": {},
    }
    if not config.dry_run:
        result["outputs"] = write_portfolio_outputs(config, result)
    return result


def build_portfolio_holdings(rule: PortfolioRule, list_payloads: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    if rule.allocations:
        rows: list[dict[str, object]] = []
        seen: set[str] = set()
        for list_id, count in allocation_counts(rule).items():
            for item in _items(list_payloads.get(list_id, {}))[:count]:
                symbol = str(item.get("symbol", ""))
                if not symbol or symbol in seen:
                    continue
                seen.add(symbol)
                rows.append(_holding_row(rule, item, source_list_id=list_id))
        return _with_equal_weights(rows)

    source = rule.source_list_id or ""
    rows = [
        _holding_row(rule, item, source_list_id=source)
        for item in _items(list_payloads.get(source, {}))[: rule.top_n]
        if item.get("symbol")
    ]
    return _with_equal_weights(rows)


def load_list_payloads(outputs_dir: Path, as_of_date: str, rules: Iterable[PortfolioRule]) -> dict[str, dict[str, object]]:
    list_ids = {
        rule.source_list_id
        for rule in rules
        if rule.source_list_id
    }
    for rule in rules:
        list_ids.update(allocation.list_id for allocation in rule.allocations)
    payloads: dict[str, dict[str, object]] = {}
    for list_id in sorted(list_ids):
        path = outputs_dir / "lists" / f"{list_id}_{as_of_date}.json"
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            payloads[list_id] = payload if isinstance(payload, dict) else {"list_id": list_id, "items": []}
        else:
            payloads[list_id] = {"list_id": list_id, "as_of_date": as_of_date, "items": [], "notes": ["missing_list_file"]}
    return payloads


def load_future_labels(outputs_dir: Path, as_of_date: str, horizon_days: int, *, limit: int | None) -> pd.DataFrame:
    path = outputs_dir / "validation" / f"walk_forward_predictions_{as_of_date}_{horizon_days}d.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, dtype={"symbol": str, "as_of_date": str})
    if limit is not None and limit > 0:
        return frame.head(limit).copy()
    return frame


def write_portfolio_outputs(config: PortfolioValidationConfig, result: dict[str, object]) -> dict[str, str]:
    outputs_dir = Path(config.outputs_dir)
    portfolio_dir = outputs_dir / "portfolios"
    review_dir = outputs_dir / "reviews"
    experiment_dir = outputs_dir / "experiments"
    portfolio_dir.mkdir(parents=True, exist_ok=True)
    review_dir.mkdir(parents=True, exist_ok=True)
    experiment_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"{config.as_of_date}_{config.horizon_days}d"
    paths = {
        "portfolio_summary": portfolio_dir / f"portfolio_summary_{suffix}.json",
        "portfolio_holdings": portfolio_dir / f"portfolio_holdings_{suffix}.csv",
        "portfolio_report": portfolio_dir / f"portfolio_report_{suffix}.md",
        "portfolio_review_json": review_dir / f"portfolio_review_{suffix}.json",
        "portfolio_review_md": review_dir / f"portfolio_review_{suffix}.md",
        "strategy_experiments": experiment_dir / f"strategy_experiments_{suffix}.json",
    }
    _write_json(paths["portfolio_summary"], {"summary": result["summary"], "portfolios": result["portfolio_performance"]})
    pd.DataFrame(sanitize_for_json(result["holdings"])).to_csv(paths["portfolio_holdings"], index=False, encoding="utf-8")
    paths["portfolio_report"].write_text(markdown_portfolio_report(result), encoding="utf-8")
    _write_json(paths["portfolio_review_json"], result["review"])
    paths["portfolio_review_md"].write_text(markdown_review_report(result["review"]), encoding="utf-8")
    _write_json(paths["strategy_experiments"], result["experiments"])
    return {key: str(path) for key, path in paths.items()}


def markdown_portfolio_report(result: dict[str, object]) -> str:
    summary = result.get("summary", {})
    lines = [
        "# Phase 2.7.3 Simulated Portfolio Validation Report",
        "",
        RESEARCH_ONLY_DISCLAIMER,
        "",
        "No future leakage: holdings are built from fixed as-of list outputs; future labels are used only for after-the-fact validation.",
        "",
        f"- Status: {summary.get('status')}",
        f"- As-of date: {summary.get('as_of_date')}",
        f"- Horizon days: {summary.get('horizon_days')}",
        f"- Portfolio count: {summary.get('portfolio_count')}",
        f"- Transaction cost bps: {summary.get('transaction_cost_bps')}",
        "",
        "## Portfolio Metrics",
    ]
    for row in result.get("portfolio_performance", []):
        lines.append(f"- {row.get('portfolio_id')}: valid={row.get('valid_future_count')}, average={row.get('average_future_return')}, net={row.get('net_average_return')}")
    return "\n".join(lines) + "\n"


def _selected_rules(portfolio_ids: tuple[str, ...]) -> tuple[PortfolioRule, ...]:
    rules = get_default_portfolio_rules()
    if not portfolio_ids:
        return rules
    wanted = {item for item in portfolio_ids if item}
    return tuple(rule for rule in rules if rule.portfolio_id in wanted)


def _items(payload: dict[str, object]) -> list[dict[str, object]]:
    value = payload.get("items", [])
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _holding_row(rule: PortfolioRule, item: dict[str, object], *, source_list_id: str) -> dict[str, object]:
    return {
        "portfolio_id": rule.portfolio_id,
        "source_list_id": source_list_id,
        "symbol": item.get("symbol", ""),
        "name": item.get("name", ""),
        "entry_rank": item.get("rank", item.get("list_rank")),
        "entry_score": item.get("total_score"),
        "primary_type": item.get("primary_type", ""),
        "secondary_tags": item.get("secondary_tags", []),
        "research_action": item.get("research_action", ""),
        "confidence_level": item.get("confidence_level", ""),
        "risk_level": item.get("risk_level", ""),
        "observation_only": rule.observation_only,
        "portfolio_weight": 0.0,
    }


def _with_equal_weights(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    if not rows:
        return rows
    weight = 1.0 / len(rows)
    for row in rows:
        row["portfolio_weight"] = weight
    return rows


def _flatten_holdings(holdings_by_portfolio: dict[str, list[dict[str, object]]]) -> list[dict[str, object]]:
    return [row for rows in holdings_by_portfolio.values() for row in rows]


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(sanitize_for_json(payload), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

