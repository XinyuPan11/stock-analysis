from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from stock_analysis.data.cache import LocalCsvCache
from stock_analysis.data.schemas import (
    validate_market_data_frame,
    validate_stock_universe_frame,
)
from stock_analysis.research.pipeline import (
    ResearchPipelineConfig,
    run_research_pipeline,
)
from stock_analysis.validation.future_returns import benchmark_aliases


FORBIDDEN_ANSWER_KEY_DATES: tuple[str, ...] = (
    "2024-01-31",
    "2024-04-30",
    "2024-07-31",
    "2024-10-31",
)


@dataclass(frozen=True)
class CacheOnlyAsOfConfig:
    as_of_date: str
    outputs_dir: str | Path = "outputs"
    cache_dir: str | Path = "data\\cache\\daily-use"
    provider: str = "baostock"
    benchmark: str = "CSI300"
    limit: int = 300
    symbols_file: str | Path | None = None
    top_n: int = 20
    lookback_years: int = 1


class CacheOnlyDataMissingError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        missing_symbols: list[str] | None = None,
        benchmark_missing: bool = False,
        universe_missing: bool = False,
    ) -> None:
        super().__init__(message)
        self.missing_symbols = list(missing_symbols or [])
        self.benchmark_missing = bool(benchmark_missing)
        self.universe_missing = bool(universe_missing)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": "blocked_missing_cache",
            "cache_only": True,
            "provider_access": False,
            "error": str(self),
            "missing_cache_count": len(self.missing_symbols)
            + int(self.benchmark_missing)
            + int(self.universe_missing),
            "missing_symbols": self.missing_symbols,
            "benchmark_missing": self.benchmark_missing,
            "universe_missing": self.universe_missing,
        }


class CacheOnlyMarketDataService:
    """Read local CSV cache only and fail instead of invoking a provider."""

    def __init__(
        self,
        *,
        cache_dir: str | Path,
        provider: str,
        universe: pd.DataFrame,
    ) -> None:
        self.cache = LocalCsvCache(cache_dir=cache_dir)
        self.provider_name = str(provider)
        self._universe = validate_stock_universe_frame(universe)

    def get_stock_universe(self) -> pd.DataFrame:
        return self._universe.copy()

    def get_stock_daily(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjusted: bool = True,
    ) -> pd.DataFrame:
        details = self.cache.market_data_coverage_details(
            provider=self.provider_name,
            dataset="stock_daily",
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjusted=adjusted,
        )
        if not details["coverage_ok"]:
            raise CacheOnlyDataMissingError(
                f"Required stock cache is missing or incomplete for {symbol}.",
                missing_symbols=[symbol],
            )
        path = self.cache.market_data_path(
            provider=self.provider_name,
            dataset="stock_daily",
            symbol=symbol,
            adjusted=adjusted,
        )
        return _read_cache_with_future_rows(path, start_date=start_date)

    def get_index_daily(
        self,
        index_code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        resolved = self.resolve_benchmark_cache(index_code, start_date, end_date)
        if resolved is None:
            raise CacheOnlyDataMissingError(
                f"Required benchmark cache is missing or incomplete for {index_code}.",
                benchmark_missing=True,
            )
        _, path = resolved
        return _read_cache_with_future_rows(path, start_date=start_date)

    def missing_stock_cache(
        self,
        symbols: list[str],
        *,
        start_date: str,
        end_date: str,
    ) -> list[str]:
        return [
            symbol
            for symbol in symbols
            if not self.cache.has_market_data_coverage(
                provider=self.provider_name,
                dataset="stock_daily",
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                adjusted=True,
            )
        ]

    def resolve_benchmark_cache(
        self,
        benchmark: str,
        start_date: str,
        end_date: str,
    ) -> tuple[str, Path] | None:
        aliases = _dedupe([benchmark, *benchmark_aliases(benchmark)])
        for alias in aliases:
            for dataset, adjusted in (("index_daily", False), ("stock_daily", True)):
                if self.cache.has_market_data_coverage(
                    provider=self.provider_name,
                    dataset=dataset,
                    symbol=alias,
                    start_date=start_date,
                    end_date=end_date,
                    adjusted=adjusted,
                ):
                    return (
                        alias,
                        self.cache.market_data_path(
                            provider=self.provider_name,
                            dataset=dataset,
                            symbol=alias,
                            adjusted=adjusted,
                        ),
                    )
        return None


def generate_cache_only_asof_daily_outputs(
    config: CacheOnlyAsOfConfig,
    *,
    allow_forbidden_date_for_tests: bool = False,
) -> dict[str, Any]:
    as_of_date = validate_cache_only_asof_config(
        config,
        allow_forbidden_date_for_tests=allow_forbidden_date_for_tests,
    )
    cache_dir = Path(config.cache_dir)
    universe_path = cache_dir / config.provider / "stock_universe.csv"
    if not universe_path.exists():
        raise CacheOnlyDataMissingError(
            f"Required cached stock universe not found: {universe_path}",
            universe_missing=True,
        )
    universe = validate_stock_universe_frame(pd.read_csv(universe_path, dtype=str))
    selected = _select_universe(config, universe)
    symbols = selected["symbol"].astype(str).tolist()
    start_date = (
        pd.Timestamp(as_of_date) - pd.DateOffset(years=config.lookback_years)
    ).strftime("%Y-%m-%d")

    service = CacheOnlyMarketDataService(
        cache_dir=cache_dir,
        provider=config.provider,
        universe=selected,
    )
    missing_symbols = service.missing_stock_cache(
        symbols,
        start_date=start_date,
        end_date=as_of_date,
    )
    benchmark_cache = service.resolve_benchmark_cache(
        config.benchmark,
        start_date,
        as_of_date,
    )
    if missing_symbols or benchmark_cache is None:
        parts = []
        if missing_symbols:
            parts.append(f"{len(missing_symbols)} stock cache entries missing")
        if benchmark_cache is None:
            parts.append("benchmark cache missing")
        raise CacheOnlyDataMissingError(
            "Cache-only preflight failed: " + "; ".join(parts) + ".",
            missing_symbols=missing_symbols,
            benchmark_missing=benchmark_cache is None,
        )

    daily_output_dir = Path(config.outputs_dir) / "daily"
    result = run_research_pipeline(
        service,
        ResearchPipelineConfig(
            start_date=start_date,
            end_date=as_of_date,
            provider=config.provider,
            benchmark=config.benchmark,
            top_n=config.top_n,
            limit=len(selected),
            output_dir=daily_output_dir,
            error_output_dir=None,
            retry=0,
            symbol_timeout_seconds=None,
            min_successful_factor_rows=1,
        ),
    )
    summary = result.summary
    latest_input_date = summary.get("latest_input_date")
    if (
        not summary.get("leakage_guard_applied")
        or not latest_input_date
        or str(latest_input_date) > as_of_date
    ):
        raise RuntimeError("Point-in-time guard verification failed after cache-only generation.")

    resolved_benchmark, _ = benchmark_cache
    safety_metadata = {
        "provider_access": False,
        "cache_only": True,
        "provider_fallback_available": False,
        "as_of_date": as_of_date,
        "latest_input_date": latest_input_date,
        "max_raw_cache_date": summary.get("max_raw_cache_date"),
        "future_rows_excluded_count": int(
            summary.get("future_rows_excluded_count") or 0
        ),
        "point_in_time_guard_applied": True,
        "missing_cache_count": 0,
        "symbol_count": len(symbols),
        "benchmark_symbol": resolved_benchmark,
        "outcomes_inspected": False,
        "future_labels_calculated": False,
        "validation_outputs_generated": False,
        "performance_metrics_computed": False,
    }
    summary.update(safety_metadata)
    summary_path = Path(result.output_paths["summary_json"])
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return {
        "status": "ok",
        **safety_metadata,
        "output_paths": {
            key: value
            for key, value in result.output_paths.items()
            if key
            in {
                "candidates_csv",
                "candidates_json",
                "factors_csv",
                "factors_json",
                "factor_explanations_csv",
                "factor_explanations_json",
                "summary_json",
            }
        },
        "notes": [
            "Local cache only; no provider object or fetch callback is available.",
            "Physical cache rows after as_of_date are excluded by the point-in-time guard.",
            "No validation labels or performance conclusions are generated.",
        ],
    }


def validate_cache_only_asof_config(
    config: CacheOnlyAsOfConfig,
    *,
    allow_forbidden_date_for_tests: bool = False,
) -> str:
    try:
        as_of_date = date.fromisoformat(str(config.as_of_date)).isoformat()
    except ValueError as exc:
        raise ValueError(f"Invalid --date value: {config.as_of_date}") from exc
    if as_of_date in FORBIDDEN_ANSWER_KEY_DATES and not allow_forbidden_date_for_tests:
        raise ValueError(
            f"Forbidden answer-key date cannot be used for U1 generation: {as_of_date}"
        )
    if config.provider != "baostock":
        raise ValueError("Phase 2.21 cache-only path supports provider namespace baostock only.")
    if config.limit <= 0:
        raise ValueError("--limit must be positive.")
    if config.top_n <= 0:
        raise ValueError("--top-n must be positive.")
    if config.lookback_years <= 0:
        raise ValueError("--lookback-years must be positive.")
    return as_of_date


def _select_universe(
    config: CacheOnlyAsOfConfig,
    universe: pd.DataFrame,
) -> pd.DataFrame:
    if config.symbols_file is None:
        return universe.iloc[: config.limit].reset_index(drop=True)
    requested = _read_symbols_file(Path(config.symbols_file))
    if not requested:
        raise ValueError("--symbols-file is empty.")
    requested = requested[: config.limit]
    by_symbol = universe.set_index("symbol", drop=False)
    unknown = [symbol for symbol in requested if symbol not in by_symbol.index]
    if unknown:
        raise ValueError(
            "Symbols are missing from cached stock universe: " + ", ".join(unknown)
        )
    return pd.DataFrame([by_symbol.loc[symbol] for symbol in requested]).reset_index(
        drop=True
    )


def _read_symbols_file(path: Path) -> list[str]:
    if not path.exists():
        raise ValueError(f"--symbols-file does not exist: {path}")
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or "symbol" not in reader.fieldnames:
                raise ValueError("CSV --symbols-file must contain a symbol column.")
            return _dedupe(
                [
                    str(row.get("symbol", "")).strip()
                    for row in reader
                    if str(row.get("symbol", "")).strip()
                ]
            )
    return _dedupe(
        [
            line.strip()
            for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    )


def _read_cache_with_future_rows(path: Path, *, start_date: str) -> pd.DataFrame:
    frame = validate_market_data_frame(
        pd.read_csv(
            path,
            dtype={"symbol": str, "trade_date": str, "source": str},
        )
    )
    return frame[frame["trade_date"] >= start_date].reset_index(drop=True)


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result
