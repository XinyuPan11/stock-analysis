from __future__ import annotations

from dataclasses import dataclass, field
import json
import time
from pathlib import Path
from typing import Protocol

import pandas as pd

from stock_analysis.data.cache import LocalCsvCache


ERROR_COLUMNS = ["symbol", "stage", "error_type", "error", "attempts"]


class PrewarmMarketDataServiceLike(Protocol):
    provider: object
    cache: LocalCsvCache

    def get_stock_universe(self) -> pd.DataFrame:
        ...

    def get_stock_daily(self, symbol: str, start_date: str, end_date: str, adjusted: bool = True) -> pd.DataFrame:
        ...


@dataclass(frozen=True)
class CachePrewarmConfig:
    provider: str
    start_date: str
    end_date: str
    limit: int = 50
    offset: int = 0
    batch_size: int = 10
    cache_dir: str | Path = "data/cache"
    output_dir: str | Path = "outputs/cache"
    resume: bool = False
    sleep_seconds: float = 0.0
    max_errors: int | None = None
    retry: int = 0
    symbols: tuple[str, ...] = ()
    adjusted: bool = True


@dataclass(frozen=True)
class CachePrewarmResult:
    summary: dict[str, object]
    errors: pd.DataFrame
    output_paths: dict[str, str] = field(default_factory=dict)


def run_cache_prewarm(service: PrewarmMarketDataServiceLike, config: CachePrewarmConfig) -> CachePrewarmResult:
    """Prewarm local daily-stock cache with serial, resumable provider calls."""

    _validate_config(config)
    started = time.monotonic()
    symbols = _resolve_symbols(service, config)
    errors: list[dict[str, object]] = []
    attempted_count = 0
    cache_hit_count = 0
    success_count = 0
    skipped_count = 0
    stopped_early = False

    for batch in _chunks(symbols, config.batch_size):
        for symbol in batch:
            hit = _has_cache_hit(service.cache, config.provider, symbol, config.start_date, config.end_date, config.adjusted)
            if hit:
                cache_hit_count += 1
                if config.resume:
                    skipped_count += 1
                    continue

            attempted_count += 1
            success, error = _fetch_with_retry(service, symbol, config)
            if success:
                success_count += 1
            else:
                errors.append(error)
                if config.max_errors is not None and len(errors) >= config.max_errors:
                    stopped_early = True
                    break
        if stopped_early:
            break
        if config.sleep_seconds > 0:
            time.sleep(config.sleep_seconds)

    error_frame = pd.DataFrame(errors, columns=ERROR_COLUMNS)
    summary = {
        "provider": config.provider,
        "start_date": _date(config.start_date),
        "end_date": _date(config.end_date),
        "limit": int(config.limit),
        "offset": int(config.offset),
        "batch_size": int(config.batch_size),
        "total_symbols": int(len(symbols)),
        "attempted_count": int(attempted_count),
        "cache_hit_count": int(cache_hit_count),
        "success_count": int(success_count),
        "error_count": int(len(error_frame)),
        "skipped_count": int(skipped_count),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "cache_dir": str(Path(config.cache_dir).resolve()),
        "errors_path": "",
        "resume": bool(config.resume),
        "retry": int(config.retry),
        "stopped_early": bool(stopped_early),
    }
    output_paths = _write_outputs(summary, error_frame, config)
    summary["errors_path"] = output_paths["errors_csv"]
    summary["output_paths"] = output_paths
    Path(output_paths["summary_json"]).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return CachePrewarmResult(summary=summary, errors=error_frame, output_paths=output_paths)


def load_symbols_file(path: str | Path) -> tuple[str, ...]:
    """Load symbols from a text/CSV file; CSV may contain a symbol column."""

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"symbols_file not found: {file_path}")
    if file_path.suffix.lower() == ".csv":
        frame = pd.read_csv(file_path, dtype=str)
        if "symbol" in frame.columns:
            values = frame["symbol"].dropna().astype(str).tolist()
        else:
            values = frame.iloc[:, 0].dropna().astype(str).tolist()
    else:
        values = [line.strip() for line in file_path.read_text(encoding="utf-8-sig").splitlines()]
    return tuple(value for value in values if value)


def _resolve_symbols(service: PrewarmMarketDataServiceLike, config: CachePrewarmConfig) -> list[str]:
    if config.symbols:
        source = list(config.symbols)
    else:
        universe = service.get_stock_universe()
        source = universe["symbol"].dropna().astype(str).tolist()
    return source[config.offset : config.offset + config.limit]


def _fetch_with_retry(
    service: PrewarmMarketDataServiceLike,
    symbol: str,
    config: CachePrewarmConfig,
) -> tuple[bool, dict[str, object]]:
    attempts = max(1, int(config.retry) + 1)
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            frame = service.get_stock_daily(symbol, config.start_date, config.end_date, adjusted=config.adjusted)
            if frame is None or frame.empty:
                raise ValueError("empty price history")
            return True, {}
        except Exception as exc:
            last_error = exc
    error_text = str(last_error) if last_error else "unknown error"
    return False, {
        "symbol": symbol,
        "stage": "stock_daily",
        "error_type": classify_fetch_error(error_text),
        "error": error_text,
        "attempts": attempts,
    }


def classify_fetch_error(error: str) -> str:
    text = str(error).lower()
    if "numeric market data" in text or "non-numeric" in text:
        return "non_numeric_market_data"
    if "empty" in text or "no data" in text:
        return "empty_data"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "connection" in text or "reset" in text or "proxy" in text:
        return "connection"
    return "provider_error"


def _has_cache_hit(
    cache: LocalCsvCache,
    provider: str,
    symbol: str,
    start_date: str,
    end_date: str,
    adjusted: bool,
) -> bool:
    return cache.has_market_data_coverage(
        provider=provider,
        dataset="stock_daily",
        symbol=symbol,
        start_date=_date(start_date),
        end_date=_date(end_date),
        adjusted=adjusted,
    )


def _write_outputs(summary: dict[str, object], errors: pd.DataFrame, config: CachePrewarmConfig) -> dict[str, str]:
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_date = _date(config.end_date)
    summary_path = output_dir / f"cache_prewarm_summary_{safe_date}.json"
    errors_path = output_dir / f"cache_prewarm_errors_{safe_date}.csv"
    errors.to_csv(errors_path, index=False, encoding="utf-8-sig")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"summary_json": str(summary_path.resolve()), "errors_csv": str(errors_path.resolve())}


def _chunks(symbols: list[str], batch_size: int) -> list[list[str]]:
    return [symbols[index : index + batch_size] for index in range(0, len(symbols), batch_size)]


def _date(value: str) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"Invalid date: {value}")
    return parsed.strftime("%Y-%m-%d")


def _validate_config(config: CachePrewarmConfig) -> None:
    if config.limit <= 0:
        raise ValueError("limit must be positive.")
    if config.offset < 0:
        raise ValueError("offset cannot be negative.")
    if config.batch_size <= 0:
        raise ValueError("batch_size must be positive.")
    if config.sleep_seconds < 0:
        raise ValueError("sleep_seconds cannot be negative.")
    if config.retry < 0:
        raise ValueError("retry cannot be negative.")
    if config.max_errors is not None and config.max_errors <= 0:
        raise ValueError("max_errors must be positive when provided.")
    if pd.Timestamp(_date(config.start_date)) > pd.Timestamp(_date(config.end_date)):
        raise ValueError("start_date must be on or before end_date.")
