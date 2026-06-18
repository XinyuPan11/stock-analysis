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

from stock_analysis.validation.forward_expansion import ControlledValidationBatchConfig, run_controlled_validation_batch
from stock_analysis.validation.walk_forward import sanitize_for_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a controlled read-only validation batch. Defaults to dry-run and never accesses a provider.")
    parser.add_argument("--as-of-date", default="2024-01-31")
    parser.add_argument("--horizon-days", type=int, default=60)
    parser.add_argument("--benchmark", default="CSI300")
    parser.add_argument("--outputs-dir", default=str(REPO_ROOT / "outputs"))
    parser.add_argument("--cache-dir", default=str(REPO_ROOT / "data" / "cache" / "daily-use"))
    parser.add_argument("--limit", type=int, default=50, help="Maximum symbols to evaluate. Use 0 for no limit.")
    parser.add_argument("--write-output", action="store_true", help="Write validation outputs. Default is dry-run with no output refresh.")
    args = parser.parse_args()

    result = run_controlled_validation_batch(
        ControlledValidationBatchConfig(
            as_of_date=args.as_of_date,
            horizon_days=args.horizon_days,
            benchmark=args.benchmark,
            outputs_dir=args.outputs_dir,
            cache_dir=args.cache_dir,
            limit=None if args.limit <= 0 else args.limit,
            dry_run=not args.write_output,
        )
    )
    print(json.dumps(sanitize_for_json(result), ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
