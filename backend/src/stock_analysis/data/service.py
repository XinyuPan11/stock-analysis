from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from stock_analysis.data.cache import LocalCsvCache
from stock_analysis.data.providers.base import MarketDataProvider, ProviderDataError
from stock_analysis.data.schemas import validate_market_data_frame, validate_stock_universe_frame


class MarketDataService:
    """Provider-independent market-data service used by upper layers."""

    def __init__(self, provider: MarketDataProvider, cache: LocalCsvCache | None = None) -> None:
        self.provider = provider
        self.cache = cache or LocalCsvCache()

    def get_stock_universe(self) -> pd.DataFrame:
        return self.cache.get_stock_universe(
            provider=self.provider.source,
            fetcher=lambda: self._provider_call("stock universe", self.provider.get_stock_universe),
        )

    def get_stock_daily(self, symbol: str, start_date: str, end_date: str, adjusted: bool = True) -> pd.DataFrame:
        return self.cache.get_market_data(
            provider=self.provider.source,
            dataset="stock_daily",
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjusted=adjusted,
            fetcher=lambda fetch_start, fetch_end: self._provider_call(
                f"stock daily {symbol} {fetch_start}..{fetch_end}",
                lambda: self.provider.get_stock_daily(
                    symbol=symbol,
                    start_date=fetch_start,
                    end_date=fetch_end,
                    adjusted=adjusted,
                ),
            ),
        )

    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        return self.cache.get_market_data(
            provider=self.provider.source,
            dataset="index_daily",
            symbol=index_code,
            start_date=start_date,
            end_date=end_date,
            adjusted=False,
            fetcher=lambda fetch_start, fetch_end: self._provider_call(
                f"index daily {index_code} {fetch_start}..{fetch_end}",
                lambda: self.provider.get_index_daily(
                    index_code=index_code,
                    start_date=fetch_start,
                    end_date=fetch_end,
                ),
            ),
        )

    def _provider_call(self, operation: str, call: Callable[[], pd.DataFrame]) -> pd.DataFrame:
        try:
            frame = call()
            if operation.startswith("stock universe"):
                return validate_stock_universe_frame(frame)
            return validate_market_data_frame(frame)
        except ProviderDataError:
            raise
        except Exception as exc:
            raise ProviderDataError(f"{self.provider.source} failed during {operation}: {exc}") from exc
