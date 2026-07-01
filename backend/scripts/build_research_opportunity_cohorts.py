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
    validate_opportunity_cohort_config,
    write_research_opportunity_cohort_outputs,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build research-only H1-H5 annotations from a feature-only "
            "point-in-time snapshot. No provider or validation access."
        )
    )
    parser.add_argument("--snapshot-file")
    parser.add_argument("--as-of-date")
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
    mode.add_argument(
        "--schema-check-only",
        action="store_true",
        help=(
            "Validate template governance and parameter keys without making "
            "the config runnable or loading a snapshot."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config = load_opportunity_cohort_config(args.config)
        if args.schema_check_only:
            validated = validate_opportunity_cohort_config(
                config,
                mode="template",
            )
            parameter_values = [
                value
                for cohort in validated["cohorts"].values()
                for value in cohort["parameters"].values()
            ]
            print(
                json.dumps(
                    {
                        "status": "schema_valid_template",
                        "schema_validation_mode": "template",
                        "runnable": False,
                        "research_only": True,
                        "provider_access": False,
                        "labels_joined": False,
                        "production_change": False,
                        "config_version": validated["config_version"],
                        "parameter_count": len(parameter_values),
                        "null_parameter_count": sum(
                            value is None for value in parameter_values
                        ),
                        "snapshot_loaded": False,
                        "outputs_written": False,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        if not args.snapshot_file or not args.as_of_date:
            raise OpportunityCohortBuildError(
                "blocked_missing_execution_argument",
                "Normal dry-run/write-output requires --snapshot-file and "
                "--as-of-date.",
            )
        validated_config = validate_opportunity_cohort_config(
            config,
            as_of_date=args.as_of_date,
            mode="execution",
        )
        snapshot = load_opportunity_snapshot(args.snapshot_file)
        result = build_research_opportunity_cohorts(
            snapshot,
            validated_config,
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
                    "schema_check_only": args.schema_check_only,
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
        "schema_check_only": False,
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
