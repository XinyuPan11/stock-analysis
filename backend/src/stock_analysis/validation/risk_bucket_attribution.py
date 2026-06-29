"""Read-only disjoint risk-bucket attribution from existing validation outputs."""

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
SUMMARY_JSON_NAME = "risk_bucket_disjoint_attribution_2024.json"
SUMMARY_MARKDOWN_NAME = "risk_bucket_disjoint_attribution_2024.md"
DISCLAIMER = (
    "Research-only risk-bucket attribution. This report evaluates whether an "
    "existing bucket is useful as a risk warning; it does not change production "
    "scoring, recommendations, rankings, factors, or validation labels."
)


@dataclass(frozen=True)
class RiskBucketAttributionConfig:
    outputs_dir: str | Path = "outputs"
    windows: tuple[tuple[str, int], ...] = DEFAULT_WINDOWS
    min_bucket_sample: int = 5
    negative_window_ratio: float = 0.75


def build_risk_bucket_attribution(
    config: RiskBucketAttributionConfig,
) -> dict[str, Any]:
    outputs_dir = Path(config.outputs_dir)
    windows: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    overlap_rows: list[dict[str, Any]] = []
    source_files: list[str] = []

    for as_of_date, horizon_days in config.windows:
        suffix = f"{as_of_date}_{horizon_days}d"
        predictions_path = (
            outputs_dir / "validation" / f"walk_forward_predictions_{suffix}.csv"
        )
        membership_path = (
            outputs_dir / "lists" / f"high_risk_active_{as_of_date}.json"
        )
        missing = [
            str(path)
            for path in (predictions_path, membership_path)
            if not path.exists()
        ]
        if missing:
            excluded.append(
                {
                    "as_of_date": as_of_date,
                    "horizon_days": horizon_days,
                    "status": (
                        "missing_membership"
                        if not membership_path.exists()
                        else "missing_predictions"
                    ),
                    "missing_files": missing,
                }
            )
            continue

        predictions = pd.read_csv(predictions_path, dtype={"symbol": str})
        high_risk_symbols = _load_list_symbols(membership_path)
        window = _build_window(
            predictions,
            high_risk_symbols,
            as_of_date=as_of_date,
            horizon_days=horizon_days,
        )
        windows.append(window)
        overlap_rows.extend(
            _list_overlap_rows(
                outputs_dir,
                as_of_date,
                horizon_days,
                high_risk_symbols,
            )
        )
        source_files.extend([str(predictions_path), str(membership_path)])

    high_risk_summary = _aggregate_cohort(windows, "high_risk_active")
    non_high_risk_summary = _aggregate_cohort(
        windows, "non_high_risk_disjoint"
    )
    classification = _classify_high_risk_bucket(
        high_risk_summary,
        non_high_risk_summary,
        min_bucket_sample=config.min_bucket_sample,
        negative_window_ratio=config.negative_window_ratio,
    )
    available = bool(windows) and not excluded

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
                "disjoint_attribution_available": available,
                "included_window_count": len(windows),
                "excluded_window_count": len(excluded),
                "classification": classification,
                "min_bucket_sample": config.min_bucket_sample,
                "negative_window_ratio": config.negative_window_ratio,
                "disclaimer": DISCLAIMER,
            },
            "window_attribution": windows,
            "cohort_summary": {
                "high_risk_active": high_risk_summary,
                "non_high_risk_disjoint": non_high_risk_summary,
            },
            "overlap_awareness": overlap_rows,
            "excluded_windows": excluded,
            "interpretation": [
                "The two primary cohorts are disjoint within every included window.",
                "A stable negative classification supports further risk-warning and candidate-downgrade analysis only.",
                "No production formula or recommendation change is supported by this report alone.",
            ],
            "limitations": [
                "The four windows are same-year controlled observations, not an out-of-sample production simulation.",
                "Historical universe and status metadata remain current-snapshot limited.",
                "Other research lists overlap; their overlap counts are descriptive and are not independent cohorts.",
                "The high-risk bucket is small in some windows, so sample counts remain visible in every result.",
            ],
            "source_files": sorted(source_files),
            "outputs": {},
        }
    )


def write_risk_bucket_attribution_outputs(
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
        render_risk_bucket_attribution_markdown(report),
        encoding="utf-8",
    )
    return report["outputs"]


def render_risk_bucket_attribution_markdown(
    report: dict[str, Any],
) -> str:
    summary = report["summary"]
    lines = [
        "# Controlled Disjoint Risk-Bucket Attribution",
        "",
        str(summary["disclaimer"]),
        "",
        f"- Classification: `{summary['classification']}`",
        f"- Disjoint attribution available: `{summary['disjoint_attribution_available']}`",
        f"- Included windows: `{summary['included_window_count']}`",
        "",
        "## Window Attribution",
        "",
        "| As-of date | Cohort | Count | Avg future | Avg excess | Win rate | Outperform | Avg drawdown | <= -10% | Loss concentration |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for window in report.get("window_attribution", []):
        for cohort_id in ("high_risk_active", "non_high_risk_disjoint"):
            row = window["cohorts"][cohort_id]
            lines.append(
                f"| {window['as_of_date']} | {cohort_id} | "
                f"{row['sample_count']} | {_fmt(row.get('average_future_return'))} | "
                f"{_fmt(row.get('average_excess_return'))} | "
                f"{_fmt(row.get('win_rate'))} | "
                f"{_fmt(row.get('outperform_rate'))} | "
                f"{_fmt(row.get('average_drawdown'))} | "
                f"{_fmt(row.get('failure_rate_below_minus_10pct'))} | "
                f"{_fmt(row.get('bottom_decile_loss_concentration_ratio'))} |"
            )

    lines.extend(
        [
            "",
            "## Cross-Window Cohort Summary",
            "",
            "| Cohort | Windows | Sample min/median | Avg excess mean | Negative windows | Direction | Avg drawdown |",
            "|---|---:|---:|---:|---:|---|---:|",
        ]
    )
    for cohort_id, row in report.get("cohort_summary", {}).items():
        lines.append(
            f"| {cohort_id} | {row['valid_window_count']} | "
            f"{_fmt(row.get('sample_count_min'))}/{_fmt(row.get('sample_count_median'))} | "
            f"{_fmt(row.get('average_excess_return_mean'))} | "
            f"{row['negative_excess_window_count']} | "
            f"{row['excess_sign_consistency']} | "
            f"{_fmt(row.get('average_drawdown_mean'))} |"
        )

    lines.extend(["", "## Overlap Awareness", ""])
    if report.get("overlap_awareness"):
        lines.extend(
            [
                "| As-of date | Other list | Overlap count | High-risk share |",
                "|---|---|---:|---:|",
            ]
        )
        for row in report["overlap_awareness"]:
            lines.append(
                f"| {row['as_of_date']} | {row['list_id']} | "
                f"{row['overlap_count']} | {_fmt(row.get('high_risk_overlap_rate'))} |"
            )
    else:
        lines.append("No optional list-overlap files were available.")

    lines.extend(["", "## Interpretation Boundary", ""])
    for item in report.get("interpretation", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Limitations", ""])
    for item in report.get("limitations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def _build_window(
    predictions: pd.DataFrame,
    high_risk_symbols: set[str],
    *,
    as_of_date: str,
    horizon_days: int,
) -> dict[str, Any]:
    if "symbol" not in predictions.columns:
        raise ValueError("Prediction output is missing required symbol column.")
    frame = predictions.drop_duplicates(subset=["symbol"], keep="first").copy()
    frame["symbol"] = frame["symbol"].astype(str)
    valid = frame.copy()
    if "data_quality" in valid.columns:
        valid = valid[valid["data_quality"].astype(str) == "ok"].copy()
    valid_symbols = set(valid["symbol"])
    matched_high_risk = valid_symbols & high_risk_symbols
    non_high_risk = valid_symbols - high_risk_symbols
    overlap = matched_high_risk & non_high_risk

    high_frame = valid[valid["symbol"].isin(matched_high_risk)].copy()
    non_high_frame = valid[valid["symbol"].isin(non_high_risk)].copy()
    return {
        "as_of_date": as_of_date,
        "horizon_days": horizon_days,
        "prediction_count": int(len(frame)),
        "valid_prediction_count": int(len(valid)),
        "high_risk_membership_count": len(high_risk_symbols),
        "matched_high_risk_count": len(matched_high_risk),
        "unmatched_high_risk_symbols": sorted(high_risk_symbols - valid_symbols),
        "disjoint_overlap_count": len(overlap),
        "disjoint_check_passed": not overlap
        and len(matched_high_risk) + len(non_high_risk) == len(valid_symbols),
        "cohorts": {
            "high_risk_active": _cohort_metrics(high_frame),
            "non_high_risk_disjoint": _cohort_metrics(non_high_frame),
        },
    }


def _cohort_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    returns = _numeric(frame, "future_return")
    excess = _numeric(frame, "future_excess_return")
    drawdown = _numeric(frame, "max_drawdown_during_holding")
    negative_returns = returns[returns < 0]
    bottom_count = max(1, math.ceil(len(returns) * 0.1)) if len(returns) else 0
    bottom = returns.nsmallest(bottom_count) if bottom_count else returns
    total_loss = float(negative_returns.abs().sum())
    concentration = (
        float(bottom[bottom < 0].abs().sum()) / total_loss
        if total_loss > 0
        else None
    )
    return {
        "sample_count": int(len(frame)),
        "average_future_return": _series_mean(returns),
        "average_excess_return": _series_mean(excess),
        "win_rate": float((returns > 0).mean()) if len(returns) else None,
        "outperform_rate": _boolean_rate(frame, "outperformed_benchmark"),
        "average_drawdown": _series_mean(drawdown),
        "failure_rate_below_minus_10pct": (
            float((returns <= -0.10).mean()) if len(returns) else None
        ),
        "failure_rate_below_minus_20pct": (
            float((returns <= -0.20).mean()) if len(returns) else None
        ),
        "bottom_5_average_return": _series_mean(returns.nsmallest(5)),
        "bottom_decile_loss_concentration_ratio": concentration,
    }


def _aggregate_cohort(
    windows: Iterable[dict[str, Any]],
    cohort_id: str,
) -> dict[str, Any]:
    rows = [window["cohorts"][cohort_id] for window in windows]
    samples = _numbers(rows, "sample_count")
    excess = _numbers(rows, "average_excess_return")
    return {
        "cohort_id": cohort_id,
        "valid_window_count": len(rows),
        "sample_count_total": int(sum(samples)),
        "sample_count_min": min(samples) if samples else None,
        "sample_count_median": median(samples) if samples else None,
        "average_future_return_mean": _mean(
            _numbers(rows, "average_future_return")
        ),
        "average_excess_return_mean": _mean(excess),
        "average_excess_return_median": _median(excess),
        "negative_excess_window_count": sum(value < 0 for value in excess),
        "positive_excess_window_count": sum(value > 0 for value in excess),
        "excess_sign_consistency": _sign_consistency(excess),
        "win_rate_mean": _mean(_numbers(rows, "win_rate")),
        "outperform_rate_mean": _mean(_numbers(rows, "outperform_rate")),
        "average_drawdown_mean": _mean(_numbers(rows, "average_drawdown")),
        "failure_rate_below_minus_10pct_mean": _mean(
            _numbers(rows, "failure_rate_below_minus_10pct")
        ),
        "failure_rate_below_minus_20pct_mean": _mean(
            _numbers(rows, "failure_rate_below_minus_20pct")
        ),
        "bottom_decile_loss_concentration_ratio_mean": _mean(
            _numbers(rows, "bottom_decile_loss_concentration_ratio")
        ),
    }


def _classify_high_risk_bucket(
    high_risk: dict[str, Any],
    non_high_risk: dict[str, Any],
    *,
    min_bucket_sample: int,
    negative_window_ratio: float,
) -> str:
    window_count = int(high_risk.get("valid_window_count") or 0)
    sample_min = float(high_risk.get("sample_count_min") or 0)
    if window_count < 3 or sample_min < min_bucket_sample:
        return "insufficient_sample"
    high_excess = high_risk.get("average_excess_return_mean")
    non_high_excess = non_high_risk.get("average_excess_return_mean")
    negative_count = int(high_risk.get("negative_excess_window_count") or 0)
    if (
        isinstance(high_excess, (int, float))
        and isinstance(non_high_excess, (int, float))
        and high_excess < 0
        and high_excess < non_high_excess
        and negative_count / window_count >= negative_window_ratio
    ):
        return "stable_negative_risk_bucket"
    return "mixed"


def _list_overlap_rows(
    outputs_dir: Path,
    as_of_date: str,
    horizon_days: int,
    high_risk_symbols: set[str],
) -> list[dict[str, Any]]:
    performance_path = (
        outputs_dir
        / "validation"
        / f"list_performance_{as_of_date}_{horizon_days}d.json"
    )
    if not performance_path.exists():
        return []
    payload = json.loads(performance_path.read_text(encoding="utf-8-sig"))
    rows = payload if isinstance(payload, list) else []
    result = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        list_id = str(row.get("list_id", "")).strip()
        if not list_id or list_id == "high_risk_active":
            continue
        path = outputs_dir / "lists" / f"{list_id}_{as_of_date}.json"
        if not path.exists():
            continue
        symbols = _load_list_symbols(path)
        overlap = high_risk_symbols & symbols
        result.append(
            {
                "as_of_date": as_of_date,
                "horizon_days": horizon_days,
                "list_id": list_id,
                "high_risk_count": len(high_risk_symbols),
                "other_list_count": len(symbols),
                "overlap_count": len(overlap),
                "high_risk_overlap_rate": (
                    len(overlap) / len(high_risk_symbols)
                    if high_risk_symbols
                    else None
                ),
            }
        )
    return result


def _load_list_symbols(path: Path) -> set[str]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    items = payload.get("items", [])
    if not isinstance(items, list):
        raise ValueError(f"Expected list items: {path}")
    return {
        str(item["symbol"]).strip()
        for item in items
        if isinstance(item, dict) and str(item.get("symbol", "")).strip()
    }


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
