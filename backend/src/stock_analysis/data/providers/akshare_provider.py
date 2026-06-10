from __future__ import annotations

from typing import Any

import pandas as pd

from stock_analysis.data.constants import CORE_INDEX_CODES
from stock_analysis.data.providers.base import MarketDataProvider
from stock_analysis.data.schemas import normalize_market_data_frame, normalize_stock_universe_frame


class AkShareProvider(MarketDataProvider):
    """AKShare provider adapter.

    Upper layers should use MarketDataService instead of importing this class
    directly.
    """

    source = "akshare"

    def __init__(self, akshare_module: Any | None = None) -> None:
        if akshare_module is None:
            try:
                import akshare as akshare_module
            except ImportError as exc:
                raise ImportError("Install akshare to use AkShareProvider.") from exc
        self.ak = akshare_module

    def get_stock_universe(self) -> pd.DataFrame:
        raw = self.ak.stock_info_a_code_name()
        symbol_column = _first_existing(raw, ["code", "symbol", "\u8bc1\u5238\u4ee3\u7801"])
        name_column = _first_existing(raw, ["name", "\u8bc1\u5238\u7b80\u79f0", "\u540d\u79f0"])
        return normalize_stock_universe_frame(
            raw,
            source=self.source,
            column_map={
                "symbol": symbol_column,
                "name": name_column,
            },
        )

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
                "trade_date": "\u65e5\u671f",
                "open": "\u5f00\u76d8",
                "high": "\u6700\u9ad8",
                "low": "\u6700\u4f4e",
                "close": "\u6536\u76d8",
                "volume": "\u6210\u4ea4\u91cf",
                "amount": "\u6210\u4ea4\u989d",
                "adj_close": "\u6536\u76d8",
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


def _first_existing(frame: pd.DataFrame, candidates: list[str]) -> str:
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    raise ValueError(f"None of the expected columns exist: {candidates}")
