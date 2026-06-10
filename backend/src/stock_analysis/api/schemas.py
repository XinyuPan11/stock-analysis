from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


NO_DAILY_OUTPUT_MESSAGE = "No daily research output found. Please run run_daily_research.py first."


class ApiMessage(BaseModel):
    ok: bool = True
    message: str = ""


class LatestOutputResponse(ApiMessage):
    as_of_date: str | None = None
    outputs_dir: str
    available: dict[str, bool] = Field(default_factory=dict)
    files: dict[str, str] = Field(default_factory=dict)


class CandidatesResponse(ApiMessage):
    as_of_date: str | None = None
    count: int = 0
    items: list[dict[str, Any]] = Field(default_factory=list)
    label_distribution: dict[str, int] = Field(default_factory=dict)
    high_confidence: list[dict[str, Any]] = Field(default_factory=list)


class SummaryResponse(ApiMessage):
    as_of_date: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)


class BacktestResponse(ApiMessage):
    as_of_date: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)


class ReportLink(BaseModel):
    symbol: str | None = None
    as_of_date: str | None = None
    markdown_path: str | None = None
    html_path: str | None = None
    markdown_url: str | None = None
    html_url: str | None = None


class ReportsResponse(ApiMessage):
    as_of_date: str | None = None
    daily: ReportLink | None = None
    backtest: ReportLink | None = None
    stocks: list[ReportLink] = Field(default_factory=list)


class ReportContentResponse(ApiMessage):
    symbol: str | None = None
    as_of_date: str | None = None
    markdown: str | None = None
    html: str | None = None
    markdown_path: str | None = None
    html_path: str | None = None
