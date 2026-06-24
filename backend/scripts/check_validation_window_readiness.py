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

from stock_analysis.validation.walk_forward import sanitize_for_json  # noqa: E402
from stock_analysis.validation.window_readiness import (  # noqa: E402
    ValidationWindowReadinessConfig,
    check_validation_window_readiness,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check whether one validation window is ready. This command never accesses providers."
    )
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--horizon-days", type=int, required=True)
    parser.add_argument("--outputs-dir", default=str(REPO_ROOT / "outputs"))
    parser.add_argument("--cache-dir", default=str(REPO_ROOT / "data" / "cache" / "daily-use"))
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--benchmark", default="CSI300")
    parser.add_argument("--min-valid-count", type=int, default=50)
    parser.add_argument("--min-coverage-rate", type=float, default=0.7)
    parser.add_argument("--provider", default="baostock")
    parser.add_argument("--write-output", action="store_true")
    args = parser.parse_args()

    result = check_validation_window_readiness(
        ValidationWindowReadinessConfig(
            as_of_date=args.as_of_date,
            horizon_days=args.horizon_days,
            outputs_dir=args.outputs_dir,
            cache_dir=args.cache_dir,
            limit=args.limit,
            benchmark=args.benchmark,
            min_valid_count=args.min_valid_count,
            min_coverage_rate=args.min_coverage_rate,
            provider=args.provider,
            write_output=args.write_output,
        )
    )
    print(json.dumps(sanitize_for_json(result), ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
