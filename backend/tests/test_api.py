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

    def test_candidates_filter_by_label(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/candidates", params={"label": "候选关注"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["symbol"], "sh.600015")
        self.assertEqual(payload["filters"]["label"], "候选关注")

    def test_candidates_filter_by_min_score(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/candidates", params={"min_score": 90})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["symbol"], "sh.600016")

    def test_candidates_sort_by_total_score_desc(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/candidates", params={"sort_by": "total_score", "sort_order": "desc"})

        self.assertEqual(response.status_code, 200)
        scores = [row["total_score"] for row in response.json()["items"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_invalid_sort_by_returns_clear_error_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/candidates", params={"sort_by": "not_a_factor"})

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertIn("Invalid sort_by", payload["message"])

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

    def test_factor_summary_for_symbol_returns_grouped_contributions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/factor-summary/sh.600016")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["symbol"], "sh.600016")
        groups = {row["factor_group"]: row for row in payload["items"]}
        self.assertIn("momentum", groups)
        self.assertIn("trend", groups)
        self.assertEqual(groups["trend"]["contribution"], 20.0)
        self.assertIn("个人研究排序", payload["explanation"])

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
        self.assertIn("筛选与排序", text)
        self.assertIn("当前筛选条件", text)
        self.assertIn("筛选后候选数量", text)
        self.assertIn("/compare", text)
        self.assertIn("查看候选股横向对比", text)
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
        self.assertIn("因子贡献总览", text)
        self.assertIn("主要正向因子", text)
        self.assertIn("主要负向/风险因子", text)
        self.assertIn("需要继续观察的信号", text)
        self.assertIn("分数解释", text)
        self.assertIn("因子贡献表", text)
        self.assertIn("单股报告", text)
        self.assertIn("返回首页", text)
        self.assertIn("仅为个人研究辅助，不构成投资建议", text)

    def test_compare_page_returns_html(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/compare")

        self.assertEqual(response.status_code, 200)
        text = response.text
        self.assertIn("候选股横向对比", text)
        self.assertIn("候选股对比总表", text)
        self.assertIn("因子组贡献对比表", text)
        self.assertIn("风险标记对比", text)
        self.assertIn("主要正向证据对比", text)
        self.assertIn("研究解释区", text)
        self.assertIn("/stocks/sh.600016", text)
        self.assertIn("/reports/stocks/sh.600016", text)

    def test_compare_api_returns_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/compare")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["count"], 2)
        self.assertIn("research_explanation", payload["items"][0])
        self.assertIn("/stocks/", payload["items"][0]["detail_link"])

    def test_compare_api_filter_by_label(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/compare", params={"label": "候选关注"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["symbol"], "sh.600015")

    def test_compare_api_sort_by_total_score_desc(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/compare", params={"sort_by": "total_score", "sort_order": "desc"})

        self.assertEqual(response.status_code, 200)
        scores = [row["total_score"] for row in response.json()["items"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_factor_groups_matrix_returns_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/factor-groups")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["count"], 2)
        first = payload["items"][0]
        self.assertIn("momentum_contribution", first)
        self.assertIn("trend_contribution", first)
        self.assertIn("top_positive_factor_group", first)

    def test_factor_group_detail_returns_specific_group(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/factor-groups/trend")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["factor_group"], "trend")
        self.assertEqual(payload["display_name"], "趋势")
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["items"][0]["factor_group"], "trend")

    def test_compare_page_shows_factor_fallback_when_explanations_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            Path(temp_dir, "daily", "factor_explanations_2024-01-31.json").unlink()
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/compare")

        self.assertEqual(response.status_code, 200)
        self.assertIn("暂无真实因子贡献表，请先生成 factor_explanations 输出", response.text)

    def test_reports_center_returns_html(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/reports")

        self.assertEqual(response.status_code, 200)
        self.assertIn("报告中心", response.text)
        self.assertIn("每日报告列表", response.text)
        self.assertIn("单股报告列表", response.text)
        self.assertIn("回测报告列表", response.text)

    def test_output_health_page_returns_html(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/health/outputs")

        self.assertEqual(response.status_code, 200)
        self.assertIn("输出健康检查", response.text)
        self.assertIn("outputs 完整性检查", response.text)
        self.assertIn("单股报告覆盖率", response.text)
        self.assertIn("failed symbols 检查", response.text)
        self.assertIn("数据质量检查", response.text)

    def test_report_index_api_returns_report_lists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/report-index")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["daily_reports"]), 1)
        self.assertEqual(len(payload["stock_reports"]), 1)
        self.assertEqual(len(payload["backtest_reports"]), 1)

    def test_output_health_api_reports_required_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/output-health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["latest_date"], "2024-01-31")
        self.assertGreaterEqual(len(payload["required_files"]), 9)
        self.assertEqual(payload["missing_files"], [])
        self.assertEqual(payload["report_coverage"]["candidate_count"], 2)

    def test_output_health_api_lists_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            Path(temp_dir, "daily", "factors_2024-01-31.json").unlink()
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/output-health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(any("factors_2024-01-31.json" in path for path in payload["missing_files"]))
        self.assertIn(payload["status"], {"missing", "warning"})

    def test_failed_symbols_api_reads_csv_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/failed-symbols")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["symbol"], "sh.600006")
        self.assertEqual(payload["items"][0]["error_type"], "non_numeric_market_data")

    def test_failed_symbols_api_does_not_crash_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            Path(temp_dir, "errors", "failed_symbols_2024-01-31.csv").unlink()
            Path(temp_dir, "cache", "cache_prewarm_errors_2024-01-31.csv").unlink()
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/failed-symbols")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], [])

    def test_data_quality_api_returns_summary_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/data-quality")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["latest_date"], "2024-01-31")
        self.assertIn("unit_warning", payload["warnings"])
        self.assertEqual(payload["fetch_error_count"], 1)
        self.assertIn("non_numeric_market_data", payload["error_type_counts"])

    def test_stock_detail_page_shows_factor_fallback_when_explanations_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            Path(temp_dir, "daily", "factor_explanations_2024-01-31.json").unlink()
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/stocks/sh.600016")

        self.assertEqual(response.status_code, 200)
        self.assertIn("暂无真实因子贡献表，请先生成 factor_explanations 输出", response.text)

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
                client.get("/compare").text,
                client.get("/reports").text,
                client.get("/health/outputs").text,
                client.get("/stocks/sh.600016").text,
                client.get("/reports/daily").text,
                client.get("/reports/stocks/sh.600016").text,
                json.dumps(client.get("/api/latest").json(), ensure_ascii=False),
                json.dumps(client.get("/api/candidates").json(), ensure_ascii=False),
                json.dumps(client.get("/api/candidates/sh.600016").json(), ensure_ascii=False),
                json.dumps(client.get("/api/compare").json(), ensure_ascii=False),
                json.dumps(client.get("/api/factor-explanations").json(), ensure_ascii=False),
                json.dumps(client.get("/api/factor-explanations/sh.600016").json(), ensure_ascii=False),
                json.dumps(client.get("/api/factor-summary/sh.600016").json(), ensure_ascii=False),
                json.dumps(client.get("/api/factor-groups").json(), ensure_ascii=False),
                json.dumps(client.get("/api/factor-groups/trend").json(), ensure_ascii=False),
                json.dumps(client.get("/api/report-index").json(), ensure_ascii=False),
                json.dumps(client.get("/api/output-health").json(), ensure_ascii=False),
                json.dumps(client.get("/api/failed-symbols").json(), ensure_ascii=False),
                json.dumps(client.get("/api/data-quality").json(), ensure_ascii=False),
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
    errors = outputs / "errors"
    cache = outputs / "cache"
    daily.mkdir(parents=True)
    stock_reports.mkdir(parents=True)
    backtests.mkdir(parents=True)
    errors.mkdir(parents=True)
    cache.mkdir(parents=True)

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
    factors = [
        {"symbol": "sh.600016", "as_of_date": "2024-01-31", "momentum_60d": 0.18},
        {"symbol": "sh.600015", "as_of_date": "2024-01-31", "momentum_60d": 0.12},
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
    cache_summary = {
        "error_count": 1,
        "error_type_counts": {"non_numeric_market_data": 1},
        "warnings": [],
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
    (daily / "factors_2024-01-31.json").write_text(json.dumps(factors, ensure_ascii=False), encoding="utf-8")
    (daily / "factor_explanations_2024-01-31.json").write_text(json.dumps(factor_explanations, ensure_ascii=False), encoding="utf-8")
    (reports / "daily_report_2024-01-31.md").write_text("# Daily Report\n\n仅用于研究复盘。", encoding="utf-8")
    (reports / "daily_report_2024-01-31.html").write_text("<h1>Daily Report</h1><p>建议买入 会被隐藏</p>", encoding="utf-8")
    (stock_reports / "sh.600016_2024-01-31.md").write_text("# Stock Report\n\n仅用于研究复盘。", encoding="utf-8")
    (stock_reports / "sh.600016_2024-01-31.html").write_text("<h1>Stock Report</h1><p>强烈买入 会被隐藏</p>", encoding="utf-8")
    (backtests / "backtest_summary_2024-01-31.json").write_text(json.dumps(backtest, ensure_ascii=False), encoding="utf-8")
    (backtests / "backtest_report_2024-01-31.md").write_text("# Backtest", encoding="utf-8")
    (backtests / "backtest_report_2024-01-31.html").write_text("<h1>Backtest</h1>", encoding="utf-8")
    (errors / "failed_symbols_2024-01-31.csv").write_text(
        "symbol,stage,error_type,error,attempts\n"
        "sh.600006,stock_daily,non_numeric_market_data,simulated failure,2\n",
        encoding="utf-8",
    )
    (cache / "cache_prewarm_errors_2024-01-31.csv").write_text(
        "symbol,name,error_type,error_message,provider,start_date,end_date,attempt_count,last_attempt_at,can_retry\n",
        encoding="utf-8",
    )
    (cache / "cache_prewarm_summary_2024-01-31.json").write_text(json.dumps(cache_summary, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
