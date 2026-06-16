from __future__ import annotations

from typing import Callable

import pandas as pd

from stock_analysis.research.multi_label import (
    PRIMARY_ACCUMULATION,
    PRIMARY_BREAKOUT,
    PRIMARY_HIGH_RISK_ACTIVE,
    PRIMARY_INSUFFICIENT_DATA,
    PRIMARY_LONG_TERM_STABLE,
    PRIMARY_NORMAL_WATCH,
    PRIMARY_REBOUND,
    PRIMARY_TREND_LEADER,
)


LIST_IDS = [
    "high_confidence_candidates",
    "trend_leaders",
    "long_term_stable",
    "breakout_watch",
    "accumulation_watch",
    "rebound_watch",
    "high_risk_active",
    "insufficient_data",
]

LIST_ITEM_COLUMNS = [
    "symbol",
    "name",
    "rank",
    "total_score",
    "primary_type",
    "secondary_tags",
    "research_action",
    "confidence_level",
    "risk_level",
    "label_reason",
    "confirmation_signals",
    "invalidation_signals",
]


def build_multi_lists(labeled_candidates: pd.DataFrame, *, top_n: int = 30, as_of_date: str | None = None) -> dict[str, object]:
    """Build static research lists from labeled candidate rows."""

    frame = labeled_candidates.copy()
    if frame.empty:
        empty = pd.DataFrame()
        lists = [
            _list_payload(
                list_id,
                as_of_date=as_of_date,
                top_n=top_n,
                source_universe_count=0,
                eligible=empty,
                sort_columns=[],
                ascending=[],
            )
            for list_id in LIST_IDS
        ]
        return {"as_of_date": as_of_date or "", "lists": lists}

    for column in ["total_score", "rank", "momentum_score", "trend_score", "relative_strength_score", "risk_score", "liquidity_score"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)

    resolved_date = as_of_date or str(frame.get("as_of_date", pd.Series([""])).iloc[0])
    source_universe_count = len(frame)
    lists = [
        _list_payload(
            "high_confidence_candidates",
            as_of_date=resolved_date,
            top_n=top_n,
            source_universe_count=source_universe_count,
            eligible=_high_confidence(frame),
            sort_columns=["total_score", "confidence", "risk_score"],
            ascending=[False, False, False],
        ),
        _list_payload(
            "trend_leaders",
            as_of_date=resolved_date,
            top_n=top_n,
            source_universe_count=source_universe_count,
            eligible=_with_tag(frame, PRIMARY_TREND_LEADER, exclude_high_risk=True),
            sort_columns=["trend_score", "momentum_score", "relative_strength_score"],
            ascending=[False, False, False],
        ),
        _list_payload(
            "long_term_stable",
            as_of_date=resolved_date,
            top_n=top_n,
            source_universe_count=source_universe_count,
            eligible=_with_tag(frame, PRIMARY_LONG_TERM_STABLE, exclude_high_risk=True),
            sort_columns=["risk_score", "liquidity_score", "trend_score"],
            ascending=[False, False, False],
        ),
        _list_payload(
            "breakout_watch",
            as_of_date=resolved_date,
            top_n=top_n,
            source_universe_count=source_universe_count,
            eligible=_with_tag(frame, PRIMARY_BREAKOUT),
            sort_columns=["momentum_score", "trend_score", "relative_strength_score"],
            ascending=[False, False, False],
            require_risk_note=True,
        ),
        _list_payload(
            "accumulation_watch",
            as_of_date=resolved_date,
            top_n=top_n,
            source_universe_count=source_universe_count,
            eligible=_accumulation_watch(frame),
            sort_columns=["trend_score", "momentum_score", "relative_strength_score", "risk_score"],
            ascending=[False, False, False, False],
        ),
        _list_payload(
            "rebound_watch",
            as_of_date=resolved_date,
            top_n=top_n,
            source_universe_count=source_universe_count,
            eligible=_with_tag(frame, PRIMARY_REBOUND),
            sort_columns=["momentum_score", "risk_score", "total_score"],
            ascending=[False, False, False],
            require_risk_note=True,
        ),
        _list_payload(
            "high_risk_active",
            as_of_date=resolved_date,
            top_n=top_n,
            source_universe_count=source_universe_count,
            eligible=_high_risk(frame),
            sort_columns=["total_score", "momentum_score", "liquidity_score"],
            ascending=[False, False, False],
            require_risk_note=True,
        ),
        _list_payload(
            "insufficient_data",
            as_of_date=resolved_date,
            top_n=top_n,
            source_universe_count=source_universe_count,
            eligible=frame[frame["primary_type"] == PRIMARY_INSUFFICIENT_DATA],
            sort_columns=["rank"],
            ascending=[True],
        ),
    ]
    return {"as_of_date": resolved_date, "lists": lists}


def list_by_id(multi_lists: dict[str, object]) -> dict[str, dict[str, object]]:
    return {str(item["list_id"]): item for item in multi_lists.get("lists", [])}


def _list_payload(
    list_id: str,
    *,
    as_of_date: str | None,
    top_n: int,
    source_universe_count: int,
    eligible: pd.DataFrame,
    sort_columns: list[str],
    ascending: list[bool],
    require_risk_note: bool = False,
) -> dict[str, object]:
    metadata = _metadata()[list_id]
    items = _items(eligible, sort_columns, ascending, top_n, require_risk_note=require_risk_note)
    return {
        "list_id": list_id,
        "list_name": metadata["list_name"],
        "description": metadata["description"],
        "sort_logic": metadata["sort_logic"],
        "eligible_filters": metadata["eligible_filters"],
        "as_of_date": as_of_date or "",
        "top_n": top_n,
        "source_universe_count": source_universe_count,
        "eligible_count": int(len(eligible)),
        "excluded_count": int(max(source_universe_count - len(eligible), 0)),
        "items": items,
    }


def _metadata() -> dict[str, dict[str, object]]:
    return {
        "high_confidence_candidates": {
            "list_name": "高置信候选",
            "description": "综合分、趋势、风险和流动性较均衡的研究候选。",
            "sort_logic": "total_score desc, confidence desc, risk_score desc",
            "eligible_filters": ["排除数据不足", "排除高风险活跃型", "排除高风险等级"],
        },
        "trend_leaders": {
            "list_name": "趋势龙头观察",
            "description": "趋势、动量和相对强度排序靠前的研究对象。",
            "sort_logic": "trend_score desc, momentum_score desc, relative_strength_score desc",
            "eligible_filters": ["包含趋势龙头型标签", "排除严重高风险"],
        },
        "long_term_stable": {
            "list_name": "长期稳定观察",
            "description": "风险分、流动性和趋势结构较稳的研究对象。",
            "sort_logic": "risk_score desc, liquidity_score desc, trend_score desc",
            "eligible_filters": ["包含长期稳定型标签", "排除高风险活跃型"],
        },
        "breakout_watch": {
            "list_name": "突破观察",
            "description": "短期动量和趋势改善较明显，同时保留风险提示。",
            "sort_logic": "momentum_score desc, trend_score desc, relative_strength_score desc",
            "eligible_filters": ["包含突破爆发型标签", "保留风险提示"],
        },
        "accumulation_watch": {
            "list_name": "蓄势观察",
            "description": "趋势改善、风险可控、仍需确认的研究对象。",
            "sort_logic": "total_score desc, risk_score desc, trend_score desc",
            "eligible_filters": ["包含潜力蓄势型标签", "排除高风险活跃型"],
        },
        "rebound_watch": {
            "list_name": "修复观察",
            "description": "短期修复信号较强但仍需风险复核的研究对象。",
            "sort_logic": "momentum_score desc, risk_score desc, total_score desc",
            "eligible_filters": ["包含超跌反弹型标签", "保留风险提示"],
        },
        "high_risk_active": {
            "list_name": "高风险活跃观察",
            "description": "活跃但风险较高，仅用于风险观察分层。",
            "sort_logic": "total_score desc, momentum_score desc, liquidity_score desc",
            "eligible_filters": ["包含高风险活跃型标签"],
        },
        "insufficient_data": {
            "list_name": "数据不足",
            "description": "历史行情、因子或候选字段不足，需要补齐后再评估。",
            "sort_logic": "rank asc",
            "eligible_filters": ["primary_type == 数据不足"],
        },
    }


def _items(
    frame: pd.DataFrame,
    sort_columns: list[str],
    ascending: list[bool],
    top_n: int,
    *,
    require_risk_note: bool = False,
) -> list[dict[str, object]]:
    if frame.empty:
        return []
    columns = [column for column in sort_columns if column in frame.columns]
    sorted_frame = frame.sort_values(columns or ["rank"], ascending=ascending[: len(columns)] or [True]).head(top_n)
    result: list[dict[str, object]] = []
    for row in sorted_frame.to_dict(orient="records"):
        item = {column: row.get(column) for column in LIST_ITEM_COLUMNS}
        if require_risk_note:
            invalidation = item.get("invalidation_signals")
            if not isinstance(invalidation, list):
                invalidation = [] if invalidation in (None, "") else [str(invalidation)]
            if not any("风险" in str(signal) or "波动" in str(signal) or "回撤" in str(signal) for signal in invalidation):
                invalidation.append("风险或波动变化需要持续复核")
            item["invalidation_signals"] = invalidation
        result.append(item)
    return result


def _high_confidence(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[
        (frame["primary_type"] != PRIMARY_INSUFFICIENT_DATA)
        & (frame["primary_type"] != PRIMARY_HIGH_RISK_ACTIVE)
        & (~frame["risk_level"].isin(["高", "中高", "不明"]))
        & (frame["confidence_level"].isin(["高", "中高"]))
    ]


def _high_risk(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[
        (frame["primary_type"] == PRIMARY_HIGH_RISK_ACTIVE)
        | (frame["risk_level"].isin(["高", "中高"]))
        | (frame["secondary_tags"].apply(lambda tags: PRIMARY_HIGH_RISK_ACTIVE in _as_list(tags)))
    ]


def _accumulation_watch(frame: pd.DataFrame) -> pd.DataFrame:
    base = _with_tag(frame, PRIMARY_ACCUMULATION, exclude_high_risk=True)
    if base.empty:
        base = frame[
            (frame["primary_type"].isin([PRIMARY_ACCUMULATION, PRIMARY_NORMAL_WATCH]))
            & (~frame["risk_level"].isin(["高", "中高", "不明"]))
        ]
    if base.empty or "total_score" not in base.columns:
        return base
    total_rank = frame["total_score"].rank(method="average", pct=True)
    return base[total_rank.loc[base.index] < 0.90]


def _with_tag(frame: pd.DataFrame, tag: str, *, exclude_high_risk: bool = False) -> pd.DataFrame:
    mask = (frame["primary_type"] == tag) | frame["secondary_tags"].apply(lambda tags: tag in _as_list(tags))
    if exclude_high_risk:
        mask &= (frame["primary_type"] != PRIMARY_HIGH_RISK_ACTIVE) & (~frame["risk_level"].isin(["高", "中高"]))
    return frame[mask]


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value in (None, ""):
        return []
    return [part for part in str(value).split(";") if part]
