from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from stock_analysis.api.output_loader import OutputLoader
from stock_analysis.api.routes import router


def create_app(outputs_dir: str | Path = "outputs") -> FastAPI:
    app = FastAPI(
        title="A 股个人研究终端",
        description="Local dashboard API that reads Phase 1 output artifacts only.",
        version="0.2.0",
    )
    app.state.output_loader = OutputLoader(outputs_dir)
    app.include_router(router)
    return app


app = create_app()
