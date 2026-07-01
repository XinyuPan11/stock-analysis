"""Print a read-only inventory for historical sealed H1-H5 source inputs."""

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

from stock_analysis.research.historical_snapshot_inventory import (  # noqa: E402
    inventory_historical_source_snapshots,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Print local historical H1-H5 source/cache inventory. "
            "No provider, prewarm, validation, labels, or output writes."
        )
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument(
        "--cache-dir",
        help="Local cache root; defaults to data/cache/daily-use.",
    )
    parser.add_argument(
        "--outputs-dir",
        help="Existing outputs root; defaults to outputs.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = inventory_historical_source_snapshots(
        args.repo_root,
        cache_dir=args.cache_dir,
        outputs_dir=args.outputs_dir,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
