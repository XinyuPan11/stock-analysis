from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from stock_analysis.data.cache_prewarm import load_symbols_file


DEFAULT_PROVIDER = "baostock"
DEFAULT_START_DATE = "2024-12-11"
DEFAULT_END_DATE = "2026-06-24"
DEFAULT_CACHE_DIR = "data/cache/daily-use"
DEFAULT_OUTPUT_DIR = "outputs/cache"
DEFAULT_CHUNK_SIZE = 500
DEFAULT_START_OFFSET = 250


@dataclass(frozen=True)
class RawCacheCoverageConfig:
    cache_dir: str | Path = DEFAULT_CACHE_DIR
    provider: str = DEFAULT_PROVIDER
    target_end_date: str = DEFAULT_END_DATE
    symbols_file: str | Path | None = None


@dataclass(frozen=True)
class RawCacheCatchupPlanConfig:
    provider: str = DEFAULT_PROVIDER
    start_date: str = DEFAULT_START_DATE
    end_date: str = DEFAULT_END_DATE
    cache_dir: str | Path = DEFAULT_CACHE_DIR
    output_dir: str | Path = DEFAULT_OUTPUT_DIR
    chunk_size: int = DEFAULT_CHUNK_SIZE
    start_offset: int = DEFAULT_START_OFFSET
    chunk_count: int = 1
    total_symbols: int | None = None
    batch_size: int = 5
    sleep_seconds: float = 1.0
    retry: int = 1
    max_errors: int = 50
    symbol_timeout_seconds: int = 20
    max_consecutive_symbol_timeouts: int = 3
    failed_symbols_file: str | Path | None = None


def build_raw_cache_coverage_report(config: RawCacheCoverageConfig) -> dict[str, Any]:
    """Summarize local stock_daily adjusted cache freshness without provider access."""

    target_end = _date(config.target_end_date)
    cache_path = stock_daily_adjusted_cache_path(config.cache_dir, config.provider)
    rows: list[dict[str, Any]] = []
    for csv_path in sorted(cache_path.glob("*.csv")) if cache_path.exists() else []:
        row = _symbol_cache_row(csv_path, target_end)
        rows.append(row)

    cached_symbols = {str(row["symbol"]) for row in rows if row.get("symbol")}
    expected_symbols = _load_expected_symbols(config.symbols_file)
    missing_symbols = sorted(symbol for symbol in expected_symbols if symbol not in cached_symbols)
    stale_rows = [row for row in rows if not row["reaches_target_end_date"]]
    complete_rows = [row for row in rows if row["reaches_target_end_date"]]
    return {
        "status": "ok",
        "provider_access": False,
        "prewarm_executed": False,
        "full_workflow_executed": False,
        "production_scoring_changed": False,
        "cache_layout": str(cache_path),
        "provider": config.provider,
        "target_end_date": target_end,
        "total_stock_csv_files": len(rows),
        "complete_symbol_count": len(complete_rows),
        "stale_incomplete_symbol_count": len(stale_rows),
        "missing_symbol_count": len(missing_symbols),
        "missing_symbols_source": str(config.symbols_file) if config.symbols_file else "",
        "summary_counts": {
            "total_stock_csv_files": len(rows),
            "complete_symbol_count": len(complete_rows),
            "stale_incomplete_symbol_count": len(stale_rows),
            "missing_symbol_count": len(missing_symbols),
        },
        "symbols": rows,
        "stale_incomplete_symbols": stale_rows,
        "missing_symbols": missing_symbols,
    }


def write_raw_cache_coverage_report(report: dict[str, Any], output_file: str | Path) -> str:
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def generate_raw_cache_catchup_plan(config: RawCacheCatchupPlanConfig) -> dict[str, Any]:
    _validate_plan_config(config)
    chunks = _chunk_specs(config)
    chunk_commands = [_chunk_command(config, offset, limit) for offset, limit in chunks]
    retry_command = _retry_command(config, config.failed_symbols_file) if config.failed_symbols_file else ""
    return {
        "status": "ok",
        "provider_access": False,
        "prewarm_executed": False,
        "full_workflow_executed": False,
        "production_scoring_changed": False,
        "provider": config.provider,
        "start_date": _date(config.start_date),
        "end_date": _date(config.end_date),
        "cache_dir": str(config.cache_dir),
        "cache_layout": str(stock_daily_adjusted_cache_path(config.cache_dir, config.provider)),
        "output_dir": str(config.output_dir),
        "chunk_size": config.chunk_size,
        "start_offset": config.start_offset,
        "chunk_count": len(chunk_commands),
        "total_symbols": config.total_symbols,
        "confirmed_smoke_coverage": {
            "offset_0_limit_50": "success",
            "offset_50_limit_200": "success_after_retry",
            "confirmed_successful_symbols": 250,
            "current_failed_count": 0,
        },
        "chunk_commands": chunk_commands,
        "retry_command": retry_command,
        "notes": [
            "commands_only_no_provider_access",
            "user_runs_long_prewarm_jobs_manually",
            "raw_cache_catchup_only_no_scoring_or_validation",
        ],
    }


def write_raw_cache_catchup_plan(plan: dict[str, Any], output_file: str | Path) -> str:
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def stock_daily_adjusted_cache_path(cache_dir: str | Path, provider: str = DEFAULT_PROVIDER) -> Path:
    return Path(cache_dir) / provider / "stock_daily" / "adjusted"


def _symbol_cache_row(csv_path: Path, target_end: str) -> dict[str, Any]:
    symbol = csv_path.stem
    try:
        frame = pd.read_csv(csv_path, dtype={"symbol": str})
    except Exception as exc:
        return {
            "symbol": symbol,
            "path": str(csv_path),
            "earliest_cached_date": None,
            "latest_cached_date": None,
            "row_count": 0,
            "reaches_target_end_date": False,
            "status": "read_error",
            "error_message": str(exc),
        }
    if "trade_date" not in frame.columns:
        return {
            "symbol": symbol,
            "path": str(csv_path),
            "earliest_cached_date": None,
            "latest_cached_date": None,
            "row_count": int(len(frame)),
            "reaches_target_end_date": False,
            "status": "missing_trade_date",
            "error_message": "trade_date column missing",
        }
    dates = pd.to_datetime(frame["trade_date"], errors="coerce").dropna()
    if dates.empty:
        return {
            "symbol": symbol,
            "path": str(csv_path),
            "earliest_cached_date": None,
            "latest_cached_date": None,
            "row_count": int(len(frame)),
            "reaches_target_end_date": False,
            "status": "no_valid_trade_dates",
            "error_message": "trade_date column has no valid dates",
        }
    earliest = dates.min().strftime("%Y-%m-%d")
    latest = dates.max().strftime("%Y-%m-%d")
    reaches_target = pd.Timestamp(latest) >= pd.Timestamp(target_end)
    return {
        "symbol": symbol,
        "path": str(csv_path),
        "earliest_cached_date": earliest,
        "latest_cached_date": latest,
        "row_count": int(len(frame)),
        "reaches_target_end_date": bool(reaches_target),
        "status": "complete" if reaches_target else "stale_incomplete",
        "error_message": "",
    }


def _load_expected_symbols(symbols_file: str | Path | None) -> tuple[str, ...]:
    if not symbols_file:
        return ()
    return load_symbols_file(symbols_file)


def _chunk_specs(config: RawCacheCatchupPlanConfig) -> list[tuple[int, int]]:
    if config.total_symbols is not None:
        if config.start_offset >= config.total_symbols:
            return []
        remaining = config.total_symbols - config.start_offset
        count = math.ceil(remaining / config.chunk_size)
    else:
        count = config.chunk_count
    specs: list[tuple[int, int]] = []
    for index in range(count):
        offset = config.start_offset + index * config.chunk_size
        limit = config.chunk_size
        if config.total_symbols is not None:
            limit = min(config.chunk_size, config.total_symbols - offset)
        if limit > 0:
            specs.append((offset, limit))
    return specs


def _chunk_command(config: RawCacheCatchupPlanConfig, offset: int, limit: int) -> dict[str, Any]:
    slug = _chunk_slug(config.start_date, config.end_date, offset, limit)
    command = (
        "python backend\\scripts\\prewarm_market_cache.py "
        f"--provider {config.provider} --start-date {_date(config.start_date)} --end-date {_date(config.end_date)} "
        f"--cache-dir {config.cache_dir} --output-dir {config.output_dir} "
        f"--limit {limit} --offset {offset} --batch-size {config.batch_size} "
        f"--sleep-seconds {config.sleep_seconds} --retry {config.retry} --resume --max-errors {config.max_errors} "
        f"--symbol-timeout-seconds {config.symbol_timeout_seconds} "
        f"--max-consecutive-symbol-timeouts {config.max_consecutive_symbol_timeouts} "
        f"--failed-symbols-output {Path(config.output_dir) / (slug + '_failed.csv')} "
        f"--progress-log {Path(config.output_dir) / (slug + '_progress.jsonl')}"
    )
    return {
        "chunk_id": slug,
        "offset": offset,
        "limit": limit,
        "failed_symbols_output": str(Path(config.output_dir) / (slug + "_failed.csv")),
        "progress_log": str(Path(config.output_dir) / (slug + "_progress.jsonl")),
        "command": command,
    }


def _retry_command(config: RawCacheCatchupPlanConfig, failed_symbols_file: str | Path | None) -> str:
    if not failed_symbols_file:
        return ""
    failed_path = Path(failed_symbols_file)
    retry_slug = _safe_slug(failed_path.stem) + "_retry"
    return (
        "python backend\\scripts\\prewarm_market_cache.py "
        f"--provider {config.provider} --start-date {_date(config.start_date)} --end-date {_date(config.end_date)} "
        f"--cache-dir {config.cache_dir} --output-dir {config.output_dir} "
        f"--failed-symbols-file {failed_path} --retry-only --batch-size 1 --sleep-seconds 2.0 "
        "--retry 2 --resume --max-errors 10 --symbol-timeout-seconds 40 --max-consecutive-symbol-timeouts 2 "
        f"--failed-symbols-output {Path(config.output_dir) / (retry_slug + '_failed.csv')} "
        f"--progress-log {Path(config.output_dir) / (retry_slug + '_progress.jsonl')}"
    )


def _chunk_slug(start_date: str, end_date: str, offset: int, limit: int) -> str:
    return f"raw_catchup_{_date(start_date)}_{_date(end_date)}_offset{offset}_limit{limit}"


def _safe_slug(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)


def _date(value: str) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"Invalid date: {value}")
    return parsed.strftime("%Y-%m-%d")


def _validate_plan_config(config: RawCacheCatchupPlanConfig) -> None:
    if config.chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if config.start_offset < 0:
        raise ValueError("start_offset cannot be negative")
    if config.chunk_count <= 0:
        raise ValueError("chunk_count must be positive")
    if config.total_symbols is not None and config.total_symbols <= 0:
        raise ValueError("total_symbols must be positive when provided")
    if config.batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if config.sleep_seconds < 0:
        raise ValueError("sleep_seconds cannot be negative")
    if config.retry < 0:
        raise ValueError("retry cannot be negative")
    if config.max_errors <= 0:
        raise ValueError("max_errors must be positive")
    if config.symbol_timeout_seconds <= 0:
        raise ValueError("symbol_timeout_seconds must be positive")
    if config.max_consecutive_symbol_timeouts <= 0:
        raise ValueError("max_consecutive_symbol_timeouts must be positive")
    if pd.Timestamp(_date(config.start_date)) > pd.Timestamp(_date(config.end_date)):
        raise ValueError("start_date must be on or before end_date")
