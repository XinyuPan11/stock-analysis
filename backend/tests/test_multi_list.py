from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from stock_analysis.research.multi_list import LIST_IDS, build_multi_lists, list_by_id
from test_multi_label import _candidate_rows, _factor_rows
from stock_analysis.research.multi_label import label_candidates


class MultiListTests(unittest.TestCase):
    def test_generated_list_json_structure_is_stable(self) -> None:
        lists = build_multi_lists(label_candidates(_candidate_rows(), factors=_factor_rows()), top_n=5, as_of_date="2024-01-31")

        self.assertEqual(set(list_by_id(lists)), set(LIST_IDS))
        first = lists["lists"][0]
        self.assertIn("list_id", first)
        self.assertIn("list_name", first)
        self.assertIn("description", first)
        self.assertIn("sort_logic", first)
        self.assertIn("eligible_filters", first)
        self.assertIn("items", first)

    def test_insufficient_data_enters_insufficient_list(self) -> None:
        by_id = list_by_id(build_multi_lists(label_candidates(_candidate_rows(), factors=_factor_rows())))

        symbols = [item["symbol"] for item in by_id["insufficient_data"]["items"]]
        self.assertIn("SHORT", symbols)

    def test_high_risk_does_not_enter_long_term_stable_list(self) -> None:
        by_id = list_by_id(build_multi_lists(label_candidates(_candidate_rows(), factors=_factor_rows())))

        symbols = [item["symbol"] for item in by_id["long_term_stable"]["items"]]
        self.assertNotIn("RISK", symbols)

    def test_trend_leaders_are_sorted_by_trend_then_momentum(self) -> None:
        by_id = list_by_id(build_multi_lists(label_candidates(_candidate_rows(), factors=_factor_rows())))
        items = by_id["trend_leaders"]["items"]

        self.assertGreaterEqual(len(items), 1)
        self.assertEqual(items[0]["symbol"], "AAA")

    def test_breakout_watch_keeps_risk_note(self) -> None:
        by_id = list_by_id(build_multi_lists(label_candidates(_candidate_rows(), factors=_factor_rows())))
        items = by_id["breakout_watch"]["items"]

        self.assertTrue(items)
        self.assertTrue(any("风险" in signal or "波动" in signal or "回撤" in signal for signal in items[0]["invalidation_signals"]))


if __name__ == "__main__":
    unittest.main()
