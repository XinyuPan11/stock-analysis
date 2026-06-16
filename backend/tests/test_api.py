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
NAV_LABELS = ["Home", "Compare", "Reports", "Output Health", "Guide", "Daily Report"]


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

    def test_candidates_empty_numeric_query_params_are_treated_as_unset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            empty_response = client.get("/api/candidates?min_score=&limit=")
            default_response = client.get("/api/candidates")

        self.assertEqual(empty_response.status_code, 200)
        self.assertEqual(empty_response.json()["count"], default_response.json()["count"])
        self.assertEqual(empty_response.json()["items"], default_response.json()["items"])

    def test_candidates_invalid_numeric_query_returns_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/candidates?min_score=abc&limit=")

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertIn("Invalid min_score", payload["message"])

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
        self.assertIn("/guide", text)
        self.assertIn("运行指引 / 操作手册", text)
        self.assertIn("/stocks/sh.600016", text)
        self.assertIn("/reports/stocks/sh.600016", text)
        self.assertIn("标签分布", text)
        self.assertIn("高置信候选区", text)
        self.assertIn("风险提示区", text)
        self.assertIn("回测核心指标", text)
        self.assertIn("仅为个人研究辅助，不构成投资建议", text)

    def test_major_pages_return_200_and_include_global_navigation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            for path in [
                "/",
                "/compare",
                "/reports",
                "/health/outputs",
                "/guide",
                "/stocks/sh.600016",
                "/reports/daily",
                "/reports/stocks/sh.600016",
            ]:
                response = client.get(path)
                self.assertEqual(response.status_code, 200, path)
                for label in NAV_LABELS:
                    self.assertIn(label, response.text, f"{path} missing {label}")

    def test_stock_detail_page_returns_html(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/stocks/sh.600016")

        self.assertEqual(response.status_code, 200)
        text = response.text
        self.assertIn("sh.600016", text)
        self.assertIn("个股研究详情", text)
        self.assertIn("趋势龙头型", text)
        self.assertIn("total_score", text)
        self.assertIn("分数拆解", text)
        self.assertIn("标签解释", text)
        self.assertIn("证据链", text)
        self.assertIn("风险与数据质量", text)
        self.assertIn("所属榜单", text)
        self.assertIn("报告链接", text)
        self.assertIn("返回首页", text)
        self.assertIn("不构成投资建议", text)

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

    def test_compare_empty_numeric_query_params_do_not_422(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            api_response = client.get("/api/compare?min_score=&limit=")
            page_response = client.get("/compare?min_score=&limit=")
            default_response = client.get("/api/compare")

        self.assertEqual(api_response.status_code, 200)
        self.assertEqual(page_response.status_code, 200)
        self.assertIn("text/html", page_response.headers["content-type"])
        self.assertEqual(api_response.json()["count"], default_response.json()["count"])
        self.assertEqual(api_response.json()["items"], default_response.json()["items"])

    def test_compare_invalid_numeric_query_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            api_response = client.get("/api/compare?min_score=abc&limit=")
            page_response = client.get("/compare?min_score=abc&limit=")

        self.assertEqual(api_response.status_code, 400)
        self.assertIn("Invalid min_score", api_response.json()["message"])
        self.assertEqual(page_response.status_code, 400)
        self.assertIn("Invalid min_score", page_response.text)

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

    def test_guide_page_returns_html(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/guide")

        self.assertEqual(response.status_code, 200)
        self.assertIn("A 股个人研究终端运行指引", response.text)
        self.assertIn("推荐日常运行顺序", response.text)
        self.assertIn("常用命令", response.text)
        self.assertIn("Dashboard 页面导航", response.text)
        self.assertIn("仅为个人研究辅助，不构成投资建议", response.text)

    def test_guide_api_returns_structured_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/guide")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertIn("recommended_workflow", payload)
        self.assertIn("commands", payload)
        self.assertIn("output_paths", payload)
        self.assertIn("troubleshooting", payload)
        self.assertIn("phase_status", payload)
        self.assertIn("disclaimers", payload)

    def test_guide_page_contains_daily_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/guide")

        self.assertIn("prewarm_market_cache.py", response.text)
        self.assertIn("run_daily_research.py", response.text)
        self.assertIn("generate_research_report.py", response.text)
        self.assertIn("run_backtest.py", response.text)
        self.assertIn("run_api.py", response.text)
        self.assertIn("run_daily_workflow.py", response.text)
        self.assertIn("data\\cache\\daily-use", response.text)

    def test_lists_page_returns_html_and_contains_list_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/lists")

        self.assertEqual(response.status_code, 200)
        self.assertIn("多榜单总览", response.text)
        self.assertIn("high_confidence_candidates", response.text)
        self.assertIn("查看榜单详情", response.text)
        self.assertIn("fixed historical research view", response.text)
        self.assertIn("不构成投资建议", response.text)

    def test_list_detail_page_returns_html(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/lists/high_confidence_candidates")

        self.assertEqual(response.status_code, 200)
        self.assertIn("high_confidence_candidates", response.text)
        self.assertIn("sh.600016", response.text)
        self.assertIn("个股详情", response.text)
        self.assertIn("confirmation_signals", response.text)

    def test_empty_list_detail_page_returns_200(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/lists/rebound_watch")

        self.assertEqual(response.status_code, 200)
        self.assertIn("当前榜单为空", response.text)

    def test_unknown_list_page_returns_friendly_404(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/lists/not_exist")

        self.assertEqual(response.status_code, 404)
        self.assertIn("Unknown list_id", response.text)

    def test_search_page_has_search_entry_and_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            empty = client.get("/search")
            response = client.get("/search", params={"q": "000001"})

        self.assertEqual(empty.status_code, 200)
        self.assertIn("股票搜索", empty.text)
        self.assertIn("请输入股票代码或名称", empty.text)
        self.assertEqual(response.status_code, 200)
        self.assertIn("sz.000001", response.text)
        self.assertIn("进入个股详情页", response.text)

    def test_labels_page_returns_html_and_filters(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/labels", params={"primary_type": "趋势龙头型"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("标签筛选", response.text)
        self.assertIn("趋势龙头型", response.text)
        self.assertIn("Labeled Candidates", response.text)

    def test_research_lists_api_returns_all_lists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/lists")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["date"], "2024-01-31")
        self.assertEqual(len(payload["lists"]), 8)
        self.assertIn("disclaimer", payload)
        first = payload["lists"][0]
        self.assertIn("item_count", first)
        self.assertIn("items_preview", first)

    def test_research_list_detail_returns_specific_list(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/lists/high_confidence_candidates")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["list_id"], "high_confidence_candidates")
        self.assertGreaterEqual(payload["item_count"], 1)
        self.assertEqual(payload["items"][0]["symbol"], "sh.600016")

    def test_empty_research_list_does_not_500(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/lists/rebound_watch")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["item_count"], 0)
        self.assertEqual(payload["items"], [])

    def test_unknown_research_list_returns_404_with_available_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/lists/not_a_list")

        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertIn("available_list_ids", payload)
        self.assertIn("trend_leaders", payload["available_list_ids"])

    def test_labels_api_returns_counts_and_filters(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/labels", params={"primary_type": "趋势龙头型", "limit": "2"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["item_count"], 2)
        self.assertIn("primary_type_counts", payload)
        self.assertEqual(payload["primary_type_counts"]["趋势龙头型"], 2)
        self.assertIn("risk_level_counts", payload)
        self.assertIn("research_action_counts", payload)

    def test_stock_search_matches_numeric_sh_symbol(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/stocks/search", params={"q": "600000"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["symbol"], "sh.600000")

    def test_stock_search_matches_numeric_sz_symbol(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/stocks/search", params={"q": "000001"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["symbol"], "sz.000001")

    def test_stock_search_supports_chinese_substring(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/stocks/search", params={"q": "平安"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["name"], "平安银行")

    def test_empty_stock_search_returns_400_not_500(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/stocks/search?q=")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["count"], 0)

    def test_stock_research_api_returns_label_score_risk_and_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/stocks/600016/research")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["symbol"], "sh.600016")
        self.assertEqual(payload["primary_type"], "趋势龙头型")
        self.assertIn("score_breakdown", payload)
        self.assertIn("risk_flags", payload)
        self.assertIn("report_links", payload)
        self.assertIn("/reports/stocks/sh.600016", payload["report_links"]["page_url"])
        self.assertTrue(any(item["list_id"] == "high_confidence_candidates" for item in payload["related_lists"]))

    def test_stock_research_missing_symbol_does_not_500(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/stocks/sh.999999/research")

        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertIn("not found", payload["message"].lower())

    def test_home_and_output_health_show_latest_workflow_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outputs(temp_dir)
            client = TestClient(create_app(outputs_dir=temp_dir))

            home = client.get("/")
            health = client.get("/health/outputs")
            health_api = client.get("/api/output-health")

        self.assertEqual(home.status_code, 200)
        self.assertEqual(health.status_code, 200)
        self.assertIn("Workflow Summary", home.text)
        self.assertIn("workflow_summary_2024-01-31.json", home.text)
        self.assertIn("Workflow Summary", health.text)
        self.assertIn("workflow_log_2024-01-31.txt", health.text)
        self.assertTrue(health_api.json()["workflow_summary"]["ok"])

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
        self.assertIn("Symbol not found", stock_page.text)
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
                client.get("/lists").text,
                client.get("/lists/high_confidence_candidates").text,
                client.get("/labels").text,
                client.get("/search?q=600000").text,
                client.get("/reports").text,
                client.get("/health/outputs").text,
                client.get("/guide").text,
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
                json.dumps(client.get("/api/guide").json(), ensure_ascii=False),
                json.dumps(client.get("/api/lists").json(), ensure_ascii=False),
                json.dumps(client.get("/api/lists/high_confidence_candidates").json(), ensure_ascii=False),
                json.dumps(client.get("/api/labels").json(), ensure_ascii=False),
                json.dumps(client.get("/api/stocks/search?q=600000").json(), ensure_ascii=False),
                json.dumps(client.get("/api/stocks/sh.600016/research").json(), ensure_ascii=False),
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
    workflow = outputs / "workflow"
    labels_dir = outputs / "labels"
    lists_dir = outputs / "lists"
    daily.mkdir(parents=True)
    stock_reports.mkdir(parents=True)
    backtests.mkdir(parents=True)
    errors.mkdir(parents=True)
    cache.mkdir(parents=True)
    workflow.mkdir(parents=True)
    labels_dir.mkdir(parents=True)
    lists_dir.mkdir(parents=True)

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
    workflow_summary = {
        "status": "ok",
        "start_time": "2024-02-01T08:00:00",
        "end_time": "2024-02-01T08:05:00",
        "elapsed_seconds": 300,
        "provider": "baostock",
        "start_date": "2023-01-01",
        "end_date": "2024-01-31",
        "benchmark": "CSI300",
        "limit": 50,
        "top_n": 10,
        "steps": [],
        "step_statuses": {"daily_research": "ok"},
        "output_files": [],
        "missing_files": [],
        "warnings": [],
        "errors": [],
        "dashboard_url": "",
        "summary_path": str(workflow / "workflow_summary_2024-01-31.json"),
        "log_path": str(workflow / "workflow_log_2024-01-31.txt"),
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
    labels = [
        _label_row("sh.600016", "姘戠敓閾惰", primary_type="趋势龙头型", rank=1, total_score=91.2),
        _label_row("sh.600000", "浦发银行", primary_type="长期稳定型", rank=2, total_score=88.0, research_action="重点研究", risk_level="中低"),
        _label_row("sz.000001", "平安银行", primary_type="趋势龙头型", rank=3, total_score=86.5, research_action="持续跟踪", risk_level="中"),
    ]
    lists = _research_lists(labels)

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
    (workflow / "workflow_summary_2024-01-31.json").write_text(json.dumps(workflow_summary, ensure_ascii=False), encoding="utf-8")
    (workflow / "workflow_log_2024-01-31.txt").write_text("workflow started\nworkflow status: ok\n", encoding="utf-8")
    (labels_dir / "candidate_labels_2024-01-31.json").write_text(json.dumps(labels, ensure_ascii=False), encoding="utf-8")
    (labels_dir / "candidate_labels_2024-01-31.csv").write_text("symbol,name\nsh.600016,姘戠敓閾惰\n", encoding="utf-8")
    (lists_dir / "multi_lists_2024-01-31.json").write_text(
        json.dumps({"status": "ok", "as_of_date": "2024-01-31", "lists": lists}, ensure_ascii=False),
        encoding="utf-8",
    )
    for item in lists:
        (lists_dir / f"{item['list_id']}_2024-01-31.json").write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")


def _label_row(
    symbol: str,
    name: str,
    *,
    primary_type: str,
    rank: int,
    total_score: float,
    research_action: str = "重点研究",
    risk_level: str = "低",
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "name": name,
        "as_of_date": "2024-01-31",
        "rank": rank,
        "total_score": total_score,
        "primary_type": primary_type,
        "secondary_tags": [primary_type, "行业字段待补充"],
        "research_label": f"{primary_type}｜中高置信｜{risk_level}风险",
        "research_action": research_action,
        "confidence_level": "中高",
        "risk_level": risk_level,
        "confirmation_signals": ["趋势结构保持完整", "风险标记没有新增"],
        "invalidation_signals": ["趋势结构转弱", "风险分继续下行"],
        "label_reason": "基于 fixed historical outputs 的横截面相对排序生成。",
        "data_quality": "ok",
        "source_label": "楂樼疆淇″€欓€?",
        "momentum_score": 23.0,
        "trend_score": 20.0,
        "relative_strength_score": 19.0,
        "risk_score": 16.0,
        "liquidity_score": 13.2,
        "positive_evidence": "趋势结构较强",
        "negative_evidence": "",
        "risk_flags": "",
        "warnings": "",
        "report_path_md": "",
        "report_path_html": "",
    }


def _research_lists(labels: list[dict[str, object]]) -> list[dict[str, object]]:
    def item(symbol: str) -> dict[str, object]:
        row = next(label for label in labels if label["symbol"] == symbol)
        return {
            "symbol": row["symbol"],
            "name": row["name"],
            "rank": row["rank"],
            "total_score": row["total_score"],
            "primary_type": row["primary_type"],
            "secondary_tags": row["secondary_tags"],
            "research_action": row["research_action"],
            "confidence_level": row["confidence_level"],
            "risk_level": row["risk_level"],
            "label_reason": row["label_reason"],
            "confirmation_signals": row["confirmation_signals"],
            "invalidation_signals": row["invalidation_signals"],
        }

    definitions = {
        "high_confidence_candidates": [item("sh.600016"), item("sh.600000")],
        "trend_leaders": [item("sh.600016"), item("sz.000001")],
        "long_term_stable": [item("sh.600000")],
        "breakout_watch": [item("sh.600016")],
        "accumulation_watch": [item("sz.000001")],
        "rebound_watch": [],
        "high_risk_active": [],
        "insufficient_data": [],
    }
    return [
        {
            "list_id": list_id,
            "list_name": list_id,
            "description": f"{list_id} description",
            "sort_logic": "unit sort",
            "eligible_filters": ["unit filter"],
            "as_of_date": "2024-01-31",
            "top_n": 30,
            "items": items,
        }
        for list_id, items in definitions.items()
    ]


if __name__ == "__main__":
    unittest.main()
