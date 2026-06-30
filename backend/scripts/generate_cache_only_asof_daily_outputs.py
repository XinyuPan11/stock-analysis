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

from stock_analysis.research.cache_only_asof import (  # noqa: E402
    CacheOnlyAsOfConfig,
    CacheOnlyDataMissingError,
    generate_cache_only_asof_daily_outputs,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate one historical as-of daily candidates/factors set from "
            "local cache only. Missing cache fails closed."
        )
    )
    parser.add_argument("--date", required=True, help="Explicit as-of date YYYY-MM-DD.")
    parser.add_argument("--outputs-dir", default=str(REPO_ROOT / "outputs"))
    parser.add_argument(
        "--cache-dir", default=str(REPO_ROOT / "data" / "cache" / "daily-use")
    )
    parser.add_argument("--provider", choices=["baostock"], default="baostock")
    parser.add_argument("--benchmark", default="CSI300")
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--symbols-file", default=None)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--lookback-years", type=int, default=1)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = generate_cache_only_asof_daily_outputs(
            CacheOnlyAsOfConfig(
                as_of_date=args.date,
                outputs_dir=args.outputs_dir,
                cache_dir=args.cache_dir,
                provider=args.provider,
                benchmark=args.benchmark,
                limit=args.limit,
                symbols_file=args.symbols_file,
                top_n=args.top_n,
                lookback_years=args.lookback_years,
            )
        )
    except (CacheOnlyDataMissingError, ValueError, RuntimeError) as exc:
        payload = (
            exc.as_dict()
            if isinstance(exc, CacheOnlyDataMissingError)
            else {
                "status": "blocked_invalid_request",
                "cache_only": True,
                "provider_access": False,
                "error": str(exc),
            }
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
