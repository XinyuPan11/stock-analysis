from __future__ import annotations

import pandas as pd

from stock_analysis.research.scoring import COMPONENT_OUTPUT_COLUMNS, calculate_score_components


FACTOR_EXPLANATION_COLUMNS = COMPONENT_OUTPUT_COLUMNS


def explain_factor_contributions(factor_df: pd.DataFrame, *, symbol: str | None = None) -> pd.DataFrame:
    """Build per-factor contribution rows for score explainability."""

    components = calculate_score_components(factor_df)
    if symbol is not None:
        components = components[components["symbol"] == symbol].copy()
    if components.empty:
        return pd.DataFrame(columns=FACTOR_EXPLANATION_COLUMNS)
    return components.loc[:, FACTOR_EXPLANATION_COLUMNS].sort_values(
        ["symbol", "contribution", "factor_group"],
        ascending=[True, False, True],
    ).reset_index(drop=True)
