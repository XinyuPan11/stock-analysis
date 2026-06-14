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

from stock_analysis.backtesting.walk_forward import WalkForwardConfig, run_walk_forward_backtest
from stock_analysis.data.cache import LocalCsvCache
from stock_analysis.data.providers import AkShareProvider, BaoStockProvider, MarketDataProvider, TushareProvider
from stock_analysis.data.service import MarketDataService


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a Phase 1 walk-forward A-share Top N backtest.")
    parser.add_argument("--provider", choices=["akshare", "baostock", "tushare"], default="baostock")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--lookback-days", type=int, default=120)
    parser.add_argument("--rebalance-frequency", choices=["monthly", "weekly"], default="monthly")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--benchmark", choices=["CSI300"], default="CSI300")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--batch-id", default="")
    parser.add_argument("--retry", type=int, default=0)
    parser.add_argument("--cache-dir", default=str(REPO_ROOT / "data" / "cache" / "backtest"))
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "outputs" / "backtests"))
    parser.add_argument("--error-output-dir", default=str(REPO_ROOT / "outputs" / "errors"))
    parser.add_argument("--transaction-cost-bps", type=float, default=10.0)
    parser.add_argument("--progress-log", default="")
    parser.add_argument("--progress-every", type=int, default=100)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()

    provider = _build_provider(args.provider)
    service = MarketDataService(provider=provider, cache=LocalCsvCache(cache_dir=args.cache_dir))
    result = run_walk_forward_backtest(
        service,
        WalkForwardConfig(
            start_date=args.start_date,
            end_date=args.end_date,
            lookback_days=args.lookback_days,
            rebalance_frequency=args.rebalance_frequency,
            top_n=args.top_n,
            benchmark=args.benchmark,
            limit=args.limit,
            offset=args.offset,
            batch_id=args.batch_id,
            retry=args.retry,
            cache_dir=args.cache_dir,
            output_dir=args.output_dir,
            error_output_dir=args.error_output_dir,
            transaction_cost_bps=args.transaction_cost_bps,
            provider=provider.source,
            progress_log_path=args.progress_log,
            progress_every=args.progress_every,
        ),
    )

    payload = {
        "status": "ok",
        "provider": provider.source,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "benchmark": args.benchmark,
        "top_n": args.top_n,
        "limit": args.limit,
        "offset": args.offset,
        "batch_id": args.batch_id,
        "retry": args.retry,
        "cache_dir": str(Path(args.cache_dir).resolve()),
        "output_dir": str(Path(args.output_dir).resolve()),
        "error_output_dir": str(Path(args.error_output_dir).resolve()),
        "progress_log": str(Path(args.progress_log).resolve()) if args.progress_log else "",
        "progress_every": args.progress_every,
        "summary": result.summary,
        "output_paths": result.output_paths,
        "fetch_errors": result.fetch_errors[:20],
        "skipped_symbols": result.skipped_symbols[:20],
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
