"""CLI for fail-closed U3 H1-H5 execution readiness."""

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

from stock_analysis.research.u3_readiness import (  # noqa: E402
    check_u3_readiness,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check U3 H1-H5 configs, checksums, and local feature-only "
            "snapshots. No provider or validation access."
        )
    )
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT),
    )
    parser.add_argument(
        "--snapshot-dir",
        help=(
            "Directory containing member_level_asof_features_<date>.csv. "
            "Defaults to research/inputs under the repo root."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = check_u3_readiness(
        args.repo_root,
        snapshot_dir=args.snapshot_dir,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
