from __future__ import annotations

import pandas as pd

from stock_analysis.research.scoring import SCORE_OUTPUT_COLUMNS, score_factors


RECOMMENDATION_OUTPUT_COLUMNS = [
    "rank",
    *SCORE_OUTPUT_COLUMNS,
]


def rank_candidates(factor_df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    """Return ranked structured candidate rows from a factor DataFrame."""

    if top_n <= 0:
        raise ValueError("top_n must be positive.")
    scored = score_factors(factor_df)
    ranked = scored.sort_values(
        ["total_score", "confidence", "risk_score", "symbol"],
        ascending=[False, False, False, True],
    ).head(top_n).reset_index(drop=True)
    ranked.insert(0, "rank", range(1, len(ranked) + 1))
    return ranked.loc[:, RECOMMENDATION_OUTPUT_COLUMNS]
