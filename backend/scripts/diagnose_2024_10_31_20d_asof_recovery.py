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

from stock_analysis.validation.asof_recovery import (  # noqa: E402
    ControlledAsOfRecoveryConfig,
    TARGET_AS_OF_DATE,
    TARGET_HORIZON_DAYS,
    diagnose_controlled_2024_10_31_20d_recovery,
)
from stock_analysis.validation.walk_forward import sanitize_for_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Diagnose the controlled Phase 2.8.7 2024-10-31 20d as-of recovery. "
            "This command is target-locked and never accesses providers."
        )
    )
    parser.add_argument("--outputs-dir", default=str(REPO_ROOT / "outputs"))
    parser.add_argument("--cache-dir", default=str(REPO_ROOT / "data" / "cache" / "daily-use"))
    parser.add_argument("--provider", default="baostock")
    parser.add_argument("--benchmark", default="CSI300")
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--min-valid-count", type=int, default=50)
    parser.add_argument("--min-coverage-rate", type=float, default=0.7)
    parser.add_argument("--write-output", action="store_true")
    args = parser.parse_args()

    result = diagnose_controlled_2024_10_31_20d_recovery(
        ControlledAsOfRecoveryConfig(
            outputs_dir=args.outputs_dir,
            cache_dir=args.cache_dir,
            provider=args.provider,
            benchmark=args.benchmark,
            limit=None if args.limit <= 0 else args.limit,
            min_valid_count=args.min_valid_count,
            min_coverage_rate=args.min_coverage_rate,
            write_output=args.write_output,
        )
    )
    result["target_locked"] = {
        "as_of_date": TARGET_AS_OF_DATE,
        "horizon_days": TARGET_HORIZON_DAYS,
    }
    print(json.dumps(sanitize_for_json(result), ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
