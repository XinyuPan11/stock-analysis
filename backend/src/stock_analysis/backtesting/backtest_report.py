from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

import pandas as pd


DISCLAIMER = "该回测仅用于个人研究和模型验证，不构成投资建议。"


def generate_backtest_report(
    summary: dict[str, Any],
    equity_curve: pd.DataFrame,
    rebalance_log: pd.DataFrame,
    *,
    output_dir: str | Path | None = None,
    as_of_date: str | None = None,
) -> dict[str, str]:
    """Generate Chinese Markdown/HTML report for a walk-forward backtest."""

    report_date = pd.Timestamp(as_of_date or summary.get("end_date") or pd.Timestamp.today()).strftime("%Y-%m-%d")
    markdown = _markdown(summary, equity_curve, rebalance_log)
    html = markdown_to_html(markdown)
    if output_dir is None:
        return {"markdown_text": markdown, "html_text": html}

    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    md_path = path / f"backtest_report_{report_date}.md"
    html_path = path / f"backtest_report_{report_date}.html"
    md_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    return {"markdown": str(md_path.resolve()), "html": str(html_path.resolve())}


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    html_lines = ["<!doctype html>", "<html lang=\"zh-CN\">", "<head><meta charset=\"utf-8\"><title>回测报告</title></head>", "<body>"]
    in_table = False
    for line in lines:
        if line.startswith("# "):
            html_lines.append(f"<h1>{escape(line[2:])}</h1>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{escape(line[3:])}</h2>")
        elif line.startswith("|"):
            if not in_table:
                html_lines.append("<table>")
                in_table = True
            if set(line.replace("|", "").strip()) <= {"-", " "}:
                continue
            cells = [escape(cell.strip()) for cell in line.strip("|").split("|")]
            tag = "th" if all(item in line for item in ["指标", "数值"]) else "td"
            html_lines.append("<tr>" + "".join(f"<{tag}>{cell}</{tag}>" for cell in cells) + "</tr>")
        else:
            if in_table:
                html_lines.append("</table>")
                in_table = False
            if not line:
                html_lines.append("<br>")
            elif line.startswith("- "):
                html_lines.append(f"<p>{escape(line)}</p>")
            else:
                html_lines.append(f"<p>{escape(line)}</p>")
    if in_table:
        html_lines.append("</table>")
    html_lines.extend(["</body>", "</html>"])
    return "\n".join(html_lines)


def _markdown(summary: dict[str, Any], equity_curve: pd.DataFrame, rebalance_log: pd.DataFrame) -> str:
    metrics = summary.get("metrics", {}) or {}
    params = summary.get("parameters", {}) or {}
    warnings = summary.get("warnings", []) or []
    skipped = summary.get("skipped_symbols", []) or []
    lines = [
        f"# A股 Top N 候选策略 Walk-Forward 回测报告 - {summary.get('end_date', '')}",
        "",
        DISCLAIMER,
        "",
        "## 一、回测设置",
        "",
        f"- 数据区间：{summary.get('start_date', '')} 至 {summary.get('end_date', '')}",
        f"- 数据来源：{summary.get('provider', '')}",
        f"- 基准指数：{summary.get('benchmark', '')}",
        f"- Top N：{params.get('top_n', '')}",
        f"- 调仓频率：{params.get('rebalance_frequency', '')}",
        f"- lookback_days：{params.get('lookback_days', '')}",
        f"- transaction_cost_bps：{params.get('transaction_cost_bps', '')}",
        f"- limit：{params.get('limit', '')}",
        "",
        "## 二、策略逻辑",
        "",
        "每个调仓日仅使用该日期之前已经存在的日线数据，经过 A 股过滤、因子计算、评分排名后，选择 Top N 候选股票等权持有至下一个调仓日。收益从调仓日之后的交易日开始计入，避免使用未来价格参与选股。",
        "",
        "## 三、核心表现指标",
        "",
        *_metric_table(metrics),
        "",
        "## 四、相对基准表现",
        "",
        f"- 策略总收益：{_fmt_pct(metrics.get('net_total_return_after_cost'))}",
        f"- 基准总收益：{_fmt_pct(metrics.get('benchmark_total_return'))}",
        f"- 超额收益：{_fmt_pct(metrics.get('excess_return'))}",
        "",
        "## 五、最大回撤与风险",
        "",
        f"- 策略最大回撤：{_fmt_pct(metrics.get('max_drawdown'))}",
        f"- 基准最大回撤：{_fmt_pct(metrics.get('benchmark_max_drawdown'))}",
        f"- 年化波动率：{_fmt_pct(metrics.get('volatility'))}",
        f"- Sharpe Ratio：{_fmt_number(metrics.get('sharpe_ratio'))}",
        "",
        "## 六、调仓记录摘要",
        "",
        *_rebalance_summary(rebalance_log),
        "",
        "## 七、交易成本影响",
        "",
        f"- 累计交易成本影响：{_fmt_pct(metrics.get('transaction_cost'))}",
        f"- 成本后总收益：{_fmt_pct(metrics.get('net_total_return_after_cost'))}",
        "",
        "## 八、结果解释",
        "",
        _interpretation(metrics),
        "",
        "## 九、局限性与下一步改进",
        "",
        "- 第一版使用免费/开源数据源和小样本 limit，不能代表全市场最终结论。",
        "- 当前未纳入财务、估值、公告、新闻、行业事件和组合风险约束。",
        "- 回测结果需要结合更长历史区间、更多样本、交易成本敏感性和后续样本外验证。",
    ]
    if warnings:
        lines.extend(["", "### 数据与指标 Warning", "", *[f"- {warning}" for warning in warnings]])
    if skipped:
        lines.extend(["", "### 跳过股票样例", "", *[f"- {item}" for item in skipped[:20]]])
    lines.extend(["", DISCLAIMER, ""])
    return "\n".join(lines)


def _metric_table(metrics: dict[str, Any]) -> list[str]:
    rows = [
        ("total_return", _fmt_pct(metrics.get("total_return"))),
        ("annualized_return", _fmt_pct(metrics.get("annualized_return"))),
        ("benchmark_total_return", _fmt_pct(metrics.get("benchmark_total_return"))),
        ("excess_return", _fmt_pct(metrics.get("excess_return"))),
        ("max_drawdown", _fmt_pct(metrics.get("max_drawdown"))),
        ("benchmark_max_drawdown", _fmt_pct(metrics.get("benchmark_max_drawdown"))),
        ("sharpe_ratio", _fmt_number(metrics.get("sharpe_ratio"))),
        ("volatility", _fmt_pct(metrics.get("volatility"))),
        ("win_rate", _fmt_pct(metrics.get("win_rate"))),
        ("turnover", _fmt_pct(metrics.get("turnover"))),
        ("number_of_rebalances", str(metrics.get("number_of_rebalances", ""))),
        ("average_holdings", _fmt_number(metrics.get("average_holdings"))),
        ("transaction_cost", _fmt_pct(metrics.get("transaction_cost"))),
        ("net_total_return_after_cost", _fmt_pct(metrics.get("net_total_return_after_cost"))),
    ]
    return ["| 指标 | 数值 |", "| --- | --- |", *[f"| {name} | {value} |" for name, value in rows]]


def _rebalance_summary(rebalance_log: pd.DataFrame) -> list[str]:
    if rebalance_log is None or rebalance_log.empty:
        return ["暂无有效调仓记录。"]
    grouped = rebalance_log.groupby("rebalance_date")
    lines = []
    for date, group in grouped:
        symbols = ", ".join(group["symbol"].astype(str).head(10).tolist())
        lines.append(f"- {date}：持仓 {len(group)} 只，样例 {symbols}")
    return lines


def _interpretation(metrics: dict[str, Any]) -> str:
    excess = metrics.get("excess_return")
    drawdown = metrics.get("max_drawdown")
    if excess is None:
        return "样本不足或无有效净值曲线，暂时不能判断策略相对基准的历史优势。"
    if float(excess) > 0:
        return f"本次样本内策略成本后相对基准取得正超额收益（{_fmt_pct(excess)}），但仍需关注最大回撤（{_fmt_pct(drawdown)}）和样本外稳定性。"
    return f"本次样本内策略成本后未跑赢基准（超额收益 {_fmt_pct(excess)}），需要复查因子权重、过滤条件和调仓频率。"


def _fmt_pct(value: Any) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):.2%}"


def _fmt_number(value: Any) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):.4f}"

