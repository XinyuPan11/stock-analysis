from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.api.app import create_app


PROHIBITED_TERMS = ["买入", "卖出", "强烈买入", "建议买入"]


class ApiTests(unittest.TestCase):
    def test_health_returns_ok(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_candidates_returns_rows_when_file_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/candidates")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["as_of_date"], "2024-01-31")
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["items"][0]["symbol"], "sh.600016")
        self.assertEqual(payload["label_distribution"]["高置信候选"], 1)

    def test_summary_returns_summary_when_file_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/summary")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["summary"]["provider"], "baostock")
        self.assertEqual(payload["summary"]["scored_count"], 2)

    def test_missing_outputs_do_not_crash_api(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            client = TestClient(create_app(outputs_dir=temp_dir))

            latest = client.get("/api/latest")
            candidates = client.get("/api/candidates")
            summary = client.get("/api/summary")

        self.assertEqual(latest.status_code, 200)
        self.assertFalse(latest.json()["ok"])
        self.assertIn("No daily research output found", latest.json()["message"])
        self.assertEqual(candidates.status_code, 200)
        self.assertEqual(candidates.json()["items"], [])
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["summary"], {})

    def test_dashboard_home_returns_html(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        text = response.text
        self.assertIn("A 股个人研究终端", text)
        self.assertIn("最新数据日期", text)
        self.assertIn("Top N 候选股", text)
        self.assertIn("标签分布", text)
        self.assertIn("高置信候选区", text)
        self.assertIn("风险提示区", text)
        self.assertIn("回测核心指标", text)
        self.assertIn("仅为个人研究辅助，不构成投资建议", text)

    def test_page_and_api_do_not_contain_deterministic_trading_terms(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            texts = [
                client.get("/").text,
                json.dumps(client.get("/api/latest").json(), ensure_ascii=False),
                json.dumps(client.get("/api/candidates").json(), ensure_ascii=False),
                json.dumps(client.get("/api/summary").json(), ensure_ascii=False),
                json.dumps(client.get("/api/backtest").json(), ensure_ascii=False),
                json.dumps(client.get("/api/reports").json(), ensure_ascii=False),
                client.get("/api/reports/daily?format=markdown").text,
                client.get("/api/reports/stocks/sh.600016?format=html").text,
            ]

        combined = "\n".join(texts)
        for term in PROHIBITED_TERMS:
            self.assertNotIn(term, combined)


def _write_outputs(root: str) -> None:
    outputs = Path(root)
    daily = outputs / "daily"
    reports = outputs / "reports"
    stock_reports = reports / "stocks"
    backtests = outputs / "backtests"
    daily.mkdir(parents=True)
    stock_reports.mkdir(parents=True)
    backtests.mkdir(parents=True)

    candidates = [
        {
            "rank": 1,
            "symbol": "sh.600016",
            "name": "民生银行",
            "as_of_date": "2024-01-31",
            "total_score": 91.2,
            "label": "高置信候选",
            "confidence": 0.92,
            "positive_evidence": "多项因子共振",
            "negative_evidence": "",
            "risk_flags": "",
            "warnings": "",
            "source": "baostock",
        },
        {
            "rank": 2,
            "symbol": "sh.600015",
            "name": "华夏银行",
            "as_of_date": "2024-01-31",
            "total_score": 82.0,
            "label": "候选关注",
            "confidence": 0.88,
            "positive_evidence": "趋势结构较强",
            "negative_evidence": "流动性仍需观察",
            "risk_flags": "",
            "warnings": "",
            "source": "baostock",
        },
    ]
    summary = {
        "as_of_date": "2024-01-31",
        "updated_at": "2024-02-01 08:00:00",
        "provider": "baostock",
        "benchmark": "CSI300",
        "start_date": "2023-01-01",
        "end_date": "2024-01-31",
        "universe_count": 5493,
        "filtered_count": 1,
        "attempted_count": 20,
        "successful_factor_count": 19,
        "scored_count": 2,
        "fetch_error_count": 0,
        "warnings": ["unit_warning"],
    }
    backtest = {
        "as_of_date": "2024-01-31",
        "metrics": {
            "total_return": 0.08,
            "net_total_return_after_cost": 0.06,
            "benchmark_total_return": -0.17,
            "excess_return": 0.23,
            "max_drawdown": -0.19,
            "sharpe_ratio": 0.39,
            "number_of_rebalances": 13,
            "average_holdings": 5,
        },
    }

    (daily / "candidates_2024-01-31.json").write_text(json.dumps(candidates, ensure_ascii=False), encoding="utf-8")
    (daily / "summary_2024-01-31.json").write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    (reports / "daily_report_2024-01-31.md").write_text("# Daily", encoding="utf-8")
    (reports / "daily_report_2024-01-31.html").write_text("<h1>Daily</h1>", encoding="utf-8")
    (stock_reports / "sh.600016_2024-01-31.md").write_text("# Stock", encoding="utf-8")
    (stock_reports / "sh.600016_2024-01-31.html").write_text("<h1>Stock</h1>", encoding="utf-8")
    (backtests / "backtest_summary_2024-01-31.json").write_text(json.dumps(backtest, ensure_ascii=False), encoding="utf-8")
    (backtests / "backtest_report_2024-01-31.md").write_text("# Backtest", encoding="utf-8")
    (backtests / "backtest_report_2024-01-31.html").write_text("<h1>Backtest</h1>", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
