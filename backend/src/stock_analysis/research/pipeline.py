from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Protocol

import pandas as pd

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
    limit: int = 20
    output_dir: str | Path | None = None
    adjusted: bool = True
    filter_config: FilterConfig | None = None


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
    universe = service.get_stock_universe()
    limited_universe = universe.head(config.limit).reset_index(drop=True)
    if limited_universe.empty:
        result = _empty_result(universe_count=len(universe), output_dir=config.output_dir, as_of_date=config.end_date)
        return result

    daily_frames: list[pd.DataFrame] = []
    fetch_errors: list[dict[str, str]] = []
    for symbol in limited_universe["symbol"].astype(str).tolist():
        try:
            daily_frames.append(
                service.get_stock_daily(symbol, config.start_date, config.end_date, adjusted=config.adjusted)
            )
        except Exception as exc:
            fetch_errors.append({"symbol": symbol, "stage": "stock_daily", "error": str(exc)})

    all_daily = pd.concat(daily_frames, ignore_index=True) if daily_frames else pd.DataFrame()
    benchmark_frame = _fetch_benchmark(service, config, fetch_errors)
    filter_config = config.filter_config or FilterConfig(as_of_date=config.end_date)
    filter_result = filter_universe(
        limited_universe,
        all_daily,
        config=filter_config,
        benchmark_dates=benchmark_frame["trade_date"].tolist() if not benchmark_frame.empty else None,
    )

    factors = _calculate_factors_for_passed(filter_result, all_daily, benchmark_frame, config, fetch_errors)
    factor_explanations = explain_factor_contributions(factors) if not factors.empty else pd.DataFrame(columns=FACTOR_EXPLANATION_COLUMNS)
    candidates = _rank_and_enrich_candidates(factors, limited_universe, config.top_n)
    output_paths = (
        _write_data_outputs(candidates, factors, factor_explanations, config.output_dir, config.end_date)
        if config.output_dir
        else {}
    )
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
    )
    if config.output_dir:
        output_paths["summary_json"] = _write_summary(summary, config.output_dir, config.end_date)
        summary["output_paths"] = output_paths
        summary["output_path"] = output_paths.get("candidates_csv", "")
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
        fetch_errors.append({"symbol": config.benchmark, "stage": "benchmark_daily", "error": str(exc)})
        return pd.DataFrame()


def _calculate_factors_for_passed(
    filter_result: FilterResult,
    all_daily: pd.DataFrame,
    benchmark_frame: pd.DataFrame,
    config: ResearchPipelineConfig,
    fetch_errors: list[dict[str, str]],
) -> pd.DataFrame:
    if filter_result.passed_universe.empty or all_daily.empty:
        return pd.DataFrame(columns=FACTOR_OUTPUT_COLUMNS)

    passed_symbols = set(filter_result.passed_universe["symbol"].astype(str))
    rows: list[pd.DataFrame] = []
    for symbol, history in all_daily.groupby("symbol", sort=True):
        if str(symbol) not in passed_symbols:
            continue
        try:
            rows.append(calculate_stock_factors(history, benchmark_frame, as_of_date=config.end_date))
        except Exception as exc:
            fetch_errors.append({"symbol": str(symbol), "stage": "factor_calculation", "error": str(exc)})

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
) -> dict[str, object]:
    output_path = output_paths.get("candidates_csv") or output_paths.get("candidates_json") or ""
    return {
        "as_of_date": pd.Timestamp(config.end_date).strftime("%Y-%m-%d"),
        "updated_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "provider": config.provider,
        "benchmark": config.benchmark,
        "start_date": pd.Timestamp(config.start_date).strftime("%Y-%m-%d"),
        "end_date": pd.Timestamp(config.end_date).strftime("%Y-%m-%d"),
        "universe_count": int(universe_count),
        "filtered_count": int(filter_result.stats.get("filtered_count", 0)),
        "attempted_count": int(attempted_count),
        "successful_factor_count": int(successful_factor_count),
        "scored_count": int(scored_count),
        "fetch_error_count": int(len(fetch_errors)),
        "fetch_errors": fetch_errors,
        "output_path": output_path,
        "output_paths": output_paths,
        "warnings": warnings,
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


def _validate_config(config: ResearchPipelineConfig) -> None:
    if config.top_n <= 0:
        raise ValueError("top_n must be positive.")
    if config.limit <= 0:
        raise ValueError("limit must be positive.")
    start = pd.to_datetime(config.start_date, errors="coerce")
    end = pd.to_datetime(config.end_date, errors="coerce")
    if pd.isna(start) or pd.isna(end):
        raise ValueError("start_date and end_date must be valid dates.")
    if start > end:
        raise ValueError("start_date must be on or before end_date.")
