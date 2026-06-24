from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.data.cache import LocalCsvCache
from stock_analysis.data.cache_prewarm import CachePrewarmConfig, load_symbols_file, run_cache_prewarm
from stock_analysis.data.providers import AkShareProvider, BaoStockProvider, MarketDataProvider, TushareProvider
from stock_analysis.data.service import MarketDataService


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prewarm local A-share daily market-data cache.")
    parser.add_argument("--provider", choices=["akshare", "baostock", "tushare"], default="baostock")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--cache-dir", default=str(REPO_ROOT / "data" / "cache" / "prewarm"))
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "outputs" / "cache"))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--max-errors", type=int, default=None)
    parser.add_argument("--retry", type=int, default=0)
    parser.add_argument("--symbols-file", default=None)
    parser.add_argument("--failed-symbols-file", default=None)
    parser.add_argument("--retry-only", action="store_true")
    parser.add_argument("--include-lookback-days", type=int, default=0)
    parser.add_argument("--symbol-timeout-seconds", type=float, default=None)
    parser.add_argument("--max-consecutive-symbol-timeouts", type=int, default=None)
    parser.add_argument("--failed-symbols-output", default=None)
    parser.add_argument("--progress-log", default=None)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()

    provider = _build_provider(args.provider)
    cache = LocalCsvCache(cache_dir=args.cache_dir)
    service = MarketDataService(provider=provider, cache=cache)
    symbols_file = args.failed_symbols_file or args.symbols_file
    if args.retry_only and not symbols_file:
        raise ValueError("--retry-only requires --failed-symbols-file or --symbols-file.")
    symbols = load_symbols_file(symbols_file) if symbols_file else ()
    effective_start_date = _effective_start_date(args.start_date, args.include_lookback_days)
    result = run_cache_prewarm(
        service,
        CachePrewarmConfig(
            provider=provider.source,
            start_date=effective_start_date,
            end_date=args.end_date,
            requested_start_date=args.start_date,
            include_lookback_days=args.include_lookback_days,
            limit=args.limit,
            offset=args.offset,
            batch_size=args.batch_size,
            cache_dir=args.cache_dir,
            output_dir=args.output_dir,
            resume=args.resume,
            sleep_seconds=args.sleep_seconds,
            max_errors=args.max_errors,
            retry=args.retry,
            symbols=symbols,
            retry_only=args.retry_only,
            symbol_timeout_seconds=args.symbol_timeout_seconds,
            max_consecutive_symbol_timeouts=args.max_consecutive_symbol_timeouts,
            failed_symbols_output=args.failed_symbols_output,
            progress_log=args.progress_log,
        ),
    )

    payload = {
        "status": "ok",
        "summary": result.summary,
        "errors": result.errors.to_dict(orient="records")[:20],
        "output_paths": result.output_paths,
    }
    print(json.dumps(_clean(payload), ensure_ascii=False, indent=2, allow_nan=False))
    return 0


def _build_provider(name: str) -> MarketDataProvider:
    if name == "akshare":
        return AkShareProvider()
    if name == "baostock":
        return BaoStockProvider()
    if name == "tushare":
        return TushareProvider()
    raise ValueError(f"Unsupported provider: {name}")


def _effective_start_date(start_date: str, include_lookback_days: int) -> str:
    if include_lookback_days < 0:
        raise ValueError("--include-lookback-days cannot be negative.")
    parsed = pd.to_datetime(start_date, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"Invalid --start-date: {start_date}")
    return (parsed - pd.Timedelta(days=include_lookback_days)).strftime("%Y-%m-%d")


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if hasattr(value, "item"):
        return _clean(value.item())
    if value != value:
        return None
    return value


if __name__ == "__main__":
    raise SystemExit(main())
