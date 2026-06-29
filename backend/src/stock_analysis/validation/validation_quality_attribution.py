"""Read-only attribution of controlled validation quality across windows."""

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
SUMMARY_JSON_NAME = "validation_quality_attribution_2024.json"
SUMMARY_MARKDOWN_NAME = "validation_quality_attribution_2024.md"
DISCLAIMER = (
    "Research-only controlled validation attribution. This report uses existing "
    "outputs only, does not recompute labels, and does not justify production "
    "scoring or recommendation changes."
)


@dataclass(frozen=True)
class ValidationQualityAttributionConfig:
    outputs_dir: str | Path = "outputs"
    windows: tuple[tuple[str, int], ...] = DEFAULT_WINDOWS


def build_validation_quality_attribution(
    config: ValidationQualityAttributionConfig,
) -> dict[str, Any]:
    outputs_dir = Path(config.outputs_dir)
    included_windows: list[dict[str, Any]] = []
    excluded_windows: list[dict[str, Any]] = []
    list_rows: list[dict[str, Any]] = []
    factor_rows: list[dict[str, Any]] = []
    source_files: list[str] = []

    for as_of_date, horizon_days in config.windows:
        suffix = f"{as_of_date}_{horizon_days}d"
        paths = {
            "predictions": outputs_dir
            / "validation"
            / f"walk_forward_predictions_{suffix}.csv",
            "list_performance": outputs_dir
            / "validation"
            / f"list_performance_{suffix}.json",
            "factor_effectiveness": outputs_dir
            / "validation"
            / f"factor_effectiveness_{suffix}.json",
        }
        missing = [str(path) for path in paths.values() if not path.exists()]
        if missing:
            excluded_windows.append(
                {
                    "as_of_date": as_of_date,
                    "horizon_days": horizon_days,
                    "status": "missing_required_outputs",
                    "missing_files": missing,
                }
            )
            continue

        predictions = pd.read_csv(paths["predictions"])
        lists = _load_json_rows(paths["list_performance"])
        factors = _load_json_rows(paths["factor_effectiveness"])
        included_windows.append(
            _prediction_window_summary(predictions, as_of_date, horizon_days)
        )
        list_rows.extend(_with_window(row, as_of_date, horizon_days) for row in lists)
        factor_rows.extend(
            _with_window(row, as_of_date, horizon_days) for row in factors
        )
        source_files.extend(str(path) for path in paths.values())

    list_attribution = _summarize_lists(list_rows)
    factor_attribution = _summarize_factors(factor_rows)
    risk_attribution = _risk_profile_attribution(list_attribution)
    unavailable = [
        {
            "dimension": "industry_sector_market_cap",
            "reason": "Historical point-in-time industry, sector, and market-cap fields are not present in the controlled validation outputs.",
        },
        {
            "dimension": "member_level_score_and_factor_buckets",
            "reason": "Prediction CSVs do not contain score or factor input columns; existing factor-effectiveness quantiles are summarized instead.",
        },
        {
            "dimension": "disjoint_non_high_risk_cohort",
            "reason": "List summaries overlap and do not define a disjoint non-high-risk membership cohort.",
        },
    ]

    return _json_safe(
        {
            "summary": {
                "status": "ok" if included_windows else "insufficient_data",
                "research_only": True,
                "provider_access": False,
                "cache_fetch_executed": False,
                "labels_recomputed": False,
                "production_scoring_changed": False,
                "production_recommendations_changed": False,
                "included_window_count": len(included_windows),
                "excluded_window_count": len(excluded_windows),
                "disclaimer": DISCLAIMER,
                "interpretation": (
                    "Use sign consistency and cross-window dispersion to identify "
                    "stable risk separation or regime dependence. Do not optimize "
                    "production formulas from this same-period panel."
                ),
            },
            "included_windows": included_windows,
            "excluded_windows": excluded_windows,
            "list_attribution": list_attribution,
            "factor_attribution": factor_attribution,
            "risk_profile_attribution": risk_attribution,
            "unavailable_dimensions": unavailable,
            "source_files": sorted(source_files),
            "outputs": {},
        }
    )


def write_validation_quality_attribution_outputs(
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
        render_validation_quality_attribution_markdown(report),
        encoding="utf-8",
    )
    return report["outputs"]


def render_validation_quality_attribution_markdown(
    report: dict[str, Any],
) -> str:
    lines = [
        "# Controlled Validation Quality Attribution",
        "",
        str(report["summary"]["disclaimer"]),
        "",
        "## Windows Used",
        "",
        "| As-of date | Horizon | Valid predictions | Average excess | Average drawdown | Data quality |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in report.get("included_windows", []):
        lines.append(
            f"| {row['as_of_date']} | {row['horizon_days']}d | "
            f"{row['valid_prediction_count']}/{row['prediction_count']} | "
            f"{_fmt(row.get('average_excess_return'))} | "
            f"{_fmt(row.get('max_drawdown_average'))} | "
            f"{_compact_counts(row.get('data_quality_counts', {}))} |"
        )
    if not report.get("included_windows"):
        lines.append("| none | - | - | - | - | missing |")

    lines.extend(
        [
            "",
            "## List Attribution",
            "",
            "| List | Windows | Sample min/median | Avg excess mean | Win rate mean | Outperform mean | Drawdown mean | Sign consistency |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in report.get("list_attribution", []):
        lines.append(
            f"| {row['list_id']} | {row['valid_window_count']} | "
            f"{_fmt(row.get('sample_count_min'))}/{_fmt(row.get('sample_count_median'))} | "
            f"{_fmt(row.get('average_excess_return_mean'))} | "
            f"{_fmt(row.get('win_rate_mean'))} | "
            f"{_fmt(row.get('outperform_rate_mean'))} | "
            f"{_fmt(row.get('max_drawdown_average_mean'))} | "
            f"{row['excess_sign_consistency']} |"
        )

    lines.extend(
        [
            "",
            "## Factor Attribution",
            "",
            "| Factor | Windows | Correlation mean | Spread mean | Positive spread windows | Sign consistency |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for row in report.get("factor_attribution", []):
        lines.append(
            f"| {row['factor_name']} | {row['valid_window_count']} | "
            f"{_fmt(row.get('correlation_mean'))} | "
            f"{_fmt(row.get('spread_mean'))} | "
            f"{row['positive_spread_window_count']} | "
            f"{row['spread_sign_consistency']} |"
        )

    lines.extend(["", "## Risk Profile Attribution", ""])
    risk = report.get("risk_profile_attribution", {})
    high_risk = risk.get("high_risk_active")
    if high_risk:
        lines.append(
            f"- `high_risk_active`: {high_risk['valid_window_count']} windows, "
            f"mean excess {_fmt(high_risk.get('average_excess_return_mean'))}, "
            f"sign consistency `{high_risk['excess_sign_consistency']}`."
        )
    lines.append(
        "- Non-high-risk reference: "
        + str(risk.get("comparison_note", "unavailable"))
    )

    lines.extend(["", "## Unavailable Dimensions", ""])
    for item in report.get("unavailable_dimensions", []):
        lines.append(f"- `{item['dimension']}`: {item['reason']}")

    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- Existing validation labels are consumed as-is and are not recomputed.",
            "- Cross-window sign consistency is descriptive, not proof of future effectiveness.",
            "- Overlapping lists must not be interpreted as independent cohorts.",
            "- No production scoring or recommendation changes are supported by this report alone.",
            "",
        ]
    )
    return "\n".join(lines)


def _prediction_window_summary(
    frame: pd.DataFrame,
    as_of_date: str,
    horizon_days: int,
) -> dict[str, Any]:
    quality = (
        frame["data_quality"].fillna("missing").astype(str)
        if "data_quality" in frame.columns
        else pd.Series(["missing"] * len(frame))
    )
    valid = frame[quality == "ok"].copy()
    return {
        "as_of_date": as_of_date,
        "horizon_days": horizon_days,
        "prediction_count": int(len(frame)),
        "valid_prediction_count": int(len(valid)),
        "data_quality_counts": {
            str(key): int(value) for key, value in quality.value_counts().items()
        },
        "average_future_return": _series_mean(valid, "future_return"),
        "average_excess_return": _series_mean(valid, "future_excess_return"),
        "win_rate": _positive_rate(valid, "future_return"),
        "outperform_rate": _boolean_rate(valid, "outperformed_benchmark"),
        "max_drawdown_average": _series_mean(
            valid, "max_drawdown_during_holding"
        ),
    }


def _summarize_lists(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = _group_rows(rows, "list_id")
    result = []
    for list_id, group in sorted(grouped.items()):
        samples = _numbers(group, "valid_future_count")
        excess = _numbers(group, "average_excess_return")
        result.append(
            {
                "list_id": list_id,
                "valid_window_count": len(group),
                "sample_count_total": int(sum(samples)),
                "sample_count_min": min(samples) if samples else None,
                "sample_count_median": median(samples) if samples else None,
                "average_future_return_mean": _mean(
                    _numbers(group, "average_future_return")
                ),
                "average_excess_return_mean": _mean(excess),
                "average_excess_return_median": _median(excess),
                "positive_excess_window_count": sum(value > 0 for value in excess),
                "negative_excess_window_count": sum(value < 0 for value in excess),
                "win_rate_mean": _mean(_numbers(group, "win_rate")),
                "outperform_rate_mean": _mean(
                    _numbers(group, "outperform_rate")
                ),
                "max_drawdown_average_mean": _mean(
                    _numbers(group, "max_drawdown_average")
                ),
                "excess_sign_consistency": _sign_consistency(excess),
                "windows": [
                    {
                        key: row.get(key)
                        for key in (
                            "as_of_date",
                            "horizon_days",
                            "valid_future_count",
                            "average_future_return",
                            "average_excess_return",
                            "win_rate",
                            "outperform_rate",
                            "max_drawdown_average",
                        )
                    }
                    for row in group
                ],
            }
        )
    return result


def _summarize_factors(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = _group_rows(rows, "factor_name")
    result = []
    for factor_name, group in sorted(grouped.items()):
        correlations = _numbers(group, "correlation_with_future_return")
        spreads = _numbers(group, "spread")
        result.append(
            {
                "factor_name": factor_name,
                "valid_window_count": len(group),
                "correlation_mean": _mean(correlations),
                "correlation_median": _median(correlations),
                "correlation_sign_consistency": _sign_consistency(correlations),
                "spread_mean": _mean(spreads),
                "spread_median": _median(spreads),
                "spread_min": min(spreads) if spreads else None,
                "spread_max": max(spreads) if spreads else None,
                "positive_spread_window_count": sum(value > 0 for value in spreads),
                "negative_spread_window_count": sum(value < 0 for value in spreads),
                "spread_sign_consistency": _sign_consistency(spreads),
                "top_quantile_average_return_mean": _mean(
                    _numbers(group, "top_quantile_average_return")
                ),
                "top_quantile_outperform_rate_mean": _mean(
                    _numbers(group, "top_quantile_outperform_rate")
                ),
                "windows": [
                    {
                        key: row.get(key)
                        for key in (
                            "as_of_date",
                            "horizon_days",
                            "correlation_with_future_return",
                            "top_quantile_average_return",
                            "bottom_quantile_average_return",
                            "spread",
                            "top_quantile_outperform_rate",
                        )
                    }
                    for row in group
                ],
            }
        )
    return result


def _risk_profile_attribution(
    list_attribution: list[dict[str, Any]],
) -> dict[str, Any]:
    high_risk = next(
        (row for row in list_attribution if row["list_id"] == "high_risk_active"),
        None,
    )
    comparison = [
        row
        for row in list_attribution
        if row["list_id"] != "high_risk_active"
        and row.get("average_excess_return_mean") is not None
    ]
    return {
        "high_risk_active": high_risk,
        "other_list_average_excess_mean": _mean(
            [float(row["average_excess_return_mean"]) for row in comparison]
        ),
        "comparison_note": (
            "Other-list average is descriptive only because lists overlap; it is "
            "not a disjoint non-high-risk cohort."
        ),
    }


def _load_json_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list: {path}")
    return [row for row in payload if isinstance(row, dict)]


def _with_window(
    row: dict[str, Any], as_of_date: str, horizon_days: int
) -> dict[str, Any]:
    return {**row, "as_of_date": as_of_date, "horizon_days": horizon_days}


def _group_rows(
    rows: Iterable[dict[str, Any]], key: str
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        value = str(row.get(key, "")).strip()
        if value:
            grouped.setdefault(value, []).append(row)
    return grouped


def _numbers(rows: Iterable[dict[str, Any]], key: str) -> list[float]:
    values = []
    for row in rows:
        value = row.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            numeric = float(value)
            if math.isfinite(numeric):
                values.append(numeric)
    return values


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


def _series_mean(frame: pd.DataFrame, column: str) -> float | None:
    if column not in frame.columns:
        return None
    numeric = pd.to_numeric(frame[column], errors="coerce").dropna()
    return float(numeric.mean()) if not numeric.empty else None


def _positive_rate(frame: pd.DataFrame, column: str) -> float | None:
    if column not in frame.columns:
        return None
    numeric = pd.to_numeric(frame[column], errors="coerce").dropna()
    return float((numeric > 0).mean()) if not numeric.empty else None


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


def _compact_counts(counts: dict[str, Any]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


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
