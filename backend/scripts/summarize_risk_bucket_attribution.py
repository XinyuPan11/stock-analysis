"""CLI for controlled disjoint risk-bucket attribution."""

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

from stock_analysis.validation.risk_bucket_attribution import (  # noqa: E402
    DEFAULT_WINDOWS,
    RiskBucketAttributionConfig,
    build_risk_bucket_attribution,
    write_risk_bucket_attribution_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build disjoint high-risk versus non-high-risk attribution from "
            "existing outputs only. No provider access or label recomputation."
        )
    )
    parser.add_argument("--outputs-dir", default=str(REPO_ROOT / "outputs"))
    parser.add_argument(
        "--windows",
        default=",".join(f"{date}:{horizon}" for date, horizon in DEFAULT_WINDOWS),
    )
    parser.add_argument("--min-bucket-sample", type=int, default=5)
    parser.add_argument("--negative-window-ratio", type=float, default=0.75)
    parser.add_argument("--write-output", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_risk_bucket_attribution(
        RiskBucketAttributionConfig(
            outputs_dir=args.outputs_dir,
            windows=_parse_windows(args.windows),
            min_bucket_sample=args.min_bucket_sample,
            negative_window_ratio=args.negative_window_ratio,
        )
    )
    if args.write_output:
        outputs = write_risk_bucket_attribution_outputs(
            report, args.outputs_dir
        )
        payload = {
            "status": report["summary"]["status"],
            "classification": report["summary"]["classification"],
            "disjoint_attribution_available": report["summary"][
                "disjoint_attribution_available"
            ],
            "provider_access": False,
            "labels_recomputed": False,
            "outputs": outputs,
        }
    else:
        payload = {
            "status": report["summary"]["status"],
            "dry_run": True,
            "classification": report["summary"]["classification"],
            "disjoint_attribution_available": report["summary"][
                "disjoint_attribution_available"
            ],
            "included_window_count": report["summary"]["included_window_count"],
            "excluded_window_count": report["summary"]["excluded_window_count"],
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
