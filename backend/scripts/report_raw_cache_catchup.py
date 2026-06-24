from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.data.raw_cache_catchup import (  # noqa: E402
    DEFAULT_CACHE_DIR,
    DEFAULT_END_DATE,
    DEFAULT_PROVIDER,
    RawCacheCoverageConfig,
    build_raw_cache_coverage_report,
    write_raw_cache_coverage_report,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report local raw stock_daily adjusted cache catch-up coverage. No provider access.")
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR)
    parser.add_argument("--provider", default=DEFAULT_PROVIDER)
    parser.add_argument("--target-end-date", default=DEFAULT_END_DATE)
    parser.add_argument("--symbols-file", default=None)
    parser.add_argument("--output-file", default=None)
    parser.add_argument("--include-details", action="store_true", help="Print per-symbol details to console. Output files always keep full details.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_raw_cache_coverage_report(
        RawCacheCoverageConfig(
            cache_dir=args.cache_dir,
            provider=args.provider,
            target_end_date=args.target_end_date,
            symbols_file=args.symbols_file,
        )
    )
    if args.output_file:
        report["output_file"] = write_raw_cache_coverage_report(report, args.output_file)
    console_report = report if args.include_details else _summary_only(report)
    print(json.dumps(_clean(console_report), ensure_ascii=False, indent=2, allow_nan=False))
    return 0


def _summary_only(report: dict[str, Any]) -> dict[str, Any]:
    summary = dict(report)
    summary.pop("symbols", None)
    summary.pop("stale_incomplete_symbols", None)
    summary.pop("missing_symbols", None)
    summary["details_omitted_from_console"] = True
    summary["details_hint"] = "Use --include-details or --output-file for per-symbol rows."
    return summary


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if hasattr(value, "item"):
        return _clean(value.item())
    return value


if __name__ == "__main__":
    raise SystemExit(main())
