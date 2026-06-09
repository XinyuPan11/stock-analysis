from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.analysis.price_analysis import calculate_return_summary
from stock_analysis.data.cache import FileDataFrameCache
from stock_analysis.data.constants import CORE_INDEX_CODES
from stock_analysis.data.providers import AkShareProvider, BaoStockProvider, MarketDataProvider, TushareProvider
from stock_analysis.data.service import MarketDataService


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a real market-data smoke test through the provider layer.")
    parser.add_argument("--provider", choices=["akshare", "baostock", "tushare"], default="akshare")
    parser.add_argument("--symbol", default="000001", help="Provider-specific A-share symbol, e.g. 000001 for AKShare.")
    parser.add_argument("--index-code", choices=sorted(CORE_INDEX_CODES), default="CSI300")
    parser.add_argument("--start-date", default="2024-01-01")
    parser.add_argument("--end-date", default="2024-01-31")
    parser.add_argument("--cache-dir", default=str(ROOT / ".cache" / "market_data"))
    parser.add_argument("--cache-ttl-seconds", type=int, default=3600)
    args = parser.parse_args()

    provider = _build_provider(args.provider)
    service = MarketDataService(
        provider=provider,
        cache=FileDataFrameCache(cache_dir=args.cache_dir, ttl_seconds=args.cache_ttl_seconds),
    )

    stock_frame = service.get_stock_daily(args.symbol, args.start_date, args.end_date)
    index_frame = service.get_index_daily(args.index_code, args.start_date, args.end_date)

    result = {
        "status": "ok",
        "provider": provider.source,
        "schema": list(stock_frame.columns),
        "stock": {
            "symbol": args.symbol,
            "rows": len(stock_frame),
            "summary": calculate_return_summary(stock_frame),
            "sample": stock_frame.head(3).to_dict(orient="records"),
        },
        "index": {
            "symbol": args.index_code,
            "display_name": CORE_INDEX_CODES[args.index_code]["display_name"],
            "rows": len(index_frame),
            "summary": calculate_return_summary(index_frame),
            "sample": index_frame.head(3).to_dict(orient="records"),
        },
        "cache_dir": str(Path(args.cache_dir).resolve()),
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _build_provider(name: str) -> MarketDataProvider:
    if name == "akshare":
        return AkShareProvider()
    if name == "baostock":
        return BaoStockProvider()
    if name == "tushare":
        return TushareProvider()
    raise ValueError(f"Unsupported provider: {name}")


if __name__ == "__main__":
    raise SystemExit(main())
