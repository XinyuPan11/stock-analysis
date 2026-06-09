from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from stock_analysis.research.factor_explanation import FACTOR_EXPLANATION_COLUMNS, explain_factor_contributions
from test_scoring import _factor_frame


class FactorExplanationTests(unittest.TestCase):
    def test_factor_explanation_outputs_required_fields(self) -> None:
        explanations = explain_factor_contributions(_factor_frame(), symbol="AAA")

        self.assertEqual(list(explanations.columns), FACTOR_EXPLANATION_COLUMNS)
        first = explanations.iloc[0]
        self.assertEqual(first["symbol"], "AAA")
        self.assertIn("raw_value", explanations.columns)
        self.assertIn("normalized_score", explanations.columns)
        self.assertIn("weight", explanations.columns)
        self.assertIn("contribution", explanations.columns)
        self.assertIn("explanation", explanations.columns)
        self.assertGreaterEqual(first["normalized_score"], 0)
        self.assertLessEqual(first["normalized_score"], 1)
        self.assertGreater(first["contribution"], 0)

    def test_factor_explanation_filters_single_symbol(self) -> None:
        explanations = explain_factor_contributions(_factor_frame(), symbol="BBB")

        self.assertEqual(set(explanations["symbol"]), {"BBB"})

    def test_unknown_symbol_returns_empty_explanation_frame(self) -> None:
        explanations = explain_factor_contributions(_factor_frame(), symbol="ZZZ")

        self.assertTrue(explanations.empty)
        self.assertEqual(list(explanations.columns), FACTOR_EXPLANATION_COLUMNS)


if __name__ == "__main__":
    unittest.main()
