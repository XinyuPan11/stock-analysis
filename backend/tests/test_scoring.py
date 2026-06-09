from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.research.scoring import (
    LABEL_CANDIDATE,
    LABEL_HIGH_RISK,
    LABEL_INSUFFICIENT_DATA,
    SCORE_OUTPUT_COLUMNS,
    calculate_score_components,
    score_factors,
)


class ScoringTests(unittest.TestCase):
    def test_high_momentum_stock_scores_higher(self) -> None:
        scored = score_factors(_factor_frame())

        high = _row(scored, "AAA")
        low = _row(scored, "CCC")

        self.assertGreater(high["momentum_score"], low["momentum_score"])

    def test_bullish_trend_stock_gets_full_trend_score(self) -> None:
        scored = score_factors(_factor_frame())

        self.assertEqual(_row(scored, "AAA")["trend_score"], 20.0)
        self.assertEqual(_row(scored, "CCC")["trend_score"], 0.0)

    def test_strong_relative_strength_scores_higher(self) -> None:
        scored = score_factors(_factor_frame())

        self.assertGreater(_row(scored, "AAA")["relative_strength_score"], _row(scored, "BBB")["relative_strength_score"])

    def test_high_volatility_and_large_drawdown_lower_risk_score(self) -> None:
        scored = score_factors(_factor_frame())

        self.assertGreater(_row(scored, "AAA")["risk_score"], _row(scored, "CCC")["risk_score"])
        self.assertIn("severe_max_drawdown", _row(scored, "CCC")["risk_flags"])

    def test_high_liquidity_scores_higher(self) -> None:
        scored = score_factors(_factor_frame())

        self.assertGreater(_row(scored, "AAA")["liquidity_score"], _row(scored, "CCC")["liquidity_score"])

    def test_total_score_weighting_is_correct_for_top_stock(self) -> None:
        scored = score_factors(_factor_frame())
        row = _row(scored, "AAA")

        expected = (
            row["momentum_score"]
            + row["trend_score"]
            + row["relative_strength_score"]
            + row["risk_score"]
            + row["liquidity_score"]
        )

        self.assertAlmostEqual(row["total_score"], expected)
        self.assertEqual(row["total_score"], 100.0)
        self.assertEqual(row["label"], LABEL_CANDIDATE)

    def test_insufficient_data_lowers_confidence_and_sets_label(self) -> None:
        rows = _factor_frame().to_dict(orient="records")
        rows.append(_factor_row("SHORT", data_points=80))
        scored = score_factors(pd.DataFrame(rows))
        row = _row(scored, "SHORT")

        self.assertEqual(row["label"], LABEL_INSUFFICIENT_DATA)
        self.assertLess(row["confidence"], 0.7)

    def test_high_risk_stock_is_not_candidate(self) -> None:
        scored = score_factors(_factor_frame())
        row = _row(scored, "CCC")

        self.assertEqual(row["label"], LABEL_HIGH_RISK)
        self.assertNotEqual(row["label"], LABEL_CANDIDATE)

    def test_score_output_schema_is_stable(self) -> None:
        scored = score_factors(_factor_frame())

        self.assertEqual(list(scored.columns), SCORE_OUTPUT_COLUMNS)

    def test_empty_factor_frame_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "factor data is empty"):
            score_factors(pd.DataFrame())

    def test_score_components_sum_to_group_scores(self) -> None:
        scored = score_factors(_factor_frame())
        components = calculate_score_components(_factor_frame())
        aaa_components = components[components["symbol"] == "AAA"]

        self.assertAlmostEqual(
            aaa_components.loc[
                aaa_components["factor_group"].isin(["momentum_20d", "momentum_60d", "momentum_120d"]),
                "contribution",
            ].sum(),
            _row(scored, "AAA")["momentum_score"],
        )


def _row(frame: pd.DataFrame, symbol: str) -> pd.Series:
    return frame[frame["symbol"] == symbol].iloc[0]


def _factor_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _factor_row("AAA"),
            _factor_row(
                "BBB",
                momentum_20d=0.08,
                momentum_60d=0.10,
                momentum_120d=0.12,
                rs_20d=0.02,
                rs_60d=0.03,
                rs_120d=0.04,
                above_ma20=True,
                above_ma60=False,
                ma_bullish_alignment=False,
                volatility_20d=0.03,
                volatility_60d=0.035,
                max_drawdown=-0.18,
                max_drawdown_20d=-0.08,
                max_drawdown_60d=-0.10,
                avg_amount_20d=80_000_000,
                avg_amount_60d=70_000_000,
                avg_volume_20d=8_000_000,
                avg_volume_60d=7_000_000,
            ),
            _factor_row(
                "CCC",
                momentum_20d=-0.05,
                momentum_60d=-0.08,
                momentum_120d=-0.12,
                rs_20d=-0.04,
                rs_60d=-0.06,
                rs_120d=-0.08,
                above_ma20=False,
                above_ma60=False,
                ma_bullish_alignment=False,
                volatility_20d=0.08,
                volatility_60d=0.09,
                max_drawdown=-0.45,
                max_drawdown_20d=-0.22,
                max_drawdown_60d=-0.35,
                avg_amount_20d=20_000_000,
                avg_amount_60d=18_000_000,
                avg_volume_20d=2_000_000,
                avg_volume_60d=1_800_000,
            ),
        ]
    )


def _factor_row(symbol: str, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "symbol": symbol,
        "as_of_date": "2024-01-31",
        "momentum_20d": 0.20,
        "momentum_60d": 0.30,
        "momentum_120d": 0.40,
        "ma5": 12.0,
        "ma20": 11.0,
        "ma60": 10.0,
        "above_ma20": True,
        "above_ma60": True,
        "ma_bullish_alignment": True,
        "rs_20d": 0.08,
        "rs_60d": 0.12,
        "rs_120d": 0.16,
        "volatility_20d": 0.01,
        "volatility_60d": 0.012,
        "max_drawdown": -0.08,
        "max_drawdown_20d": -0.02,
        "max_drawdown_60d": -0.04,
        "avg_amount_20d": 200_000_000,
        "avg_amount_60d": 180_000_000,
        "avg_volume_20d": 20_000_000,
        "avg_volume_60d": 18_000_000,
        "data_points": 180,
        "source": "unit",
        "warnings": "",
    }
    row.update(overrides)
    if symbol == "SHORT":
        row.update(
            {
                "momentum_120d": None,
                "rs_60d": None,
                "volatility_60d": None,
                "max_drawdown_60d": None,
                "warnings": "insufficient_120d_history;missing_benchmark_data",
            }
        )
    return row


if __name__ == "__main__":
    unittest.main()
