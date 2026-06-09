from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.reports.report_generator import (
    PROHIBITED_TERMS,
    generate_daily_report,
    generate_reports_from_candidates,
    generate_stock_report,
)


class ReportGeneratorTests(unittest.TestCase):
    def test_generate_daily_markdown_report(self) -> None:
        artifact = generate_daily_report(
            _candidates(),
            summary=_summary(),
            as_of_date="2024-01-31",
            updated_at="2024-02-01 08:00:00",
        )

        self.assertIn("A股每日候选研究报告", artifact.markdown)
        self.assertIn("数据日期：2024-01-31", artifact.markdown)
        self.assertIn("更新时间：2024-02-01 08:00:00", artifact.markdown)
        self.assertIn("数据来源：baostock", artifact.markdown)

    def test_daily_report_contains_top_table_label_explanation_and_risk_sections(self) -> None:
        artifact = generate_daily_report(_candidates(), summary=_summary(), as_of_date="2024-01-31")

        self.assertIn("## 推荐标签说明", artifact.markdown)
        self.assertIn("高置信候选", artifact.markdown)
        self.assertIn("## Top N 候选股总表", artifact.markdown)
        self.assertIn("| rank | symbol | name |", artifact.markdown)
        self.assertIn("## 主要风险提示", artifact.markdown)
        self.assertIn("## 免责声明", artifact.markdown)

    def test_generate_single_stock_markdown_report(self) -> None:
        artifact = generate_stock_report(
            _candidates().iloc[0],
            explanations=_explanations(),
            updated_at="2024-02-01 08:00:00",
        )

        self.assertIn("## 一、推荐结论", artifact.markdown)
        self.assertIn("## 二、核心观点", artifact.markdown)
        self.assertIn("## 三、关键证据", artifact.markdown)
        self.assertIn("## 四、因子贡献表", artifact.markdown)
        self.assertIn("## 五、风险反证", artifact.markdown)
        self.assertIn("## 六、失效条件", artifact.markdown)
        self.assertIn("## 七、后续跟踪指标", artifact.markdown)
        self.assertIn("## 八、数据来源与更新时间", artifact.markdown)

    def test_html_outputs_can_be_written(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = generate_reports_from_candidates(
                _candidates(),
                summary=_summary(),
                explanations=_explanations(),
                output_dir=temp_dir,
                as_of_date="2024-01-31",
                updated_at="2024-02-01 08:00:00",
            )

            self.assertTrue(Path(result["daily_markdown"]).exists())
            self.assertTrue(Path(result["daily_html"]).exists())
            self.assertGreaterEqual(len(result["stock_reports"]), 1)
            self.assertTrue(Path(result["stock_reports"][0]["html"]).exists())

    def test_empty_candidates_generate_clear_no_result_report(self) -> None:
        artifact = generate_daily_report(pd.DataFrame(), as_of_date="2024-01-31")

        self.assertIn("无候选结果", artifact.markdown)
        self.assertIn("高置信候选", artifact.markdown)

    def test_missing_candidate_fields_surface_warning(self) -> None:
        artifact = generate_daily_report(pd.DataFrame([{"symbol": "AAA"}]), as_of_date="2024-01-31")

        self.assertTrue(any("missing_candidate_columns" in warning for warning in artifact.warnings))
        self.assertIn("missing_candidate_columns", artifact.markdown)

    def test_report_has_no_deterministic_trading_terms(self) -> None:
        daily = generate_daily_report(_candidates(), summary=_summary(), as_of_date="2024-01-31")
        stock = generate_stock_report(_candidates().iloc[0], explanations=_explanations())
        combined = daily.markdown + stock.markdown

        for term in PROHIBITED_TERMS:
            self.assertNotIn(term, combined)


def _candidates() -> pd.DataFrame:
    return pd.DataFrame(
        [
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
                "positive_evidence": "动量分位靠前；趋势结构较强",
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
                "positive_evidence": "相对沪深300超额收益较强",
                "negative_evidence": "流动性仍需观察",
                "risk_flags": "",
                "warnings": "",
                "source": "baostock",
            },
        ]
    )


def _summary() -> dict[str, int]:
    return {
        "universe_count": 5493,
        "attempted_count": 20,
        "successful_factor_count": 19,
        "scored_count": 10,
        "fetch_error_count": 1,
    }


def _explanations() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": "sh.600016",
                "factor_group": "momentum_60d",
                "raw_value": 0.18,
                "normalized_score": 0.95,
                "weight": 10,
                "contribution": 9.5,
                "explanation": "momentum_60d横截面分位数 95%，贡献 9.50 分。",
            }
        ]
    )


if __name__ == "__main__":
    unittest.main()
