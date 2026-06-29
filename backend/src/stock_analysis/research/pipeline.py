from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
import multiprocessing as mp
import queue
from pathlib import Path
import time
from typing import Protocol

import pandas as pd

from stock_analysis.data.point_in_time import PointInTimeSliceResult, slice_daily_as_of
from stock_analysis.research.ashare_filters import FilterConfig, FilterResult, filter_universe
from stock_analysis.research.factor_explanation import FACTOR_EXPLANATION_COLUMNS, explain_factor_contributions
from stock_analysis.research.factors import FACTOR_OUTPUT_COLUMNS, calculate_stock_factors
from stock_analysis.research.recommendation_engine import rank_candidates


CANDIDATE_OUTPUT_COLUMNS = [
    "rank",
    "symbol",
    "name",
    "as_of_date",
    "total_score",
    "label",
    "confidence",
    "momentum_score",
    "trend_score",
    "relative_strength_score",
    "risk_score",
    "liquidity_score",
    "positive_evidence",
    "negative_evidence",
    "risk_flags",
    "warnings",
    "source",
]


class MarketDataServiceLike(Protocol):
    def get_stock_universe(self) -> pd.DataFrame:
        ...

    def get_stock_daily(self, symbol: str, start_date: str, end_date: str, adjusted: bool = True) -> pd.DataFrame:
        ...

    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        ...


@dataclass(frozen=True)
class ResearchPipelineConfig:
    start_date: str
    end_date: str
    provider: str = ""
    benchmark: str = "CSI300"
    top_n: int = 20
    limit: int | None = None
    offset: int = 0
    batch_id: str = ""
    retry: int = 0
    output_dir: str | Path | None = None
    error_output_dir: str | Path | None = None
    adjusted: bool = True
    filter_config: FilterConfig | None = None
    progress_log_path: str | Path | None = None
    progress_every: int = 100
    symbol_timeout_seconds: float | None = 60.0
    max_consecutive_symbol_timeouts: int | None = None
    min_successful_factor_rows: int = 1


@dataclass(frozen=True)
class ResearchPipelineResult:
    candidates: pd.DataFrame
    factor_frame: pd.DataFrame
    factor_explanations: pd.DataFrame
    filtered_stocks: pd.DataFrame
    fetch_errors: list[dict[str, str]]
    summary: dict[str, object]
    output_paths: dict[str, str] = field(default_factory=dict)


def run_research_pipeline(service: MarketDataServiceLike, config: ResearchPipelineConfig) -> ResearchPipelineResult:
    """Run the Phase 1 daily research pipeline on a limited A-share sample."""

    _validate_config(config)
    progress = _progress_logger(config)
    progress("pipeline start", provider=config.provider, start_date=config.start_date, end_date=config.end_date, limit=config.limit)
    progress("stock universe loading start")
    universe = service.get_stock_universe()
    progress("stock universe loaded", universe_count=len(universe))
    limited_universe = _select_universe_batch(universe, config)
    progress("stock universe batch selected", offset=config.offset, selected_count=len(limited_universe), full_market=config.limit is None)
    if limited_universe.empty:
        progress("stock universe batch empty", universe_count=len(universe))
        result = _empty_result(universe_count=len(universe), output_dir=config.output_dir, as_of_date=config.end_date)
        progress("pipeline end", status="empty")
        return result

    daily_frames: list[pd.DataFrame] = []
    fetch_errors: list[dict[str, str]] = []
    consecutive_symbol_timeouts = 0
    timeout_stopped_early = False
    timeout_stop_reason = ""
    timeout_skipped_count = 0
    symbols = limited_universe["symbol"].astype(str).tolist()
    progress("cache coverage / loading start", symbol_count=len(symbols), progress_every=config.progress_every)
    for index, symbol in enumerate(symbols, start=1):
        debug_enabled = config.progress_every == 1
        symbol_timer = time.perf_counter()
        if debug_enabled:
            progress(
                "stock daily start",
                index=index,
                total=len(symbols),
                symbol=symbol,
            )
        debug = _cache_debug_state(service, symbol, config)
        if debug_enabled:
            progress(
                "stock daily cache state",
                index=index,
                total=len(symbols),
                symbol=symbol,
                **debug,
            )
        frame, error = _fetch_stock_daily_for_symbol(service, symbol, config, debug)
        elapsed = time.perf_counter() - symbol_timer
        row_count = 0 if frame is None else len(frame)
        if error:
            error.setdefault("index", str(index))
            error.setdefault("total", str(len(symbols)))
            error.setdefault("elapsed_seconds", str(round(elapsed, 4)))
            fetch_errors.append(error)
            if error.get("error_type") in {"symbol_timeout", "timeout"}:
                consecutive_symbol_timeouts += 1
            else:
                consecutive_symbol_timeouts = 0
        elif frame is not None:
            daily_frames.append(frame)
            consecutive_symbol_timeouts = 0
        if debug_enabled or error or elapsed > 10.0:
            event = "SYMBOL_TIMEOUT" if error and error.get("error_type") == "symbol_timeout" else "SLOW_SYMBOL" if elapsed > 10.0 else "stock daily end"
            coverage_ok = debug.get("coverage_ok", "unknown")
            fetch_attempted: object = not coverage_ok if isinstance(coverage_ok, bool) else "unknown"
            progress(
                event,
                index=index,
                total=len(symbols),
                symbol=symbol,
                elapsed_seconds=round(elapsed, 4),
                loaded_rows=row_count,
                stage=error.get("stage", "") if error else "",
                cache_hit=debug.get("cache_hit", "unknown"),
                coverage_ok=coverage_ok,
                fetch_attempted=fetch_attempted,
                error_type=error.get("error_type", "") if error else "",
                error_message=error.get("error", "") if error else "",
            )
        if _should_report_progress(index, len(symbols), config.progress_every):
            progress(
                "stock daily progress",
                processed=index,
                total=len(symbols),
                loaded_frames=len(daily_frames),
                fetch_errors=len(fetch_errors),
                last_symbol=symbol,
            )
        if (
            config.max_consecutive_symbol_timeouts is not None
            and consecutive_symbol_timeouts >= config.max_consecutive_symbol_timeouts
        ):
            timeout_stopped_early = True
            timeout_stop_reason = "max_consecutive_symbol_timeouts"
            timeout_skipped_count = max(0, len(symbols) - index)
            progress(
                "timeout protection stop",
                processed=index,
                total=len(symbols),
                consecutive_symbol_timeouts=consecutive_symbol_timeouts,
                skipped_count=timeout_skipped_count,
                max_consecutive_symbol_timeouts=config.max_consecutive_symbol_timeouts,
            )
            break

    all_daily = pd.concat(daily_frames, ignore_index=True) if daily_frames else pd.DataFrame()
    stock_guard = slice_daily_as_of(all_daily, config.end_date)
    all_daily = stock_guard.frame
    progress(
        "cache coverage / loading end",
        loaded_frames=len(daily_frames),
        rows=len(all_daily),
        fetch_errors=len(fetch_errors),
        stopped_early=timeout_stopped_early,
        skipped_count=timeout_skipped_count,
    )
    progress("benchmark loading start", benchmark=config.benchmark)
    benchmark_frame = _fetch_benchmark(service, config, fetch_errors)
    benchmark_guard = slice_daily_as_of(benchmark_frame, config.end_date)
    benchmark_frame = benchmark_guard.frame
    leakage_diagnostics = _combine_point_in_time_diagnostics(config.end_date, stock_guard, benchmark_guard)
    progress("benchmark loading end", rows=len(benchmark_frame), fetch_errors=len(fetch_errors))
    filter_config = config.filter_config or FilterConfig(as_of_date=config.end_date)
    progress("filtering start", universe_count=len(limited_universe), market_rows=len(all_daily))
    filter_result = filter_universe(
        limited_universe,
        all_daily,
        config=filter_config,
        benchmark_dates=benchmark_frame["trade_date"].tolist() if not benchmark_frame.empty else None,
    )
    progress(
        "filtering end",
        passed_count=len(filter_result.passed_universe),
        filtered_count=int(filter_result.stats.get("filtered_count", 0)),
        warnings=len(filter_result.warnings),
    )

    progress("factor calculation start", passed_count=len(filter_result.passed_universe))
    factors = _calculate_factors_for_passed(filter_result, all_daily, benchmark_frame, config, fetch_errors, progress)
    progress("factor calculation end", factor_rows=len(factors), fetch_errors=len(fetch_errors))
    progress("factor explanation start", factor_rows=len(factors))
    factor_explanations = explain_factor_contributions(factors) if not factors.empty else pd.DataFrame(columns=FACTOR_EXPLANATION_COLUMNS)
    progress("factor explanation end", explanation_rows=len(factor_explanations))
    progress("scoring start", factor_rows=len(factors), top_n=config.top_n)
    candidates = _rank_and_enrich_candidates(factors, limited_universe, config.top_n)
    progress("scoring end", candidate_count=len(candidates))
    progress("top N candidate generation", candidate_count=len(candidates), top_n=config.top_n)
    if config.output_dir:
        progress("output writing start", output_dir=str(Path(config.output_dir)))
    output_paths = (
        _write_data_outputs(candidates, factors, factor_explanations, config.output_dir, config.end_date)
        if config.output_dir
        else {}
    )
    if config.output_dir:
        progress("output writing end", output_files=len(output_paths))
    progress("summary building start")
    summary = _summary(
        config=config,
        universe_count=len(universe),
        filter_result=filter_result,
        attempted_count=len(limited_universe),
        successful_factor_count=len(factors),
        scored_count=len(candidates),
        fetch_errors=fetch_errors,
        output_paths=output_paths,
        warnings=list(filter_result.warnings),
        stopped_early=timeout_stopped_early,
        stop_reason=timeout_stop_reason,
        skipped_count=timeout_skipped_count,
        leakage_diagnostics=leakage_diagnostics,
    )
    progress("summary building end", fetch_error_count=len(fetch_errors), scored_count=len(candidates))
    if config.error_output_dir and fetch_errors:
        progress("fetch error writing start", error_count=len(fetch_errors), output_dir=str(Path(config.error_output_dir)))
        output_paths["failed_symbols_csv"] = _write_fetch_errors(fetch_errors, config.error_output_dir, config)
        summary["failed_symbols_path"] = output_paths["failed_symbols_csv"]
        summary["output_paths"] = output_paths
        progress("fetch error writing end", path=output_paths["failed_symbols_csv"])
    if config.output_dir:
        progress("summary writing start", output_dir=str(Path(config.output_dir)))
        summary["output_paths"] = output_paths
        summary["output_path"] = output_paths.get("candidates_csv", "")
        output_paths["summary_json"] = _write_summary(summary, config.output_dir, config.end_date)
        summary["output_paths"] = output_paths
        _write_summary(summary, config.output_dir, config.end_date)
        progress("summary writing end", path=output_paths["summary_json"])
    progress("pipeline end", status="ok", candidate_count=len(candidates), factor_rows=len(factors))
    return ResearchPipelineResult(
        candidates=candidates,
        factor_frame=factors,
        factor_explanations=factor_explanations,
        filtered_stocks=filter_result.filtered_stocks,
        fetch_errors=fetch_errors,
        summary=summary,
        output_paths=output_paths,
    )


def _fetch_benchmark(
    service: MarketDataServiceLike,
    config: ResearchPipelineConfig,
    fetch_errors: list[dict[str, str]],
) -> pd.DataFrame:
    try:
        return service.get_index_daily(config.benchmark, config.start_date, config.end_date)
    except Exception as exc:
        fetch_errors.append({"symbol": config.benchmark, "stage": "benchmark_daily", "error_type": _classify_error(str(exc)), "error": str(exc), "attempts": "1"})
        return pd.DataFrame()


def _fetch_stock_daily_for_symbol(
    service: MarketDataServiceLike,
    symbol: str,
    config: ResearchPipelineConfig,
    debug: dict[str, object],
) -> tuple[pd.DataFrame | None, dict[str, str] | None]:
    coverage_ok = debug.get("coverage_ok")
    needs_provider_fetch = isinstance(coverage_ok, bool) and not coverage_ok
    timeout_metadata = _service_timeout_metadata(service)
    if config.symbol_timeout_seconds and needs_provider_fetch and timeout_metadata:
        return _fetch_stock_daily_with_provider_timeout(
            service=service,
            symbol=symbol,
            config=config,
            timeout_metadata=timeout_metadata,
        )
    return _fetch_stock_daily_with_retry(service, symbol, config)


def _fetch_stock_daily_with_retry(
    service: MarketDataServiceLike,
    symbol: str,
    config: ResearchPipelineConfig,
) -> tuple[pd.DataFrame | None, dict[str, str] | None]:
    attempts = max(1, int(config.retry) + 1)
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return service.get_stock_daily(symbol, config.start_date, config.end_date, adjusted=config.adjusted), None
        except Exception as exc:
            last_error = exc
    error_text = str(last_error) if last_error else "unknown error"
    return None, {
        "symbol": symbol,
        "stage": "stock_daily",
        "error_type": _classify_error(error_text),
        "error": error_text,
        "attempts": str(attempts),
    }


def _fetch_stock_daily_with_provider_timeout(
    *,
    service: MarketDataServiceLike,
    symbol: str,
    config: ResearchPipelineConfig,
    timeout_metadata: dict[str, str],
) -> tuple[pd.DataFrame | None, dict[str, str] | None]:
    timeout_seconds = float(config.symbol_timeout_seconds or 0)
    attempts = max(1, int(config.retry) + 1)
    started = time.perf_counter()
    context = mp.get_context("spawn")
    result_queue = context.Queue(maxsize=1)
    process = context.Process(
        target=_provider_fetch_worker,
        args=(
            result_queue,
            timeout_metadata["provider"],
            symbol,
            config.start_date,
            config.end_date,
            config.adjusted,
            attempts,
        ),
    )
    process.daemon = True
    process.start()
    process.join(timeout_seconds)
    elapsed = time.perf_counter() - started

    if process.is_alive():
        process.terminate()
        process.join(timeout=5)
        return None, {
            "symbol": symbol,
            "stage": "provider_fetch",
            "error_type": "symbol_timeout",
            "error": f"Symbol fetch timed out after {timeout_seconds:.1f}s during provider_fetch.",
            "attempts": str(attempts),
            "elapsed_seconds": str(round(elapsed, 4)),
        }

    try:
        payload = result_queue.get_nowait()
    except queue.Empty:
        return None, {
            "symbol": symbol,
            "stage": "provider_fetch",
            "error_type": "provider_error",
            "error": f"Symbol fetch worker exited without a result. exitcode={process.exitcode}",
            "attempts": str(attempts),
            "elapsed_seconds": str(round(elapsed, 4)),
        }

    if payload.get("status") != "ok":
        error_text = str(payload.get("error", "unknown provider error"))
        return None, {
            "symbol": symbol,
            "stage": "provider_fetch",
            "error_type": _classify_error(error_text),
            "error": error_text,
            "attempts": str(payload.get("attempts", attempts)),
            "elapsed_seconds": str(round(elapsed, 4)),
        }

    fetched = pd.DataFrame(payload.get("records", []))
    if fetched.empty:
        return None, {
            "symbol": symbol,
            "stage": "provider_fetch",
            "error_type": "empty_market_data",
            "error": f"{config.provider} failed during stock daily {symbol} {config.start_date}..{config.end_date}: empty_market_data: provider returned no daily rows.",
            "attempts": str(attempts),
            "elapsed_seconds": str(round(elapsed, 4)),
        }

    cache = getattr(service, "cache")
    provider = timeout_metadata["provider"]

    def cached_fetcher(fetch_start: str, fetch_end: str) -> pd.DataFrame:
        return fetched[(fetched["trade_date"] >= fetch_start) & (fetched["trade_date"] <= fetch_end)].copy()

    try:
        frame = cache.get_market_data(
            provider=provider,
            dataset="stock_daily",
            symbol=symbol,
            start_date=config.start_date,
            end_date=config.end_date,
            adjusted=config.adjusted,
            fetcher=cached_fetcher,
        )
    except Exception as exc:
        error_text = str(exc)
        return None, {
            "symbol": symbol,
            "stage": "cache_loading",
            "error_type": _classify_error(error_text),
            "error": error_text,
            "attempts": str(attempts),
            "elapsed_seconds": str(round(time.perf_counter() - started, 4)),
        }
    return frame, None


def _provider_fetch_worker(
    result_queue,
    provider_name: str,
    symbol: str,
    start_date: str,
    end_date: str,
    adjusted: bool,
    attempts: int,
) -> None:
    try:
        provider = _build_provider_for_timeout(provider_name)
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                frame = provider.get_stock_daily(symbol=symbol, start_date=start_date, end_date=end_date, adjusted=adjusted)
                result_queue.put({"status": "ok", "records": frame.to_dict(orient="records"), "attempts": attempts})
                return
            except Exception as exc:
                last_error = exc
        result_queue.put({"status": "error", "error": str(last_error) if last_error else "unknown error", "attempts": attempts})
    except Exception as exc:
        result_queue.put({"status": "error", "error": str(exc), "attempts": attempts})


def _build_provider_for_timeout(provider_name: str):
    from stock_analysis.data.providers import AkShareProvider, BaoStockProvider, TushareProvider

    if provider_name == "akshare":
        return AkShareProvider()
    if provider_name == "baostock":
        return BaoStockProvider()
    if provider_name == "tushare":
        return TushareProvider()
    raise ValueError(f"Unsupported provider for symbol timeout: {provider_name}")


def _service_timeout_metadata(service: MarketDataServiceLike) -> dict[str, str] | None:
    provider = getattr(getattr(service, "provider", None), "source", "")
    cache = getattr(service, "cache", None)
    cache_dir = getattr(cache, "cache_dir", None)
    if not provider or cache_dir is None or not hasattr(cache, "get_market_data"):
        return None
    return {"provider": str(provider), "cache_dir": str(cache_dir)}


def _calculate_factors_for_passed(
    filter_result: FilterResult,
    all_daily: pd.DataFrame,
    benchmark_frame: pd.DataFrame,
    config: ResearchPipelineConfig,
    fetch_errors: list[dict[str, str]],
    progress,
) -> pd.DataFrame:
    if filter_result.passed_universe.empty or all_daily.empty:
        return pd.DataFrame(columns=FACTOR_OUTPUT_COLUMNS)

    passed_symbols = set(filter_result.passed_universe["symbol"].astype(str))
    total = len(passed_symbols)
    rows: list[pd.DataFrame] = []
    processed = 0
    for symbol, history in all_daily.groupby("symbol", sort=True):
        if str(symbol) not in passed_symbols:
            continue
        processed += 1
        try:
            rows.append(calculate_stock_factors(history, benchmark_frame, as_of_date=config.end_date))
        except Exception as exc:
            fetch_errors.append({"symbol": str(symbol), "stage": "factor_calculation", "error": str(exc)})
        if _should_report_progress(processed, total, config.progress_every):
            progress(
                "factor calculation progress",
                processed=processed,
                total=total,
                factor_rows=sum(len(row) for row in rows),
                fetch_errors=len(fetch_errors),
                last_symbol=str(symbol),
            )

    if not rows:
        return pd.DataFrame(columns=FACTOR_OUTPUT_COLUMNS)
    return pd.concat(rows, ignore_index=True).loc[:, FACTOR_OUTPUT_COLUMNS]


def _rank_and_enrich_candidates(factors: pd.DataFrame, universe: pd.DataFrame, top_n: int) -> pd.DataFrame:
    if factors.empty:
        return pd.DataFrame(columns=CANDIDATE_OUTPUT_COLUMNS)

    ranked = rank_candidates(factors, top_n=top_n)
    names = universe.loc[:, ["symbol", "name"]].drop_duplicates("symbol")
    enriched = ranked.merge(names, on="symbol", how="left")
    enriched["name"] = enriched["name"].fillna("")
    return enriched.loc[:, CANDIDATE_OUTPUT_COLUMNS]


def _write_data_outputs(
    candidates: pd.DataFrame,
    factors: pd.DataFrame,
    factor_explanations: pd.DataFrame,
    output_dir: str | Path,
    as_of_date: str,
) -> dict[str, str]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    safe_date = pd.Timestamp(as_of_date).strftime("%Y-%m-%d")
    paths = {
        "candidates_csv": output_path / f"candidates_{safe_date}.csv",
        "candidates_json": output_path / f"candidates_{safe_date}.json",
        "factors_csv": output_path / f"factors_{safe_date}.csv",
        "factors_json": output_path / f"factors_{safe_date}.json",
        "factor_explanations_csv": output_path / f"factor_explanations_{safe_date}.csv",
        "factor_explanations_json": output_path / f"factor_explanations_{safe_date}.json",
    }
    _write_frame(candidates, paths["candidates_csv"], paths["candidates_json"])
    _write_frame(factors, paths["factors_csv"], paths["factors_json"])
    _write_frame(factor_explanations, paths["factor_explanations_csv"], paths["factor_explanations_json"])
    return {key: str(path.resolve()) for key, path in paths.items()}


def _write_frame(frame: pd.DataFrame, csv_path: Path, json_path: Path) -> None:
    frame.to_csv(csv_path, index=False, encoding="utf-8-sig")
    json_path.write_text(json.dumps(frame.to_dict(orient="records"), ensure_ascii=False, indent=2), encoding="utf-8")


def _write_summary(summary: dict[str, object], output_dir: str | Path, as_of_date: str) -> str:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    safe_date = pd.Timestamp(as_of_date).strftime("%Y-%m-%d")
    summary_path = output_path / f"summary_{safe_date}.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(summary_path.resolve())


def _write_fetch_errors(fetch_errors: list[dict[str, str]], output_dir: str | Path, config: ResearchPipelineConfig) -> str:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    safe_date = pd.Timestamp(config.end_date).strftime("%Y-%m-%d")
    errors_path = path / f"failed_symbols_{safe_date}.csv"
    rows = [_error_output_row(error, config) for error in fetch_errors]
    pd.DataFrame(rows).to_csv(errors_path, index=False, encoding="utf-8-sig")
    return str(errors_path.resolve())


def _error_output_row(error: dict[str, str], config: ResearchPipelineConfig) -> dict[str, object]:
    error_type = error.get("error_type") or _classify_error(error.get("error", ""))
    return {
        "symbol": error.get("symbol", ""),
        "name": error.get("name", ""),
        "stage": error.get("stage", ""),
        "index": error.get("index", ""),
        "total": error.get("total", ""),
        "error_type": error_type,
        "error_message": error.get("error", ""),
        "elapsed_seconds": error.get("elapsed_seconds", ""),
        "provider": config.provider,
        "start_date": pd.Timestamp(config.start_date).strftime("%Y-%m-%d"),
        "end_date": pd.Timestamp(config.end_date).strftime("%Y-%m-%d"),
        "attempt_count": error.get("attempts", "1"),
        "last_attempt_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "can_retry": error_type in {"connection", "timeout", "symbol_timeout", "empty_market_data", "non_numeric_market_data", "provider_error"},
    }


def _summary(
    *,
    config: ResearchPipelineConfig,
    universe_count: int,
    filter_result: FilterResult,
    attempted_count: int,
    successful_factor_count: int,
    scored_count: int,
    fetch_errors: list[dict[str, str]],
    output_paths: dict[str, str],
    warnings: list[str],
    stopped_early: bool = False,
    stop_reason: str = "",
    skipped_count: int = 0,
    leakage_diagnostics: dict[str, object] | None = None,
) -> dict[str, object]:
    output_path = output_paths.get("candidates_csv") or output_paths.get("candidates_json") or ""
    timeout_count = sum(1 for error in fetch_errors if error.get("error_type") in {"symbol_timeout", "timeout"})
    partial_success = bool(stopped_early and successful_factor_count >= config.min_successful_factor_rows)
    guard = leakage_diagnostics or _empty_point_in_time_diagnostics(config.end_date)
    return {
        "status": "partial_timeout_protected" if stopped_early else "ok",
        "as_of_date": pd.Timestamp(config.end_date).strftime("%Y-%m-%d"),
        "latest_input_date": guard["latest_input_date"],
        "max_raw_cache_date": guard["max_raw_cache_date"],
        "future_rows_excluded_count": int(guard["future_rows_excluded_count"]),
        "leakage_guard_applied": bool(guard["leakage_guard_applied"]),
        "updated_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "provider": config.provider,
        "benchmark": config.benchmark,
        "start_date": pd.Timestamp(config.start_date).strftime("%Y-%m-%d"),
        "end_date": pd.Timestamp(config.end_date).strftime("%Y-%m-%d"),
        "offset": int(config.offset),
        "limit": config.limit,
        "full_market": config.limit is None,
        "batch_id": config.batch_id,
        "retry": int(config.retry),
        "universe_count": int(universe_count),
        "filtered_count": int(filter_result.stats.get("filtered_count", 0)),
        "attempted_count": int(attempted_count),
        "successful_factor_count": int(successful_factor_count),
        "valid_factor_rows": int(successful_factor_count),
        "scored_count": int(scored_count),
        "fetch_error_count": int(len(fetch_errors)),
        "timeout_count": int(timeout_count),
        "skipped_count": int(skipped_count),
        "stopped_early": bool(stopped_early),
        "stop_reason": stop_reason,
        "max_consecutive_symbol_timeouts": config.max_consecutive_symbol_timeouts,
        "min_successful_factor_rows": int(config.min_successful_factor_rows),
        "partial_success": partial_success,
        "failed_symbols_path": output_paths.get("failed_symbols_csv", ""),
        "fetch_errors": fetch_errors,
        "output_path": output_path,
        "output_paths": output_paths,
        "warnings": warnings,
    }


def _combine_point_in_time_diagnostics(
    as_of_date: str,
    *guards: PointInTimeSliceResult,
) -> dict[str, object]:
    latest_dates = [guard.latest_input_date for guard in guards if guard.latest_input_date]
    raw_dates = [guard.max_raw_cache_date for guard in guards if guard.max_raw_cache_date]
    return {
        "as_of_date": pd.Timestamp(as_of_date).strftime("%Y-%m-%d"),
        "latest_input_date": max(latest_dates) if latest_dates else None,
        "max_raw_cache_date": max(raw_dates) if raw_dates else None,
        "future_rows_excluded_count": sum(guard.future_rows_excluded_count for guard in guards),
        "leakage_guard_applied": True,
    }


def _empty_point_in_time_diagnostics(as_of_date: str) -> dict[str, object]:
    return {
        "as_of_date": pd.Timestamp(as_of_date).strftime("%Y-%m-%d"),
        "latest_input_date": None,
        "max_raw_cache_date": None,
        "future_rows_excluded_count": 0,
        "leakage_guard_applied": True,
    }


def _empty_result(universe_count: int, output_dir: str | Path | None, as_of_date: str) -> ResearchPipelineResult:
    candidates = pd.DataFrame(columns=CANDIDATE_OUTPUT_COLUMNS)
    factors = pd.DataFrame(columns=FACTOR_OUTPUT_COLUMNS)
    explanations = pd.DataFrame(columns=FACTOR_EXPLANATION_COLUMNS)
    empty_config = ResearchPipelineConfig(start_date=as_of_date, end_date=as_of_date)
    output_paths = _write_data_outputs(candidates, factors, explanations, output_dir, as_of_date) if output_dir else {}
    empty_filter = FilterResult(
        passed_universe=pd.DataFrame(),
        filtered_stocks=pd.DataFrame(),
        stats={"filtered_count": 0},
    )
    summary = _summary(
        config=empty_config,
        universe_count=universe_count,
        filter_result=empty_filter,
        attempted_count=0,
        successful_factor_count=0,
        scored_count=0,
        fetch_errors=[],
        output_paths=output_paths,
        warnings=[],
    )
    if output_dir:
        output_paths["summary_json"] = _write_summary(summary, output_dir, as_of_date)
        summary["output_paths"] = output_paths
        summary["output_path"] = output_paths.get("candidates_csv", "")
    return ResearchPipelineResult(
        candidates=candidates,
        factor_frame=factors,
        factor_explanations=explanations,
        filtered_stocks=pd.DataFrame(),
        fetch_errors=[],
        summary=summary,
        output_paths=output_paths,
    )


def _select_universe_batch(universe: pd.DataFrame, config: ResearchPipelineConfig) -> pd.DataFrame:
    if config.limit is None:
        return universe.iloc[config.offset :].reset_index(drop=True)
    return universe.iloc[config.offset : config.offset + config.limit].reset_index(drop=True)


def _cache_debug_state(service: MarketDataServiceLike, symbol: str, config: ResearchPipelineConfig) -> dict[str, object]:
    cache = getattr(service, "cache", None)
    provider = getattr(getattr(service, "provider", None), "source", config.provider)
    if cache is None or not hasattr(cache, "market_data_path"):
        return {
            "cache_hit": "unknown",
            "coverage_ok": "unknown",
            "cache_path": "",
            "coverage_path": "",
            "csv_exists": "unknown",
            "coverage_exists": "unknown",
        }
    try:
        cache_path = cache.market_data_path(
            provider=provider,
            dataset="stock_daily",
            symbol=symbol,
            adjusted=config.adjusted,
        )
        coverage_path = cache_path.with_suffix(".coverage.json")
        coverage_ok = bool(
            cache.has_market_data_coverage(
                provider=provider,
                dataset="stock_daily",
                symbol=symbol,
                start_date=config.start_date,
                end_date=config.end_date,
                adjusted=config.adjusted,
            )
        )
        return {
            "cache_hit": cache_path.exists() and coverage_ok,
            "coverage_ok": coverage_ok,
            "cache_path": str(cache_path),
            "coverage_path": str(coverage_path),
            "csv_exists": cache_path.exists(),
            "coverage_exists": coverage_path.exists(),
        }
    except Exception as exc:
        return {
            "cache_hit": "unknown",
            "coverage_ok": "unknown",
            "cache_path": "",
            "coverage_path": "",
            "csv_exists": "unknown",
            "coverage_exists": "unknown",
            "cache_debug_error": str(exc),
        }


def _classify_error(error: str) -> str:
    text = str(error).lower()
    if "numeric market data" in text or "non-numeric" in text:
        return "non_numeric_market_data"
    if "missing_required_columns" in text or "missing provider column" in text:
        return "missing_required_columns"
    if "invalid_price_data" in text or "ohlc" in text:
        return "invalid_price_data"
    if "empty" in text or "no data" in text:
        return "empty_market_data"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "connection" in text or "reset" in text or "proxy" in text:
        return "connection"
    return "provider_error"


def _validate_config(config: ResearchPipelineConfig) -> None:
    if config.top_n <= 0:
        raise ValueError("top_n must be positive.")
    if config.limit is not None and config.limit <= 0:
        raise ValueError("limit must be positive.")
    if config.offset < 0:
        raise ValueError("offset cannot be negative.")
    if config.retry < 0:
        raise ValueError("retry cannot be negative.")
    if config.progress_every <= 0:
        raise ValueError("progress_every must be positive.")
    if config.symbol_timeout_seconds is not None and config.symbol_timeout_seconds <= 0:
        raise ValueError("symbol_timeout_seconds must be positive when set.")
    if config.max_consecutive_symbol_timeouts is not None and config.max_consecutive_symbol_timeouts <= 0:
        raise ValueError("max_consecutive_symbol_timeouts must be positive when set.")
    if config.min_successful_factor_rows < 0:
        raise ValueError("min_successful_factor_rows cannot be negative.")
    start = pd.to_datetime(config.start_date, errors="coerce")
    end = pd.to_datetime(config.end_date, errors="coerce")
    if pd.isna(start) or pd.isna(end):
        raise ValueError("start_date and end_date must be valid dates.")
    if start > end:
        raise ValueError("start_date must be on or before end_date.")


def _progress_logger(config: ResearchPipelineConfig):
    path = Path(config.progress_log_path) if config.progress_log_path else None
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    def log(event: str, **fields: object) -> None:
        payload = " ".join(f"{key}={_format_progress_value(value)}" for key, value in fields.items())
        line = f"[{datetime.now().isoformat(timespec='seconds')}] {event}"
        if payload:
            line = f"{line} {payload}"
        print(line, flush=True)
        if path:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    return log


def _format_progress_value(value: object) -> str:
    if value is None:
        return "null"
    return str(value).replace("\n", " ")


def _should_report_progress(index: int, total: int, every: int) -> bool:
    return index == 1 or index == total or index % every == 0
