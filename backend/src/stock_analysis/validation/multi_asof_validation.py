from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd

from stock_analysis.validation.cache_plan import recommended_target_end_date
from stock_analysis.validation.walk_forward import sanitize_for_json


MULTI_ASOF_YEAR = 2024
DEFAULT_AS_OF_DATES: tuple[str, ...] = ("2024-01-31", "2024-04-30", "2024-07-31", "2024-10-31")
DEFAULT_HORIZONS: tuple[int, ...] = (20, 60, 120)
DEFAULT_FOCUS_FILTERS: tuple[str, ...] = (
    "volatility_cap_filter",
    "drawdown_control_filter",
    "combined_aggressive_quality_filter",
)
DEFAULT_CACHE_DIR = "data\\cache\\daily-use"
DISCLAIMER = "Research-only multi-as-of validation planning. This does not run provider access, prewarm, full workflow, or production scoring changes."


@dataclass(frozen=True)
class MultiAsOfValidationConfig:
    outputs_dir: str | Path = "outputs"
    cache_dir: str | Path = DEFAULT_CACHE_DIR
    provider: str = "baostock"
    benchmark: str = "CSI300"
    as_of_dates: tuple[str, ...] = DEFAULT_AS_OF_DATES
    horizons: tuple[int, ...] = DEFAULT_HORIZONS
    focus_filters: tuple[str, ...] = DEFAULT_FOCUS_FILTERS
    recommended_limit: int = 50


def build_multi_asof_validation_plan(config: MultiAsOfValidationConfig) -> dict[str, object]:
    outputs_dir = Path(config.outputs_dir)
    cache_dir = Path(config.cache_dir)
    as_of_entries = []
    cache_requirements = []
    for as_of_date in config.as_of_dates:
        entries = []
        as_of_outputs = _as_of_required_outputs(outputs_dir, as_of_date)
        missing_as_of_outputs = _missing_as_of_outputs(as_of_outputs)
        for horizon in config.horizons:
            window = future_window_for(as_of_date, horizon)
            crosses_year_boundary = window["end_date"] > f"{MULTI_ASOF_YEAR}-12-31"
            status = _output_status(outputs_dir, as_of_date, horizon)
            cache_status = _cache_requirement(
                cache_dir,
                config.provider,
                outputs_dir,
                as_of_date,
                horizon,
                window,
                config.recommended_limit,
                missing_as_of_outputs,
            )
            entries.append(
                {
                    "horizon_days": horizon,
                    "future_window": window,
                    "crosses_2025_boundary": crosses_year_boundary,
                    "deferred_until_2025_allowed": crosses_year_boundary,
                    "missing_as_of_outputs": missing_as_of_outputs,
                    "required_outputs": status["required_outputs"],
                    "existing_outputs": status["existing_outputs"],
                    "missing_outputs": status["missing_outputs"],
                    "ready_for_comparison": (not status["missing_outputs"]) and (not missing_as_of_outputs) and not crosses_year_boundary,
                    "cache_requirement_id": cache_status["cache_requirement_id"],
                    "manual_validation_commands": _manual_validation_commands(config, as_of_date, horizon, crosses_year_boundary, missing_as_of_outputs),
                }
            )
            cache_requirements.append(cache_status)
        as_of_entries.append(
            {
                "as_of_date": as_of_date,
                "feature_data_rule": "Use only features, lists, filters, and dynamic states available on or before this as-of date.",
                "horizons": entries,
                "required_as_of_outputs": as_of_outputs,
            }
        )
    return {
        "status": "plan_only",
        "year": MULTI_ASOF_YEAR,
        "provider_access": False,
        "prewarm_executed": False,
        "full_workflow_executed": False,
        "production_scoring_changed": False,
        "no_future_leakage": True,
        "disclaimer": DISCLAIMER,
        "as_of_dates": list(config.as_of_dates),
        "horizons": list(config.horizons),
        "focus_filters": list(config.focus_filters),
        "as_of_plan": as_of_entries,
        "cache_requirements": cache_requirements,
        "comparison_metrics": [
            "right_tail_preservation_ratio",
            "left_tail_reduction_ratio",
            "payoff_ratio",
            "right_tail_ratio",
            "failure_rate_below_minus_10pct",
            "failure_rate_below_minus_20pct",
        ],
        "dynamic_state_history_plan": {
            "states": ["eligible", "watch_only", "blocked_now", "cooldown", "re_entry_candidate"],
            "history_required": True,
            "notes": [
                "Current Phase 2.8.3 states are single-as-of snapshots.",
                "cooldown and re_entry_candidate require previous as-of state history before full add/reduce/exit logic.",
            ],
        },
        "notes": [
            "Codex must not run BaoStock, prewarm, full workflow, full-market validation, or long data jobs in this phase.",
            "Future returns, future drawdowns, and benchmark outcomes are labels/evaluation only.",
            "Do not tune filters on one as-of date and report the same date as validated.",
            "Windows that require 2025 future data are listed but deferred; no 2025 commands are generated in this phase.",
        ],
    }


def write_multi_asof_outputs(plan: dict[str, object], outputs_dir: str | Path) -> dict[str, str]:
    experiments_dir = Path(outputs_dir) / "experiments"
    experiments_dir.mkdir(parents=True, exist_ok=True)
    validation_path = experiments_dir / "multi_asof_validation_plan_2024.json"
    cache_path = experiments_dir / "multi_asof_cache_plan_2024.json"
    summary_path = experiments_dir / "multi_asof_validation_summary_2024.md"
    symbols_files = _write_multi_asof_symbols_files(plan, Path(outputs_dir))
    cache_payload = {
        "status": plan.get("status"),
        "provider_access": False,
        "prewarm_executed": False,
        "cache_requirements": plan.get("cache_requirements", []),
    }
    validation_path.write_text(json.dumps(sanitize_for_json(plan), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    cache_path.write_text(json.dumps(sanitize_for_json(cache_payload), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    summary_path.write_text(markdown_multi_asof_summary(plan), encoding="utf-8")
    return {"validation_plan": str(validation_path), "cache_plan": str(cache_path), "summary_md": str(summary_path), "symbols_files": symbols_files}


def _write_multi_asof_symbols_files(plan: dict[str, object], outputs_dir: Path) -> list[str]:
    cache_plan_dir = outputs_dir / "cache_plans"
    written: list[str] = []
    for requirement in plan.get("cache_requirements", []):
        if not isinstance(requirement, dict):
            continue
        if requirement.get("status") != "evaluated":
            continue
        symbols = [str(symbol).strip() for symbol in requirement.get("symbols", []) if str(symbol).strip()]
        if not symbols:
            continue
        as_of_date = str(requirement.get("as_of_date"))
        horizon = int(requirement.get("horizon_days"))
        path = cache_plan_dir / f"multi_asof_symbols_{as_of_date}_{horizon}d.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(symbols) + "\n", encoding="utf-8")
        requirement["symbols_file"] = str(path)
        requirement["symbols_file_status"] = "written"
        written.append(str(path))
    return written


def markdown_multi_asof_summary(plan: dict[str, object]) -> str:
    ready_rows, missing_experiment_rows, blocked_rows, deferred_rows = _readiness_rows(plan)
    lines = [
        "# Phase 2.8.4 Multi-As-Of Controlled Validation Plan",
        "",
        str(plan.get("disclaimer", DISCLAIMER)),
        "",
        "Anti-leakage: for each as-of date, features, lists, filters, and dynamic states use only data available on or before that as-of date.",
        "Future returns, future drawdowns, and benchmark outcomes are labels/evaluation metrics only.",
        "",
        f"- As-of dates: {', '.join(plan.get('as_of_dates', []))}",
        f"- Horizons: {', '.join(str(item) + 'd' for item in plan.get('horizons', []))}",
        f"- Provider access: {plan.get('provider_access')}",
        f"- Full workflow executed: {plan.get('full_workflow_executed')}",
        "",
        "## Validation Readiness",
        "",
        "### Ready validations",
        "",
    ]
    lines.extend(_table(ready_rows, ["as_of_date", "horizon_days", "cache_status", "missing_outputs"]))
    lines.extend(["", "### Missing experiment outputs only", ""])
    lines.extend(_table(missing_experiment_rows, ["as_of_date", "horizon_days", "cache_status", "missing_outputs"]))
    lines.extend(
        [
            "",
            "### Blocked because as-of outputs are missing",
            "",
            "Generate as-of labels, factor rows, and list outputs first. Rows with symbol_count=0 in this section are blocked, not cache-complete.",
            "",
        ]
    )
    lines.extend(_table(blocked_rows, ["as_of_date", "horizon_days", "cache_status", "missing_as_of_outputs"]))
    lines.extend(["", "### Deferred because crosses 2025", ""])
    lines.extend(_table(deferred_rows, ["as_of_date", "horizon_days", "cache_status", "future_window"]))
    lines.extend(["", "## Required Outputs By As-Of", ""])
    for as_of in plan.get("as_of_plan", []):
        if not isinstance(as_of, dict):
            continue
        lines.extend([f"### {as_of.get('as_of_date')}", ""])
        lines.extend(_table(as_of.get("horizons", []), ["horizon_days", "ready_for_comparison", "missing_as_of_outputs", "missing_outputs", "cache_requirement_id"]))
        lines.append("")
    lines.extend(
        [
            "## Manual Commands",
            "",
            "These commands are for the user to run manually. The planner does not execute provider fetches or validations.",
            "",
        ]
    )
    for requirement in plan.get("cache_requirements", []):
        if not isinstance(requirement, dict):
            continue
        lines.extend(
            [
                f"### {requirement.get('cache_requirement_id')}",
                "",
                f"Status: {requirement.get('status')}",
                "",
                "Cache coverage check:",
                "",
                "~~~powershell",
                str(requirement.get("manual_cache_coverage_command", "")),
                "~~~",
                "",
                "Manual prewarm, only if the user chooses to fetch missing cache:",
                "",
                "~~~powershell",
                str(requirement.get("manual_prewarm_command", "")),
                "~~~",
                "",
            ]
        )
    lines.extend(
        [
            "## Dynamic State History",
            "",
            "- Track eligible, watch_only, blocked_now, cooldown, and re_entry_candidate across as-of dates.",
            "- cooldown and re_entry_candidate require previous as-of state history before full dynamic add/reduce/exit logic.",
            "",
            "## Non-goals",
            "",
            "- Do not access BaoStock automatically.",
            "- Do not prewarm automatically.",
            "- Do not run full workflow or full-market validation.",
            "- Do not enter 2025.",
            "- Do not change production scoring.",
        ]
    )
    return "\n".join(lines) + "\n"


def future_window_for(as_of_date: str, horizon_days: int) -> dict[str, str]:
    start = date.fromisoformat(as_of_date) + timedelta(days=1)
    return {
        "start_date": start.isoformat(),
        "end_date": recommended_target_end_date(as_of_date, horizon_days),
        "target_end_date_source": "validation.cache_plan.recommended_target_end_date",
    }


def _output_status(outputs_dir: Path, as_of_date: str, horizon: int) -> dict[str, object]:
    required = {
        "walk_forward_predictions": outputs_dir / "validation" / f"walk_forward_predictions_{as_of_date}_{horizon}d.csv",
        "list_performance": outputs_dir / "validation" / f"list_performance_{as_of_date}_{horizon}d.json",
        "factor_effectiveness": outputs_dir / "validation" / f"factor_effectiveness_{as_of_date}_{horizon}d.json",
        "strategy_family_experiments": outputs_dir / "experiments" / f"strategy_family_experiments_{as_of_date}_{horizon}d.json",
        "aggressive_filter_experiments": outputs_dir / "experiments" / f"aggressive_filter_experiments_{as_of_date}_{horizon}d.json",
    }
    existing = {key: str(path) for key, path in required.items() if path.exists()}
    missing = {key: str(path) for key, path in required.items() if not path.exists()}
    return {
        "required_outputs": {key: str(path) for key, path in required.items()},
        "existing_outputs": existing,
        "missing_outputs": missing,
    }


def _as_of_required_outputs(outputs_dir: Path, as_of_date: str) -> dict[str, object]:
    required = {
        "stock_labels": outputs_dir / "labels" / f"stock_labels_{as_of_date}.json",
        "factor_rows_csv": outputs_dir / "daily" / f"factors_{as_of_date}.csv",
        "high_confidence_list": outputs_dir / "lists" / f"high_confidence_candidates_{as_of_date}.json",
    }
    return {key: {"path": str(path), "exists": path.exists()} for key, path in required.items()}


def _missing_as_of_outputs(required_outputs: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in required_outputs.items()
        if isinstance(value, dict) and not value.get("exists")
    }


def _cache_requirement(
    cache_dir: Path,
    provider: str,
    outputs_dir: Path,
    as_of_date: str,
    horizon: int,
    window: dict[str, str],
    recommended_limit: int,
    missing_as_of_outputs: dict[str, object],
) -> dict[str, object]:
    requirement_id = f"{as_of_date}_{horizon}d"
    crosses_year_boundary = window["end_date"] > f"{MULTI_ASOF_YEAR}-12-31"
    if missing_as_of_outputs:
        return {
            "cache_requirement_id": requirement_id,
            "as_of_date": as_of_date,
            "horizon_days": horizon,
            "status": "blocked_missing_as_of_outputs",
            "future_window": window,
            "crosses_2025_boundary": crosses_year_boundary,
            "deferred_until_2025_allowed": crosses_year_boundary,
            "missing_as_of_outputs": missing_as_of_outputs,
            "symbol_count": 0,
            "covered_count": 0,
            "missing_count": 0,
            "missing_symbols": [],
            "provider_access": False,
            "manual_cache_coverage_command": "unavailable_missing_as_of_outputs",
            "manual_prewarm_command": "unavailable_missing_as_of_outputs",
            "notes": ["generate_as_of_labels_lists_first"],
        }
    symbols = _load_symbols_for_cache_requirement(outputs_dir, as_of_date, horizon, recommended_limit)
    if not symbols and not crosses_year_boundary:
        return {
            "cache_requirement_id": requirement_id,
            "as_of_date": as_of_date,
            "horizon_days": horizon,
            "status": "blocked_empty_symbols",
            "future_window": window,
            "crosses_2025_boundary": crosses_year_boundary,
            "deferred_until_2025_allowed": crosses_year_boundary,
            "symbol_count": 0,
            "covered_count": 0,
            "missing_count": 0,
            "missing_symbols": [],
            "symbols": [],
            "provider_access": False,
            "manual_cache_coverage_command": "unavailable_empty_symbols",
            "manual_prewarm_command": "unavailable_empty_symbols",
            "notes": ["no_symbols_loaded_from_as_of_outputs"],
        }
    rows = [_coverage_status(cache_dir, provider=provider, symbol=symbol, start_date=window["start_date"], end_date=window["end_date"]) for symbol in symbols]
    covered_count = sum(1 for row in rows if row["covered"])
    missing_symbols = [row["symbol"] for row in rows if not row["covered"]]
    coverage_limit = len(symbols) if symbols else recommended_limit
    symbols_file = _symbols_file_path(as_of_date, horizon)
    return {
        "cache_requirement_id": requirement_id,
        "as_of_date": as_of_date,
        "horizon_days": horizon,
        "status": "deferred_2025_boundary" if crosses_year_boundary else "evaluated",
        "future_window": window,
        "crosses_2025_boundary": crosses_year_boundary,
        "deferred_until_2025_allowed": crosses_year_boundary,
        "symbol_count": len(symbols),
        "covered_count": covered_count,
        "missing_count": len(missing_symbols),
        "missing_symbols": missing_symbols,
        "symbols": symbols,
        "symbols_file": "not_generated_2025_boundary" if crosses_year_boundary else str(symbols_file),
        "provider_access": False,
        "manual_cache_coverage_command": "not_generated_2025_boundary" if crosses_year_boundary else _cache_coverage_command(as_of_date, horizon, window, coverage_limit),
        "manual_prewarm_command": "not_generated_2025_boundary" if crosses_year_boundary else _prewarm_command(provider, window, coverage_limit),
    }


def _manual_validation_commands(
    config: MultiAsOfValidationConfig,
    as_of_date: str,
    horizon: int,
    crosses_year_boundary: bool,
    missing_as_of_outputs: dict[str, object],
) -> dict[str, str]:
    if crosses_year_boundary:
        return {"strategy_family": "not_generated_2025_boundary", "aggressive_filter": "not_generated_2025_boundary"}
    if missing_as_of_outputs:
        return {"strategy_family": "unavailable_missing_as_of_outputs", "aggressive_filter": "unavailable_missing_as_of_outputs"}
    strategy = (
        "python backend\\scripts\\run_strategy_family_experiments.py "
        f"--as-of-date {as_of_date} --horizon-days {horizon} --outputs-dir outputs --cache-dir {config.cache_dir} --write-output"
    )
    aggressive = (
        "python backend\\scripts\\run_aggressive_filter_experiments.py "
        f"--as-of-date {as_of_date} --horizon-days {horizon} --outputs-dir outputs --cache-dir {config.cache_dir} --write-output"
    )
    return {"strategy_family": strategy, "aggressive_filter": aggressive}


def _symbols_file_path(as_of_date: str, horizon: int) -> Path:
    return Path("outputs") / "cache_plans" / f"multi_asof_symbols_{as_of_date}_{horizon}d.txt"


def _cache_coverage_command(as_of_date: str, horizon: int, window: dict[str, str], limit: int) -> str:
    return (
        "python backend\\scripts\\check_cache_coverage.py "
        f"--start-date {window['start_date']} --end-date {window['end_date']} --cache-dir data\\cache\\daily-use "
        f"--symbols-file outputs\\cache_plans\\multi_asof_symbols_{as_of_date}_{horizon}d.txt --limit {limit} "
        f"--output-file outputs\\experiments\\cache_coverage_{as_of_date}_{horizon}d.json"
    )


def _prewarm_command(provider: str, window: dict[str, str], limit: int) -> str:
    return (
        "python backend\\scripts\\prewarm_market_cache.py "
        f"--provider {provider} --start-date {window['start_date']} --end-date {window['end_date']} "
        f"--cache-dir data\\cache\\daily-use --output-dir outputs\\cache --limit {limit} "
        "--batch-size 10 --sleep-seconds 0.5 --retry 1 --resume"
    )


def _load_symbols_for_cache_requirement(outputs_dir: Path, as_of_date: str, horizon: int, limit: int) -> list[str]:
    prediction_path = outputs_dir / "validation" / f"walk_forward_predictions_{as_of_date}_{horizon}d.csv"
    if prediction_path.exists():
        frame = pd.read_csv(prediction_path, dtype={"symbol": str})
        if "symbol" in frame.columns:
            return _dedupe(str(symbol).strip() for symbol in frame["symbol"].dropna())
    return _load_symbols_for_as_of(outputs_dir, as_of_date, limit)


def _load_symbols_for_as_of(outputs_dir: Path, as_of_date: str, limit: int) -> list[str]:
    symbols: list[str] = []
    list_json_paths = [
        outputs_dir / "labels" / f"stock_labels_{as_of_date}.json",
        outputs_dir / "labels" / f"candidate_labels_{as_of_date}.json",
        outputs_dir / "daily" / f"candidates_{as_of_date}.json",
    ]
    for path in list_json_paths:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            symbols.extend(str(row.get("symbol", "")).strip() for row in payload if isinstance(row, dict) and row.get("symbol"))
    factors_path = outputs_dir / "daily" / f"factors_{as_of_date}.csv"
    if factors_path.exists():
        frame = pd.read_csv(factors_path, dtype={"symbol": str})
        if "symbol" in frame.columns:
            symbols.extend(str(symbol).strip() for symbol in frame["symbol"].dropna())
    symbols.extend(_load_as_of_list_symbols(outputs_dir, as_of_date))
    return _dedupe(symbols)[:limit]


def _load_as_of_list_symbols(outputs_dir: Path, as_of_date: str) -> list[str]:
    symbols: list[str] = []
    high_confidence_path = outputs_dir / "lists" / f"high_confidence_candidates_{as_of_date}.json"
    if high_confidence_path.exists():
        payload = json.loads(high_confidence_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            symbols.extend(_symbols_from_items(payload.get("items", [])))
    multi_lists_path = outputs_dir / "lists" / f"multi_lists_{as_of_date}.json"
    if multi_lists_path.exists():
        payload = json.loads(multi_lists_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            for list_payload in payload.get("lists", {}).values() if isinstance(payload.get("lists"), dict) else []:
                if isinstance(list_payload, dict):
                    symbols.extend(_symbols_from_items(list_payload.get("items", [])))
    return symbols


def _symbols_from_items(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(item.get("symbol", "")).strip() for item in items if isinstance(item, dict) and item.get("symbol")]


def _coverage_status(cache_dir: Path, *, provider: str, symbol: str, start_date: str, end_date: str) -> dict[str, object]:
    path = cache_dir / provider / "stock_daily" / "adjusted" / f"{symbol}.csv"
    if not path.exists():
        return {"symbol": symbol, "covered": False, "status": "missing_file", "path": str(path)}
    try:
        frame = pd.read_csv(path, dtype={"trade_date": str, "symbol": str})
    except Exception as exc:  # pragma: no cover
        return {"symbol": symbol, "covered": False, "status": "read_error", "path": str(path), "error": str(exc)}
    if frame.empty or "trade_date" not in frame.columns:
        return {"symbol": symbol, "covered": False, "status": "empty_or_invalid", "path": str(path)}
    dates = pd.to_datetime(frame["trade_date"], errors="coerce").dropna()
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    window_rows = dates[(dates >= start) & (dates <= end)]
    return {
        "symbol": symbol,
        "covered": not window_rows.empty,
        "status": "covered" if not window_rows.empty else "missing_range",
        "path": str(path),
        "window_row_count": int(len(window_rows)),
    }


def _readiness_rows(plan: dict[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    requirement_by_id = {
        requirement.get("cache_requirement_id"): requirement
        for requirement in plan.get("cache_requirements", [])
        if isinstance(requirement, dict)
    }
    ready_rows: list[dict[str, object]] = []
    missing_experiment_rows: list[dict[str, object]] = []
    blocked_rows: list[dict[str, object]] = []
    deferred_rows: list[dict[str, object]] = []
    for as_of in plan.get("as_of_plan", []):
        if not isinstance(as_of, dict):
            continue
        as_of_date = str(as_of.get("as_of_date", ""))
        for horizon in as_of.get("horizons", []):
            if not isinstance(horizon, dict):
                continue
            requirement = requirement_by_id.get(horizon.get("cache_requirement_id"), {})
            row = {
                "as_of_date": as_of_date,
                "horizon_days": horizon.get("horizon_days"),
                "future_window": horizon.get("future_window"),
                "cache_status": requirement.get("status"),
                "missing_outputs": horizon.get("missing_outputs"),
                "missing_as_of_outputs": horizon.get("missing_as_of_outputs"),
            }
            if horizon.get("crosses_2025_boundary"):
                deferred_rows.append(row)
            elif horizon.get("missing_as_of_outputs"):
                blocked_rows.append(row)
            elif horizon.get("missing_outputs"):
                missing_experiment_rows.append(row)
            else:
                ready_rows.append(row)
    return ready_rows, missing_experiment_rows, blocked_rows, deferred_rows


def _table(rows: object, columns: list[str]) -> list[str]:
    if not isinstance(rows, list) or not rows:
        return ["No rows available."]
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append("| " + " | ".join(_format_cell(row.get(column)) for column in columns) + " |")
    return lines


def _format_cell(value: object) -> str:
    if isinstance(value, dict):
        return ", ".join(value.keys()) if value else ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return "" if value is None else str(value)


def _dedupe(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result

