from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from stock_analysis.research.recommendation_engine import RECOMMENDATION_OUTPUT_COLUMNS, rank_candidates
from test_scoring import _factor_frame


class RecommendationEngineTests(unittest.TestCase):
    def test_rank_candidates_returns_top_n_in_score_order(self) -> None:
        ranked = rank_candidates(_factor_frame(), top_n=2)

        self.assertEqual(len(ranked), 2)
        self.assertEqual(ranked["rank"].tolist(), [1, 2])
        self.assertEqual(ranked.iloc[0]["symbol"], "AAA")
        self.assertGreaterEqual(ranked.iloc[0]["total_score"], ranked.iloc[1]["total_score"])

    def test_rank_candidates_outputs_structured_fields(self) -> None:
        ranked = rank_candidates(_factor_frame(), top_n=1)

        self.assertEqual(list(ranked.columns), RECOMMENDATION_OUTPUT_COLUMNS)
        self.assertIn("label", ranked.columns)
        self.assertIn("positive_evidence", ranked.columns)
        self.assertIn("negative_evidence", ranked.columns)
        self.assertIn("risk_flags", ranked.columns)

    def test_rank_candidates_rejects_non_positive_top_n(self) -> None:
        with self.assertRaisesRegex(ValueError, "top_n must be positive"):
            rank_candidates(_factor_frame(), top_n=0)

    def test_rank_candidates_empty_input_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "factor data is empty"):
            rank_candidates(pd.DataFrame())


if __name__ == "__main__":
    unittest.main()
