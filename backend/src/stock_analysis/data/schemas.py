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

STOCK_UNIVERSE_COLUMNS = [
    "symbol",
    "name",
    "exchange",
    "listing_status",
    "source",
]

NUMERIC_MARKET_COLUMNS = ["open", "high", "low", "close", "volume", "amount", "adj_close"]


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

    return validate_market_data_frame(normalized)


def validate_market_data_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and order the internal market-data DataFrame schema."""
    missing = [column for column in MARKET_DATA_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Market data frame missing required columns: {missing}")

    ordered = frame.loc[:, MARKET_DATA_COLUMNS].copy()
    ordered["trade_date"] = _normalize_trade_date(ordered["trade_date"])
    for column in NUMERIC_MARKET_COLUMNS:
        ordered[column] = pd.to_numeric(ordered[column], errors="coerce")

    if ordered[["symbol", "trade_date", "source"]].isna().any().any():
        raise ValueError("symbol, trade_date, and source are required.")
    if ordered[NUMERIC_MARKET_COLUMNS].isna().any().any():
        raise ValueError("Numeric market data columns contain missing or non-numeric values.")

    return ordered.drop_duplicates(["symbol", "trade_date"]).sort_values(["symbol", "trade_date"]).reset_index(drop=True)


def normalize_stock_universe_frame(
    raw: pd.DataFrame,
    *,
    source: str,
    column_map: Mapping[str, str],
    default_listing_status: str = "listed",
) -> pd.DataFrame:
    """Normalize provider-specific A-share universe data into the internal schema."""
    normalized = pd.DataFrame()
    for target_column in STOCK_UNIVERSE_COLUMNS:
        if target_column == "source":
            normalized[target_column] = [source] * len(raw)
            continue
        if target_column == "listing_status" and target_column not in column_map:
            normalized[target_column] = [default_listing_status] * len(raw)
            continue

        provider_column = column_map.get(target_column)
        if provider_column in raw.columns:
            normalized[target_column] = raw[provider_column]
        elif target_column == "exchange" and "symbol" in normalized:
            normalized[target_column] = normalized["symbol"].map(infer_exchange)
        else:
            raise ValueError(f"Missing provider column for {target_column}: {provider_column}")

    return validate_stock_universe_frame(normalized)


def validate_stock_universe_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and order the internal A-share universe schema."""
    missing = [column for column in STOCK_UNIVERSE_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Stock universe frame missing required columns: {missing}")

    ordered = frame.loc[:, STOCK_UNIVERSE_COLUMNS].copy()
    for column in STOCK_UNIVERSE_COLUMNS:
        ordered[column] = ordered[column].astype(str).str.strip()

    if ordered[["symbol", "name", "exchange", "listing_status", "source"]].replace("", pd.NA).isna().any().any():
        raise ValueError("Stock universe contains empty required values.")

    return ordered.drop_duplicates(["symbol"]).sort_values("symbol").reset_index(drop=True)


def infer_exchange(symbol: object) -> str:
    """Infer mainland China exchange from an A-share symbol/code."""
    value = str(symbol).strip().lower()
    digits = value.split(".")[-1] if value.startswith(("sh.", "sz.", "bj.")) else value.split(".")[0]
    suffix = value.split(".")[-1].upper() if "." in value else ""

    if value.startswith("sh.") or suffix == "SH" or digits.startswith(("5", "6", "9")):
        return "SSE"
    if value.startswith("sz.") or suffix == "SZ" or digits.startswith(("0", "2", "3")):
        return "SZSE"
    if value.startswith("bj.") or suffix == "BJ" or digits.startswith(("4", "8")):
        return "BSE"
    return "UNKNOWN"


def _normalize_trade_date(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series.astype(str), errors="coerce")
    if parsed.isna().any():
        raise ValueError("trade_date contains invalid date values.")
    return parsed.dt.strftime("%Y-%m-%d")
