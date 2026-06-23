from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from stock_analysis.portfolio.simulator import PortfolioValidationConfig, run_portfolio_validation
from stock_analysis.validation.walk_forward import WalkForwardConfig, run_walk_forward_validation, sanitize_for_json


FORWARD_EXPANSION_YEAR = 2024
DEFAULT_BATCHES: tuple[tuple[str, str, str], ...] = (
    ("batch_1", "2024-02-01", "2024-05-31"),
    ("batch_2", "2024-06-01", "2024-08-31"),
    ("batch_3", "2024-09-01", "2024-12-31"),
)
DEFAULT_LIMIT_STEPS: tuple[int, ...] = (50, 300, 1000)
DEFAULT_AS_OF_DATE = "2024-01-31"
DEFAULT_CACHE_DIR = "data\\cache\\daily-use"
DISCLAIMER = "Research-only validation planning. This does not run a full-market workflow or provide investment advice."


@dataclass(frozen=True)
class ForwardExpansionConfig:
    outputs_dir: str | Path = "outputs"
    cache_dir: str | Path = DEFAULT_CACHE_DIR
    year: int = FORWARD_EXPANSION_YEAR
    as_of_date: str = DEFAULT_AS_OF_DATE
    benchmark: str = "CSI300"
    provider: str = "baostock"
    recommended_limit: int = 50


@dataclass(frozen=True)
class CacheCoverageConfig:
    start_date: str
    end_date: str
    cache_dir: str | Path = DEFAULT_CACHE_DIR
    outputs_dir: str | Path = "outputs"
    symbols_file: str | Path | None = None
    limit: int | None = 50
    provider: str = "baostock"
    allow_empty_symbols: bool = False


@dataclass(frozen=True)
class ControlledValidationBatchConfig:
    as_of_date: str = DEFAULT_AS_OF_DATE
    horizon_days: int = 60
    benchmark: str = "CSI300"
    outputs_dir: str | Path = "outputs"
    cache_dir: str | Path = DEFAULT_CACHE_DIR
    limit: int | None = 50
    dry_run: bool = True


def build_forward_expansion_plan(config: ForwardExpansionConfig) -> dict[str, object]:
    batches = []
    for batch_id, start_date, end_date in DEFAULT_BATCHES:
        batches.append(
            {
                "batch_id": batch_id,
                "start_date": start_date,
                "end_date": end_date,
                "recommended_limit": config.recommended_limit,
                "limit_steps": list(DEFAULT_LIMIT_STEPS),
                "full_market_later": True,
                "cache_dir": str(config.cache_dir),
                "manual_prewarm_command": _prewarm_command(config, start_date, end_date, config.recommended_limit),
                "manual_controlled_validation_dry_run_command": _controlled_validation_command(
                    config,
                    horizon_days=_horizon_for_batch(batch_id),
                    limit=config.recommended_limit,
                    write_output=False,
                ),
                "manual_controlled_validation_write_command": _controlled_validation_command(
                    config,
                    horizon_days=_horizon_for_batch(batch_id),
                    limit=config.recommended_limit,
                    write_output=True,
                ),
                "cache_coverage_command": _coverage_command(config, start_date, end_date, config.recommended_limit),
                "expected_outputs": _expected_outputs(config, _horizon_for_batch(batch_id), config.recommended_limit),
                "estimated_risk": _risk_for_batch(batch_id),
            }
        )
    return {
        "status": "plan_only",
        "year": config.year,
        "as_of_date": config.as_of_date,
        "date_range": {"start_date": "2024-02-01", "end_date": "2024-12-31"},
        "provider_access": False,
        "no_full_market_default": True,
        "no_future_leakage": True,
        "disclaimer": DISCLAIMER,
        "batches": batches,
        "notes": [
            "Codex should not run full-year prewarm, full-market workflow, or full-market backtest in this phase.",
            "Signals and rankings remain fixed as of 2024-01-31; forward prices are for validation labels only.",
            "Use limit 50 first, then 300, then 1000 before considering full market.",
        ],
    }


def write_forward_expansion_plan(plan: dict[str, object], outputs_dir: str | Path) -> dict[str, str]:
    output_dir = Path(outputs_dir) / "expansion"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "forward_expansion_plan_2024.json"
    md_path = output_dir / "forward_expansion_plan_2024.md"
    json_path.write_text(json.dumps(sanitize_for_json(plan), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    md_path.write_text(markdown_forward_expansion_plan(plan), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def markdown_forward_expansion_plan(plan: dict[str, object]) -> str:
    lines = [
        "# Phase 2.8.1 Controlled 2024 Forward Expansion Plan",
        "",
        str(plan.get("disclaimer", DISCLAIMER)),
        "",
        "No future leakage: research views stay fixed as of `2024-01-31`; future price data is used only for validation labels.",
        "",
        "## Batches",
        "",
    ]
    for batch in plan.get("batches", []):
        if not isinstance(batch, dict):
            continue
        lines.extend(
            [
                f"### {batch.get('batch_id')}: {batch.get('start_date')} to {batch.get('end_date')}",
                "",
                f"- Recommended first limit: {batch.get('recommended_limit')}",
                f"- Limit ladder: {batch.get('limit_steps')}",
                f"- Estimated risk: {batch.get('estimated_risk')}",
                "",
                "Prewarm command:",
                "",
                "```powershell",
                str(batch.get("manual_prewarm_command", "")),
                "```",
                "",
                "Cache coverage command:",
                "",
                "```powershell",
                str(batch.get("cache_coverage_command", "")),
                "```",
                "",
                "Controlled validation dry-run command:",
                "",
                "```powershell",
                str(batch.get("manual_controlled_validation_dry_run_command", "")),
                "```",
                "",
                "Controlled validation write-output command:",
                "",
                "```powershell",
                str(batch.get("manual_controlled_validation_write_command", "")),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Explicit Non-goals",
            "",
            "- Do not let Codex run full-year prewarm.",
            "- Do not let Codex run full-market workflow.",
            "- Do not let Codex run full-market backtest.",
            "- Do not enter 2025 until 2024 controlled batches are reviewed.",
        ]
    )
    return "\n".join(lines) + "\n"


def check_cache_coverage(config: CacheCoverageConfig) -> dict[str, object]:
    symbols = _load_symbols(config)
    rows = []
    covered = 0
    for symbol in symbols:
        status = _coverage_status(
            Path(config.cache_dir),
            provider=config.provider,
            symbol=symbol,
            start_date=config.start_date,
            end_date=config.end_date,
        )
        rows.append(status)
        if status["covered"]:
            covered += 1
    missing = [row["symbol"] for row in rows if not row["covered"]]
    return {
        "status": "ok",
        "provider_access": False,
        "date_range": {"start_date": config.start_date, "end_date": config.end_date},
        "cache_dir": str(config.cache_dir),
        "symbol_count": len(symbols),
        "covered_count": covered,
        "missing_count": len(missing),
        "coverage_rate": (covered / len(symbols)) if symbols else 0.0,
        "missing_symbols": missing,
        "symbols": rows,
    }


def write_cache_coverage_report(report: dict[str, object], output_file: str | Path) -> str:
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(report), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return str(path)


def run_controlled_validation_batch(config: ControlledValidationBatchConfig) -> dict[str, object]:
    walk_forward = run_walk_forward_validation(
        WalkForwardConfig(
            as_of_date=config.as_of_date,
            horizon_days=config.horizon_days,
            benchmark=config.benchmark,
            outputs_dir=config.outputs_dir,
            cache_dir=config.cache_dir,
            limit=config.limit,
            dry_run=config.dry_run,
        )
    )
    portfolio = run_portfolio_validation(
        PortfolioValidationConfig(
            as_of_date=config.as_of_date,
            horizon_days=config.horizon_days,
            benchmark=config.benchmark,
            outputs_dir=config.outputs_dir,
            cache_dir=config.cache_dir,
            limit=config.limit,
            dry_run=config.dry_run,
        )
    )
    return {
        "status": "dry_run" if config.dry_run else "ok",
        "dry_run": config.dry_run,
        "provider_access": False,
        "no_full_market_workflow": True,
        "no_future_leakage": True,
        "walk_forward_summary": walk_forward.get("summary", {}),
        "portfolio_summary": portfolio.get("summary", {}),
        "outputs": {
            "walk_forward": walk_forward.get("outputs", {}),
            "portfolio": portfolio.get("outputs", {}),
        },
    }


def default_coverage_output(outputs_dir: str | Path, start_date: str, end_date: str, limit: int | None) -> Path:
    limit_part = "all" if limit is None or limit <= 0 else f"limit{limit}"
    return Path(outputs_dir) / "expansion" / f"cache_coverage_{start_date}_{end_date}_{limit_part}.json"


def _prewarm_command(config: ForwardExpansionConfig, start_date: str, end_date: str, limit: int) -> str:
    return (
        "python backend\\scripts\\prewarm_market_cache.py "
        f"--provider {config.provider} --start-date {start_date} --end-date {end_date} "
        f"--cache-dir {config.cache_dir} --output-dir outputs\\cache --limit {limit} "
        "--batch-size 10 --sleep-seconds 0.5 --retry 1 --resume"
    )


def _coverage_command(config: ForwardExpansionConfig, start_date: str, end_date: str, limit: int) -> str:
    return (
        "python backend\\scripts\\check_cache_coverage.py "
        f"--start-date {start_date} --end-date {end_date} --cache-dir {config.cache_dir} --limit {limit} "
        f"--output-file outputs\\expansion\\cache_coverage_{start_date}_{end_date}_limit{limit}.json"
    )


def _controlled_validation_command(config: ForwardExpansionConfig, *, horizon_days: int, limit: int, write_output: bool) -> str:
    command = (
        "python backend\\scripts\\run_controlled_validation_batch.py "
        f"--as-of-date {config.as_of_date} --horizon-days {horizon_days} --benchmark {config.benchmark} "
        f"--outputs-dir outputs --cache-dir {config.cache_dir} --limit {limit}"
    )
    return f"{command} --write-output" if write_output else command


def _expected_outputs(config: ForwardExpansionConfig, horizon_days: int, limit: int) -> list[str]:
    suffix = f"{config.as_of_date}_{horizon_days}d"
    return [
        f"outputs\\validation\\walk_forward_summary_{suffix}.json",
        f"outputs\\validation\\walk_forward_predictions_{suffix}.csv",
        f"outputs\\portfolios\\portfolio_summary_{suffix}.json",
        f"outputs\\expansion\\cache_coverage_{{batch_start}}_{{batch_end}}_limit{limit}.json",
    ]


def _risk_for_batch(batch_id: str) -> str:
    if batch_id == "batch_1":
        return "low_to_medium: already aligned with 60D fixed-historical validation window."
    if batch_id == "batch_2":
        return "medium: requires more forward cache and checks for suspended/new symbols."
    return "medium_to_high: longest 2024 segment; review batch 1 and 2 before expanding."


def _horizon_for_batch(batch_id: str) -> int:
    return 60 if batch_id == "batch_1" else 20


def _load_symbols(config: CacheCoverageConfig) -> list[str]:
    if config.symbols_file:
        symbols = _read_symbol_lines(Path(config.symbols_file))
    else:
        symbols = _load_default_symbols(Path(config.outputs_dir))
    if config.limit is not None and config.limit > 0:
        symbols = symbols[: config.limit]
    if not symbols and not config.allow_empty_symbols:
        source = f"symbols_file={config.symbols_file}" if config.symbols_file else f"outputs_dir={config.outputs_dir}"
        raise ValueError(f"cache coverage requires at least one symbol; {source} produced zero symbols")
    return symbols


def _read_symbol_lines(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"symbols_file not found: {path}")
    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if value and not value.startswith("#"):
            result.append(value)
    return _dedupe(result)


def _load_default_symbols(outputs_dir: Path) -> list[str]:
    for path in [
        outputs_dir / "labels" / "stock_labels_2024-01-31.json",
        outputs_dir / "labels" / "candidate_labels_2024-01-31.json",
        outputs_dir / "daily" / "candidates_2024-01-31.json",
    ]:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return _dedupe(str(row.get("symbol", "")).strip() for row in payload if isinstance(row, dict) and row.get("symbol"))
    return []


def _coverage_status(cache_dir: Path, *, provider: str, symbol: str, start_date: str, end_date: str) -> dict[str, object]:
    path = cache_dir / provider / "stock_daily" / "adjusted" / f"{symbol}.csv"
    if not path.exists():
        return {"symbol": symbol, "covered": False, "status": "missing_file", "path": str(path), "row_count": 0}
    try:
        frame = pd.read_csv(path, dtype={"trade_date": str, "symbol": str})
    except Exception as exc:  # pragma: no cover - defensive for corrupt local cache
        return {"symbol": symbol, "covered": False, "status": "read_error", "path": str(path), "row_count": 0, "error": str(exc)}
    if frame.empty or "trade_date" not in frame.columns:
        return {"symbol": symbol, "covered": False, "status": "empty_or_invalid", "path": str(path), "row_count": int(len(frame))}
    dates = pd.to_datetime(frame["trade_date"], errors="coerce").dropna()
    if dates.empty:
        return {"symbol": symbol, "covered": False, "status": "invalid_dates", "path": str(path), "row_count": int(len(frame))}
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    in_window = dates[(dates >= start) & (dates <= end)]
    return {
        "symbol": symbol,
        "covered": not in_window.empty,
        "status": "covered" if not in_window.empty else "missing_range",
        "path": str(path),
        "row_count": int(len(frame)),
        "window_row_count": int(len(in_window)),
        "min_trade_date": dates.min().strftime("%Y-%m-%d"),
        "max_trade_date": dates.max().strftime("%Y-%m-%d"),
    }


def _dedupe(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result
