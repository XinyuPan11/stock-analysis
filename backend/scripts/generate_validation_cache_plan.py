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

from stock_analysis.validation.cache_plan import build_validation_cache_plan, default_output_file, write_cache_plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a read-only symbol plan for Phase 2.7.2 future-window cache preparation.")
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--horizon-days", type=int, required=True)
    parser.add_argument("--outputs-dir", default=str(REPO_ROOT / "outputs"))
    parser.add_argument("--cache-dir", default=str(REPO_ROOT / "data" / "cache" / "daily-use"))
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--benchmark", default="CSI300")
    parser.add_argument("--provider", default="baostock")
    parser.add_argument("--target-end-date", default=None)
    parser.add_argument("--output-file", default=None)
    args = parser.parse_args()

    limit = None if args.limit <= 0 else args.limit
    plan = build_validation_cache_plan(
        as_of_date=args.as_of_date,
        horizon_days=args.horizon_days,
        outputs_dir=args.outputs_dir,
        cache_dir=args.cache_dir,
        benchmark=args.benchmark,
        provider=args.provider,
        limit=limit,
        target_end_date=args.target_end_date,
    )
    output_file = Path(args.output_file) if args.output_file else default_output_file(args.outputs_dir, args.as_of_date, args.horizon_days, limit)
    paths = write_cache_plan(plan, output_file)
    print(json.dumps({"status": "ok", "paths": paths, "summary": {key: plan[key] for key in ["as_of_date", "horizon_days", "target_end_date", "symbol_count", "missing_future_count", "ok_count", "benchmark_symbol"]}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
