from __future__ import annotations

from html import escape
import re
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from stock_analysis.api.output_loader import RESEARCH_LABELS, OutputLoader
from stock_analysis.api.schemas import (
    BacktestResponse,
    CandidateDetailResponse,
    CandidatesResponse,
    FactorExplanationsResponse,
    LatestOutputResponse,
    NO_DAILY_OUTPUT_MESSAGE,
    NO_STOCK_REPORT_MESSAGE,
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


@router.get("/stocks/{symbol}", response_class=HTMLResponse)
def stock_detail_page(request: Request, symbol: str) -> HTMLResponse:
    detail = get_loader(request).get_candidate_by_symbol(symbol)
    if not detail["ok"]:
        return HTMLResponse(_message_page("候选股详情", detail["message"], back_href="/"), status_code=404)
    return HTMLResponse(_stock_detail_html(detail))


@router.get("/reports/daily", response_class=HTMLResponse)
def daily_report_page(request: Request) -> HTMLResponse:
    content = get_loader(request).get_daily_report()
    if not content["ok"]:
        return HTMLResponse(_message_page("每日报告", content["message"], back_href="/"), status_code=404)
    return HTMLResponse(_report_page("每日报告", content, back_href="/"))


@router.get("/reports/stocks/{symbol}", response_class=HTMLResponse)
def stock_report_page(request: Request, symbol: str) -> HTMLResponse:
    content = get_loader(request).get_stock_report(symbol)
    if not content["ok"]:
        return HTMLResponse(_message_page("单股报告", NO_STOCK_REPORT_MESSAGE, back_href=f"/stocks/{escape(symbol)}"), status_code=404)
    return HTMLResponse(_report_page(f"单股报告 - {symbol}", content, back_href=f"/stocks/{escape(symbol)}"))


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/latest", response_model=LatestOutputResponse)
def latest(request: Request) -> dict[str, Any]:
    return get_loader(request).latest()


@router.get("/api/candidates", response_model=CandidatesResponse)
def candidates(request: Request) -> dict[str, Any]:
    return get_loader(request).load_candidates()


@router.get("/api/candidates/{symbol}", response_model=CandidateDetailResponse)
def candidate_detail(request: Request, symbol: str) -> Any:
    detail = get_loader(request).get_candidate_by_symbol(symbol)
    if not detail["ok"]:
        return JSONResponse(detail, status_code=404)
    return detail


@router.get("/api/factor-explanations", response_model=FactorExplanationsResponse)
def factor_explanations(request: Request) -> dict[str, Any]:
    return get_loader(request).load_factor_explanations()


@router.get("/api/factor-explanations/{symbol}", response_model=FactorExplanationsResponse)
def factor_explanations_for_symbol(request: Request, symbol: str) -> Any:
    payload = get_loader(request).get_factor_explanations_by_symbol(symbol)
    if not payload["items"] and payload["ok"]:
        return JSONResponse(payload, status_code=404)
    return payload


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
    content = get_loader(request).get_daily_report(format=format)
    return _report_response(content, format)


@router.get("/api/reports/stocks/{symbol}", response_model=ReportContentResponse)
def stock_report(
    request: Request,
    symbol: str,
    format: str = Query("json", pattern="^(json|html|markdown)$"),
) -> Any:
    content = get_loader(request).get_stock_report(symbol, format=format)
    return _report_response(content, format, not_found=NO_STOCK_REPORT_MESSAGE)


def _report_response(content: dict[str, Any], format: str, *, not_found: str = "Report output not found.") -> Any:
    message = content.get("message") or not_found
    if format == "html":
        if content.get("html"):
            return HTMLResponse(str(content["html"]))
        return HTMLResponse(_not_found_html(message), status_code=404)
    if format == "markdown":
        if content.get("markdown"):
            return PlainTextResponse(str(content["markdown"]))
        return PlainTextResponse(message, status_code=404)
    if not content.get("ok"):
        return JSONResponse(content, status_code=404)
    return content


def _empty_dashboard(outputs_dir: str) -> str:
    return _page_shell(
        "A 股个人研究终端",
        f"""
        <section class="notice">
          <strong>{escape(NO_DAILY_OUTPUT_MESSAGE)}</strong>
          <p>outputs 目录：{escape(outputs_dir)}</p>
        </section>
        <p class="disclaimer">仅为个人研究辅助，不构成投资建议。</p>
        """,
    )


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

    body = f"""
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
    """
    return _page_shell("A 股个人研究终端", body)


def _stock_detail_html(detail: dict[str, Any]) -> str:
    row = detail["item"] or {}
    symbol = str(row.get("symbol") or detail.get("symbol") or "")
    name = str(row.get("name") or "")
    explanations = detail.get("factor_explanations", [])
    report = detail.get("report") or {}
    scores = [
        ("total_score", row.get("total_score", "")),
        ("confidence", row.get("confidence", "")),
        ("momentum_score", row.get("momentum_score", "")),
        ("trend_score", row.get("trend_score", "")),
        ("relative_strength_score", row.get("relative_strength_score", "")),
        ("risk_score", row.get("risk_score", "")),
        ("liquidity_score", row.get("liquidity_score", "")),
    ]

    body = f"""
    <header class="topbar">
      <div>
        <a href="/" class="back-link">返回首页</a>
        <h1>{escape(symbol)} {escape(name)}</h1>
        <p>数据日期：{escape(str(row.get("as_of_date") or detail.get("as_of_date") or ""))}</p>
      </div>
      <span class="tag-badge">{escape(str(row.get("label", "")))}</span>
    </header>

    <section>
      <h2>评分概览</h2>
      <div class="grid">
        {''.join(f'<div class="metric"><span>{escape(label)}</span><strong>{escape(_format_metric(value))}</strong></div>' for label, value in scores)}
      </div>
    </section>

    <section class="columns">
      <div>
        <h2>正向证据</h2>
        <dl class="field-list">
          <dt>positive_evidence</dt>
          <dd>{escape(_fallback(row.get("positive_evidence"), "暂无正向证据记录。"))}</dd>
        </dl>
      </div>
      <div>
        <h2>风险与反证</h2>
        <dl class="field-list">
          <dt>negative_evidence</dt>
          <dd>{escape(_fallback(row.get("negative_evidence"), "暂无显著反向证据。"))}</dd>
          <dt>risk_flags</dt>
          <dd>{escape(_fallback(row.get("risk_flags"), "暂无结构化风险标记。"))}</dd>
          <dt>warnings</dt>
          <dd>{escape(_fallback(row.get("warnings"), "暂无数据 warning。"))}</dd>
        </dl>
      </div>
    </section>

    <section>
      <h2>因子贡献表</h2>
      {_factor_table(explanations)}
    </section>

    <section>
      <h2>单股报告</h2>
      {_stock_report_entry(symbol, report)}
    </section>

    <p class="disclaimer">仅为个人研究辅助，不构成投资建议。</p>
    """
    return _page_shell(f"{symbol} 候选股详情", body)


def _report_page(title: str, content: dict[str, Any], *, back_href: str) -> str:
    report_html = content.get("html")
    markdown = content.get("markdown")
    if report_html:
        report_body = f"<iframe class=\"report-frame\" srcdoc=\"{escape(str(report_html), quote=True)}\"></iframe>"
    elif markdown:
        report_body = _markdown_to_html(str(markdown))
    else:
        report_body = f"<p class=\"muted\">{escape(content.get('message') or 'Report output not found.')}</p>"
    body = f"""
    <header class="topbar">
      <div>
        <a href="{escape(back_href)}" class="back-link">返回</a>
        <h1>{escape(title)}</h1>
        <p>数据日期：{escape(str(content.get("as_of_date") or ""))}</p>
      </div>
    </header>
    <section class="report-section">
      {report_body}
    </section>
    <p class="disclaimer">仅为个人研究辅助，不构成投资建议。</p>
    """
    return _page_shell(title, body)


def _message_page(title: str, message: str, *, back_href: str) -> str:
    body = f"""
    <header class="topbar">
      <div>
        <a href="{escape(back_href)}" class="back-link">返回</a>
        <h1>{escape(title)}</h1>
      </div>
    </header>
    <section class="notice">
      <strong>{escape(message)}</strong>
    </section>
    <p class="disclaimer">仅为个人研究辅助，不构成投资建议。</p>
    """
    return _page_shell(title, body)


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
    body = "".join(_candidate_row(row) for row in rows)
    return f"""<div class="table-wrap"><table>
<thead><tr><th>Rank</th><th>Symbol</th><th>Name</th><th>Score</th><th>Label</th><th>Risk</th><th>Report</th></tr></thead>
<tbody>{body}</tbody>
</table></div>"""


def _candidate_row(row: dict[str, Any]) -> str:
    symbol = str(row.get("symbol", ""))
    name = str(row.get("name", ""))
    detail_href = f"/stocks/{escape(symbol)}"
    report_href = f"/reports/stocks/{escape(symbol)}"
    risk = _fallback(row.get("risk_flags") or row.get("negative_evidence") or row.get("warnings"), "暂无显著风险标记")
    return (
        "<tr>"
        f"<td>{escape(str(row.get('rank', '')))}</td>"
        f"<td><a href=\"{detail_href}\">{escape(symbol)}</a></td>"
        f"<td><a href=\"{detail_href}\">{escape(name)}</a></td>"
        f"<td>{escape(_format_metric(row.get('total_score', '')))}</td>"
        f"<td><span class=\"tag-badge\">{escape(str(row.get('label', '')))}</span></td>"
        f"<td class=\"risk-cell\">{escape(risk)}</td>"
        f"<td><a href=\"{report_href}\">报告</a></td>"
        "</tr>"
    )


def _factor_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p class=\"muted\">暂无因子贡献数据。</p>"
    columns = ["factor_group", "raw_value", "normalized_score", "weight", "contribution", "explanation"]
    header = "".join(f"<th>{escape(column)}</th>" for column in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(_format_metric(row.get(column, '')))}</td>" for column in columns) + "</tr>"
        for row in rows
    )
    return f"<div class=\"table-wrap\"><table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>"


def _distribution_list(distribution: dict[str, int]) -> str:
    if not distribution:
        return "<p class=\"muted\">暂无标签分布。</p>"
    labels = [label for label in RESEARCH_LABELS if label in distribution]
    labels.extend(label for label in distribution if label not in labels)
    return "<ul>" + "".join(f"<li>{escape(label)}：{distribution[label]}</li>" for label in labels) + "</ul>"


def _high_confidence_list(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p class=\"muted\">当前样本中暂无高置信候选。</p>"
    return "<ul>" + "".join(
        f"<li><a href=\"/stocks/{escape(str(row.get('symbol', '')))}\">{escape(str(row.get('symbol', '')))} {escape(str(row.get('name', '')))}</a>，score {escape(_format_metric(row.get('total_score', '')))}</li>"
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


def _daily_report_link(report: dict[str, Any]) -> str:
    if not report:
        return "<p class=\"muted\">暂无每日报告。</p>"
    links = [f"<a href=\"/reports/daily\">浏览报告</a>"]
    if report.get("html_url"):
        links.append(f"<a href=\"{escape(report['html_url'])}\">HTML API</a>")
    if report.get("markdown_url"):
        links.append(f"<a href=\"{escape(report['markdown_url'])}\">Markdown API</a>")
    return "<p>" + " / ".join(links) + "</p>"


def _stock_report_links(reports: list[dict[str, Any]]) -> str:
    if not reports:
        return "<p class=\"muted\">暂无单股报告。</p>"
    return "<ul>" + "".join(
        f"<li><a href=\"{escape(str(report.get('page_url') or '#'))}\">{escape(str(report.get('symbol') or ''))}</a></li>"
        for report in reports
    ) + "</ul>"


def _stock_report_entry(symbol: str, report: dict[str, Any]) -> str:
    if not report or not (report.get("html_path") or report.get("markdown_path")):
        return f"<p class=\"muted\">{escape(NO_STOCK_REPORT_MESSAGE)}</p>"
    links = [f"<a href=\"/reports/stocks/{escape(symbol)}\">浏览单股报告</a>"]
    if report.get("html_url"):
        links.append(f"<a href=\"{escape(report['html_url'])}\">HTML API</a>")
    if report.get("markdown_url"):
        links.append(f"<a href=\"{escape(report['markdown_url'])}\">Markdown API</a>")
    return "<p>" + " / ".join(links) + "</p>"


def _markdown_to_html(markdown: str) -> str:
    lines = []
    in_list = False
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            if in_list:
                lines.append("</ul>")
                in_list = False
            lines.append("<br>")
        elif line.startswith("# "):
            lines.append(f"<h1>{escape(line[2:])}</h1>")
        elif line.startswith("## "):
            lines.append(f"<h2>{escape(line[3:])}</h2>")
        elif line.startswith("### "):
            lines.append(f"<h3>{escape(line[4:])}</h3>")
        elif line.startswith("- "):
            if not in_list:
                lines.append("<ul>")
                in_list = True
            lines.append(f"<li>{escape(line[2:])}</li>")
        else:
            if in_list:
                lines.append("</ul>")
                in_list = False
            lines.append(f"<p>{escape(line)}</p>")
    if in_list:
        lines.append("</ul>")
    return "<article class=\"markdown-report\">" + "\n".join(lines) + "</article>"


def _format_metric(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    try:
        if isinstance(value, str) and re.fullmatch(r"-?\d+\.\d+", value):
            return f"{float(value):.4f}"
    except ValueError:
        pass
    return str(value)


def _fallback(value: Any, fallback: str) -> str:
    if value is None or str(value).strip() == "":
        return fallback
    return str(value)


def _not_found_html(message: str) -> str:
    return f"<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><title>Not Found</title></head><body><p>{escape(message)}</p></body></html>"


def _page_shell(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>{_css()}</style>
</head>
<body>
  <main class="shell">
    {body}
  </main>
</body>
</html>"""


def _css() -> str:
    return """
:root { color-scheme: light; font-family: Arial, "Microsoft YaHei", sans-serif; color: #17202a; background: #f6f7f9; }
body { margin: 0; }
.shell { max-width: 1180px; margin: 0 auto; padding: 28px 20px 48px; }
.topbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; border-bottom: 1px solid #d9dee7; padding-bottom: 18px; }
h1 { margin: 6px 0 8px; font-size: 30px; font-weight: 700; letter-spacing: 0; }
h2 { margin: 0 0 14px; font-size: 19px; letter-spacing: 0; }
p { line-height: 1.65; }
section { margin-top: 24px; background: #ffffff; border: 1px solid #dde3ec; border-radius: 8px; padding: 18px; }
.columns { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 18px; }
.columns > div { min-width: 0; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
.metric { border: 1px solid #e0e5ed; border-radius: 8px; padding: 12px; background: #fbfcfe; min-height: 62px; }
.metric span { display: block; color: #667085; font-size: 12px; margin-bottom: 8px; overflow-wrap: anywhere; }
.metric strong { display: block; font-size: 16px; overflow-wrap: anywhere; }
.badge, .tag-badge { display: inline-block; border: 1px solid #9db7d8; color: #24466f; background: #eef5ff; border-radius: 999px; padding: 5px 9px; font-size: 13px; white-space: nowrap; }
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; min-width: 760px; }
th, td { border-bottom: 1px solid #e4e8ef; padding: 10px 8px; text-align: left; vertical-align: top; font-size: 14px; }
th { color: #455468; background: #f3f5f8; }
ul { margin: 0; padding-left: 20px; line-height: 1.7; }
dl { margin: 0; }
dt { color: #667085; font-size: 12px; margin-top: 10px; }
dt:first-child { margin-top: 0; }
dd { margin: 4px 0 0; line-height: 1.65; overflow-wrap: anywhere; }
a { color: #1f5f99; text-decoration: none; }
a:hover { text-decoration: underline; }
.back-link { font-size: 14px; }
.muted { color: #667085; }
.notice { border-color: #f0c36d; background: #fff8e6; }
.risk-cell { max-width: 260px; }
.report-frame { width: 100%; min-height: 680px; border: 1px solid #dde3ec; border-radius: 8px; background: #fff; }
.report-section { padding: 12px; }
.markdown-report { line-height: 1.7; }
.disclaimer { margin-top: 24px; color: #4b5563; font-size: 14px; }
@media (max-width: 760px) {
  .topbar, .columns { display: block; }
  .badge, .tag-badge { margin-top: 10px; white-space: normal; }
  h1 { font-size: 24px; }
}
"""
