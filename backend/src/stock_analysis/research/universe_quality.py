from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd


NON_STOCK_KEYWORDS = [
    "指数",
    "企债",
    "信用债",
    "转债",
    "可转债",
    "基金",
    "ETF",
    "etf",
    "国证",
    "中证",
    "深证成指",
    "沪深",
    "上证指数",
]


def classify_instrument(row: dict[str, object]) -> dict[str, object]:
    """Classify whether a row is a plain A-share stock research target."""

    symbol = normalize_symbol(str(row.get("symbol", "") or ""))
    name = str(row.get("name", "") or "")
    code = symbol_code(symbol)
    text = f"{name} {symbol}".lower()

    for keyword in NON_STOCK_KEYWORDS:
        if keyword.lower() in text:
            return {
                "is_stock": False,
                "instrument_type": _instrument_type_from_keyword(keyword),
                "excluded_reason": f"name_or_symbol_contains:{keyword}",
            }

    if symbol.startswith("sh.") and code.startswith(("000", "880", "990")):
        return {"is_stock": False, "instrument_type": "index", "excluded_reason": "sh_index_symbol_pattern"}
    if symbol.startswith("sz.") and code.startswith(("399",)):
        return {"is_stock": False, "instrument_type": "index", "excluded_reason": "sz_index_symbol_pattern"}

    if symbol.startswith("sh.") and code.startswith(("600", "601", "603", "605", "688", "689")):
        return {"is_stock": True, "instrument_type": "stock", "excluded_reason": ""}
    if symbol.startswith("sz.") and code.startswith(("000", "001", "002", "003", "300", "301")):
        return {"is_stock": True, "instrument_type": "stock", "excluded_reason": ""}
    if symbol.startswith("bj.") and code[:1] in {"4", "8", "9"}:
        return {"is_stock": True, "instrument_type": "stock", "excluded_reason": ""}

    if code and len(code) == 6 and code[0] in {"0", "3", "6", "8", "4", "9"}:
        return {"is_stock": True, "instrument_type": "stock", "excluded_reason": ""}

    return {"is_stock": False, "instrument_type": "unknown", "excluded_reason": "not_plain_a_share_symbol"}


def build_label_input_rows(
    candidates: pd.DataFrame | Iterable[dict[str, object]],
    *,
    factors: pd.DataFrame | Iterable[dict[str, object]] | None = None,
    failed_symbols: pd.DataFrame | Iterable[dict[str, object]] | None = None,
    stock_universe: pd.DataFrame | Iterable[dict[str, object]] | None = None,
    as_of_date: str | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Build the full stock label universe input from existing local outputs only."""

    candidate_frame = _to_frame(candidates)
    factor_frame = _to_frame(factors)
    failed_frame = _to_frame(failed_symbols)
    universe_frame = _to_frame(stock_universe)

    candidate_by_symbol = _index_by_symbol(candidate_frame)
    factor_by_symbol = _index_by_symbol(factor_frame)
    failed_by_symbol = _index_by_symbol(failed_frame)
    universe_by_symbol = _index_by_symbol(universe_frame)
    factor_scores = _factor_score_rows(factor_frame, as_of_date=as_of_date)

    ordered_symbols = _ordered_symbols([universe_frame, factor_frame, candidate_frame, failed_frame])
    label_inputs: list[dict[str, object]] = []
    excluded: list[dict[str, object]] = []

    for symbol in ordered_symbols:
        base = {
            **universe_by_symbol.get(symbol, {}),
            **factor_by_symbol.get(symbol, {}),
            **candidate_by_symbol.get(symbol, {}),
        }
        base["symbol"] = symbol
        base["name"] = _first_text(
            candidate_by_symbol.get(symbol, {}).get("name"),
            universe_by_symbol.get(symbol, {}).get("name"),
            failed_by_symbol.get(symbol, {}).get("name"),
            base.get("name"),
        )
        classification = classify_instrument(base)
        if not classification["is_stock"]:
            excluded.append(
                {
                    "symbol": symbol,
                    "name": base.get("name", ""),
                    "instrument_type": classification["instrument_type"],
                    "excluded_reason": classification["excluded_reason"],
                    "source": _source_for_symbol(symbol, candidate_by_symbol, factor_by_symbol, failed_by_symbol, universe_by_symbol),
                }
            )
            continue

        if symbol in candidate_by_symbol:
            row = dict(candidate_by_symbol[symbol])
            row["name"] = base.get("name", row.get("name", ""))
        elif symbol in factor_by_symbol:
            row = _factor_only_candidate_row(symbol, base, factor_scores.get(symbol, {}), as_of_date=as_of_date)
        else:
            row = _insufficient_candidate_row(symbol, base, failed_by_symbol.get(symbol, {}), as_of_date=as_of_date)

        row["symbol"] = symbol
        row["name"] = _first_text(row.get("name"), base.get("name"), symbol)
        label_inputs.append(row)

    return label_inputs, excluded


def build_stock_index(
    labels: pd.DataFrame | Iterable[dict[str, object]],
    *,
    excluded_non_stock: pd.DataFrame | Iterable[dict[str, object]] | None = None,
    candidates: pd.DataFrame | Iterable[dict[str, object]] | None = None,
    factors: pd.DataFrame | Iterable[dict[str, object]] | None = None,
    failed_symbols: pd.DataFrame | Iterable[dict[str, object]] | None = None,
    multi_lists: dict[str, object] | None = None,
    reports_dir: str | Path | None = None,
    as_of_date: str | None = None,
) -> dict[str, object]:
    """Build a searchable stock/instrument index from static outputs."""

    label_frame = _to_frame(labels)
    excluded_frame = _to_frame(excluded_non_stock)
    candidate_symbols = set(_index_by_symbol(_to_frame(candidates)))
    factor_symbols = set(_index_by_symbol(_to_frame(factors)))
    failed_by_symbol = _index_by_symbol(_to_frame(failed_symbols))
    related_lists = _related_lists(multi_lists or {})
    report_symbols = _report_symbols(Path(reports_dir) if reports_dir else None, as_of_date)

    items: list[dict[str, object]] = []
    for row in label_frame.to_dict(orient="records"):
        symbol = normalize_symbol(str(row.get("symbol", "") or ""))
        if not symbol:
            continue
        reports = _report_links(symbol, Path(reports_dir) if reports_dir else None, as_of_date)
        lists = related_lists.get(symbol, [])
        in_failed = symbol in failed_by_symbol
        items.append(
            {
                "symbol": symbol,
                "code": symbol_code(symbol),
                "name": row.get("name", ""),
                "is_stock": True,
                "instrument_type": "stock",
                "research_status": _research_status(row, lists, in_failed),
                "primary_type": row.get("primary_type", ""),
                "secondary_tags": _as_list(row.get("secondary_tags")),
                "research_action": row.get("research_action", ""),
                "confidence_level": row.get("confidence_level", ""),
                "risk_level": row.get("risk_level", ""),
                "rank": row.get("rank", 0),
                "total_score": row.get("total_score", 0),
                "momentum_score": row.get("momentum_score", 0),
                "trend_score": row.get("trend_score", 0),
                "relative_strength_score": row.get("relative_strength_score", 0),
                "risk_score": row.get("risk_score", 0),
                "liquidity_score": row.get("liquidity_score", 0),
                "in_factors": symbol in factor_symbols,
                "in_candidate_labels": True,
                "in_candidate_pool": symbol in candidate_symbols,
                "in_failed_symbols": in_failed,
                "in_any_list": bool(lists),
                "related_lists": lists,
                "has_report": symbol in report_symbols or bool(reports),
                "report_links": reports,
                "data_quality": row.get("data_quality", ""),
                "excluded_reason": "",
                "message": _stock_index_message(row, lists, in_failed),
            }
        )

    for row in excluded_frame.to_dict(orient="records"):
        symbol = normalize_symbol(str(row.get("symbol", "") or ""))
        if not symbol:
            continue
        items.append(
            {
                "symbol": symbol,
                "code": symbol_code(symbol),
                "name": row.get("name", ""),
                "is_stock": False,
                "instrument_type": row.get("instrument_type", "unknown"),
                "research_status": "非股票标的",
                "primary_type": "非股票标的",
                "secondary_tags": [],
                "research_action": "不纳入股票研究榜单",
                "confidence_level": "",
                "risk_level": "",
                "rank": 0,
                "total_score": 0,
                "momentum_score": 0,
                "trend_score": 0,
                "relative_strength_score": 0,
                "risk_score": 0,
                "liquidity_score": 0,
                "in_factors": symbol in factor_symbols,
                "in_candidate_labels": False,
                "in_candidate_pool": symbol in candidate_symbols,
                "in_failed_symbols": symbol in failed_by_symbol,
                "in_any_list": False,
                "related_lists": [],
                "has_report": symbol in report_symbols,
                "report_links": _report_links(symbol, Path(reports_dir) if reports_dir else None, as_of_date),
                "data_quality": "excluded_non_stock",
                "excluded_reason": row.get("excluded_reason", ""),
                "message": "该标的不纳入 A 股个股研究榜单。",
            }
        )

    return {
        "status": "ok",
        "as_of_date": as_of_date or "",
        "item_count": len(items),
        "stock_count": sum(1 for item in items if item["is_stock"]),
        "excluded_non_stock_count": sum(1 for item in items if not item["is_stock"]),
        "items": items,
    }


def normalize_symbol(symbol: str) -> str:
    text = str(symbol or "").strip().lower()
    return text


def symbol_code(symbol: str) -> str:
    text = normalize_symbol(symbol)
    return text.split(".")[-1] if "." in text else text


def _factor_only_candidate_row(symbol: str, base: dict[str, object], scores: dict[str, float], *, as_of_date: str | None) -> dict[str, object]:
    return {
        "rank": 0,
        "symbol": symbol,
        "name": base.get("name", ""),
        "as_of_date": base.get("as_of_date") or as_of_date or "",
        "total_score": scores.get("total_score", 0.0),
        "label": "观察",
        "confidence": scores.get("confidence", 0.55),
        "momentum_score": scores.get("momentum_score", 0.0),
        "trend_score": scores.get("trend_score", 0.0),
        "relative_strength_score": scores.get("relative_strength_score", 0.0),
        "risk_score": scores.get("risk_score", 0.0),
        "liquidity_score": scores.get("liquidity_score", 0.0),
        "positive_evidence": "存在可用因子数据，但当前未必进入主要榜单。",
        "negative_evidence": "",
        "risk_flags": "",
        "warnings": str(base.get("warnings", "") or ""),
        "source": "factors_universe",
    }


def _insufficient_candidate_row(symbol: str, base: dict[str, object], failed: dict[str, object], *, as_of_date: str | None) -> dict[str, object]:
    error_type = str(failed.get("error_type", "") or "missing_factor_row")
    error_message = str(failed.get("error_message", failed.get("error", "")) or "")
    return {
        "rank": 0,
        "symbol": symbol,
        "name": base.get("name", ""),
        "as_of_date": base.get("as_of_date") or as_of_date or "",
        "total_score": 0.0,
        "label": "数据不足",
        "confidence": 0.1,
        "momentum_score": 0.0,
        "trend_score": 0.0,
        "relative_strength_score": 0.0,
        "risk_score": 0.0,
        "liquidity_score": 0.0,
        "positive_evidence": "",
        "negative_evidence": error_message,
        "risk_flags": "",
        "warnings": error_type,
        "source": "failed_or_missing_factor",
    }


def _factor_score_rows(frame: pd.DataFrame, *, as_of_date: str | None) -> dict[str, dict[str, float]]:
    if frame.empty or "symbol" not in frame.columns:
        return {}
    work = frame.copy()
    for column in work.columns:
        if column not in {"symbol", "as_of_date", "source", "warnings"}:
            work[column] = pd.to_numeric(work[column], errors="coerce")

    def pct(column: str, *, higher_is_better: bool = True) -> pd.Series:
        if column not in work.columns:
            return pd.Series([0.5] * len(work), index=work.index)
        values = pd.to_numeric(work[column], errors="coerce")
        return values.rank(pct=True, ascending=higher_is_better).fillna(0.5).clip(0.0, 1.0)

    momentum = (pct("momentum_20d") + pct("momentum_60d") + pct("momentum_120d")) / 3.0
    trend = (
        pct("ma_bullish_alignment")
        + pct("above_ma20")
        + pct("above_ma60")
    ) / 3.0
    relative_strength = (pct("rs_20d") + pct("rs_60d") + pct("rs_120d")) / 3.0
    risk = (
        pct("volatility_20d", higher_is_better=False)
        + pct("volatility_60d", higher_is_better=False)
        + pct("max_drawdown_60d", higher_is_better=False)
    ) / 3.0
    liquidity = (pct("avg_amount_20d") + pct("avg_amount_60d")) / 2.0

    scores: dict[str, dict[str, float]] = {}
    for idx, row in work.iterrows():
        symbol = normalize_symbol(str(row.get("symbol", "") or ""))
        if not symbol:
            continue
        values = {
            "momentum_score": float(momentum.loc[idx] * 25.0),
            "trend_score": float(trend.loc[idx] * 20.0),
            "relative_strength_score": float(relative_strength.loc[idx] * 20.0),
            "risk_score": float(risk.loc[idx] * 20.0),
            "liquidity_score": float(liquidity.loc[idx] * 15.0),
            "confidence": 0.55 if float(row.get("data_points", 0) or 0) >= 120 else 0.35,
        }
        values["total_score"] = sum(values[key] for key in ["momentum_score", "trend_score", "relative_strength_score", "risk_score", "liquidity_score"])
        scores[symbol] = values
    return scores


def _stock_index_message(row: dict[str, object], related_lists: list[dict[str, object]], in_failed: bool) -> str:
    if in_failed or str(row.get("primary_type", "")) == "数据不足":
        return "当前数据不足，需要补齐后再评估。"
    if related_lists:
        return "已进入当前研究榜单。"
    return "有标签但未进入主要榜单，作为普通观察。"


def _research_status(row: dict[str, object], related_lists: list[dict[str, object]], in_failed: bool) -> str:
    primary = str(row.get("primary_type", "") or "")
    if in_failed or primary == "数据不足":
        return "数据不足"
    if primary == "高风险活跃型":
        return "高风险活跃型"
    if not related_lists:
        return "普通观察"
    return str(row.get("research_status") or primary)


def _related_lists(multi_lists: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = {}
    raw_lists = multi_lists.get("lists", []) if isinstance(multi_lists, dict) else []
    if not isinstance(raw_lists, list):
        return result
    for raw in raw_lists:
        if not isinstance(raw, dict):
            continue
        list_id = str(raw.get("list_id", ""))
        list_name = str(raw.get("list_name", ""))
        items = raw.get("items", [])
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            symbol = normalize_symbol(str(item.get("symbol", "") or ""))
            result.setdefault(symbol, []).append({"list_id": list_id, "list_name": list_name, "position": index, "item_count": len(items)})
    return result


def _report_symbols(reports_dir: Path | None, as_of_date: str | None) -> set[str]:
    if not reports_dir:
        return set()
    stock_dir = reports_dir / "stocks"
    if not stock_dir.exists():
        return set()
    suffix = f"_{as_of_date}" if as_of_date else "_"
    symbols = set()
    for path in stock_dir.iterdir():
        if not path.is_file():
            continue
        stem = path.stem
        if suffix in stem:
            symbols.add(normalize_symbol(stem.split(suffix)[0]))
    return symbols


def _report_links(symbol: str, reports_dir: Path | None, as_of_date: str | None) -> dict[str, str]:
    if not reports_dir or not as_of_date:
        return {}
    stock_dir = reports_dir / "stocks"
    md = stock_dir / f"{symbol}_{as_of_date}.md"
    html = stock_dir / f"{symbol}_{as_of_date}.html"
    result = {}
    if md.exists():
        result["markdown_path"] = str(md)
    if html.exists():
        result["html_path"] = str(html)
    return result


def _instrument_type_from_keyword(keyword: str) -> str:
    if "ETF" in keyword or "etf" in keyword or "基金" in keyword:
        return "fund_or_etf"
    if "债" in keyword:
        return "bond_or_bond_index"
    if "指数" in keyword or keyword in {"国证", "中证", "沪深", "深证成指"}:
        return "index"
    return "non_stock"


def _source_for_symbol(
    symbol: str,
    candidate_by_symbol: dict[str, dict[str, object]],
    factor_by_symbol: dict[str, dict[str, object]],
    failed_by_symbol: dict[str, dict[str, object]],
    universe_by_symbol: dict[str, dict[str, object]],
) -> str:
    sources = []
    if symbol in candidate_by_symbol:
        sources.append("candidates")
    if symbol in factor_by_symbol:
        sources.append("factors")
    if symbol in failed_by_symbol:
        sources.append("failed_symbols")
    if symbol in universe_by_symbol:
        sources.append("stock_universe_cache")
    return ";".join(sources)


def _ordered_symbols(frames: list[pd.DataFrame]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for frame in frames:
        if frame.empty or "symbol" not in frame.columns:
            continue
        for value in frame["symbol"].tolist():
            symbol = normalize_symbol(str(value or ""))
            if symbol and symbol not in seen:
                seen.add(symbol)
                result.append(symbol)
    return result


def _index_by_symbol(frame: pd.DataFrame) -> dict[str, dict[str, object]]:
    if frame.empty or "symbol" not in frame.columns:
        return {}
    return {normalize_symbol(str(row.get("symbol", "") or "")): row for row in frame.to_dict(orient="records") if row.get("symbol")}


def _to_frame(value: pd.DataFrame | Iterable[dict[str, object]] | None) -> pd.DataFrame:
    if value is None:
        return pd.DataFrame()
    if isinstance(value, pd.DataFrame):
        return value.copy()
    return pd.DataFrame(list(value))


def _first_text(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text and text.lower() != "nan":
            return text
    return ""


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value in (None, ""):
        return []
    return [part for part in str(value).split(";") if part]
