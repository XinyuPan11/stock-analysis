"""CLI for read-only 2024 answer-key case-study learning."""

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

from stock_analysis.validation.answer_key_learning import (  # noqa: E402
    AnswerKeyLearningConfig,
    build_answer_key_learning_report,
    write_answer_key_learning_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Match an existing 2024 case-study answer key to system list "
            "memberships. No provider access or label recomputation."
        )
    )
    parser.add_argument(
        "--case-study-file",
        default=str(
            REPO_ROOT
            / "research"
            / "case_studies"
            / "case_study_filled_2024.csv"
        ),
    )
    parser.add_argument("--outputs-dir", default=str(REPO_ROOT / "outputs"))
    parser.add_argument("--write-output", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_answer_key_learning_report(
        AnswerKeyLearningConfig(
            case_study_file=args.case_study_file,
            outputs_dir=args.outputs_dir,
        )
    )
    if args.write_output:
        outputs = write_answer_key_learning_outputs(report, args.outputs_dir)
        payload = {
            "status": report["summary"]["status"],
            "case_count": report["summary"]["case_count"],
            "winner_missed_count": report["capture_summary"][
                "winner_missed_count"
            ],
            "loser_incorrectly_captured_count": report["capture_summary"][
                "loser_incorrectly_captured_count"
            ],
            "provider_access": False,
            "labels_recomputed": False,
            "outputs": outputs,
        }
    else:
        payload = {
            "status": report["summary"]["status"],
            "dry_run": True,
            "case_count": report["summary"]["case_count"],
            "prediction_match_count": report["input_status"][
                "prediction_match_count"
            ],
            "membership_files_complete": report["input_status"][
                "membership_files_complete"
            ],
            "winner_missed_count": report["capture_summary"][
                "winner_missed_count"
            ],
            "loser_incorrectly_captured_count": report["capture_summary"][
                "loser_incorrectly_captured_count"
            ],
            "provider_access": False,
            "labels_recomputed": False,
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
