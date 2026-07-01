"""Read-only local inventory for historical sealed H1-H5 source snapshots."""

from __future__ import annotations

import csv
from datetime import date, timedelta
import json
from pathlib import Path
from typing import Any, Iterable

from stock_analysis.research.feature_only_snapshot import (
    REQUIRED_COLUMNS,
    VOLATILITY_COLUMNS,
    find_outcome_columns,
)
from stock_analysis.research.historical_h1h5_readiness import (
    HISTORICAL_BACKUP_WINDOWS,
    HISTORICAL_EXCLUDED_WINDOWS,
    HISTORICAL_PRIMARY_WINDOWS,
    HISTORICAL_VALIDATION_ID,
    HISTORICAL_WINDOWS,
    MINIMUM_VALID_UNIVERSE_ROWS,
)


HISTORICAL_EVIDENCE_LEVEL = "historical_sealed_not_prospective"
BENCHMARK = "CSI300"
PROVIDER = "baostock"
LOOKBACK_CALENDAR_DAYS = 365
BENCHMARK_CACHE_CANDIDATES: tuple[tuple[str, str, str], ...] = (
    ("index_daily", "raw", "CSI300"),
    ("stock_daily", "adjusted", "sh.000300"),
    ("stock_daily", "adjusted", "sz.399300"),
    ("stock_daily", "adjusted", "000300"),
)


def inventory_historical_source_snapshots(
    repo_root: str | Path,
    *,
    cache_dir: str | Path | None = None,
    outputs_dir: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    cache_root = _resolve_path(
        root,
        cache_dir,
        root / "data" / "cache" / "daily-use",
    )
    outputs_root = _resolve_path(root, outputs_dir, root / "outputs")
    provider_root = cache_root / PROVIDER
    universe_path = provider_root / "stock_universe.csv"
    stock_cache_dir = provider_root / "stock_daily" / "adjusted"

    universe_symbols = _read_universe_symbols(universe_path)
    stock_coverage = _load_stock_coverage(
        stock_cache_dir,
        universe_symbols,
    )
    benchmark_coverage = _load_benchmark_coverage(provider_root)
    benchmark_trade_dates = _read_benchmark_trade_dates(
        benchmark_coverage
    )

    windows = [
        _inventory_window(
            as_of_date=as_of_date,
            outputs_root=outputs_root,
            stock_coverage=stock_coverage,
            benchmark_coverage=benchmark_coverage,
            benchmark_trade_dates=benchmark_trade_dates,
        )
        for as_of_date in HISTORICAL_WINDOWS
    ]
    primary = [
        item
        for item in windows
        if item["as_of_date"] in HISTORICAL_PRIMARY_WINDOWS
    ]
    source_ready = all(
        item["source_snapshot_exists"]
        and item["source_snapshot_format_status"] == "safe_header"
        and item["source_snapshot_row_count"]
        >= MINIMUM_VALID_UNIVERSE_ROWS
        for item in primary
    )
    return {
        "status": "source_snapshots_ready" if source_ready else "blocked",
        "inventory_complete": True,
        "research_only": True,
        "inventory_only": True,
        "provider_access": False,
        "cache_prewarm_executed": False,
        "validation_run": False,
        "validation_outputs_read": False,
        "evaluator_called": False,
        "outcome_values_read": False,
        "future_labels_generated": False,
        "future_returns_computed": False,
        "h1h5_cohort_outputs_generated": False,
        "production_change": False,
        "validation_id": HISTORICAL_VALIDATION_ID,
        "evidence_level": HISTORICAL_EVIDENCE_LEVEL,
        "benchmark": BENCHMARK,
        "horizon_trading_days": 20,
        "repo_root": str(root),
        "cache_dir": str(cache_root),
        "outputs_dir": str(outputs_root),
        "source_snapshot_path_pattern": str(
            outputs_root
            / "experiments"
            / "historical_h1h5_source_snapshot_<date>.csv"
        ),
        "source_snapshot_format": {
            "required_columns": list(REQUIRED_COLUMNS),
            "required_one_of_volatility_columns": list(
                VOLATILITY_COLUMNS
            ),
            "required_point_in_time_metadata": [
                "as_of_date",
                "leakage_guard_applied",
            ],
            "conditional_point_in_time_metadata": [
                "latest_input_date",
            ],
            "allowed_physical_cache_diagnostic": "max_raw_cache_date",
            "allowed_excluded_row_diagnostic": (
                "future_rows_excluded_count"
            ),
            "minimum_valid_universe_rows": MINIMUM_VALID_UNIVERSE_ROWS,
            "latest_input_date_rule": (
                "latest_input_date must be on or before as_of_date"
            ),
            "forbidden_column_categories": [
                "future or forward fields",
                "realized fields",
                "target or outcome fields",
                "label fields",
                "winner or loser fields",
                "benchmark outcome fields",
                "holding-period fields",
            ],
        },
        "local_cache": {
            "provider": PROVIDER,
            "universe_path": str(universe_path),
            "universe_exists": universe_path.exists(),
            "universe_symbol_count": len(universe_symbols),
            "stock_coverage_metadata_count": len(stock_coverage),
            "benchmark_candidates": benchmark_coverage,
            "benchmark_trade_date_count": len(benchmark_trade_dates),
            "benchmark_latest_trade_date": (
                benchmark_trade_dates[-1]
                if benchmark_trade_dates
                else None
            ),
        },
        "legacy_member_snapshot_builder": {
            "script": (
                "backend/scripts/build_member_level_asof_snapshot.py"
            ),
            "safe_for_historical_sealed_source": False,
            "reason": (
                "The current builder requires validation prediction files "
                "as its member universe and attaches future label fields."
            ),
            "must_not_run_for_phase3_7_1": True,
        },
        "eligible_windows": list(HISTORICAL_WINDOWS),
        "excluded_or_reserved_windows": sorted(
            HISTORICAL_EXCLUDED_WINDOWS
        ),
        "windows": windows,
    }


def classify_inventory_window(as_of_date: str) -> dict[str, Any]:
    if as_of_date in HISTORICAL_WINDOWS:
        return {
            "as_of_date": as_of_date,
            "eligible": True,
            "window_kind": (
                "primary"
                if as_of_date in HISTORICAL_PRIMARY_WINDOWS
                else "backup"
            ),
            "status": "eligible_historical_sealed_window",
        }
    if as_of_date in HISTORICAL_EXCLUDED_WINDOWS:
        return {
            "as_of_date": as_of_date,
            "eligible": False,
            "window_kind": None,
            "status": "excluded_consumed_or_u3_window",
        }
    return {
        "as_of_date": as_of_date,
        "eligible": False,
        "window_kind": None,
        "status": "unknown_window",
    }


def _inventory_window(
    *,
    as_of_date: str,
    outputs_root: Path,
    stock_coverage: dict[str, tuple[str, str]],
    benchmark_coverage: list[dict[str, Any]],
    benchmark_trade_dates: list[str],
) -> dict[str, Any]:
    cutoff = date.fromisoformat(as_of_date)
    lookback_start = (
        cutoff - timedelta(days=LOOKBACK_CALENDAR_DAYS)
    ).isoformat()
    future_dates = [
        item for item in benchmark_trade_dates if item > as_of_date
    ]
    future_20d_target = (
        future_dates[19] if len(future_dates) >= 20 else None
    )
    stock_asof_count = _coverage_count(
        stock_coverage.values(),
        start_date=lookback_start,
        end_date=as_of_date,
    )
    benchmark_asof = _covering_benchmark_candidates(
        benchmark_coverage,
        start_date=lookback_start,
        end_date=as_of_date,
    )
    stock_future_count = (
        _coverage_count(
            stock_coverage.values(),
            start_date=lookback_start,
            end_date=future_20d_target,
        )
        if future_20d_target is not None
        else 0
    )
    benchmark_future = (
        _covering_benchmark_candidates(
            benchmark_coverage,
            start_date=lookback_start,
            end_date=future_20d_target,
        )
        if future_20d_target is not None
        else []
    )
    stock_asof_ok = stock_asof_count >= MINIMUM_VALID_UNIVERSE_ROWS
    benchmark_asof_ok = bool(benchmark_asof)
    stock_future_ok = (
        future_20d_target is not None
        and stock_future_count >= MINIMUM_VALID_UNIVERSE_ROWS
    )
    benchmark_future_ok = bool(benchmark_future)

    source_path = (
        outputs_root
        / "experiments"
        / f"historical_h1h5_source_snapshot_{as_of_date}.csv"
    )
    source_inspection = _inspect_source_snapshot_header(
        source_path,
        expected_as_of_date=as_of_date,
    )
    factors_path = outputs_root / "daily" / f"factors_{as_of_date}.csv"
    candidates_path = (
        outputs_root / "daily" / f"candidates_{as_of_date}.csv"
    )
    predictions_path = (
        outputs_root
        / "validation"
        / f"walk_forward_predictions_{as_of_date}_20d.csv"
    )
    list_files = list(
        (outputs_root / "lists").glob(f"*_{as_of_date}.json")
    )

    if source_inspection["exists"]:
        blocker = (
            None
            if source_inspection["format_status"] == "safe_header"
            and source_inspection["row_count"]
            >= MINIMUM_VALID_UNIVERSE_ROWS
            else "blocked_unsafe_or_underpowered_source_snapshot"
        )
    elif not stock_asof_ok or not benchmark_asof_ok:
        blocker = "blocked_missing_local_asof_cache"
    else:
        blocker = "blocked_safe_source_snapshot_builder_required"

    return {
        **classify_inventory_window(as_of_date),
        "lookback_start": lookback_start,
        "source_snapshot_path": str(source_path),
        "source_snapshot_exists": source_inspection["exists"],
        "source_snapshot_format_status": source_inspection[
            "format_status"
        ],
        "source_snapshot_row_count": source_inspection["row_count"],
        "source_snapshot_missing_columns": source_inspection[
            "missing_columns"
        ],
        "source_snapshot_forbidden_columns": source_inspection[
            "forbidden_columns"
        ],
        "stock_cache_coverage_count": stock_asof_count,
        "minimum_stock_cache_count": MINIMUM_VALID_UNIVERSE_ROWS,
        "stock_cache_appears_present": stock_asof_ok,
        "benchmark_cache_appears_present": benchmark_asof_ok,
        "benchmark_cache_sources": [
            item["path"] for item in benchmark_asof
        ],
        "future_trade_dates_available": len(future_dates),
        "future_20d_target_date": future_20d_target,
        "stock_future_20d_coverage_count": stock_future_count,
        "stock_future_20d_cache_appears_present": stock_future_ok,
        "benchmark_future_20d_cache_appears_present": benchmark_future_ok,
        "future_20d_local_cache_appears_present": (
            stock_future_ok and benchmark_future_ok
        ),
        "provider_fetch_needed_for_source": (
            not stock_asof_ok or not benchmark_asof_ok
        ),
        "provider_fetch_needed_for_future_20d": not (
            stock_future_ok and benchmark_future_ok
        ),
        "cache_only_factors_path": str(factors_path),
        "cache_only_factors_exist": factors_path.exists(),
        "cache_only_candidates_path": str(candidates_path),
        "cache_only_candidates_exist": candidates_path.exists(),
        "existing_list_file_count": len(list_files),
        "legacy_validation_predictions_path": str(predictions_path),
        "legacy_validation_predictions_exist": predictions_path.exists(),
        "phase3_7_readiness_status": (
            "blocked_missing_source_snapshot"
            if not source_inspection["exists"]
            else "source_snapshot_present_requires_readiness"
        ),
        "inventory_blocker": blocker,
    }


def _inspect_source_snapshot_header(
    path: Path,
    *,
    expected_as_of_date: str,
) -> dict[str, Any]:
    if not path.exists():
        return {
            "exists": False,
            "format_status": "missing",
            "row_count": 0,
            "missing_columns": [],
            "forbidden_columns": [],
        }
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = list(reader.fieldnames or [])
            forbidden = find_outcome_columns(columns)
            missing = sorted(set(REQUIRED_COLUMNS) - set(columns))
            if not any(item in columns for item in VOLATILITY_COLUMNS):
                missing.append(
                    "technical_volatility_20d|volatility_20d"
                )
            row_count = 0
            date_mismatch = False
            latest_input_violation = False
            for row in reader:
                row_count += 1
                if str(row.get("as_of_date", "")).strip() != (
                    expected_as_of_date
                ):
                    date_mismatch = True
                latest_input = str(
                    row.get("latest_input_date", "")
                ).strip()
                if latest_input and latest_input > expected_as_of_date:
                    latest_input_violation = True
    except (OSError, csv.Error, UnicodeError):
        return {
            "exists": True,
            "format_status": "unreadable_header",
            "row_count": 0,
            "missing_columns": [],
            "forbidden_columns": [],
        }
    safe = (
        not forbidden
        and not missing
        and not date_mismatch
        and not latest_input_violation
    )
    return {
        "exists": True,
        "format_status": "safe_header" if safe else "unsafe_header",
        "row_count": row_count,
        "missing_columns": missing,
        "forbidden_columns": forbidden,
    }


def _read_universe_symbols(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or "symbol" not in reader.fieldnames:
                return []
            return _dedupe(
                str(row.get("symbol", "")).strip()
                for row in reader
            )
    except (OSError, csv.Error, UnicodeError):
        return []


def _load_stock_coverage(
    stock_cache_dir: Path,
    universe_symbols: list[str],
) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    for symbol in universe_symbols:
        interval = _read_coverage(
            stock_cache_dir / f"{symbol}.coverage.json"
        )
        if interval is not None:
            result[symbol] = interval
    return result


def _load_benchmark_coverage(
    provider_root: Path,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for dataset, variant, symbol in BENCHMARK_CACHE_CANDIDATES:
        directory = provider_root / dataset / variant
        coverage_path = directory / f"{symbol}.coverage.json"
        interval = _read_coverage(coverage_path)
        if interval is None:
            continue
        result.append(
            {
                "dataset": dataset,
                "variant": variant,
                "symbol": symbol,
                "covered_start": interval[0],
                "covered_end": interval[1],
                "path": str(directory / f"{symbol}.csv"),
                "coverage_path": str(coverage_path),
            }
        )
    return result


def _read_benchmark_trade_dates(
    benchmark_coverage: list[dict[str, Any]],
) -> list[str]:
    dates: set[str] = set()
    for item in benchmark_coverage:
        path = Path(str(item["path"]))
        if not path.exists():
            continue
        try:
            with path.open(
                "r",
                encoding="utf-8-sig",
                newline="",
            ) as handle:
                reader = csv.DictReader(handle)
                if (
                    not reader.fieldnames
                    or "trade_date" not in reader.fieldnames
                ):
                    continue
                for row in reader:
                    value = str(row.get("trade_date", "")).strip()
                    if _is_iso_date(value):
                        dates.add(value)
        except (OSError, csv.Error, UnicodeError):
            continue
    return sorted(dates)


def _read_coverage(path: Path) -> tuple[str, str] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    start = str(payload.get("covered_start", "")).strip()
    end = str(payload.get("covered_end", "")).strip()
    if not _is_iso_date(start) or not _is_iso_date(end) or start > end:
        return None
    return start, end


def _coverage_count(
    intervals: Iterable[tuple[str, str]],
    *,
    start_date: str,
    end_date: str | None,
) -> int:
    if end_date is None:
        return 0
    return sum(
        start <= start_date and end >= end_date
        for start, end in intervals
    )


def _covering_benchmark_candidates(
    candidates: list[dict[str, Any]],
    *,
    start_date: str,
    end_date: str | None,
) -> list[dict[str, Any]]:
    if end_date is None:
        return []
    return [
        item
        for item in candidates
        if str(item["covered_start"]) <= start_date
        and str(item["covered_end"]) >= end_date
    ]


def _resolve_path(
    root: Path,
    value: str | Path | None,
    default: Path,
) -> Path:
    if value is None:
        return default.resolve()
    path = Path(value)
    return (path if path.is_absolute() else root / path).resolve()


def _dedupe(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _is_iso_date(value: str) -> bool:
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False
