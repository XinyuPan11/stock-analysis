from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from stock_analysis.research.candidate_tiering import (
    CANDIDATE_TIERING_CONFIG,
    TIER_SOURCE_LIST_IDS,
    build_candidate_tiering_display,
)
from stock_analysis.research.defensive_positioning import (
    DEFENSIVE_POSITIONING_CONFIG,
    build_defensive_positioning_display,
)
from stock_analysis.api.schemas import NO_DAILY_OUTPUT_MESSAGE, NO_STOCK_REPORT_MESSAGE


DAILY_FILE_PATTERNS = {
    "candidates": "candidates_{date}.json",
    "summary": "summary_{date}.json",
    "factors": "factors_{date}.json",
    "factor_explanations": "factor_explanations_{date}.json",
}

BACKTEST_FILE_PATTERNS = {
    "summary": "backtest_summary_{date}.json",
    "markdown": "backtest_report_{date}.md",
    "html": "backtest_report_{date}.html",
}

RESEARCH_LABELS = [
    "高置信候选",
    "候选关注",
    "重点观察",
    "观察",
    "风险过高",
    "数据不足",
]

PROHIBITED_TERMS = ["买入", "卖出", "强烈买入", "建议买入"]
PROHIBITED_REPLACEMENT = "确定性交易表述已隐藏"
SORTABLE_CANDIDATE_FIELDS = {
    "rank",
    "total_score",
    "confidence",
    "momentum_score",
    "trend_score",
    "relative_strength_score",
    "risk_score",
    "liquidity_score",
}

FACTOR_GROUP_LABELS = {
    "momentum": "动量",
    "trend": "趋势",
    "relative_strength": "相对强度",
    "risk": "风险",
    "liquidity": "流动性",
}

FACTOR_GROUP_ALIASES = {
    "动量": "momentum",
    "momentum": "momentum",
    "趋势": "trend",
    "trend": "trend",
    "相对强度": "relative_strength",
    "relative_strength": "relative_strength",
    "relative-strength": "relative_strength",
    "strength": "relative_strength",
    "风险": "risk",
    "risk": "risk",
    "流动性": "liquidity",
    "liquidity": "liquidity",
}

NO_FACTOR_EXPLANATIONS_MESSAGE = "暂无真实因子贡献表，请先生成 factor_explanations 输出。"
NO_REPORTS_MESSAGE = "No reports found. Please generate research reports first."
API_DISCLAIMER = "本系统仅用于个人研究和学习，不构成投资建议，不提供确定性交易指令或收益承诺。"
SUPPORTED_RESEARCH_LIST_IDS = {
    "high_confidence_candidates",
    "trend_leaders",
    "long_term_stable",
    "breakout_watch",
    "accumulation_watch",
    "rebound_watch",
    "high_risk_active",
    "insufficient_data",
}


@dataclass(frozen=True)
class ReportFile:
    symbol: str | None
    as_of_date: str | None
    markdown_path: Path | None
    html_path: Path | None


class OutputLoader:
    def __init__(self, outputs_dir: str | Path) -> None:
        self.outputs_dir = Path(outputs_dir).resolve()

    @property
    def daily_dir(self) -> Path:
        return self.outputs_dir / "daily"

    @property
    def reports_dir(self) -> Path:
        return self.outputs_dir / "reports"

    @property
    def stock_reports_dir(self) -> Path:
        return self.reports_dir / "stocks"

    @property
    def backtests_dir(self) -> Path:
        return self.outputs_dir / "backtests"

    @property
    def labels_dir(self) -> Path:
        return self.outputs_dir / "labels"

    @property
    def lists_dir(self) -> Path:
        return self.outputs_dir / "lists"

    @property
    def search_dir(self) -> Path:
        return self.outputs_dir / "search"

    def latest_daily_date(self) -> str | None:
        dates: set[str] = set()
        for prefix in ["candidates", "summary", "factors", "factor_explanations"]:
            dates.update(self._dates_from_files(self.daily_dir, rf"^{prefix}_(\d{{4}}-\d{{2}}-\d{{2}})\.json$"))
        return max(dates) if dates else None

    def latest_backtest_date(self) -> str | None:
        dates = self._dates_from_files(self.backtests_dir, r"^backtest_summary_(\d{4}-\d{2}-\d{2})\.json$")
        return max(dates) if dates else None

    def latest_workflow_date(self) -> str | None:
        dates = self._dates_from_files(self.outputs_dir / "workflow", r"^workflow_summary_(\d{4}-\d{2}-\d{2})\.json$")
        return max(dates) if dates else None

    def latest_label_date(self) -> str | None:
        dates = self._dates_from_files(self.labels_dir, r"^candidate_labels_(\d{4}-\d{2}-\d{2})\.json$")
        return max(dates) if dates else self.latest_daily_date()

    def latest_list_date(self) -> str | None:
        dates = self._dates_from_files(self.lists_dir, r"^multi_lists_(\d{4}-\d{2}-\d{2})\.json$")
        return max(dates) if dates else self.latest_label_date()

    def latest_search_date(self) -> str | None:
        dates = self._dates_from_files(self.search_dir, r"^stock_index_(\d{4}-\d{2}-\d{2})\.json$")
        return max(dates) if dates else self.latest_label_date()

    def latest(self) -> dict[str, Any]:
        as_of_date = self.latest_daily_date()
        files = self._daily_files(as_of_date) if as_of_date else {}
        available = {key: path.exists() for key, path in files.items()}
        return {
            "ok": as_of_date is not None,
            "message": "" if as_of_date else NO_DAILY_OUTPUT_MESSAGE,
            "as_of_date": as_of_date,
            "outputs_dir": str(self.outputs_dir),
            "available": available,
            "files": {key: str(path) for key, path in files.items() if path.exists()},
        }

    def load_candidates(
        self,
        *,
        label: str | None = None,
        min_score: float | None = None,
        max_score: float | None = None,
        min_confidence: float | None = None,
        sort_by: str = "total_score",
        sort_order: str = "desc",
        limit: int | None = None,
    ) -> dict[str, Any]:
        as_of_date = self.latest_daily_date()
        if not as_of_date:
            return self._empty_candidates()
        path = self._daily_files(as_of_date)["candidates"]
        if not path.exists():
            return self._empty_candidates(as_of_date=as_of_date)

        payload = self._read_json(path, fallback=[])
        rows = payload.get("candidates", payload) if isinstance(payload, dict) else payload
        rows = rows if isinstance(rows, list) else []
        rows = self._sanitize_payload(rows)
        rows = sorted([row for row in rows if isinstance(row, dict)], key=self._score_sort_key, reverse=True)
        total_count = len(rows)
        filters = {
            "label": label or "",
            "min_score": min_score,
            "max_score": max_score,
            "min_confidence": min_confidence,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "limit": limit,
        }
        validation_error = self._candidate_filter_error(sort_by=sort_by, sort_order=sort_order, limit=limit)
        if validation_error:
            return {
                "ok": False,
                "message": validation_error,
                "as_of_date": as_of_date,
                "count": 0,
                "total_count": total_count,
                "filters": filters,
                "items": [],
                "label_distribution": dict(Counter(str(row.get("label", "")) for row in rows)),
                "high_confidence": [],
            }
        rows = self._filter_candidate_rows(
            rows,
            label=label,
            min_score=min_score,
            max_score=max_score,
            min_confidence=min_confidence,
        )
        rows = self._sort_candidate_rows(rows, sort_by=sort_by, sort_order=sort_order)
        if limit is not None:
            rows = rows[:limit]
        label_distribution = dict(Counter(str(row.get("label", "")) for row in rows))
        high_confidence = [row for row in rows if row.get("label") == RESEARCH_LABELS[0]]
        return {
            "ok": True,
            "message": "",
            "as_of_date": as_of_date,
            "count": len(rows),
            "total_count": total_count,
            "filters": filters,
            "items": rows,
            "label_distribution": label_distribution,
            "high_confidence": high_confidence,
        }

    def get_candidate_by_symbol(self, symbol: str) -> dict[str, Any]:
        normalized = self._normalize_symbol(symbol)
        candidates = self.load_candidates()
        if not candidates["ok"]:
            return {
                "ok": False,
                "message": candidates["message"],
                "as_of_date": candidates["as_of_date"],
                "symbol": normalized,
                "item": None,
                "factor_explanations": [],
                "report": None,
            }
        for row in candidates["items"]:
            if self._normalize_symbol(str(row.get("symbol", ""))) == normalized:
                return {
                    "ok": True,
                    "message": "",
                    "as_of_date": candidates["as_of_date"],
                    "symbol": str(row.get("symbol", normalized)),
                    "item": row,
                    "factor_explanations": self.get_factor_explanations_by_symbol(normalized)["items"],
                    "factor_summary": self.get_factor_summary_by_symbol(normalized),
                    "report": self._report_link(self.stock_report_file(normalized)),
                }
        return {
            "ok": False,
            "message": f"No candidate found for symbol: {normalized}.",
            "as_of_date": candidates["as_of_date"],
            "symbol": normalized,
            "item": None,
            "factor_explanations": [],
            "factor_summary": self.get_factor_summary_by_symbol(normalized),
            "report": self._report_link(self.stock_report_file(normalized)),
        }

    def load_factor_explanations(self) -> dict[str, Any]:
        as_of_date = self.latest_daily_date()
        if not as_of_date:
            return {"ok": False, "message": NO_DAILY_OUTPUT_MESSAGE, "as_of_date": None, "symbol": None, "count": 0, "items": []}
        path = self._daily_files(as_of_date)["factor_explanations"]
        if not path.exists():
            return {
                "ok": False,
                "message": f"Factor explanations output not found for {as_of_date}.",
                "as_of_date": as_of_date,
                "symbol": None,
                "count": 0,
                "items": [],
            }
        payload = self._read_json(path, fallback=[])
        rows = payload.get("factor_explanations", payload) if isinstance(payload, dict) else payload
        rows = rows if isinstance(rows, list) else []
        rows = [row for row in self._sanitize_payload(rows) if isinstance(row, dict)]
        return {"ok": True, "message": "", "as_of_date": as_of_date, "symbol": None, "count": len(rows), "items": rows}

    def get_factor_explanations_by_symbol(self, symbol: str) -> dict[str, Any]:
        normalized = self._normalize_symbol(symbol)
        payload = self.load_factor_explanations()
        rows = [
            row for row in payload["items"]
            if self._normalize_symbol(str(row.get("symbol", ""))) == normalized
        ]
        return {
            "ok": bool(rows) or payload["ok"],
            "message": "" if rows else ("No factor explanations found for this symbol." if payload["ok"] else payload["message"]),
            "as_of_date": payload["as_of_date"],
            "symbol": normalized,
            "count": len(rows),
            "items": rows,
        }

    def get_factor_summary_by_symbol(self, symbol: str) -> dict[str, Any]:
        normalized = self._normalize_symbol(symbol)
        payload = self.get_factor_explanations_by_symbol(normalized)
        if not payload["items"]:
            return {
                "ok": False,
                "message": NO_FACTOR_EXPLANATIONS_MESSAGE,
                "as_of_date": payload["as_of_date"],
                "symbol": normalized,
                "count": 0,
                "items": [],
                "positive_factors": [],
                "risk_factors": [],
                "watch_signals": [],
                "explanation": NO_FACTOR_EXPLANATIONS_MESSAGE,
            }

        grouped: dict[str, dict[str, Any]] = {}
        for row in payload["items"]:
            group_key = self._factor_group_key(str(row.get("factor_group", "")))
            item = grouped.setdefault(
                group_key,
                {
                    "factor_group": group_key,
                    "display_name": FACTOR_GROUP_LABELS.get(group_key, group_key),
                    "normalized_score": 0.0,
                    "weight": 0.0,
                    "contribution": 0.0,
                    "explanations": [],
                },
            )
            item["normalized_score"] += self._number(row.get("normalized_score"))
            item["weight"] += self._number(row.get("weight"))
            item["contribution"] += self._number(row.get("contribution"))
            explanation = str(row.get("explanation", "") or "").strip()
            if explanation:
                item["explanations"].append(explanation)

        summaries = []
        for item in grouped.values():
            explanations = item.pop("explanations")
            item["explanation"] = "；".join(explanations[:3])
            summaries.append(item)
        summaries = sorted(summaries, key=lambda row: self._number(row.get("contribution")), reverse=True)
        positive = [row for row in summaries if self._number(row.get("contribution")) > 0][:3]
        risks = [
            row for row in summaries
            if row["factor_group"] == "risk" or self._number(row.get("normalized_score")) < 0.35 or self._number(row.get("contribution")) < 0
        ][:3]
        watch = [
            row for row in summaries
            if row not in positive and row not in risks
        ][:3]
        explanation = self._score_explanation(summaries, risks)
        return {
            "ok": True,
            "message": "",
            "as_of_date": payload["as_of_date"],
            "symbol": normalized,
            "count": len(summaries),
            "items": summaries,
            "positive_factors": positive,
            "risk_factors": risks,
            "watch_signals": watch,
            "explanation": explanation,
        }

    def get_compare_rows(
        self,
        *,
        label: str | None = None,
        min_score: float | None = None,
        sort_by: str = "total_score",
        sort_order: str = "desc",
        limit: int | None = None,
    ) -> dict[str, Any]:
        candidates = self.load_candidates(
            label=label,
            min_score=min_score,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
        )
        if not candidates["ok"]:
            return {**candidates, "items": []}

        rows = []
        for candidate in candidates["items"]:
            symbol = str(candidate.get("symbol", ""))
            factor_summary = self.get_factor_summary_by_symbol(symbol)
            rows.append(
                {
                    **candidate,
                    "detail_link": f"/stocks/{symbol}",
                    "report_link": f"/reports/stocks/{symbol}",
                    "research_explanation": factor_summary.get("explanation", NO_FACTOR_EXPLANATIONS_MESSAGE),
                    "factor_summary": factor_summary,
                }
            )
        return {**candidates, "items": rows}

    def get_factor_group_matrix(
        self,
        *,
        label: str | None = None,
        min_score: float | None = None,
        sort_by: str = "total_score",
        sort_order: str = "desc",
        limit: int | None = None,
    ) -> dict[str, Any]:
        compare = self.get_compare_rows(
            label=label,
            min_score=min_score,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
        )
        if not compare["ok"]:
            return {**compare, "factor_group": None, "display_name": None}

        rows = [self._factor_group_matrix_row(row) for row in compare["items"]]
        return {
            "ok": True,
            "message": "",
            "as_of_date": compare["as_of_date"],
            "factor_group": None,
            "display_name": None,
            "count": len(rows),
            "filters": compare.get("filters", {}),
            "items": rows,
        }

    def get_factor_group_comparison(
        self,
        factor_group: str,
        *,
        label: str | None = None,
        min_score: float | None = None,
        sort_by: str = "total_score",
        sort_order: str = "desc",
        limit: int | None = None,
    ) -> dict[str, Any]:
        group_key = self._normalize_factor_group(factor_group)
        matrix = self.get_factor_group_matrix(
            label=label,
            min_score=min_score,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
        )
        if not matrix["ok"]:
            return {**matrix, "factor_group": group_key, "display_name": FACTOR_GROUP_LABELS.get(group_key, group_key)}

        contribution_key = f"{group_key}_contribution"
        score_key = f"{group_key}_normalized_score"
        rows = []
        for row in matrix["items"]:
            rows.append(
                {
                    "symbol": row.get("symbol"),
                    "name": row.get("name"),
                    "label": row.get("label"),
                    "total_score": row.get("total_score"),
                    "factor_group": group_key,
                    "display_name": FACTOR_GROUP_LABELS.get(group_key, group_key),
                    "contribution": row.get(contribution_key, 0.0),
                    "normalized_score": row.get(score_key, 0.0),
                    "top_positive_factor_group": row.get("top_positive_factor_group", ""),
                    "top_risk_factor_group": row.get("top_risk_factor_group", ""),
                    "warning": row.get("factor_warning", ""),
                    "detail_link": row.get("detail_link"),
                    "report_link": row.get("report_link"),
                }
            )
        return {
            "ok": True,
            "message": "",
            "as_of_date": matrix["as_of_date"],
            "factor_group": group_key,
            "display_name": FACTOR_GROUP_LABELS.get(group_key, group_key),
            "count": len(rows),
            "filters": matrix.get("filters", {}),
            "items": rows,
        }

    def get_research_lists(self) -> dict[str, Any]:
        as_of_date = self.latest_list_date()
        if not as_of_date:
            return {
                "ok": False,
                "message": "No multi-list output found. Please run generate_research_views.py first.",
                "date": None,
                "lists": [],
                "disclaimer": API_DISCLAIMER,
            }
        path = self.lists_dir / f"multi_lists_{as_of_date}.json"
        payload = self._read_json(path, fallback={})
        raw_lists = payload.get("lists", []) if isinstance(payload, dict) else []
        lists = []
        for item in raw_lists if isinstance(raw_lists, list) else []:
            if not isinstance(item, dict):
                continue
            rows = item.get("items", [])
            rows = rows if isinstance(rows, list) else []
            lists.append(
                {
                    "list_id": item.get("list_id", ""),
                    "list_name": item.get("list_name", ""),
                    "description": item.get("description", ""),
                    "sort_logic": item.get("sort_logic", ""),
                    "eligible_filters": item.get("eligible_filters", []),
                    "top_n": item.get("top_n", 0),
                    "source_universe_count": item.get("source_universe_count", 0),
                    "eligible_count": item.get("eligible_count", 0),
                    "excluded_count": item.get("excluded_count", 0),
                    "item_count": len(rows),
                    "items_preview": rows[:5],
                }
            )
        return {
            "ok": bool(lists),
            "message": "" if lists else "No multi-list output found. Please run generate_research_views.py first.",
            "date": as_of_date,
            "lists": self._sanitize_payload(lists),
            "disclaimer": API_DISCLAIMER,
        }

    def get_research_list_tiers(self) -> dict[str, Any]:
        source_lists = {
            list_id: self.get_research_list(list_id)
            for list_id in TIER_SOURCE_LIST_IDS
        }
        source_lists["insufficient_data"] = self.get_research_list(
            "insufficient_data"
        )
        return build_candidate_tiering_display(
            source_lists,
            CANDIDATE_TIERING_CONFIG,
        )

    def get_research_list(self, list_id: str) -> dict[str, Any]:
        normalized_id = list_id.strip()
        if normalized_id not in SUPPORTED_RESEARCH_LIST_IDS:
            return {
                "ok": False,
                "message": f"Unknown list_id: {normalized_id}.",
                "available_list_ids": sorted(SUPPORTED_RESEARCH_LIST_IDS),
                "date": self.latest_list_date(),
                "disclaimer": API_DISCLAIMER,
            }
        as_of_date = self.latest_list_date()
        if not as_of_date:
            return {
                "ok": False,
                "message": "No multi-list output found. Please run generate_research_views.py first.",
                "available_list_ids": sorted(SUPPORTED_RESEARCH_LIST_IDS),
                "date": None,
                "disclaimer": API_DISCLAIMER,
            }
        path = self.lists_dir / f"{normalized_id}_{as_of_date}.json"
        payload = self._read_json(path, fallback={})
        if not isinstance(payload, dict):
            return {
                "ok": False,
                "message": f"Research list output not found for {normalized_id}.",
                "available_list_ids": sorted(SUPPORTED_RESEARCH_LIST_IDS),
                "date": as_of_date,
                "disclaimer": API_DISCLAIMER,
            }
        items = payload.get("items", [])
        items = items if isinstance(items, list) else []
        result = {
            "ok": True,
            "message": "",
            "date": payload.get("as_of_date") or as_of_date,
            "list_id": payload.get("list_id", normalized_id),
            "list_name": payload.get("list_name", ""),
            "description": payload.get("description", ""),
            "sort_logic": payload.get("sort_logic", ""),
            "eligible_filters": payload.get("eligible_filters", []),
            "top_n": payload.get("top_n", 0),
            "source_universe_count": payload.get("source_universe_count", 0),
            "eligible_count": payload.get("eligible_count", 0),
            "excluded_count": payload.get("excluded_count", 0),
            "item_count": len(items),
            "items": self._sanitize_payload(items),
            "disclaimer": API_DISCLAIMER,
        }
        defensive_positioning = build_defensive_positioning_display(
            normalized_id,
            DEFENSIVE_POSITIONING_CONFIG,
        )
        if defensive_positioning is not None:
            result["defensive_positioning"] = defensive_positioning
        return result

    def get_labels(
        self,
        *,
        primary_type: str | None = None,
        research_action: str | None = None,
        risk_level: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        as_of_date = self.latest_label_date()
        rows = self._load_label_rows(as_of_date)
        filtered = rows
        if primary_type:
            filtered = [row for row in filtered if str(row.get("primary_type", "")) == primary_type]
        if research_action:
            filtered = [row for row in filtered if str(row.get("research_action", "")) == research_action]
        if risk_level:
            filtered = [row for row in filtered if str(row.get("risk_level", "")) == risk_level]
        if limit is not None:
            filtered = filtered[:limit]
        return {
            "ok": bool(as_of_date),
            "message": "" if rows else ("No label output found. Please run generate_research_views.py first." if as_of_date else NO_DAILY_OUTPUT_MESSAGE),
            "date": as_of_date,
            "item_count": len(filtered),
            "total_count": len(rows),
            "filters": {
                "primary_type": primary_type or "",
                "research_action": research_action or "",
                "risk_level": risk_level or "",
                "limit": limit,
            },
            "items": self._sanitize_payload(filtered),
            "label_counts": dict(Counter(str(row.get("research_label", "")) for row in filtered)),
            "primary_type_counts": dict(Counter(str(row.get("primary_type", "")) for row in filtered)),
            "risk_level_counts": dict(Counter(str(row.get("risk_level", "")) for row in filtered)),
            "research_action_counts": dict(Counter(str(row.get("research_action", "")) for row in filtered)),
            "disclaimer": API_DISCLAIMER,
        }

    def search_stocks(self, query: str) -> dict[str, Any]:
        query_text = query.strip()
        if not query_text:
            return {"ok": False, "message": "Query parameter q is required.", "query": query, "count": 0, "items": [], "disclaimer": API_DISCLAIMER}
        rows = self._load_stock_index_rows(self.latest_search_date())
        if not rows:
            rows = self._load_label_rows(self.latest_label_date())
        matches = [row for row in rows if self._symbol_or_name_matches(row, query_text)]
        if "." not in query_text and any(bool(row.get("is_stock", True)) for row in matches):
            matches = [row for row in matches if bool(row.get("is_stock", True))]
        return {
            "ok": True,
            "message": "" if matches else "No matching stock found in current static outputs.",
            "query": query_text,
            "count": len(matches),
            "items": [self._search_result_item(row) for row in matches],
            "disclaimer": API_DISCLAIMER,
        }

    def get_stock_research(self, symbol: str) -> dict[str, Any]:
        requested = symbol.strip()
        label_date = self.latest_label_date()
        if not label_date:
            return {
                "ok": False,
                "message": NO_DAILY_OUTPUT_MESSAGE,
                "date": None,
                "symbol": self._normalize_symbol_with_prefix(requested),
                "data_quality": "missing_outputs",
                "failed_symbol": None,
                "disclaimer": API_DISCLAIMER,
            }
        rows = self._load_label_rows(label_date)
        label_row = next((row for row in rows if self._symbol_matches(str(row.get("symbol", "")), requested)), None)
        stock_index_row = self._stock_index_row_for_symbol(requested)
        normalized = str(label_row.get("symbol")) if label_row else str(stock_index_row.get("symbol") or self._normalize_symbol_with_prefix(requested))
        failed = self._failed_symbol_detail(requested)
        if not label_row:
            if stock_index_row:
                return self._stock_index_research_detail(stock_index_row, failed=failed)
            if failed:
                return self._failed_symbol_research_detail(requested, failed, label_date)
            return {
                "ok": False,
                "message": "Symbol not found in current static research outputs.",
                "date": label_date,
                "symbol": normalized,
                "data_quality": "not_found",
                "failed_symbol": failed,
                "disclaimer": API_DISCLAIMER,
            }

        candidate = self._candidate_row_for_symbol(normalized)
        factors = self._factor_row_for_symbol(normalized)
        related_lists = self._related_lists_for_symbol(normalized)
        report = self._report_link(self.stock_report_file(normalized)) or {}
        score_breakdown = {
            "momentum_score": label_row.get("momentum_score", candidate.get("momentum_score")),
            "trend_score": label_row.get("trend_score", candidate.get("trend_score")),
            "relative_strength_score": label_row.get("relative_strength_score", candidate.get("relative_strength_score")),
            "risk_score": label_row.get("risk_score", candidate.get("risk_score")),
            "liquidity_score": label_row.get("liquidity_score", candidate.get("liquidity_score")),
        }
        return {
            "ok": True,
            "message": "",
            "date": label_row.get("as_of_date") or self.latest_label_date(),
            "symbol": normalized,
            "name": label_row.get("name", ""),
            "basic_info": {
                "symbol": normalized,
                "name": label_row.get("name", ""),
                "as_of_date": label_row.get("as_of_date", ""),
                "source_label": label_row.get("source_label", candidate.get("label", "")),
            },
            "current_rank": label_row.get("rank"),
            "total_score": label_row.get("total_score"),
            "score_breakdown": score_breakdown,
            "primary_type": label_row.get("primary_type", ""),
            "secondary_tags": label_row.get("secondary_tags", []),
            "research_action": label_row.get("research_action", ""),
            "confidence_level": label_row.get("confidence_level", ""),
            "risk_level": label_row.get("risk_level", ""),
            "confirmation_signals": label_row.get("confirmation_signals", []),
            "invalidation_signals": label_row.get("invalidation_signals", []),
            "label_reason": label_row.get("label_reason", ""),
            "factor_explanation": self.get_factor_summary_by_symbol(normalized),
            "evidence": {
                "positive": label_row.get("positive_evidence", candidate.get("positive_evidence", "")),
                "negative": label_row.get("negative_evidence", candidate.get("negative_evidence", "")),
            },
            "risk_flags": label_row.get("risk_flags", candidate.get("risk_flags", "")),
            "warnings": label_row.get("warnings", candidate.get("warnings", "")),
            "factor_row": self._sanitize_payload(factors),
            "report_links": report,
            "related_lists": related_lists,
            "data_quality": label_row.get("data_quality", ""),
            "disclaimer": API_DISCLAIMER,
        }

    def load_summary(self) -> dict[str, Any]:
        as_of_date = self.latest_daily_date()
        if not as_of_date:
            return {"ok": False, "message": NO_DAILY_OUTPUT_MESSAGE, "as_of_date": None, "summary": {}}
        path = self._daily_files(as_of_date)["summary"]
        if not path.exists():
            return {"ok": False, "message": f"Summary output not found for {as_of_date}.", "as_of_date": as_of_date, "summary": {}}
        payload = self._read_json(path, fallback={})
        summary = payload.get("summary", payload) if isinstance(payload, dict) else {}
        summary = self._sanitize_payload(summary)
        return {"ok": True, "message": "", "as_of_date": as_of_date, "summary": summary}

    def load_backtest(self) -> dict[str, Any]:
        as_of_date = self.latest_backtest_date()
        if not as_of_date:
            return {"ok": False, "message": "No backtest output found.", "as_of_date": None, "summary": {}, "metrics": {}}
        path = self.backtests_dir / BACKTEST_FILE_PATTERNS["summary"].format(date=as_of_date)
        payload = self._read_json(path, fallback={})
        summary = self._sanitize_payload(payload if isinstance(payload, dict) else {})
        metrics = summary.get("metrics", {}) if isinstance(summary.get("metrics", {}), dict) else {}
        return {"ok": True, "message": "", "as_of_date": as_of_date, "summary": summary, "metrics": metrics}

    def reports(self) -> dict[str, Any]:
        as_of_date = self.latest_daily_date()
        if not as_of_date:
            return {"ok": False, "message": NO_DAILY_OUTPUT_MESSAGE, "as_of_date": None, "daily": None, "backtest": None, "stocks": []}
        return {
            "ok": True,
            "message": "",
            "as_of_date": as_of_date,
            "daily": self._report_link(self.daily_report_file(as_of_date), daily=True),
            "backtest": self._report_link(self.backtest_report_file(), backtest=True),
            "stocks": [self._report_link(report) for report in self.get_available_stock_reports(as_of_date)],
        }

    def get_report_index(self) -> dict[str, Any]:
        latest_date = self.latest_daily_date()
        daily_reports = self._report_index_from_directory(
            self.reports_dir,
            r"^daily_report_(\d{4}-\d{2}-\d{2})\.(md|html)$",
            report_type="daily",
        )
        stock_reports = self._stock_report_index()
        backtest_reports = self._report_index_from_directory(
            self.backtests_dir,
            r"^backtest_report_(\d{4}-\d{2}-\d{2})\.(md|html)$",
            report_type="backtest",
        )
        found = bool(daily_reports or stock_reports or backtest_reports)
        return {
            "ok": found,
            "message": "" if found else NO_REPORTS_MESSAGE,
            "latest_date": latest_date,
            "daily_reports": daily_reports,
            "stock_reports": stock_reports,
            "backtest_reports": backtest_reports,
        }

    def get_output_health(self) -> dict[str, Any]:
        latest_date = self.latest_daily_date()
        workflow_summary = self.get_latest_workflow_summary()
        if not latest_date:
            return {
                "ok": False,
                "latest_date": None,
                "status": "missing",
                "required_files": [],
                "missing_files": [],
                "report_coverage": {"candidate_count": 0, "stock_report_count": 0, "missing_stock_report_count": 0, "missing_stock_reports": []},
                "failed_symbols_count": 0,
                "data_quality_warnings": [NO_DAILY_OUTPUT_MESSAGE],
                "blocking_issues": [NO_DAILY_OUTPUT_MESSAGE],
                "non_blocking_warnings": [],
                "workflow_summary": workflow_summary,
            }

        required_files = self._required_output_files(latest_date)
        missing_files = [item["path"] for item in required_files if not item["exists"]]
        candidates = self.load_candidates()
        candidate_symbols = [str(row.get("symbol", "")) for row in candidates.get("items", [])]
        stock_reports = self.get_available_stock_reports(latest_date)
        stock_report_symbols = {self._normalize_symbol(report.symbol or "") for report in stock_reports if report.html_path or report.markdown_path}
        missing_stock_reports = [
            symbol for symbol in candidate_symbols
            if self._normalize_symbol(symbol) not in stock_report_symbols
        ]
        failed = self.get_failed_symbols()
        quality = self.get_data_quality_summary()
        blocking_issues = [path for path in missing_files if "\\daily\\" in path or "/daily/" in path]
        status = "ok"
        if blocking_issues:
            status = "missing"
        elif missing_files or failed["count"] or quality["warnings"]:
            status = "warning"
        return {
            "ok": status != "missing",
            "latest_date": latest_date,
            "status": status,
            "required_files": required_files,
            "missing_files": missing_files,
            "report_coverage": {
                "candidate_count": len(candidate_symbols),
                "stock_report_count": len(stock_report_symbols),
                "missing_stock_report_count": len(missing_stock_reports),
                "missing_stock_reports": missing_stock_reports,
            },
            "failed_symbols_count": failed["count"],
            "data_quality_warnings": quality["warnings"],
            "blocking_issues": blocking_issues,
            "non_blocking_warnings": self._non_blocking_warnings(missing_files, missing_stock_reports, failed, quality),
            "workflow_summary": workflow_summary,
        }

    def get_latest_workflow_summary(self) -> dict[str, Any]:
        latest_date = self.latest_workflow_date()
        if not latest_date:
            return {"ok": False, "message": "No workflow summary found.", "latest_date": None, "summary": None}
        path = self.outputs_dir / "workflow" / f"workflow_summary_{latest_date}.json"
        payload = self._read_json(path, fallback={})
        if not isinstance(payload, dict):
            payload = {}
        return {
            "ok": bool(payload),
            "message": "" if payload else "Workflow summary could not be read.",
            "latest_date": latest_date,
            "summary": self._sanitize_payload(payload),
            "path": str(path),
        }

    def get_failed_symbols(self) -> dict[str, Any]:
        latest_date = self.latest_daily_date()
        if not latest_date:
            return {"ok": True, "latest_date": None, "count": 0, "items": []}
        files = [
            ("pipeline", self.outputs_dir / "errors" / f"failed_symbols_{latest_date}.csv"),
            ("cache_prewarm", self.outputs_dir / "cache" / f"cache_prewarm_errors_{latest_date}.csv"),
        ]
        items: list[dict[str, Any]] = []
        for source, path in files:
            for row in self._read_csv_rows(path):
                items.append(
                    {
                        "source": source,
                        "symbol": row.get("symbol", ""),
                        "name": row.get("name", ""),
                        "error_type": row.get("error_type", ""),
                        "error_message": row.get("error_message") or row.get("error", ""),
                        "can_retry": row.get("can_retry", ""),
                        "path": str(path),
                    }
                )
        return {"ok": True, "latest_date": latest_date, "count": len(items), "items": self._sanitize_payload(items)}

    def get_data_quality_summary(self) -> dict[str, Any]:
        latest_date = self.latest_daily_date()
        if not latest_date:
            return {
                "ok": False,
                "latest_date": None,
                "fetch_error_count": 0,
                "error_type_counts": {},
                "warnings": [NO_DAILY_OUTPUT_MESSAGE],
                "summary": {},
            }
        daily_summary = self.load_summary().get("summary", {})
        cache_summary = self._read_json(self.outputs_dir / "cache" / f"cache_prewarm_summary_{latest_date}.json", fallback={})
        error_type_counts: dict[str, Any] = {}
        for payload in [daily_summary, cache_summary if isinstance(cache_summary, dict) else {}]:
            counts = payload.get("error_type_counts", {})
            if isinstance(counts, dict):
                for key, value in counts.items():
                    error_type_counts[key] = error_type_counts.get(key, 0) + self._number(value)
        warnings: list[str] = []
        for key in ["warnings", "data_quality_warnings"]:
            value = daily_summary.get(key, [])
            if isinstance(value, list):
                warnings.extend(str(item) for item in value)
        for key in [
            "listing_date_missing",
            "missing_liquidity_data",
            "non_numeric_market_data",
            "empty_market_data",
            "missing_required_columns",
            "invalid_price_data",
        ]:
            if key in error_type_counts or key in warnings:
                warnings.append(key)
        fetch_error_count = int(self._number(daily_summary.get("fetch_error_count")) + self._number(cache_summary.get("error_count") if isinstance(cache_summary, dict) else 0))
        return {
            "ok": True,
            "latest_date": latest_date,
            "fetch_error_count": fetch_error_count,
            "error_type_counts": error_type_counts,
            "warnings": sorted(set(warnings)),
            "summary": {
                "daily": daily_summary,
                "cache": cache_summary if isinstance(cache_summary, dict) else {},
            },
        }

    def get_guide(self) -> dict[str, Any]:
        return {
            "ok": True,
            "recommended_workflow": [
                "预热缓存",
                "生成每日候选股",
                "生成研究报告",
                "运行回测",
                "启动 Dashboard",
                "查看输出健康检查",
            ],
            "commands": {
                "One-click daily workflow": [
                    r"python backend\scripts\run_daily_workflow.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --limit 50 --top-n 10 --benchmark CSI300 --cache-dir data\cache\daily-use --output-dir outputs",
                ],
                "缓存预热": [
                    '$env:HTTP_PROXY="http://127.0.0.1:8668"',
                    '$env:HTTPS_PROXY="http://127.0.0.1:8668"',
                    r"python backend\scripts\prewarm_market_cache.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --include-lookback-days 120 --limit 50 --batch-size 10 --cache-dir data\cache\phase1-final-smoke --output-dir outputs\cache --sleep-seconds 0.5 --retry 1 --resume",
                ],
                "每日研究 pipeline": [
                    r"python backend\scripts\run_daily_research.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --benchmark CSI300 --top-n 10 --limit 50 --cache-dir data\cache\phase1-final-smoke --output-dir outputs\daily --retry 1",
                ],
                "生成研究报告": [
                    r"python backend\scripts\generate_research_report.py --candidates outputs\daily\candidates_2024-01-31.json --summary outputs\daily\summary_2024-01-31.json --factors outputs\daily\factors_2024-01-31.json --factor-explanations outputs\daily\factor_explanations_2024-01-31.json --output-dir outputs\reports",
                ],
                "运行回测": [
                    r"python backend\scripts\run_backtest.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --lookback-days 120 --rebalance-frequency monthly --top-n 5 --benchmark CSI300 --limit 50 --cache-dir data\cache\phase1-final-smoke --output-dir outputs\backtests --transaction-cost-bps 10 --retry 1",
                ],
                "启动 Dashboard": [
                    r"python backend\scripts\run_api.py --outputs-dir outputs --host 127.0.0.1 --port 8000",
                ],
                "运行测试": [
                    r"python -m unittest discover -s backend\tests",
                ],
            },
            "output_paths": [
                "outputs/daily/candidates_YYYY-MM-DD.json",
                "outputs/daily/summary_YYYY-MM-DD.json",
                "outputs/daily/factors_YYYY-MM-DD.json",
                "outputs/daily/factor_explanations_YYYY-MM-DD.json",
                "outputs/reports/daily_report_YYYY-MM-DD.md/html",
                "outputs/reports/stocks/*.md/html",
                "outputs/backtests/backtest_summary_YYYY-MM-DD.json",
                "outputs/backtests/backtest_report_YYYY-MM-DD.md/html",
                "outputs/cache/cache_prewarm_summary_YYYY-MM-DD.json",
                "outputs/errors/failed_symbols_YYYY-MM-DD.csv",
                "outputs/workflow/workflow_summary_YYYY-MM-DD.json",
                "outputs/workflow/workflow_log_YYYY-MM-DD.txt",
            ],
            "navigation": [
                {"path": "/", "label": "首页 Dashboard"},
                {"path": "/compare", "label": "候选股横向对比"},
                {"path": "/reports", "label": "报告中心"},
                {"path": "/health/outputs", "label": "输出健康检查"},
                {"path": "/guide", "label": "运行指引"},
                {"path": "/stocks/{symbol}", "label": "单股详情页"},
                {"path": "/reports/daily", "label": "每日报告"},
                {"path": "/reports/stocks/{symbol}", "label": "单股报告"},
            ],
            "troubleshooting": [
                "如果页面提示 No daily research output found，先运行 run_daily_research.py。",
                "如果报告缺失，先运行 generate_research_report.py。",
                "如果回测缺失，先运行 run_backtest.py。",
                "如果 BaoStock 慢，先运行 prewarm_market_cache.py 并使用 resume。",
                "如果看到 pandas/numexpr warning，当前不影响运行。",
                "如果 GitHub 网络失败，确认代理 127.0.0.1:8668 可用。",
                "如果 outputs 健康检查有 missing files，按页面提示补跑对应命令。",
                "如需本地一键日常流程，先用 run_daily_workflow.py --dry-run 预览，再执行正式 workflow。",
            ],
            "phase_status": [
                "Phase 1：已完成并合并 main",
                "Phase 2：Dashboard 本地只读版本开发中",
                "当前边界：只读 outputs，不拉数、不重算、不回测",
            ],
            "disclaimers": ["仅为个人研究辅助，不构成投资建议。"],
        }

    def get_daily_report(self, format: str = "json") -> dict[str, Any]:
        return self._format_report_content(self.read_report(self.daily_report_file()), format=format)

    def get_stock_report(self, symbol: str, format: str = "json") -> dict[str, Any]:
        content = self.read_report(self.stock_report_file(symbol))
        if not content["ok"]:
            content["message"] = NO_STOCK_REPORT_MESSAGE
        return self._format_report_content(content, format=format)

    def get_available_stock_reports(self, as_of_date: str | None = None) -> list[ReportFile]:
        date = as_of_date or self.latest_daily_date()
        if not date or not self.stock_reports_dir.exists():
            return []
        reports: dict[str, dict[str, Path]] = {}
        for path in self.stock_reports_dir.glob(f"*_{date}.*"):
            match = re.match(rf"^(.+)_{re.escape(date)}\.(md|html)$", path.name)
            if not match:
                continue
            symbol, suffix = match.groups()
            reports.setdefault(symbol, {})[suffix] = path
        return [
            ReportFile(symbol=symbol, as_of_date=date, markdown_path=paths.get("md"), html_path=paths.get("html"))
            for symbol, paths in sorted(reports.items())
        ]

    def daily_report_file(self, as_of_date: str | None = None) -> ReportFile:
        date = as_of_date or self.latest_daily_date()
        if not date:
            return ReportFile(symbol=None, as_of_date=None, markdown_path=None, html_path=None)
        return ReportFile(
            symbol=None,
            as_of_date=date,
            markdown_path=self.reports_dir / f"daily_report_{date}.md",
            html_path=self.reports_dir / f"daily_report_{date}.html",
        )

    def backtest_report_file(self) -> ReportFile:
        date = self.latest_backtest_date()
        if not date:
            return ReportFile(symbol=None, as_of_date=None, markdown_path=None, html_path=None)
        return ReportFile(
            symbol=None,
            as_of_date=date,
            markdown_path=self.backtests_dir / BACKTEST_FILE_PATTERNS["markdown"].format(date=date),
            html_path=self.backtests_dir / BACKTEST_FILE_PATTERNS["html"].format(date=date),
        )

    def stock_report_file(self, symbol: str) -> ReportFile:
        normalized = self._normalize_symbol(symbol)
        for report in self.get_available_stock_reports():
            if self._normalize_symbol(report.symbol or "") == normalized:
                return report
        return ReportFile(symbol=normalized, as_of_date=self.latest_daily_date(), markdown_path=None, html_path=None)

    def read_report(self, report: ReportFile) -> dict[str, Any]:
        markdown = self._sanitize_text(self._read_text(report.markdown_path)) if report.markdown_path else None
        html = self._sanitize_text(self._read_text(report.html_path)) if report.html_path else None
        return {
            "ok": bool(markdown or html),
            "message": "" if (markdown or html) else "Report output not found.",
            "symbol": report.symbol,
            "as_of_date": report.as_of_date,
            "markdown": markdown,
            "html": html,
            "markdown_path": str(report.markdown_path) if report.markdown_path and report.markdown_path.exists() else None,
            "html_path": str(report.html_path) if report.html_path and report.html_path.exists() else None,
        }

    def _label_file(self, as_of_date: str | None) -> Path | None:
        if not as_of_date:
            return None
        return self.labels_dir / f"candidate_labels_{as_of_date}.json"

    def _load_label_rows(self, as_of_date: str | None) -> list[dict[str, Any]]:
        path = self._label_file(as_of_date)
        if not path or not path.exists():
            return []
        payload = self._read_json(path, fallback=[])
        rows = payload.get("items", payload) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return []
        return [row for row in self._sanitize_payload(rows) if isinstance(row, dict)]

    def _stock_index_file(self, as_of_date: str | None) -> Path | None:
        if not as_of_date:
            return None
        return self.search_dir / f"stock_index_{as_of_date}.json"

    def _load_stock_index_rows(self, as_of_date: str | None) -> list[dict[str, Any]]:
        path = self._stock_index_file(as_of_date)
        if not path or not path.exists():
            return []
        payload = self._read_json(path, fallback={})
        rows = payload.get("items", payload) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return []
        return [row for row in self._sanitize_payload(rows) if isinstance(row, dict)]

    def _candidate_row_for_symbol(self, symbol: str) -> dict[str, Any]:
        candidates = self.load_candidates()
        for row in candidates.get("items", []):
            if self._symbol_matches(str(row.get("symbol", "")), symbol):
                return row
        return {}

    def _factor_row_for_symbol(self, symbol: str) -> dict[str, Any]:
        as_of_date = self.latest_daily_date()
        if not as_of_date:
            return {}
        path = self._daily_files(as_of_date).get("factors")
        payload = self._read_json(path, fallback=[]) if path else []
        rows = payload.get("factors", payload) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return {}
        for row in rows:
            if isinstance(row, dict) and self._symbol_matches(str(row.get("symbol", "")), symbol):
                return row
        return {}

    def _stock_index_row_for_symbol(self, symbol: str) -> dict[str, Any]:
        for row in self._load_stock_index_rows(self.latest_search_date()):
            if self._symbol_matches(str(row.get("symbol", "")), symbol):
                return row
        return {}

    def _related_lists_for_symbol(self, symbol: str) -> list[dict[str, Any]]:
        as_of_date = self.latest_list_date()
        if not as_of_date or not self.lists_dir.exists():
            return []
        related: list[dict[str, Any]] = []
        for list_id in sorted(SUPPORTED_RESEARCH_LIST_IDS):
            payload = self._read_json(self.lists_dir / f"{list_id}_{as_of_date}.json", fallback={})
            if not isinstance(payload, dict):
                continue
            items = payload.get("items", [])
            if not isinstance(items, list):
                continue
            for index, item in enumerate(items, start=1):
                if isinstance(item, dict) and self._symbol_matches(str(item.get("symbol", "")), symbol):
                    related.append(
                        {
                            "list_id": list_id,
                            "list_name": payload.get("list_name", ""),
                            "position": index,
                            "item_count": len(items),
                        }
                    )
                    break
        return related

    def _failed_symbol_detail(self, symbol: str) -> dict[str, Any] | None:
        for row in self.get_failed_symbols().get("items", []):
            if isinstance(row, dict) and self._symbol_matches(str(row.get("symbol", "")), symbol):
                return row
        return None

    def _search_result_item(self, row: dict[str, Any]) -> dict[str, Any]:
        symbol = str(row.get("symbol", ""))
        return {
            "symbol": symbol,
            "code": row.get("code", self._symbol_code(symbol)),
            "name": row.get("name", ""),
            "rank": row.get("rank", 0),
            "total_score": row.get("total_score", 0),
            "research_status": row.get("research_status", row.get("primary_type", "")),
            "primary_type": row.get("primary_type", ""),
            "secondary_tags": row.get("secondary_tags", []),
            "research_action": row.get("research_action", ""),
            "confidence_level": row.get("confidence_level", ""),
            "risk_level": row.get("risk_level", ""),
            "in_any_list": bool(row.get("in_any_list", False)),
            "related_lists": row.get("related_lists", []),
            "data_quality": row.get("data_quality", ""),
            "has_report": self._has_report_link(row.get("report_links")) or self._has_report_link(self._report_link(self.stock_report_file(symbol))),
            "report_links": row.get("report_links") or self._report_link(self.stock_report_file(symbol)) or {},
            "message": row.get("message", ""),
        }

    def _stock_index_research_detail(self, row: dict[str, Any], *, failed: dict[str, Any] | None) -> dict[str, Any]:
        symbol = str(row.get("symbol", ""))
        is_stock = bool(row.get("is_stock", True))
        factors = self._factor_row_for_symbol(symbol) if is_stock else {}
        report = row.get("report_links") or self._report_link(self.stock_report_file(symbol)) or {}
        score_breakdown = {
            "momentum_score": row.get("momentum_score", factors.get("momentum_score", "")),
            "trend_score": row.get("trend_score", factors.get("trend_score", "")),
            "relative_strength_score": row.get("relative_strength_score", factors.get("relative_strength_score", "")),
            "risk_score": row.get("risk_score", factors.get("risk_score", "")),
            "liquidity_score": row.get("liquidity_score", factors.get("liquidity_score", "")),
        }
        return {
            "ok": True,
            "message": row.get("message", ""),
            "date": self.latest_search_date(),
            "symbol": symbol,
            "name": row.get("name", ""),
            "basic_info": {
                "symbol": symbol,
                "name": row.get("name", ""),
                "as_of_date": self.latest_search_date() or "",
                "source_label": row.get("research_status", ""),
                "instrument_type": row.get("instrument_type", ""),
            },
            "current_rank": row.get("rank", 0),
            "total_score": row.get("total_score", 0),
            "score_breakdown": score_breakdown,
            "primary_type": row.get("primary_type", row.get("research_status", "")),
            "secondary_tags": row.get("secondary_tags", []),
            "research_action": row.get("research_action", ""),
            "confidence_level": row.get("confidence_level", ""),
            "risk_level": row.get("risk_level", ""),
            "confirmation_signals": row.get("confirmation_signals", []),
            "invalidation_signals": row.get("invalidation_signals", []),
            "label_reason": row.get("message", ""),
            "factor_explanation": self.get_factor_summary_by_symbol(symbol) if is_stock else {},
            "evidence": {"positive": "", "negative": row.get("excluded_reason", "")},
            "risk_flags": "",
            "warnings": row.get("excluded_reason", ""),
            "factor_row": self._sanitize_payload(factors),
            "report_links": report,
            "related_lists": row.get("related_lists", []),
            "data_quality": row.get("data_quality", ""),
            "failed_symbol": failed,
            "is_stock": is_stock,
            "instrument_type": row.get("instrument_type", ""),
            "excluded_reason": row.get("excluded_reason", ""),
            "disclaimer": API_DISCLAIMER,
        }

    def _failed_symbol_research_detail(self, requested: str, failed: dict[str, Any], label_date: str | None) -> dict[str, Any]:
        normalized = self._normalize_symbol_with_prefix(requested)
        return {
            "ok": True,
            "message": "Symbol exists in failed_symbols and has insufficient data.",
            "date": label_date,
            "symbol": normalized,
            "name": failed.get("name", ""),
            "basic_info": {"symbol": normalized, "name": failed.get("name", ""), "as_of_date": label_date or "", "source_label": "数据不足"},
            "current_rank": 0,
            "total_score": 0,
            "score_breakdown": {},
            "primary_type": "数据不足",
            "secondary_tags": [],
            "research_action": "数据补充后再评估",
            "confidence_level": "低",
            "risk_level": "不明",
            "confirmation_signals": [],
            "invalidation_signals": [],
            "label_reason": "当前仅存在失败记录，未形成完整因子与榜单输出。",
            "factor_explanation": {},
            "evidence": {"positive": "", "negative": failed.get("error_message", failed.get("error", ""))},
            "risk_flags": "",
            "warnings": failed.get("error_type", ""),
            "factor_row": {},
            "report_links": {},
            "related_lists": [],
            "data_quality": "failed_symbol",
            "failed_symbol": failed,
            "disclaimer": API_DISCLAIMER,
        }

    def _symbol_or_name_matches(self, row: dict[str, Any], query: str) -> bool:
        symbol = str(row.get("symbol", ""))
        name = str(row.get("name", ""))
        return self._symbol_matches(symbol, query) or query.lower() in name.lower()

    def _symbol_matches(self, symbol: str, query: str) -> bool:
        normalized_symbol = self._normalize_symbol(symbol)
        normalized_query = self._normalize_symbol(query)
        if normalized_symbol == normalized_query:
            return True
        if "." in normalized_query:
            return False
        return self._symbol_code(normalized_symbol) == self._symbol_code(normalized_query)

    def _symbol_code(self, symbol: str) -> str:
        text = self._normalize_symbol(symbol)
        if "." in text:
            return text.split(".")[-1]
        return text

    def _normalize_symbol_with_prefix(self, symbol: str) -> str:
        text = self._normalize_symbol(symbol)
        if "." in text or not re.fullmatch(r"\d{6}", text):
            return text
        if text.startswith("6"):
            return f"sh.{text}"
        if text.startswith(("0", "3")):
            return f"sz.{text}"
        if text.startswith(("4", "8")):
            return f"bj.{text}"
        return text

    def _daily_files(self, as_of_date: str | None) -> dict[str, Path]:
        if not as_of_date:
            return {}
        return {key: self.daily_dir / pattern.format(date=as_of_date) for key, pattern in DAILY_FILE_PATTERNS.items()}

    def _required_output_files(self, as_of_date: str) -> list[dict[str, Any]]:
        paths = [
            self.daily_dir / f"candidates_{as_of_date}.json",
            self.daily_dir / f"summary_{as_of_date}.json",
            self.daily_dir / f"factors_{as_of_date}.json",
            self.daily_dir / f"factor_explanations_{as_of_date}.json",
            self.reports_dir / f"daily_report_{as_of_date}.md",
            self.reports_dir / f"daily_report_{as_of_date}.html",
            self.backtests_dir / f"backtest_summary_{as_of_date}.json",
            self.backtests_dir / f"backtest_report_{as_of_date}.md",
            self.backtests_dir / f"backtest_report_{as_of_date}.html",
        ]
        return [
            {"path": str(path), "exists": path.exists(), "status": "ok" if path.exists() else "missing"}
            for path in paths
        ]

    def _report_index_from_directory(self, directory: Path, pattern: str, *, report_type: str) -> list[dict[str, Any]]:
        if not directory.exists():
            return []
        grouped: dict[str, dict[str, Any]] = {}
        regex = re.compile(pattern)
        for path in directory.iterdir():
            match = regex.match(path.name)
            if not match:
                continue
            date, suffix = match.groups()
            item = grouped.setdefault(date, {"type": report_type, "as_of_date": date, "markdown_path": None, "html_path": None, "formats": []})
            item["formats"].append("Markdown" if suffix == "md" else "HTML")
            item["markdown_path" if suffix == "md" else "html_path"] = str(path)
        return sorted(grouped.values(), key=lambda item: item["as_of_date"], reverse=True)

    def _stock_report_index(self) -> list[dict[str, Any]]:
        if not self.stock_reports_dir.exists():
            return []
        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        regex = re.compile(r"^(.+)_(\d{4}-\d{2}-\d{2})\.(md|html)$")
        for path in self.stock_reports_dir.iterdir():
            match = regex.match(path.name)
            if not match:
                continue
            symbol, date, suffix = match.groups()
            item = grouped.setdefault(
                (symbol, date),
                {"type": "stock", "symbol": symbol, "as_of_date": date, "markdown_path": None, "html_path": None, "formats": []},
            )
            item["formats"].append("Markdown" if suffix == "md" else "HTML")
            item["markdown_path" if suffix == "md" else "html_path"] = str(path)
            item["page_url"] = f"/reports/stocks/{symbol}"
        return sorted(grouped.values(), key=lambda item: (item["as_of_date"], item["symbol"]), reverse=True)

    def _read_csv_rows(self, path: Path) -> list[dict[str, str]]:
        if not path.exists():
            return []
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                return [dict(row) for row in csv.DictReader(handle)]
        except OSError:
            return []

    def _non_blocking_warnings(
        self,
        missing_files: list[str],
        missing_stock_reports: list[str],
        failed: dict[str, Any],
        quality: dict[str, Any],
    ) -> list[str]:
        warnings: list[str] = []
        if missing_files:
            warnings.append(f"missing_files:{len(missing_files)}")
        if missing_stock_reports:
            warnings.append(f"missing_stock_reports:{len(missing_stock_reports)}")
        if failed["count"]:
            warnings.append(f"failed_symbols:{failed['count']}")
        warnings.extend(str(item) for item in quality.get("warnings", []))
        return sorted(set(warnings))

    def _empty_candidates(self, *, as_of_date: str | None = None) -> dict[str, Any]:
        return {
            "ok": False,
            "message": NO_DAILY_OUTPUT_MESSAGE,
            "as_of_date": as_of_date,
            "count": 0,
            "total_count": 0,
            "filters": {},
            "items": [],
            "label_distribution": {},
            "high_confidence": [],
        }

    def _report_link(self, report: ReportFile, *, daily: bool = False, backtest: bool = False) -> dict[str, Any] | None:
        if not report.as_of_date:
            return None
        route = "/api/reports/daily" if daily else f"/api/reports/stocks/{report.symbol}"
        page_route = "/reports/daily" if daily else f"/reports/stocks/{report.symbol}"
        if backtest:
            route = None
            page_route = None
        return {
            "symbol": report.symbol,
            "as_of_date": report.as_of_date,
            "markdown_path": str(report.markdown_path) if report.markdown_path and report.markdown_path.exists() else None,
            "html_path": str(report.html_path) if report.html_path and report.html_path.exists() else None,
            "markdown_url": f"{route}?format=markdown" if route and report.markdown_path and report.markdown_path.exists() else None,
            "html_url": f"{route}?format=html" if route and report.html_path and report.html_path.exists() else None,
            "page_url": page_route if page_route and ((report.markdown_path and report.markdown_path.exists()) or (report.html_path and report.html_path.exists())) else None,
        }

    def _has_report_link(self, value: Any) -> bool:
        return isinstance(value, dict) and bool(value.get("markdown_path") or value.get("html_path") or value.get("markdown_url") or value.get("html_url") or value.get("page_url"))

    def _format_report_content(self, content: dict[str, Any], *, format: str) -> dict[str, Any]:
        if format == "html":
            return {**content, "content": content.get("html")}
        if format == "markdown":
            return {**content, "content": content.get("markdown")}
        return content

    def _dates_from_files(self, directory: Path, pattern: str) -> set[str]:
        if not directory.exists():
            return set()
        regex = re.compile(pattern)
        dates: set[str] = set()
        for path in directory.iterdir():
            match = regex.match(path.name)
            if match:
                dates.add(match.group(1))
        return dates

    def _read_json(self, path: Path, *, fallback: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return fallback

    def _read_text(self, path: Path | None) -> str | None:
        if not path or not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8-sig")
        except OSError:
            return None

    def _sanitize_payload(self, value: Any) -> Any:
        if isinstance(value, str):
            return self._sanitize_text(value)
        if isinstance(value, list):
            return [self._sanitize_payload(item) for item in value]
        if isinstance(value, dict):
            return {key: self._sanitize_payload(item) for key, item in value.items()}
        return value

    def _sanitize_text(self, text: str | None) -> str | None:
        if text is None:
            return None
        sanitized = text
        for term in PROHIBITED_TERMS:
            sanitized = sanitized.replace(term, PROHIBITED_REPLACEMENT)
        return sanitized

    def _normalize_symbol(self, symbol: str) -> str:
        return symbol.strip().lower()

    def _score_sort_key(self, row: dict[str, Any]) -> float:
        try:
            return float(row.get("total_score", 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    def _candidate_filter_error(self, *, sort_by: str, sort_order: str, limit: int | None) -> str:
        if sort_by not in SORTABLE_CANDIDATE_FIELDS:
            return "Invalid sort_by. Supported fields: " + ", ".join(sorted(SORTABLE_CANDIDATE_FIELDS))
        if sort_order not in {"asc", "desc"}:
            return "Invalid sort_order. Supported values: asc, desc."
        if limit is not None and limit < 1:
            return "Invalid limit. It must be greater than 0."
        return ""

    def _filter_candidate_rows(
        self,
        rows: list[dict[str, Any]],
        *,
        label: str | None,
        min_score: float | None,
        max_score: float | None,
        min_confidence: float | None,
    ) -> list[dict[str, Any]]:
        filtered = rows
        if label:
            filtered = [row for row in filtered if str(row.get("label", "")) == label]
        if min_score is not None:
            filtered = [row for row in filtered if self._number(row.get("total_score")) >= min_score]
        if max_score is not None:
            filtered = [row for row in filtered if self._number(row.get("total_score")) <= max_score]
        if min_confidence is not None:
            filtered = [row for row in filtered if self._number(row.get("confidence")) >= min_confidence]
        return filtered

    def _sort_candidate_rows(self, rows: list[dict[str, Any]], *, sort_by: str, sort_order: str) -> list[dict[str, Any]]:
        reverse = sort_order == "desc"
        return sorted(rows, key=lambda row: self._number(row.get(sort_by)), reverse=reverse)

    def _number(self, value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    def _factor_group_key(self, value: str) -> str:
        text = value.lower()
        if "relative" in text or "strength" in text:
            return "relative_strength"
        if "momentum" in text:
            return "momentum"
        if "trend" in text or "ma" in text:
            return "trend"
        if "risk" in text or "drawdown" in text or "volatility" in text:
            return "risk"
        if "liquidity" in text or "amount" in text or "volume" in text:
            return "liquidity"
        return text or "other"

    def _normalize_factor_group(self, value: str) -> str:
        text = value.strip()
        return FACTOR_GROUP_ALIASES.get(text, FACTOR_GROUP_ALIASES.get(text.lower(), text.lower()))

    def _factor_group_matrix_row(self, candidate: dict[str, Any]) -> dict[str, Any]:
        symbol = str(candidate.get("symbol", ""))
        summary = candidate.get("factor_summary")
        if not isinstance(summary, dict):
            summary = self.get_factor_summary_by_symbol(symbol)
        groups = {row.get("factor_group"): row for row in summary.get("items", []) if isinstance(row, dict)}
        row = {
            "symbol": symbol,
            "name": candidate.get("name", ""),
            "label": candidate.get("label", ""),
            "total_score": candidate.get("total_score", ""),
            "detail_link": f"/stocks/{symbol}",
            "report_link": f"/reports/stocks/{symbol}",
            "factor_warning": "" if summary.get("ok") else NO_FACTOR_EXPLANATIONS_MESSAGE,
        }
        for group_key in FACTOR_GROUP_LABELS:
            group = groups.get(group_key, {})
            row[f"{group_key}_contribution"] = self._number(group.get("contribution"))
            row[f"{group_key}_normalized_score"] = self._number(group.get("normalized_score"))
        positives = summary.get("positive_factors", []) if isinstance(summary.get("positive_factors", []), list) else []
        risks = summary.get("risk_factors", []) if isinstance(summary.get("risk_factors", []), list) else []
        row["top_positive_factor_group"] = self._group_display(positives[0]) if positives else ""
        row["top_risk_factor_group"] = self._group_display(risks[0]) if risks else ""
        return row

    def _group_display(self, row: dict[str, Any]) -> str:
        return str(row.get("display_name") or FACTOR_GROUP_LABELS.get(str(row.get("factor_group", "")), row.get("factor_group", "")))

    def _score_explanation(self, summaries: list[dict[str, Any]], risks: list[dict[str, Any]]) -> str:
        leaders = [str(row.get("display_name", "")) for row in summaries[:2] if row.get("display_name")]
        if not leaders:
            return "当前候选排序来自综合评分，仍需结合后续数据复核。该结论仅用于个人研究排序，不构成投资建议。"
        risk_text = "风险分没有触发重大扣分" if not risks else "仍需关注风险相关因子的变化"
        return f"该股票当前综合分主要由{'和'.join(leaders)}贡献，{risk_text}。该结论仅用于个人研究排序，不构成投资建议。"
