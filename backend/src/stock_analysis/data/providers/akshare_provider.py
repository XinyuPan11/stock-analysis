from __future__ import annotations

from typing import Any

import pandas as pd

from stock_analysis.data.constants import CORE_INDEX_CODES
from stock_analysis.data.providers.base import MarketDataProvider
from stock_analysis.data.schemas import normalize_market_data_frame


class AkShareProvider(MarketDataProvider):
    """AKShare provider adapter.

    Business logic should never import this class directly. Use the service
    layer and the normalized schema instead.
    """

    source = "akshare"

    def __init__(self, akshare_module: Any | None = None) -> None:
        if akshare_module is None:
            try:
                import akshare as akshare_module
            except ImportError as exc:
                raise ImportError("Install akshare to use AkShareProvider.") from exc
        self.ak = akshare_module

    def get_stock_daily(self, symbol: str, start_date: str, end_date: str, adjusted: bool = True) -> pd.DataFrame:
        raw = self.ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq" if adjusted else "",
        )
        return normalize_market_data_frame(
            raw,
            source=self.source,
            symbol=symbol,
            column_map={
                "trade_date": "日期",
                "open": "开盘",
                "high": "最高",
                "low": "最低",
                "close": "收盘",
                "volume": "成交量",
                "amount": "成交额",
                "adj_close": "收盘",
            },
        )

    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        provider_code = CORE_INDEX_CODES.get(index_code, {}).get("akshare", index_code)
        raw = self.ak.stock_zh_index_daily(symbol=provider_code)
        frame = normalize_market_data_frame(
            raw,
            source=self.source,
            symbol=index_code,
            column_map={
                "trade_date": "date",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume",
                "amount": "amount",
                "adj_close": "close",
            },
            allow_missing_amount=True,
        )
        return frame[(frame["trade_date"] >= start_date) & (frame["trade_date"] <= end_date)].reset_index(drop=True)
