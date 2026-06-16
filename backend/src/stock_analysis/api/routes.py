from __future__ import annotations

from html import escape
import re
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from stock_analysis.api.output_loader import API_DISCLAIMER, RESEARCH_LABELS, OutputLoader
from stock_analysis.api.schemas import (
    BacktestResponse,
    CandidateDetailResponse,
    CandidatesResponse,
    CompareResponse,
    FactorExplanationsResponse,
    FactorGroupMatrixResponse,
    FactorSummaryResponse,
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


def _parse_optional_float(value: str | None, field: str) -> tuple[float | None, str]:
    if value is None or value.strip() == "":
        return None, ""
    try:
        return float(value), ""
    except ValueError:
        return None, f"Invalid {field}. It must be a number."


def _parse_optional_int(value: str | None, field: str) -> tuple[int | None, str]:
    if value is None or value.strip() == "":
        return None, ""
    try:
        return int(value), ""
    except ValueError:
        return None, f"Invalid {field}. It must be an integer."


def _parse_candidate_filter_params(
    *,
    min_score: str | None = None,
    max_score: str | None = None,
    min_confidence: str | None = None,
    limit: str | None = None,
) -> tuple[dict[str, Any], str]:
    parsed_min_score, error = _parse_optional_float(min_score, "min_score")
    if error:
        return {}, error
    parsed_max_score, error = _parse_optional_float(max_score, "max_score")
    if error:
        return {}, error
    parsed_min_confidence, error = _parse_optional_float(min_confidence, "min_confidence")
    if error:
        return {}, error
    parsed_limit, error = _parse_optional_int(limit, "limit")
    if error:
        return {}, error
    return {
        "min_score": parsed_min_score,
        "max_score": parsed_max_score,
        "min_confidence": parsed_min_confidence,
        "limit": parsed_limit,
    }, ""


def _empty_filter_error_payload(loader: OutputLoader, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "message": message,
        "as_of_date": loader.latest_daily_date(),
        "count": 0,
        "total_count": 0,
        "filters": {},
        "items": [],
        "label_distribution": {},
        "high_confidence": [],
    }


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    label: str | None = None,
    min_score: str | None = None,
    max_score: str | None = None,
    min_confidence: str | None = None,
    sort_by: str = "total_score",
    sort_order: str = "desc",
    limit: str | None = None,
) -> HTMLResponse:
    loader = get_loader(request)
    latest = loader.latest()
    if not latest["ok"]:
        return HTMLResponse(_empty_dashboard(str(latest["outputs_dir"])))
    parsed_filters, filter_error = _parse_candidate_filter_params(
        min_score=min_score,
        max_score=max_score,
        min_confidence=min_confidence,
        limit=limit,
    )
    if filter_error:
        return HTMLResponse(_message_page("筛选参数错误", filter_error, back_href="/"), status_code=400)

    candidates = loader.load_candidates(
        label=label,
        min_score=parsed_filters["min_score"],
        max_score=parsed_filters["max_score"],
        min_confidence=parsed_filters["min_confidence"],
        sort_by=sort_by,
        sort_order=sort_order,
        limit=parsed_filters["limit"],
    )
    summary = loader.load_summary()
    backtest = loader.load_backtest()
    reports = loader.reports()
    workflow = loader.get_latest_workflow_summary()
    return HTMLResponse(_dashboard_html(latest, candidates, summary, backtest, reports, workflow))


@router.get("/lists", response_class=HTMLResponse)
def lists_page(request: Request) -> HTMLResponse:
    return HTMLResponse(_lists_overview_html(get_loader(request).get_research_lists()))


@router.get("/lists/{list_id}", response_class=HTMLResponse)
def list_detail_page(request: Request, list_id: str) -> HTMLResponse:
    payload = get_loader(request).get_research_list(list_id)
    if not payload.get("ok"):
        return HTMLResponse(_message_page("榜单详情", payload.get("message", "Research list not found."), back_href="/lists"), status_code=404)
    return HTMLResponse(_list_detail_html(payload))


@router.get("/labels", response_class=HTMLResponse)
def labels_page(
    request: Request,
    primary_type: str | None = None,
    research_action: str | None = None,
    risk_level: str | None = None,
    limit: str | None = None,
) -> HTMLResponse:
    parsed_limit, error = _parse_optional_int(limit, "limit")
    if error:
        return HTMLResponse(_message_page("标签筛选", error, back_href="/labels"), status_code=400)
    payload = get_loader(request).get_labels(
        primary_type=primary_type,
        research_action=research_action,
        risk_level=risk_level,
        limit=parsed_limit,
    )
    return HTMLResponse(_labels_html(payload))


@router.get("/search", response_class=HTMLResponse)
def search_page(request: Request, q: str = "") -> HTMLResponse:
    if not q.strip():
        return HTMLResponse(_search_html({"ok": True, "query": q, "count": 0, "items": [], "message": "请输入股票代码或名称。"}))
    return HTMLResponse(_search_html(get_loader(request).search_stocks(q)))


@router.get("/stocks/{symbol}", response_class=HTMLResponse)
def stock_detail_page(request: Request, symbol: str) -> HTMLResponse:
    detail = get_loader(request).get_stock_research(symbol)
    if not detail["ok"]:
        return HTMLResponse(_message_page("候选股详情", detail["message"], back_href="/"), status_code=404)
    return HTMLResponse(_stock_research_html(detail))


@router.get("/compare", response_class=HTMLResponse)
def compare_page(
    request: Request,
    label: str | None = None,
    min_score: str | None = None,
    sort_by: str = "total_score",
    sort_order: str = "desc",
    limit: str | None = None,
) -> HTMLResponse:
    loader = get_loader(request)
    parsed_filters, filter_error = _parse_candidate_filter_params(min_score=min_score, limit=limit)
    if filter_error:
        return HTMLResponse(_message_page("筛选参数错误", filter_error, back_href="/compare"), status_code=400)
    compare = loader.get_compare_rows(
        label=label,
        min_score=parsed_filters["min_score"],
        sort_by=sort_by,
        sort_order=sort_order,
        limit=parsed_filters["limit"],
    )
    factor_matrix = loader.get_factor_group_matrix(
        label=label,
        min_score=parsed_filters["min_score"],
        sort_by=sort_by,
        sort_order=sort_order,
        limit=parsed_filters["limit"],
    )
    return HTMLResponse(_compare_html(compare, factor_matrix))


@router.get("/reports", response_class=HTMLResponse)
def report_center_page(request: Request) -> HTMLResponse:
    return HTMLResponse(_report_center_html(get_loader(request).get_report_index()))


@router.get("/health/outputs", response_class=HTMLResponse)
def output_health_page(request: Request) -> HTMLResponse:
    loader = get_loader(request)
    return HTMLResponse(
        _output_health_html(
            loader.get_output_health(),
            loader.get_failed_symbols(),
            loader.get_data_quality_summary(),
        )
    )


@router.get("/guide", response_class=HTMLResponse)
def guide_page(request: Request) -> HTMLResponse:
    return HTMLResponse(_guide_html(get_loader(request).get_guide()))


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
def candidates(
    request: Request,
    label: str | None = None,
    min_score: str | None = None,
    max_score: str | None = None,
    min_confidence: str | None = None,
    sort_by: str = "total_score",
    sort_order: str = "desc",
    limit: str | None = None,
) -> Any:
    loader = get_loader(request)
    parsed_filters, filter_error = _parse_candidate_filter_params(
        min_score=min_score,
        max_score=max_score,
        min_confidence=min_confidence,
        limit=limit,
    )
    if filter_error:
        return JSONResponse(_empty_filter_error_payload(loader, filter_error), status_code=400)
    payload = loader.load_candidates(
        label=label,
        min_score=parsed_filters["min_score"],
        max_score=parsed_filters["max_score"],
        min_confidence=parsed_filters["min_confidence"],
        sort_by=sort_by,
        sort_order=sort_order,
        limit=parsed_filters["limit"],
    )
    if not payload["ok"] and payload["as_of_date"]:
        return JSONResponse(payload, status_code=400)
    return payload


@router.get("/api/candidates/{symbol}", response_model=CandidateDetailResponse)
def candidate_detail(request: Request, symbol: str) -> Any:
    detail = get_loader(request).get_candidate_by_symbol(symbol)
    if not detail["ok"]:
        return JSONResponse(detail, status_code=404)
    return detail


@router.get("/api/compare", response_model=CompareResponse)
def compare_api(
    request: Request,
    label: str | None = None,
    min_score: str | None = None,
    sort_by: str = "total_score",
    sort_order: str = "desc",
    limit: str | None = None,
) -> Any:
    loader = get_loader(request)
    parsed_filters, filter_error = _parse_candidate_filter_params(min_score=min_score, limit=limit)
    if filter_error:
        return JSONResponse(_empty_filter_error_payload(loader, filter_error), status_code=400)
    payload = loader.get_compare_rows(
        label=label,
        min_score=parsed_filters["min_score"],
        sort_by=sort_by,
        sort_order=sort_order,
        limit=parsed_filters["limit"],
    )
    if not payload["ok"] and payload["as_of_date"]:
        return JSONResponse(payload, status_code=400)
    return payload


@router.get("/api/factor-explanations", response_model=FactorExplanationsResponse)
def factor_explanations(request: Request) -> dict[str, Any]:
    return get_loader(request).load_factor_explanations()


@router.get("/api/factor-explanations/{symbol}", response_model=FactorExplanationsResponse)
def factor_explanations_for_symbol(request: Request, symbol: str) -> Any:
    payload = get_loader(request).get_factor_explanations_by_symbol(symbol)
    if not payload["items"] and payload["ok"]:
        return JSONResponse(payload, status_code=404)
    return payload


@router.get("/api/factor-summary/{symbol}", response_model=FactorSummaryResponse)
def factor_summary_for_symbol(request: Request, symbol: str) -> Any:
    payload = get_loader(request).get_factor_summary_by_symbol(symbol)
    if not payload["ok"]:
        return JSONResponse(payload, status_code=404)
    return payload


@router.get("/api/factor-groups", response_model=FactorGroupMatrixResponse)
def factor_groups(
    request: Request,
    label: str | None = None,
    min_score: str | None = None,
    sort_by: str = "total_score",
    sort_order: str = "desc",
    limit: str | None = None,
) -> Any:
    loader = get_loader(request)
    parsed_filters, filter_error = _parse_candidate_filter_params(min_score=min_score, limit=limit)
    if filter_error:
        return JSONResponse(_empty_filter_error_payload(loader, filter_error), status_code=400)
    payload = loader.get_factor_group_matrix(
        label=label,
        min_score=parsed_filters["min_score"],
        sort_by=sort_by,
        sort_order=sort_order,
        limit=parsed_filters["limit"],
    )
    if not payload["ok"] and payload["as_of_date"]:
        return JSONResponse(payload, status_code=400)
    return payload


@router.get("/api/factor-groups/{factor_group}", response_model=FactorGroupMatrixResponse)
def factor_group_detail(
    request: Request,
    factor_group: str,
    label: str | None = None,
    min_score: str | None = None,
    sort_by: str = "total_score",
    sort_order: str = "desc",
    limit: str | None = None,
) -> Any:
    loader = get_loader(request)
    parsed_filters, filter_error = _parse_candidate_filter_params(min_score=min_score, limit=limit)
    if filter_error:
        return JSONResponse(_empty_filter_error_payload(loader, filter_error), status_code=400)
    payload = loader.get_factor_group_comparison(
        factor_group,
        label=label,
        min_score=parsed_filters["min_score"],
        sort_by=sort_by,
        sort_order=sort_order,
        limit=parsed_filters["limit"],
    )
    if not payload["ok"] and payload["as_of_date"]:
        return JSONResponse(payload, status_code=400)
    return payload


@router.get("/api/output-health")
def output_health(request: Request) -> dict[str, Any]:
    return get_loader(request).get_output_health()


@router.get("/api/report-index")
def report_index(request: Request) -> dict[str, Any]:
    return get_loader(request).get_report_index()


@router.get("/api/failed-symbols")
def failed_symbols(request: Request) -> dict[str, Any]:
    return get_loader(request).get_failed_symbols()


@router.get("/api/data-quality")
def data_quality(request: Request) -> dict[str, Any]:
    return get_loader(request).get_data_quality_summary()


@router.get("/api/guide")
def guide(request: Request) -> dict[str, Any]:
    return get_loader(request).get_guide()


@router.get("/api/lists")
def research_lists(request: Request) -> dict[str, Any]:
    return get_loader(request).get_research_lists()


@router.get("/api/lists/{list_id}")
def research_list_detail(request: Request, list_id: str) -> Any:
    payload = get_loader(request).get_research_list(list_id)
    if not payload.get("ok"):
        return JSONResponse(payload, status_code=404)
    return payload


@router.get("/api/labels")
def labels(
    request: Request,
    primary_type: str | None = None,
    research_action: str | None = None,
    risk_level: str | None = None,
    limit: str | None = None,
) -> Any:
    parsed_limit, error = _parse_optional_int(limit, "limit")
    if error:
        return JSONResponse({"ok": False, "message": error, "items": []}, status_code=400)
    return get_loader(request).get_labels(
        primary_type=primary_type,
        research_action=research_action,
        risk_level=risk_level,
        limit=parsed_limit,
    )


@router.get("/api/stocks/search")
def stock_search(request: Request, q: str = "") -> Any:
    payload = get_loader(request).search_stocks(q)
    if not payload.get("ok"):
        return JSONResponse(payload, status_code=400)
    return payload


@router.get("/api/stocks/{symbol}/research")
def stock_research(request: Request, symbol: str) -> Any:
    payload = get_loader(request).get_stock_research(symbol)
    if not payload.get("ok"):
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
    workflow: dict[str, Any],
) -> str:
    filters = candidates.get("filters", {})
    default_limit = int(filters.get("limit") or 10)
    rows = candidates.get("items", [])[:default_limit]
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
      <h2>快捷入口</h2>
      <div class="entry-row">
        <a class="primary-link" href="/compare">查看候选股横向对比</a>
        <a class="primary-link" href="/reports">报告中心</a>
        <a class="primary-link" href="/health/outputs">输出健康检查</a>
        <a class="primary-link" href="/guide">运行指引 / 操作手册</a>
      </div>
    </section>

    <section>
      <h2>Pipeline Summary</h2>
      {_summary_grid(summary_payload)}
    </section>

    <section>
      <h2>Workflow Summary</h2>
      {_workflow_summary_panel(workflow)}
    </section>

    <section>
      <h2>筛选与排序</h2>
      {_filter_panel(filters, candidates)}
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


def _compare_html(compare: dict[str, Any], factor_matrix: dict[str, Any]) -> str:
    if not compare.get("ok"):
        body = f"""
        <header class="topbar">
          <div>
            <a href="/" class="back-link">返回首页</a>
            <h1>候选股横向对比</h1>
          </div>
        </header>
        <section class="notice">
          <strong>{escape(compare.get("message") or NO_DAILY_OUTPUT_MESSAGE)}</strong>
        </section>
        <p class="disclaimer">仅为个人研究辅助，不构成投资建议。</p>
        """
        return _page_shell("候选股横向对比", body)

    rows = compare.get("items", [])
    body = f"""
    <header class="topbar">
      <div>
        <a href="/" class="back-link">返回首页</a>
        <h1>候选股横向对比</h1>
        <p>最新数据日期：{escape(str(compare.get("as_of_date") or ""))}</p>
      </div>
      <span class="badge">Compare</span>
    </header>

    <section>
      <h2>筛选与排序</h2>
      {_filter_panel(compare.get("filters", {}), compare)}
    </section>

    <section>
      <h2>候选股对比总表</h2>
      {_candidate_table(rows)}
    </section>

    <section>
      <h2>因子组贡献对比表</h2>
      {_factor_group_matrix_table(factor_matrix.get("items", []))}
    </section>

    <section>
      <h2>风险标记对比</h2>
      {_risk_compare_table(rows)}
    </section>

    <section>
      <h2>主要正向证据对比</h2>
      {_positive_evidence_table(rows)}
    </section>

    <section>
      <h2>研究解释区</h2>
      {_research_explanation_list(rows)}
    </section>

    <p class="disclaimer">仅为个人研究辅助，不构成投资建议。</p>
    """
    return _page_shell("候选股横向对比", body)


def _report_center_html(index: dict[str, Any]) -> str:
    body = f"""
    <header class="topbar">
      <div>
        <a href="/" class="back-link">返回首页</a>
        <h1>报告中心</h1>
        <p>最新数据日期：{escape(str(index.get("latest_date") or ""))}</p>
      </div>
      <span class="badge">Reports</span>
    </header>

    {_report_empty_notice(index)}

    <section>
      <h2>每日报告列表</h2>
      {_report_index_table(index.get("daily_reports", []), report_kind="daily")}
    </section>

    <section>
      <h2>单股报告列表</h2>
      {_report_index_table(index.get("stock_reports", []), report_kind="stock")}
    </section>

    <section>
      <h2>回测报告列表</h2>
      {_report_index_table(index.get("backtest_reports", []), report_kind="backtest")}
    </section>

    <p class="disclaimer">仅为个人研究辅助，不构成投资建议。</p>
    """
    return _page_shell("报告中心", body)


def _output_health_html(health: dict[str, Any], failed: dict[str, Any], quality: dict[str, Any]) -> str:
    coverage = health.get("report_coverage", {})
    body = f"""
    <header class="topbar">
      <div>
        <a href="/" class="back-link">返回首页</a>
        <h1>输出健康检查</h1>
        <p>最新数据日期：{escape(str(health.get("latest_date") or ""))}</p>
      </div>
      <span class="badge">status: {escape(str(health.get("status") or ""))}</span>
    </header>

    <section>
      <h2>outputs 完整性检查</h2>
      {_required_files_table(health.get("required_files", []))}
    </section>

    <section>
      <h2>单股报告覆盖率</h2>
      <div class="grid">
        <div class="metric"><span>候选股数量</span><strong>{escape(str(coverage.get("candidate_count", 0)))}</strong></div>
        <div class="metric"><span>已有单股报告</span><strong>{escape(str(coverage.get("stock_report_count", 0)))}</strong></div>
        <div class="metric"><span>缺失单股报告</span><strong>{escape(str(coverage.get("missing_stock_report_count", 0)))}</strong></div>
      </div>
      {_missing_stock_reports(coverage.get("missing_stock_reports", []))}
    </section>

    <section>
      <h2>failed symbols 检查</h2>
      {_failed_symbols_table(failed.get("items", []))}
    </section>

    <section>
      <h2>数据质量检查</h2>
      {_data_quality_panel(quality)}
    </section>

    <section>
      <h2>Workflow Summary</h2>
      {_workflow_summary_panel(health.get("workflow_summary", {}))}
    </section>

    <p class="disclaimer">仅为个人研究辅助，不构成投资建议。</p>
    """
    return _page_shell("输出健康检查", body)


def _guide_html(guide: dict[str, Any]) -> str:
    body = f"""
    <header class="topbar">
      <div>
        <a href="/" class="back-link">返回首页</a>
        <h1>A 股个人研究终端运行指引</h1>
      </div>
      <span class="badge">Guide</span>
    </header>

    <section>
      <h2>推荐日常运行顺序</h2>
      {_ordered_list(guide.get("recommended_workflow", []))}
    </section>

    <section>
      <h2>常用命令</h2>
      {_command_sections(guide.get("commands", {}))}
    </section>

    <section>
      <h2>主要输出文件说明</h2>
      {_plain_list(guide.get("output_paths", []))}
    </section>

    <section>
      <h2>Dashboard 页面导航</h2>
      {_navigation_table(guide.get("navigation", []))}
    </section>

    <section>
      <h2>常见问题和排错</h2>
      {_plain_list(guide.get("troubleshooting", []))}
    </section>

    <section>
      <h2>当前 Phase 状态</h2>
      {_plain_list(guide.get("phase_status", []))}
    </section>

    <p class="disclaimer">{escape((guide.get("disclaimers") or ["仅为个人研究辅助，不构成投资建议。"])[0])}</p>
    """
    return _page_shell("A 股个人研究终端运行指引", body)


def _lists_overview_html(payload: dict[str, Any]) -> str:
    lists = payload.get("lists", [])
    body = f"""
    <header class="topbar">
      <div>
        <a href="/" class="back-link">返回首页</a>
        <h1>多榜单总览</h1>
        <p>当前为 fixed historical research view，日期为 {escape(str(payload.get("date") or ""))}。</p>
      </div>
      <span class="badge">Research Lists</span>
    </header>

    <section class="notice">
      <p>榜单为从全市场有效股票标签层中筛选出的 Top N 研究视角，不代表只有这些股票存在研究数据。</p>
    </section>

    <section>
      <h2>股票搜索</h2>
      {_stock_search_form()}
    </section>

    <section>
      <h2>榜单卡片</h2>
      {_list_cards(lists)}
    </section>

    <p class="disclaimer">{escape(API_DISCLAIMER)}</p>
    """
    return _page_shell("多榜单总览", body)


def _list_detail_html(payload: dict[str, Any]) -> str:
    list_id = str(payload.get("list_id", ""))
    is_risk_list = list_id == "high_risk_active"
    risk_notice = "<p class=\"notice-text\">风险观察，不作为稳健候选。</p>" if is_risk_list else ""
    body = f"""
    <header class="topbar">
      <div>
        <a href="/lists" class="back-link">返回榜单总览</a>
        <h1>{escape(str(payload.get("list_name") or list_id))}</h1>
        <p>当前为 fixed historical research view，日期为 {escape(str(payload.get("date") or ""))}。</p>
      </div>
      <span class="badge">{escape(list_id)}</span>
    </header>

    <section>
      <h2>榜单说明</h2>
      <p>{escape(str(payload.get("description") or ""))}</p>
      <dl>
        <dt>sort_logic</dt><dd>{escape(str(payload.get("sort_logic") or ""))}</dd>
        <dt>eligible_filters</dt><dd>{escape("; ".join(str(item) for item in _as_list(payload.get("eligible_filters"))))}</dd>
        <dt>source_universe_count</dt><dd>{escape(str(payload.get("source_universe_count", "")))}</dd>
        <dt>eligible_count</dt><dd>{escape(str(payload.get("eligible_count", "")))}</dd>
        <dt>top_n</dt><dd>{escape(str(payload.get("top_n", "")))}</dd>
        <dt>excluded_count</dt><dd>{escape(str(payload.get("excluded_count", "")))}</dd>
        <dt>item_count</dt><dd>{escape(str(payload.get("item_count", 0)))}</dd>
      </dl>
      <p class="muted">榜单为从全市场有效股票标签层中筛选出的 Top N 研究视角，不代表只有这些股票存在研究数据。</p>
      {risk_notice}
    </section>

    <section>
      <h2>榜单股票</h2>
      {_list_items_table(payload.get("items", []))}
    </section>

    <p class="disclaimer">{escape(API_DISCLAIMER)}</p>
    """
    return _page_shell(str(payload.get("list_name") or list_id), body)


def _labels_html(payload: dict[str, Any]) -> str:
    body = f"""
    <header class="topbar">
      <div>
        <a href="/" class="back-link">返回首页</a>
        <h1>标签筛选</h1>
        <p>当前为 fixed historical research view，日期为 {escape(str(payload.get("date") or ""))}。</p>
      </div>
      <span class="badge">Labels</span>
    </header>

    <section>
      <h2>筛选条件</h2>
      {_label_filter_form(payload.get("filters", {}))}
    </section>

    <section>
      <h2>统计</h2>
      <div class="columns three">
        <div><h3>primary_type</h3>{_distribution_list(payload.get("primary_type_counts", {}))}</div>
        <div><h3>research_action</h3>{_distribution_list(payload.get("research_action_counts", {}))}</div>
        <div><h3>risk_level</h3>{_distribution_list(payload.get("risk_level_counts", {}))}</div>
      </div>
    </section>

    <section>
      <h2>Labeled Candidates</h2>
      {_list_items_table(payload.get("items", []))}
    </section>

    <p class="disclaimer">{escape(API_DISCLAIMER)}</p>
    """
    return _page_shell("标签筛选", body)


def _search_html(payload: dict[str, Any]) -> str:
    query = str(payload.get("query") or "")
    body = f"""
    <header class="topbar">
      <div>
        <a href="/" class="back-link">返回首页</a>
        <h1>股票搜索</h1>
        <p>支持股票代码、完整 symbol 和中文名称模糊搜索。</p>
      </div>
      <span class="badge">Search</span>
    </header>

    <section>
      <h2>搜索</h2>
      {_stock_search_form(query)}
    </section>

    <section>
      <h2>搜索结果</h2>
      {_search_results(payload)}
    </section>

    <p class="disclaimer">{escape(API_DISCLAIMER)}</p>
    """
    return _page_shell("股票搜索", body)


def _stock_research_html(detail: dict[str, Any]) -> str:
    symbol = str(detail.get("symbol") or "")
    name = str(detail.get("name") or "")
    score_breakdown = detail.get("score_breakdown", {}) if isinstance(detail.get("score_breakdown"), dict) else {}
    score_cards = [
        ("total_score", detail.get("total_score", "")),
        ("momentum_score", score_breakdown.get("momentum_score", "")),
        ("trend_score", score_breakdown.get("trend_score", "")),
        ("relative_strength_score", score_breakdown.get("relative_strength_score", "")),
        ("risk_score", score_breakdown.get("risk_score", "")),
        ("liquidity_score", score_breakdown.get("liquidity_score", "")),
    ]
    body = f"""
    <header class="topbar">
      <div>
        <a href="/" class="back-link">返回首页</a>
        <h1>{escape(symbol)} {escape(name)}</h1>
        <p>个股研究详情｜日期：{escape(str(detail.get("date") or ""))}</p>
      </div>
      <span class="tag-badge">{escape(str(detail.get("primary_type") or ""))}</span>
    </header>

    <section>
      <h2>基本信息</h2>
      <div class="grid">
        <div class="metric"><span>rank</span><strong>{escape(str(detail.get("current_rank", "暂无")))}</strong></div>
        <div class="metric"><span>research_action</span><strong>{escape(str(detail.get("research_action", "暂无")))}</strong></div>
        <div class="metric"><span>confidence_level</span><strong>{escape(str(detail.get("confidence_level", "暂无")))}</strong></div>
        <div class="metric"><span>risk_level</span><strong>{escape(str(detail.get("risk_level", "暂无")))}</strong></div>
      </div>
      <p><strong>secondary_tags:</strong> {escape("; ".join(str(item) for item in _as_list(detail.get("secondary_tags"))))}</p>
    </section>

    <section>
      <h2>分数拆解</h2>
      <div class="grid">
        {''.join(f'<div class="metric"><span>{escape(label)}</span><strong>{escape(_format_metric(value) if value not in (None, "") else "暂无")}</strong></div>' for label, value in score_cards)}
      </div>
    </section>

    <section class="columns">
      <div>
        <h2>标签解释</h2>
        <p>{escape(str(detail.get("label_reason") or "暂无"))}</p>
        <h3>confirmation_signals</h3>
        {_plain_list(_as_list(detail.get("confirmation_signals")))}
      </div>
      <div>
        <h2>失效信号</h2>
        {_plain_list(_as_list(detail.get("invalidation_signals")))}
      </div>
    </section>

    <section class="columns">
      <div>
        <h2>证据链</h2>
        {_evidence_panel(detail.get("evidence", {}))}
      </div>
      <div>
        <h2>风险与数据质量</h2>
        <dl>
          <dt>risk_flags</dt><dd>{escape(_fallback(detail.get("risk_flags"), "暂无"))}</dd>
          <dt>warnings</dt><dd>{escape(_fallback(detail.get("warnings"), "暂无"))}</dd>
          <dt>data_quality</dt><dd>{escape(_fallback(detail.get("data_quality"), "暂无"))}</dd>
        </dl>
      </div>
    </section>

    <section>
      <h2>因子解释</h2>
      {_factor_summary_table(detail.get("factor_explanation", {}))}
    </section>

    <section>
      <h2>所属榜单</h2>
      {_related_lists(detail.get("related_lists", []))}
    </section>

    <section>
      <h2>报告链接</h2>
      {_research_report_links(detail.get("report_links", {}))}
    </section>

    <p class="disclaimer">{escape(API_DISCLAIMER)}</p>
    """
    return _page_shell(f"{symbol} 个股研究详情", body)


def _stock_detail_html(detail: dict[str, Any]) -> str:
    row = detail["item"] or {}
    symbol = str(row.get("symbol") or detail.get("symbol") or "")
    name = str(row.get("name") or "")
    explanations = detail.get("factor_explanations", [])
    factor_summary = detail.get("factor_summary") or {}
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

    <section>
      <h2>分数解释</h2>
      <p>{escape(str(factor_summary.get("explanation") or "当前候选排序来自综合评分，仍需结合后续数据复核。该结论仅用于个人研究排序，不构成投资建议。"))}</p>
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
      <h2>因子贡献总览</h2>
      {_factor_summary_table(factor_summary)}
    </section>

    <section class="columns three">
      <div>
        <h2>主要正向因子</h2>
        {_factor_cards(factor_summary.get("positive_factors", []), "暂无显著正向因子。")}
      </div>
      <div>
        <h2>主要负向/风险因子</h2>
        {_factor_cards(factor_summary.get("risk_factors", []), "暂无显著负向或风险因子。")}
      </div>
      <div>
        <h2>需要继续观察的信号</h2>
        {_factor_cards(factor_summary.get("watch_signals", []), "暂无额外观察信号。")}
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


def _stock_search_form(query: str = "") -> str:
    return f"""
    <form method="get" action="/search" class="filter-form">
      <label>股票代码或名称
        <input name="q" value="{escape(query)}" placeholder="600000 / sh.600000 / 平安">
      </label>
      <button type="submit">搜索</button>
    </form>
    """


def _list_cards(lists: list[dict[str, Any]]) -> str:
    if not lists:
        return "<p class=\"muted\">暂无榜单输出，请先运行 generate_research_views.py。</p>"
    cards = []
    for item in lists:
        list_id = str(item.get("list_id", ""))
        preview = item.get("items_preview", [])
        cards.append(
            f"""
            <div class="list-card">
              <h3>{escape(str(item.get("list_name") or list_id))}</h3>
              <p>{escape(str(item.get("description") or ""))}</p>
              <dl>
                <dt>item_count</dt><dd>{escape(str(item.get("item_count", 0)))}</dd>
                <dt>sort_logic</dt><dd>{escape(str(item.get("sort_logic") or ""))}</dd>
                <dt>eligible_filters</dt><dd>{escape("; ".join(str(x) for x in _as_list(item.get("eligible_filters"))))}</dd>
              </dl>
              {_list_preview(preview)}
              <p><a class="primary-link" href="/lists/{escape(list_id)}">查看榜单详情</a></p>
            </div>
            """
        )
    return "<div class=\"list-grid\">" + "".join(cards) + "</div>"


def _list_preview(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<p class=\"muted\">当前榜单暂无候选。</p>"
    rows = "".join(
        f"<li><a href=\"/stocks/{escape(str(item.get('symbol', '')))}\">{escape(str(item.get('symbol', '')))} {escape(str(item.get('name', '')))}</a></li>"
        for item in items[:5]
        if isinstance(item, dict)
    )
    return f"<ul>{rows}</ul>"


def _list_items_table(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<p class=\"muted\">当前榜单暂无候选。</p>"
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol", ""))
        rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('rank', '')))}</td>"
            f"<td><a href=\"/stocks/{escape(symbol)}\">{escape(symbol)}</a></td>"
            f"<td>{escape(str(item.get('name', '')))}</td>"
            f"<td>{escape(_format_metric(item.get('total_score', '')))}</td>"
            f"<td><span class=\"tag-badge\">{escape(str(item.get('primary_type', '')))}</span></td>"
            f"<td>{escape('; '.join(str(x) for x in _as_list(item.get('secondary_tags'))))}</td>"
            f"<td>{escape(str(item.get('research_action', '')))}</td>"
            f"<td>{escape(str(item.get('confidence_level', '')))}</td>"
            f"<td>{escape(str(item.get('risk_level', '')))}</td>"
            f"<td>{escape(str(item.get('label_reason', '')))}</td>"
            f"<td>{escape('; '.join(str(x) for x in _as_list(item.get('confirmation_signals'))))}</td>"
            f"<td>{escape('; '.join(str(x) for x in _as_list(item.get('invalidation_signals'))))}</td>"
            f"<td><a href=\"/stocks/{escape(symbol)}\">个股详情</a></td>"
            "</tr>"
        )
    return f"""<div class="table-wrap"><table>
<thead><tr><th>rank</th><th>symbol</th><th>name</th><th>total_score</th><th>primary_type</th><th>secondary_tags</th><th>research_action</th><th>confidence_level</th><th>risk_level</th><th>label_reason</th><th>confirmation_signals</th><th>invalidation_signals</th><th>detail</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table></div>"""


def _label_filter_form(filters: dict[str, Any]) -> str:
    return f"""
    <form method="get" action="/labels" class="filter-form">
      <label>primary_type
        <input name="primary_type" value="{escape(str(filters.get('primary_type') or ''))}">
      </label>
      <label>research_action
        <input name="research_action" value="{escape(str(filters.get('research_action') or ''))}">
      </label>
      <label>risk_level
        <input name="risk_level" value="{escape(str(filters.get('risk_level') or ''))}">
      </label>
      <label>limit
        <input name="limit" type="number" min="1" value="{escape(str(filters.get('limit') or ''))}">
      </label>
      <button type="submit">应用</button>
    </form>
    """


def _search_results(payload: dict[str, Any]) -> str:
    items = payload.get("items", [])
    if not payload.get("query"):
        return f"<p class=\"muted\">{escape(str(payload.get('message') or '请输入搜索条件。'))}</p>"
    if not items:
        return "<p class=\"muted\">未在当前 fixed historical candidate set 中找到。</p>"
    rows = []
    for item in items:
        symbol = str(item.get("symbol", ""))
        report = item.get("report_links") if isinstance(item.get("report_links"), dict) else {}
        report_link = report.get("page_url") or ""
        report_cell = f'<a href="{escape(str(report_link))}">报告</a>' if report_link else "暂无"
        rows.append(
            "<tr>"
            f"<td><a href=\"/stocks/{escape(symbol)}\">{escape(symbol)}</a></td>"
            f"<td>{escape(str(item.get('name', '')))}</td>"
            f"<td>{escape(str(item.get('rank', '')))}</td>"
            f"<td>{escape(_format_metric(item.get('total_score', '')))}</td>"
            f"<td>{escape(str(item.get('primary_type', '')))}</td>"
            f"<td>{escape(str(item.get('research_action', '')))}</td>"
            f"<td>{escape(str(item.get('confidence_level', '')))}</td>"
            f"<td>{escape(str(item.get('risk_level', '')))}</td>"
            f"<td><a href=\"/stocks/{escape(symbol)}\">进入个股详情页</a></td>"
            f"<td>{report_cell}</td>"
            "</tr>"
        )
    return f"""<div class="table-wrap"><table>
<thead><tr><th>symbol</th><th>name</th><th>rank</th><th>total_score</th><th>primary_type</th><th>research_action</th><th>confidence_level</th><th>risk_level</th><th>detail</th><th>report</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table></div>"""


def _evidence_panel(evidence: Any) -> str:
    payload = evidence if isinstance(evidence, dict) else {}
    return (
        "<dl>"
        f"<dt>positive_evidence</dt><dd>{escape(_fallback(payload.get('positive'), '暂无'))}</dd>"
        f"<dt>negative_evidence</dt><dd>{escape(_fallback(payload.get('negative'), '暂无'))}</dd>"
        "</dl>"
    )


def _related_lists(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<p class=\"muted\">当前未出现在任何多榜单中。</p>"
    rows = "".join(
        f"<li><a href=\"/lists/{escape(str(item.get('list_id', '')))}\">{escape(str(item.get('list_name') or item.get('list_id') or ''))}</a>，position {escape(str(item.get('position', '')))} / {escape(str(item.get('item_count', '')))}</li>"
        for item in items
        if isinstance(item, dict)
    )
    return f"<ul>{rows}</ul>"


def _research_report_links(report: Any) -> str:
    payload = report if isinstance(report, dict) else {}
    links = []
    if payload.get("markdown_url"):
        links.append(f"<a class=\"primary-link\" href=\"{escape(str(payload['markdown_url']))}\">Markdown report</a>")
    if payload.get("html_url"):
        links.append(f"<a class=\"primary-link\" href=\"{escape(str(payload['html_url']))}\">HTML report</a>")
    if payload.get("page_url"):
        links.append(f"<a class=\"primary-link\" href=\"{escape(str(payload['page_url']))}\">浏览报告</a>")
    if not links:
        return "<p class=\"muted\">当前暂无报告链接。</p>"
    return "<div class=\"link-row\">" + "".join(links) + "</div>"


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [part for part in str(value).split(";") if part]


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


def _workflow_summary_panel(workflow: dict[str, Any]) -> str:
    if not workflow or not workflow.get("ok"):
        return "<p class=\"muted\">No workflow summary found. Run run_daily_workflow.py to generate one.</p>"
    summary = workflow.get("summary") if isinstance(workflow.get("summary"), dict) else {}
    if not summary:
        return "<p class=\"muted\">Workflow summary could not be read.</p>"
    fields = [
        ("status", summary.get("status", "")),
        ("end_date", summary.get("end_date", workflow.get("latest_date", ""))),
        ("elapsed_seconds", summary.get("elapsed_seconds", "")),
        ("summary_path", summary.get("summary_path", workflow.get("path", ""))),
        ("log_path", summary.get("log_path", "")),
        ("dashboard_url", summary.get("dashboard_url", "")),
    ]
    cards = "".join(
        f"<div class=\"metric\"><span>{escape(label)}</span><strong>{escape(str(value or ''))}</strong></div>"
        for label, value in fields
    )
    missing = summary.get("missing_files", [])
    missing_html = ""
    if isinstance(missing, list) and missing:
        missing_html = "<p class=\"notice-text\">missing_files: " + escape(str(len(missing))) + "</p>"
    return f"<div class=\"grid\">{cards}</div>{missing_html}"


def _candidate_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p class=\"muted\">暂无候选股数据。</p>"
    body = "".join(_candidate_row(row) for row in rows)
    return f"""<div class="table-wrap"><table>
<thead><tr><th>rank</th><th>symbol</th><th>name</th><th>label</th><th>total_score</th><th>confidence</th><th>momentum</th><th>trend</th><th>relative_strength</th><th>risk_score</th><th>liquidity</th><th>risk_flags</th><th>detail</th><th>report</th></tr></thead>
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
        f"<td><span class=\"tag-badge\">{escape(str(row.get('label', '')))}</span></td>"
        f"<td>{escape(_format_metric(row.get('total_score', '')))}</td>"
        f"<td>{escape(_format_metric(row.get('confidence', '')))}</td>"
        f"<td>{escape(_format_metric(row.get('momentum_score', '')))}</td>"
        f"<td>{escape(_format_metric(row.get('trend_score', '')))}</td>"
        f"<td>{escape(_format_metric(row.get('relative_strength_score', '')))}</td>"
        f"<td>{escape(_format_metric(row.get('risk_score', '')))}</td>"
        f"<td>{escape(_format_metric(row.get('liquidity_score', '')))}</td>"
        f"<td class=\"risk-cell\">{escape(risk)}</td>"
        f"<td><a href=\"{detail_href}\">详情</a></td>"
        f"<td><a href=\"{report_href}\">报告</a></td>"
        "</tr>"
    )


def _filter_panel(filters: dict[str, Any], candidates: dict[str, Any]) -> str:
    label = str(filters.get("label") or "")
    sort_by = str(filters.get("sort_by") or "total_score")
    sort_order = str(filters.get("sort_order") or "desc")
    min_score = _form_value(filters.get("min_score"))
    max_score = _form_value(filters.get("max_score"))
    min_confidence = _form_value(filters.get("min_confidence"))
    limit = _form_value(filters.get("limit"))
    label_options = [""] + RESEARCH_LABELS
    options = "".join(
        f"<option value=\"{escape(value)}\"{' selected' if value == label else ''}>{escape(value or '全部')}</option>"
        for value in label_options
    )
    sort_options = [
        "rank",
        "total_score",
        "confidence",
        "momentum_score",
        "trend_score",
        "relative_strength_score",
        "risk_score",
        "liquidity_score",
    ]
    sort_select = "".join(
        f"<option value=\"{field}\"{' selected' if field == sort_by else ''}>{field}</option>"
        for field in sort_options
    )
    order_select = "".join(
        f"<option value=\"{order}\"{' selected' if order == sort_order else ''}>{order}</option>"
        for order in ["desc", "asc"]
    )
    quick_links = [
        ("按分数排序", "/?sort_by=total_score&sort_order=desc"),
        ("按风险分排序", "/?sort_by=risk_score&sort_order=asc"),
        ("按置信度排序", "/?sort_by=confidence&sort_order=desc"),
    ]
    label_links = [("全部", "/")] + [(label_name, f"/?label={label_name}") for label_name in RESEARCH_LABELS]
    warning = f"<p class=\"notice-text\">{escape(candidates.get('message', ''))}</p>" if candidates.get("message") else ""
    return f"""
    <form method="get" class="filter-form">
      <label>标签
        <select name="label">{options}</select>
      </label>
      <label>最低分
        <input name="min_score" type="number" step="0.01" value="{escape(min_score)}">
      </label>
      <label>最高分
        <input name="max_score" type="number" step="0.01" value="{escape(max_score)}">
      </label>
      <label>最低置信度
        <input name="min_confidence" type="number" step="0.01" value="{escape(min_confidence)}">
      </label>
      <label>排序
        <select name="sort_by">{sort_select}</select>
      </label>
      <label>方向
        <select name="sort_order">{order_select}</select>
      </label>
      <label>数量
        <input name="limit" type="number" min="1" value="{escape(limit)}">
      </label>
      <button type="submit">应用</button>
    </form>
    {warning}
    <p class="muted">当前筛选条件：label={escape(label or '全部')}，min_score={escape(min_score or '无')}，max_score={escape(max_score or '无')}，min_confidence={escape(min_confidence or '无')}，sort_by={escape(sort_by)}，sort_order={escape(sort_order)}，limit={escape(limit or '默认10')}</p>
    <p>筛选后候选数量：<strong>{escape(str(candidates.get("count", 0)))}</strong> / 原始数量：{escape(str(candidates.get("total_count", 0)))}</p>
    <div class="link-row">
      {''.join(f'<a href="{escape(href)}">{escape(text)}</a>' for text, href in quick_links)}
    </div>
    <div class="link-row label-links">
      {''.join(f'<a href="{escape(href)}">{escape(text)}</a>' for text, href in label_links)}
    </div>
    """


def _form_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _factor_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p class=\"muted\">暂无真实因子贡献表，请先生成 factor_explanations 输出。</p>"
    columns = ["factor_group", "raw_value", "normalized_score", "weight", "contribution", "explanation"]
    header = "".join(f"<th>{escape(column)}</th>" for column in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(_format_metric(row.get(column, '')))}</td>" for column in columns) + "</tr>"
        for row in rows
    )
    return f"<div class=\"table-wrap\"><table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>"


def _factor_summary_table(summary: dict[str, Any]) -> str:
    rows = summary.get("items") if isinstance(summary, dict) else []
    if not rows:
        return "<p class=\"muted\">暂无真实因子贡献表，请先生成 factor_explanations 输出。</p>"
    columns = ["display_name", "factor_group", "normalized_score", "weight", "contribution", "explanation"]
    header = "".join(f"<th>{escape(column)}</th>" for column in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(_format_metric(row.get(column, '')))}</td>" for column in columns) + "</tr>"
        for row in rows
    )
    return f"<div class=\"table-wrap\"><table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>"


def _factor_group_matrix_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p class=\"muted\">暂无真实因子贡献表，请先生成 factor_explanations 输出。</p>"
    columns = [
        ("symbol", "symbol"),
        ("name", "name"),
        ("动量贡献", "momentum_contribution"),
        ("趋势贡献", "trend_contribution"),
        ("相对强度贡献", "relative_strength_contribution"),
        ("风险贡献", "risk_contribution"),
        ("流动性贡献", "liquidity_contribution"),
        ("最大正向贡献组", "top_positive_factor_group"),
        ("主要风险组", "top_risk_factor_group"),
        ("warning", "factor_warning"),
    ]
    header = "".join(f"<th>{escape(label)}</th>" for label, _ in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(_format_metric(row.get(key, '')))}</td>" for _, key in columns) + "</tr>"
        for row in rows
    )
    return f"<div class=\"table-wrap\"><table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>"


def _report_empty_notice(index: dict[str, Any]) -> str:
    if index.get("ok"):
        return ""
    return f"<section class=\"notice\"><strong>{escape(index.get('message') or 'No reports found. Please generate research reports first.')}</strong></section>"


def _report_index_table(rows: list[dict[str, Any]], *, report_kind: str) -> str:
    if not rows:
        return "<p class=\"muted\">No reports found. Please generate research reports first.</p>"
    columns = ["as_of_date", "symbol", "formats", "markdown", "html", "page"]
    header = "".join(f"<th>{escape(column)}</th>" for column in columns)
    body_parts = []
    for row in rows:
        symbol = str(row.get("symbol", ""))
        page_url = _report_page_url(row, report_kind)
        page_link = f"<a href=\"{escape(page_url)}\">浏览</a>" if page_url else ""
        body_parts.append(
            "<tr>"
            f"<td>{escape(str(row.get('as_of_date', '')))}</td>"
            f"<td>{escape(symbol)}</td>"
            f"<td>{escape(', '.join(row.get('formats', [])))}</td>"
            f"<td>{_file_link(row.get('markdown_path'), 'Markdown')}</td>"
            f"<td>{_file_link(row.get('html_path'), 'HTML')}</td>"
            f"<td>{page_link}</td>"
            "</tr>"
        )
    return f"<div class=\"table-wrap\"><table><thead><tr>{header}</tr></thead><tbody>{''.join(body_parts)}</tbody></table></div>"


def _report_page_url(row: dict[str, Any], report_kind: str) -> str:
    if report_kind == "daily":
        return "/reports/daily"
    if report_kind == "stock":
        return str(row.get("page_url") or "")
    return ""


def _file_link(path: Any, label: str) -> str:
    if not path:
        return ""
    return f"<span title=\"{escape(str(path))}\">{escape(label)}</span>"


def _required_files_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p class=\"muted\">No daily research output found. Please run run_daily_research.py first.</p>"
    header = "<th>status</th><th>path</th>"
    body = "".join(
        f"<tr><td><span class=\"status {escape(str(row.get('status', '')))}\">{escape(str(row.get('status', '')))}</span></td><td>{escape(str(row.get('path', '')))}</td></tr>"
        for row in rows
    )
    return f"<div class=\"table-wrap\"><table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>"


def _missing_stock_reports(symbols: list[str]) -> str:
    if not symbols:
        return "<p class=\"muted\">单股报告覆盖完整。</p>"
    return "<p class=\"muted\">缺失单股报告：" + escape(", ".join(symbols)) + "</p>"


def _failed_symbols_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p class=\"muted\">暂无 failed symbols 记录。</p>"
    columns = ["source", "symbol", "name", "error_type", "error_message", "can_retry"]
    header = "".join(f"<th>{escape(column)}</th>" for column in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(str(row.get(column, '')))}</td>" for column in columns) + "</tr>"
        for row in rows
    )
    return f"<div class=\"table-wrap\"><table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>"


def _data_quality_panel(quality: dict[str, Any]) -> str:
    warnings = quality.get("warnings", [])
    counts = quality.get("error_type_counts", {})
    if not warnings and not counts and not quality.get("fetch_error_count"):
        status_text = "当前 outputs 未发现阻断 Dashboard 展示的严重数据质量问题。"
    else:
        status_text = "当前 outputs 存在非阻断 warning，请结合下方字段复核。"
    counts_text = ", ".join(f"{key}:{value}" for key, value in counts.items()) if isinstance(counts, dict) else ""
    warning_items = "<ul>" + "".join(f"<li>{escape(str(item))}</li>" for item in warnings) + "</ul>" if warnings else "<p class=\"muted\">暂无 warning。</p>"
    return f"""
    <p>{escape(status_text)}</p>
    <div class="grid">
      <div class="metric"><span>fetch_error_count</span><strong>{escape(str(quality.get("fetch_error_count", 0)))}</strong></div>
      <div class="metric"><span>error_type_counts</span><strong>{escape(counts_text or '{}')}</strong></div>
    </div>
    <h3>warnings</h3>
    {warning_items}
    """


def _ordered_list(items: list[str]) -> str:
    if not items:
        return "<p class=\"muted\">暂无内容。</p>"
    return "<ol>" + "".join(f"<li>{escape(str(item))}</li>" for item in items) + "</ol>"


def _plain_list(items: list[str]) -> str:
    if not items:
        return "<p class=\"muted\">暂无内容。</p>"
    return "<ul>" + "".join(f"<li>{escape(str(item))}</li>" for item in items) + "</ul>"


def _command_sections(commands: dict[str, list[str]]) -> str:
    if not commands:
        return "<p class=\"muted\">暂无命令。</p>"
    sections = []
    for title, lines in commands.items():
        command_text = "\n".join(str(line) for line in lines)
        sections.append(
            f"<div class=\"command-block\"><h3>{escape(str(title))}</h3>"
            f"<pre><code>{escape(command_text)}</code></pre></div>"
        )
    return "".join(sections)


def _navigation_table(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<p class=\"muted\">暂无导航。</p>"
    header = "<th>path</th><th>说明</th><th>链接</th>"
    body_parts = []
    for item in items:
        path = str(item.get("path", ""))
        label = str(item.get("label", ""))
        link = "" if "{" in path else f"<a href=\"{escape(path)}\">打开</a>"
        body_parts.append(
            f"<tr><td><code>{escape(path)}</code></td><td>{escape(label)}</td><td>{link}</td></tr>"
        )
    return f"<div class=\"table-wrap\"><table><thead><tr>{header}</tr></thead><tbody>{''.join(body_parts)}</tbody></table></div>"


def _risk_compare_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p class=\"muted\">暂无风险对比数据。</p>"
    columns = ["symbol", "name", "risk_score", "risk_flags", "negative_evidence", "warnings"]
    header = "".join(f"<th>{escape(column)}</th>" for column in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(_fallback(row.get(column), ''))}</td>" for column in columns) + "</tr>"
        for row in rows
    )
    return f"<div class=\"table-wrap\"><table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>"


def _positive_evidence_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p class=\"muted\">暂无正向证据对比数据。</p>"
    columns = ["symbol", "name", "label", "total_score", "positive_evidence", "detail_link", "report_link"]
    header = "".join(f"<th>{escape(column)}</th>" for column in columns)
    body_parts = []
    for row in rows:
        body_parts.append(
            "<tr>"
            f"<td>{escape(str(row.get('symbol', '')))}</td>"
            f"<td>{escape(str(row.get('name', '')))}</td>"
            f"<td><span class=\"tag-badge\">{escape(str(row.get('label', '')))}</span></td>"
            f"<td>{escape(_format_metric(row.get('total_score', '')))}</td>"
            f"<td>{escape(_fallback(row.get('positive_evidence'), '暂无主要正向证据。'))}</td>"
            f"<td><a href=\"{escape(str(row.get('detail_link', '#')))}\">详情</a></td>"
            f"<td><a href=\"{escape(str(row.get('report_link', '#')))}\">报告</a></td>"
            "</tr>"
        )
    return f"<div class=\"table-wrap\"><table><thead><tr>{header}</tr></thead><tbody>{''.join(body_parts)}</tbody></table></div>"


def _research_explanation_list(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p class=\"muted\">暂无研究解释。</p>"
    return "<ul class=\"compare-list\">" + "".join(
        f"<li><strong>{escape(str(row.get('symbol', '')))} {escape(str(row.get('name', '')))}</strong>"
        f"<p>{escape(_fallback(row.get('research_explanation'), '暂无真实因子贡献表，请先生成 factor_explanations 输出。'))}</p></li>"
        for row in rows
    ) + "</ul>"


def _factor_cards(rows: list[dict[str, Any]], fallback: str) -> str:
    if not rows:
        return f"<p class=\"muted\">{escape(fallback)}</p>"
    return "<ul class=\"factor-list\">" + "".join(
        f"<li><strong>{escape(str(row.get('display_name') or row.get('factor_group') or ''))}</strong>"
        f"<span>contribution {escape(_format_metric(row.get('contribution', '')))} / normalized {escape(_format_metric(row.get('normalized_score', '')))}</span>"
        f"<p>{escape(str(row.get('explanation') or ''))}</p></li>"
        for row in rows
    ) + "</ul>"


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


def _global_nav() -> str:
    links = [
        ("/", "Home"),
        ("/compare", "Compare"),
        ("/lists", "Lists"),
        ("/labels", "Labels"),
        ("/search", "Search"),
        ("/reports", "Reports"),
        ("/health/outputs", "Output Health"),
        ("/guide", "Guide"),
        ("/reports/daily", "Daily Report"),
    ]
    return "<nav class=\"global-nav\">" + "".join(
        f"<a href=\"{escape(href)}\">{escape(label)}</a>" for href, label in links
    ) + "</nav>"


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
    {_global_nav()}
    {body}
  </main>
</body>
</html>"""


def _css() -> str:
    return """
:root { color-scheme: light; font-family: Arial, "Microsoft YaHei", sans-serif; color: #17202a; background: #f6f7f9; }
body { margin: 0; }
.shell { max-width: 1180px; margin: 0 auto; padding: 28px 20px 48px; }
.global-nav { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 18px; border-bottom: 1px solid #d9dee7; padding-bottom: 12px; }
.global-nav a { border: 1px solid #d5deea; border-radius: 999px; padding: 6px 10px; background: #ffffff; color: #24466f; font-size: 13px; }
.topbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; border-bottom: 1px solid #d9dee7; padding-bottom: 18px; }
h1 { margin: 6px 0 8px; font-size: 30px; font-weight: 700; letter-spacing: 0; }
h2 { margin: 0 0 14px; font-size: 19px; letter-spacing: 0; }
p { line-height: 1.65; }
section { margin-top: 24px; background: #ffffff; border: 1px solid #dde3ec; border-radius: 8px; padding: 18px; }
.columns { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 18px; }
.columns.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.columns > div { min-width: 0; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
.list-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
.list-card { border: 1px solid #e0e5ed; border-radius: 8px; padding: 14px; background: #fbfcfe; }
.list-card h3 { margin: 0 0 8px; font-size: 17px; }
.filter-form { display: grid; grid-template-columns: repeat(auto-fit, minmax(145px, 1fr)); gap: 12px; align-items: end; }
.filter-form label { display: grid; gap: 5px; color: #455468; font-size: 13px; }
.filter-form input, .filter-form select { min-height: 34px; border: 1px solid #cfd6e1; border-radius: 6px; padding: 5px 8px; font: inherit; background: #fff; }
.filter-form button { min-height: 36px; border: 1px solid #1f5f99; border-radius: 6px; background: #1f5f99; color: #fff; font: inherit; cursor: pointer; }
.link-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.link-row a { border: 1px solid #d5deea; border-radius: 999px; padding: 5px 9px; background: #fbfcfe; font-size: 13px; }
.primary-link { display: inline-block; border: 1px solid #1f5f99; border-radius: 6px; padding: 8px 12px; background: #1f5f99; color: #fff; }
.primary-link:hover { color: #fff; }
.notice-text { color: #9a5b00; }
.status { display: inline-block; border-radius: 999px; padding: 3px 8px; font-size: 12px; border: 1px solid #cfd6e1; }
.status.ok { color: #17663a; background: #e9f7ef; border-color: #b7e1c8; }
.status.missing, .status.error { color: #9a3412; background: #fff1e8; border-color: #f3c3a6; }
.metric { border: 1px solid #e0e5ed; border-radius: 8px; padding: 12px; background: #fbfcfe; min-height: 62px; }
.metric span { display: block; color: #667085; font-size: 12px; margin-bottom: 8px; overflow-wrap: anywhere; }
.metric strong { display: block; font-size: 16px; overflow-wrap: anywhere; }
.command-block { margin-bottom: 16px; }
pre { margin: 0; overflow-x: auto; background: #111827; color: #f9fafb; border-radius: 8px; padding: 12px; }
code { font-family: Consolas, "Courier New", monospace; font-size: 13px; }
.badge, .tag-badge { display: inline-block; border: 1px solid #9db7d8; color: #24466f; background: #eef5ff; border-radius: 999px; padding: 5px 9px; font-size: 13px; white-space: nowrap; }
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; min-width: 760px; }
th, td { border-bottom: 1px solid #e4e8ef; padding: 10px 8px; text-align: left; vertical-align: top; font-size: 14px; }
th { color: #455468; background: #f3f5f8; }
ul { margin: 0; padding-left: 20px; line-height: 1.7; }
.factor-list { list-style: none; padding-left: 0; display: grid; gap: 10px; }
.compare-list { list-style: none; padding-left: 0; display: grid; gap: 10px; }
.compare-list li { border: 1px solid #e0e5ed; border-radius: 8px; padding: 10px; background: #fbfcfe; }
.factor-list li { border: 1px solid #e0e5ed; border-radius: 8px; padding: 10px; background: #fbfcfe; }
.factor-list span { display: block; color: #667085; font-size: 12px; margin-top: 4px; }
.factor-list p { margin: 6px 0 0; }
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
  .topbar, .columns, .columns.three { display: block; }
  .badge, .tag-badge { margin-top: 10px; white-space: normal; }
  h1 { font-size: 24px; }
}
"""
