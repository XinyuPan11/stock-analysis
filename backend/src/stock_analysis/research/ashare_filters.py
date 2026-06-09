from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import pandas as pd

from stock_analysis.data.schemas import MARKET_DATA_COLUMNS, NUMERIC_MARKET_COLUMNS, validate_stock_universe_frame


@dataclass(frozen=True)
class FilterConfig:
    """Configurable A-share candidate-pool filter thresholds."""

    as_of_date: str | None = None
    min_listing_days: int = 180
    history_window_days: int = 60
    min_valid_trading_days: int = 20
    liquidity_window_days: int = 20
    min_avg_amount_20d: float = 20_000_000.0
    max_missing_ratio: float = 0.2


@dataclass(frozen=True)
class StockFilterDecision:
    symbol: str
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.reasons


@dataclass(frozen=True)
class FilterResult:
    passed_universe: pd.DataFrame
    filtered_stocks: pd.DataFrame
    stats: dict[str, int]
    warnings: tuple[str, ...] = field(default_factory=tuple)


def filter_universe(
    universe: pd.DataFrame,
    daily_bars: pd.DataFrame,
    *,
    config: FilterConfig | None = None,
    benchmark_dates: Iterable[str] | None = None,
) -> FilterResult:
    """Filter the A-share universe before any factor, scoring, or report work."""

    resolved_config = config or FilterConfig()
    stocks = validate_stock_universe_frame(universe)
    bars = _safe_market_data(daily_bars)
    as_of_date = _resolve_as_of_date(resolved_config.as_of_date, bars)
    benchmark = _normalize_benchmark_dates(benchmark_dates)
    grouped = {symbol: history.copy() for symbol, history in bars.groupby("symbol")} if not bars.empty else {}

    decisions: list[StockFilterDecision] = []
    for _, row in stocks.iterrows():
        symbol = str(row["symbol"])
        history = grouped.get(symbol, pd.DataFrame(columns=MARKET_DATA_COLUMNS))
        decisions.append(_filter_one(row, history, as_of_date=as_of_date, config=resolved_config, benchmark_dates=benchmark))

    filtered_symbols = {decision.symbol for decision in decisions if not decision.passed}
    passed = stocks[~stocks["symbol"].isin(filtered_symbols)].reset_index(drop=True)
    filtered = _decisions_to_frame(stocks, decisions)
    warnings = tuple(sorted({warning for decision in decisions for warning in decision.warnings}))
    stats = _stats(stocks, filtered, decisions)
    return FilterResult(passed_universe=passed, filtered_stocks=filtered, stats=stats, warnings=warnings)


def filter_by_stock_status(stock: pd.Series) -> StockFilterDecision:
    """Filter ST, delisting-risk, and non-normal listing-status stocks."""

    reasons: list[str] = []
    symbol = str(stock.get("symbol", ""))
    name = str(stock.get("name", ""))

    if _truthy(stock.get("is_st", "")) or _looks_like_st_or_delisting_name(name):
        reasons.append("stock_status_risk")

    listing_status = str(stock.get("listing_status", "")).strip().lower()
    if listing_status and listing_status not in _NORMAL_LISTING_STATUSES:
        reasons.append("non_normal_listing_status")

    if _has_value(stock.get("delisting_date", "")) or _has_value(stock.get("out_date", "")):
        reasons.append("delisted_or_out_date_present")

    return StockFilterDecision(symbol=symbol, reasons=tuple(sorted(set(reasons))))


def filter_by_listing_age(stock: pd.Series, *, as_of_date: str, min_listing_days: int = 180) -> StockFilterDecision:
    """Filter newly listed stocks when listing date is available."""

    symbol = str(stock.get("symbol", ""))
    listing_date = _first_value(stock, ["listing_date", "ipo_date"])
    if not _has_value(listing_date):
        return StockFilterDecision(symbol=symbol, warnings=("listing_date_missing",))

    parsed_listing_date = pd.to_datetime(str(listing_date), errors="coerce")
    parsed_as_of_date = pd.to_datetime(as_of_date, errors="coerce")
    if pd.isna(parsed_listing_date):
        return StockFilterDecision(symbol=symbol, warnings=("listing_date_invalid",))
    if pd.isna(parsed_as_of_date):
        raise ValueError(f"Invalid as_of_date: {as_of_date}")

    age_days = int((parsed_as_of_date - parsed_listing_date).days)
    if age_days < min_listing_days:
        return StockFilterDecision(symbol=symbol, reasons=("listed_less_than_180_days",))
    return StockFilterDecision(symbol=symbol)


def filter_by_liquidity(
    symbol: str,
    history: pd.DataFrame,
    *,
    liquidity_window_days: int = 20,
    min_avg_amount_20d: float = 20_000_000.0,
) -> StockFilterDecision:
    """Filter low-liquidity stocks by recent average turnover amount."""

    if history.empty:
        return StockFilterDecision(symbol=symbol, reasons=("no_price_history",))

    tail = history.sort_values("trade_date").tail(liquidity_window_days)
    if len(tail) < liquidity_window_days:
        return StockFilterDecision(symbol=symbol, reasons=("insufficient_liquidity_window",))

    avg_amount = float(pd.to_numeric(tail["amount"], errors="coerce").mean())
    if pd.isna(avg_amount) or avg_amount < min_avg_amount_20d:
        return StockFilterDecision(symbol=symbol, reasons=("low_20d_average_amount",))
    return StockFilterDecision(symbol=symbol)


def filter_by_price_history_quality(
    symbol: str,
    history: pd.DataFrame,
    *,
    as_of_date: str,
    history_window_days: int = 60,
    min_valid_trading_days: int = 20,
    max_missing_ratio: float = 0.2,
    benchmark_dates: tuple[str, ...] = (),
) -> StockFilterDecision:
    """Filter suspended, sparse, missing, or structurally invalid daily bars."""

    if history.empty:
        return StockFilterDecision(symbol=symbol, reasons=("no_price_history",))

    window_start = (pd.Timestamp(as_of_date) - pd.Timedelta(days=history_window_days)).strftime("%Y-%m-%d")
    window = history[(history["trade_date"] >= window_start) & (history["trade_date"] <= as_of_date)].copy()

    reasons: list[str] = []
    warnings: list[str] = []
    if len(window) < min_valid_trading_days:
        reasons.append("insufficient_valid_trading_days")

    required = ["trade_date", "open", "high", "low", "close", "volume", "amount", "adj_close"]
    missing_ratio = float(window[required].isna().mean().max()) if not window.empty else 1.0
    if missing_ratio > max_missing_ratio:
        reasons.append("severe_missing_price_data")
    elif missing_ratio > 0:
        warnings.append("minor_missing_price_data")

    if not window.empty:
        numeric = window[["open", "high", "low", "close", "adj_close"]].apply(pd.to_numeric, errors="coerce")
        if (numeric <= 0).any().any():
            reasons.append("non_positive_price")
        if (numeric["high"] < numeric["low"]).any():
            reasons.append("high_lower_than_low")
        if ((numeric["close"] > numeric["high"]) | (numeric["close"] < numeric["low"])).any():
            reasons.append("close_outside_high_low")

    if benchmark_dates:
        available = set(window["trade_date"].astype(str))
        expected = {date for date in benchmark_dates if window_start <= date <= as_of_date}
        if expected:
            coverage = len(available & expected) / len(expected)
            if coverage < (1.0 - max_missing_ratio):
                reasons.append("low_benchmark_date_coverage")

    return StockFilterDecision(symbol=symbol, reasons=tuple(sorted(set(reasons))), warnings=tuple(sorted(set(warnings))))


def _filter_one(
    stock: pd.Series,
    history: pd.DataFrame,
    *,
    as_of_date: str,
    config: FilterConfig,
    benchmark_dates: tuple[str, ...],
) -> StockFilterDecision:
    symbol = str(stock["symbol"])
    return _merge_decisions(
        symbol,
        [
            filter_by_stock_status(stock),
            filter_by_listing_age(stock, as_of_date=as_of_date, min_listing_days=config.min_listing_days),
            filter_by_price_history_quality(
                symbol,
                history,
                as_of_date=as_of_date,
                history_window_days=config.history_window_days,
                min_valid_trading_days=config.min_valid_trading_days,
                max_missing_ratio=config.max_missing_ratio,
                benchmark_dates=benchmark_dates,
            ),
            filter_by_liquidity(
                symbol,
                history,
                liquidity_window_days=config.liquidity_window_days,
                min_avg_amount_20d=config.min_avg_amount_20d,
            ),
        ],
    )


def _merge_decisions(symbol: str, decisions: list[StockFilterDecision]) -> StockFilterDecision:
    reasons = tuple(sorted({reason for decision in decisions for reason in decision.reasons}))
    warnings = tuple(sorted({warning for decision in decisions for warning in decision.warnings}))
    return StockFilterDecision(symbol=symbol, reasons=reasons, warnings=warnings)


def _decisions_to_frame(stocks: pd.DataFrame, decisions: list[StockFilterDecision]) -> pd.DataFrame:
    by_symbol = {decision.symbol: decision for decision in decisions if not decision.passed}
    rows: list[dict[str, str]] = []
    for _, stock in stocks.iterrows():
        symbol = str(stock["symbol"])
        decision = by_symbol.get(symbol)
        if decision is None:
            continue
        rows.append(
            {
                "symbol": symbol,
                "name": str(stock.get("name", "")),
                "exchange": str(stock.get("exchange", "")),
                "reasons": ";".join(decision.reasons),
                "warnings": ";".join(decision.warnings),
            }
        )
    return pd.DataFrame(rows, columns=["symbol", "name", "exchange", "reasons", "warnings"])


def _stats(stocks: pd.DataFrame, filtered: pd.DataFrame, decisions: list[StockFilterDecision]) -> dict[str, int]:
    stats = {
        "input_count": int(len(stocks)),
        "passed_count": int(len(stocks) - len(filtered)),
        "filtered_count": int(len(filtered)),
        "warning_count": int(sum(1 for decision in decisions if decision.warnings)),
    }
    for decision in decisions:
        for reason in decision.reasons:
            stats[f"reason_{reason}"] = stats.get(f"reason_{reason}", 0) + 1
    return stats


def _safe_market_data(daily_bars: pd.DataFrame) -> pd.DataFrame:
    if daily_bars is None or daily_bars.empty:
        return pd.DataFrame(columns=MARKET_DATA_COLUMNS)
    missing = [column for column in MARKET_DATA_COLUMNS if column not in daily_bars.columns]
    if missing:
        raise ValueError(f"Daily bars missing required columns: {missing}")

    bars = daily_bars.loc[:, MARKET_DATA_COLUMNS].copy()
    parsed_dates = pd.to_datetime(bars["trade_date"].astype(str), errors="coerce")
    if parsed_dates.isna().any():
        raise ValueError("trade_date contains invalid date values.")
    bars["trade_date"] = parsed_dates.dt.strftime("%Y-%m-%d")
    for column in NUMERIC_MARKET_COLUMNS:
        bars[column] = pd.to_numeric(bars[column], errors="coerce")
    if bars[["symbol", "trade_date", "source"]].isna().any().any():
        raise ValueError("symbol, trade_date, and source are required.")
    return bars.drop_duplicates(["symbol", "trade_date"]).sort_values(["symbol", "trade_date"]).reset_index(drop=True)


def _resolve_as_of_date(as_of_date: str | None, bars: pd.DataFrame) -> str:
    if as_of_date:
        parsed = pd.to_datetime(as_of_date, errors="coerce")
        if pd.isna(parsed):
            raise ValueError(f"Invalid as_of_date: {as_of_date}")
        return parsed.strftime("%Y-%m-%d")
    if bars.empty:
        return pd.Timestamp.today().strftime("%Y-%m-%d")
    return str(bars["trade_date"].max())


def _normalize_benchmark_dates(benchmark_dates: Iterable[str] | None) -> tuple[str, ...]:
    if benchmark_dates is None:
        return ()
    parsed = pd.to_datetime(pd.Series(list(benchmark_dates)).astype(str), errors="coerce")
    if parsed.isna().any():
        raise ValueError("benchmark_dates contains invalid date values.")
    return tuple(parsed.dt.strftime("%Y-%m-%d").sort_values().tolist())


def _looks_like_st_or_delisting_name(name: str) -> bool:
    upper = name.upper()
    delisting_terms = ("\u9000", "\u9000\u5e02")
    return "*ST" in upper or upper.startswith("ST") or any(term in name for term in delisting_terms)


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "st", "*st"}


def _has_value(value: object) -> bool:
    return str(value).strip().lower() not in {"", "none", "nan", "nat"}


def _first_value(stock: pd.Series, columns: list[str]) -> object:
    for column in columns:
        if column in stock and _has_value(stock.get(column, "")):
            return stock.get(column)
    return ""


_NORMAL_LISTING_STATUSES = {
    "1",
    "l",
    "list",
    "listed",
    "normal",
    "active",
    "\u4e0a\u5e02",
    "\u6b63\u5e38",
    "\u6b63\u5e38\u4e0a\u5e02",
}
