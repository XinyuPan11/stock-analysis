from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from stock_analysis.data.cache import LocalCsvCache


ERROR_COLUMNS = [
    "symbol",
    "name",
    "stage",
    "error_type",
    "error_message",
    "provider",
    "start_date",
    "end_date",
    "attempt_count",
    "last_attempt_at",
    "can_retry",
]


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
    requested_start_date: str | None = None
    include_lookback_days: int = 0
    limit: int | None = None
    offset: int = 0
    batch_size: int = 10
    cache_dir: str | Path = "data/cache"
    output_dir: str | Path = "outputs/cache"
    resume: bool = False
    sleep_seconds: float = 0.0
    max_errors: int | None = None
    retry: int = 0
    symbols: tuple[str, ...] = ()
    retry_only: bool = False
    adjusted: bool = True
    symbol_timeout_seconds: float | None = None
    max_consecutive_symbol_timeouts: int | None = None
    failed_symbols_output: str | Path | None = None
    progress_log: str | Path | None = None


@dataclass(frozen=True)
class CachePrewarmResult:
    summary: dict[str, object]
    errors: pd.DataFrame
    output_paths: dict[str, str] = field(default_factory=dict)


def run_cache_prewarm(service: PrewarmMarketDataServiceLike, config: CachePrewarmConfig) -> CachePrewarmResult:
    """Prewarm local daily-stock cache with serial, resumable provider calls."""

    _validate_config(config)
    started = time.monotonic()
    symbol_rows = _resolve_symbol_rows(service, config)
    errors: list[dict[str, object]] = []
    attempted_count = 0
    cache_hit_count = 0
    success_count = 0
    skipped_count = 0
    timeout_count = 0
    coverage_metadata_mismatch_count = 0
    coverage_metadata_repaired_count = 0
    consecutive_symbol_timeouts = 0
    stopped_early = False
    stop_reason = ""
    total_symbols = len(symbol_rows)
    processed_count = 0

    for batch in _chunks(symbol_rows, config.batch_size):
        for item in batch:
            processed_count += 1
            symbol = str(item["symbol"])
            start_date = _effective_start_date(config)
            symbol_index = processed_count
            coverage_details = _cache_coverage_details(
                service.cache,
                config.provider,
                symbol,
                start_date,
                config.end_date,
                config.adjusted,
            )
            hit = bool(coverage_details["coverage_ok"])
            if bool(coverage_details.get("coverage_metadata_mismatch")):
                coverage_metadata_mismatch_count += 1
                repaired = service.cache.repair_market_data_coverage_metadata(
                    provider=config.provider,
                    dataset="stock_daily",
                    symbol=symbol,
                    adjusted=config.adjusted,
                )
                if repaired:
                    coverage_metadata_repaired_count += 1
            if hit:
                cache_hit_count += 1
                consecutive_symbol_timeouts = 0
                if config.resume:
                    skipped_count += 1
                    _emit_progress(
                        config,
                        _progress_event(symbol_index, total_symbols, symbol, True, True, False, "cache_hit_skipped"),
                    )
                    continue

            attempted_count += 1
            _emit_progress(
                config,
                _progress_event(symbol_index, total_symbols, symbol, hit, hit, True, "fetch_started"),
            )
            success, error = _fetch_with_retry(service, item, config)
            if success:
                success_count += 1
                consecutive_symbol_timeouts = 0
                _emit_progress(
                    config,
                    _progress_event(symbol_index, total_symbols, symbol, hit, True, True, "success"),
                )
            else:
                errors.append(error)
                error_type = str(error.get("error_type", "provider_error"))
                if error_type == "symbol_timeout":
                    timeout_count += 1
                    consecutive_symbol_timeouts += 1
                else:
                    consecutive_symbol_timeouts = 0
                _emit_progress(
                    config,
                    _progress_event(symbol_index, total_symbols, symbol, hit, False, True, "error", error_type),
                )
                if (
                    config.max_consecutive_symbol_timeouts is not None
                    and consecutive_symbol_timeouts >= config.max_consecutive_symbol_timeouts
                ):
                    stopped_early = True
                    stop_reason = "max_consecutive_symbol_timeouts"
                    break
                if config.max_errors is not None and len(errors) >= config.max_errors:
                    stopped_early = True
                    stop_reason = "max_errors"
                    break
        if stopped_early:
            break
        if config.sleep_seconds > 0:
            time.sleep(config.sleep_seconds)

    error_frame = pd.DataFrame(errors, columns=ERROR_COLUMNS)
    error_type_counts = _error_type_counts(error_frame)
    requested_start = _date(config.requested_start_date or config.start_date)
    effective_start = _effective_start_date(config)
    summary = {
        "provider": config.provider,
        "requested_start_date": requested_start,
        "effective_start_date": effective_start,
        "start_date": effective_start,
        "end_date": _date(config.end_date),
        "include_lookback_days": int(config.include_lookback_days),
        "limit": config.limit,
        "full_market": config.limit is None,
        "offset": int(config.offset),
        "batch_size": int(config.batch_size),
        "total_symbols": int(len(symbol_rows)),
        "attempted_count": int(attempted_count),
        "cache_hit_count": int(cache_hit_count),
        "success_count": int(success_count),
        "error_count": int(len(error_frame)),
        "skipped_count": int(skipped_count),
        "timeout_count": int(timeout_count),
        "coverage_metadata_mismatch_count": int(coverage_metadata_mismatch_count),
        "coverage_metadata_repaired_count": int(coverage_metadata_repaired_count),
        "consecutive_symbol_timeouts": int(consecutive_symbol_timeouts),
        "max_consecutive_symbol_timeouts": config.max_consecutive_symbol_timeouts,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "cache_dir": str(Path(config.cache_dir).resolve()),
        "errors_path": "",
        "resume": bool(config.resume),
        "retry": int(config.retry),
        "retry_only": bool(config.retry_only),
        "stopped_early": bool(stopped_early),
        "stop_reason": stop_reason,
        "failed_symbols_output": str(Path(config.failed_symbols_output).resolve()) if config.failed_symbols_output else "",
        "progress_log": str(Path(config.progress_log).resolve()) if config.progress_log else "",
        "symbol_timeout_seconds": config.symbol_timeout_seconds,
        "error_type_counts": error_type_counts,
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


def _resolve_symbol_rows(service: PrewarmMarketDataServiceLike, config: CachePrewarmConfig) -> list[dict[str, str]]:
    if config.symbols:
        source = [{"symbol": symbol, "name": ""} for symbol in config.symbols]
    else:
        universe = service.get_stock_universe()
        source = [
            {"symbol": str(row["symbol"]), "name": str(row.get("name", ""))}
            for _, row in universe.dropna(subset=["symbol"]).iterrows()
        ]
    if config.limit is None:
        return source[config.offset :]
    return source[config.offset : config.offset + config.limit]


def _fetch_with_retry(
    service: PrewarmMarketDataServiceLike,
    item: dict[str, str],
    config: CachePrewarmConfig,
) -> tuple[bool, dict[str, object]]:
    if config.symbol_timeout_seconds is not None:
        return _fetch_with_symbol_timeout(item, config)
    return _fetch_in_process(service, item, config)


def _fetch_in_process(
    service: PrewarmMarketDataServiceLike,
    item: dict[str, str],
    config: CachePrewarmConfig,
) -> tuple[bool, dict[str, object]]:
    symbol = str(item["symbol"])
    attempts = max(1, int(config.retry) + 1)
    last_error: Exception | None = None
    for _attempt in range(1, attempts + 1):
        try:
            frame = service.get_stock_daily(symbol, _effective_start_date(config), config.end_date, adjusted=config.adjusted)
            if frame is None or frame.empty:
                raise ValueError("empty price history")
            return True, {}
        except Exception as exc:
            last_error = exc
    error_text = str(last_error) if last_error else "unknown error"
    return False, _error_row(item, config, classify_fetch_error(error_text), error_text, attempts)


def _fetch_with_symbol_timeout(item: dict[str, str], config: CachePrewarmConfig) -> tuple[bool, dict[str, object]]:
    payload = {
        "provider": config.provider,
        "symbol": str(item["symbol"]),
        "start_date": _effective_start_date(config),
        "end_date": _date(config.end_date),
        "cache_dir": str(config.cache_dir),
        "adjusted": bool(config.adjusted),
        "retry": int(config.retry),
    }
    command = [
        sys.executable,
        "-c",
        (
            "import json, sys; "
            "from stock_analysis.data.cache_prewarm import _symbol_fetch_worker_main; "
            "raise SystemExit(_symbol_fetch_worker_main(json.loads(sys.argv[1])))"
        ),
        json.dumps(payload, ensure_ascii=False),
    ]
    env = os.environ.copy()
    src_path = str(Path(__file__).resolve().parents[2])
    env["PYTHONPATH"] = src_path + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    try:
        completed = subprocess.run(
            command,
            cwd=str(Path(__file__).resolve().parents[4]),
            env=env,
            capture_output=True,
            text=True,
            timeout=float(config.symbol_timeout_seconds),
            check=False,
        )
    except subprocess.TimeoutExpired:
        timeout_text = f"Symbol fetch timed out after {config.symbol_timeout_seconds} seconds during provider_fetch."
        return False, _error_row(item, config, "symbol_timeout", timeout_text, max(1, int(config.retry) + 1))
    if completed.returncode == 0:
        return True, {}
    error_text = (completed.stderr or completed.stdout or "symbol fetch failed").strip()
    return False, _error_row(item, config, classify_fetch_error(error_text), error_text, max(1, int(config.retry) + 1))


def _symbol_fetch_worker_main(payload: dict[str, Any]) -> int:
    provider_name = str(payload["provider"])
    provider = _build_worker_provider(provider_name)
    cache = LocalCsvCache(cache_dir=str(payload["cache_dir"]))
    from stock_analysis.data.service import MarketDataService

    service = MarketDataService(provider=provider, cache=cache)
    attempts = max(1, int(payload.get("retry", 0)) + 1)
    last_error: Exception | None = None
    for _attempt in range(1, attempts + 1):
        try:
            frame = service.get_stock_daily(
                str(payload["symbol"]),
                str(payload["start_date"]),
                str(payload["end_date"]),
                adjusted=bool(payload.get("adjusted", True)),
            )
            if frame is None or frame.empty:
                raise ValueError("empty price history")
            return 0
        except Exception as exc:
            last_error = exc
    print(str(last_error) if last_error else "unknown error", file=sys.stderr)
    return 1


def _build_worker_provider(name: str) -> object:
    from stock_analysis.data.providers import AkShareProvider, BaoStockProvider, TushareProvider

    if name == "akshare":
        return AkShareProvider()
    if name == "baostock":
        return BaoStockProvider()
    if name == "tushare":
        return TushareProvider()
    raise ValueError(f"Unsupported timeout worker provider: {name}")


def _error_row(
    item: dict[str, str],
    config: CachePrewarmConfig,
    error_type: str,
    error_message: str,
    attempts: int,
) -> dict[str, object]:
    return {
        "symbol": str(item["symbol"]),
        "name": str(item.get("name", "")),
        "stage": "provider_fetch",
        "error_type": error_type,
        "error_message": error_message,
        "provider": config.provider,
        "start_date": _effective_start_date(config),
        "end_date": _date(config.end_date),
        "attempt_count": attempts,
        "last_attempt_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "can_retry": _can_retry(error_type),
    }


def classify_fetch_error(error: str) -> str:
    text = str(error).lower()
    if "missing_required_columns" in text or "missing provider column" in text or "missing required columns" in text:
        return "missing_required_columns"
    if "invalid_price_data" in text or "ohlc" in text or "high < low" in text or "price" in text and "constraint" in text:
        return "invalid_price_data"
    if "numeric market data" in text or "non-numeric" in text:
        return "non_numeric_market_data"
    if "empty_market_data" in text or "empty" in text or "no data" in text:
        return "empty_market_data"
    if "symbol_timeout" in text:
        return "symbol_timeout"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "connection" in text or "reset" in text or "proxy" in text:
        return "connection"
    return "provider_error"


def _error_type_counts(errors: pd.DataFrame) -> dict[str, int]:
    if errors.empty or "error_type" not in errors.columns:
        return {}
    return {str(key): int(value) for key, value in errors["error_type"].value_counts().sort_index().items()}


def _can_retry(error_type: str) -> bool:
    return error_type in {"connection", "timeout", "symbol_timeout", "empty_market_data", "non_numeric_market_data", "provider_error"}


def _has_cache_hit(
    cache: LocalCsvCache,
    provider: str,
    symbol: str,
    start_date: str,
    end_date: str,
    adjusted: bool,
) -> bool:
    return bool(
        _cache_coverage_details(cache, provider, symbol, start_date, end_date, adjusted)["coverage_ok"]
    )


def _cache_coverage_details(
    cache: LocalCsvCache,
    provider: str,
    symbol: str,
    start_date: str,
    end_date: str,
    adjusted: bool,
) -> dict[str, object]:
    return cache.market_data_coverage_details(
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
    errors_path = Path(config.failed_symbols_output) if config.failed_symbols_output else output_dir / f"cache_prewarm_errors_{safe_date}.csv"
    errors_path.parent.mkdir(parents=True, exist_ok=True)
    errors.to_csv(errors_path, index=False, encoding="utf-8-sig")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    paths = {"summary_json": str(summary_path.resolve()), "errors_csv": str(errors_path.resolve())}
    if config.progress_log:
        paths["progress_log"] = str(Path(config.progress_log).resolve())
    return paths


def _progress_event(
    index: int,
    total: int,
    symbol: str,
    cache_hit: bool,
    coverage_ok: bool,
    fetch_attempted: bool,
    status: str,
    error_type: str = "",
) -> dict[str, object]:
    return {
        "index": int(index),
        "total": int(total),
        "symbol": symbol,
        "cache_hit": bool(cache_hit),
        "coverage_ok": bool(coverage_ok),
        "fetch_attempted": bool(fetch_attempted),
        "status": status,
        "error_type": error_type,
    }


def _emit_progress(config: CachePrewarmConfig, event: dict[str, object]) -> None:
    if not config.progress_log:
        return
    line = json.dumps(event, ensure_ascii=False, sort_keys=True)
    print(line, flush=True)
    log_path = Path(config.progress_log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _chunks(symbols: list[dict[str, str]], batch_size: int) -> list[list[dict[str, str]]]:
    return [symbols[index : index + batch_size] for index in range(0, len(symbols), batch_size)]


def _date(value: str) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"Invalid date: {value}")
    return parsed.strftime("%Y-%m-%d")


def _effective_start_date(config: CachePrewarmConfig) -> str:
    if config.include_lookback_days <= 0:
        return _date(config.start_date)
    requested = _date(config.requested_start_date or config.start_date)
    return (pd.Timestamp(requested) - pd.Timedelta(days=config.include_lookback_days)).strftime("%Y-%m-%d")


def _validate_config(config: CachePrewarmConfig) -> None:
    if config.limit is not None and config.limit <= 0:
        raise ValueError("limit must be positive.")
    if config.offset < 0:
        raise ValueError("offset cannot be negative.")
    if config.batch_size <= 0:
        raise ValueError("batch_size must be positive.")
    if config.sleep_seconds < 0:
        raise ValueError("sleep_seconds cannot be negative.")
    if config.retry < 0:
        raise ValueError("retry cannot be negative.")
    if config.include_lookback_days < 0:
        raise ValueError("include_lookback_days cannot be negative.")
    if config.retry_only and not config.symbols:
        raise ValueError("retry_only requires symbols or a failed symbols file.")
    if config.max_errors is not None and config.max_errors <= 0:
        raise ValueError("max_errors must be positive when provided.")
    if config.symbol_timeout_seconds is not None and config.symbol_timeout_seconds <= 0:
        raise ValueError("symbol_timeout_seconds must be positive when provided.")
    if config.max_consecutive_symbol_timeouts is not None and config.max_consecutive_symbol_timeouts <= 0:
        raise ValueError("max_consecutive_symbol_timeouts must be positive when provided.")
    if pd.Timestamp(_effective_start_date(config)) > pd.Timestamp(_date(config.end_date)):
        raise ValueError("start_date must be on or before end_date.")
