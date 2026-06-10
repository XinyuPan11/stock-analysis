from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class ProviderDataError(RuntimeError):
    """Raised when a market-data provider fails with a clear user-facing cause."""


class MarketDataProvider(ABC):
    """Base interface for replaceable market-data providers."""

    source: str

    @abstractmethod
    def get_stock_universe(self) -> pd.DataFrame:
        """Return normalized A-share stock universe."""

    @abstractmethod
    def get_stock_daily(self, symbol: str, start_date: str, end_date: str, adjusted: bool = True) -> pd.DataFrame:
        """Return normalized A-share stock daily bars."""

    @abstractmethod
    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Return normalized benchmark index daily bars."""
