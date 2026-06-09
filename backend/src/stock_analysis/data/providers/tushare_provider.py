from __future__ import annotations

import os
from typing import Any

import pandas as pd

from stock_analysis.data.constants import CORE_INDEX_CODES
from stock_analysis.data.providers.base import MarketDataProvider
from stock_analysis.data.schemas import normalize_market_data_frame


class TushareProvider(MarketDataProvider):
    """Tushare Pro provider adapter.

    Tushare is optional in version 1. It should remain behind this adapter so
    analysis code does not depend on Tushare-specific APIs or field names.
    """

    source = "tushare"

    def __init__(self, token: str | None = None, tushare_module: Any | None = None) -> None:
        if tushare_module is None:
            try:
                import tushare as tushare_module
            except ImportError as exc:
                raise ImportError("Install tushare to use TushareProvider.") from exc
        self.ts = tushare_module
        resolved_token = token or os.getenv("TUSHARE_TOKEN")
        if not resolved_token:
            raise ValueError("TushareProvider requires a token or TUSHARE_TOKEN environment variable.")
        self.pro = self.ts.pro_api(resolved_token)

    def get_stock_daily(self, symbol: str, start_date: str, end_date: str, adjusted: bool = True) -> pd.DataFrame:
        raw = self.pro.daily(
            ts_code=symbol,
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
        )
        frame = normalize_market_data_frame(
            raw,
            source=self.source,
            symbol=symbol,
            column_map={
                "trade_date": "trade_date",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "vol",
                "amount": "amount",
                "adj_close": "close",
            },
        )
        return frame.sort_values("trade_date").reset_index(drop=True)

    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        provider_code = CORE_INDEX_CODES.get(index_code, {}).get("tushare", index_code)
        raw = self.pro.index_daily(
            ts_code=provider_code,
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
        )
        frame = normalize_market_data_frame(
            raw,
            source=self.source,
            symbol=index_code,
            column_map={
                "trade_date": "trade_date",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "vol",
                "amount": "amount",
                "adj_close": "close",
            },
        )
        return frame.sort_values("trade_date").reset_index(drop=True)
