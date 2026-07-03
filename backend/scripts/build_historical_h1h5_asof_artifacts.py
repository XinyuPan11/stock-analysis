"""CLI for safe historical H1-H5 as-of factor and membership artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
SRC = BACKEND_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.research.historical_asof_artifacts import (  # noqa: E402
    HistoricalAsOfArtifactError,
    build_historical_asof_artifacts,
    write_historical_asof_artifacts,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Project explicit local as-of factors and multi-list membership "
            "into label-free historical H1-H5 source inputs."
        )
    )
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--factors-file", required=True)
    parser.add_argument("--multi-list-file", required=True)
    parser.add_argument("--outputs-dir", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and print metadata without writing files (default).",
    )
    mode.add_argument(
        "--write-output",
        action="store_true",
        help="Write only the safe factors and membership CSV files.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = build_historical_asof_artifacts(
            as_of_date=args.as_of_date,
            factors_file=args.factors_file,
            multi_list_file=args.multi_list_file,
        )
        payload: dict[str, object] = {
            **result.metadata,
            "dry_run": not args.write_output,
            "outputs_written": False,
        }
        if args.write_output:
            payload["outputs"] = write_historical_asof_artifacts(
                result,
                outputs_dir=args.outputs_dir,
            )
            payload["outputs_written"] = True
    except HistoricalAsOfArtifactError as exc:
        print(
            json.dumps(
                {
                    "status": exc.status,
                    "error": exc.message,
                    "details": exc.details,
                    "research_only": True,
                    "safe_as_of_projection": True,
                    "provider_access": False,
                    "labels_joined": False,
                    "production_change": False,
                    "validation_run": False,
                    "future_labels_generated": False,
                    "future_returns_computed": False,
                    "h1h5_cohort_builder_called": False,
                    "feature_only_snapshot_generated": False,
                    "as_of_date": args.as_of_date,
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
