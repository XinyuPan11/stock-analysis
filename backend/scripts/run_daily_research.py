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
from stock_analysis.data.providers import AkShareProvider, BaoStockProvider, MarketDataProvider, TushareProvider
from stock_analysis.data.service import MarketDataService
from stock_analysis.research.pipeline import ResearchPipelineConfig, run_research_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Phase 1 daily A-share research pipeline.")
    parser.add_argument("--provider", choices=["akshare", "baostock", "tushare"], default="baostock")
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    parser.add_argument("--lookback-days", type=int, default=None)
    parser.add_argument("--lookback-years", type=int, default=None)
    parser.add_argument("--benchmark", choices=["CSI300"], default="CSI300")
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--cache-dir", default=str(REPO_ROOT / "data" / "cache" / "daily-research"))
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "outputs" / "daily"))
    args = parser.parse_args()

    start_date = _resolve_start_date(args.start_date, args.end_date, args.lookback_days, args.lookback_years)
    provider = _build_provider(args.provider)
    service = MarketDataService(provider=provider, cache=LocalCsvCache(cache_dir=args.cache_dir))
    result = run_research_pipeline(
        service,
        ResearchPipelineConfig(
            start_date=start_date,
            end_date=args.end_date,
            provider=provider.source,
            benchmark=args.benchmark,
            top_n=args.top_n,
            limit=args.limit,
            output_dir=args.output_dir,
        ),
    )

    payload = {
        "status": "ok",
        "provider": provider.source,
        "start_date": start_date,
        "end_date": args.end_date,
        "benchmark": args.benchmark,
        "top_n": args.top_n,
        "limit": args.limit,
        "cache_dir": str(Path(args.cache_dir).resolve()),
        "output_dir": str(Path(args.output_dir).resolve()),
        "summary": result.summary,
        "fetch_errors": result.fetch_errors[:20],
        "candidates": _records(result.candidates),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


def _resolve_start_date(
    start_date: str | None,
    end_date: str,
    lookback_days: int | None,
    lookback_years: int | None,
) -> str:
    parsed_end = pd.to_datetime(end_date, errors="coerce")
    if pd.isna(parsed_end):
        raise ValueError(f"Invalid end_date: {end_date}")
    if start_date:
        parsed_start = pd.to_datetime(start_date, errors="coerce")
        if pd.isna(parsed_start):
            raise ValueError(f"Invalid start_date: {start_date}")
        return parsed_start.strftime("%Y-%m-%d")
    if lookback_days is not None:
        if lookback_days <= 0:
            raise ValueError("lookback-days must be positive.")
        return (parsed_end - pd.Timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    if lookback_years is not None:
        if lookback_years <= 0:
            raise ValueError("lookback-years must be positive.")
        return (parsed_end - pd.DateOffset(years=lookback_years)).strftime("%Y-%m-%d")
    return (parsed_end - pd.DateOffset(years=1)).strftime("%Y-%m-%d")


def _build_provider(name: str) -> MarketDataProvider:
    if name == "akshare":
        return AkShareProvider()
    if name == "baostock":
        return BaoStockProvider()
    if name == "tushare":
        return TushareProvider()
    raise ValueError(f"Unsupported provider: {name}")


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [{key: _clean(value) for key, value in row.items()} for row in frame.to_dict(orient="records")]


def _clean(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return _clean(value.item())
    return value


if __name__ == "__main__":
    raise SystemExit(main())
