"""Summarize ready strategy experiment windows without running data jobs."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Any


DEFAULT_WINDOWS: tuple[tuple[str, int], ...] = (
    ("2024-01-31", 20),
    ("2024-01-31", 60),
    ("2024-01-31", 120),
    ("2024-04-30", 20),
    ("2024-04-30", 60),
)

SUMMARY_JSON_NAME = "multi_window_experiment_summary_2024.json"
SUMMARY_MARKDOWN_NAME = "multi_window_experiment_summary_2024.md"

RESEARCH_ONLY_DISCLAIMER = (
    "Research-only experiment summary. This is not investment advice, does not "
    "replace production scoring, and must not be interpreted as evidence of "
    "future model effectiveness."
)

ANTI_LEAKAGE_NOTE = (
    "Inputs are existing as-of experiment outputs. Features, lists, filters, "
    "and dynamic states must have been generated only from data available on "
    "or before each as-of date; future returns and benchmark outcomes are used "
    "only as evaluation labels."
)

SAME_PERIOD_NOTE = (
    "Same-period experiment results are exploratory only. Do not tune a filter "
    "on one as-of window and report that same window as validated."
)


@dataclass(frozen=True)
class MultiWindowSummaryConfig:
    outputs_dir: Path
    plan_file: Path
    windows: tuple[tuple[str, int], ...] = DEFAULT_WINDOWS
    min_valid_count: int = 10


@dataclass
class WindowFiles:
    as_of_date: str
    horizon_days: int
    strategy_file: Path
    aggressive_file: Path
    plan_status: str | None = None
    plan_ready: bool | None = None

    @property
    def window_id(self) -> str:
        return f"{self.as_of_date}_{self.horizon_days}d"


def build_multi_window_experiment_summary(config: MultiWindowSummaryConfig) -> dict[str, Any]:
    """Build a read-only stability summary from existing experiment outputs."""

    outputs_dir = Path(config.outputs_dir)
    experiments_dir = outputs_dir / "experiments"
    plan = _load_json(Path(config.plan_file)) if Path(config.plan_file).exists() else {}
    plan_lookup = _build_plan_lookup(plan)

    ready_windows: list[dict[str, Any]] = []
    missing_windows: list[dict[str, Any]] = []
    strategy_rows: list[dict[str, Any]] = []
    aggressive_rows: list[dict[str, Any]] = []
    source_files: list[str] = []

    for as_of_date, horizon_days in config.windows:
        window = _window_files(experiments_dir, as_of_date, horizon_days, plan_lookup)
        missing: list[str] = []
        if not window.strategy_file.exists():
            missing.append(str(window.strategy_file))
        if not window.aggressive_file.exists():
            missing.append(str(window.aggressive_file))

        if missing:
            missing_windows.append(
                {
                    "as_of_date": as_of_date,
                    "horizon_days": horizon_days,
                    "status": "missing_experiment_outputs",
                    "plan_status": window.plan_status,
                    "plan_ready": window.plan_ready,
                    "missing_files": missing,
                }
            )
            continue

        strategy_payload = _load_json(window.strategy_file)
        aggressive_payload = _load_json(window.aggressive_file)
        source_files.extend([str(window.strategy_file), str(window.aggressive_file)])

        ready_windows.append(
            {
                "as_of_date": as_of_date,
                "horizon_days": horizon_days,
                "window_id": window.window_id,
                "plan_status": window.plan_status,
                "plan_ready": window.plan_ready,
                "strategy_file": str(window.strategy_file),
                "aggressive_file": str(window.aggressive_file),
            }
        )
        strategy_rows.extend(
            _with_window(row, as_of_date, horizon_days, window.window_id)
            for row in strategy_payload.get("strategy_family_results", [])
        )
        aggressive_rows.extend(
            _with_window(row, as_of_date, horizon_days, window.window_id)
            for row in aggressive_payload.get("aggressive_filter_results", [])
        )

    strategy_summary = _summarize_strategy_families(strategy_rows, config.min_valid_count)
    aggressive_summary = _summarize_aggressive_filters(aggressive_rows, config.min_valid_count)
    recommended = _recommended_interpretation(strategy_summary, aggressive_summary)

    exploratory_count = sum(
        1
        for row in aggressive_rows
        if row.get("validation_status") == "exploratory_same_period"
    )
    warnings = []
    if exploratory_count:
        warnings.append(
            f"{exploratory_count} aggressive filter rows are exploratory_same_period."
        )
    if missing_windows:
        warnings.append("Some default windows are missing experiment outputs.")

    return {
        "summary": {
            "status": "ok",
            "research_only": True,
            "production_scoring_changed": False,
            "provider_access": False,
            "prewarm_executed": False,
            "full_workflow_executed": False,
            "no_future_leakage": True,
            "min_valid_count": config.min_valid_count,
            "ready_window_count": len(ready_windows),
            "missing_window_count": len(missing_windows),
            "strategy_family_count": len(strategy_summary),
            "aggressive_filter_count": len(aggressive_summary),
            "disclaimer": RESEARCH_ONLY_DISCLAIMER,
            "anti_leakage_note": ANTI_LEAKAGE_NOTE,
            "same_period_interpretation": SAME_PERIOD_NOTE,
            "warnings": warnings,
        },
        "ready_windows_used": ready_windows,
        "excluded_or_missing_windows": missing_windows,
        "strategy_family_stability": strategy_summary,
        "aggressive_filter_stability": aggressive_summary,
        "recommended_current_interpretation": recommended,
        "guardrails": [
            RESEARCH_ONLY_DISCLAIMER,
            ANTI_LEAKAGE_NOTE,
            SAME_PERIOD_NOTE,
            "No production scoring changes are recommended by this summary.",
            "Do not rank filters only by average_excess_return.",
            "Small samples and right-tail destruction are penalized explicitly.",
        ],
        "next_validation_recommendation": (
            "Continue controlled multi-as-of validation by adding missing windows "
            "and then checking whether conclusions hold out of sample."
        ),
        "source_files": sorted(source_files),
        "outputs": {},
    }


def write_multi_window_experiment_summary_outputs(
    summary: dict[str, Any],
    outputs_dir: Path,
) -> dict[str, str]:
    experiments_dir = Path(outputs_dir) / "experiments"
    experiments_dir.mkdir(parents=True, exist_ok=True)
    json_path = experiments_dir / SUMMARY_JSON_NAME
    markdown_path = experiments_dir / SUMMARY_MARKDOWN_NAME

    summary = _json_safe(summary)
    summary["outputs"] = {
        "json": str(json_path),
        "markdown": str(markdown_path),
    }
    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_multi_window_experiment_summary_markdown(summary),
        encoding="utf-8",
    )
    return summary["outputs"]


def render_multi_window_experiment_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Phase 2.8.5 Multi-Window Experiment Summary",
        "",
        summary["summary"]["disclaimer"],
        "",
        "## Ready Windows Used",
        "",
    ]
    ready_windows = summary.get("ready_windows_used", [])
    if ready_windows:
        lines.append("| As-of date | Horizon | Plan status |")
        lines.append("|---|---:|---|")
        for row in ready_windows:
            lines.append(
                f"| {row['as_of_date']} | {row['horizon_days']}d | "
                f"{row.get('plan_status') or 'unknown'} |"
            )
    else:
        lines.append("No ready windows were available.")

    lines.extend(["", "## Excluded And Missing Windows", ""])
    missing = summary.get("excluded_or_missing_windows", [])
    if missing:
        lines.append("| As-of date | Horizon | Status | Missing files |")
        lines.append("|---|---:|---|---|")
        for row in missing:
            lines.append(
                f"| {row['as_of_date']} | {row['horizon_days']}d | "
                f"{row['status']} | {len(row.get('missing_files', []))} |"
            )
    else:
        lines.append("No default windows were excluded.")

    lines.extend(["", "## Strategy Family Stability", ""])
    lines.append(
        "| Profile | Windows | Avg excess mean | Outperform mean | "
        "Top 5 mean | Failure <= -20% max | Classification |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    for row in summary.get("strategy_family_stability", []):
        lines.append(
            f"| {row['profile_id']} | {row['valid_window_count']} | "
            f"{_fmt(row.get('average_excess_return_mean'))} | "
            f"{_fmt(row.get('outperform_rate_mean'))} | "
            f"{_fmt(row.get('top_5_average_return_mean'))} | "
            f"{_fmt(row.get('failure_rate_below_minus_20pct_max'))} | "
            f"{row['classification']} |"
        )

    lines.extend(["", "## Aggressive Filter Stability", ""])
    lines.append(
        "| Source family | Filter | Windows | Avg excess mean | "
        "Right-tail preservation | Sample min | Classification |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---|")
    for row in summary.get("aggressive_filter_stability", []):
        lines.append(
            f"| {row['source_strategy_family']} | {row['filter_id']} | "
            f"{row['valid_window_count']} | "
            f"{_fmt(row.get('average_excess_return_mean'))} | "
            f"{_fmt(row.get('right_tail_preservation_ratio_mean'))} | "
            f"{_fmt(row.get('sample_count_min'))} | "
            f"{row['classification']} |"
        )

    lines.extend(["", "## Recommended Current Interpretation", ""])
    for item in summary.get("recommended_current_interpretation", []):
        lines.append(f"- {item}")

    lines.extend(["", "## Guardrails", ""])
    for item in summary.get("guardrails", []):
        lines.append(f"- {item}")

    lines.extend(["", "## Next Validation Recommendation", ""])
    lines.append(summary.get("next_validation_recommendation", "Continue controlled validation."))
    lines.append("")
    return "\n".join(lines)


def _window_files(
    experiments_dir: Path,
    as_of_date: str,
    horizon_days: int,
    plan_lookup: dict[tuple[str, int], dict[str, Any]],
) -> WindowFiles:
    plan_row = plan_lookup.get((as_of_date, horizon_days), {})
    return WindowFiles(
        as_of_date=as_of_date,
        horizon_days=horizon_days,
        strategy_file=experiments_dir
        / f"strategy_family_experiments_{as_of_date}_{horizon_days}d.json",
        aggressive_file=experiments_dir
        / f"aggressive_filter_experiments_{as_of_date}_{horizon_days}d.json",
        plan_status=plan_row.get("status"),
        plan_ready=plan_row.get("ready_for_comparison"),
    )


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_plan_lookup(plan: dict[str, Any]) -> dict[tuple[str, int], dict[str, Any]]:
    lookup: dict[tuple[str, int], dict[str, Any]] = {}
    for row in plan.get("validation_windows", []):
        as_of_date = row.get("as_of_date")
        horizon_days = row.get("horizon_days")
        if as_of_date and horizon_days is not None:
            lookup[(str(as_of_date), int(horizon_days))] = row
    for as_of_row in plan.get("as_of_plan", []):
        as_of_date = as_of_row.get("as_of_date")
        if not as_of_date:
            continue
        for horizon_row in as_of_row.get("horizons", []):
            horizon_days = horizon_row.get("horizon_days")
            if horizon_days is None:
                continue
            lookup[(str(as_of_date), int(horizon_days))] = {
                **horizon_row,
                "as_of_date": str(as_of_date),
                "status": _plan_window_status(horizon_row),
            }
    return lookup


def _plan_window_status(row: dict[str, Any]) -> str:
    if row.get("crosses_2025_boundary"):
        return "deferred_crosses_2025"
    if row.get("ready_for_comparison"):
        return "ready_for_comparison"
    if row.get("missing_as_of_outputs"):
        return "blocked_missing_as_of_outputs"
    if row.get("missing_outputs"):
        return "missing_experiment_outputs"
    return str(row.get("status") or "not_ready")


def _with_window(
    row: dict[str, Any],
    as_of_date: str,
    horizon_days: int,
    window_id: str,
) -> dict[str, Any]:
    value = dict(row)
    value.setdefault("as_of_date", as_of_date)
    value.setdefault("horizon_days", horizon_days)
    value["window_id"] = window_id
    return value


def _summarize_strategy_families(
    rows: list[dict[str, Any]],
    min_valid_count: int,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("profile_id", "unknown")), []).append(row)

    summaries = []
    for profile_id, group in sorted(grouped.items()):
        valid_counts = [_number(row.get("valid_future_count")) for row in group]
        valid_counts = [value for value in valid_counts if value is not None]
        row = {
            "profile_id": profile_id,
            "family_type": _first_text(group, "family_type"),
            "valid_window_count": len(group),
            "valid_future_count_min": _min(valid_counts),
            "valid_future_count_median": _median(valid_counts),
            "valid_future_count_average": _mean(valid_counts),
            "average_excess_return_mean": _metric_mean(group, "average_excess_return"),
            "average_excess_return_median": _metric_median(group, "average_excess_return"),
            "positive_excess_window_count": _positive_count(group, "average_excess_return"),
            "outperform_rate_mean": _metric_mean(group, "outperform_rate"),
            "outperform_rate_median": _metric_median(group, "outperform_rate"),
            "top_5_average_return_mean": _metric_mean(group, "top_5_average_return"),
            "top_5_average_return_median": _metric_median(group, "top_5_average_return"),
            "payoff_ratio_mean": _metric_mean(group, "payoff_ratio"),
            "payoff_ratio_median": _metric_median(group, "payoff_ratio"),
            "failure_rate_below_minus_20pct_mean": _metric_mean(
                group, "failure_rate_below_minus_20pct"
            ),
            "failure_rate_below_minus_20pct_max": _metric_max(
                group, "failure_rate_below_minus_20pct"
            ),
            "warnings": _strategy_warnings(group, min_valid_count),
            "windows": _window_metrics(group),
        }
        row["classification"] = _classify_strategy(row)
        summaries.append(row)
    return summaries


def _summarize_aggressive_filters(
    rows: list[dict[str, Any]],
    min_valid_count: int,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (
            str(row.get("source_strategy_family", "unknown")),
            str(row.get("filter_id", "unknown")),
        )
        grouped.setdefault(key, []).append(row)

    summaries = []
    for (source_family, filter_id), group in sorted(grouped.items()):
        sample_counts = [
            _sample_count(row)
            for row in group
            if _sample_count(row) is not None
        ]
        insufficient_count = sum(
            1
            for row in group
            if row.get("validation_status") == "insufficient_data"
            or (_sample_count(row) or 0) < min_valid_count
        )
        row = {
            "source_strategy_family": source_family,
            "filter_id": filter_id,
            "valid_window_count": len(group),
            "insufficient_data_count": insufficient_count,
            "average_excess_return_mean": _metric_mean(group, "average_excess_return"),
            "average_excess_return_median": _metric_median(group, "average_excess_return"),
            "positive_excess_window_count": _positive_count(group, "average_excess_return"),
            "outperform_rate_mean": _metric_mean(group, "outperform_rate"),
            "outperform_rate_median": _metric_median(group, "outperform_rate"),
            "top_5_average_return_mean": _metric_mean(group, "top_5_average_return"),
            "top_5_average_return_median": _metric_median(group, "top_5_average_return"),
            "right_tail_preservation_ratio_mean": _metric_mean(
                group, "right_tail_preservation_ratio"
            ),
            "right_tail_preservation_ratio_median": _metric_median(
                group, "right_tail_preservation_ratio"
            ),
            "left_tail_reduction_ratio_mean": _metric_mean(
                group, "left_tail_reduction_ratio"
            ),
            "left_tail_reduction_ratio_median": _metric_median(
                group, "left_tail_reduction_ratio"
            ),
            "payoff_ratio_mean": _metric_mean(group, "payoff_ratio"),
            "payoff_ratio_median": _metric_median(group, "payoff_ratio"),
            "failure_rate_below_minus_20pct_mean": _metric_mean(
                group, "failure_rate_below_minus_20pct"
            ),
            "failure_rate_below_minus_20pct_max": _metric_max(
                group, "failure_rate_below_minus_20pct"
            ),
            "sample_count_min": _min(sample_counts),
            "sample_count_median": _median(sample_counts),
            "warnings": _aggressive_warnings(group, min_valid_count),
            "windows": _window_metrics(group),
        }
        row["classification"] = _classify_aggressive_filter(row, min_valid_count)
        summaries.append(row)
    return summaries


def _classify_strategy(row: dict[str, Any]) -> str:
    window_count = int(row.get("valid_window_count") or 0)
    positive = int(row.get("positive_excess_window_count") or 0)
    avg_excess = row.get("average_excess_return_mean")
    outperform = row.get("outperform_rate_mean")
    failure_max = row.get("failure_rate_below_minus_20pct_max")
    profile_id = str(row.get("profile_id", ""))

    if window_count < 2:
        return "insufficient_data"
    if avg_excess is None or outperform is None:
        return "insufficient_data"
    if positive == window_count and avg_excess > 0 and outperform >= 0.55 and (
        failure_max is None or failure_max <= 0.25
    ):
        if profile_id in {"right_tail_hunter", "volatility_expansion"}:
            return "observation_only"
        return "robust_candidate"
    if positive >= max(1, math.ceil(window_count * 0.6)) and avg_excess > 0:
        return "context_dependent"
    if profile_id in {"right_tail_hunter", "volatility_expansion"} and positive:
        return "observation_only"
    return "weak_or_rejected_for_now"


def _classify_aggressive_filter(row: dict[str, Any], min_valid_count: int) -> str:
    window_count = int(row.get("valid_window_count") or 0)
    insufficient = int(row.get("insufficient_data_count") or 0)
    positive = int(row.get("positive_excess_window_count") or 0)
    sample_min = row.get("sample_count_min")
    avg_excess = row.get("average_excess_return_mean")
    right_tail = row.get("right_tail_preservation_ratio_mean")
    left_tail = row.get("left_tail_reduction_ratio_mean")
    failure_max = row.get("failure_rate_below_minus_20pct_max")

    if window_count < 2 or sample_min is None or sample_min < min_valid_count:
        return "sample_too_small"
    if insufficient >= math.ceil(window_count / 2):
        return "sample_too_small"
    if right_tail is not None and right_tail < 0.65:
        return "right_tail_destructive"
    if avg_excess is None:
        return "weak_filter_for_now"
    if (
        positive == window_count
        and avg_excess > 0
        and (right_tail is None or right_tail >= 0.8)
        and (left_tail is None or left_tail <= 1.05)
        and (failure_max is None or failure_max <= 0.25)
    ):
        return "strong_filter_candidate"
    if positive >= max(1, math.ceil(window_count * 0.5)):
        return "horizon_sensitive_filter"
    return "weak_filter_for_now"


def _recommended_interpretation(
    strategy_summary: list[dict[str, Any]],
    aggressive_summary: list[dict[str, Any]],
) -> list[str]:
    by_profile = {row["profile_id"]: row for row in strategy_summary}
    items = []

    for profile_id in ("long_term_stable", "conservative_quality"):
        row = by_profile.get(profile_id)
        if row and row["classification"] in {"robust_candidate", "context_dependent"}:
            items.append(
                f"{profile_id} can be treated as a stable baseline candidate "
                "within the current research set."
            )
        else:
            items.append(
                f"{profile_id} is not yet a stable baseline candidate without "
                "more windows or stronger consistency."
            )

    momentum = by_profile.get("momentum_breakout")
    if momentum and momentum["classification"] == "robust_candidate":
        items.append("momentum_breakout is the main aggressive candidate in this summary.")
    else:
        items.append(
            "momentum_breakout should be treated as context-dependent until it "
            "is supported across more windows."
        )

    items.append("right_tail_hunter requires filters before candidate use.")
    items.append(
        "volatility_expansion remains observation-only unless filtered results "
        "become stable with sufficient sample size."
    )

    strong_filters = [
        row
        for row in aggressive_summary
        if row["classification"] == "strong_filter_candidate"
    ]
    if strong_filters:
        names = ", ".join(
            f"{row['source_strategy_family']}:{row['filter_id']}"
            for row in strong_filters[:5]
        )
        items.append(f"Current strong filter candidates: {names}.")
    else:
        items.append("No aggressive filter should be promoted without more validation.")

    items.append("No production scoring changes are recommended yet.")
    return items


def _strategy_warnings(rows: list[dict[str, Any]], min_valid_count: int) -> list[str]:
    warnings = []
    if any((_number(row.get("valid_future_count")) or 0) < min_valid_count for row in rows):
        warnings.append("small_n_window")
    warnings.append("same_period_results_are_exploratory")
    return warnings


def _aggressive_warnings(rows: list[dict[str, Any]], min_valid_count: int) -> list[str]:
    warnings = []
    if any((_sample_count(row) or 0) < min_valid_count for row in rows):
        warnings.append("small_n_window")
    if any(row.get("validation_status") == "exploratory_same_period" for row in rows):
        warnings.append("exploratory_same_period")
    if any(
        (_number(row.get("right_tail_preservation_ratio")) or 1.0) < 0.65
        for row in rows
    ):
        warnings.append("right_tail_preservation_risk")
    return warnings


def _window_metrics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "window_id": row.get("window_id"),
            "as_of_date": row.get("as_of_date"),
            "horizon_days": row.get("horizon_days"),
            "valid_future_count": row.get("valid_future_count"),
            "average_excess_return": row.get("average_excess_return"),
            "outperform_rate": row.get("outperform_rate"),
            "top_5_average_return": row.get("top_5_average_return"),
            "validation_status": row.get("validation_status"),
        }
        for row in rows
    ]


def _first_text(rows: list[dict[str, Any]], key: str) -> str | None:
    for row in rows:
        value = row.get(key)
        if value is not None:
            return str(value)
    return None


def _metric_values(rows: list[dict[str, Any]], key: str) -> list[float]:
    return [value for value in (_number(row.get(key)) for row in rows) if value is not None]


def _metric_mean(rows: list[dict[str, Any]], key: str) -> float | None:
    return _mean(_metric_values(rows, key))


def _metric_median(rows: list[dict[str, Any]], key: str) -> float | None:
    return _median(_metric_values(rows, key))


def _metric_max(rows: list[dict[str, Any]], key: str) -> float | None:
    return _max(_metric_values(rows, key))


def _positive_count(rows: list[dict[str, Any]], key: str) -> int:
    return sum(1 for value in _metric_values(rows, key) if value > 0)


def _sample_count(row: dict[str, Any]) -> float | None:
    return _number(row.get("valid_future_count")) or _number(row.get("symbol_count_after_filter"))


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    return numeric


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _median(values: list[float]) -> float | None:
    return float(median(values)) if values else None


def _min(values: list[float]) -> float | None:
    return min(values) if values else None


def _max(values: list[float]) -> float | None:
    return max(values) if values else None


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
    return value


def _fmt(value: Any) -> str:
    numeric = _number(value)
    if numeric is None:
        return ""
    return f"{numeric:.4f}"

