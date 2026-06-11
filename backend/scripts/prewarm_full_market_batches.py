from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.data.cache import LocalCsvCache
from stock_analysis.data.cache_prewarm import CachePrewarmConfig, CachePrewarmResult, run_cache_prewarm
from stock_analysis.data.providers import AkShareProvider, BaoStockProvider, MarketDataProvider, TushareProvider
from stock_analysis.data.service import MarketDataService


COMPLETED_BATCH_STATUSES = {"ok", "warning", "skipped"}
BATCH_CSV_FIELDS = [
    "batch_index",
    "offset",
    "limit",
    "started_at",
    "finished_at",
    "elapsed_seconds",
    "status",
    "attempted_count",
    "success_count",
    "failed_count",
    "last_symbol",
    "error_summary",
]


@dataclass(frozen=True)
class BatchSpec:
    batch_index: int
    offset: int
    limit: int


@dataclass(frozen=True)
class FullMarketBatchPrewarmConfig:
    provider: str
    start_date: str
    end_date: str
    include_lookback_days: int = 0
    cache_dir: str | Path = "data/cache/daily-use"
    output_dir: str | Path = "outputs/cache"
    batch_limit: int = 500
    batch_size: int = 20
    sleep_seconds: float = 0.5
    retry: int = 1
    resume: bool = False
    start_offset: int = 0
    max_batches: int | None = None
    offset: int | None = None
    limit: int | None = None
    batch_timeout_seconds: int | None = 1800
    continue_on_error: bool = False


PrewarmRunner = Callable[[object, CachePrewarmConfig], CachePrewarmResult]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prewarm full-market A-share cache in resumable batches.")
    parser.add_argument("--provider", choices=["akshare", "baostock", "tushare"], default="baostock")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--include-lookback-days", type=int, default=0)
    parser.add_argument("--cache-dir", default=str(REPO_ROOT / "data" / "cache" / "daily-use"))
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "outputs" / "cache"))
    parser.add_argument("--batch-limit", type=int, default=500)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--sleep-seconds", type=float, default=0.5)
    parser.add_argument("--retry", type=int, default=1)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--start-offset", type=int, default=0)
    parser.add_argument("--max-batches", type=int, default=None)
    parser.add_argument("--offset", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-timeout-seconds", type=int, default=1800)
    parser.add_argument("--continue-on-error", action="store_true")
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    provider = _build_provider(args.provider)
    service = MarketDataService(provider=provider, cache=LocalCsvCache(cache_dir=args.cache_dir))
    summary = run_full_market_batch_prewarm(
        service,
        FullMarketBatchPrewarmConfig(
            provider=provider.source,
            start_date=args.start_date,
            end_date=args.end_date,
            include_lookback_days=args.include_lookback_days,
            cache_dir=args.cache_dir,
            output_dir=args.output_dir,
            batch_limit=args.batch_limit,
            batch_size=args.batch_size,
            sleep_seconds=args.sleep_seconds,
            retry=args.retry,
            resume=args.resume,
            start_offset=args.start_offset,
            max_batches=args.max_batches,
            offset=args.offset,
            limit=args.limit,
            batch_timeout_seconds=args.batch_timeout_seconds,
            continue_on_error=args.continue_on_error,
        ),
        prewarm_runner=_subprocess_prewarm_runner(args.batch_timeout_seconds),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not summary["failed_batches"] else 1


def run_full_market_batch_prewarm(
    service: object,
    config: FullMarketBatchPrewarmConfig,
    *,
    prewarm_runner: PrewarmRunner = run_cache_prewarm,
) -> dict[str, Any]:
    _validate_config(config)
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    universe = service.get_stock_universe()
    symbols = [str(row["symbol"]) for _, row in universe.dropna(subset=["symbol"]).iterrows()]
    total_symbols = len(symbols)
    specs = build_batch_specs(
        total_symbols,
        batch_limit=config.batch_limit,
        start_offset=config.start_offset,
        max_batches=config.max_batches,
        offset=config.offset,
        limit=config.limit,
    )
    paths = _output_paths(output_dir, config.end_date)
    existing_batches = _load_existing_batches(paths["json"]) if config.resume else {}
    records = dict(existing_batches)
    run_started = _now()
    _write_outputs(paths, _build_summary(config, total_symbols, specs, records, run_started, _now()))

    for spec in specs:
        key = _batch_key(spec.offset, spec.limit)
        existing = records.get(key)
        if config.resume and existing and existing.get("status") in COMPLETED_BATCH_STATUSES:
            skipped = _skipped_record(spec, existing)
            records[key] = skipped
            _write_outputs(paths, _build_summary(config, total_symbols, specs, records, run_started, _now()))
            continue

        record = _run_one_batch(service, config, spec, symbols, prewarm_runner)
        records[key] = record
        _write_outputs(paths, _build_summary(config, total_symbols, specs, records, run_started, _now()))
        if record["status"] == "failed" and not config.continue_on_error:
            break

    return _build_summary(config, total_symbols, specs, records, run_started, _now())


def build_batch_specs(
    total_symbols: int,
    *,
    batch_limit: int,
    start_offset: int = 0,
    max_batches: int | None = None,
    offset: int | None = None,
    limit: int | None = None,
) -> list[BatchSpec]:
    if total_symbols < 0:
        raise ValueError("total_symbols cannot be negative.")
    if batch_limit <= 0:
        raise ValueError("batch_limit must be positive.")
    if max_batches is not None and max_batches <= 0:
        raise ValueError("max_batches must be positive when provided.")
    if (offset is None) != (limit is None):
        raise ValueError("--offset and --limit must be provided together for a single-batch run.")
    if offset is not None and limit is not None:
        if offset < 0:
            raise ValueError("offset cannot be negative.")
        if limit <= 0:
            raise ValueError("limit must be positive.")
        if offset >= total_symbols:
            return []
        return [BatchSpec(batch_index=1, offset=offset, limit=min(limit, total_symbols - offset))]
    if start_offset < 0:
        raise ValueError("start_offset cannot be negative.")
    specs: list[BatchSpec] = []
    current_offset = start_offset
    while current_offset < total_symbols:
        if max_batches is not None and len(specs) >= max_batches:
            break
        specs.append(
            BatchSpec(
                batch_index=len(specs) + 1,
                offset=current_offset,
                limit=min(batch_limit, total_symbols - current_offset),
            )
        )
        current_offset += batch_limit
    return specs


def _run_one_batch(
    service: object,
    config: FullMarketBatchPrewarmConfig,
    spec: BatchSpec,
    symbols: list[str],
    prewarm_runner: PrewarmRunner,
) -> dict[str, Any]:
    started_at = _now()
    timer = time.monotonic()
    last_symbol = _last_symbol(symbols, spec)
    try:
        result = prewarm_runner(
            service,
            CachePrewarmConfig(
                provider=config.provider,
                start_date=config.start_date,
                end_date=config.end_date,
                requested_start_date=config.start_date,
                include_lookback_days=config.include_lookback_days,
                limit=spec.limit,
                offset=spec.offset,
                batch_size=config.batch_size,
                cache_dir=config.cache_dir,
                output_dir=config.output_dir,
                resume=config.resume,
                sleep_seconds=config.sleep_seconds,
                retry=config.retry,
            ),
        )
        failed_count = int(result.summary.get("error_count", 0))
        status = "warning" if failed_count or result.summary.get("stopped_early") else "ok"
        return {
            "batch_index": spec.batch_index,
            "offset": spec.offset,
            "limit": spec.limit,
            "started_at": started_at,
            "finished_at": _now(),
            "elapsed_seconds": round(time.monotonic() - timer, 3),
            "status": status,
            "attempted_count": int(result.summary.get("attempted_count", 0)),
            "success_count": int(result.summary.get("success_count", 0)),
            "failed_count": failed_count,
            "last_symbol": last_symbol,
            "error_summary": _error_summary(result.summary),
        }
    except Exception as exc:
        return {
            "batch_index": spec.batch_index,
            "offset": spec.offset,
            "limit": spec.limit,
            "started_at": started_at,
            "finished_at": _now(),
            "elapsed_seconds": round(time.monotonic() - timer, 3),
            "status": "failed",
            "attempted_count": 0,
            "success_count": 0,
            "failed_count": 0,
            "last_symbol": last_symbol,
            "error_summary": str(exc),
        }


def _skipped_record(spec: BatchSpec, existing: dict[str, Any]) -> dict[str, Any]:
    now = _now()
    return {
        **existing,
        "batch_index": spec.batch_index,
        "offset": spec.offset,
        "limit": spec.limit,
        "started_at": now,
        "finished_at": now,
        "elapsed_seconds": 0.0,
        "status": "skipped",
        "error_summary": "Skipped because a completed batch already exists and resume is enabled.",
    }


def _build_summary(
    config: FullMarketBatchPrewarmConfig,
    total_symbols: int,
    specs: list[BatchSpec],
    records_by_key: dict[str, dict[str, Any]],
    run_started: str,
    updated_at: str,
) -> dict[str, Any]:
    records = _ordered_records(records_by_key)
    completed = [record for record in records if record["status"] in COMPLETED_BATCH_STATUSES]
    failed = [record for record in records if record["status"] == "failed"]
    completed_offsets = {int(record["offset"]) for record in completed}
    expected_offsets = {spec.offset for spec in specs}
    full_market_scope = config.offset is None and config.start_offset == 0 and config.max_batches is None
    complete_offsets = expected_offsets.issubset(completed_offsets)
    full_market_complete = bool(full_market_scope and complete_offsets and _coverage_end(completed) >= total_symbols)
    next_offset = _next_offset(specs, completed_offsets, total_symbols)
    return {
        "provider": config.provider,
        "start_date": config.start_date,
        "end_date": config.end_date,
        "include_lookback_days": config.include_lookback_days,
        "batch_limit": config.batch_limit,
        "batch_size": config.batch_size,
        "batch_timeout_seconds": config.batch_timeout_seconds,
        "resume": config.resume,
        "run_started_at": run_started,
        "updated_at": updated_at,
        "total_symbols": total_symbols,
        "planned_batches": len(specs),
        "completed_batches": len(completed),
        "failed_batches": len(failed),
        "full_market_prewarm_complete": full_market_complete,
        "total_attempted": sum(int(record.get("attempted_count", 0)) for record in records),
        "total_success": sum(int(record.get("success_count", 0)) for record in records),
        "total_failed": sum(int(record.get("failed_count", 0)) for record in records),
        "last_completed_offset": max((int(record["offset"]) for record in completed), default=None),
        "next_offset": next_offset,
        "batches": records,
        "output_paths": {key: str(value.resolve()) for key, value in _output_paths(Path(config.output_dir), config.end_date).items()},
    }


def _write_outputs(paths: dict[str, Path], summary: dict[str, Any]) -> None:
    paths["json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    with paths["csv"].open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=BATCH_CSV_FIELDS)
        writer.writeheader()
        for record in summary["batches"]:
            writer.writerow({field: record.get(field, "") for field in BATCH_CSV_FIELDS})
    log_lines = [
        f"provider={summary['provider']} end_date={summary['end_date']} updated_at={summary['updated_at']}",
        f"planned_batches={summary['planned_batches']} completed_batches={summary['completed_batches']} failed_batches={summary['failed_batches']} next_offset={summary['next_offset']}",
    ]
    for record in summary["batches"]:
        log_lines.append(
            "batch_index={batch_index} offset={offset} limit={limit} status={status} "
            "attempted={attempted_count} success={success_count} failed={failed_count} "
            "last_symbol={last_symbol} elapsed_seconds={elapsed_seconds} error_summary={error_summary}".format(**record)
        )
    paths["log"].write_text("\n".join(log_lines) + "\n", encoding="utf-8")


def _load_existing_batches(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    batches = payload.get("batches", [])
    return {_batch_key(int(batch["offset"]), int(batch["limit"])): batch for batch in batches}


def _output_paths(output_dir: Path, end_date: str) -> dict[str, Path]:
    safe_date = _safe_date(end_date)
    return {
        "json": output_dir / f"full_market_prewarm_batches_{safe_date}.json",
        "csv": output_dir / f"full_market_prewarm_batches_{safe_date}.csv",
        "log": output_dir / f"full_market_prewarm_batches_{safe_date}.log",
    }


def _ordered_records(records_by_key: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(records_by_key.values(), key=lambda record: (int(record["offset"]), int(record["limit"])))


def _next_offset(specs: list[BatchSpec], completed_offsets: set[int], total_symbols: int) -> int | None:
    for spec in specs:
        if spec.offset not in completed_offsets:
            return spec.offset
    return total_symbols if specs else None


def _coverage_end(records: list[dict[str, Any]]) -> int:
    return max((int(record["offset"]) + int(record["limit"]) for record in records), default=0)


def _last_symbol(symbols: list[str], spec: BatchSpec) -> str:
    if not symbols or spec.offset >= len(symbols):
        return ""
    index = min(spec.offset + spec.limit - 1, len(symbols) - 1)
    return symbols[index]


def _error_summary(summary: dict[str, Any]) -> str:
    counts = summary.get("error_type_counts") or {}
    if not counts:
        return ""
    return json.dumps(counts, ensure_ascii=False, sort_keys=True)


def _batch_key(offset: int, limit: int) -> str:
    return f"{offset}:{limit}"


def _safe_date(value: str) -> str:
    return value.replace("/", "-").replace("\\", "-")


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _validate_config(config: FullMarketBatchPrewarmConfig) -> None:
    if config.batch_limit <= 0:
        raise ValueError("batch_limit must be positive.")
    if config.batch_size <= 0:
        raise ValueError("batch_size must be positive.")
    if config.sleep_seconds < 0:
        raise ValueError("sleep_seconds cannot be negative.")
    if config.retry < 0:
        raise ValueError("retry cannot be negative.")
    if config.include_lookback_days < 0:
        raise ValueError("include_lookback_days cannot be negative.")
    if config.start_offset < 0:
        raise ValueError("start_offset cannot be negative.")
    if config.max_batches is not None and config.max_batches <= 0:
        raise ValueError("max_batches must be positive when provided.")
    if (config.offset is None) != (config.limit is None):
        raise ValueError("offset and limit must be provided together.")
    if config.offset is not None and config.offset < 0:
        raise ValueError("offset cannot be negative.")
    if config.limit is not None and config.limit <= 0:
        raise ValueError("limit must be positive.")
    if config.batch_timeout_seconds is not None and config.batch_timeout_seconds <= 0:
        raise ValueError("batch_timeout_seconds must be positive when provided.")


def _build_provider(name: str) -> MarketDataProvider:
    if name == "akshare":
        return AkShareProvider()
    if name == "baostock":
        return BaoStockProvider()
    if name == "tushare":
        return TushareProvider()
    raise ValueError(f"Unsupported provider: {name}")


def _subprocess_prewarm_runner(timeout_seconds: int | None) -> PrewarmRunner:
    def runner(service: object, config: CachePrewarmConfig) -> CachePrewarmResult:
        command = _prewarm_command(config)
        try:
            completed = subprocess.run(
                command,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"prewarm batch timed out after {timeout_seconds} seconds: {' '.join(command)}") from exc
        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            stdout = completed.stdout.strip()
            raise RuntimeError((stderr or stdout or f"prewarm batch exited with code {completed.returncode}")[-2000:])
        summary_path = Path(config.output_dir) / f"cache_prewarm_summary_{_safe_date(config.end_date)}.json"
        errors_path = Path(config.output_dir) / f"cache_prewarm_errors_{_safe_date(config.end_date)}.csv"
        if not summary_path.exists():
            raise FileNotFoundError(f"prewarm summary not found: {summary_path}")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        errors = pd.read_csv(errors_path, dtype=str) if errors_path.exists() else pd.DataFrame()
        return CachePrewarmResult(
            summary=summary,
            errors=errors,
            output_paths={"summary_json": str(summary_path.resolve()), "errors_csv": str(errors_path.resolve())},
        )

    return runner


def _prewarm_command(config: CachePrewarmConfig) -> list[str]:
    command = [
        sys.executable,
        r"backend\scripts\prewarm_market_cache.py",
        "--provider",
        config.provider,
        "--start-date",
        config.requested_start_date or config.start_date,
        "--end-date",
        config.end_date,
        "--include-lookback-days",
        str(config.include_lookback_days),
        "--limit",
        str(config.limit),
        "--offset",
        str(config.offset),
        "--batch-size",
        str(config.batch_size),
        "--cache-dir",
        str(config.cache_dir),
        "--output-dir",
        str(config.output_dir),
        "--sleep-seconds",
        str(config.sleep_seconds),
        "--retry",
        str(config.retry),
    ]
    if config.resume:
        command.append("--resume")
    return command


if __name__ == "__main__":
    raise SystemExit(main())
