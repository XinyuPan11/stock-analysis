"""CLI for research-only H1-H5 opportunity cohort annotations."""

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

from stock_analysis.research.opportunity_cohorts import (  # noqa: E402
    OpportunityCohortBuildError,
    build_research_opportunity_cohorts,
    load_opportunity_cohort_config,
    load_opportunity_snapshot,
    write_research_opportunity_cohort_outputs,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build research-only H1-H5 annotations from a feature-only "
            "point-in-time snapshot. No provider or validation access."
        )
    )
    parser.add_argument("--snapshot-file", required=True)
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument(
        "--outputs-dir",
        default=str(REPO_ROOT / "outputs"),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and print metadata without writing output files.",
    )
    mode.add_argument(
        "--write-output",
        action="store_true",
        help="Write separate research JSON and CSV outputs.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        snapshot = load_opportunity_snapshot(args.snapshot_file)
        config = load_opportunity_cohort_config(args.config)
        result = build_research_opportunity_cohorts(
            snapshot,
            config,
            as_of_date=args.as_of_date,
            source_snapshot_path=args.snapshot_file,
            config_path=args.config,
        )
    except OpportunityCohortBuildError as exc:
        print(
            json.dumps(
                {
                    "status": exc.status,
                    "error": exc.message,
                    "details": exc.details,
                    "research_only": True,
                    "provider_access": False,
                    "labels_joined": False,
                    "production_change": False,
                    "as_of_date": args.as_of_date,
                    "dry_run": not args.write_output,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    metadata = result.report["metadata"]
    payload: dict[str, object] = {
        **metadata,
        "dry_run": not args.write_output,
        "cohorts": result.report["cohorts"],
    }
    if args.write_output:
        payload["outputs"] = write_research_opportunity_cohort_outputs(
            result,
            args.outputs_dir,
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
