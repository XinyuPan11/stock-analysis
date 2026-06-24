"""CLI for Phase 2.8.5 multi-window experiment summaries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stock_analysis.validation.multi_window_experiment_summary import (  # noqa: E402
    MultiWindowSummaryConfig,
    build_multi_window_experiment_summary,
    write_multi_window_experiment_summary_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize existing multi-window strategy experiment outputs."
    )
    parser.add_argument("--outputs-dir", default="outputs")
    parser.add_argument(
        "--plan-file",
        default="outputs/experiments/multi_asof_validation_plan_2024.json",
    )
    parser.add_argument("--min-valid-count", type=int, default=50)
    parser.add_argument("--min-coverage-rate", type=float, default=0.7)
    parser.add_argument(
        "--windows",
        default=None,
        help=(
            "Optional comma-separated windows like 2024-01-31:20,2024-04-30:60. "
            "When omitted, all ready_for_comparison windows from the plan are used."
        ),
    )
    parser.add_argument(
        "--write-output",
        action="store_true",
        help="Write JSON and markdown outputs. Omit for dry-run stdout only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = MultiWindowSummaryConfig(
        outputs_dir=Path(args.outputs_dir),
        plan_file=Path(args.plan_file),
        windows=_parse_windows(args.windows) if args.windows else None,
        min_valid_count=args.min_valid_count,
        min_coverage_rate=args.min_coverage_rate,
    )
    summary = build_multi_window_experiment_summary(config)
    if args.write_output:
        outputs = write_multi_window_experiment_summary_outputs(
            summary,
            Path(args.outputs_dir),
        )
        print(json.dumps({"status": "ok", "outputs": outputs}, ensure_ascii=False, indent=2))
    else:
        print(
            json.dumps(
                {
                    "status": summary["summary"]["status"],
                    "dry_run": True,
                    "ready_window_count": summary["summary"]["ready_window_count"],
                    "missing_window_count": summary["summary"]["missing_window_count"],
                    "strategy_family_count": summary["summary"]["strategy_family_count"],
                    "aggressive_filter_count": summary["summary"]["aggressive_filter_count"],
                    "write_output": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


def _parse_windows(value: str) -> tuple[tuple[str, int], ...]:
    windows: list[tuple[str, int]] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise SystemExit(f"Invalid window: {item}")
        as_of_date, horizon = item.split(":", 1)
        horizon = horizon.removesuffix("d")
        windows.append((as_of_date, int(horizon)))
    return tuple(windows)


if __name__ == "__main__":
    raise SystemExit(main())
