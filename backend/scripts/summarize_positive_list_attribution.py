"""CLI for read-only positive-list weakness attribution."""

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

from stock_analysis.validation.positive_list_attribution import (  # noqa: E402
    DEFAULT_LIST_IDS,
    DEFAULT_WINDOWS,
    PositiveListAttributionConfig,
    build_positive_list_attribution,
    write_positive_list_attribution_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Attribute weak positive-list results using existing outputs only. "
            "No provider access or label recomputation."
        )
    )
    parser.add_argument("--outputs-dir", default=str(REPO_ROOT / "outputs"))
    parser.add_argument(
        "--windows",
        default=",".join(f"{date}:{horizon}" for date, horizon in DEFAULT_WINDOWS),
    )
    parser.add_argument("--list-ids", default=",".join(DEFAULT_LIST_IDS))
    parser.add_argument("--warning-quantile", type=float, default=0.20)
    parser.add_argument("--min-variant-sample", type=int, default=5)
    parser.add_argument("--write-output", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_positive_list_attribution(
        PositiveListAttributionConfig(
            outputs_dir=args.outputs_dir,
            windows=_parse_windows(args.windows),
            list_ids=tuple(
                item.strip() for item in args.list_ids.split(",") if item.strip()
            ),
            warning_quantile=args.warning_quantile,
            min_variant_sample=args.min_variant_sample,
        )
    )
    if args.write_output:
        outputs = write_positive_list_attribution_outputs(
            report, args.outputs_dir
        )
        payload = {
            "status": report["summary"]["status"],
            "included_window_count": report["summary"]["included_window_count"],
            "high_risk_exclusion_improved_list_count": report[
                "high_risk_exclusion_summary"
            ]["improved_list_count"],
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
            "variant_summary_count": len(report["variant_stability"]),
            "high_risk_exclusion_improved_list_count": report[
                "high_risk_exclusion_summary"
            ]["improved_list_count"],
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
