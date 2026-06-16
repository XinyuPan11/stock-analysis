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

from stock_analysis.portfolio.simulator import PortfolioValidationConfig, run_portfolio_validation


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 2.7.3 research-only simulated portfolio validation from existing outputs.")
    parser.add_argument("--as-of-date", required=True, help="Fixed research view date, for example 2024-01-31.")
    parser.add_argument("--horizon-days", type=int, default=60, help="Future validation horizon, normally 20 or 60.")
    parser.add_argument("--benchmark", default="CSI300", help="Benchmark label for reporting only.")
    parser.add_argument("--outputs-dir", default=str(REPO_ROOT / "outputs"), help="Existing outputs directory.")
    parser.add_argument("--cache-dir", default=str(REPO_ROOT / "data" / "cache" / "daily-use"), help="Reserved for compatibility; provider access is not used.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum future-label rows to read. Use 0 for no limit.")
    parser.add_argument("--portfolio-ids", default="", help="Comma-separated portfolio IDs. Defaults to all Phase 2.7.3 portfolios.")
    parser.add_argument("--transaction-cost-bps", type=float, default=10.0, help="One-period transaction cost in basis points.")
    parser.add_argument("--dry-run", action="store_true", help="Print summary without writing portfolio/review/experiment outputs.")
    args = parser.parse_args()

    portfolio_ids = tuple(item.strip() for item in args.portfolio_ids.split(",") if item.strip())
    config = PortfolioValidationConfig(
        as_of_date=args.as_of_date,
        horizon_days=args.horizon_days,
        benchmark=args.benchmark,
        outputs_dir=args.outputs_dir,
        cache_dir=args.cache_dir,
        portfolio_ids=portfolio_ids,
        limit=None if args.limit == 0 else args.limit,
        transaction_cost_bps=args.transaction_cost_bps,
        dry_run=args.dry_run,
    )
    result = run_portfolio_validation(config)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    outputs = result.get("outputs")
    if outputs:
        print(json.dumps({"outputs": outputs}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
