from __future__ import annotations

import pandas as pd

from stock_analysis.data.cache import FileDataFrameCache
from stock_analysis.data.providers.base import MarketDataProvider
from stock_analysis.data.schemas import validate_market_data_frame


class MarketDataService:
    """Provider-independent market-data service used by analysis modules."""

    def __init__(self, provider: MarketDataProvider, cache: FileDataFrameCache | None = None) -> None:
        self.provider = provider
        self.cache = cache or FileDataFrameCache()

    def get_stock_daily(self, symbol: str, start_date: str, end_date: str, adjusted: bool = True) -> pd.DataFrame:
        key = (self.provider.source, "stock_daily", symbol, start_date, end_date, adjusted)
        return self.cache.get_or_fetch(
            key,
            lambda: validate_market_data_frame(
                self.provider.get_stock_daily(symbol=symbol, start_date=start_date, end_date=end_date, adjusted=adjusted)
            ),
        )

    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        key = (self.provider.source, "index_daily", index_code, start_date, end_date)
        return self.cache.get_or_fetch(
            key,
            lambda: validate_market_data_frame(
                self.provider.get_index_daily(index_code=index_code, start_date=start_date, end_date=end_date)
            ),
        )
