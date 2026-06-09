from __future__ import annotations

from typing import Mapping

import pandas as pd


MARKET_DATA_COLUMNS = [
    "symbol",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "adj_close",
    "source",
]

NUMERIC_COLUMNS = ["open", "high", "low", "close", "volume", "amount", "adj_close"]


def normalize_market_data_frame(
    raw: pd.DataFrame,
    *,
    source: str,
    symbol: str,
    column_map: Mapping[str, str],
    allow_missing_amount: bool = False,
) -> pd.DataFrame:
    """Normalize provider-specific market data into the internal schema."""
    normalized = pd.DataFrame()
    for target_column in MARKET_DATA_COLUMNS:
        if target_column == "symbol":
            normalized[target_column] = [symbol] * len(raw)
            continue
        if target_column == "source":
            normalized[target_column] = [source] * len(raw)
            continue

        provider_column = column_map.get(target_column)
        if provider_column in raw.columns:
            normalized[target_column] = raw[provider_column]
        elif target_column == "amount" and allow_missing_amount:
            normalized[target_column] = 0
        elif target_column == "adj_close" and "close" in normalized:
            normalized[target_column] = normalized["close"]
        else:
            raise ValueError(f"Missing provider column for {target_column}: {provider_column}")

    normalized["trade_date"] = _normalize_trade_date(normalized["trade_date"])
    for column in NUMERIC_COLUMNS:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    return validate_market_data_frame(normalized)


def validate_market_data_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and order the internal market-data DataFrame schema."""
    missing = [column for column in MARKET_DATA_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Market data frame missing required columns: {missing}")

    ordered = frame.loc[:, MARKET_DATA_COLUMNS].copy()
    ordered["trade_date"] = _normalize_trade_date(ordered["trade_date"])
    for column in NUMERIC_COLUMNS:
        ordered[column] = pd.to_numeric(ordered[column], errors="coerce")

    if ordered[["symbol", "trade_date", "source"]].isna().any().any():
        raise ValueError("symbol, trade_date, and source are required.")
    if ordered[NUMERIC_COLUMNS].isna().any().any():
        raise ValueError("Numeric market data columns contain missing or non-numeric values.")

    return ordered.sort_values(["symbol", "trade_date"]).reset_index(drop=True)


def _normalize_trade_date(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series.astype(str), errors="coerce")
    if parsed.isna().any():
        raise ValueError("trade_date contains invalid date values.")
    return parsed.dt.strftime("%Y-%m-%d")
