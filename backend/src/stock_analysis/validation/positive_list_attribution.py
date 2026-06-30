"""Read-only attribution for weak positive-list validation performance."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Iterable

import pandas as pd


DEFAULT_WINDOWS: tuple[tuple[str, int], ...] = (
    ("2024-01-31", 20),
    ("2024-04-30", 20),
    ("2024-07-31", 20),
    ("2024-10-31", 20),
)
DEFAULT_LIST_IDS: tuple[str, ...] = (
    "high_confidence_candidates",
    "trend_leaders",
    "long_term_stable",
    "breakout_watch",
    "accumulation_watch",
)
SUMMARY_JSON_NAME = "positive_list_weakness_attribution_2024.json"
SUMMARY_MARKDOWN_NAME = "positive_list_weakness_attribution_2024.md"
DISCLAIMER = (
    "Research-only positive-list attribution. This report compares existing "
    "list memberships and validation labels; it does not change production "
    "scoring, rankings, factors, labels, or recommendations."
)


@dataclass(frozen=True)
class PositiveListAttributionConfig:
    outputs_dir: str | Path = "outputs"
    windows: tuple[tuple[str, int], ...] = DEFAULT_WINDOWS
    list_ids: tuple[str, ...] = DEFAULT_LIST_IDS
    warning_quantile: float = 0.20
    min_variant_sample: int = 5


def build_positive_list_attribution(
    config: PositiveListAttributionConfig,
) -> dict[str, Any]:
    outputs_dir = Path(config.outputs_dir)
    windows: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    factor_context_rows: list[dict[str, Any]] = []
    source_files: list[str] = []

    for as_of_date, horizon_days in config.windows:
        suffix = f"{as_of_date}_{horizon_days}d"
        predictions_path = (
            outputs_dir / "validation" / f"walk_forward_predictions_{suffix}.csv"
        )
        high_risk_path = (
            outputs_dir / "lists" / f"high_risk_active_{as_of_date}.json"
        )
        missing = [
            str(path)
            for path in (predictions_path, high_risk_path)
            if not path.exists()
        ]
        list_paths = {
            list_id: outputs_dir / "lists" / f"{list_id}_{as_of_date}.json"
            for list_id in config.list_ids
        }
        missing.extend(str(path) for path in list_paths.values() if not path.exists())
        if missing:
            excluded.append(
                {
                    "as_of_date": as_of_date,
                    "horizon_days": horizon_days,
                    "status": "missing_required_membership_or_predictions",
                    "missing_files": sorted(set(missing)),
                }
            )
            continue

        predictions = pd.read_csv(predictions_path, dtype={"symbol": str})
        frame, availability, exposure_paths = _member_attribution_frame(
            outputs_dir,
            predictions,
            as_of_date,
        )
        high_risk_symbols = _load_ordered_symbols(high_risk_path)
        warning_sets, thresholds = _warning_sets(
            frame,
            high_risk_symbols,
            config.warning_quantile,
            availability,
        )
        benchmark_return = _series_median(_numeric(frame, "benchmark_return"))
        list_rows = []
        for list_id, path in list_paths.items():
            symbols = _load_ordered_symbols(path)
            list_rows.append(
                _build_list_window_attribution(
                    frame,
                    symbols,
                    list_id=list_id,
                    high_risk_symbols=set(high_risk_symbols),
                    warning_sets=warning_sets,
                    availability=availability,
                )
            )

        factor_context_path = (
            outputs_dir / "validation" / f"factor_effectiveness_{suffix}.json"
        )
        factor_context = _load_factor_context(
            factor_context_path, as_of_date, horizon_days
        )
        factor_context_rows.extend(factor_context)
        windows.append(
            {
                "as_of_date": as_of_date,
                "horizon_days": horizon_days,
                "prediction_count": int(len(predictions)),
                "valid_prediction_count": int(len(frame)),
                "benchmark_return": benchmark_return,
                "benchmark_regime": _benchmark_regime(benchmark_return),
                "member_factor_availability": availability,
                "warning_thresholds": thresholds,
                "factor_context": factor_context,
                "lists": list_rows,
            }
        )
        source_files.extend(
            [
                str(predictions_path),
                str(high_risk_path),
                *(str(path) for path in list_paths.values()),
                *(str(path) for path in exposure_paths),
            ]
        )
        if factor_context_path.exists():
            source_files.append(str(factor_context_path))

    variant_summary = _aggregate_variants(
        windows, min_variant_sample=config.min_variant_sample
    )
    factor_summary = _aggregate_factor_context(factor_context_rows)
    high_risk_exclusion = _high_risk_exclusion_summary(variant_summary)
    availability_summary = _availability_summary(windows)

    return _json_safe(
        {
            "summary": {
                "status": "ok" if windows else "insufficient_data",
                "research_only": True,
                "provider_access": False,
                "cache_fetch_executed": False,
                "labels_recomputed": False,
                "production_scoring_changed": False,
                "production_recommendations_changed": False,
                "included_window_count": len(windows),
                "excluded_window_count": len(excluded),
                "warning_quantile": config.warning_quantile,
                "min_variant_sample": config.min_variant_sample,
                "disclaimer": DISCLAIMER,
            },
            "window_attribution": windows,
            "variant_stability": variant_summary,
            "high_risk_exclusion_summary": high_risk_exclusion,
            "factor_context_summary": factor_summary,
            "member_factor_availability": availability_summary,
            "excluded_windows": excluded,
            "interpretation": [
                "Variant results are exploratory diagnostics built from existing memberships and labels.",
                "Improvement after an exclusion identifies a risk-aware construction hypothesis, not a production rule.",
                "Benchmark regime and factor-sign instability must remain visible when comparing windows.",
                "No production scoring or recommendation change is supported by this report alone.",
            ],
            "source_files": sorted(set(source_files)),
            "outputs": {},
        }
    )


def write_positive_list_attribution_outputs(
    report: dict[str, Any],
    outputs_dir: str | Path,
) -> dict[str, str]:
    experiments_dir = Path(outputs_dir) / "experiments"
    experiments_dir.mkdir(parents=True, exist_ok=True)
    json_path = experiments_dir / SUMMARY_JSON_NAME
    markdown_path = experiments_dir / SUMMARY_MARKDOWN_NAME
    report["outputs"] = {
        "json": str(json_path),
        "markdown": str(markdown_path),
    }
    json_path.write_text(
        json.dumps(_json_safe(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_positive_list_attribution_markdown(report),
        encoding="utf-8",
    )
    return report["outputs"]


def render_positive_list_attribution_markdown(
    report: dict[str, Any],
) -> str:
    summary = report["summary"]
    lines = [
        "# Controlled Positive-List Weakness Attribution",
        "",
        str(summary["disclaimer"]),
        "",
        "## Window Context",
        "",
        "| As-of date | Valid predictions | Benchmark return | Regime | Member factors available |",
        "|---|---:|---:|---|---|",
    ]
    for row in report.get("window_attribution", []):
        available = [
            key for key, value in row["member_factor_availability"].items() if value
        ]
        lines.append(
            f"| {row['as_of_date']} | {row['valid_prediction_count']} | "
            f"{_fmt(row.get('benchmark_return'))} | {row['benchmark_regime']} | "
            f"{', '.join(available) or 'none'} |"
        )

    lines.extend(
        [
            "",
            "## Variant Stability",
            "",
            "| List | Variant | Windows | Sample min | Avg excess | Delta vs original | Improved windows | Sign | Classification |",
            "|---|---|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for row in report.get("variant_stability", []):
        lines.append(
            f"| {row['list_id']} | {row['variant_id']} | "
            f"{row['valid_window_count']} | {_fmt(row.get('sample_count_min'))} | "
            f"{_fmt(row.get('average_excess_return_mean'))} | "
            f"{_fmt(row.get('average_excess_delta_mean'))} | "
            f"{row['improved_window_count']} | "
            f"{row['excess_sign_consistency']} | {row['classification']} |"
        )

    lines.extend(["", "## High-Risk Exclusion", ""])
    high_risk = report.get("high_risk_exclusion_summary", {})
    lines.append(
        f"- Lists improved on average: `{high_risk.get('improved_list_count', 0)}`."
    )
    lines.append(
        "- Improved list IDs: "
        + (", ".join(high_risk.get("improved_list_ids", [])) or "none")
        + "."
    )
    lines.append(
        "- Interpretation: "
        + str(
            high_risk.get(
                "interpretation",
                "Insufficient data for high-risk exclusion attribution.",
            )
        )
    )

    lines.extend(
        [
            "",
            "## Factor Context",
            "",
            "| Factor | Windows | Spread mean | Positive/negative windows | Sign |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for row in report.get("factor_context_summary", []):
        lines.append(
            f"| {row['factor_name']} | {row['valid_window_count']} | "
            f"{_fmt(row.get('spread_mean'))} | "
            f"{row['positive_spread_window_count']}/{row['negative_spread_window_count']} | "
            f"{row['spread_sign_consistency']} |"
        )

    lines.extend(["", "## Availability And Limitations", ""])
    availability = report.get("member_factor_availability", {})
    for key, value in availability.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "- Percentile exclusions are same-window diagnostics, not fixed production thresholds.",
            "- Positive lists can overlap with each other; each list is evaluated independently.",
            "- Historical industry, sector, and market-cap attribution remains unavailable.",
            "",
            "## Interpretation Boundary",
            "",
        ]
    )
    for item in report.get("interpretation", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def _member_attribution_frame(
    outputs_dir: Path,
    predictions: pd.DataFrame,
    as_of_date: str,
) -> tuple[pd.DataFrame, dict[str, bool], list[Path]]:
    frame = predictions.drop_duplicates(subset=["symbol"], keep="first").copy()
    frame["symbol"] = frame["symbol"].astype(str)
    if "data_quality" in frame.columns:
        frame = frame[frame["data_quality"].astype(str) == "ok"].copy()

    factors_path = outputs_dir / "daily" / f"factors_{as_of_date}.csv"
    labels_path = outputs_dir / "labels" / f"stock_labels_{as_of_date}.csv"
    paths = [path for path in (factors_path, labels_path) if path.exists()]

    factor_aliases = {
        "volatility": "volatility_20d",
        "historical_drawdown": "max_drawdown_20d",
        "amount": "avg_amount_20d",
        "volume": "avg_volume_20d",
    }
    if factors_path.exists():
        factors = pd.read_csv(factors_path, dtype={"symbol": str})
        selected = ["symbol"]
        rename = {}
        for output_name, source_name in factor_aliases.items():
            if source_name in factors.columns:
                selected.append(source_name)
                rename[source_name] = output_name
        factors = factors.loc[:, selected].rename(columns=rename)
        frame = frame.merge(factors, on="symbol", how="left")

    label_columns = ("total_score", "risk_score", "liquidity_score")
    if labels_path.exists():
        labels = pd.read_csv(labels_path, dtype={"symbol": str})
        selected = ["symbol", *[c for c in label_columns if c in labels.columns]]
        frame = frame.merge(labels.loc[:, selected], on="symbol", how="left")

    exposure_columns = (
        "volatility",
        "historical_drawdown",
        "amount",
        "volume",
        "total_score",
        "risk_score",
        "liquidity_score",
    )
    availability = {}
    for column in exposure_columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
            availability[column] = bool(frame[column].notna().any())
        else:
            availability[column] = False
    return frame, availability, paths


def _warning_sets(
    frame: pd.DataFrame,
    high_risk_symbols: list[str],
    warning_quantile: float,
    availability: dict[str, bool],
) -> tuple[dict[str, set[str] | None], dict[str, float | None]]:
    thresholds: dict[str, float | None] = {
        "high_volatility_threshold": None,
        "drawdown_warning_threshold": None,
        "low_risk_score_threshold": None,
    }
    warning_sets: dict[str, set[str] | None] = {
        "high_risk_active": set(high_risk_symbols),
        "high_volatility": None,
        "drawdown_warning": None,
        "low_risk_score_warning": None,
    }
    if availability.get("volatility"):
        threshold = float(frame["volatility"].quantile(1 - warning_quantile))
        thresholds["high_volatility_threshold"] = threshold
        warning_sets["high_volatility"] = set(
            frame.loc[frame["volatility"] >= threshold, "symbol"].astype(str)
        )
    if availability.get("historical_drawdown"):
        threshold = float(
            frame["historical_drawdown"].quantile(warning_quantile)
        )
        thresholds["drawdown_warning_threshold"] = threshold
        warning_sets["drawdown_warning"] = set(
            frame.loc[
                frame["historical_drawdown"] <= threshold, "symbol"
            ].astype(str)
        )
    if availability.get("risk_score"):
        threshold = float(frame["risk_score"].quantile(warning_quantile))
        thresholds["low_risk_score_threshold"] = threshold
        warning_sets["low_risk_score_warning"] = set(
            frame.loc[frame["risk_score"] <= threshold, "symbol"].astype(str)
        )
    return warning_sets, thresholds


def _build_list_window_attribution(
    frame: pd.DataFrame,
    ordered_symbols: list[str],
    *,
    list_id: str,
    high_risk_symbols: set[str],
    warning_sets: dict[str, set[str] | None],
    availability: dict[str, bool],
) -> dict[str, Any]:
    order = {symbol: index for index, symbol in enumerate(ordered_symbols)}
    original = frame[frame["symbol"].isin(order)].copy()
    original["list_order"] = original["symbol"].map(order)
    original = original.sort_values("list_order")
    original_metrics = _list_metrics(original)

    variant_specs: list[tuple[str, set[str] | None]] = [
        ("original", set()),
        ("exclude_high_risk_active", warning_sets["high_risk_active"]),
        ("exclude_high_volatility", warning_sets["high_volatility"]),
        ("exclude_drawdown_warning", warning_sets["drawdown_warning"]),
        ("exclude_low_risk_score_warning", warning_sets["low_risk_score_warning"]),
    ]
    available_warning_sets = [
        value for value in warning_sets.values() if value is not None
    ]
    combined = set().union(*available_warning_sets) if available_warning_sets else None
    variant_specs.append(("exclude_any_available_risk_warning", combined))

    variants = []
    for variant_id, excluded_symbols in variant_specs:
        if excluded_symbols is None:
            variants.append(
                {
                    "variant_id": variant_id,
                    "status": "unavailable_missing_member_factor_columns",
                    "sample_count": None,
                    "removed_count": None,
                    "delta_vs_original": {},
                }
            )
            continue
        working = original[
            ~original["symbol"].isin(excluded_symbols)
        ].copy()
        metrics = _list_metrics(working)
        variants.append(
            {
                "variant_id": variant_id,
                "status": "ok",
                "removed_count": int(len(original) - len(working)),
                "retained_fraction": (
                    len(working) / len(original) if len(original) else None
                ),
                **metrics,
                "delta_vs_original": _metric_deltas(
                    metrics, original_metrics
                ),
            }
        )
    return {
        "list_id": list_id,
        "membership_count": len(ordered_symbols),
        "matched_valid_count": int(len(original)),
        "high_risk_overlap_count": len(set(ordered_symbols) & high_risk_symbols),
        "high_risk_overlap_rate": (
            len(set(ordered_symbols) & high_risk_symbols) / len(ordered_symbols)
            if ordered_symbols
            else None
        ),
        "member_factor_availability": availability,
        "variants": variants,
    }


def _list_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    returns = _numeric(frame, "future_return")
    excess = _numeric(frame, "future_excess_return")
    top_10 = frame.head(10)
    top_10_excess = _series_mean(_numeric(top_10, "future_excess_return"))
    full_excess = _series_mean(excess)
    exposures = {
        column: _series_mean(_numeric(frame, column))
        for column in (
            "volatility",
            "historical_drawdown",
            "amount",
            "volume",
            "total_score",
            "risk_score",
            "liquidity_score",
        )
    }
    return {
        "sample_count": int(len(frame)),
        "average_future_return": _series_mean(returns),
        "average_excess_return": full_excess,
        "win_rate": float((returns > 0).mean()) if len(returns) else None,
        "outperform_rate": _boolean_rate(frame, "outperformed_benchmark"),
        "average_future_drawdown": _series_mean(
            _numeric(frame, "max_drawdown_during_holding")
        ),
        "failure_rate_below_minus_10pct": (
            float((returns <= -0.10).mean()) if len(returns) else None
        ),
        "top_10_average_excess_return": top_10_excess,
        "breadth_dilution": (
            top_10_excess - full_excess
            if top_10_excess is not None and full_excess is not None
            else None
        ),
        "factor_exposure": exposures,
    }


def _metric_deltas(
    metrics: dict[str, Any],
    original: dict[str, Any],
) -> dict[str, float | None]:
    keys = (
        "average_future_return",
        "average_excess_return",
        "win_rate",
        "outperform_rate",
        "average_future_drawdown",
        "failure_rate_below_minus_10pct",
    )
    result = {}
    for key in keys:
        current = metrics.get(key)
        baseline = original.get(key)
        result[key] = (
            float(current) - float(baseline)
            if isinstance(current, (int, float))
            and isinstance(baseline, (int, float))
            else None
        )
    return result


def _aggregate_variants(
    windows: Iterable[dict[str, Any]],
    *,
    min_variant_sample: int,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for window in windows:
        for list_row in window["lists"]:
            for variant in list_row["variants"]:
                if variant.get("status") != "ok":
                    continue
                row = {
                    **variant,
                    "as_of_date": window["as_of_date"],
                    "horizon_days": window["horizon_days"],
                    "list_id": list_row["list_id"],
                }
                grouped.setdefault(
                    (list_row["list_id"], variant["variant_id"]), []
                ).append(row)

    result = []
    for (list_id, variant_id), rows in sorted(grouped.items()):
        samples = _numbers(rows, "sample_count")
        excess = _numbers(rows, "average_excess_return")
        deltas = [
            float(row["delta_vs_original"]["average_excess_return"])
            for row in rows
            if isinstance(
                row.get("delta_vs_original", {}).get(
                    "average_excess_return"
                ),
                (int, float),
            )
        ]
        improved_count = sum(value > 0 for value in deltas)
        classification = _variant_classification(
            variant_id,
            rows,
            samples,
            deltas,
            min_variant_sample,
        )
        result.append(
            {
                "list_id": list_id,
                "variant_id": variant_id,
                "valid_window_count": len(rows),
                "sample_count_min": min(samples) if samples else None,
                "sample_count_median": median(samples) if samples else None,
                "average_future_return_mean": _mean(
                    _numbers(rows, "average_future_return")
                ),
                "average_excess_return_mean": _mean(excess),
                "average_excess_return_median": _median(excess),
                "positive_excess_window_count": sum(value > 0 for value in excess),
                "negative_excess_window_count": sum(value < 0 for value in excess),
                "excess_sign_consistency": _sign_consistency(excess),
                "average_future_drawdown_mean": _mean(
                    _numbers(rows, "average_future_drawdown")
                ),
                "average_excess_delta_mean": _mean(deltas),
                "improved_window_count": improved_count,
                "classification": classification,
                "windows": rows,
            }
        )
    return result


def _variant_classification(
    variant_id: str,
    rows: list[dict[str, Any]],
    samples: list[float],
    deltas: list[float],
    min_variant_sample: int,
) -> str:
    if variant_id == "original":
        return "baseline_observation"
    if len(rows) < 2 or not samples or min(samples) < min_variant_sample:
        return "insufficient_sample"
    delta_mean = _mean(deltas)
    if delta_mean is None:
        return "insufficient_data"
    improved_count = sum(value > 0 for value in deltas)
    if delta_mean > 0 and improved_count / len(rows) >= 0.75:
        return "improved_consistently_exploratory"
    if delta_mean > 0:
        return "improved_but_mixed"
    if delta_mean < 0:
        return "weakened"
    return "neutral"


def _high_risk_exclusion_summary(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    selected = [
        row
        for row in rows
        if row["variant_id"] == "exclude_high_risk_active"
    ]
    improved = [
        row["list_id"]
        for row in selected
        if row["classification"]
        in {"improved_consistently_exploratory", "improved_but_mixed"}
    ]
    return {
        "evaluated_list_count": len(selected),
        "improved_list_count": len(improved),
        "improved_list_ids": sorted(improved),
        "all_list_results": [
            {
                "list_id": row["list_id"],
                "average_excess_delta_mean": row[
                    "average_excess_delta_mean"
                ],
                "improved_window_count": row["improved_window_count"],
                "classification": row["classification"],
            }
            for row in selected
        ],
        "interpretation": (
            "High-risk exclusion is a research hypothesis only; review whether "
            "improvement is consistent across windows and whether retained "
            "sample sizes remain adequate."
        ),
    }


def _load_factor_context(
    path: Path,
    as_of_date: str,
    horizon_days: int,
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = payload if isinstance(payload, list) else []
    selected = {
        "total_score",
        "volatility",
        "drawdown",
        "risk_score",
        "liquidity_score",
        "amount",
        "volume",
    }
    return [
        {
            **row,
            "as_of_date": as_of_date,
            "horizon_days": horizon_days,
        }
        for row in rows
        if isinstance(row, dict) and row.get("factor_name") in selected
    ]


def _aggregate_factor_context(
    rows: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        factor_name = str(row.get("factor_name", ""))
        if factor_name:
            grouped.setdefault(factor_name, []).append(row)
    result = []
    for factor_name, group in sorted(grouped.items()):
        spreads = _numbers(group, "spread")
        result.append(
            {
                "factor_name": factor_name,
                "valid_window_count": len(group),
                "spread_mean": _mean(spreads),
                "positive_spread_window_count": sum(value > 0 for value in spreads),
                "negative_spread_window_count": sum(value < 0 for value in spreads),
                "spread_sign_consistency": _sign_consistency(spreads),
            }
        )
    return result


def _availability_summary(
    windows: Iterable[dict[str, Any]],
) -> dict[str, str]:
    rows = list(windows)
    keys = (
        "volatility",
        "historical_drawdown",
        "amount",
        "volume",
        "total_score",
        "risk_score",
        "liquidity_score",
    )
    result = {}
    for key in keys:
        available_count = sum(
            bool(row["member_factor_availability"].get(key)) for row in rows
        )
        if not rows:
            result[key] = "unavailable"
        elif available_count == len(rows):
            result[key] = "available_all_windows"
        elif available_count:
            result[key] = "available_partial_windows"
        else:
            result[key] = "unavailable"
    return result


def _load_ordered_symbols(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError(f"Expected list membership object: {path}")
    result = []
    for item in payload["items"]:
        symbol = str(item.get("symbol", "")).strip() if isinstance(item, dict) else ""
        if symbol and symbol not in result:
            result.append(symbol)
    return result


def _benchmark_regime(value: float | None) -> str:
    if value is None:
        return "unknown"
    if value > 0:
        return "positive_benchmark"
    if value < 0:
        return "negative_benchmark"
    return "flat_benchmark"


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").dropna()


def _boolean_rate(frame: pd.DataFrame, column: str) -> float | None:
    if column not in frame.columns:
        return None
    values = frame[column].dropna()
    if values.empty:
        return None
    if values.dtype == object:
        values = values.astype(str).str.lower().map(
            {"true": True, "false": False, "1": True, "0": False}
        )
    values = values.dropna()
    return float(values.astype(bool).mean()) if not values.empty else None


def _series_mean(values: pd.Series) -> float | None:
    return float(values.mean()) if not values.empty else None


def _series_median(values: pd.Series) -> float | None:
    return float(values.median()) if not values.empty else None


def _numbers(rows: Iterable[dict[str, Any]], key: str) -> list[float]:
    result = []
    for row in rows:
        value = row.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            numeric = float(value)
            if math.isfinite(numeric):
                result.append(numeric)
    return result


def _mean(values: Iterable[float]) -> float | None:
    items = list(values)
    return sum(items) / len(items) if items else None


def _median(values: Iterable[float]) -> float | None:
    items = list(values)
    return median(items) if items else None


def _sign_consistency(values: Iterable[float]) -> str:
    items = list(values)
    if not items:
        return "insufficient_data"
    positive_count = sum(value > 0 for value in items)
    negative_count = sum(value < 0 for value in items)
    if positive_count == len(items):
        return "consistently_positive"
    if negative_count == len(items):
        return "consistently_negative"
    if positive_count / len(items) >= 0.75:
        return "mostly_positive"
    if negative_count / len(items) >= 0.75:
        return "mostly_negative"
    return "mixed_or_neutral"


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if hasattr(value, "item"):
        return _json_safe(value.item())
    return value
