from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from stock_analysis.research.strategy_profiles import StrategyFamilyProfile, get_default_strategy_family_profiles
from stock_analysis.validation.walk_forward import sanitize_for_json


@dataclass(frozen=True)
class StrategyFamilyExperimentConfig:
    as_of_date: str
    horizon_days: int = 120
    outputs_dir: str | Path = "outputs"
    cache_dir: str | Path = "data/cache/daily-use"
    profile_ids: tuple[str, ...] = ()
    dry_run: bool = True


def run_strategy_family_experiments(config: StrategyFamilyExperimentConfig) -> dict[str, object]:
    outputs_dir = Path(config.outputs_dir)
    profiles = _select_profiles(get_default_strategy_family_profiles(), config.profile_ids)
    predictions = _load_predictions(outputs_dir, config.as_of_date, config.horizon_days)
    list_payloads = _load_list_payloads(outputs_dir, config.as_of_date, profiles)
    context = _load_context(outputs_dir, config.as_of_date, config.horizon_days)

    results = [
        evaluate_strategy_family(profile, list_payloads, predictions, as_of_date=config.as_of_date, horizon_days=config.horizon_days)
        for profile in profiles
    ]
    summary = {
        "status": "dry_run" if config.dry_run else "ok",
        "as_of_date": config.as_of_date,
        "horizon_days": config.horizon_days,
        "dry_run": config.dry_run,
        "research_only": True,
        "no_future_leakage": True,
        "disclaimer": "Research-only experiment. This is not investment advice and does not replace production scoring.",
        "profile_count": len(results),
        "prediction_count": int(len(predictions)),
        "valid_prediction_count": int(_valid_predictions(predictions).shape[0]) if not predictions.empty else 0,
        "cache_dir": str(config.cache_dir),
        "source_files": context["source_files"],
        "source_notes": context["source_notes"],
    }
    result = {
        "summary": summary,
        "profiles": [profile.to_dict() for profile in profiles],
        "strategy_family_results": results,
        "source_context": context["source_context"],
        "outputs": {},
    }
    if not config.dry_run:
        result["outputs"] = write_strategy_family_experiment_outputs(config, result)
    return result


def evaluate_strategy_family(
    profile: StrategyFamilyProfile,
    list_payloads: dict[str, dict[str, object]],
    future_labels: pd.DataFrame | Iterable[dict[str, object]],
    *,
    as_of_date: str,
    horizon_days: int,
) -> dict[str, object]:
    labels = _to_frame(future_labels)
    symbols = _symbols_for_profile(profile, list_payloads)
    base = {
        "profile_id": profile.profile_id,
        "family_type": profile.family_type,
        "objective": profile.objective,
        "as_of_date": as_of_date,
        "horizon_days": horizon_days,
        "source_list_ids": list(profile.source_list_ids),
        "symbol_count": len(symbols),
        "valid_future_count": 0,
        "hit_rate": None,
        "average_future_return": None,
        "average_excess_return": None,
        "outperform_rate": None,
        "win_rate": None,
        "top_decile_average_return": None,
        "bottom_decile_average_return": None,
        "top_5_average_return": None,
        "best_case_return": None,
        "worst_case_return": None,
        "payoff_ratio": None,
        "right_tail_ratio": None,
        "max_drawdown_average": None,
        "failure_rate_below_minus_10pct": None,
        "failure_rate_below_minus_20pct": None,
        "negative_return_rate": None,
        "stability_score": None,
        "best_cases": [],
        "worst_cases": [],
        "notes": list(profile.notes),
    }
    if not symbols:
        return {**base, "notes": [*base["notes"], "empty_strategy_family"]}
    if labels.empty or "symbol" not in labels.columns:
        return {**base, "notes": [*base["notes"], "missing_future_labels"]}

    valid = _valid_predictions(labels)
    if valid.empty:
        return {**base, "notes": [*base["notes"], "no_valid_future_labels"]}
    rows = valid[valid["symbol"].astype(str).isin(symbols)].copy()
    if rows.empty:
        return {**base, "notes": [*base["notes"], "no_matching_future_labels"]}

    returns = pd.to_numeric(rows["future_return"], errors="coerce").dropna()
    if returns.empty:
        return {**base, "notes": [*base["notes"], "no_numeric_future_return"]}
    rows = rows.loc[returns.index].copy()
    returns = pd.to_numeric(rows["future_return"], errors="coerce")
    excess = pd.to_numeric(rows["future_excess_return"], errors="coerce") if "future_excess_return" in rows.columns else pd.Series(dtype=float)
    drawdown = pd.to_numeric(rows["max_drawdown_during_holding"], errors="coerce") if "max_drawdown_during_holding" in rows.columns else pd.Series(dtype=float)
    sorted_returns = returns.sort_values(ascending=False)
    top_decile = _tail_average(sorted_returns, top=True)
    bottom_decile = _tail_average(sorted_returns, top=False)
    notes = [*base["notes"]]
    if len(rows) / len(symbols) < 0.8:
        notes.append("low_strategy_future_coverage")

    return {
        **base,
        "valid_future_count": int(len(rows)),
        "hit_rate": _rate(returns > 0),
        "average_future_return": _mean_or_none(returns),
        "average_excess_return": _mean_or_none(excess),
        "outperform_rate": _outperform_rate(rows),
        "win_rate": _rate(returns > 0),
        "top_decile_average_return": top_decile,
        "bottom_decile_average_return": bottom_decile,
        "top_5_average_return": _mean_or_none(sorted_returns.head(5)),
        "best_case_return": _max_or_none(returns),
        "worst_case_return": _min_or_none(returns),
        "payoff_ratio": _payoff_ratio(returns),
        "right_tail_ratio": _right_tail_ratio(top_decile, bottom_decile),
        "max_drawdown_average": _mean_or_none(drawdown),
        "failure_rate_below_minus_10pct": _rate(returns <= -0.10),
        "failure_rate_below_minus_20pct": _rate(returns <= -0.20),
        "negative_return_rate": _rate(returns < 0),
        "stability_score": _stability_score(returns, rows, drawdown),
        "best_cases": _case_rows(rows.sort_values("future_return", ascending=False).head(5)),
        "worst_cases": _case_rows(rows.sort_values("future_return", ascending=True).head(5)),
        "notes": notes,
    }


def write_strategy_family_experiment_outputs(config: StrategyFamilyExperimentConfig, result: dict[str, object]) -> dict[str, str]:
    experiments_dir = Path(config.outputs_dir) / "experiments"
    experiments_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"{config.as_of_date}_{config.horizon_days}d"
    json_path = experiments_dir / f"strategy_family_experiments_{suffix}.json"
    md_path = experiments_dir / f"strategy_family_experiments_{suffix}.md"
    json_path.write_text(json.dumps(sanitize_for_json(result), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    md_path.write_text(render_strategy_family_experiment_report(result), encoding="utf-8")
    return {"json": str(json_path), "report_md": str(md_path)}


def render_strategy_family_experiment_report(result: dict[str, object]) -> str:
    summary = result.get("summary", {})
    rows = result.get("strategy_family_results", [])
    conservative = [row for row in rows if row.get("family_type") == "conservative"]
    aggressive = [row for row in rows if row.get("family_type") == "aggressive"]
    right_tail = [row for row in rows if row.get("family_type") == "right_tail"]
    risk = [row for row in rows if row.get("family_type") == "risk_filter"]
    lines = [
        "# Phase 2.8.2 Strategy Family Experiment Report",
        "",
        "Research-only experiment. This is not investment advice and does not replace production scoring.",
        "",
        f"- As-of date: {summary.get('as_of_date')}",
        f"- Horizon days: {summary.get('horizon_days')}",
        f"- Valid future labels: {summary.get('valid_prediction_count')}",
        f"- No future leakage: {summary.get('no_future_leakage')}",
        "",
        "## Conservative strategy results",
        *_table(conservative, ["profile_id", "average_excess_return", "outperform_rate", "win_rate", "max_drawdown_average", "negative_return_rate", "stability_score"]),
        "",
        "## Aggressive strategy results",
        *_table(aggressive, ["profile_id", "hit_rate", "average_future_return", "average_excess_return", "top_decile_average_return", "payoff_ratio", "failure_rate_below_minus_20pct"]),
        "",
        "## Right-tail opportunity results",
        *_table(right_tail, ["profile_id", "hit_rate", "top_5_average_return", "best_case_return", "right_tail_ratio", "worst_case_return"]),
        "",
        "## Failure/risk analysis",
        *_table([*aggressive, *right_tail, *risk], ["profile_id", "max_drawdown_average", "failure_rate_below_minus_10pct", "failure_rate_below_minus_20pct", "worst_case_return"]),
        "",
        "## Recommended next experiments",
        "- Compare the same families across more controlled 2024 as-of dates before changing production scoring.",
        "- Keep aggressive families separate from conservative families and judge them with right-tail and failure metrics.",
        "- Expand cache and symbol coverage where future-label coverage is low.",
    ]
    return "\n".join(lines) + "\n"


def _select_profiles(profiles: list[StrategyFamilyProfile], profile_ids: tuple[str, ...]) -> list[StrategyFamilyProfile]:
    if not profile_ids:
        return profiles
    wanted = set(profile_ids)
    return [profile for profile in profiles if profile.profile_id in wanted]


def _load_predictions(outputs_dir: Path, as_of_date: str, horizon_days: int) -> pd.DataFrame:
    path = outputs_dir / "validation" / f"walk_forward_predictions_{as_of_date}_{horizon_days}d.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _load_list_payloads(outputs_dir: Path, as_of_date: str, profiles: Iterable[StrategyFamilyProfile]) -> dict[str, dict[str, object]]:
    list_ids = sorted({list_id for profile in profiles for list_id in profile.source_list_ids})
    payloads: dict[str, dict[str, object]] = {}
    for list_id in list_ids:
        path = outputs_dir / "lists" / f"{list_id}_{as_of_date}.json"
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            payloads[list_id] = payload if isinstance(payload, dict) else {"list_id": list_id, "items": [], "notes": ["invalid_list_payload"]}
        else:
            payloads[list_id] = {"list_id": list_id, "as_of_date": as_of_date, "items": [], "notes": ["missing_list_file"]}
    return payloads


def _load_context(outputs_dir: Path, as_of_date: str, horizon_days: int) -> dict[str, object]:
    paths = {
        "list_performance": outputs_dir / "validation" / f"list_performance_{as_of_date}_{horizon_days}d.json",
        "factor_effectiveness": outputs_dir / "validation" / f"factor_effectiveness_{as_of_date}_{horizon_days}d.json",
        "portfolio_summary": outputs_dir / "portfolios" / f"portfolio_summary_{as_of_date}_{horizon_days}d.json",
    }
    context: dict[str, object] = {}
    notes: list[str] = []
    source_files: dict[str, str] = {}
    for key, path in paths.items():
        if path.exists():
            source_files[key] = str(path)
            context[key] = _summarize_source_payload(json.loads(path.read_text(encoding="utf-8")), key)
        else:
            notes.append(f"missing_{key}")
            context[key] = {}
    return {"source_files": source_files, "source_notes": notes, "source_context": context}


def _summarize_source_payload(payload: object, key: str) -> object:
    if isinstance(payload, list):
        return {"row_count": len(payload), "ids": [str(row.get("list_id") or row.get("factor_name") or "") for row in payload if isinstance(row, dict)][:20]}
    if isinstance(payload, dict) and key == "portfolio_summary":
        summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
        portfolios = payload.get("portfolios", []) if isinstance(payload.get("portfolios"), list) else []
        return {
            "status": summary.get("status"),
            "benchmark_symbol": summary.get("benchmark_symbol"),
            "benchmark_data_quality": summary.get("benchmark_data_quality"),
            "portfolio_count": len(portfolios),
        }
    if isinstance(payload, dict):
        return {"keys": sorted(payload.keys())}
    return {}


def _symbols_for_profile(profile: StrategyFamilyProfile, list_payloads: dict[str, dict[str, object]]) -> list[str]:
    symbols: list[str] = []
    for list_id in profile.source_list_ids:
        payload = list_payloads.get(list_id, {})
        items = payload.get("items", []) if isinstance(payload, dict) else []
        for item in items if isinstance(items, list) else []:
            if isinstance(item, dict) and item.get("symbol"):
                symbol = str(item["symbol"]).strip()
                if symbol and symbol not in symbols:
                    symbols.append(symbol)
    return symbols


def _valid_predictions(labels: pd.DataFrame) -> pd.DataFrame:
    if labels.empty or "data_quality" not in labels.columns or "future_return" not in labels.columns:
        return pd.DataFrame()
    frame = labels.copy()
    frame["future_return"] = pd.to_numeric(frame["future_return"], errors="coerce")
    return frame[(frame["data_quality"] == "ok") & frame["future_return"].notna()].copy()


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


def _stability_score(returns: pd.Series, rows: pd.DataFrame, drawdown: pd.Series) -> float | None:
    if returns.empty:
        return None
    win_rate = _rate(returns > 0) or 0.0
    outperform = _outperform_rate(rows)
    outperform_score = 0.0 if outperform is None else float(outperform)
    negative_score = 1.0 - (_rate(returns < 0) or 0.0)
    avg_drawdown = _mean_or_none(drawdown)
    drawdown_score = 0.0 if avg_drawdown is None else max(0.0, min(1.0, 1.0 - abs(float(avg_drawdown)) / 0.30))
    return float((win_rate + outperform_score + negative_score + drawdown_score) / 4.0)


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


def _case_rows(frame: pd.DataFrame) -> list[dict[str, object]]:
    columns = ["symbol", "future_return", "future_excess_return", "outperformed_benchmark", "max_drawdown_during_holding", "data_quality"]
    existing = [column for column in columns if column in frame.columns]
    return sanitize_for_json(frame.loc[:, existing].to_dict(orient="records"))


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
    return str(value)


def _to_frame(value: pd.DataFrame | Iterable[dict[str, object]]) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    return pd.DataFrame(list(value))

