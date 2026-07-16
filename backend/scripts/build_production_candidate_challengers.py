"""CLI for transparent Phase 4.2 research-only challengers."""

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

from stock_analysis.research.production_candidate_challengers import (  # noqa: E402
    ProductionCandidateChallengerError,
    build_challengers,
    write_challenger_outputs,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build full-row transparent research challenger scores from one "
            "label-free feature matrix. Default dry-run writes nothing."
        )
    )
    parser.add_argument("--feature-matrix", required=True)
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
        "--challenger-config",
        default=str(
            REPO_ROOT
            / "research"
            / "configs"
            / "production_candidate_challengers.v1.json"
        ),
    )
    parser.add_argument("--outputs-dir", default=str(REPO_ROOT / "outputs"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--write-output", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = build_challengers(
            feature_matrix_path=args.feature_matrix,
            feature_config_path=args.feature_config,
            challenger_config_path=args.challenger_config,
        )
        report = dict(result.report)
        if args.write_output:
            report["outputs"] = write_challenger_outputs(
                result, outputs_dir=args.outputs_dir
            )
            report["dry_run"] = False
            report["outputs_written"] = True
    except ProductionCandidateChallengerError as exc:
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
