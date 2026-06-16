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

from stock_analysis.validation.list_performance import SUPPORTED_LIST_IDS
from stock_analysis.validation.walk_forward import WalkForwardConfig, run_walk_forward_validation


def main() -> int:
    parser = argparse.ArgumentParser(description="Run read-only Phase 2.7.2 walk-forward validation from existing outputs/cache.")
    parser.add_argument("--start-date", default="", help="Reserved for multi-date validation; not used by the first single as-of implementation.")
    parser.add_argument("--end-date", default="", help="Reserved for multi-date validation; not used by the first single as-of implementation.")
    parser.add_argument("--as-of-date", required=True, help="Fixed research view date, for example 2024-01-31.")
    parser.add_argument("--horizon-days", type=int, default=20, help="Future trading-day horizon. Phase 2.7.2 normally uses 20 or 60.")
    parser.add_argument("--benchmark", default="CSI300", help="Cached benchmark symbol, default CSI300.")
    parser.add_argument("--outputs-dir", default=str(REPO_ROOT / "outputs"), help="Existing outputs directory.")
    parser.add_argument("--cache-dir", default=str(REPO_ROOT / "data" / "cache" / "daily-use"), help="Existing local cache directory.")
    parser.add_argument("--list-ids", default="", help="Comma-separated list IDs. Defaults to supported Phase 2.7 lists.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum symbols to evaluate. Use 0 for no limit.")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Default mode: calculate and print summary without writing outputs.")
    parser.add_argument("--write-output", action="store_true", help="Write validation files under outputs/validation.")
    args = parser.parse_args()

    list_ids = tuple(item.strip() for item in args.list_ids.split(",") if item.strip())
    config = WalkForwardConfig(
        as_of_date=args.as_of_date,
        horizon_days=args.horizon_days,
        benchmark=args.benchmark,
        outputs_dir=args.outputs_dir,
        cache_dir=args.cache_dir,
        list_ids=list_ids or tuple(SUPPORTED_LIST_IDS),
        limit=None if args.limit == 0 else args.limit,
        dry_run=not args.write_output,
    )
    result = run_walk_forward_validation(config)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    outputs = result.get("outputs")
    if outputs:
        print(json.dumps({"outputs": outputs}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
