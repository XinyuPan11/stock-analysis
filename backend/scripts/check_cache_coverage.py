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

from stock_analysis.validation.forward_expansion import CacheCoverageConfig, check_cache_coverage, default_coverage_output, write_cache_coverage_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local cache coverage for a date range. This command never accesses a provider.")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--cache-dir", default=str(REPO_ROOT / "data" / "cache" / "daily-use"))
    parser.add_argument("--outputs-dir", default=str(REPO_ROOT / "outputs"))
    parser.add_argument("--symbols-file", default=None)
    parser.add_argument("--limit", type=int, default=50, help="Maximum symbols to inspect. Use 0 for no limit.")
    parser.add_argument("--output-file", default=None)
    parser.add_argument("--provider", default="baostock")
    args = parser.parse_args()

    limit = None if args.limit <= 0 else args.limit
    report = check_cache_coverage(
        CacheCoverageConfig(
            start_date=args.start_date,
            end_date=args.end_date,
            cache_dir=args.cache_dir,
            outputs_dir=args.outputs_dir,
            symbols_file=args.symbols_file,
            limit=limit,
            provider=args.provider,
        )
    )
    output_file = Path(args.output_file) if args.output_file else default_coverage_output(args.outputs_dir, args.start_date, args.end_date, limit)
    path = write_cache_coverage_report(report, output_file)
    summary = {key: report[key] for key in ["status", "provider_access", "symbol_count", "covered_count", "missing_count", "coverage_rate"]}
    print(json.dumps({"summary": summary, "output_file": path}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
