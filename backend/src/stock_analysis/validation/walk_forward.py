from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from stock_analysis.validation.bias_metadata import validation_bias_metadata
from stock_analysis.validation.factor_effectiveness import evaluate_factor_effectiveness
from stock_analysis.validation.future_returns import calculate_future_return_labels, load_cached_benchmark_history, load_cached_price_history
from stock_analysis.validation.list_performance import SUPPORTED_LIST_IDS, evaluate_lists_performance


@dataclass(frozen=True)
class WalkForwardConfig:
    as_of_date: str
    horizon_days: int = 20
    benchmark: str = "CSI300"
    outputs_dir: str | Path = "outputs"
    cache_dir: str | Path = "data/cache/daily-use"
    provider: str = "baostock"
    list_ids: tuple[str, ...] = tuple(SUPPORTED_LIST_IDS)
    limit: int | None = 50
    dry_run: bool = True


def run_walk_forward_validation(config: WalkForwardConfig) -> dict[str, object]:
    """Run one as-of-date validation pass from static outputs and local cache only.

    No future leakage: candidate lists and scores are loaded as fixed as-of
    outputs. Future returns are calculated afterward only to validate them.
    """

    outputs_dir = Path(config.outputs_dir)
    labels = _load_label_rows(outputs_dir, config.as_of_date)
    labels = _limit_rows(labels, config.limit)
    list_payloads = _load_list_payloads(outputs_dir, config.as_of_date, config.list_ids)
    symbols = _dedupe([*_label_symbols(labels), *_list_payload_symbols(list_payloads)])
    benchmark_history, benchmark_symbol, benchmark_quality = load_cached_benchmark_history(
        config.cache_dir,
        provider=config.provider,
        benchmark=config.benchmark,
    )
    price_histories = {
        symbol: load_cached_price_history(config.cache_dir, provider=config.provider, symbol=symbol)
        for symbol in symbols
    }
    future_labels = calculate_future_return_labels(
        symbols,
        price_histories,
        as_of_date=config.as_of_date,
        horizon_days=config.horizon_days,
        benchmark_history=benchmark_history,
    )
    future_frame = pd.DataFrame(future_labels)
    list_performance = evaluate_lists_performance(list_payloads, future_frame, horizon_days=config.horizon_days)
    factor_rows = load_factor_rows_for_validation(outputs_dir, config.as_of_date, labels)
    factor_effectiveness = evaluate_factor_effectiveness(
        factor_rows,
        future_frame,
        as_of_date=config.as_of_date,
        horizon_days=config.horizon_days,
    )
    summary = _summary_payload(config, future_frame, list_performance, factor_effectiveness, benchmark_symbol=benchmark_symbol, benchmark_quality=benchmark_quality)
    result = {
        "summary": summary,
        "future_labels": future_labels,
        "list_performance": list_performance,
        "factor_effectiveness": factor_effectiveness,
        "outputs": {},
    }
    if not config.dry_run:
        result["outputs"] = write_validation_outputs(config, result)
    return result


def write_validation_outputs(config: WalkForwardConfig, result: dict[str, object]) -> dict[str, str]:
    validation_dir = Path(config.outputs_dir) / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"{config.as_of_date}_{config.horizon_days}d"
    paths = {
        "summary": validation_dir / f"walk_forward_summary_{suffix}.json",
        "predictions": validation_dir / f"walk_forward_predictions_{suffix}.csv",
        "list_performance": validation_dir / f"list_performance_{suffix}.json",
        "factor_effectiveness": validation_dir / f"factor_effectiveness_{suffix}.json",
        "report_md": validation_dir / f"walk_forward_report_{suffix}.md",
    }
    _write_json(paths["summary"], result["summary"])
    pd.DataFrame(sanitize_for_json(result["future_labels"])).to_csv(paths["predictions"], index=False, encoding="utf-8")
    _write_json(paths["list_performance"], result["list_performance"])
    _write_json(paths["factor_effectiveness"], result["factor_effectiveness"])
    paths["report_md"].write_text(_markdown_report(result), encoding="utf-8")
    return {key: str(path) for key, path in paths.items()}


def _summary_payload(
    config: WalkForwardConfig,
    future_frame: pd.DataFrame,
    list_performance: list[dict[str, object]],
    factor_effectiveness: list[dict[str, object]],
    benchmark_symbol: str,
    benchmark_quality: str,
) -> dict[str, object]:
    quality_counts = future_frame["data_quality"].value_counts().to_dict() if "data_quality" in future_frame.columns else {}
    valid = future_frame[future_frame.get("data_quality", "") == "ok"] if not future_frame.empty else pd.DataFrame()
    latest_input_date = _latest_date_from_column(future_frame, "latest_input_date")
    max_raw_cache_date = _latest_date_from_column(future_frame, "max_raw_cache_date")
    excluded_count = int(pd.to_numeric(future_frame.get("future_rows_excluded_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    return {
        "status": "dry_run" if config.dry_run else "ok",
        **validation_bias_metadata(),
        "as_of_date": config.as_of_date,
        "latest_input_date": latest_input_date,
        "max_raw_cache_date": max_raw_cache_date,
        "future_rows_excluded_count": excluded_count,
        "leakage_guard_applied": True,
        "feature_window_rule": "trade_date <= as_of_date",
        "label_window_rule": "trade_date > as_of_date; first horizon_days trading rows",
        "horizon_days": config.horizon_days,
        "benchmark": config.benchmark,
        "benchmark_symbol": benchmark_symbol,
        "benchmark_data_quality": benchmark_quality,
        "dry_run": config.dry_run,
        "no_future_leakage": True,
        "symbol_count": int(len(future_frame)),
        "valid_future_count": int(len(valid)),
        "data_quality_counts": quality_counts,
        "list_count": len(list_performance),
        "factor_count": len(factor_effectiveness),
    }


def _latest_date_from_column(frame: pd.DataFrame, column: str) -> str | None:
    if frame.empty or column not in frame.columns:
        return None
    values = frame[column].dropna().astype(str)
    return values.max() if not values.empty else None


def _load_label_rows(outputs_dir: Path, as_of_date: str) -> pd.DataFrame:
    candidates = [
        outputs_dir / "labels" / f"stock_labels_{as_of_date}.json",
        outputs_dir / "labels" / f"candidate_labels_{as_of_date}.json",
        outputs_dir / "daily" / f"candidates_{as_of_date}.json",
    ]
    for path in candidates:
        if path.exists():
            rows = json.loads(path.read_text(encoding="utf-8"))
            return pd.DataFrame(rows if isinstance(rows, list) else [])
    return pd.DataFrame()


def _load_list_payloads(outputs_dir: Path, as_of_date: str, list_ids: Iterable[str]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for list_id in list_ids:
        path = outputs_dir / "lists" / f"{list_id}_{as_of_date}.json"
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                result.append(payload)
        else:
            result.append({"list_id": list_id, "as_of_date": as_of_date, "items": [], "notes": ["missing_list_file"]})
    return result



def _label_symbols(labels: pd.DataFrame) -> list[str]:
    if labels.empty or "symbol" not in labels.columns:
        return []
    return [str(symbol).strip() for symbol in labels["symbol"].dropna().tolist() if str(symbol).strip()]


def _list_payload_symbols(list_payloads: Iterable[dict[str, object]]) -> list[str]:
    result: list[str] = []
    for payload in list_payloads:
        items = payload.get("items", []) if isinstance(payload, dict) else []
        for item in items if isinstance(items, list) else []:
            if isinstance(item, dict) and item.get("symbol"):
                result.append(str(item["symbol"]).strip())
    return result


def _dedupe(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result

def load_factor_rows_for_validation(outputs_dir: str | Path, as_of_date: str, labels: pd.DataFrame | None = None) -> pd.DataFrame:
    outputs_path = Path(outputs_dir)
    frames: list[pd.DataFrame] = []
    if labels is not None and not labels.empty:
        frames.append(_normalize_factor_source(labels))
    for path in [
        outputs_path / "labels" / f"stock_labels_{as_of_date}.json",
        outputs_path / "labels" / f"candidate_labels_{as_of_date}.json",
        outputs_path / "daily" / f"candidates_{as_of_date}.json",
        outputs_path / "daily" / f"factors_{as_of_date}.json",
    ]:
        rows = _load_json_rows(path)
        if rows:
            frames.append(_normalize_factor_source(pd.DataFrame(rows)))
    list_rows = _load_list_item_rows(outputs_path, as_of_date)
    if list_rows:
        frames.append(_normalize_factor_source(pd.DataFrame(list_rows)))
    return _merge_factor_frames(frames)


def _limit_rows(frame: pd.DataFrame, limit: int | None) -> pd.DataFrame:
    if limit is None or limit <= 0:
        return frame.copy()
    return frame.head(limit).copy()


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(sanitize_for_json(payload), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def sanitize_for_json(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): sanitize_for_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_for_json(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_for_json(item) for item in value]
    if isinstance(value, pd.DataFrame):
        return sanitize_for_json(value.to_dict(orient="records"))
    if isinstance(value, pd.Series):
        return sanitize_for_json(value.to_list())
    if hasattr(value, "item"):
        return sanitize_for_json(value.item())
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def _load_json_rows(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else []


def _load_list_item_rows(outputs_dir: Path, as_of_date: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    multi_path = outputs_dir / "lists" / f"multi_lists_{as_of_date}.json"
    if multi_path.exists():
        payload = json.loads(multi_path.read_text(encoding="utf-8"))
        for list_payload in payload.get("lists", []) if isinstance(payload, dict) else []:
            items = list_payload.get("items", []) if isinstance(list_payload, dict) else []
            rows.extend(item for item in items if isinstance(item, dict))
    if rows:
        return rows
    for path in (outputs_dir / "lists").glob(f"*_{as_of_date}.json"):
        if path.name.startswith("multi_lists_"):
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload.get("items", []) if isinstance(payload, dict) else []
        rows.extend(item for item in items if isinstance(item, dict))
    return rows


def _normalize_factor_source(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "symbol" not in frame.columns:
        return pd.DataFrame()
    flattened = pd.DataFrame([_flatten_record(row) for row in frame.to_dict(orient="records")])
    if "symbol" not in flattened.columns:
        return pd.DataFrame()
    result = pd.DataFrame({"symbol": flattened["symbol"].astype(str)})
    alias_map = {
        "total_score": ["total_score", "score_breakdown.total_score", "scores.total_score", "factor_values.total_score"],
        "momentum_score": ["momentum_score", "score_breakdown.momentum_score", "scores.momentum_score", "factor_values.momentum_score"],
        "trend_score": ["trend_score", "score_breakdown.trend_score", "scores.trend_score", "factor_values.trend_score"],
        "relative_strength_score": ["relative_strength_score", "score_breakdown.relative_strength_score", "scores.relative_strength_score", "factor_values.relative_strength_score"],
        "risk_score": ["risk_score", "score_breakdown.risk_score", "scores.risk_score", "factor_values.risk_score"],
        "liquidity_score": ["liquidity_score", "score_breakdown.liquidity_score", "scores.liquidity_score", "factor_values.liquidity_score"],
        "volatility": ["volatility", "volatility_20d", "volatility_60d"],
        "drawdown": ["drawdown", "max_drawdown", "max_drawdown_20d", "max_drawdown_60d"],
        "amount": ["amount", "avg_amount_20d", "avg_amount_60d"],
        "volume": ["volume", "avg_volume_20d", "avg_volume_60d"],
    }
    for output_column, candidates in alias_map.items():
        series = _first_available_numeric(flattened, candidates)
        if series is not None:
            result[output_column] = series
    return result


def _merge_factor_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    valid = [frame for frame in frames if frame is not None and not frame.empty and "symbol" in frame.columns]
    if not valid:
        return pd.DataFrame()
    merged = valid[0].drop_duplicates("symbol").set_index("symbol")
    for frame in valid[1:]:
        current = frame.drop_duplicates("symbol").set_index("symbol")
        merged = merged.combine_first(current)
    return merged.reset_index()


def _flatten_record(row: dict[str, object], *, prefix: str = "") -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in row.items():
        name = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            result.update(_flatten_record(value, prefix=name))
        else:
            result[name] = value
    return result


def _first_available_numeric(frame: pd.DataFrame, candidates: list[str]) -> pd.Series | None:
    result: pd.Series | None = None
    for column in candidates:
        if column not in frame.columns:
            continue
        current = pd.to_numeric(frame[column], errors="coerce")
        result = current if result is None else result.combine_first(current)
    return result


def _markdown_report(result: dict[str, object]) -> str:
    summary = result.get("summary", {})
    limitations = summary.get("known_bias_limitations", [])
    limitation_lines = [f"- `{item}`" for item in limitations] if isinstance(limitations, list) else []
    return "\n".join(
        [
            "# Controlled Walk-forward Validation Report",
            "",
            "No future leakage: future return labels are used only for after-the-fact validation.",
            "",
            f"- Status: {summary.get('status')}",
            f"- As-of date: {summary.get('as_of_date')}",
            f"- Horizon days: {summary.get('horizon_days')}",
            f"- Symbols: {summary.get('symbol_count')}",
            f"- Valid future labels: {summary.get('valid_future_count')}",
            "",
            "## Point-in-time and bias limitations",
            "",
            f"- Price point-in-time guard applied: {summary.get('price_point_in_time_guard_applied')}",
            f"- Feature input point-in-time status: {summary.get('feature_input_point_in_time_status')}",
            f"- Future label window status: {summary.get('future_label_window_status')}",
            f"- Universe point-in-time status: {summary.get('universe_point_in_time_status')}",
            f"- Listing status point-in-time status: {summary.get('listing_status_point_in_time_status')}",
            f"- ST status point-in-time status: {summary.get('st_status_point_in_time_status')}",
            f"- Suspension status point-in-time status: {summary.get('suspension_status_point_in_time_status')}",
            "",
            "Price and factor inputs are guarded by Phase 2.10. Historical universe and status metadata remain limited by current or non-versioned snapshots.",
            "",
            "Interpretation: controlled validation only, not a final production-grade historical simulation.",
            "",
            "Known bias limitations:",
            *limitation_lines,
        ]
    )

