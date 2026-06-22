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

from stock_analysis.validation.strategy_family_experiment import StrategyFamilyExperimentConfig, run_strategy_family_experiments
from stock_analysis.validation.walk_forward import sanitize_for_json


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Phase 2.8.2 research-only strategy family experiments from existing outputs. No provider access is used."
    )
    parser.add_argument("--as-of-date", required=True, help="Fixed research view date, for example 2024-01-31.")
    parser.add_argument("--horizon-days", type=int, default=120, help="Future validation horizon.")
    parser.add_argument("--outputs-dir", default=str(REPO_ROOT / "outputs"), help="Existing outputs directory.")
    parser.add_argument("--cache-dir", default=str(REPO_ROOT / "data" / "cache" / "daily-use"), help="Reserved for provenance; provider access is not used.")
    parser.add_argument("--profile-ids", default="", help="Comma-separated strategy family IDs. Defaults to all profiles.")
    parser.add_argument("--write-output", action="store_true", help="Write JSON and markdown experiment outputs. Default is dry-run.")
    args = parser.parse_args()

    profile_ids = tuple(item.strip() for item in args.profile_ids.split(",") if item.strip())
    result = run_strategy_family_experiments(
        StrategyFamilyExperimentConfig(
            as_of_date=args.as_of_date,
            horizon_days=args.horizon_days,
            outputs_dir=args.outputs_dir,
            cache_dir=args.cache_dir,
            profile_ids=profile_ids,
            dry_run=not args.write_output,
        )
    )
    print(json.dumps(sanitize_for_json(result["summary"]), ensure_ascii=False, indent=2, allow_nan=False))
    outputs = result.get("outputs")
    if outputs:
        print(json.dumps({"outputs": outputs}, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

