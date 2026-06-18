from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from stock_analysis.portfolio.experiments import create_default_experiments
from stock_analysis.portfolio.performance import evaluate_portfolios
from stock_analysis.portfolio.portfolio_rules import PortfolioRule, allocation_counts, get_default_portfolio_rules
from stock_analysis.portfolio.review import generate_portfolio_review, markdown_review_report
from stock_analysis.validation.future_returns import benchmark_aliases, calculate_future_return_label, calculate_future_return_labels, load_cached_price_history
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
    required_symbols = _required_symbols(holdings_by_portfolio)
    if config.limit is not None and config.limit > 0:
        required_symbols = required_symbols[: config.limit]
    future_labels = load_future_labels_for_symbols(
        outputs_dir,
        config.as_of_date,
        config.horizon_days,
        required_symbols=required_symbols,
        cache_dir=Path(config.cache_dir),
        benchmark=config.benchmark,
    )
    benchmark_data_quality = str(future_labels.attrs.get("benchmark_data_quality", "benchmark_missing"))
    benchmark_symbol = str(future_labels.attrs.get("benchmark_symbol", config.benchmark))
    benchmark_aliases_tried = list(future_labels.attrs.get("benchmark_aliases_tried", _portfolio_benchmark_aliases(config.benchmark)))
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
        "benchmark_symbol": benchmark_symbol,
        "benchmark_data_quality": benchmark_data_quality,
        "benchmark_aliases_tried": benchmark_aliases_tried,
        "dry_run": config.dry_run,
        "no_future_leakage": True,
        "research_only": True,
        "disclaimer": RESEARCH_ONLY_DISCLAIMER,
        "portfolio_count": len(performance),
        "future_label_count": int(len(future_labels)),
        "required_symbol_count": len(required_symbols),
        "missing_future_label_symbols": _missing_label_symbols(required_symbols, future_labels),
        "non_ok_future_label_symbols": _non_ok_label_symbols(required_symbols, future_labels),
        "transaction_cost_bps": config.transaction_cost_bps,
        "smoke_note": f"This limit-{config.limit} smoke validates the framework only. It is not evidence of model effectiveness." if config.limit else "",
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
    frame = pd.read_csv(path, dtype={"symbol": str, "as_of_date": str}, encoding="utf-8")
    if limit is not None and limit > 0:
        return frame.head(limit).copy()
    return frame


def load_future_labels_for_symbols(
    outputs_dir: Path,
    as_of_date: str,
    horizon_days: int,
    *,
    required_symbols: list[str],
    cache_dir: Path,
    benchmark: str,
) -> pd.DataFrame:
    """Load or compute future labels for the exact portfolio holdings.

    This function is cache-only. It never calls BaoStock or any provider. Static
    walk-forward predictions are reused first; missing holding symbols are then
    calculated from local cached price files when available.
    """

    if not required_symbols:
        return pd.DataFrame()
    predictions = _filter_and_order_labels(load_future_labels(outputs_dir, as_of_date, horizon_days, limit=None), required_symbols)
    missing = _symbols_needing_cache_refresh(required_symbols, predictions)
    computed = pd.DataFrame()
    if missing:
        benchmark_history, benchmark_symbol, benchmark_quality = _load_benchmark_history_for_horizon(
            cache_dir,
            benchmark=benchmark,
            as_of_date=as_of_date,
            horizon_days=horizon_days,
        )
        price_histories = {symbol: load_cached_price_history(cache_dir, provider="baostock", symbol=symbol) for symbol in missing}
        computed = pd.DataFrame(
            calculate_future_return_labels(
                missing,
                price_histories,
                as_of_date=as_of_date,
                horizon_days=horizon_days,
                benchmark_history=benchmark_history,
            )
        )
        if not computed.empty and not predictions.empty and "symbol" in computed.columns:
            existing_symbols = set(predictions["symbol"].dropna().astype(str))
            computed = computed[
                (~computed["symbol"].astype(str).isin(existing_symbols))
                | (computed.get("data_quality", "") == "ok")
            ].copy()
    combined = pd.concat([predictions, computed], ignore_index=True) if not computed.empty else predictions
    result = _filter_and_order_labels(combined, required_symbols)
    if "benchmark_quality" not in locals():
        benchmark_history, benchmark_symbol, benchmark_quality = _load_benchmark_history_for_horizon(
            cache_dir,
            benchmark=benchmark,
            as_of_date=as_of_date,
            horizon_days=horizon_days,
        )
    result.attrs["benchmark_symbol"] = benchmark_symbol
    result.attrs["benchmark_data_quality"] = benchmark_quality if benchmark_quality != "ok" else _benchmark_quality_from_labels(result, fallback=benchmark_quality)
    result.attrs["benchmark_aliases_tried"] = _portfolio_benchmark_aliases(benchmark)
    return result


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
        "portfolio_cache_plan": portfolio_dir / f"portfolio_cache_plan_{suffix}_limit{config.limit or 'all'}.txt",
        "portfolio_cache_plan_md": portfolio_dir / f"portfolio_cache_plan_{suffix}_limit{config.limit or 'all'}.md",
        "benchmark_cache_plan": portfolio_dir / f"benchmark_cache_plan_{suffix}.txt",
        "benchmark_cache_plan_md": portfolio_dir / f"benchmark_cache_plan_{suffix}.md",
        "portfolio_review_json": review_dir / f"portfolio_review_{suffix}.json",
        "portfolio_review_md": review_dir / f"portfolio_review_{suffix}.md",
        "strategy_experiments": experiment_dir / f"strategy_experiments_{suffix}.json",
    }
    _write_json(paths["portfolio_summary"], {"summary": result["summary"], "portfolios": result["portfolio_performance"]})
    pd.DataFrame(sanitize_for_json(result["holdings"])).to_csv(paths["portfolio_holdings"], index=False, encoding="utf-8")
    paths["portfolio_report"].write_text(markdown_portfolio_report(result), encoding="utf-8")
    paths["portfolio_cache_plan"].write_text(_symbol_plan_text(_portfolio_cache_plan_symbols(result)), encoding="utf-8")
    paths["portfolio_cache_plan_md"].write_text(_cache_plan_markdown(result), encoding="utf-8")
    paths["benchmark_cache_plan"].write_text(_symbol_plan_text(_benchmark_cache_plan_symbols(result)), encoding="utf-8")
    paths["benchmark_cache_plan_md"].write_text(_benchmark_cache_plan_markdown(result), encoding="utf-8")
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
        f"- Benchmark data quality: {summary.get('benchmark_data_quality')}",
        f"- Portfolio count: {summary.get('portfolio_count')}",
        f"- Transaction cost bps: {summary.get('transaction_cost_bps')}",
        f"- Required symbols: {summary.get('required_symbol_count')}",
        f"- Missing future labels: {len(summary.get('missing_future_label_symbols') or [])}",
        f"- Non-ok future labels: {len(summary.get('non_ok_future_label_symbols') or [])}",
        "",
    ]
    if summary.get("smoke_note"):
        lines.extend([str(summary["smoke_note"]), ""])
    lines.append("## Portfolio Metrics")
    for row in result.get("portfolio_performance", []):
        lines.append(
            f"- {row.get('portfolio_id')}: valid={row.get('valid_future_count')}/{row.get('holding_count')}, "
            f"average={row.get('average_future_return')}, excess={row.get('average_excess_return')}, "
            f"net={row.get('net_average_return')}, notes={row.get('notes')}"
        )
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


def _required_symbols(holdings_by_portfolio: dict[str, list[dict[str, object]]]) -> list[str]:
    symbols: list[str] = []
    seen: set[str] = set()
    for rows in holdings_by_portfolio.values():
        for row in rows:
            symbol = str(row.get("symbol", ""))
            if symbol and symbol not in seen:
                seen.add(symbol)
                symbols.append(symbol)
    return symbols


def _filter_and_order_labels(frame: pd.DataFrame, required_symbols: list[str]) -> pd.DataFrame:
    if frame.empty or "symbol" not in frame.columns:
        return pd.DataFrame()
    order = {symbol: index for index, symbol in enumerate(required_symbols)}
    result = frame.copy()
    result["symbol"] = result["symbol"].astype(str)
    result = result[result["symbol"].isin(order)].drop_duplicates("symbol", keep="last")
    result["portfolio_symbol_order"] = result["symbol"].map(order)
    return result.sort_values("portfolio_symbol_order").drop(columns=["portfolio_symbol_order"]).reset_index(drop=True)


def _missing_label_symbols(required_symbols: list[str], labels: pd.DataFrame) -> list[str]:
    if labels.empty or "symbol" not in labels.columns:
        return required_symbols
    covered = set(labels["symbol"].dropna().astype(str))
    return [symbol for symbol in required_symbols if symbol not in covered]


def _non_ok_label_symbols(required_symbols: list[str], labels: pd.DataFrame) -> list[str]:
    if labels.empty or "symbol" not in labels.columns or "data_quality" not in labels.columns:
        return required_symbols
    indexed = labels.drop_duplicates("symbol", keep="last").set_index("symbol")
    symbols: list[str] = []
    for symbol in required_symbols:
        if symbol not in indexed.index:
            symbols.append(symbol)
            continue
        if indexed.loc[symbol].get("data_quality") != "ok":
            symbols.append(symbol)
    return symbols


def _symbols_needing_cache_refresh(required_symbols: list[str], labels: pd.DataFrame) -> list[str]:
    if labels.empty or "symbol" not in labels.columns:
        return required_symbols
    indexed = labels.drop_duplicates("symbol", keep="last").set_index("symbol")
    symbols: list[str] = []
    for symbol in required_symbols:
        if symbol not in indexed.index:
            symbols.append(symbol)
            continue
        row = indexed.loc[symbol]
        if row.get("data_quality") != "ok":
            symbols.append(symbol)
            continue
        if "future_excess_return" in row.index and pd.isna(row.get("future_excess_return")):
            symbols.append(symbol)
    return symbols


def _load_benchmark_history_for_horizon(cache_dir: Path, *, benchmark: str, as_of_date: str, horizon_days: int) -> tuple[pd.DataFrame, str, str]:
    aliases = _portfolio_benchmark_aliases(benchmark)
    fallback = pd.DataFrame()
    fallback_symbol = _benchmark_cache_plan_symbol(benchmark)
    fallback_quality = "benchmark_missing"
    frames_by_alias: dict[str, list[pd.DataFrame]] = {alias: [] for alias in aliases}
    for alias in aliases:
        for dataset, adjusted in [("index_daily", False), ("stock_daily", True)]:
            frame = load_cached_price_history(cache_dir, provider="baostock", symbol=alias, dataset=dataset, adjusted=adjusted)
            if frame.empty:
                continue
            frames_by_alias[alias].append(frame)
            if fallback.empty:
                fallback = frame
                fallback_symbol = alias
            label = calculate_future_return_label(
                alias,
                frame,
                as_of_date=as_of_date,
                horizon_days=horizon_days,
                benchmark_history=None,
            )
            if label.get("data_quality") == "ok":
                return frame, alias, "ok"
            fallback_quality = f"benchmark_{label.get('data_quality', 'missing_price')}"
    stitched = _stitch_price_frames([frame for frames in frames_by_alias.values() for frame in frames])
    if not stitched.empty:
        stitched_symbol = _resolved_stitched_benchmark_symbol(frames_by_alias, benchmark)
        label = calculate_future_return_label(
            stitched_symbol,
            stitched,
            as_of_date=as_of_date,
            horizon_days=horizon_days,
            benchmark_history=None,
        )
        if label.get("data_quality") == "ok":
            return stitched, stitched_symbol, "ok"
        fallback = stitched
        fallback_symbol = stitched_symbol
        fallback_quality = f"benchmark_{label.get('data_quality', 'missing_price')}"
    return fallback, fallback_symbol, fallback_quality


def _portfolio_benchmark_aliases(benchmark: str) -> list[str]:
    result: list[str] = []
    for alias in [str(benchmark or "").strip(), *benchmark_aliases(benchmark)]:
        if alias and alias not in result:
            result.append(alias)
    return result


def _stitch_price_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    valid = [frame for frame in frames if frame is not None and not frame.empty]
    if not valid:
        return pd.DataFrame()
    combined = pd.concat(valid, ignore_index=True)
    if "trade_date" not in combined.columns:
        return pd.DataFrame()
    return combined.sort_values("trade_date").drop_duplicates("trade_date", keep="last").reset_index(drop=True)


def _resolved_stitched_benchmark_symbol(frames_by_alias: dict[str, list[pd.DataFrame]], benchmark: str) -> str:
    for alias in benchmark_aliases(benchmark):
        if frames_by_alias.get(alias):
            return alias
    for alias, frames in frames_by_alias.items():
        if frames:
            return alias
    return _benchmark_cache_plan_symbol(benchmark)


def _benchmark_quality_from_labels(labels: pd.DataFrame, *, fallback: str) -> str:
    if labels.empty or "benchmark_data_quality" not in labels.columns:
        return fallback
    qualities = [str(item) for item in labels["benchmark_data_quality"].dropna().tolist() if str(item)]
    if any(item == "ok" for item in qualities):
        return "ok"
    return qualities[0] if qualities else fallback


def _portfolio_cache_plan_symbols(result: dict[str, object]) -> list[str]:
    summary = result.get("summary", {})
    missing = summary.get("missing_future_label_symbols") or []
    non_ok = summary.get("non_ok_future_label_symbols") or []
    return _valid_symbol_lines([*missing, *non_ok])


def _benchmark_cache_plan_symbols(result: dict[str, object]) -> list[str]:
    summary = result.get("summary", {})
    benchmark_quality = str(summary.get("benchmark_data_quality") or "benchmark_missing")
    if benchmark_quality == "ok":
        return []
    return _valid_symbol_lines([_benchmark_cache_plan_symbol(str(summary.get("benchmark") or "CSI300"))])


def _symbol_plan_text(symbols: list[str]) -> str:
    return "\n".join(symbols) + ("\n" if symbols else "")


def _cache_plan_markdown(result: dict[str, object]) -> str:
    summary = result.get("summary", {})
    missing = summary.get("missing_future_label_symbols") or []
    benchmark_quality = str(summary.get("benchmark_data_quality") or "benchmark_missing")
    non_ok = _portfolio_cache_plan_symbols(result)
    lines = [
        "# Portfolio Future Label Coverage Plan",
        "",
        "The companion .txt file contains only executable stock symbols for cache prewarm.",
        "Do not use future labels to generate as-of portfolios. No future leakage.",
        "",
        f"As-of date: {summary.get('as_of_date')}",
        f"Horizon days: {summary.get('horizon_days')}",
        f"Benchmark: {summary.get('benchmark')}",
        f"Benchmark data quality: {benchmark_quality}",
        f"Required symbols: {summary.get('required_symbol_count')}",
        f"Missing future labels: {len(missing)}",
        f"Non-ok future labels: {len(non_ok)}",
        f"Benchmark aliases tried: {summary.get('benchmark_aliases_tried')}",
        "",
    ]
    if missing:
        lines.extend(["## Missing future labels", ""])
        lines.extend(str(symbol) for symbol in missing)
        lines.append("")
    if non_ok:
        lines.extend(["## Non-ok future labels", ""])
        lines.extend(non_ok)
        lines.append("")
    if benchmark_quality != "ok":
        lines.extend(
            [
                "## Benchmark future window",
                "",
                f"Benchmark data quality is {benchmark_quality}. Prepare/refresh the benchmark future-window cache before interpreting excess-return metrics.",
            ]
        )
    return "\n".join(lines) + "\n"


def _benchmark_cache_plan_markdown(result: dict[str, object]) -> str:
    summary = result.get("summary", {})
    symbols = _benchmark_cache_plan_symbols(result)
    lines = [
        "# Benchmark Future Window Cache Plan",
        "",
        "The companion .txt file contains only executable benchmark symbols for cache prewarm.",
        "",
        f"Benchmark input: {summary.get('benchmark')}",
        f"Benchmark symbol: {summary.get('benchmark_symbol')}",
        f"Benchmark data quality: {summary.get('benchmark_data_quality')}",
        f"Benchmark aliases tried: {summary.get('benchmark_aliases_tried')}",
        "",
        "## Symbols",
        "",
    ]
    lines.extend(symbols or ["No benchmark cache prep needed."])
    return "\n".join(lines) + "\n"


def _benchmark_cache_plan_symbol(benchmark: str) -> str:
    for alias in benchmark_aliases(benchmark):
        if _is_valid_symbol_line(alias):
            return alias
    value = str(benchmark or "").strip()
    return value if _is_valid_symbol_line(value) else benchmark_aliases(benchmark)[0]


def _valid_symbol_lines(symbols: Iterable[str]) -> list[str]:
    result: list[str] = []
    for symbol in symbols:
        value = str(symbol or "").strip()
        if value and value not in result and _is_valid_symbol_line(value):
            result.append(value)
    return result


def _is_valid_symbol_line(value: str) -> bool:
    return bool(re.fullmatch(r"(sh|sz)\.\d{6}", str(value or "").strip()))


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(sanitize_for_json(payload), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
