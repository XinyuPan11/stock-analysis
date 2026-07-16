"""CLI for the read-only Phase 4.1 production-candidate foundation audit."""

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

from stock_analysis.research.production_candidate_foundation import (  # noqa: E402
    ProductionCandidateFoundationError,
    audit_production_candidate_foundation,
    write_foundation_audit,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the frozen production baseline and Phase 4.1 research "
            "foundation. Default is dry-run and writes nothing."
        )
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--baseline-manifest")
    parser.add_argument("--foundation-config")
    parser.add_argument("--outputs-dir")
    parser.add_argument(
        "--write-output",
        action="store_true",
        help=(
            "Write only outputs/research/"
            "production_candidate_foundation_audit.json."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    outputs_dir = (
        Path(args.outputs_dir).resolve()
        if args.outputs_dir
        else repo_root / "outputs"
    )
    try:
        report = audit_production_candidate_foundation(
            repo_root=repo_root,
            baseline_path=args.baseline_manifest,
            foundation_path=args.foundation_config,
        )
        if args.write_output:
            output_path = write_foundation_audit(
                report,
                outputs_dir=outputs_dir,
            )
            report = {
                **report,
                "dry_run": False,
                "outputs_written": True,
                "output_path": output_path,
            }
    except ProductionCandidateFoundationError as exc:
        print(
            json.dumps(
                {
                    "status": exc.status,
                    "error": exc.message,
                    "details": exc.details,
                    "provider_access": False,
                    "labels_generated": False,
                    "features_generated": False,
                    "model_trained": False,
                    "backtest_run": False,
                    "production_modules_invoked": False,
                    "production_change": False,
                    "u3_changed": False,
                    "dry_run": not args.write_output,
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
