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

    def load_candidates(self) -> dict[str, Any]:
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
        label_distribution = dict(Counter(str(row.get("label", "")) for row in rows))
        high_confidence = [row for row in rows if row.get("label") == RESEARCH_LABELS[0]]
        return {
            "ok": True,
            "message": "",
            "as_of_date": as_of_date,
            "count": len(rows),
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
                    "report": self._report_link(self.stock_report_file(normalized)),
                }
        return {
            "ok": False,
            "message": f"No candidate found for symbol: {normalized}.",
            "as_of_date": candidates["as_of_date"],
            "symbol": normalized,
            "item": None,
            "factor_explanations": [],
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
