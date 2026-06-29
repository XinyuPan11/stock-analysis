"""CLI for read-only controlled validation quality attribution."""

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

from stock_analysis.validation.validation_quality_attribution import (  # noqa: E402
    DEFAULT_WINDOWS,
    ValidationQualityAttributionConfig,
    build_validation_quality_attribution,
    write_validation_quality_attribution_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize existing validation outputs for attribution. "
            "This command never accesses providers or recomputes labels."
        )
    )
    parser.add_argument("--outputs-dir", default=str(REPO_ROOT / "outputs"))
    parser.add_argument(
        "--windows",
        default=",".join(f"{date}:{horizon}" for date, horizon in DEFAULT_WINDOWS),
        help="Comma-separated windows such as 2024-01-31:20,2024-04-30:20.",
    )
    parser.add_argument(
        "--write-output",
        action="store_true",
        help="Write JSON and Markdown under outputs/experiments.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_validation_quality_attribution(
        ValidationQualityAttributionConfig(
            outputs_dir=args.outputs_dir,
            windows=_parse_windows(args.windows),
        )
    )
    if args.write_output:
        outputs = write_validation_quality_attribution_outputs(
            report, args.outputs_dir
        )
        payload = {
            "status": report["summary"]["status"],
            "included_window_count": report["summary"]["included_window_count"],
            "provider_access": False,
            "labels_recomputed": False,
            "outputs": outputs,
        }
    else:
        payload = {
            "status": report["summary"]["status"],
            "dry_run": True,
            "included_window_count": report["summary"]["included_window_count"],
            "excluded_window_count": report["summary"]["excluded_window_count"],
            "list_count": len(report["list_attribution"]),
            "factor_count": len(report["factor_attribution"]),
            "provider_access": False,
            "labels_recomputed": False,
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _parse_windows(value: str) -> tuple[tuple[str, int], ...]:
    windows = []
    for item in value.split(","):
        text = item.strip()
        if not text or ":" not in text:
            raise SystemExit(f"Invalid window: {item}")
        as_of_date, horizon = text.split(":", 1)
        windows.append((as_of_date, int(horizon.removesuffix("d"))))
    return tuple(windows)


if __name__ == "__main__":
    raise SystemExit(main())
