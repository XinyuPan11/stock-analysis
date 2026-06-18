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

from stock_analysis.validation.forward_expansion import ForwardExpansionConfig, build_forward_expansion_plan, write_forward_expansion_plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a Phase 2.8.1 controlled 2024 forward expansion plan. No provider access.")
    parser.add_argument("--outputs-dir", default=str(REPO_ROOT / "outputs"))
    parser.add_argument("--cache-dir", default=str(REPO_ROOT / "data" / "cache" / "daily-use"))
    parser.add_argument("--as-of-date", default="2024-01-31")
    parser.add_argument("--benchmark", default="CSI300")
    parser.add_argument("--provider", default="baostock")
    parser.add_argument("--recommended-limit", type=int, default=50)
    args = parser.parse_args()

    plan = build_forward_expansion_plan(
        ForwardExpansionConfig(
            outputs_dir=args.outputs_dir,
            cache_dir=args.cache_dir,
            as_of_date=args.as_of_date,
            benchmark=args.benchmark,
            provider=args.provider,
            recommended_limit=args.recommended_limit,
        )
    )
    paths = write_forward_expansion_plan(plan, args.outputs_dir)
    print(json.dumps({"status": "ok", "provider_access": False, "paths": paths, "batch_count": len(plan["batches"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
