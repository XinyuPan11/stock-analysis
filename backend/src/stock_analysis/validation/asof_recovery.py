from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from stock_analysis.validation.forward_expansion import CacheCoverageConfig, check_cache_coverage
from stock_analysis.validation.multi_asof_validation import (
    MultiAsOfValidationConfig,
    build_multi_asof_validation_plan,
    future_window_for,
)
from stock_analysis.validation.walk_forward import sanitize_for_json
from stock_analysis.validation.window_readiness import classify_validation_quality

TARGET_AS_OF_DATE = "2024-10-31"
TARGET_HORIZON_DAYS = 20
TARGET_YEAR_END = "2024-12-31"
OUTPUT_NAME = "asof_recovery_2024-10-31_20d.json"


@dataclass(frozen=True)
class ControlledAsOfRecoveryConfig:
    outputs_dir: str | Path = "outputs"
    cache_dir: str | Path = "data/cache/daily-use"
    provider: str = "baostock"
    benchmark: str = "CSI300"
    limit: int | None = 300
    min_valid_count: int = 50
    min_coverage_rate: float = 0.7
    write_output: bool = False


def diagnose_controlled_2024_10_31_20d_recovery(
    config: ControlledAsOfRecoveryConfig,
) -> dict[str, Any]:
    outputs_dir = Path(config.outputs_dir)
    plan = _load_or_build_target_plan(config)
    horizon = _find_horizon(plan) or {}
    requirement = _find_cache_requirement(plan) or {}
    future_window = horizon.get("future_window") or future_window_for(
        TARGET_AS_OF_DATE,
        TARGET_HORIZON_DAYS,
    )
    missing_as_of_outputs = horizon.get("missing_as_of_outputs") or {}
    required_outputs = horizon.get("required_outputs") or _required_validation_outputs(outputs_dir)
    existing_outputs = horizon.get("existing_outputs") or {
        key: str(Path(path))
        for key, path in required_outputs.items()
        if Path(path).exists()
    }
    missing_outputs = horizon.get("missing_outputs") or {
        key: str(Path(path))
        for key, path in required_outputs.items()
        if not Path(path).exists()
    }

    symbol_details = _candidate_symbols(outputs_dir, limit=config.limit)
    prediction_details = _prediction_quality_details(outputs_dir, config)
    symbols_file = _symbols_file(outputs_dir)
    cache_details = _cache_details(config, symbols_file, future_window)
    future_recoverable = str(future_window.get("end_date")) <= TARGET_YEAR_END

    if missing_as_of_outputs:
        status = "blocked_missing_as_of_outputs"
        root_cause = "missing_as_of_outputs"
    elif str(future_window.get("end_date")) > TARGET_YEAR_END:
        status = "deferred_crosses_2025"
        root_cause = "future_window_crosses_2025"
    elif not symbols_file.exists():
        status = "missing_symbols_file"
        root_cause = "symbols_file_missing"
    elif cache_details.get("coverage_rate") is not None and float(cache_details.get("coverage_rate") or 0.0) < config.min_coverage_rate:
        status = "missing_cache"
        root_cause = "cache_coverage_below_threshold"
    elif missing_outputs:
        status = "missing_validation_outputs"
        root_cause = "validation_outputs_missing"
    elif prediction_details["quality_status"] == "high_quality":
        status = "recovered_valid"
        root_cause = "none"
    else:
        status = "recovered_low_quality"
        root_cause = str(prediction_details["quality_status"])

    as_of_recoverable_with_cache_only = bool(
        future_recoverable
        and not missing_as_of_outputs
        and str(future_window.get("end_date")) <= TARGET_YEAR_END
    )

    payload: dict[str, Any] = {
        "status": status,
        "root_cause": root_cause,
        "as_of_date": TARGET_AS_OF_DATE,
        "horizon_days": TARGET_HORIZON_DAYS,
        "benchmark": config.benchmark,
        "provider_access": False,
        "prewarm_executed": False,
        "daily_research_executed": False,
        "validation_executed": False,
        "full_workflow_executed": False,
        "production_scoring_changed": False,
        "future_window": future_window,
        "required_future_end_date": future_window.get("end_date"),
        "future_window_recoverable_with_late_2024_cache": future_recoverable,
        "as_of_result_recoverable_with_cache_through_late_2024_only": as_of_recoverable_with_cache_only,
        "candidate_count": symbol_details["candidate_count"],
        "candidate_count_before_limit": symbol_details["candidate_count_before_limit"],
        "candidate_sources": symbol_details["candidate_sources"],
        "symbols_file": str(symbols_file),
        "symbols_file_exists": symbols_file.exists(),
        "symbols_file_symbol_count": _symbols_file_count(symbols_file),
        "valid_future_count": prediction_details["valid_future_count"],
        "prediction_count": prediction_details["prediction_count"],
        "valid_coverage_ratio": prediction_details["valid_coverage_ratio"],
        "missing_price_count": prediction_details["missing_price_count"],
        "insufficient_future_window_count": prediction_details["insufficient_future_window_count"],
        "data_quality_counts": prediction_details["data_quality_counts"],
        "quality_status": prediction_details["quality_status"],
        "comparison_eligible": prediction_details["comparison_eligible"],
        "high_quality_ready": prediction_details["high_quality_ready"],
        "skipped_symbols": prediction_details["skipped_symbols"],
        "missing_as_of_outputs": missing_as_of_outputs,
        "required_outputs": required_outputs,
        "existing_outputs": existing_outputs,
        "missing_outputs": missing_outputs,
        "cache_coverage": cache_details,
        "next_manual_commands": _next_manual_commands(config, status, missing_as_of_outputs),
        "notes": _notes(status, future_recoverable, missing_as_of_outputs),
    }
    if config.write_output:
        payload["output_file"] = write_controlled_asof_recovery_diagnostic(payload, outputs_dir)
    return sanitize_for_json(payload)


def write_controlled_asof_recovery_diagnostic(
    payload: dict[str, Any],
    outputs_dir: str | Path,
) -> str:
    path = Path(outputs_dir) / "experiments" / OUTPUT_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(sanitize_for_json(payload), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return str(path)


def _load_or_build_target_plan(config: ControlledAsOfRecoveryConfig) -> dict[str, Any]:
    outputs_dir = Path(config.outputs_dir)
    plan_path = outputs_dir / "experiments" / "multi_asof_validation_plan_2024.json"
    if plan_path.exists():
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        if _find_horizon(plan):
            return plan
    return build_multi_asof_validation_plan(
        MultiAsOfValidationConfig(
            outputs_dir=outputs_dir,
            cache_dir=config.cache_dir,
            provider=config.provider,
            benchmark=config.benchmark,
            as_of_dates=(TARGET_AS_OF_DATE,),
            horizons=(TARGET_HORIZON_DAYS,),
            recommended_limit=config.limit or 0,
        )
    )


def _find_horizon(plan: dict[str, Any]) -> dict[str, Any] | None:
    for as_of in plan.get("as_of_plan", []):
        if not isinstance(as_of, dict) or as_of.get("as_of_date") != TARGET_AS_OF_DATE:
            continue
        for horizon in as_of.get("horizons", []):
            if isinstance(horizon, dict) and horizon.get("horizon_days") == TARGET_HORIZON_DAYS:
                return horizon
    return None


def _find_cache_requirement(plan: dict[str, Any]) -> dict[str, Any] | None:
    for requirement in plan.get("cache_requirements", []):
        if isinstance(requirement, dict) and requirement.get("cache_requirement_id") == f"{TARGET_AS_OF_DATE}_{TARGET_HORIZON_DAYS}d":
            return requirement
    return None


def _required_validation_outputs(outputs_dir: Path) -> dict[str, str]:
    suffix = f"{TARGET_AS_OF_DATE}_{TARGET_HORIZON_DAYS}d"
    return {
        "walk_forward_predictions": str(outputs_dir / "validation" / f"walk_forward_predictions_{suffix}.csv"),
        "list_performance": str(outputs_dir / "validation" / f"list_performance_{suffix}.json"),
        "factor_effectiveness": str(outputs_dir / "validation" / f"factor_effectiveness_{suffix}.json"),
        "strategy_family_experiments": str(outputs_dir / "experiments" / f"strategy_family_experiments_{suffix}.json"),
        "aggressive_filter_experiments": str(outputs_dir / "experiments" / f"aggressive_filter_experiments_{suffix}.json"),
    }


def _candidate_symbols(outputs_dir: Path, *, limit: int | None) -> dict[str, Any]:
    symbols: list[str] = []
    sources: list[str] = []
    for path in [
        outputs_dir / "labels" / f"stock_labels_{TARGET_AS_OF_DATE}.json",
        outputs_dir / "labels" / f"candidate_labels_{TARGET_AS_OF_DATE}.json",
        outputs_dir / "daily" / f"candidates_{TARGET_AS_OF_DATE}.json",
    ]:
        rows = _load_json_rows(path)
        found = _symbols_from_rows(rows)
        if found:
            symbols.extend(found)
            sources.append(str(path))
    for path in (outputs_dir / "lists").glob(f"*_{TARGET_AS_OF_DATE}.json"):
        rows = _list_symbols(path)
        if rows:
            symbols.extend(rows)
            sources.append(str(path))
    deduped = _dedupe(symbols)
    limited = deduped[:limit] if limit and limit > 0 else deduped
    return {
        "candidate_count": len(limited),
        "candidate_count_before_limit": len(deduped),
        "candidate_sources": sources,
        "symbols": limited,
    }


def _prediction_quality_details(
    outputs_dir: Path,
    config: ControlledAsOfRecoveryConfig,
) -> dict[str, Any]:
    path = outputs_dir / "validation" / f"walk_forward_predictions_{TARGET_AS_OF_DATE}_{TARGET_HORIZON_DAYS}d.csv"
    if not path.exists():
        classified = classify_validation_quality(None, None, config.min_valid_count, config.min_coverage_rate)
        return {
            "prediction_count": 0,
            "valid_future_count": 0,
            "missing_price_count": 0,
            "insufficient_future_window_count": 0,
            "data_quality_counts": {},
            "skipped_symbols": [],
            **classified,
        }
    frame = pd.read_csv(path, dtype={"symbol": str, "data_quality": str})
    if "data_quality" not in frame.columns:
        frame["data_quality"] = "unknown"
    counts = frame["data_quality"].fillna("unknown").value_counts().to_dict()
    valid_count = int(counts.get("ok", 0))
    classified = classify_validation_quality(
        int(len(frame)),
        valid_count,
        config.min_valid_count,
        config.min_coverage_rate,
    )
    skipped = []
    for row in frame[frame["data_quality"] != "ok"].head(50).to_dict(orient="records"):
        skipped.append(
            {
                "symbol": row.get("symbol"),
                "reason": row.get("data_quality"),
            }
        )
    return {
        "prediction_count": int(len(frame)),
        "valid_future_count": valid_count,
        "missing_price_count": int(counts.get("missing_price", 0)),
        "insufficient_future_window_count": int(counts.get("insufficient_future_window", 0)),
        "data_quality_counts": counts,
        "skipped_symbols": skipped,
        **classified,
    }


def _cache_details(
    config: ControlledAsOfRecoveryConfig,
    symbols_file: Path,
    future_window: dict[str, Any],
) -> dict[str, Any]:
    if not symbols_file.exists():
        return {
            "status": "symbols_file_missing",
            "symbol_count": 0,
            "covered_count": 0,
            "missing_count": 0,
            "coverage_rate": None,
        }
    try:
        report = check_cache_coverage(
            CacheCoverageConfig(
                start_date=str(future_window.get("start_date")),
                end_date=str(future_window.get("end_date")),
                cache_dir=config.cache_dir,
                outputs_dir=config.outputs_dir,
                symbols_file=symbols_file,
                limit=config.limit,
                provider=config.provider,
            )
        )
    except (FileNotFoundError, ValueError) as exc:
        return {
            "status": "unavailable",
            "error": str(exc),
            "symbol_count": 0,
            "covered_count": 0,
            "missing_count": 0,
            "coverage_rate": None,
        }
    return {
        "status": report.get("status"),
        "symbol_count": report.get("symbol_count"),
        "covered_count": report.get("covered_count"),
        "missing_count": report.get("missing_count"),
        "coverage_rate": report.get("coverage_rate"),
        "date_range": report.get("date_range"),
    }


def _symbols_file(outputs_dir: Path) -> Path:
    return outputs_dir / "cache_plans" / f"multi_asof_symbols_{TARGET_AS_OF_DATE}_{TARGET_HORIZON_DAYS}d.txt"


def _symbols_file_count(path: Path) -> int:
    if not path.exists():
        return 0
    return len([line for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.strip().startswith("#")])


def _next_manual_commands(
    config: ControlledAsOfRecoveryConfig,
    status: str,
    missing_as_of_outputs: dict[str, Any],
) -> list[str]:
    outputs_dir = Path(config.outputs_dir)
    commands: list[str] = []
    if missing_as_of_outputs:
        commands.extend(
            [
                "python backend\\scripts\\run_daily_research.py "
                f"--provider {config.provider} --end-date {TARGET_AS_OF_DATE} "
                f"--cache-dir {config.cache_dir} --output-dir {outputs_dir / 'daily'} "
                f"--limit {config.limit or 0}",
                "python backend\\scripts\\generate_research_views.py "
                f"--date {TARGET_AS_OF_DATE} --outputs-dir {config.outputs_dir} "
                f"--cache-dir {config.cache_dir}",
                "python backend\\scripts\\generate_multi_asof_validation_plan.py "
                f"--outputs-dir {config.outputs_dir} --cache-dir {config.cache_dir} "
                f"--as-of-dates {TARGET_AS_OF_DATE} --horizons {TARGET_HORIZON_DAYS} "
                f"--recommended-limit {config.limit or 0}",
            ]
        )
        return commands
    if status in {"missing_symbols_file", "missing_cache"}:
        commands.append(
            "python backend\\scripts\\generate_multi_asof_validation_plan.py "
            f"--outputs-dir {config.outputs_dir} --cache-dir {config.cache_dir} "
            f"--as-of-dates {TARGET_AS_OF_DATE} --horizons {TARGET_HORIZON_DAYS} "
            f"--recommended-limit {config.limit or 0}"
        )
    commands.append(
        "python backend\\scripts\\run_controlled_validation_batch.py "
        f"--as-of-date {TARGET_AS_OF_DATE} --horizon-days {TARGET_HORIZON_DAYS} "
        f"--benchmark {config.benchmark} --outputs-dir {config.outputs_dir} "
        f"--cache-dir {config.cache_dir} --limit {config.limit or 0} --write-output"
    )
    return commands


def _notes(
    status: str,
    future_recoverable: bool,
    missing_as_of_outputs: dict[str, Any],
) -> list[str]:
    notes = [
        "diagnostic_only_no_provider_access",
        "target_locked_to_2024_10_31_20d",
    ]
    if future_recoverable:
        notes.append("future_window_ends_in_2024")
    if missing_as_of_outputs:
        notes.append("generate_as_of_outputs_before_cache_or_validation_recovery")
    if status == "missing_validation_outputs":
        notes.append("run_controlled_validation_batch_after_cache_coverage_is_ready")
    return notes


def _load_json_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def _list_symbols(path: Path) -> list[str]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("lists"), list):
        symbols = []
        for list_payload in payload["lists"]:
            if isinstance(list_payload, dict):
                symbols.extend(_symbols_from_rows(list_payload.get("items", [])))
        return symbols
    if isinstance(payload, dict):
        return _symbols_from_rows(payload.get("items", []))
    return []


def _symbols_from_rows(rows: object) -> list[str]:
    if not isinstance(rows, list):
        return []
    return [
        str(row.get("symbol", "")).strip()
        for row in rows
        if isinstance(row, dict) and str(row.get("symbol", "")).strip()
    ]


def _dedupe(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result
