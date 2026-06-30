"""CLI for read-only member-level as-of feature snapshots."""

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

from stock_analysis.validation.member_level_asof_snapshot import (  # noqa: E402
    DEFAULT_WINDOWS,
    MemberLevelSnapshotConfig,
    build_member_level_asof_snapshot,
    write_member_level_asof_snapshot_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build research-only member-level as-of snapshots from existing "
            "outputs and local daily cache. No provider access."
        )
    )
    parser.add_argument("--outputs-dir", default=str(REPO_ROOT / "outputs"))
    parser.add_argument(
        "--cache-dir",
        default=str(REPO_ROOT / "data" / "cache" / "daily-use"),
    )
    parser.add_argument("--provider", default="baostock")
    parser.add_argument(
        "--windows",
        default=",".join(
            f"{date}:{horizon}" for date, horizon in DEFAULT_WINDOWS
        ),
        help="Comma-separated as-of:horizon pairs.",
    )
    parser.add_argument("--write-output", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_member_level_asof_snapshot(
        MemberLevelSnapshotConfig(
            outputs_dir=args.outputs_dir,
            cache_dir=args.cache_dir,
            provider=args.provider,
            windows=_parse_windows(args.windows),
        )
    )
    summary = result.report["summary"]
    payload = {
        "status": summary["status"],
        "dry_run": not args.write_output,
        "row_count": summary["row_count"],
        "included_window_count": summary["included_window_count"],
        "excluded_window_count": summary["excluded_window_count"],
        "local_cache_features_used": summary["local_cache_features_used"],
        "provider_access": False,
        "labels_recomputed": False,
    }
    if args.write_output:
        payload["outputs"] = write_member_level_asof_snapshot_outputs(
            result,
            args.outputs_dir,
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if summary["status"] != "insufficient_data" else 2


def _parse_windows(value: str) -> tuple[tuple[str, int], ...]:
    windows: list[tuple[str, int]] = []
    for raw_item in value.split(","):
        item = raw_item.strip()
        if not item or ":" not in item:
            raise SystemExit(f"Invalid window: {raw_item}")
        as_of_date, raw_horizon = item.split(":", 1)
        try:
            horizon = int(raw_horizon.lower().removesuffix("d"))
        except ValueError as exc:
            raise SystemExit(f"Invalid horizon: {raw_horizon}") from exc
        windows.append((as_of_date, horizon))
    if not windows:
        raise SystemExit("At least one window is required.")
    return tuple(windows)


if __name__ == "__main__":
    raise SystemExit(main())
