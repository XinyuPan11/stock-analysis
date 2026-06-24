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
    DEFAULT_CHUNK_SIZE,
    DEFAULT_END_DATE,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PROVIDER,
    DEFAULT_START_DATE,
    DEFAULT_START_OFFSET,
    RawCacheCatchupPlanConfig,
    generate_raw_cache_catchup_plan,
    write_raw_cache_catchup_plan,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate manual raw daily cache catch-up commands. No provider access.")
    parser.add_argument("--provider", default=DEFAULT_PROVIDER)
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", default=DEFAULT_END_DATE)
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--start-offset", type=int, default=DEFAULT_START_OFFSET)
    parser.add_argument("--chunk-count", type=int, default=1)
    parser.add_argument("--total-symbols", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    parser.add_argument("--retry", type=int, default=1)
    parser.add_argument("--max-errors", type=int, default=50)
    parser.add_argument("--symbol-timeout-seconds", type=int, default=20)
    parser.add_argument("--max-consecutive-symbol-timeouts", type=int, default=3)
    parser.add_argument("--failed-symbols-file", default=None)
    parser.add_argument("--output-file", default=None)
    parser.add_argument("--write-output", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    plan = generate_raw_cache_catchup_plan(
        RawCacheCatchupPlanConfig(
            provider=args.provider,
            start_date=args.start_date,
            end_date=args.end_date,
            cache_dir=args.cache_dir,
            output_dir=args.output_dir,
            chunk_size=args.chunk_size,
            start_offset=args.start_offset,
            chunk_count=args.chunk_count,
            total_symbols=args.total_symbols,
            batch_size=args.batch_size,
            sleep_seconds=args.sleep_seconds,
            retry=args.retry,
            max_errors=args.max_errors,
            symbol_timeout_seconds=args.symbol_timeout_seconds,
            max_consecutive_symbol_timeouts=args.max_consecutive_symbol_timeouts,
            failed_symbols_file=args.failed_symbols_file,
        )
    )
    output_file = args.output_file or str(Path(args.output_dir) / f"raw_cache_catchup_plan_{args.start_date}_{args.end_date}.json")
    if args.write_output:
        plan["output_file"] = write_raw_cache_catchup_plan(plan, output_file)
    print(json.dumps(_clean(plan), ensure_ascii=False, indent=2, allow_nan=False))
    return 0


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
