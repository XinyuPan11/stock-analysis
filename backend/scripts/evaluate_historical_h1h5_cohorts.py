"""CLI for the historical sealed H1-H5 evaluator framework."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
SRC = BACKEND_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.research.historical_h1h5_evaluator import (  # noqa: E402
    HistoricalH1H5EvaluatorError,
    evaluate_historical_h1h5_cohorts,
    evaluator_schema_contract,
    load_explicit_label_source,
    load_frozen_cohort_output,
    write_historical_h1h5_evaluation_outputs,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate a digest-verified historical H1-H5 cohort with an "
            "explicit precomputed label source. No provider or builder call."
        )
    )
    parser.add_argument("--cohort-output")
    parser.add_argument("--as-of-date")
    parser.add_argument("--horizon-days", type=int)
    parser.add_argument("--benchmark")
    parser.add_argument("--label-source")
    parser.add_argument("--expected-cohort-sha256")
    parser.add_argument("--outputs-dir")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Evaluate in memory and write no files (default).",
    )
    mode.add_argument(
        "--write-output",
        action="store_true",
        help="Write one evaluation CSV and JSON after explicit authorization.",
    )
    mode.add_argument(
        "--schema-check-only",
        action="store_true",
        help="Print the evaluator schema without loading cohort or labels.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.schema_check_only:
        print(
            json.dumps(
                evaluator_schema_contract(),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    missing = [
        name
        for name, value in (
            ("--cohort-output", args.cohort_output),
            ("--as-of-date", args.as_of_date),
            ("--horizon-days", args.horizon_days),
            ("--benchmark", args.benchmark),
            ("--label-source", args.label_source),
            ("--expected-cohort-sha256", args.expected_cohort_sha256),
            ("--outputs-dir", args.outputs_dir),
        )
        if value is None
    ]
    if missing:
        print(
            json.dumps(
                {
                    "status": "blocked_missing_execution_argument",
                    "error": "Normal execution requires explicit inputs.",
                    "details": {"missing_arguments": missing},
                    "research_only": True,
                    "provider_access": False,
                    "labels_joined_by_evaluator": False,
                    "builder_labels_joined": False,
                    "production_change": False,
                    "dry_run": not args.write_output,
                    "outputs_written": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    try:
        frozen = load_frozen_cohort_output(
            args.cohort_output,
            as_of_date=args.as_of_date,
            expected_sha256=args.expected_cohort_sha256,
        )
        # This is intentionally after the frozen digest and pre-join guards.
        labels = load_explicit_label_source(args.label_source)
        result = evaluate_historical_h1h5_cohorts(
            frozen,
            labels,
            as_of_date=args.as_of_date,
            horizon_days=args.horizon_days,
            benchmark=args.benchmark,
            label_source_path=args.label_source,
        )
        payload: dict[str, object] = {
            **result.report["metadata"],
            "status": (
                "evaluation_complete"
                if args.write_output
                else "evaluator_dry_run_complete"
            ),
            "dry_run": not args.write_output,
            "outputs_written": False,
            "performance_results_exposed": args.write_output,
            "underpowered_cohort_count": sum(
                bool(row["underpowered"]) for row in result.report["cohorts"]
            ),
        }
        if args.write_output:
            payload["cohorts"] = result.report["cohorts"]
            payload["outputs"] = write_historical_h1h5_evaluation_outputs(
                result,
                outputs_dir=args.outputs_dir,
            )
            payload["outputs_written"] = True
    except HistoricalH1H5EvaluatorError as exc:
        print(
            json.dumps(
                {
                    "status": exc.status,
                    "error": exc.message,
                    "details": exc.details,
                    "research_only": True,
                    "provider_access": False,
                    "labels_joined_by_evaluator": False,
                    "builder_labels_joined": False,
                    "production_change": False,
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
