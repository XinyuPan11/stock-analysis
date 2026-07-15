"""CLI for the Phase 3.13 local-cache-only label-source builder."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
SRC = BACKEND_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.research.historical_h1h5_label_source import (  # noqa: E402
    HistoricalH1H5LabelSourceError,
    build_historical_h1h5_label_source,
    write_historical_h1h5_label_source_outputs,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build frozen historical H1-H5 labels from local cache only."
    )
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--horizon-days", required=True, type=int)
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--label-definition-config", required=True)
    parser.add_argument("--cache-dir", required=True)
    parser.add_argument("--outputs-dir", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--write-output", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = build_historical_h1h5_label_source(
            as_of_date=args.as_of_date,
            horizon_days=args.horizon_days,
            benchmark=args.benchmark,
            label_definition_config=args.label_definition_config,
            cache_dir=args.cache_dir,
            outputs_dir=args.outputs_dir,
        )
        payload: dict[str, object] = {
            **result.metadata,
            "dry_run": not args.write_output,
            "outputs_written": False,
        }
        if args.write_output:
            payload["outputs"] = write_historical_h1h5_label_source_outputs(
                result,
                outputs_dir=args.outputs_dir,
            )
            payload["outputs_written"] = True
    except HistoricalH1H5LabelSourceError as exc:
        print(
            json.dumps(
                {
                    "status": exc.status,
                    "error": exc.message,
                    "details": exc.details,
                    "as_of_date": args.as_of_date,
                    "research_only": True,
                    "local_cache_only": True,
                    "provider_access": False,
                    "labels_joined": False,
                    "evaluator_run": False,
                    "final_validation_outputs_written": False,
                    "production_change": False,
                    "dry_run": not args.write_output,
                    "outputs_written": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
