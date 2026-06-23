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

from stock_analysis.validation.multi_asof_validation import (  # noqa: E402
    DEFAULT_AS_OF_DATES,
    DEFAULT_HORIZONS,
    MultiAsOfValidationConfig,
    build_multi_asof_validation_plan,
    write_multi_asof_outputs,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Phase 2.8.4 multi-as-of validation and cache plans. This command does not access providers."
    )
    parser.add_argument("--outputs-dir", default=str(REPO_ROOT / "outputs"))
    parser.add_argument("--cache-dir", default=str(REPO_ROOT / "data" / "cache" / "daily-use"))
    parser.add_argument("--provider", default="baostock")
    parser.add_argument("--benchmark", default="CSI300")
    parser.add_argument("--as-of-dates", default=",".join(DEFAULT_AS_OF_DATES))
    parser.add_argument("--horizons", default=",".join(str(item) for item in DEFAULT_HORIZONS))
    parser.add_argument("--recommended-limit", type=int, default=50)
    args = parser.parse_args()

    as_of_dates = tuple(item.strip() for item in args.as_of_dates.split(",") if item.strip())
    horizons = tuple(int(item.strip()) for item in args.horizons.split(",") if item.strip())
    plan = build_multi_asof_validation_plan(
        MultiAsOfValidationConfig(
            outputs_dir=args.outputs_dir,
            cache_dir=args.cache_dir,
            provider=args.provider,
            benchmark=args.benchmark,
            as_of_dates=as_of_dates,
            horizons=horizons,
            recommended_limit=args.recommended_limit,
        )
    )
    paths = write_multi_asof_outputs(plan, args.outputs_dir)
    print(
        json.dumps(
            {
                "status": "ok",
                "provider_access": False,
                "prewarm_executed": False,
                "full_workflow_executed": False,
                "paths": paths,
                "as_of_count": len(as_of_dates),
                "horizon_count": len(horizons),
                "cache_requirement_count": len(plan["cache_requirements"]),
            },
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
