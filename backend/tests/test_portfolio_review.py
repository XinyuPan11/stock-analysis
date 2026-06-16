from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.portfolio.review import generate_portfolio_review


class PortfolioReviewTests(unittest.TestCase):
    def test_success_and_failure_cases_are_generated(self) -> None:
        performance = [
            {
                "portfolio_id": "baseline",
                "as_of_date": "2024-01-31",
                "horizon_days": 60,
                "best_cases": [{"symbol": "AAA", "future_return": 0.2, "future_excess_return": 0.1, "max_drawdown_during_holding": -0.03}],
                "worst_cases": [{"symbol": "BBB", "future_return": -0.1, "future_excess_return": -0.2, "max_drawdown_during_holding": -0.25}],
            }
        ]
        holdings = {
            "baseline": [
                {"symbol": "AAA", "entry_score": 90, "primary_type": "trend", "secondary_tags": ["relative_strength"]},
                {"symbol": "BBB", "entry_score": 50, "primary_type": "watch", "secondary_tags": ["volatile"]},
            ]
        }

        review = generate_portfolio_review(performance, holdings)

        self.assertEqual(len(review["success_cases"]), 1)
        self.assertEqual(len(review["failure_cases"]), 1)
        self.assertIn("trend continuation", review["success_cases"][0]["success_reason_candidates"])
        self.assertIn("post-entry pullback", review["failure_cases"][0]["failure_reason_candidates"])

    def test_review_suggestions_do_not_fabricate_non_price_reasons(self) -> None:
        review = generate_portfolio_review([], {})
        text = str(review)

        self.assertNotIn("fundamental", text.lower())
        self.assertNotIn("news", text.lower())
        self.assertNotIn("valuation", text.lower())
        self.assertIn("hypothesis / next experiment", text)


if __name__ == "__main__":
    unittest.main()

