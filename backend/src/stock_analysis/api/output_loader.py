from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

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

    def latest_daily_date(self) -> str | None:
        dates: set[str] = set()
        for prefix in ["candidates", "summary", "factors", "factor_explanations"]:
            dates.update(self._dates_from_files(self.daily_dir, rf"^{prefix}_(\d{{4}}-\d{{2}}-\d{{2}})\.json$"))
        return max(dates) if dates else None

    def latest_backtest_date(self) -> str | None:
        dates = self._dates_from_files(self.backtests_dir, r"^backtest_summary_(\d{4}-\d{2}-\d{2})\.json$")
        return max(dates) if dates else None

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

    def _daily_files(self, as_of_date: str | None) -> dict[str, Path]:
        if not as_of_date:
            return {}
        return {key: self.daily_dir / pattern.format(date=as_of_date) for key, pattern in DAILY_FILE_PATTERNS.items()}

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
            "page_url": page_route if page_route and (report.markdown_path or report.html_path) else None,
        }

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
