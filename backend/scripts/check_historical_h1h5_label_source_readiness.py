"""CLI for read-only historical H1-H5 label-source readiness."""

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

from stock_analysis.research.historical_h1h5_label_source_readiness import (  # noqa: E402
    check_historical_h1h5_label_source_readiness,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check frozen cohorts, local 20D cache coverage, explicit label "
            "sources, and conflicting validation outputs without writing."
        )
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--cache-dir")
    parser.add_argument("--outputs-dir")
    parser.add_argument(
        "--label-source",
        action="append",
        default=[],
        metavar="DATE=PATH",
        help="Optional explicit metadata-bearing label JSON for one primary.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        label_sources = _parse_date_paths(args.label_source)
    except ValueError as exc:
        print(
            json.dumps(
                {
                    "status": "blocked_invalid_label_source_argument",
                    "ready": False,
                    "error": str(exc),
                    "research_only": True,
                    "readiness_only": True,
                    "provider_access": False,
                    "labels_generated": False,
                    "labels_joined": False,
                    "evaluator_run": False,
                    "final_validation_outputs_written": False,
                    "production_change": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    report = check_historical_h1h5_label_source_readiness(
        args.repo_root,
        cache_dir=args.cache_dir,
        outputs_dir=args.outputs_dir,
        label_sources=label_sources,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ready") else 2


def _parse_date_paths(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--label-source must use DATE=PATH.")
        date, path = value.split("=", 1)
        date = date.strip()
        path = path.strip()
        if not date or not path:
            raise ValueError("--label-source requires non-empty DATE and PATH.")
        if date in result:
            raise ValueError(f"Duplicate --label-source date: {date}")
        result[date] = path
    return result


if __name__ == "__main__":
    raise SystemExit(main())
