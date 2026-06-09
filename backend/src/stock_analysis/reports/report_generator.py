from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
import json
from pathlib import Path
from typing import Any

import pandas as pd


DAILY_REPORT_PREFIX = "daily_report"
DISCLAIMER = "\u672c\u62a5\u544a\u4ec5\u7528\u4e8e\u4e2a\u4eba\u7814\u7a76\u8f85\u52a9\uff0c\u4e0d\u6784\u6210\u6295\u8d44\u5efa\u8bae\u3002\u5e02\u573a\u5b58\u5728\u4e0d\u786e\u5b9a\u6027\uff0c\u6240\u6709\u7ed3\u8bba\u9700\u8981\u6301\u7eed\u8ddf\u8e2a\u548c\u590d\u6838\u3002"
PROHIBITED_TERMS = ["\u4e70\u5165", "\u5356\u51fa", "\u5f3a\u70c8\u4e70\u5165", "\u5efa\u8bae\u4e70\u5165"]

CANDIDATE_REPORT_COLUMNS = [
    "rank",
    "symbol",
    "name",
    "as_of_date",
    "total_score",
    "label",
    "confidence",
    "momentum_score",
    "trend_score",
    "relative_strength_score",
    "risk_score",
    "liquidity_score",
    "positive_evidence",
    "negative_evidence",
    "risk_flags",
    "warnings",
    "source",
]

EXPLANATION_COLUMNS = [
    "symbol",
    "factor_group",
    "raw_value",
    "normalized_score",
    "weight",
    "contribution",
    "explanation",
]


@dataclass(frozen=True)
class ReportArtifact:
    markdown: str
    html: str
    markdown_path: str = ""
    html_path: str = ""
    warnings: tuple[str, ...] = field(default_factory=tuple)


def generate_daily_report(
    candidates: pd.DataFrame,
    *,
    summary: dict[str, Any] | None = None,
    output_dir: str | Path | None = None,
    as_of_date: str | None = None,
    updated_at: str | None = None,
    input_warnings: list[str] | None = None,
) -> ReportArtifact:
    prepared, warnings = _prepare_candidates(candidates)
    warnings.extend(input_warnings or [])
    summary = summary or {}
    report_date = _resolve_report_date(prepared, as_of_date or _summary_value(summary, "as_of_date"))
    update_time = _resolve_update_time(updated_at or _summary_value(summary, "updated_at"))
    markdown = _daily_markdown(prepared, summary=summary, as_of_date=report_date, updated_at=update_time, warnings=warnings)
    _assert_no_prohibited_terms(markdown)
    html = markdown_to_html(markdown)
    paths = _write_artifact(markdown, html, output_dir, f"{DAILY_REPORT_PREFIX}_{report_date}") if output_dir else {}
    return ReportArtifact(markdown=markdown, html=html, markdown_path=paths.get("markdown", ""), html_path=paths.get("html", ""), warnings=tuple(warnings))


def generate_stock_report(
    candidate: pd.Series | dict[str, Any],
    *,
    explanations: pd.DataFrame | None = None,
    output_dir: str | Path | None = None,
    updated_at: str | None = None,
) -> ReportArtifact:
    row = _prepare_candidate_row(candidate)
    update_time = _resolve_update_time(updated_at)
    explanation_frame = _prepare_explanations(explanations, symbol=str(row["symbol"]))
    markdown = _stock_markdown(row, explanation_frame, updated_at=update_time)
    _assert_no_prohibited_terms(markdown)
    html = markdown_to_html(markdown)
    report_date = str(row.get("as_of_date") or pd.Timestamp.today().strftime("%Y-%m-%d"))
    file_stem = f"{_safe_filename(str(row['symbol']))}_{report_date}"
    stock_dir = Path(output_dir) / "stocks" if output_dir else None
    paths = _write_artifact(markdown, html, stock_dir, file_stem) if stock_dir else {}
    return ReportArtifact(markdown=markdown, html=html, markdown_path=paths.get("markdown", ""), html_path=paths.get("html", ""))


def generate_reports_from_candidates(
    candidates: pd.DataFrame,
    *,
    summary: dict[str, Any] | None = None,
    factors: pd.DataFrame | None = None,
    explanations: pd.DataFrame | None = None,
    output_dir: str | Path,
    as_of_date: str | None = None,
    updated_at: str | None = None,
    input_warnings: list[str] | None = None,
) -> dict[str, Any]:
    report_warnings = list(input_warnings or [])
    if factors is None:
        report_warnings.append("missing_factors_input: using candidates only.")
    if explanations is None:
        report_warnings.append("missing_factor_explanations_input: single-stock reports use fallback explanation rows.")
    daily = generate_daily_report(
        candidates,
        summary=summary,
        output_dir=output_dir,
        as_of_date=as_of_date,
        updated_at=updated_at,
        input_warnings=report_warnings,
    )
    prepared, _ = _prepare_candidates(candidates)
    stock_reports = [
        generate_stock_report(row, explanations=explanations, output_dir=output_dir, updated_at=updated_at)
        for _, row in prepared.iterrows()
    ]
    return {
        "daily_markdown": daily.markdown_path,
        "daily_html": daily.html_path,
        "stock_reports": [
            {"markdown": artifact.markdown_path, "html": artifact.html_path}
            for artifact in stock_reports
        ],
        "warnings": list(daily.warnings),
    }


def load_candidates_json(path: str | Path) -> pd.DataFrame:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if isinstance(payload, dict) and "candidates" in payload:
        payload = payload["candidates"]
    if not isinstance(payload, list):
        raise ValueError("Candidates JSON must contain a list of candidate rows.")
    return pd.DataFrame(payload)


def load_summary_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if isinstance(payload, dict) and "summary" in payload and isinstance(payload["summary"], dict):
        return payload["summary"]
    if isinstance(payload, dict):
        return payload
    raise ValueError("Summary JSON must contain an object.")


def load_frame_json(path: str | Path) -> pd.DataFrame:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if isinstance(payload, dict):
        for key in ["factor_explanations", "factors", "candidates"]:
            if key in payload:
                payload = payload[key]
                break
    if not isinstance(payload, list):
        raise ValueError("Frame JSON must contain a list of rows.")
    return pd.DataFrame(payload)


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    html_lines = ["<!doctype html>", "<html lang=\"zh-CN\">", "<head><meta charset=\"utf-8\"><title>研究报告</title></head>", "<body>"]
    in_table = False
    for line in lines:
        if line.startswith("|") and line.endswith("|"):
            if set(line.replace("|", "").strip()) <= {"-", ":"}:
                continue
            cells = [escape(cell.strip()) for cell in line.strip("|").split("|")]
            tag = "th" if not in_table else "td"
            if not in_table:
                html_lines.append("<table border=\"1\" cellspacing=\"0\" cellpadding=\"4\">")
                in_table = True
            html_lines.append("<tr>" + "".join(f"<{tag}>{cell}</{tag}>" for cell in cells) + "</tr>")
            continue
        if in_table:
            html_lines.append("</table>")
            in_table = False
        if line.startswith("# "):
            html_lines.append(f"<h1>{escape(line[2:])}</h1>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{escape(line[3:])}</h2>")
        elif line.startswith("### "):
            html_lines.append(f"<h3>{escape(line[4:])}</h3>")
        elif line.startswith("- "):
            html_lines.append(f"<p>{escape(line)}</p>")
        elif not line.strip():
            html_lines.append("<br>")
        else:
            html_lines.append(f"<p>{escape(line)}</p>")
    if in_table:
        html_lines.append("</table>")
    html_lines.append("</body></html>")
    return "\n".join(html_lines)


def _daily_markdown(
    candidates: pd.DataFrame,
    *,
    summary: dict[str, Any],
    as_of_date: str,
    updated_at: str,
    warnings: list[str],
) -> str:
    source = _source_summary(candidates) or str(summary.get("provider", ""))
    lines = [
        f"# A股每日候选研究报告 - {as_of_date}",
        "",
        f"- 数据日期：{as_of_date}",
        f"- 更新时间：{updated_at}",
        f"- 数据来源：{source}",
        f"- provider：{summary.get('provider', '')}",
        f"- benchmark：{summary.get('benchmark', '')}",
        f"- universe_count：{summary.get('universe_count', '')}",
        f"- filtered_count：{summary.get('filtered_count', '')}",
        f"- attempted_count：{summary.get('attempted_count', '')}",
        f"- successful_factor_count：{summary.get('successful_factor_count', '')}",
        f"- scored_count：{summary.get('scored_count', len(candidates))}",
        f"- fetch_error_count：{summary.get('fetch_error_count', '')}",
        "",
        "## 推荐标签说明",
        "",
        "- 高置信候选：多个信号共振，当前研究优先级最高；不是交易结论。",
        "- 候选关注：进入正式候选池，值得进一步研究。",
        "- 重点观察：有明显亮点，但仍需确认。",
        "- 观察：普通跟踪，不作为当前核心候选。",
        "- 风险过高：风险标记较重，不适合进入当前候选池。",
        "- 数据不足：历史数据或关键字段不足，暂不可靠。",
        "",
        "## 高置信候选",
        "",
    ]
    high_confidence = candidates[candidates["label"] == "\u9ad8\u7f6e\u4fe1\u5019\u9009"]
    if high_confidence.empty:
        lines.append("本次样本中没有高置信候选。")
    else:
        for _, row in high_confidence.iterrows():
            lines.append(_candidate_brief(row))
    lines.extend(["", "## Top N 候选股总表", ""])
    if candidates.empty:
        lines.append("无候选结果。请检查股票池、过滤条件、数据源可用性和样本范围。")
    else:
        lines.extend(_markdown_table(candidates.loc[:, _existing_columns(candidates, CANDIDATE_REPORT_COLUMNS)]))
    lines.extend(["", "## 候选股简要研究结论", ""])
    for _, row in candidates.iterrows():
        lines.extend(_candidate_research_block(row))
    lines.extend(["", "## 主要风险提示", ""])
    lines.append("候选结果来自日线量价和相对强度因子，尚未纳入财务、估值、公告、新闻和行业事件。")
    lines.append("若出现风险标记、数据缺口、成交显著收缩或趋势破位，应降低研究优先级。")
    lines.extend(["", "## 数据质量说明", ""])
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("候选表字段完整性检查未发现结构性缺失。")
    lines.extend(["", "## 免责声明", "", DISCLAIMER])
    return "\n".join(lines)


def _stock_markdown(row: pd.Series, explanations: pd.DataFrame, *, updated_at: str) -> str:
    title = f"{row['symbol']} {row.get('name', '')}".strip()
    lines = [
        f"# 单股分析报告 - {title}",
        "",
        "## 一、推荐结论",
        "",
        f"- 推荐标签：{row.get('label', '')}",
        f"- 综合分：{row.get('total_score', '')}",
        f"- confidence：{row.get('confidence', '')}",
        "该标签表示当前研究优先级，不代表交易结论。",
        "",
        "## 二、核心观点",
        "",
        _fallback_text(row.get("positive_evidence"), "暂未形成明确正向证据。"),
        "",
        "## 三、关键证据",
        "",
        f"- 动量分：{row.get('momentum_score', '')}",
        f"- 趋势分：{row.get('trend_score', '')}",
        f"- 相对强度分：{row.get('relative_strength_score', '')}",
        f"- 风险分：{row.get('risk_score', '')}",
        f"- 流动性分：{row.get('liquidity_score', '')}",
        "",
        "## 四、因子贡献表",
        "",
    ]
    lines.extend(_markdown_table(explanations.loc[:, _existing_columns(explanations, EXPLANATION_COLUMNS)]))
    lines.extend(
        [
            "",
            "## 五、风险反证",
            "",
            _fallback_text(row.get("negative_evidence"), "暂未出现显著反向证据，但仍需持续复核。"),
            _fallback_text(row.get("risk_flags"), "当前结构化风险标记为空。"),
            _fallback_text(row.get("warnings"), "当前数据 warning 为空。"),
            "",
            "## 六、失效条件",
            "",
            "- 综合分明显回落，且趋势分或相对强度分同步走弱。",
            "- 出现新的严重风险标记，或最大回撤、波动率显著恶化。",
            "- 成交额和成交量持续收缩，导致流动性分显著下降。",
            "- 数据源出现缺口，导致关键因子无法可靠计算。",
            "",
            "## 七、后续跟踪指标",
            "",
            "- total_score、confidence、label 的变化。",
            "- momentum_20d / momentum_60d / relative_strength_score 的持续性。",
            "- risk_score、max_drawdown_60d、volatility_60d。",
            "- avg_amount_20d 与 avg_volume_20d。",
            "",
            "## 八、数据来源与更新时间",
            "",
            f"- 数据日期：{row.get('as_of_date', '')}",
            f"- 更新时间：{updated_at}",
            f"- 数据来源：{row.get('source', '')}",
            "",
            "## 免责声明",
            "",
            DISCLAIMER,
        ]
    )
    return "\n".join(lines)


def _candidate_research_block(row: pd.Series) -> list[str]:
    name = f"{row.get('symbol', '')} {row.get('name', '')}".strip()
    return [
        f"### {row.get('rank', '')}. {name}",
        "",
        f"- 推荐结论：{row.get('label', '')}，综合分 {row.get('total_score', '')}，confidence {row.get('confidence', '')}。",
        f"- 核心观点：{_fallback_text(row.get('positive_evidence'), '正向证据不足。')}",
        f"- 风险反证：{_fallback_text(row.get('negative_evidence'), '暂无显著反向证据。')}",
        f"- 风险标记：{_fallback_text(row.get('risk_flags'), '无')}",
        f"- 数据提示：{_fallback_text(row.get('warnings'), '无')}",
        "",
    ]


def _candidate_brief(row: pd.Series) -> str:
    return f"- {row.get('symbol', '')} {row.get('name', '')}：综合分 {row.get('total_score', '')}，当前研究优先级最高；{_fallback_text(row.get('positive_evidence'), '需继续补充证据。')}"


def _prepare_candidates(candidates: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    if candidates is None:
        candidates = pd.DataFrame()
    frame = candidates.copy()
    missing = [column for column in CANDIDATE_REPORT_COLUMNS if column not in frame.columns]
    if missing:
        warnings.append("missing_candidate_columns: " + ",".join(missing))
        for column in missing:
            frame[column] = ""
    if frame.empty:
        return pd.DataFrame(columns=CANDIDATE_REPORT_COLUMNS), warnings
    return frame.loc[:, CANDIDATE_REPORT_COLUMNS].copy(), warnings


def _prepare_candidate_row(candidate: pd.Series | dict[str, Any]) -> pd.Series:
    frame, _ = _prepare_candidates(pd.DataFrame([dict(candidate)]))
    return frame.iloc[0]


def _prepare_explanations(explanations: pd.DataFrame | None, *, symbol: str) -> pd.DataFrame:
    if explanations is None or explanations.empty:
        return _fallback_explanations(symbol)
    frame = explanations.copy()
    missing = [column for column in EXPLANATION_COLUMNS if column not in frame.columns]
    for column in missing:
        frame[column] = ""
    if "symbol" in frame.columns:
        frame = frame[frame["symbol"].astype(str) == symbol].copy()
    if frame.empty:
        return _fallback_explanations(symbol)
    return frame.loc[:, EXPLANATION_COLUMNS].copy()


def _fallback_explanations(symbol: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": symbol,
                "factor_group": "score_summary",
                "raw_value": "",
                "normalized_score": "",
                "weight": "",
                "contribution": "",
                "explanation": "\u672a\u63d0\u4f9b\u8be6\u7ec6\u56e0\u5b50\u8d21\u732e\u8868\uff0c\u672c\u62a5\u544a\u4ec5\u5c55\u793a\u5206\u9879\u5f97\u5206\u548c\u8bc1\u636e\u6458\u8981\u3002",
            }
        ],
        columns=EXPLANATION_COLUMNS,
    )


def _markdown_table(frame: pd.DataFrame) -> list[str]:
    if frame.empty:
        return ["无数据。"]
    header = "| " + " | ".join(frame.columns.astype(str)) + " |"
    separator = "| " + " | ".join(["---"] * len(frame.columns)) + " |"
    rows = [header, separator]
    for _, row in frame.iterrows():
        rows.append("| " + " | ".join(_cell(row[column]) for column in frame.columns) + " |")
    return rows


def _cell(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).replace("\n", " ").replace("|", "/")
    return text


def _existing_columns(frame: pd.DataFrame, columns: list[str]) -> list[str]:
    return [column for column in columns if column in frame.columns]


def _fallback_text(value: Any, fallback: str) -> str:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return fallback
    return str(value)


def _source_summary(candidates: pd.DataFrame) -> str:
    if candidates.empty or "source" not in candidates.columns:
        return ""
    return ";".join(sorted(set(candidates["source"].dropna().astype(str))))


def _summary_value(summary: dict[str, Any], key: str) -> str:
    value = summary.get(key)
    if value is None or value == "":
        return ""
    return str(value)


def _resolve_report_date(candidates: pd.DataFrame, as_of_date: str | None) -> str:
    if as_of_date:
        return pd.Timestamp(as_of_date).strftime("%Y-%m-%d")
    if not candidates.empty and "as_of_date" in candidates.columns and str(candidates["as_of_date"].iloc[0]).strip():
        return pd.Timestamp(candidates["as_of_date"].iloc[0]).strftime("%Y-%m-%d")
    return pd.Timestamp.today().strftime("%Y-%m-%d")


def _resolve_update_time(updated_at: str | None) -> str:
    if updated_at:
        return str(updated_at)
    return pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")


def _write_artifact(markdown: str, html: str, output_dir: str | Path, file_stem: str) -> dict[str, str]:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    markdown_path = path / f"{file_stem}.md"
    html_path = path / f"{file_stem}.html"
    markdown_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    return {"markdown": str(markdown_path.resolve()), "html": str(html_path.resolve())}


def _safe_filename(value: str) -> str:
    return value.replace("/", "_").replace("\\", "_").replace(":", "_")


def _assert_no_prohibited_terms(text: str) -> None:
    found = [term for term in PROHIBITED_TERMS if term in text]
    if found:
        raise ValueError("Report contains prohibited deterministic wording: " + ",".join(found))
