"""CLI for Phase 4.2 local-cache-only feature matrix construction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
SRC = BACKEND_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.research.production_candidate_feature_matrix import (  # noqa: E402
    ProductionCandidateFeatureMatrixError,
    build_feature_matrix,
    write_feature_matrix,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build one research-only point-in-time feature matrix from local "
            "adjusted daily cache. Default dry-run writes nothing."
        )
    )
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument(
        "--cache-dir",
        default=str(REPO_ROOT / "data" / "cache" / "daily-use"),
    )
    parser.add_argument(
        "--feature-config",
        default=str(
            REPO_ROOT
            / "research"
            / "configs"
            / "production_candidate_features.v1.json"
        ),
    )
    parser.add_argument(
        "--baseline-config",
        default=str(
            REPO_ROOT
            / "research"
            / "configs"
            / "production_candidate_baseline.v1.json"
        ),
    )
    parser.add_argument(
        "--baseline-snapshot-dir",
        default=str(REPO_ROOT / "outputs" / "daily"),
    )
    parser.add_argument(
        "--outputs-dir",
        default=str(REPO_ROOT / "research" / "inputs"),
    )
    parser.add_argument("--limit", type=int)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--write-output", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = build_feature_matrix(
            as_of_date=args.as_of_date,
            cache_dir=args.cache_dir,
            feature_config_path=args.feature_config,
            baseline_config_path=args.baseline_config,
            baseline_snapshot_dir=args.baseline_snapshot_dir,
            limit=args.limit,
        )
        report = dict(result.report)
        if args.write_output:
            report["outputs"] = write_feature_matrix(
                result, outputs_dir=args.outputs_dir
            )
            report["dry_run"] = False
            report["outputs_written"] = True
    except ProductionCandidateFeatureMatrixError as exc:
        print(
            json.dumps(
                {
                    "status": exc.status,
                    "error": exc.message,
                    "details": exc.details,
                    "provider_access": False,
                    "labels_joined": False,
                    "production_change": False,
                    "results_are_effectiveness_evidence": False,
                    "outputs_written": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
