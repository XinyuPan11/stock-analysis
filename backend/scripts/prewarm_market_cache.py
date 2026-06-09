from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.data.cache import LocalCsvCache
from stock_analysis.data.cache_prewarm import CachePrewarmConfig, load_symbols_file, run_cache_prewarm
from stock_analysis.data.providers import AkShareProvider, BaoStockProvider, MarketDataProvider, TushareProvider
from stock_analysis.data.service import MarketDataService


def main() -> int:
    parser = argparse.ArgumentParser(description="Prewarm local A-share daily market-data cache.")
    parser.add_argument("--provider", choices=["akshare", "baostock", "tushare"], default="baostock")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--cache-dir", default=str(REPO_ROOT / "data" / "cache" / "prewarm"))
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "outputs" / "cache"))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--max-errors", type=int, default=None)
    parser.add_argument("--retry", type=int, default=0)
    parser.add_argument("--symbols-file", default=None)
    args = parser.parse_args()

    provider = _build_provider(args.provider)
    cache = LocalCsvCache(cache_dir=args.cache_dir)
    service = MarketDataService(provider=provider, cache=cache)
    symbols = load_symbols_file(args.symbols_file) if args.symbols_file else ()
    result = run_cache_prewarm(
        service,
        CachePrewarmConfig(
            provider=provider.source,
            start_date=args.start_date,
            end_date=args.end_date,
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
