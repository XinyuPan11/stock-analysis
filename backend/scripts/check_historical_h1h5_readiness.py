"""CLI for historical sealed H1-H5 feature-only execution readiness."""

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

from stock_analysis.research.historical_h1h5_readiness import (  # noqa: E402
    HISTORICAL_WINDOWS,
    check_historical_readiness,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check historical sealed H1-H5 configs and local feature-only "
            "snapshots. No provider, label, outcome, or validation access."
        )
    )
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT),
    )
    parser.add_argument(
        "--feature-snapshot-dir",
        help=(
            "Directory containing member_level_asof_features_<date>.csv. "
            "Defaults to research/inputs under the repo root."
        ),
    )
    parser.add_argument(
        "--source-snapshot",
        action="append",
        default=[],
        metavar="DATE=PATH",
        help=(
            "Optional exact local source snapshot for one preregistered date. "
            "Repeat for multiple dates. No missing file is fetched."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        source_paths = _parse_source_paths(args.source_snapshot)
    except ValueError as exc:
        print(
            json.dumps(
                {
                    "status": "blocked_invalid_source_snapshot_argument",
                    "error": str(exc),
                    "research_only": True,
                    "provider_access": False,
                    "labels_joined": False,
                    "production_change": False,
                    "validation_run": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    report = check_historical_readiness(
        args.repo_root,
        source_snapshot_paths=source_paths,
        feature_snapshot_dir=args.feature_snapshot_dir,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ready"] else 2


def _parse_source_paths(values: list[str]) -> dict[str, Path]:
    parsed: dict[str, Path] = {}
    for value in values:
        date, separator, path = value.partition("=")
        date = date.strip()
        path = path.strip()
        if (
            not separator
            or date not in HISTORICAL_WINDOWS
            or not path
            or date in parsed
        ):
            raise ValueError(
                "--source-snapshot must be a unique preregistered DATE=PATH."
            )
        parsed[date] = Path(path)
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
