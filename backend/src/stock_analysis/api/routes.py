from __future__ import annotations

from html import escape
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

from stock_analysis.api.output_loader import RESEARCH_LABELS, OutputLoader
from stock_analysis.api.schemas import (
    BacktestResponse,
    CandidatesResponse,
    LatestOutputResponse,
    NO_DAILY_OUTPUT_MESSAGE,
    ReportContentResponse,
    ReportsResponse,
    SummaryResponse,
)


router = APIRouter()


def get_loader(request: Request) -> OutputLoader:
    return request.app.state.output_loader


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    loader = get_loader(request)
    latest = loader.latest()
    if not latest["ok"]:
        return HTMLResponse(_empty_dashboard(str(latest["outputs_dir"])))

    candidates = loader.load_candidates()
    summary = loader.load_summary()
    backtest = loader.load_backtest()
    reports = loader.reports()
    return HTMLResponse(_dashboard_html(latest, candidates, summary, backtest, reports))


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/latest", response_model=LatestOutputResponse)
def latest(request: Request) -> dict[str, Any]:
    return get_loader(request).latest()


@router.get("/api/candidates", response_model=CandidatesResponse)
def candidates(request: Request) -> dict[str, Any]:
    return get_loader(request).load_candidates()


@router.get("/api/summary", response_model=SummaryResponse)
def summary(request: Request) -> dict[str, Any]:
    return get_loader(request).load_summary()


@router.get("/api/backtest", response_model=BacktestResponse)
def backtest(request: Request) -> dict[str, Any]:
    return get_loader(request).load_backtest()


@router.get("/api/reports", response_model=ReportsResponse)
def reports(request: Request) -> dict[str, Any]:
    return get_loader(request).reports()


@router.get("/api/reports/daily", response_model=ReportContentResponse)
def daily_report(
    request: Request,
    format: str = Query("json", pattern="^(json|html|markdown)$"),
) -> Any:
    loader = get_loader(request)
    content = loader.read_report(loader.daily_report())
    return _report_response(content, format)


@router.get("/api/reports/stocks/{symbol}", response_model=ReportContentResponse)
def stock_report(
    request: Request,
    symbol: str,
    format: str = Query("json", pattern="^(json|html|markdown)$"),
) -> Any:
    loader = get_loader(request)
    content = loader.read_report(loader.stock_report(symbol))
    return _report_response(content, format)


def _report_response(content: dict[str, Any], format: str) -> Any:
    if format == "html":
        if content.get("html"):
            return HTMLResponse(str(content["html"]))
        return HTMLResponse(_not_found_html(content.get("message") or "Report output not found."), status_code=404)
    if format == "markdown":
        if content.get("markdown"):
            return PlainTextResponse(str(content["markdown"]))
        return PlainTextResponse(content.get("message") or "Report output not found.", status_code=404)
    return content


def _empty_dashboard(outputs_dir: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>A 股个人研究终端</title>
  <style>{_css()}</style>
</head>
<body>
  <main class="shell">
    <h1>A 股个人研究终端</h1>
    <section class="notice">
      <strong>{escape(NO_DAILY_OUTPUT_MESSAGE)}</strong>
      <p>outputs 目录：{escape(outputs_dir)}</p>
    </section>
    <p class="disclaimer">仅为个人研究辅助，不构成投资建议。</p>
  </main>
</body>
</html>"""


def _dashboard_html(
    latest: dict[str, Any],
    candidates: dict[str, Any],
    summary: dict[str, Any],
    backtest: dict[str, Any],
    reports: dict[str, Any],
) -> str:
    rows = candidates.get("items", [])[:10]
    distribution = candidates.get("label_distribution", {})
    high_confidence = candidates.get("high_confidence", [])
    summary_payload = summary.get("summary", {})
    metrics = backtest.get("metrics", {})
    report_daily = reports.get("daily") or {}
    stock_reports = reports.get("stocks", [])[:12]
    risk_items = _risk_items(rows, summary_payload)

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>A 股个人研究终端</title>
  <style>{_css()}</style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div>
        <h1>A 股个人研究终端</h1>
        <p>最新数据日期：{escape(str(latest.get("as_of_date") or ""))}</p>
      </div>
      <span class="badge">本地 Dashboard</span>
    </header>

    <section>
      <h2>Pipeline Summary</h2>
      {_summary_grid(summary_payload)}
    </section>

    <section>
      <h2>Top N 候选股</h2>
      {_candidate_table(rows)}
    </section>

    <section class="columns">
      <div>
        <h2>标签分布</h2>
        {_distribution_list(distribution)}
      </div>
      <div>
        <h2>高置信候选区</h2>
        {_high_confidence_list(high_confidence)}
      </div>
    </section>

    <section>
      <h2>风险提示区</h2>
      {_risk_list(risk_items)}
    </section>

    <section>
      <h2>回测核心指标</h2>
      {_metrics_grid(metrics)}
    </section>

    <section class="columns">
      <div>
        <h2>每日报告链接</h2>
        {_daily_report_link(report_daily)}
      </div>
      <div>
        <h2>单股报告链接</h2>
        {_stock_report_links(stock_reports)}
      </div>
    </section>

    <p class="disclaimer">仅为个人研究辅助，不构成投资建议。</p>
  </main>
</body>
</html>"""


def _summary_grid(summary: dict[str, Any]) -> str:
    keys = [
        "provider",
        "benchmark",
        "start_date",
        "end_date",
        "universe_count",
        "filtered_count",
        "attempted_count",
        "successful_factor_count",
        "scored_count",
        "fetch_error_count",
        "updated_at",
    ]
    cards = "".join(
        f"<div class=\"metric\"><span>{escape(key)}</span><strong>{escape(str(summary.get(key, '')))}</strong></div>"
        for key in keys
    )
    return f"<div class=\"grid\">{cards}</div>"


def _candidate_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p class=\"muted\">暂无候选股数据。</p>"
    body = "".join(
        "<tr>"
        f"<td>{escape(str(row.get('rank', '')))}</td>"
        f"<td>{escape(str(row.get('symbol', '')))}</td>"
        f"<td>{escape(str(row.get('name', '')))}</td>"
        f"<td>{escape(str(row.get('total_score', '')))}</td>"
        f"<td>{escape(str(row.get('label', '')))}</td>"
        f"<td>{escape(str(row.get('confidence', '')))}</td>"
        "</tr>"
        for row in rows
    )
    return f"""<div class="table-wrap"><table>
<thead><tr><th>Rank</th><th>Symbol</th><th>Name</th><th>Score</th><th>Label</th><th>Confidence</th></tr></thead>
<tbody>{body}</tbody>
</table></div>"""


def _distribution_list(distribution: dict[str, int]) -> str:
    if not distribution:
        return "<p class=\"muted\">暂无标签分布。</p>"
    labels = [label for label in RESEARCH_LABELS if label in distribution]
    labels.extend(label for label in distribution if label not in labels)
    return "<ul>" + "".join(f"<li>{escape(label)}：{distribution[label]}</li>" for label in labels) + "</ul>"


def _high_confidence_list(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p class=\"muted\">本次输出暂无高置信候选。</p>"
    return "<ul>" + "".join(
        f"<li>{escape(str(row.get('symbol', '')))} {escape(str(row.get('name', '')))}，score {escape(str(row.get('total_score', '')))}</li>"
        for row in rows
    ) + "</ul>"


def _risk_items(rows: list[dict[str, Any]], summary: dict[str, Any]) -> list[str]:
    items: list[str] = []
    warnings = summary.get("warnings", [])
    if isinstance(warnings, list):
        items.extend(str(item) for item in warnings[:5])
    for row in rows:
        for key in ["risk_flags", "negative_evidence", "warnings"]:
            value = str(row.get(key, "") or "").strip()
            if value:
                items.append(f"{row.get('symbol', '')}: {value}")
    if not items:
        items.append("当前候选表未记录显著结构化风险，但仍需结合数据质量、成交活跃度和后续走势复核。")
    return items[:8]


def _risk_list(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>"


def _metrics_grid(metrics: dict[str, Any]) -> str:
    if not metrics:
        return "<p class=\"muted\">暂无回测 summary。</p>"
    keys = [
        "total_return",
        "net_total_return_after_cost",
        "benchmark_total_return",
        "excess_return",
        "max_drawdown",
        "sharpe_ratio",
        "number_of_rebalances",
        "average_holdings",
    ]
    cards = "".join(
        f"<div class=\"metric\"><span>{escape(key)}</span><strong>{escape(_format_metric(metrics.get(key, '')))}</strong></div>"
        for key in keys
    )
    return f"<div class=\"grid\">{cards}</div>"


def _format_metric(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _daily_report_link(report: dict[str, Any]) -> str:
    if not report:
        return "<p class=\"muted\">暂无每日报告。</p>"
    links = []
    if report.get("html_url"):
        links.append(f"<a href=\"{escape(report['html_url'])}\">HTML 报告</a>")
    if report.get("markdown_url"):
        links.append(f"<a href=\"{escape(report['markdown_url'])}\">Markdown 报告</a>")
    return "<p>" + " / ".join(links) + "</p>" if links else "<p class=\"muted\">报告文件未找到。</p>"


def _stock_report_links(reports: list[dict[str, Any]]) -> str:
    if not reports:
        return "<p class=\"muted\">暂无单股报告。</p>"
    return "<ul>" + "".join(
        f"<li><a href=\"{escape(str(report.get('html_url') or report.get('markdown_url') or '#'))}\">{escape(str(report.get('symbol') or ''))}</a></li>"
        for report in reports
    ) + "</ul>"


def _not_found_html(message: str) -> str:
    return f"<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><title>Not Found</title></head><body><p>{escape(message)}</p></body></html>"


def _css() -> str:
    return """
:root { color-scheme: light; font-family: Arial, "Microsoft YaHei", sans-serif; color: #17202a; background: #f6f7f9; }
body { margin: 0; }
.shell { max-width: 1180px; margin: 0 auto; padding: 28px 20px 48px; }
.topbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; border-bottom: 1px solid #d9dee7; padding-bottom: 18px; }
h1 { margin: 0 0 8px; font-size: 30px; font-weight: 700; letter-spacing: 0; }
h2 { margin: 0 0 14px; font-size: 19px; letter-spacing: 0; }
p { line-height: 1.65; }
section { margin-top: 24px; background: #ffffff; border: 1px solid #dde3ec; border-radius: 8px; padding: 18px; }
.columns { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 18px; }
.columns > div { min-width: 0; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
.metric { border: 1px solid #e0e5ed; border-radius: 8px; padding: 12px; background: #fbfcfe; min-height: 62px; }
.metric span { display: block; color: #667085; font-size: 12px; margin-bottom: 8px; overflow-wrap: anywhere; }
.metric strong { display: block; font-size: 16px; overflow-wrap: anywhere; }
.badge { border: 1px solid #9db7d8; color: #24466f; border-radius: 999px; padding: 6px 10px; font-size: 13px; white-space: nowrap; }
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; min-width: 760px; }
th, td { border-bottom: 1px solid #e4e8ef; padding: 10px 8px; text-align: left; vertical-align: top; font-size: 14px; }
th { color: #455468; background: #f3f5f8; }
ul { margin: 0; padding-left: 20px; line-height: 1.7; }
a { color: #1f5f99; text-decoration: none; }
a:hover { text-decoration: underline; }
.muted { color: #667085; }
.notice { border-color: #f0c36d; background: #fff8e6; }
.disclaimer { margin-top: 24px; color: #4b5563; font-size: 14px; }
@media (max-width: 760px) {
  .topbar, .columns { display: block; }
  .badge { display: inline-block; margin-top: 10px; }
  h1 { font-size: 24px; }
}
"""
