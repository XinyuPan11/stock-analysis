"""Export a research-only feature snapshot from an existing merged snapshot."""

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

from stock_analysis.research.feature_only_snapshot import (  # noqa: E402
    FeatureOnlySnapshotError,
    build_feature_only_snapshot,
    load_member_snapshot,
    write_feature_only_snapshot_outputs,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export one research-only feature snapshot without provider "
            "access, label computation, or validation."
        )
    )
    parser.add_argument("--snapshot-file", required=True)
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument(
        "--output-dir",
        "--outputs-dir",
        dest="output_dir",
        default=str(REPO_ROOT / "research" / "inputs"),
    )
    parser.add_argument(
        "--output-path",
        help="Optional explicit CSV output path; JSON uses the same stem.",
    )
    parser.add_argument(
        "--drop-outcome-columns",
        action="store_true",
        help=(
            "Explicitly remove audited future/outcome columns. Without this "
            "flag their presence fails closed."
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print metadata without writing files (default).",
    )
    mode.add_argument(
        "--write-output",
        action="store_true",
        help="Write the feature-only CSV and JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        source = load_member_snapshot(args.snapshot_file)
        result = build_feature_only_snapshot(
            source,
            as_of_date=args.as_of_date,
            source_snapshot_path=args.snapshot_file,
            drop_outcome_columns=args.drop_outcome_columns,
        )
        payload: dict[str, object] = {
            **result.metadata,
            "dry_run": not args.write_output,
        }
        if args.write_output:
            payload["outputs"] = write_feature_only_snapshot_outputs(
                result,
                output_dir=args.output_dir,
                output_path=args.output_path,
            )
            payload["output_path"] = result.metadata["output_path"]
    except FeatureOnlySnapshotError as exc:
        print(
            json.dumps(
                {
                    "status": exc.status,
                    "error": exc.message,
                    "details": exc.details,
                    "research_only": True,
                    "feature_only": True,
                    "labels_joined": False,
                    "provider_access": False,
                    "production_change": False,
                    "as_of_date": args.as_of_date,
                    "dry_run": not args.write_output,
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
