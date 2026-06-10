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
from stock_analysis.data.constants import CORE_INDEX_CODES
from stock_analysis.data.providers import AkShareProvider, BaoStockProvider, MarketDataProvider, TushareProvider
from stock_analysis.data.service import MarketDataService
from stock_analysis.research.factors import FACTOR_OUTPUT_COLUMNS, calculate_stock_factors


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a real-data smoke test for Phase 1 factor calculations.")
    parser.add_argument("--provider", choices=["akshare", "baostock", "tushare"], default="baostock")
    parser.add_argument("--symbol", default="sz.000001")
    parser.add_argument("--benchmark", choices=["CSI300"], default="CSI300")
    parser.add_argument("--start-date", default="2023-01-01")
    parser.add_argument("--end-date", default="2024-01-31")
    parser.add_argument("--cache-dir", default=str(REPO_ROOT / "data" / "cache"))
    args = parser.parse_args()

    provider = _build_provider(args.provider)
    service = MarketDataService(provider=provider, cache=LocalCsvCache(cache_dir=args.cache_dir))

    stock_frame = service.get_stock_daily(args.symbol, args.start_date, args.end_date)
    benchmark_frame = service.get_index_daily(args.benchmark, args.start_date, args.end_date)
    factor_frame = calculate_stock_factors(stock_frame, benchmark_frame, as_of_date=args.end_date)
    factor_row = factor_frame.iloc[0].to_dict()

    output = {
        "status": "ok",
        "provider": provider.source,
        "symbol": args.symbol,
        "benchmark": args.benchmark,
        "benchmark_display_name": CORE_INDEX_CODES[args.benchmark]["display_name"],
        "start_date": args.start_date,
        "end_date": args.end_date,
        "stock_rows": len(stock_frame),
        "benchmark_rows": len(benchmark_frame),
        "factor_schema": FACTOR_OUTPUT_COLUMNS,
        "factors": {key: _clean_json_value(value) for key, value in factor_row.items()},
        "cache_dir": str(Path(args.cache_dir).resolve()),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


def _build_provider(name: str) -> MarketDataProvider:
    if name == "akshare":
        return AkShareProvider()
    if name == "baostock":
        return BaoStockProvider()
    if name == "tushare":
        return TushareProvider()
    raise ValueError(f"Unsupported provider: {name}")


def _clean_json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, bool, int, float)):
        if isinstance(value, float) and pd.isna(value):
            return None
        return value
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return _clean_json_value(value.item())
    return value


if __name__ == "__main__":
    raise SystemExit(main())
