from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.data.cache import LocalCsvCache
from stock_analysis.data.providers import AkShareProvider, BaoStockProvider, MarketDataProvider, TushareProvider
from stock_analysis.data.service import MarketDataService
from stock_analysis.research.ashare_filters import FilterConfig, filter_universe


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a small real-data smoke test for A-share candidate filters.")
    parser.add_argument("--provider", choices=["akshare", "baostock", "tushare"], default="baostock")
    parser.add_argument("--start-date", default="2024-01-01")
    parser.add_argument("--end-date", default="2024-01-31")
    parser.add_argument("--cache-dir", default=str(REPO_ROOT / "data" / "cache"))
    parser.add_argument("--limit", type=int, default=50, help="Maximum universe rows to fetch daily bars for.")
    parser.add_argument("--min-avg-amount-20d", type=float, default=20_000_000)
    args = parser.parse_args()

    provider = _build_provider(args.provider)
    service = MarketDataService(provider=provider, cache=LocalCsvCache(cache_dir=args.cache_dir))

    universe = service.get_stock_universe().head(args.limit).copy()
    frames: list[pd.DataFrame] = []
    fetch_errors: list[dict[str, str]] = []
    for symbol in universe["symbol"].tolist():
        try:
            frames.append(service.get_stock_daily(symbol, args.start_date, args.end_date))
        except Exception as exc:  # smoke script should report all sample failures.
            fetch_errors.append({"symbol": str(symbol), "error": str(exc)})

    daily_bars = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    result = filter_universe(
        universe,
        daily_bars,
        config=FilterConfig(
            as_of_date=args.end_date,
            min_avg_amount_20d=args.min_avg_amount_20d,
        ),
    )

    output = {
        "status": "ok",
        "provider": provider.source,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "cache_dir": str(Path(args.cache_dir).resolve()),
        "sample_limit": args.limit,
        "fetched_daily_symbols": len(frames),
        "fetch_errors": fetch_errors[:10],
        "stats": result.stats,
        "warnings": list(result.warnings),
        "passed_sample": result.passed_universe.head(10).to_dict(orient="records"),
        "filtered_sample": result.filtered_stocks.head(10).to_dict(orient="records"),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
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
