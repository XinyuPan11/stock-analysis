from __future__ import annotations

import re

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
CRITICAL_COLUMNS = ["trade_date", "open", "high", "low", "close"]
PRICE_COLUMNS = ["open", "high", "low", "close", "adj_close"]
LIQUIDITY_COLUMNS = ["volume", "amount"]


class MarketDataQualityError(ValueError):
    """Raised when provider market data cannot be safely cleaned."""


def clean_market_data_frame(
    frame: pd.DataFrame,
    *,
    source: str,
    symbol: str,
    allow_missing_liquidity: bool = True,
) -> pd.DataFrame:
    """Clean normalized daily market data and classify unrecoverable issues.

    Critical price data must remain trustworthy. Liquidity fields may be filled
    with zero when missing so downstream factors penalize liquidity instead of
    crashing.
    """

    if frame is None or frame.empty:
        raise MarketDataQualityError("empty_market_data: provider returned no daily rows.")

    missing_critical = [column for column in CRITICAL_COLUMNS if column not in frame.columns]
    if missing_critical:
        raise MarketDataQualityError(f"missing_required_columns: {missing_critical}")

    cleaned = frame.copy()
    cleaned["symbol"] = symbol
    cleaned["source"] = source
    warnings: list[str] = []

    if "adj_close" not in cleaned.columns:
        cleaned["adj_close"] = cleaned["close"]
    for column in LIQUIDITY_COLUMNS:
        if column not in cleaned.columns:
            if allow_missing_liquidity:
                cleaned[column] = 0
                warnings.append("missing_liquidity_data")
            else:
                raise MarketDataQualityError(f"missing_required_columns: ['{column}']")

    parsed_dates = pd.to_datetime(cleaned["trade_date"].astype(str), errors="coerce")
    if parsed_dates.isna().any():
        raise MarketDataQualityError("missing_required_columns: invalid trade_date values.")
    cleaned["trade_date"] = parsed_dates.dt.strftime("%Y-%m-%d")

    for column in [*PRICE_COLUMNS, *LIQUIDITY_COLUMNS]:
        cleaned[column] = _to_numeric(cleaned[column])

    if cleaned[PRICE_COLUMNS].isna().any().any():
        raise MarketDataQualityError("non_numeric_market_data: critical price fields contain non-numeric values.")

    missing_liquidity = cleaned[LIQUIDITY_COLUMNS].isna().any().any()
    if missing_liquidity:
        if not allow_missing_liquidity:
            raise MarketDataQualityError("non_numeric_market_data: liquidity fields contain non-numeric values.")
        cleaned[LIQUIDITY_COLUMNS] = cleaned[LIQUIDITY_COLUMNS].fillna(0)
        warnings.append("missing_liquidity_data")

    if (
        (cleaned[["open", "high", "low", "close", "adj_close"]] <= 0).any().any()
        or (cleaned["high"] < cleaned["low"]).any()
        or (cleaned["close"] > cleaned["high"]).any()
        or (cleaned["close"] < cleaned["low"]).any()
    ):
        raise MarketDataQualityError("invalid_price_data: OHLC prices violate basic constraints.")

    result = cleaned.loc[:, MARKET_DATA_COLUMNS].drop_duplicates(["symbol", "trade_date"]).sort_values(
        ["symbol", "trade_date"]
    ).reset_index(drop=True)
    result.attrs["warnings"] = tuple(sorted(set(warnings)))
    return result


def _to_numeric(series: pd.Series) -> pd.Series:
    normalized = series.astype(str).map(_normalize_numeric_text)
    return pd.to_numeric(normalized, errors="coerce")


def _normalize_numeric_text(value: str) -> str:
    text = str(value).strip()
    if text.lower() in {"", "none", "nan", "null", "na", "n/a", "--", "-", "停牌"}:
        return ""
    return re.sub(r"[,\s]", "", text)
