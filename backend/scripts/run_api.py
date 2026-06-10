from __future__ import annotations

import argparse
from pathlib import Path
import sys

import uvicorn


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.api.app import create_app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local A-share research dashboard API.")
    parser.add_argument("--outputs-dir", default="outputs", help="Phase 1 outputs directory to read.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host.")
    parser.add_argument("--port", type=int, default=8000, help="Bind port.")
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn reload for local development.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = create_app(outputs_dir=args.outputs_dir)
    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
