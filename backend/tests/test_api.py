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

    def test_candidate_detail_api_returns_single_stock(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/candidates/sh.600016")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["symbol"], "sh.600016")
        self.assertEqual(payload["item"]["name"], "民生银行")
        self.assertEqual(len(payload["factor_explanations"]), 2)
        self.assertIn("/reports/stocks/sh.600016", payload["report"]["page_url"])

    def test_factor_explanations_for_symbol_returns_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/factor-explanations/sh.600016")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["symbol"], "sh.600016")
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["items"][0]["factor_group"], "momentum_60d")

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

    def test_missing_outputs_do_not_crash_api_or_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            client = TestClient(create_app(outputs_dir=temp_dir))

            latest = client.get("/api/latest")
            candidates = client.get("/api/candidates")
            summary = client.get("/api/summary")
            home = client.get("/")
            stock_page = client.get("/stocks/sh.600016")
            daily_page = client.get("/reports/daily")

        self.assertEqual(latest.status_code, 200)
        self.assertFalse(latest.json()["ok"])
        self.assertIn("No daily research output found", latest.json()["message"])
        self.assertEqual(candidates.status_code, 200)
        self.assertEqual(candidates.json()["items"], [])
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["summary"], {})
        self.assertEqual(home.status_code, 200)
        self.assertIn("No daily research output found", home.text)
        self.assertEqual(stock_page.status_code, 404)
        self.assertIn("No daily research output found", stock_page.text)
        self.assertEqual(daily_page.status_code, 404)

    def test_dashboard_home_returns_enhanced_html(self) -> None:
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
        self.assertIn("/stocks/sh.600016", text)
        self.assertIn("/reports/stocks/sh.600016", text)
        self.assertIn("标签分布", text)
        self.assertIn("高置信候选区", text)
        self.assertIn("风险提示区", text)
        self.assertIn("回测核心指标", text)
        self.assertIn("仅为个人研究辅助，不构成投资建议", text)

    def test_stock_detail_page_returns_html(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/stocks/sh.600016")

        self.assertEqual(response.status_code, 200)
        text = response.text
        self.assertIn("sh.600016", text)
        self.assertIn("民生银行", text)
        self.assertIn("高置信候选", text)
        self.assertIn("total_score", text)
        self.assertIn("positive_evidence", text)
        self.assertIn("因子贡献表", text)
        self.assertIn("单股报告", text)
        self.assertIn("返回首页", text)
        self.assertIn("仅为个人研究辅助，不构成投资建议", text)

    def test_daily_report_page_returns_html(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/reports/daily")

        self.assertEqual(response.status_code, 200)
        self.assertIn("每日报告", response.text)
        self.assertIn("Daily Report", response.text)

    def test_stock_report_page_returns_html(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/reports/stocks/sh.600016")

        self.assertEqual(response.status_code, 200)
        self.assertIn("单股报告", response.text)
        self.assertIn("Stock Report", response.text)

    def test_missing_symbol_returns_clear_not_found_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            candidate = client.get("/api/candidates/sh.000000")
            stock_page = client.get("/stocks/sh.000000")
            report_page = client.get("/reports/stocks/sh.000000")
            report_api = client.get("/api/reports/stocks/sh.000000")

        self.assertEqual(candidate.status_code, 404)
        self.assertIn("No candidate found", candidate.json()["message"])
        self.assertEqual(stock_page.status_code, 404)
        self.assertIn("No candidate found", stock_page.text)
        self.assertEqual(report_page.status_code, 404)
        self.assertIn("No stock report found for this symbol", report_page.text)
        self.assertEqual(report_api.status_code, 404)
        self.assertIn("No stock report found for this symbol", report_api.json()["message"])

    def test_page_and_api_do_not_contain_deterministic_trading_terms(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            texts = [
                client.get("/").text,
                client.get("/stocks/sh.600016").text,
                client.get("/reports/daily").text,
                client.get("/reports/stocks/sh.600016").text,
                json.dumps(client.get("/api/latest").json(), ensure_ascii=False),
                json.dumps(client.get("/api/candidates").json(), ensure_ascii=False),
                json.dumps(client.get("/api/candidates/sh.600016").json(), ensure_ascii=False),
                json.dumps(client.get("/api/factor-explanations").json(), ensure_ascii=False),
                json.dumps(client.get("/api/factor-explanations/sh.600016").json(), ensure_ascii=False),
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
            "momentum_score": 23.0,
            "trend_score": 20.0,
            "relative_strength_score": 19.0,
            "risk_score": 16.0,
            "liquidity_score": 13.2,
            "positive_evidence": "多项因子共振，但原始文件里混入买入措辞时应被隐藏",
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
            "momentum_score": 20.0,
            "trend_score": 18.0,
            "relative_strength_score": 16.0,
            "risk_score": 15.0,
            "liquidity_score": 13.0,
            "positive_evidence": "趋势结构较强",
            "negative_evidence": "流动性仍需观察",
            "risk_flags": "",
            "warnings": "",
            "source": "baostock",
        },
    ]
    factor_explanations = [
        {
            "symbol": "sh.600016",
            "factor_group": "momentum_60d",
            "raw_value": 0.18,
            "normalized_score": 0.95,
            "weight": 10,
            "contribution": 9.5,
            "explanation": "momentum_60d 横截面分位数较高",
        },
        {
            "symbol": "sh.600016",
            "factor_group": "trend_score",
            "raw_value": 1.0,
            "normalized_score": 1.0,
            "weight": 20,
            "contribution": 20.0,
            "explanation": "均线结构较强",
        },
        {
            "symbol": "sh.600015",
            "factor_group": "momentum_60d",
            "raw_value": 0.12,
            "normalized_score": 0.80,
            "weight": 10,
            "contribution": 8.0,
            "explanation": "动量表现尚可",
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
    (daily / "factor_explanations_2024-01-31.json").write_text(json.dumps(factor_explanations, ensure_ascii=False), encoding="utf-8")
    (reports / "daily_report_2024-01-31.md").write_text("# Daily Report\n\n仅用于研究复盘。", encoding="utf-8")
    (reports / "daily_report_2024-01-31.html").write_text("<h1>Daily Report</h1><p>建议买入 会被隐藏</p>", encoding="utf-8")
    (stock_reports / "sh.600016_2024-01-31.md").write_text("# Stock Report\n\n仅用于研究复盘。", encoding="utf-8")
    (stock_reports / "sh.600016_2024-01-31.html").write_text("<h1>Stock Report</h1><p>强烈买入 会被隐藏</p>", encoding="utf-8")
    (backtests / "backtest_summary_2024-01-31.json").write_text(json.dumps(backtest, ensure_ascii=False), encoding="utf-8")
    (backtests / "backtest_report_2024-01-31.md").write_text("# Backtest", encoding="utf-8")
    (backtests / "backtest_report_2024-01-31.html").write_text("<h1>Backtest</h1>", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
