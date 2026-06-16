from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.research.multi_label import (
    PRIMARY_HIGH_RISK_ACTIVE,
    PRIMARY_INSUFFICIENT_DATA,
    PRIMARY_LONG_TERM_STABLE,
    PRIMARY_NORMAL_WATCH,
    PRIMARY_TREND_LEADER,
    TAG_INDUSTRY_PENDING,
    label_candidates,
)
from stock_analysis.research.universe_quality import build_label_input_rows, classify_instrument


class MultiLabelTests(unittest.TestCase):
    def test_single_stock_can_have_multiple_secondary_tags(self) -> None:
        labels = label_candidates(_candidate_rows(), factors=_factor_rows())
        row = _row(labels, "AAA")

        self.assertIn(PRIMARY_TREND_LEADER, row["secondary_tags"])
        self.assertGreaterEqual(len(row["secondary_tags"]), 2)

    def test_high_risk_stock_does_not_enter_long_term_stable(self) -> None:
        labels = label_candidates(_candidate_rows(), factors=_factor_rows())
        row = _row(labels, "RISK")

        self.assertEqual(row["primary_type"], PRIMARY_HIGH_RISK_ACTIVE)
        self.assertNotIn(PRIMARY_LONG_TERM_STABLE, row["secondary_tags"])

    def test_insufficient_data_is_labeled(self) -> None:
        labels = label_candidates(_candidate_rows(), factors=_factor_rows())
        row = _row(labels, "SHORT")

        self.assertEqual(row["primary_type"], PRIMARY_INSUFFICIENT_DATA)
        self.assertIn("insufficient", row["data_quality"])

    def test_missing_fields_do_not_crash(self) -> None:
        labels = label_candidates([{"symbol": "MISS", "name": "Missing", "total_score": 50}])
        row = _row(labels, "MISS")

        self.assertEqual(row["symbol"], "MISS")
        self.assertIn("missing_factor_row", row["data_quality"])

    def test_missing_industry_does_not_invent_industry_judgment(self) -> None:
        labels = label_candidates(_candidate_rows(), factors=_factor_rows())
        row = _row(labels, "AAA")

        self.assertNotEqual(row["primary_type"], "行业热股型")
        self.assertIn(TAG_INDUSTRY_PENDING, row["secondary_tags"])
        self.assertIn("不做行业热度判断", row["label_reason"])

    def test_non_stock_index_is_excluded_from_label_input(self) -> None:
        label_inputs, excluded = build_label_input_rows(
            [],
            factors=[_factor("sz.399001")],
            stock_universe=[{"symbol": "sz.399001", "name": "深证成份指数"}],
            as_of_date="2024-01-31",
        )

        self.assertEqual(label_inputs, [])
        self.assertEqual(excluded[0]["instrument_type"], "index")
        self.assertIn("指数", excluded[0]["excluded_reason"])

    def test_bond_index_is_excluded_with_reason(self) -> None:
        classification = classify_instrument({"symbol": "sh.000999", "name": "国证企债指数"})

        self.assertFalse(classification["is_stock"])
        self.assertIn(classification["instrument_type"], {"bond_or_bond_index", "index"})
        self.assertTrue(classification["excluded_reason"])

    def test_state_owned_company_name_is_not_excluded_by_country_character(self) -> None:
        classification = classify_instrument({"symbol": "sh.601088", "name": "中国神华"})

        self.assertTrue(classification["is_stock"])

    def test_factor_only_stock_receives_observation_status(self) -> None:
        label_inputs, excluded = build_label_input_rows(
            [],
            factors=[_factor("sz.300119")],
            stock_universe=[{"symbol": "sz.300119", "name": "瑞普生物"}],
            as_of_date="2024-01-31",
        )
        labels = label_candidates(label_inputs, factors=[_factor("sz.300119")])
        row = _row(labels, "sz.300119")

        self.assertEqual(excluded, [])
        self.assertIn(row["primary_type"], {PRIMARY_NORMAL_WATCH, "突破爆发型", "潜力蓄势型", PRIMARY_TREND_LEADER, PRIMARY_LONG_TERM_STABLE})
        self.assertEqual(row["research_status"], row["primary_type"])


def _row(frame: pd.DataFrame, symbol: str) -> pd.Series:
    return frame[frame["symbol"] == symbol].iloc[0]


def _candidate_rows() -> list[dict[str, object]]:
    return [
        _candidate("AAA", total_score=99, momentum_score=25, trend_score=20, relative_strength_score=20, risk_score=20, liquidity_score=14),
        _candidate("BBB", total_score=78, momentum_score=14, trend_score=14, relative_strength_score=13, risk_score=18, liquidity_score=12),
        _candidate("RISK", total_score=76, momentum_score=20, trend_score=18, relative_strength_score=17, risk_score=2, liquidity_score=13, label="风险过高", risk_flags="severe_max_drawdown"),
        _candidate("SHORT", total_score=40, momentum_score=5, trend_score=5, relative_strength_score=5, risk_score=5, liquidity_score=5, label="数据不足", warnings="insufficient_history"),
    ]


def _candidate(symbol: str, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "rank": 1,
        "symbol": symbol,
        "name": symbol,
        "as_of_date": "2024-01-31",
        "total_score": 80,
        "label": "候选关注",
        "confidence": 0.9,
        "momentum_score": 16,
        "trend_score": 16,
        "relative_strength_score": 14,
        "risk_score": 16,
        "liquidity_score": 12,
        "positive_evidence": "趋势结构较强",
        "negative_evidence": "",
        "risk_flags": "",
        "warnings": "",
        "source": "unit",
    }
    row.update(overrides)
    return row


def _factor_rows() -> list[dict[str, object]]:
    return [
        _factor("AAA", momentum_20d=0.20, momentum_120d=0.25, volatility_60d=0.01, max_drawdown_60d=-0.03, data_points=180),
        _factor("BBB", momentum_20d=0.08, momentum_120d=0.10, volatility_60d=0.03, max_drawdown_60d=-0.10, data_points=180),
        _factor("RISK", momentum_20d=0.18, momentum_120d=0.22, volatility_60d=0.12, max_drawdown_60d=-0.45, data_points=180),
        _factor("SHORT", momentum_20d=None, momentum_120d=None, volatility_60d=None, max_drawdown_60d=None, data_points=60, warnings="insufficient_history"),
    ]


def _factor(symbol: str, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "symbol": symbol,
        "as_of_date": "2024-01-31",
        "momentum_20d": 0.1,
        "momentum_60d": 0.1,
        "momentum_120d": 0.1,
        "rs_20d": 0.1,
        "rs_60d": 0.1,
        "rs_120d": 0.1,
        "volatility_20d": 0.02,
        "volatility_60d": 0.02,
        "max_drawdown": -0.1,
        "max_drawdown_20d": -0.05,
        "max_drawdown_60d": -0.08,
        "avg_amount_20d": 100_000_000,
        "avg_amount_60d": 90_000_000,
        "data_points": 180,
        "source": "unit",
        "warnings": "",
    }
    row.update(overrides)
    return row


if __name__ == "__main__":
    unittest.main()
