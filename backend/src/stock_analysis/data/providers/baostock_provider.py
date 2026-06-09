from __future__ import annotations

from typing import Any

import pandas as pd

from stock_analysis.data.constants import CORE_INDEX_CODES
from stock_analysis.data.providers.base import MarketDataProvider
from stock_analysis.data.schemas import normalize_market_data_frame


class BaoStockProvider(MarketDataProvider):
    """BaoStock provider adapter with normalized DataFrame output."""

    source = "baostock"

    def __init__(self, baostock_module: Any | None = None) -> None:
        if baostock_module is None:
            try:
                import baostock as baostock_module
            except ImportError as exc:
                raise ImportError("Install baostock to use BaoStockProvider.") from exc
        self.bs = baostock_module

    def get_stock_daily(self, symbol: str, start_date: str, end_date: str, adjusted: bool = True) -> pd.DataFrame:
        return self._query_daily(symbol=symbol, start_date=start_date, end_date=end_date, adjusted=adjusted)

    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        provider_code = CORE_INDEX_CODES.get(index_code, {}).get("baostock", index_code)
        return self._query_daily(symbol=provider_code, start_date=start_date, end_date=end_date, adjusted=False)

    def _query_daily(self, symbol: str, start_date: str, end_date: str, adjusted: bool) -> pd.DataFrame:
        login = self.bs.login()
        if getattr(login, "error_code", "0") != "0":
            raise RuntimeError(f"BaoStock login failed: {getattr(login, 'error_msg', '')}")

        try:
            result = self.bs.query_history_k_data_plus(
                symbol,
                "date,code,open,high,low,close,volume,amount",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="2" if adjusted else "3",
            )
            rows: list[list[str]] = []
            while result.error_code == "0" and result.next():
                rows.append(result.get_row_data())
            if result.error_code != "0":
                raise RuntimeError(f"BaoStock query failed: {result.error_msg}")
            raw = pd.DataFrame(rows, columns=result.fields)
        finally:
            self.bs.logout()

        return normalize_market_data_frame(
            raw,
            source=self.source,
            symbol=symbol,
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
        )
