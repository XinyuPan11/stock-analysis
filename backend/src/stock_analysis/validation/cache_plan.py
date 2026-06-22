from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from stock_analysis.validation.future_returns import (
    benchmark_aliases,
    calculate_future_return_label,
    load_cached_benchmark_history,
    load_cached_price_history,
)


def build_validation_cache_plan(
    *,
    as_of_date: str,
    horizon_days: int,
    outputs_dir: str | Path,
    cache_dir: str | Path,
    benchmark: str = "CSI300",
    provider: str = "baostock",
    limit: int | None = 50,
    target_end_date: str | None = None,
) -> dict[str, object]:
    symbols = _load_validation_symbols(Path(outputs_dir), as_of_date, limit=limit)
    symbols_to_prewarm: list[str] = []
    ok_count = 0
    symbol_statuses: list[dict[str, object]] = []
    for symbol in symbols:
        frame = load_cached_price_history(cache_dir, provider=provider, symbol=symbol)
        label = calculate_future_return_label(symbol, frame, as_of_date=as_of_date, horizon_days=horizon_days)
        status = str(label.get("data_quality", "missing_price"))
        if status == "ok":
            ok_count += 1
        else:
            symbols_to_prewarm.append(symbol)
        symbol_statuses.append({"symbol": symbol, "data_quality": status})

    benchmark_history, benchmark_symbol, benchmark_quality = load_cached_benchmark_history(cache_dir, provider=provider, benchmark=benchmark)
    benchmark_label = calculate_future_return_label(benchmark_symbol, benchmark_history, as_of_date=as_of_date, horizon_days=horizon_days)
    benchmark_future_quality = str(benchmark_label.get("data_quality", "missing_price")) if benchmark_quality == "ok" else benchmark_quality
    if benchmark_future_quality != "ok" and benchmark_symbol not in symbols_to_prewarm:
        symbols_to_prewarm.append(benchmark_symbol)

    return {
        "as_of_date": as_of_date,
        "horizon_days": horizon_days,
        "target_end_date": target_end_date or recommended_target_end_date(as_of_date, horizon_days),
        "symbol_count": len(symbols),
        "missing_future_count": len(symbols_to_prewarm),
        "ok_count": ok_count,
        "benchmark": benchmark,
        "benchmark_symbol": benchmark_symbol,
        "benchmark_data_quality": benchmark_future_quality,
        "symbols_to_prewarm": symbols_to_prewarm,
        "symbol_statuses": symbol_statuses,
        "provider_access": False,
    }


def recommended_target_end_date(as_of_date: str, horizon_days: int) -> str:
    if as_of_date == "2024-01-31" and horizon_days <= 20:
        return "2024-03-15"
    if as_of_date == "2024-01-31" and horizon_days <= 60:
        return "2024-05-31"
    return (pd.Timestamp(as_of_date) + pd.Timedelta(days=max(int(horizon_days * 2), 14))).strftime("%Y-%m-%d")


def write_cache_plan(plan: dict[str, object], output_file: str | Path) -> dict[str, str]:
    txt_path = Path(output_file)
    json_path = txt_path.with_suffix(".json")
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    symbols = [str(symbol) for symbol in plan.get("symbols_to_prewarm", [])]
    txt_path.write_text("\n".join(symbols) + ("\n" if symbols else ""), encoding="utf-8")
    json_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return {"symbols_file": str(txt_path), "json_file": str(json_path)}


def default_output_file(outputs_dir: str | Path, as_of_date: str, horizon_days: int, limit: int | None) -> Path:
    limit_part = "all" if limit is None or limit <= 0 else f"limit{limit}"
    return Path(outputs_dir) / "validation" / f"cache_plan_{as_of_date}_{horizon_days}d_{limit_part}.txt"


def _load_validation_symbols(outputs_dir: Path, as_of_date: str, *, limit: int | None) -> list[str]:
    symbols: list[str] = []
    for path in [
        outputs_dir / "labels" / f"stock_labels_{as_of_date}.json",
        outputs_dir / "labels" / f"candidate_labels_{as_of_date}.json",
        outputs_dir / "daily" / f"candidates_{as_of_date}.json",
    ]:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else []
        symbols = [str(row.get("symbol", "")).strip() for row in rows if isinstance(row, dict) and row.get("symbol")]
        if limit is not None and limit > 0:
            symbols = symbols[:limit]
        break
    return _dedupe([*symbols, *_load_list_symbols(outputs_dir, as_of_date)])


def _load_list_symbols(outputs_dir: Path, as_of_date: str) -> list[str]:
    list_dir = outputs_dir / "lists"
    if not list_dir.exists():
        return []
    symbols: list[str] = []
    for path in list_dir.glob(f"*_{as_of_date}.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        list_payloads = payload.get("lists", []) if isinstance(payload, dict) and path.name.startswith("multi_lists_") else [payload]
        for list_payload in list_payloads:
            items = list_payload.get("items", []) if isinstance(list_payload, dict) else []
            for item in items if isinstance(items, list) else []:
                if isinstance(item, dict) and item.get("symbol"):
                    symbols.append(str(item["symbol"]).strip())
    return symbols


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result

