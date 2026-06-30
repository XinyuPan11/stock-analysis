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

from stock_analysis.validation.unseen_window_readiness import (  # noqa: E402
    UnseenWindowReadinessConfig,
    check_unseen_window_readiness,
    write_unseen_window_readiness,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check Phase 2.19 proposed U1 technical readiness without reading "
            "unseen outcomes or accessing providers."
        )
    )
    parser.add_argument("--outputs-dir", default=str(REPO_ROOT / "outputs"))
    parser.add_argument(
        "--cache-dir", default=str(REPO_ROOT / "data" / "cache" / "daily-use")
    )
    parser.add_argument("--provider", default="baostock")
    parser.add_argument("--benchmark", default="CSI300")
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--write-output", action="store_true")
    args = parser.parse_args()

    config = UnseenWindowReadinessConfig(
        outputs_dir=args.outputs_dir,
        cache_dir=args.cache_dir,
        provider=args.provider,
        benchmark=args.benchmark,
        limit=args.limit,
    )
    result = check_unseen_window_readiness(config)
    if args.write_output:
        result["output_files"] = write_unseen_window_readiness(
            result, args.outputs_dir
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
