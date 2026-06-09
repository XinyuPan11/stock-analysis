from __future__ import annotations

import pandas as pd

from stock_analysis.data.schemas import validate_market_data_frame


def calculate_return_summary(frame: pd.DataFrame) -> dict[str, float | int | str]:
    """Calculate basic return statistics from the normalized market-data schema."""
    data = validate_market_data_frame(frame)
    if data.empty:
        return {
            "rows": 0,
            "first_trade_date": "",
            "last_trade_date": "",
            "total_return": 0.0,
            "max_drawdown": 0.0,
        }

    ordered = data.sort_values("trade_date").reset_index(drop=True)
    start_price = float(ordered.loc[0, "adj_close"])
    end_price = float(ordered.loc[len(ordered) - 1, "adj_close"])
    total_return = 0.0 if start_price == 0 else end_price / start_price - 1.0

    running_max = ordered["adj_close"].cummax()
    drawdown = ordered["adj_close"] / running_max - 1.0

    return {
        "rows": int(len(ordered)),
        "first_trade_date": str(ordered.loc[0, "trade_date"]),
        "last_trade_date": str(ordered.loc[len(ordered) - 1, "trade_date"]),
        "total_return": float(total_return),
        "max_drawdown": float(drawdown.min()),
    }
