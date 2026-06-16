from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd


PRIMARY_LONG_TERM_STABLE = "长期稳定型"
PRIMARY_TREND_LEADER = "趋势龙头型"
PRIMARY_INDUSTRY_HOT = "行业热股型"
PRIMARY_ACCUMULATION = "潜力蓄势型"
PRIMARY_BREAKOUT = "突破爆发型"
PRIMARY_REBOUND = "超跌反弹型"
PRIMARY_HIGH_RISK_ACTIVE = "高风险活跃型"
PRIMARY_INSUFFICIENT_DATA = "数据不足"

TAG_INDUSTRY_PENDING = "行业字段待补充"

LABEL_OUTPUT_COLUMNS = [
    "symbol",
    "name",
    "as_of_date",
    "rank",
    "total_score",
    "primary_type",
    "secondary_tags",
    "research_label",
    "research_action",
    "confidence_level",
    "risk_level",
    "confirmation_signals",
    "invalidation_signals",
    "label_reason",
    "data_quality",
    "source_label",
    "momentum_score",
    "trend_score",
    "relative_strength_score",
    "risk_score",
    "liquidity_score",
    "positive_evidence",
    "negative_evidence",
    "risk_flags",
    "warnings",
    "report_path_md",
    "report_path_html",
]

FORBIDDEN_RESEARCH_TERMS = ["买入", "卖出", "必涨", "强烈建议购入"]


def label_candidates(
    candidates: pd.DataFrame | Iterable[dict[str, object]],
    *,
    factors: pd.DataFrame | Iterable[dict[str, object]] | None = None,
    failed_symbols: pd.DataFrame | Iterable[dict[str, object]] | None = None,
    reports_dir: str | Path | None = None,
    as_of_date: str | None = None,
) -> pd.DataFrame:
    """Create research-style multi-label rows from existing candidate outputs only."""

    candidate_frame = _to_frame(candidates)
    if candidate_frame.empty:
        return pd.DataFrame(columns=LABEL_OUTPUT_COLUMNS)

    factor_frame = _to_frame(factors)
    failed_frame = _to_frame(failed_symbols)
    candidate_frame = candidate_frame.copy()
    factor_frame = factor_frame.copy()

    _coerce_candidate_numeric(candidate_frame)
    _coerce_factor_numeric(factor_frame)
    candidate_percentiles = _candidate_percentiles(candidate_frame)
    factor_percentiles = _factor_percentiles(factor_frame)
    factor_by_symbol = _index_by_symbol(factor_frame)
    factor_pct_by_symbol = _index_by_symbol(factor_percentiles)
    failed_by_symbol = _failed_by_symbol(failed_frame)

    rows: list[dict[str, object]] = []
    for idx, row in candidate_frame.reset_index(drop=True).iterrows():
        symbol = str(row.get("symbol", "")).strip()
        factors_row = factor_by_symbol.get(symbol, {})
        factor_pct = factor_pct_by_symbol.get(symbol, {})
        percentiles = candidate_percentiles.iloc[idx].to_dict()
        rows.append(
            _label_one(
                row.to_dict(),
                percentiles=percentiles,
                factors_row=factors_row,
                factor_percentiles=factor_pct,
                failed_error=failed_by_symbol.get(symbol, ""),
                reports_dir=Path(reports_dir) if reports_dir else None,
                fallback_date=as_of_date,
            )
        )

    frame = pd.DataFrame(rows)
    return frame.loc[:, LABEL_OUTPUT_COLUMNS]


def serialize_label_rows_for_csv(labels: pd.DataFrame) -> pd.DataFrame:
    """Return a CSV-friendly copy while keeping JSON output list-shaped."""

    frame = labels.copy()
    for column in ["secondary_tags", "confirmation_signals", "invalidation_signals"]:
        if column in frame.columns:
            frame[column] = frame[column].apply(lambda value: ";".join(value) if isinstance(value, list) else str(value or ""))
    return frame


def ensure_research_language(value: object) -> None:
    text = str(value)
    found = [term for term in FORBIDDEN_RESEARCH_TERMS if term in text]
    if found:
        raise ValueError(f"Research output contains forbidden deterministic terms: {found}")


def _label_one(
    row: dict[str, object],
    *,
    percentiles: dict[str, object],
    factors_row: dict[str, object],
    factor_percentiles: dict[str, object],
    failed_error: str,
    reports_dir: Path | None,
    fallback_date: str | None,
) -> dict[str, object]:
    symbol = str(row.get("symbol", "")).strip()
    source_label = str(row.get("label", "")).strip()
    risk_flags = str(row.get("risk_flags", "") or "").strip()
    warnings = str(row.get("warnings", "") or "").strip()
    as_of_date = str(row.get("as_of_date") or fallback_date or "")

    data_quality_notes = _data_quality_notes(row, factors_row=factors_row, failed_error=failed_error)
    insufficient = source_label == PRIMARY_INSUFFICIENT_DATA or any(note.startswith("insufficient") for note in data_quality_notes)
    severe_risk = source_label == "风险过高" or _contains_severe_risk(risk_flags) or _pct(percentiles, "risk_score") <= 0.12
    high_risk = severe_risk or bool(risk_flags) or _pct(percentiles, "risk_score") <= 0.25
    stable = _is_stable_candidate(percentiles, factor_percentiles, high_risk=high_risk)
    trend_leader = _is_trend_leader(percentiles, high_risk=severe_risk)
    breakout = _is_breakout_candidate(percentiles, factor_percentiles, high_risk=severe_risk)
    accumulation = _is_accumulation_candidate(percentiles, high_risk=high_risk)
    rebound = _is_rebound_candidate(percentiles, factor_percentiles, high_risk=severe_risk)

    secondary_tags = _ordered_tags(
        [
            (PRIMARY_TREND_LEADER, trend_leader),
            (PRIMARY_LONG_TERM_STABLE, stable),
            (PRIMARY_BREAKOUT, breakout),
            (PRIMARY_ACCUMULATION, accumulation),
            (PRIMARY_REBOUND, rebound),
            (PRIMARY_HIGH_RISK_ACTIVE, high_risk and not insufficient),
            (TAG_INDUSTRY_PENDING, "industry" not in row),
        ]
    )

    if insufficient:
        primary_type = PRIMARY_INSUFFICIENT_DATA
    elif high_risk and _has_active_signal(percentiles):
        primary_type = PRIMARY_HIGH_RISK_ACTIVE
    elif stable:
        primary_type = PRIMARY_LONG_TERM_STABLE
    elif trend_leader:
        primary_type = PRIMARY_TREND_LEADER
    elif breakout:
        primary_type = PRIMARY_BREAKOUT
    elif rebound:
        primary_type = PRIMARY_REBOUND
    elif accumulation:
        primary_type = PRIMARY_ACCUMULATION
    else:
        primary_type = PRIMARY_ACCUMULATION
        if PRIMARY_ACCUMULATION not in secondary_tags:
            secondary_tags.insert(0, PRIMARY_ACCUMULATION)

    confidence_level = _confidence_level(row, data_quality_notes=data_quality_notes, high_risk=high_risk, insufficient=insufficient)
    risk_level = _risk_level(percentiles, risk_flags=risk_flags, high_risk=high_risk, severe_risk=severe_risk, insufficient=insufficient)
    confirmation_signals = _confirmation_signals(primary_type, row, factor_percentiles)
    invalidation_signals = _invalidation_signals(primary_type, risk_level, risk_flags, warnings)
    label_reason = _label_reason(primary_type, row, percentiles, data_quality_notes, high_risk=high_risk)
    research_action = _research_action(primary_type, confidence_level, risk_level)
    research_label = f"{primary_type}｜{confidence_level}置信｜{risk_level}风险"
    report_md, report_html = _report_paths(symbol, as_of_date, reports_dir)

    output = {
        "symbol": symbol,
        "name": str(row.get("name", "") or ""),
        "as_of_date": as_of_date,
        "rank": _safe_int(row.get("rank")),
        "total_score": _safe_float(row.get("total_score")),
        "primary_type": primary_type,
        "secondary_tags": secondary_tags,
        "research_label": research_label,
        "research_action": research_action,
        "confidence_level": confidence_level,
        "risk_level": risk_level,
        "confirmation_signals": confirmation_signals,
        "invalidation_signals": invalidation_signals,
        "label_reason": label_reason,
        "data_quality": "ok" if not data_quality_notes else ";".join(data_quality_notes),
        "source_label": source_label,
        "momentum_score": _safe_float(row.get("momentum_score")),
        "trend_score": _safe_float(row.get("trend_score")),
        "relative_strength_score": _safe_float(row.get("relative_strength_score")),
        "risk_score": _safe_float(row.get("risk_score")),
        "liquidity_score": _safe_float(row.get("liquidity_score")),
        "positive_evidence": str(row.get("positive_evidence", "") or ""),
        "negative_evidence": str(row.get("negative_evidence", "") or ""),
        "risk_flags": risk_flags,
        "warnings": warnings,
        "report_path_md": report_md,
        "report_path_html": report_html,
    }
    ensure_research_language(output)
    return output


def _candidate_percentiles(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "total_score",
        "confidence",
        "momentum_score",
        "trend_score",
        "relative_strength_score",
        "risk_score",
        "liquidity_score",
    ]
    return pd.DataFrame({column: _percentile(frame.get(column)) for column in columns})


def _factor_percentiles(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "symbol" not in frame.columns:
        return pd.DataFrame(columns=["symbol"])
    result = pd.DataFrame({"symbol": frame["symbol"].fillna("").astype(str)})
    for column in ["momentum_20d", "momentum_60d", "momentum_120d", "rs_20d", "rs_60d", "rs_120d", "avg_amount_20d", "avg_amount_60d"]:
        if column in frame.columns:
            result[column] = _percentile(frame[column])
    for column in ["volatility_20d", "volatility_60d"]:
        if column in frame.columns:
            result[f"{column}_stability"] = _percentile(frame[column], higher_is_better=False)
    for column in ["max_drawdown", "max_drawdown_20d", "max_drawdown_60d"]:
        if column in frame.columns:
            result[f"{column}_control"] = _percentile(pd.to_numeric(frame[column], errors="coerce").abs(), higher_is_better=False)
    return result


def _is_stable_candidate(percentiles: dict[str, object], factor_percentiles: dict[str, object], *, high_risk: bool) -> bool:
    if high_risk:
        return False
    risk = _pct(percentiles, "risk_score")
    liquidity = _pct(percentiles, "liquidity_score")
    trend = _pct(percentiles, "trend_score")
    volatility_control = min(
        _pct(factor_percentiles, "volatility_20d_stability", default=0.65),
        _pct(factor_percentiles, "volatility_60d_stability", default=0.65),
    )
    drawdown_control = min(
        _pct(factor_percentiles, "max_drawdown_20d_control", default=0.65),
        _pct(factor_percentiles, "max_drawdown_60d_control", default=0.65),
    )
    return risk >= 0.65 and liquidity >= 0.55 and trend >= 0.45 and volatility_control >= 0.45 and drawdown_control >= 0.45


def _is_trend_leader(percentiles: dict[str, object], *, high_risk: bool) -> bool:
    if high_risk:
        return False
    return (
        _pct(percentiles, "trend_score") >= 0.55
        and _pct(percentiles, "momentum_score") >= 0.55
        and _pct(percentiles, "relative_strength_score") >= 0.55
    )


def _is_breakout_candidate(percentiles: dict[str, object], factor_percentiles: dict[str, object], *, high_risk: bool) -> bool:
    if high_risk:
        return False
    near_term = _pct(factor_percentiles, "momentum_20d", default=_pct(percentiles, "momentum_score"))
    return near_term >= 0.60 and _pct(percentiles, "trend_score") >= 0.45 and _pct(percentiles, "relative_strength_score") >= 0.45


def _is_accumulation_candidate(percentiles: dict[str, object], *, high_risk: bool) -> bool:
    if high_risk:
        return False
    return _pct(percentiles, "trend_score") >= 0.35 and _pct(percentiles, "risk_score") >= 0.45 and _pct(percentiles, "total_score") >= 0.25


def _is_rebound_candidate(percentiles: dict[str, object], factor_percentiles: dict[str, object], *, high_risk: bool) -> bool:
    if high_risk:
        return False
    short_momentum = _pct(factor_percentiles, "momentum_20d", default=_pct(percentiles, "momentum_score"))
    long_momentum = _pct(factor_percentiles, "momentum_120d", default=0.5)
    return short_momentum >= 0.65 and long_momentum <= 0.35 and _pct(percentiles, "risk_score") >= 0.30


def _has_active_signal(percentiles: dict[str, object]) -> bool:
    return max(_pct(percentiles, "momentum_score"), _pct(percentiles, "trend_score"), _pct(percentiles, "liquidity_score")) >= 0.50


def _confirmation_signals(primary_type: str, row: dict[str, object], factor_percentiles: dict[str, object]) -> list[str]:
    base = []
    if primary_type == PRIMARY_LONG_TERM_STABLE:
        base = ["趋势结构保持完整", "波动和回撤继续受控", "流动性保持稳定"]
    elif primary_type == PRIMARY_TREND_LEADER:
        base = ["趋势分和相对强度继续靠前", "动量优势未明显衰减", "风险标记没有新增"]
    elif primary_type == PRIMARY_BREAKOUT:
        base = ["短期动量继续改善", "价格结构维持在关键均线之上", "相对强度保持扩张"]
    elif primary_type == PRIMARY_REBOUND:
        base = ["短期修复信号延续", "回撤不再扩大", "成交活跃度没有快速收缩"]
    elif primary_type == PRIMARY_HIGH_RISK_ACTIVE:
        base = ["活跃信号仍在", "风险标记没有进一步恶化", "仅作为风险观察对象"]
    elif primary_type == PRIMARY_INSUFFICIENT_DATA:
        base = ["补齐历史行情和因子输出", "重新生成候选和因子解释文件"]
    else:
        base = ["趋势改善继续确认", "风险分保持可控", "流动性没有明显恶化"]
    positive = str(row.get("positive_evidence", "") or "")
    if positive:
        base.append(f"现有正向证据：{positive}")
    return base


def _invalidation_signals(primary_type: str, risk_level: str, risk_flags: str, warnings: str) -> list[str]:
    signals = ["趋势结构转弱", "风险分继续下行", "流动性明显收缩"]
    if primary_type in {PRIMARY_BREAKOUT, PRIMARY_REBOUND, PRIMARY_HIGH_RISK_ACTIVE} or risk_level in {"中高", "高"}:
        signals.append("波动扩大或回撤加深")
    if risk_flags:
        signals.append(f"现有风险标记未改善：{risk_flags}")
    if warnings:
        signals.append(f"数据警告仍需复核：{warnings}")
    return signals


def _label_reason(
    primary_type: str,
    row: dict[str, object],
    percentiles: dict[str, object],
    data_quality_notes: list[str],
    *,
    high_risk: bool,
) -> str:
    parts = [
        f"当前归为{primary_type}，依据为总分、趋势、动量、相对强度、风险和流动性的横截面相对排序。",
        f"总分分位约{_pct(percentiles, 'total_score'):.0%}，趋势分位约{_pct(percentiles, 'trend_score'):.0%}，风险分位约{_pct(percentiles, 'risk_score'):.0%}。",
    ]
    if high_risk:
        parts.append("风险标记或风险分位提示该标的需要更谨慎地观察。")
    if "industry" not in row:
        parts.append("当前 outputs 未包含行业字段，因此不做行业热度判断。")
    if data_quality_notes:
        parts.append(f"数据质量提示：{';'.join(data_quality_notes)}。")
    return "".join(parts)


def _research_action(primary_type: str, confidence_level: str, risk_level: str) -> str:
    if primary_type == PRIMARY_INSUFFICIENT_DATA:
        return "数据补充后再评估"
    if primary_type == PRIMARY_HIGH_RISK_ACTIVE:
        return "风险观察"
    if risk_level in {"高", "中高"}:
        return "谨慎观察"
    if confidence_level in {"高", "中高"}:
        return "重点研究"
    return "持续跟踪"


def _confidence_level(row: dict[str, object], *, data_quality_notes: list[str], high_risk: bool, insufficient: bool) -> str:
    if insufficient:
        return "低"
    confidence = _safe_float(row.get("confidence"))
    if data_quality_notes:
        confidence -= 0.15
    if high_risk:
        confidence -= 0.10
    if confidence >= 0.85:
        return "高"
    if confidence >= 0.70:
        return "中高"
    if confidence >= 0.50:
        return "中"
    if confidence >= 0.30:
        return "中低"
    return "低"


def _risk_level(percentiles: dict[str, object], *, risk_flags: str, high_risk: bool, severe_risk: bool, insufficient: bool) -> str:
    if insufficient:
        return "不明"
    if severe_risk:
        return "高"
    if high_risk:
        return "中高"
    risk_pct = _pct(percentiles, "risk_score")
    if risk_pct >= 0.75 and not risk_flags:
        return "低"
    if risk_pct >= 0.55:
        return "中低"
    return "中"


def _data_quality_notes(row: dict[str, object], *, factors_row: dict[str, object], failed_error: str) -> list[str]:
    notes: list[str] = []
    if not factors_row:
        notes.append("missing_factor_row")
    data_points = _safe_float(factors_row.get("data_points")) if factors_row else 0.0
    if factors_row and data_points < 120:
        notes.append("insufficient_history")
    warnings = ";".join([str(row.get("warnings", "") or ""), str(factors_row.get("warnings", "") or "")])
    if "insufficient" in warnings or "missing_required" in warnings:
        notes.append("insufficient_warning")
    if failed_error:
        notes.append(f"failed_symbol:{failed_error}")
    return _ordered_unique(notes)


def _report_paths(symbol: str, as_of_date: str, reports_dir: Path | None) -> tuple[str, str]:
    if not reports_dir or not symbol or not as_of_date:
        return "", ""
    stock_dir = reports_dir / "stocks"
    md = stock_dir / f"{symbol}_{as_of_date}.md"
    html = stock_dir / f"{symbol}_{as_of_date}.html"
    return (str(md) if md.exists() else "", str(html) if html.exists() else "")


def _contains_severe_risk(risk_flags: str) -> bool:
    text = risk_flags.lower()
    return any(flag in text for flag in ["severe", "high_volatility", "large_drawdown", "max_drawdown"])


def _ordered_tags(items: list[tuple[str, bool]]) -> list[str]:
    return [label for label, enabled in items if enabled]


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _pct(values: dict[str, object], key: str, *, default: float = 0.0) -> float:
    value = values.get(key, default)
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: object) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: object) -> int:
    try:
        if pd.isna(value):
            return 0
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _percentile(values: object, *, higher_is_better: bool = True) -> pd.Series:
    series = pd.to_numeric(values, errors="coerce") if values is not None else pd.Series(dtype=float)
    if series.empty:
        return pd.Series(dtype=float)
    return series.rank(method="average", pct=True, ascending=higher_is_better).fillna(0.0).clip(0.0, 1.0)


def _to_frame(value: pd.DataFrame | Iterable[dict[str, object]] | None) -> pd.DataFrame:
    if value is None:
        return pd.DataFrame()
    if isinstance(value, pd.DataFrame):
        return value.copy()
    return pd.DataFrame(list(value))


def _coerce_candidate_numeric(frame: pd.DataFrame) -> None:
    for column in [
        "rank",
        "total_score",
        "confidence",
        "momentum_score",
        "trend_score",
        "relative_strength_score",
        "risk_score",
        "liquidity_score",
    ]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")


def _coerce_factor_numeric(frame: pd.DataFrame) -> None:
    for column in frame.columns:
        if column not in {"symbol", "as_of_date", "source", "warnings"}:
            converted = pd.to_numeric(frame[column], errors="coerce")
            if not converted.isna().all():
                frame[column] = converted


def _index_by_symbol(frame: pd.DataFrame) -> dict[str, dict[str, object]]:
    if frame.empty or "symbol" not in frame.columns:
        return {}
    return {str(row.get("symbol", "")): row for row in frame.to_dict(orient="records")}


def _failed_by_symbol(frame: pd.DataFrame) -> dict[str, str]:
    if frame.empty or "symbol" not in frame.columns:
        return {}
    result: dict[str, str] = {}
    for row in frame.to_dict(orient="records"):
        symbol = str(row.get("symbol", "") or "")
        error_type = str(row.get("error_type", "") or "")
        if symbol:
            result[symbol] = error_type
    return result
