from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from stock_analysis.validation.forward_expansion import (
    CacheCoverageConfig,
    check_cache_coverage,
)
from stock_analysis.validation.multi_asof_validation import (
    MultiAsOfValidationConfig,
    build_multi_asof_validation_plan,
    write_multi_asof_outputs,
)
from stock_analysis.validation.walk_forward import sanitize_for_json


@dataclass(frozen=True)
class ValidationWindowReadinessConfig:
    as_of_date: str
    horizon_days: int
    outputs_dir: str | Path = "outputs"
    cache_dir: str | Path = "data\\cache\\daily-use"
    limit: int | None = 50
    benchmark: str = "CSI300"
    min_valid_count: int = 50
    min_coverage_rate: float = 0.7
    provider: str = "baostock"
    write_output: bool = False


def check_validation_window_readiness(
    config: ValidationWindowReadinessConfig,
) -> dict[str, Any]:
    outputs_dir = Path(config.outputs_dir)
    plan = _load_or_build_plan(config)
    horizon = _find_horizon(plan, config.as_of_date, config.horizon_days)
    requirement = _find_cache_requirement(plan, config.as_of_date, config.horizon_days)
    suffix = f"{config.as_of_date}_{config.horizon_days}d"
    symbols_file = _symbols_file_path(outputs_dir, config.as_of_date, config.horizon_days)
    future_window = horizon.get("future_window", {}) if horizon else {}

    base: dict[str, Any] = {
        "as_of_date": config.as_of_date,
        "horizon_days": config.horizon_days,
        "benchmark": config.benchmark,
        "provider_access": False,
        "prewarm_executed": False,
        "full_workflow_executed": False,
        "production_scoring_changed": False,
        "symbols_file": str(symbols_file),
        "symbol_count": None,
        "covered_count": None,
        "missing_count": None,
        "coverage_rate": None,
        "prediction_count": None,
        "valid_prediction_count": None,
        "valid_coverage_ratio": None,
        "missing_outputs": {},
        "missing_as_of_outputs": {},
        "notes": [],
    }

    if not horizon:
        return _finish(
            base,
            "blocked_missing_as_of_outputs",
            _plan_command(config),
            ["window_not_found_in_plan"],
            config,
        )
    if horizon.get("crosses_2025_boundary"):
        return _finish(
            {**base, "future_window": future_window},
            "deferred",
            "No command: deferred because the future window crosses 2025.",
            ["deferred_crosses_2025"],
            config,
        )

    missing_as_of = horizon.get("missing_as_of_outputs") or {}
    if missing_as_of:
        return _finish(
            {
                **base,
                "future_window": future_window,
                "missing_as_of_outputs": missing_as_of,
            },
            "blocked_missing_as_of_outputs",
            _research_views_command(config),
            ["generate_as_of_outputs_first"],
            config,
        )

    if not symbols_file.exists():
        return _finish(
            {**base, "future_window": future_window},
            "missing_cache",
            _plan_command(config),
            ["symbols_file_missing"],
            config,
        )

    coverage = _coverage_report(config, symbols_file, future_window)
    coverage_fields = {
        "symbol_count": coverage.get("symbol_count"),
        "covered_count": coverage.get("covered_count"),
        "missing_count": coverage.get("missing_count"),
        "coverage_rate": coverage.get("coverage_rate"),
        "cache_coverage_output": _coverage_output_path(outputs_dir, suffix),
    }
    if float(coverage.get("coverage_rate") or 0.0) < config.min_coverage_rate:
        return _finish(
            {**base, **coverage_fields, "future_window": future_window},
            "missing_cache",
            requirement.get("manual_prewarm_command") or _prewarm_command(config, future_window),
            ["cache_coverage_below_threshold"],
            config,
        )

    output_status = _output_status(outputs_dir, suffix)
    prediction = _prediction_quality(outputs_dir, suffix)
    quality_fields = {
        **coverage_fields,
        **prediction,
        "future_window": future_window,
        "missing_outputs": output_status["missing_outputs"],
        "existing_outputs": output_status["existing_outputs"],
    }

    if output_status["missing_outputs"]:
        return _finish(
            {**base, **quality_fields},
            "missing_experiment_outputs",
            _validation_command(config),
            ["generate_validation_and_experiment_outputs"],
            config,
        )

    valid_count = prediction.get("valid_prediction_count")
    prediction_count = prediction.get("prediction_count")
    valid_ratio = prediction.get("valid_coverage_ratio")
    if valid_count is not None and int(valid_count) < config.min_valid_count:
        return _finish(
            {**base, **quality_fields},
            "low_quality",
            _validation_command(config),
            ["valid_prediction_count_below_threshold"],
            config,
        )
    if (
        valid_ratio is not None
        and float(valid_ratio) < config.min_coverage_rate
        and prediction_count
    ):
        return _finish(
            {**base, **quality_fields},
            "low_quality",
            _validation_command(config),
            ["valid_prediction_ratio_below_threshold"],
            config,
        )

    return _finish(
        {**base, **quality_fields},
        "ready",
        _summary_command(config),
        ["ready_for_manual_review"],
        config,
    )


def write_validation_window_readiness(
    result: dict[str, Any],
    outputs_dir: str | Path,
) -> str:
    path = (
        Path(outputs_dir)
        / "experiments"
        / f"window_readiness_{result['as_of_date']}_{result['horizon_days']}d.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(sanitize_for_json(result), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return str(path)


def _finish(
    result: dict[str, Any],
    status: str,
    next_command: str,
    notes: list[str],
    config: ValidationWindowReadinessConfig,
) -> dict[str, Any]:
    payload = {
        **result,
        "status": status,
        "next_manual_command": next_command,
        "notes": [*result.get("notes", []), *notes],
    }
    if config.write_output:
        payload["output_file"] = write_validation_window_readiness(payload, config.outputs_dir)
    return sanitize_for_json(payload)


def _load_or_build_plan(config: ValidationWindowReadinessConfig) -> dict[str, Any]:
    outputs_dir = Path(config.outputs_dir)
    plan_path = outputs_dir / "experiments" / "multi_asof_validation_plan_2024.json"
    if plan_path.exists():
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        if _find_horizon(plan, config.as_of_date, config.horizon_days):
            return plan
    plan = build_multi_asof_validation_plan(
        MultiAsOfValidationConfig(
            outputs_dir=outputs_dir,
            cache_dir=config.cache_dir,
            provider=config.provider,
            benchmark=config.benchmark,
            as_of_dates=(config.as_of_date,),
            horizons=(config.horizon_days,),
            recommended_limit=config.limit or 0,
        )
    )
    write_multi_asof_outputs(plan, outputs_dir)
    return plan


def _find_horizon(
    plan: dict[str, Any],
    as_of_date: str,
    horizon_days: int,
) -> dict[str, Any] | None:
    for as_of in plan.get("as_of_plan", []):
        if not isinstance(as_of, dict) or as_of.get("as_of_date") != as_of_date:
            continue
        for horizon in as_of.get("horizons", []):
            if isinstance(horizon, dict) and horizon.get("horizon_days") == horizon_days:
                return horizon
    return None


def _find_cache_requirement(
    plan: dict[str, Any],
    as_of_date: str,
    horizon_days: int,
) -> dict[str, Any]:
    requirement_id = f"{as_of_date}_{horizon_days}d"
    for requirement in plan.get("cache_requirements", []):
        if (
            isinstance(requirement, dict)
            and requirement.get("cache_requirement_id") == requirement_id
        ):
            return requirement
    return {}


def _symbols_file_path(outputs_dir: Path, as_of_date: str, horizon_days: int) -> Path:
    return outputs_dir / "cache_plans" / f"multi_asof_symbols_{as_of_date}_{horizon_days}d.txt"


def _coverage_output_path(outputs_dir: Path, suffix: str) -> str:
    return str(outputs_dir / "experiments" / f"cache_coverage_{suffix}.json")


def _coverage_report(
    config: ValidationWindowReadinessConfig,
    symbols_file: Path,
    future_window: dict[str, Any],
) -> dict[str, Any]:
    suffix = f"{config.as_of_date}_{config.horizon_days}d"
    output_path = Path(_coverage_output_path(Path(config.outputs_dir), suffix))
    if output_path.exists():
        report = json.loads(output_path.read_text(encoding="utf-8"))
        if _coverage_matches(report, config, symbols_file, future_window):
            return report
    return check_cache_coverage(
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


def _coverage_matches(
    report: dict[str, Any],
    config: ValidationWindowReadinessConfig,
    symbols_file: Path,
    future_window: dict[str, Any],
) -> bool:
    if report.get("provider_access") is not False:
        return False
    if report.get("date_range") != {
        "start_date": future_window.get("start_date"),
        "end_date": future_window.get("end_date"),
    }:
        return False
    expected_limit = config.limit if config.limit and config.limit > 0 else None
    actual_symbols = [
        line.strip()
        for line in symbols_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if expected_limit:
        actual_symbols = actual_symbols[:expected_limit]
    return int(report.get("symbol_count") or -1) == len(actual_symbols)


def _output_status(outputs_dir: Path, suffix: str) -> dict[str, dict[str, str]]:
    required = {
        "walk_forward_predictions": outputs_dir / "validation" / f"walk_forward_predictions_{suffix}.csv",
        "list_performance": outputs_dir / "validation" / f"list_performance_{suffix}.json",
        "factor_effectiveness": outputs_dir / "validation" / f"factor_effectiveness_{suffix}.json",
        "strategy_family_experiments": outputs_dir / "experiments" / f"strategy_family_experiments_{suffix}.json",
        "aggressive_filter_experiments": outputs_dir / "experiments" / f"aggressive_filter_experiments_{suffix}.json",
    }
    return {
        "existing_outputs": {key: str(path) for key, path in required.items() if path.exists()},
        "missing_outputs": {key: str(path) for key, path in required.items() if not path.exists()},
    }


def _prediction_quality(outputs_dir: Path, suffix: str) -> dict[str, Any]:
    prediction_path = outputs_dir / "validation" / f"walk_forward_predictions_{suffix}.csv"
    if not prediction_path.exists():
        return {
            "prediction_count": None,
            "valid_prediction_count": None,
            "valid_coverage_ratio": None,
        }
    frame = pd.read_csv(prediction_path, dtype={"symbol": str})
    prediction_count = int(len(frame))
    if "data_quality" in frame.columns:
        valid_prediction_count = int((frame["data_quality"] == "ok").sum())
    else:
        valid_prediction_count = prediction_count
    return {
        "prediction_count": prediction_count,
        "valid_prediction_count": valid_prediction_count,
        "valid_coverage_ratio": (
            valid_prediction_count / prediction_count if prediction_count else 0.0
        ),
    }


def _validation_command(config: ValidationWindowReadinessConfig) -> str:
    return (
        "python backend\\scripts\\run_controlled_validation_batch.py "
        f"--as-of-date {config.as_of_date} --horizon-days {config.horizon_days} "
        f"--benchmark {config.benchmark} --outputs-dir {config.outputs_dir} "
        f"--cache-dir {config.cache_dir} --limit {config.limit or 0} --write-output"
    )


def _plan_command(config: ValidationWindowReadinessConfig) -> str:
    return (
        "python backend\\scripts\\generate_multi_asof_validation_plan.py "
        f"--outputs-dir {config.outputs_dir} --cache-dir {config.cache_dir}"
    )


def _research_views_command(config: ValidationWindowReadinessConfig) -> str:
    daily = (
        "python backend\\scripts\\run_daily_research.py "
        f"--provider {config.provider} --end-date {config.as_of_date} "
        f"--cache-dir {config.cache_dir} --output-dir "
        f"{Path(config.outputs_dir) / 'daily'} --limit {config.limit or 0}"
    )
    views = (
        "python backend\\scripts\\generate_research_views.py "
        f"--date {config.as_of_date} --outputs-dir {config.outputs_dir} "
        f"--cache-dir {config.cache_dir}"
    )
    return f"{daily}\n{views}"


def _prewarm_command(
    config: ValidationWindowReadinessConfig,
    future_window: dict[str, Any],
) -> str:
    return (
        "python backend\\scripts\\prewarm_market_cache.py "
        f"--provider {config.provider} --start-date {future_window.get('start_date')} "
        f"--end-date {future_window.get('end_date')} --cache-dir {config.cache_dir} "
        f"--output-dir {Path(config.outputs_dir) / 'cache'} --symbols-file "
        f"{_symbols_file_path(Path(config.outputs_dir), config.as_of_date, config.horizon_days)} "
        "--batch-size 10 --sleep-seconds 0.5 --retry 1 --resume"
    )


def _summary_command(config: ValidationWindowReadinessConfig) -> str:
    return (
        "python backend\\scripts\\summarize_multi_window_experiments.py "
        f"--outputs-dir {config.outputs_dir} --plan-file "
        f"{Path(config.outputs_dir) / 'experiments' / 'multi_asof_validation_plan_2024.json'} "
        f"--min-valid-count {config.min_valid_count} --write-output"
    )
