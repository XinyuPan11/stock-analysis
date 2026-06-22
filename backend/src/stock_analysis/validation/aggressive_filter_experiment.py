from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from stock_analysis.research.aggressive_filter_profiles import (
    AGGRESSIVE_SOURCE_FAMILIES,
    FORBIDDEN_FEATURE_COLUMNS,
    VALIDATION_STATUS_EXPLORATORY,
    VALIDATION_STATUS_INSUFFICIENT,
    AggressiveFilterProfile,
    FilterCriterion,
    all_filter_feature_columns,
    get_default_aggressive_filter_profiles,
)
from stock_analysis.research.strategy_profiles import StrategyFamilyProfile, get_default_strategy_family_profiles
from stock_analysis.validation.strategy_family_experiment import _load_list_payloads, _symbols_for_profile
from stock_analysis.validation.walk_forward import load_factor_rows_for_validation, sanitize_for_json


@dataclass(frozen=True)
class AggressiveFilterExperimentConfig:
    as_of_date: str
    horizon_days: int = 120
    outputs_dir: str | Path = "outputs"
    cache_dir: str | Path = "data/cache/daily-use"
    source_family_ids: tuple[str, ...] = AGGRESSIVE_SOURCE_FAMILIES
    filter_ids: tuple[str, ...] = ()
    dry_run: bool = True


def run_aggressive_filter_experiments(config: AggressiveFilterExperimentConfig) -> dict[str, object]:
    outputs_dir = Path(config.outputs_dir)
    filters = _select_filters(get_default_aggressive_filter_profiles(), config.filter_ids)
    _assert_no_future_feature_columns(filters)
    source_profiles = _select_source_profiles(get_default_strategy_family_profiles(), config.source_family_ids)
    predictions = _load_predictions(outputs_dir, config.as_of_date, config.horizon_days)
    features = _load_as_of_features(outputs_dir, config.as_of_date)
    list_payloads = _load_list_payloads(outputs_dir, config.as_of_date, source_profiles)
    baseline_metrics: dict[str, dict[str, object]] = {}
    results: list[dict[str, object]] = []

    for source_profile in source_profiles:
        symbols = _symbols_for_profile(source_profile, list_payloads)
        baseline = _evaluate_filtered_symbols(
            source_profile=source_profile,
            filter_profile=_baseline_filter(filters),
            symbols=symbols,
            filtered_symbols=symbols,
            future_labels=predictions,
            filter_notes=[],
            as_of_date=config.as_of_date,
            horizon_days=config.horizon_days,
        )
        baseline_metrics[source_profile.profile_id] = baseline
        for filter_profile in filters:
            filtered_symbols, filter_notes = apply_aggressive_filter(symbols, features, filter_profile)
            row = _evaluate_filtered_symbols(
                source_profile=source_profile,
                filter_profile=filter_profile,
                symbols=symbols,
                filtered_symbols=filtered_symbols,
                future_labels=predictions,
                filter_notes=filter_notes,
                as_of_date=config.as_of_date,
                horizon_days=config.horizon_days,
            )
            _add_relative_tail_metrics(row, baseline)
            results.append(row)

    context = _load_context(outputs_dir, config.as_of_date, config.horizon_days)
    summary = {
        "status": "dry_run" if config.dry_run else "ok",
        "as_of_date": config.as_of_date,
        "horizon_days": config.horizon_days,
        "dry_run": config.dry_run,
        "research_only": True,
        "production_scoring_replaced": False,
        "no_future_leakage": True,
        "anti_leakage_statement": (
            "Filters use as-of feature columns only. Future returns, future excess returns, drawdown during the future holding window, "
            "and benchmark outcomes are used only as labels/evaluation metrics after filtering."
        ),
        "disclaimer": "Research-only experiment. This is not investment advice and does not replace production scoring.",
        "source_family_count": len(source_profiles),
        "filter_count": len(filters),
        "result_count": len(results),
        "prediction_count": int(len(predictions)),
        "valid_prediction_count": int(_valid_predictions(predictions).shape[0]) if not predictions.empty else 0,
        "as_of_feature_count": int(len(features)),
        "feature_columns_used": sorted(all_filter_feature_columns(filters)),
        "forbidden_feature_columns": sorted(FORBIDDEN_FEATURE_COLUMNS),
        "validation_status_values": sorted({str(row.get("validation_status")) for row in results}),
        "cache_dir": str(config.cache_dir),
        "source_files": context["source_files"],
        "source_notes": context["source_notes"],
        "triple_barrier_note": "Optional path-based triple-barrier labels are supported by helper functions, but not generated without future price paths.",
    }
    result = {
        "summary": summary,
        "source_families": [profile.to_dict() for profile in source_profiles],
        "filters": [profile.to_dict() for profile in filters],
        "aggressive_filter_results": results,
        "source_context": context["source_context"],
        "outputs": {},
    }
    if not config.dry_run:
        result["outputs"] = write_aggressive_filter_experiment_outputs(config, result)
    return result


def apply_aggressive_filter(
    symbols: Iterable[str],
    as_of_features: pd.DataFrame,
    filter_profile: AggressiveFilterProfile,
) -> tuple[list[str], list[str]]:
    ordered_symbols = [str(symbol).strip() for symbol in symbols if str(symbol).strip()]
    if not filter_profile.criteria:
        return ordered_symbols, []
    notes: list[str] = []
    if as_of_features.empty or "symbol" not in as_of_features.columns:
        return [], ["missing_as_of_features"]
    features = as_of_features.drop_duplicates("symbol").set_index("symbol")
    eligible = features.reindex(ordered_symbols)
    active_mask = pd.Series(True, index=eligible.index)
    active_count = 0
    for criterion in filter_profile.criteria:
        if criterion.feature in FORBIDDEN_FEATURE_COLUMNS:
            raise ValueError(f"Filter criterion cannot use future/evaluation feature: {criterion.feature}")
        if criterion.feature not in eligible.columns:
            notes.append(f"missing_feature:{criterion.feature}")
            continue
        values = pd.to_numeric(eligible[criterion.feature], errors="coerce")
        missing_values = int(values.isna().sum())
        if missing_values:
            notes.append(f"missing_feature_values:{criterion.feature}:{missing_values}")
        active_mask &= _criterion_mask(values, criterion).fillna(False)
        active_count += 1
    if active_count == 0:
        notes.append("no_active_filter_criteria")
        return ordered_symbols, notes
    filtered = [symbol for symbol in ordered_symbols if bool(active_mask.get(symbol, False))]
    return filtered, notes


def write_aggressive_filter_experiment_outputs(config: AggressiveFilterExperimentConfig, result: dict[str, object]) -> dict[str, str]:
    experiments_dir = Path(config.outputs_dir) / "experiments"
    experiments_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"{config.as_of_date}_{config.horizon_days}d"
    json_path = experiments_dir / f"aggressive_filter_experiments_{suffix}.json"
    md_path = experiments_dir / f"aggressive_filter_experiments_{suffix}.md"
    json_path.write_text(json.dumps(sanitize_for_json(result), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    md_path.write_text(render_aggressive_filter_experiment_report(result), encoding="utf-8")
    return {"json": str(json_path), "report_md": str(md_path)}


def render_aggressive_filter_experiment_report(result: dict[str, object]) -> str:
    summary = result.get("summary", {})
    rows = result.get("aggressive_filter_results", [])
    lines = [
        "# Phase 2.8.3 Aggressive Filter Optimization Report",
        "",
        "Research-only experiment. This is not investment advice and does not replace production scoring.",
        "",
        "Anti-leakage statement: filters use as-of feature columns only. Future returns and benchmark outcomes are labels/evaluation metrics only.",
        "",
        f"- As-of date: {summary.get('as_of_date')}",
        f"- Horizon days: {summary.get('horizon_days')}",
        f"- Valid future labels: {summary.get('valid_prediction_count')}",
        f"- No future leakage: {summary.get('no_future_leakage')}",
        f"- Production scoring replaced: {summary.get('production_scoring_replaced')}",
        "",
        "## Baseline aggressive metrics",
        *_table(_baseline_rows(rows), ["source_strategy_family", "symbol_count_after_filter", "average_excess_return", "outperform_rate", "top_5_average_return", "failure_rate_below_minus_20pct"]),
        "",
        "## Filter comparison",
        *_table(rows, ["profile_id", "source_strategy_family", "filter_id", "symbol_count_after_filter", "average_excess_return", "outperform_rate", "payoff_ratio", "validation_status"]),
        "",
        "## Right-tail preservation",
        *_table(rows, ["profile_id", "source_strategy_family", "top_decile_average_return", "top_5_average_return", "best_case_return", "right_tail_preservation_ratio"]),
        "",
        "## Left-tail reduction",
        *_table(rows, ["profile_id", "source_strategy_family", "worst_case_return", "failure_rate_below_minus_10pct", "failure_rate_below_minus_20pct", "left_tail_reduction_ratio", "negative_return_rate"]),
        "",
        "## Payoff asymmetry check",
        *_table(rows, ["profile_id", "source_strategy_family", "payoff_ratio", "right_tail_ratio", "max_drawdown_average", "notes"]),
        "",
        "## Interpretation guardrails",
        "- Current same-period results are exploratory_same_period unless explicitly marked otherwise.",
        "- Right-tail preservation and left-tail reduction must be re-tested on additional as-of dates before any production scoring discussion.",
        "- Optional triple-barrier labels require future price paths and remain evaluation-only.",
        "",
        "## Next validation plan",
        "- Re-run on additional controlled 2024 as-of dates after cache coverage is expanded.",
        "- Keep aggressive families separate from conservative families during interpretation.",
        "- Promote no result beyond exploratory status until holdout validation exists.",
    ]
    return "\n".join(lines) + "\n"


def classify_triple_barrier_from_path(
    prices: Iterable[float],
    *,
    entry_price: float,
    upper_barrier: float,
    lower_barrier: float,
    max_holding_days: int,
) -> str:
    upper_price = entry_price * (1.0 + upper_barrier)
    lower_price = entry_price * (1.0 + lower_barrier)
    for index, price in enumerate(prices):
        if index >= max_holding_days:
            break
        if price >= upper_price:
            return "hit_upper_first"
        if price <= lower_price:
            return "hit_lower_first"
    return "timeout"


def _evaluate_filtered_symbols(
    *,
    source_profile: StrategyFamilyProfile,
    filter_profile: AggressiveFilterProfile,
    symbols: list[str],
    filtered_symbols: list[str],
    future_labels: pd.DataFrame,
    filter_notes: list[str],
    as_of_date: str,
    horizon_days: int,
) -> dict[str, object]:
    base = {
        "profile_id": f"{source_profile.profile_id}:{filter_profile.experiment_id}",
        "source_strategy_family": source_profile.profile_id,
        "filter_id": filter_profile.filter_id,
        "experiment_id": filter_profile.experiment_id,
        "as_of_date": as_of_date,
        "horizon_days": horizon_days,
        "symbol_count_before_filter": len(symbols),
        "symbol_count_after_filter": len(filtered_symbols),
        "valid_future_count": 0,
        "hit_rate": None,
        "average_future_return": None,
        "average_excess_return": None,
        "outperform_rate": None,
        "top_decile_average_return": None,
        "top_5_average_return": None,
        "best_case_return": None,
        "worst_case_return": None,
        "payoff_ratio": None,
        "right_tail_ratio": None,
        "max_drawdown_average": None,
        "failure_rate_below_minus_10pct": None,
        "failure_rate_below_minus_20pct": None,
        "negative_return_rate": None,
        "right_tail_preservation_ratio": None,
        "left_tail_reduction_ratio": None,
        "notes": [*filter_profile.notes, *filter_notes],
        "validation_status": filter_profile.validation_status,
    }
    if not symbols:
        return {**base, "notes": [*base["notes"], "empty_source_strategy_family"], "validation_status": VALIDATION_STATUS_INSUFFICIENT}
    if not filtered_symbols:
        return {**base, "notes": [*base["notes"], "empty_after_filter"], "validation_status": VALIDATION_STATUS_INSUFFICIENT}
    if future_labels.empty or "symbol" not in future_labels.columns:
        return {**base, "notes": [*base["notes"], "missing_future_labels"], "validation_status": VALIDATION_STATUS_INSUFFICIENT}
    valid = _valid_predictions(future_labels)
    rows = valid[valid["symbol"].astype(str).isin(filtered_symbols)].copy() if not valid.empty else pd.DataFrame()
    if rows.empty:
        return {**base, "notes": [*base["notes"], "no_matching_future_labels"], "validation_status": VALIDATION_STATUS_INSUFFICIENT}

    returns = pd.to_numeric(rows["future_return"], errors="coerce").dropna()
    rows = rows.loc[returns.index].copy()
    if rows.empty:
        return {**base, "notes": [*base["notes"], "no_numeric_future_return"], "validation_status": VALIDATION_STATUS_INSUFFICIENT}
    returns = pd.to_numeric(rows["future_return"], errors="coerce")
    excess = pd.to_numeric(rows["future_excess_return"], errors="coerce") if "future_excess_return" in rows.columns else pd.Series(dtype=float)
    drawdown = pd.to_numeric(rows["max_drawdown_during_holding"], errors="coerce") if "max_drawdown_during_holding" in rows.columns else pd.Series(dtype=float)
    sorted_returns = returns.sort_values(ascending=False)
    top_decile = _tail_average(sorted_returns, top=True)
    bottom_decile = _tail_average(sorted_returns, top=False)
    notes = [*base["notes"]]
    if len(rows) / len(filtered_symbols) < 0.8:
        notes.append("low_filtered_future_coverage")

    return {
        **base,
        "valid_future_count": int(len(rows)),
        "hit_rate": _rate(returns > 0),
        "average_future_return": _mean_or_none(returns),
        "average_excess_return": _mean_or_none(excess),
        "outperform_rate": _outperform_rate(rows),
        "top_decile_average_return": top_decile,
        "top_5_average_return": _mean_or_none(sorted_returns.head(5)),
        "best_case_return": _max_or_none(returns),
        "worst_case_return": _min_or_none(returns),
        "payoff_ratio": _payoff_ratio(returns),
        "right_tail_ratio": _right_tail_ratio(top_decile, bottom_decile),
        "max_drawdown_average": _mean_or_none(drawdown),
        "failure_rate_below_minus_10pct": _rate(returns <= -0.10),
        "failure_rate_below_minus_20pct": _rate(returns <= -0.20),
        "negative_return_rate": _rate(returns < 0),
        "notes": notes,
        "validation_status": VALIDATION_STATUS_EXPLORATORY,
    }


def _add_relative_tail_metrics(row: dict[str, object], baseline: dict[str, object]) -> None:
    row["right_tail_preservation_ratio"] = _safe_ratio(row.get("top_decile_average_return"), baseline.get("top_decile_average_return"))
    row["left_tail_reduction_ratio"] = _safe_ratio(row.get("failure_rate_below_minus_20pct"), baseline.get("failure_rate_below_minus_20pct"))


def _load_as_of_features(outputs_dir: Path, as_of_date: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    loaded = load_factor_rows_for_validation(outputs_dir, as_of_date)
    if not loaded.empty:
        frames.append(loaded)
    csv_path = outputs_dir / "daily" / f"factors_{as_of_date}.csv"
    if csv_path.exists():
        frames.append(_normalize_raw_factor_csv(pd.read_csv(csv_path)))
    if not frames:
        return pd.DataFrame()
    merged = frames[0].drop_duplicates("symbol").set_index("symbol")
    for frame in frames[1:]:
        if not frame.empty and "symbol" in frame.columns:
            merged = merged.combine_first(frame.drop_duplicates("symbol").set_index("symbol"))
    return merged.reset_index()


def _normalize_raw_factor_csv(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "symbol" not in frame.columns:
        return pd.DataFrame()
    result = pd.DataFrame({"symbol": frame["symbol"].astype(str)})
    aliases = {
        "volatility": ["volatility", "volatility_20d", "volatility_60d"],
        "drawdown": ["drawdown", "max_drawdown", "max_drawdown_20d", "max_drawdown_60d"],
        "amount": ["amount", "avg_amount_20d", "avg_amount_60d"],
        "volume": ["volume", "avg_volume_20d", "avg_volume_60d"],
    }
    for output_column, candidates in aliases.items():
        series = _first_available_numeric(frame, candidates)
        if series is not None:
            result[output_column] = series
    return result


def _load_predictions(outputs_dir: Path, as_of_date: str, horizon_days: int) -> pd.DataFrame:
    path = outputs_dir / "validation" / f"walk_forward_predictions_{as_of_date}_{horizon_days}d.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _load_context(outputs_dir: Path, as_of_date: str, horizon_days: int) -> dict[str, object]:
    paths = {
        "strategy_family_experiments": outputs_dir / "experiments" / f"strategy_family_experiments_{as_of_date}_{horizon_days}d.json",
        "list_performance": outputs_dir / "validation" / f"list_performance_{as_of_date}_{horizon_days}d.json",
        "factor_effectiveness": outputs_dir / "validation" / f"factor_effectiveness_{as_of_date}_{horizon_days}d.json",
        "portfolio_summary": outputs_dir / "portfolios" / f"portfolio_summary_{as_of_date}_{horizon_days}d.json",
    }
    source_files: dict[str, str] = {}
    notes: list[str] = []
    context: dict[str, object] = {}
    for key, path in paths.items():
        if not path.exists():
            notes.append(f"missing_{key}")
            context[key] = {}
            continue
        source_files[key] = str(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        context[key] = _summarize_context_payload(payload, key)
    return {"source_files": source_files, "source_notes": notes, "source_context": context}


def _summarize_context_payload(payload: object, key: str) -> dict[str, object]:
    if key == "strategy_family_experiments" and isinstance(payload, dict):
        rows = payload.get("strategy_family_results", [])
        return {
            "result_count": len(rows) if isinstance(rows, list) else 0,
            "baseline_profiles": [row.get("profile_id") for row in rows if isinstance(row, dict)][:20],
        }
    if isinstance(payload, list):
        return {"row_count": len(payload)}
    if isinstance(payload, dict):
        summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
        return {"keys": sorted(payload.keys()), "status": summary.get("status"), "benchmark_data_quality": summary.get("benchmark_data_quality")}
    return {}


def _select_filters(profiles: list[AggressiveFilterProfile], filter_ids: tuple[str, ...]) -> list[AggressiveFilterProfile]:
    if not filter_ids:
        return profiles
    wanted = set(filter_ids)
    return [profile for profile in profiles if profile.filter_id in wanted or profile.experiment_id in wanted]


def _select_source_profiles(profiles: list[StrategyFamilyProfile], source_family_ids: tuple[str, ...]) -> list[StrategyFamilyProfile]:
    wanted = set(source_family_ids or AGGRESSIVE_SOURCE_FAMILIES)
    return [profile for profile in profiles if profile.profile_id in wanted]


def _baseline_filter(filters: list[AggressiveFilterProfile]) -> AggressiveFilterProfile:
    for profile in filters:
        if profile.experiment_id == "baseline_aggressive":
            return profile
    return AggressiveFilterProfile("baseline_aggressive", "none", "Unfiltered baseline.")


def _assert_no_future_feature_columns(filters: list[AggressiveFilterProfile]) -> None:
    forbidden = all_filter_feature_columns(filters) & FORBIDDEN_FEATURE_COLUMNS
    if forbidden:
        raise ValueError(f"Aggressive filters cannot use future/evaluation columns: {sorted(forbidden)}")


def _valid_predictions(labels: pd.DataFrame) -> pd.DataFrame:
    if labels.empty or "data_quality" not in labels.columns or "future_return" not in labels.columns:
        return pd.DataFrame()
    frame = labels.copy()
    frame["future_return"] = pd.to_numeric(frame["future_return"], errors="coerce")
    return frame[(frame["data_quality"] == "ok") & frame["future_return"].notna()].copy()


def _criterion_mask(values: pd.Series, criterion: FilterCriterion) -> pd.Series:
    if criterion.operator == ">=":
        return values >= criterion.value
    if criterion.operator == "<=":
        return values <= criterion.value
    if criterion.operator == ">":
        return values > criterion.value
    if criterion.operator == "<":
        return values < criterion.value
    if criterion.operator == "abs<=":
        return values.abs() <= criterion.value
    raise ValueError(f"Unsupported filter criterion operator: {criterion.operator}")


def _tail_average(sorted_returns: pd.Series, *, top: bool) -> float | None:
    if sorted_returns.empty:
        return None
    count = max(1, int(math.ceil(len(sorted_returns) * 0.1)))
    values = sorted_returns.head(count) if top else sorted_returns.tail(count)
    return _mean_or_none(values)


def _payoff_ratio(returns: pd.Series) -> float | None:
    positive = returns[returns > 0]
    negative = returns[returns < 0]
    if positive.empty or negative.empty:
        return None
    denominator = abs(float(negative.mean()))
    return None if denominator == 0 else float(positive.mean()) / denominator


def _right_tail_ratio(top_decile_average: float | None, bottom_decile_average: float | None) -> float | None:
    if top_decile_average is None or bottom_decile_average is None:
        return None
    denominator = abs(float(bottom_decile_average))
    return None if denominator == 0 else float(top_decile_average) / denominator


def _outperform_rate(frame: pd.DataFrame) -> float | None:
    if "outperformed_benchmark" not in frame.columns:
        return None
    valid = frame["outperformed_benchmark"].dropna()
    if valid.empty:
        return None
    return float(valid.astype(bool).mean())


def _rate(mask: pd.Series) -> float | None:
    if mask.empty:
        return None
    return float(mask.astype(bool).mean())


def _mean_or_none(series: pd.Series) -> float | None:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return None
    return float(numeric.mean())


def _max_or_none(series: pd.Series) -> float | None:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    return None if numeric.empty else float(numeric.max())


def _min_or_none(series: pd.Series) -> float | None:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    return None if numeric.empty else float(numeric.min())


def _safe_ratio(numerator: object, denominator: object) -> float | None:
    try:
        top = float(numerator)
        bottom = float(denominator)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(top) or not math.isfinite(bottom) or bottom == 0:
        return None
    return top / bottom


def _first_available_numeric(frame: pd.DataFrame, candidates: list[str]) -> pd.Series | None:
    result: pd.Series | None = None
    for column in candidates:
        if column not in frame.columns:
            continue
        current = pd.to_numeric(frame[column], errors="coerce")
        result = current if result is None else result.combine_first(current)
    return result


def _baseline_rows(rows: object) -> list[dict[str, object]]:
    return [row for row in rows if isinstance(row, dict) and row.get("filter_id") == "none"] if isinstance(rows, list) else []


def _table(rows: list[dict[str, object]], columns: list[str]) -> list[str]:
    if not rows:
        return ["No rows available."]
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(_format_cell(row.get(column)) for column in columns) + " |")
    return lines


def _format_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value[:4])
    return str(value)
