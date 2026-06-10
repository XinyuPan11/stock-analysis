from __future__ import annotations

from typing import Any

import pandas as pd

from stock_analysis.data.constants import CORE_INDEX_CODES
from stock_analysis.data.providers.base import MarketDataProvider, ProviderDataError
from stock_analysis.data.schemas import normalize_market_data_frame, normalize_stock_universe_frame


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

    def get_stock_universe(self) -> pd.DataFrame:
        login = self.bs.login()
        if getattr(login, "error_code", "0") != "0":
            raise ProviderDataError(f"BaoStock login failed: {getattr(login, 'error_msg', '')}")
        try:
            raw = self._query_all_stock_with_fallback()
        finally:
            self.bs.logout()

        if "code_name" not in raw.columns:
            raw["code_name"] = raw["code"]
        if "tradeStatus" not in raw.columns:
            raw["tradeStatus"] = "listed"

        return normalize_stock_universe_frame(
            raw,
            source=self.source,
            column_map={
                "symbol": "code",
                "name": "code_name",
                "listing_status": "tradeStatus",
            },
        )

    def get_stock_daily(self, symbol: str, start_date: str, end_date: str, adjusted: bool = True) -> pd.DataFrame:
        return self._query_daily(symbol=symbol, start_date=start_date, end_date=end_date, adjusted=adjusted)

    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        provider_code = CORE_INDEX_CODES.get(index_code, {}).get("baostock", index_code)
        return self._query_daily(
            symbol=provider_code,
            start_date=start_date,
            end_date=end_date,
            adjusted=False,
            output_symbol=index_code,
        )

    def _query_daily(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjusted: bool,
        output_symbol: str | None = None,
    ) -> pd.DataFrame:
        login = self.bs.login()
        if getattr(login, "error_code", "0") != "0":
            raise ProviderDataError(f"BaoStock login failed: {getattr(login, 'error_msg', '')}")

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
                raise ProviderDataError(f"BaoStock query_history_k_data_plus failed: {result.error_msg}")
            raw = pd.DataFrame(rows, columns=result.fields)
        finally:
            self.bs.logout()

        return normalize_market_data_frame(
            raw,
            source=self.source,
            symbol=output_symbol or symbol,
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

    def _query_all_stock_with_fallback(self) -> pd.DataFrame:
        attempts: list[str | None] = [None]
        today = pd.Timestamp.today().normalize()
        attempts.extend((today - pd.Timedelta(days=offset)).strftime("%Y-%m-%d") for offset in range(1, 15))

        last_error = ""
        for day in attempts:
            result = self.bs.query_all_stock(day=day) if day else self.bs.query_all_stock()
            if result.error_code != "0":
                last_error = f"{result.error_code} {result.error_msg}"
                continue

            rows: list[list[str]] = []
            while result.next():
                rows.append(result.get_row_data())
            raw = pd.DataFrame(rows, columns=result.fields)
            stocks = self._filter_ashare_stocks(raw)
            if not stocks.empty:
                return stocks

        raise ProviderDataError(f"BaoStock query_all_stock returned no A-share stocks. Last error: {last_error}")

    def _filter_ashare_stocks(self, raw: pd.DataFrame) -> pd.DataFrame:
        if "code" not in raw.columns:
            return raw
        code = raw["code"].astype(str).str.lower()
        mask = (
            code.str.startswith("sh.6")
            | code.str.startswith("sz.0")
            | code.str.startswith("sz.3")
            | code.str.startswith("bj.4")
            | code.str.startswith("bj.8")
        )
        return raw.loc[mask].reset_index(drop=True)
