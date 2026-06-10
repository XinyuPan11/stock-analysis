from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


NO_DAILY_OUTPUT_MESSAGE = "No daily research output found. Please run run_daily_research.py first."
NO_STOCK_REPORT_MESSAGE = "No stock report found for this symbol. Please generate research reports first."


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
    total_count: int = 0
    filters: dict[str, Any] = Field(default_factory=dict)
    items: list[dict[str, Any]] = Field(default_factory=list)
    label_distribution: dict[str, int] = Field(default_factory=dict)
    high_confidence: list[dict[str, Any]] = Field(default_factory=list)


class CandidateDetailResponse(ApiMessage):
    as_of_date: str | None = None
    symbol: str
    item: dict[str, Any] | None = None
    factor_explanations: list[dict[str, Any]] = Field(default_factory=list)
    factor_summary: dict[str, Any] | None = None
    report: dict[str, Any] | None = None


class FactorExplanationsResponse(ApiMessage):
    as_of_date: str | None = None
    symbol: str | None = None
    count: int = 0
    items: list[dict[str, Any]] = Field(default_factory=list)


class FactorSummaryResponse(ApiMessage):
    as_of_date: str | None = None
    symbol: str | None = None
    count: int = 0
    items: list[dict[str, Any]] = Field(default_factory=list)
    positive_factors: list[dict[str, Any]] = Field(default_factory=list)
    risk_factors: list[dict[str, Any]] = Field(default_factory=list)
    watch_signals: list[dict[str, Any]] = Field(default_factory=list)
    explanation: str = ""


class CompareResponse(ApiMessage):
    as_of_date: str | None = None
    count: int = 0
    total_count: int = 0
    filters: dict[str, Any] = Field(default_factory=dict)
    items: list[dict[str, Any]] = Field(default_factory=list)


class FactorGroupMatrixResponse(ApiMessage):
    as_of_date: str | None = None
    factor_group: str | None = None
    display_name: str | None = None
    count: int = 0
    filters: dict[str, Any] = Field(default_factory=dict)
    items: list[dict[str, Any]] = Field(default_factory=list)


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
    page_url: str | None = None


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
