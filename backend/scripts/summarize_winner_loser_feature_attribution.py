"""CLI for read-only winner/loser feature attribution."""

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

from stock_analysis.validation.winner_loser_feature_attribution import (  # noqa: E402
    DEFAULT_SNAPSHOT_FILE,
    WinnerLoserAttributionConfig,
    build_winner_loser_feature_attribution,
    write_winner_loser_feature_attribution_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize in-sample winner/loser feature distributions from an "
            "existing Phase 2.14 snapshot. No provider access."
        )
    )
    parser.add_argument(
        "--snapshot-file",
        default=str(REPO_ROOT / DEFAULT_SNAPSHOT_FILE),
    )
    parser.add_argument("--outputs-dir", default=str(REPO_ROOT / "outputs"))
    parser.add_argument("--tail-fraction", type=float, default=0.10)
    parser.add_argument("--min-group-size", type=int, default=10)
    parser.add_argument("--write-output", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_winner_loser_feature_attribution(
        WinnerLoserAttributionConfig(
            snapshot_file=args.snapshot_file,
            tail_fraction=args.tail_fraction,
            min_group_size=args.min_group_size,
        )
    )
    summary = report["summary"]
    group_counts = {
        row["group_id"]: row["row_count"]
        for row in report["group_feature_summaries"]
    }
    payload = {
        "status": summary["status"],
        "dry_run": not args.write_output,
        "snapshot_row_count": summary["snapshot_row_count"],
        "window_count": summary["window_count"],
        "tail_fraction": summary["tail_fraction"],
        "group_counts": group_counts,
        "provider_access": False,
        "labels_recomputed": False,
    }
    if args.write_output:
        payload["outputs"] = write_winner_loser_feature_attribution_outputs(
            report,
            args.outputs_dir,
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
