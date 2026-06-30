"""CLI for the read-only captured-vs-missed winner deep dive."""

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

from stock_analysis.validation.captured_missed_winner_deep_dive import (  # noqa: E402
    DEFAULT_ATTRIBUTION_FILE,
    DEFAULT_CASE_STUDY_FILE,
    DEFAULT_SNAPSHOT_FILE,
    CapturedMissedDeepDiveConfig,
    build_captured_missed_winner_deep_dive,
    write_captured_missed_winner_deep_dive_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Deep-dive existing captured/missed winner and positive-list "
            "winner/loser cohorts. No provider access or recomputation."
        )
    )
    parser.add_argument(
        "--snapshot-file",
        default=str(REPO_ROOT / DEFAULT_SNAPSHOT_FILE),
    )
    parser.add_argument(
        "--attribution-file",
        default=str(REPO_ROOT / DEFAULT_ATTRIBUTION_FILE),
    )
    parser.add_argument(
        "--case-study-file",
        default=str(REPO_ROOT / DEFAULT_CASE_STUDY_FILE),
    )
    parser.add_argument("--outputs-dir", default=str(REPO_ROOT / "outputs"))
    parser.add_argument("--write-output", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_captured_missed_winner_deep_dive(
        CapturedMissedDeepDiveConfig(
            snapshot_file=args.snapshot_file,
            attribution_file=args.attribution_file,
            case_study_file=args.case_study_file,
        )
    )
    summary = report["summary"]
    payload = {
        "status": summary["status"],
        "dry_run": not args.write_output,
        "snapshot_row_count": summary["snapshot_row_count"],
        "window_count": summary["window_count"],
        "winner_tail_count": summary["winner_tail_count"],
        "captured_winner_count": summary["captured_winner_count"],
        "missed_winner_count": summary["missed_winner_count"],
        "positive_list_loser_count": summary[
            "positive_list_loser_count"
        ],
        "tail_fraction_reused": summary["tail_fraction_reused"],
        "provider_access": False,
        "labels_recomputed": False,
    }
    if args.write_output:
        payload["outputs"] = write_captured_missed_winner_deep_dive_outputs(
            report,
            args.outputs_dir,
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
