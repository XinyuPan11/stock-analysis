from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.workflow import DailyWorkflowConfig, run_daily_workflow


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local Phase 2.5 daily research workflow.")
    parser.add_argument("--provider", choices=["akshare", "baostock", "tushare"], default="baostock")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--benchmark", choices=["CSI300"], default="CSI300")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--backtest-top-n", type=int, default=5)
    parser.add_argument("--lookback-days", type=int, default=120)
    parser.add_argument("--include-lookback-days", type=int, default=120)
    parser.add_argument("--rebalance-frequency", choices=["monthly", "weekly"], default="monthly")
    parser.add_argument("--transaction-cost-bps", type=float, default=10.0)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--sleep-seconds", type=float, default=0.5)
    parser.add_argument("--retry", type=int, default=1)
    parser.add_argument("--daily-progress-every", type=int, default=100)
    parser.add_argument("--symbol-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--cache-dir", default="data/cache/daily-use")
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--check-proxy", action="store_true")
    parser.add_argument("--skip-prewarm", action="store_true")
    parser.add_argument("--skip-research", action="store_true")
    parser.add_argument("--skip-report", action="store_true")
    parser.add_argument("--skip-backtest", action="store_true")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()

    config = DailyWorkflowConfig(
        repo_root=REPO_ROOT,
        provider=args.provider,
        start_date=args.start_date,
        end_date=args.end_date,
        benchmark=args.benchmark,
        limit=args.limit,
        top_n=args.top_n,
        backtest_top_n=args.backtest_top_n,
        lookback_days=args.lookback_days,
        include_lookback_days=args.include_lookback_days,
        rebalance_frequency=args.rebalance_frequency,
        transaction_cost_bps=args.transaction_cost_bps,
        batch_size=args.batch_size,
        sleep_seconds=args.sleep_seconds,
        retry=args.retry,
        daily_progress_every=args.daily_progress_every,
        symbol_timeout_seconds=args.symbol_timeout_seconds,
        resume=args.resume,
        cache_dir=args.cache_dir,
        output_dir=args.output_dir,
        check_proxy=args.check_proxy,
        skip_prewarm=args.skip_prewarm,
        skip_research=args.skip_research,
        skip_report=args.skip_report,
        skip_backtest=args.skip_backtest,
        serve=args.serve,
        host=args.host,
        port=args.port,
        dry_run=args.dry_run,
        continue_on_error=args.continue_on_error,
    )
    summary = run_daily_workflow(config)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not args.serve:
        print(
            "Dashboard command:\n"
            f"python backend\\scripts\\run_api.py --outputs-dir {args.output_dir} --host {args.host} --port {args.port}"
        )
    return 0 if summary["status"] in {"ok", "warning", "planned"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
