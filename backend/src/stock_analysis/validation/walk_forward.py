from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from stock_analysis.validation.factor_effectiveness import evaluate_factor_effectiveness
from stock_analysis.validation.future_returns import calculate_future_return_labels, load_cached_price_history
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
    symbols = labels["symbol"].dropna().astype(str).tolist() if "symbol" in labels.columns else []
    benchmark_history = load_cached_price_history(
        config.cache_dir,
        provider=config.provider,
        symbol=config.benchmark,
        dataset="index_daily",
        adjusted=False,
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
    list_payloads = _load_list_payloads(outputs_dir, config.as_of_date, config.list_ids)
    list_performance = evaluate_lists_performance(list_payloads, future_frame, horizon_days=config.horizon_days)
    factor_rows = _load_factor_rows(outputs_dir, config.as_of_date, labels)
    factor_effectiveness = evaluate_factor_effectiveness(
        factor_rows,
        future_frame,
        as_of_date=config.as_of_date,
        horizon_days=config.horizon_days,
    )
    summary = _summary_payload(config, future_frame, list_performance, factor_effectiveness)
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
    pd.DataFrame(result["future_labels"]).to_csv(paths["predictions"], index=False, encoding="utf-8")
    _write_json(paths["list_performance"], result["list_performance"])
    _write_json(paths["factor_effectiveness"], result["factor_effectiveness"])
    paths["report_md"].write_text(_markdown_report(result), encoding="utf-8")
    return {key: str(path) for key, path in paths.items()}


def _summary_payload(
    config: WalkForwardConfig,
    future_frame: pd.DataFrame,
    list_performance: list[dict[str, object]],
    factor_effectiveness: list[dict[str, object]],
) -> dict[str, object]:
    quality_counts = future_frame["data_quality"].value_counts().to_dict() if "data_quality" in future_frame.columns else {}
    valid = future_frame[future_frame.get("data_quality", "") == "ok"] if not future_frame.empty else pd.DataFrame()
    return {
        "status": "dry_run" if config.dry_run else "ok",
        "as_of_date": config.as_of_date,
        "horizon_days": config.horizon_days,
        "benchmark": config.benchmark,
        "dry_run": config.dry_run,
        "no_future_leakage": True,
        "symbol_count": int(len(future_frame)),
        "valid_future_count": int(len(valid)),
        "data_quality_counts": quality_counts,
        "list_count": len(list_performance),
        "factor_count": len(factor_effectiveness),
    }


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


def _load_factor_rows(outputs_dir: Path, as_of_date: str, labels: pd.DataFrame) -> pd.DataFrame:
    path = outputs_dir / "daily" / f"factors_{as_of_date}.json"
    if path.exists():
        rows = json.loads(path.read_text(encoding="utf-8"))
        return pd.DataFrame(rows if isinstance(rows, list) else [])
    return labels.copy()


def _limit_rows(frame: pd.DataFrame, limit: int | None) -> pd.DataFrame:
    if limit is None or limit <= 0:
        return frame.copy()
    return frame.head(limit).copy()


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _markdown_report(result: dict[str, object]) -> str:
    summary = result.get("summary", {})
    return "\n".join(
        [
            "# Phase 2.7.2 Walk-forward Validation Report",
            "",
            "No future leakage: future return labels are used only for after-the-fact validation.",
            "",
            f"- Status: {summary.get('status')}",
            f"- As-of date: {summary.get('as_of_date')}",
            f"- Horizon days: {summary.get('horizon_days')}",
            f"- Symbols: {summary.get('symbol_count')}",
            f"- Valid future labels: {summary.get('valid_future_count')}",
        ]
    )

