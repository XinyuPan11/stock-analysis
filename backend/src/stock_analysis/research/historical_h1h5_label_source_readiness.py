"""Read-only readiness for historical H1-H5 explicit label sources."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from stock_analysis.research.historical_h1h5_evaluator import (
    EVIDENCE_LEVEL,
    EXPECTED_BENCHMARK,
    EXPECTED_HORIZON_DAYS,
    EXCLUDED_WINDOWS,
    PRIMARY_WINDOWS,
    VALIDATION_ID,
    HistoricalH1H5EvaluatorError,
    load_explicit_label_source,
    load_frozen_cohort_output,
    validate_explicit_label_source,
)


FROZEN_COHORT_DIGESTS: dict[str, dict[str, str]] = {
    "2026-01-30": {
        "csv": (
            "86C32E2C259E8E40E8CD638DF4BAC8A28E4ADBDA210719171D1CA76E36416198"
        ),
        "json": (
            "0BDBBFC7100D7C6ACD9F5ADC90A687BA8826C1E9700E9F9D0CF7309195CB4439"
        ),
    },
    "2026-03-31": {
        "csv": (
            "20E79A9F469EDE9924A36077E276707BAAA4A7672DA5D629C70356CD1463A890"
        ),
        "json": (
            "097390A75552825DC5F7A0D999672D3AD03B7C5EEA93CB373C775276DC87ABAB"
        ),
    },
    "2026-04-30": {
        "csv": (
            "201273F652BCEAC6E3E5D42B52DFD25EC50EF3B4CAFC960392F86EDAA0B39655"
        ),
        "json": (
            "387E5DF1D74BBBE8DB8078C062863845460E3067225EBC95DFD10BA9A090A5F7"
        ),
    },
}


class HistoricalH1H5LabelReadinessError(ValueError):
    def __init__(
        self,
        status: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.details = dict(details or {})


def check_historical_h1h5_label_source_readiness(
    repo_root: str | Path,
    *,
    cache_dir: str | Path | None = None,
    outputs_dir: str | Path | None = None,
    label_sources: Mapping[str, str | Path] | None = None,
    expected_digests: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """Check all primary windows without reading price or outcome values."""

    root = Path(repo_root).resolve()
    cache = (
        Path(cache_dir).resolve()
        if cache_dir is not None
        else root / "data" / "cache" / "daily-use"
    )
    outputs = (
        Path(outputs_dir).resolve()
        if outputs_dir is not None
        else root / "outputs"
    )
    sources = {
        str(date): Path(path)
        for date, path in dict(label_sources or {}).items()
    }
    unknown_dates = sorted(set(sources) - set(PRIMARY_WINDOWS))
    if unknown_dates:
        status = (
            "blocked_excluded_window"
            if any(date in EXCLUDED_WINDOWS for date in unknown_dates)
            else "blocked_non_primary_window"
        )
        return _blocked_report(
            root=root,
            cache=cache,
            outputs=outputs,
            status=status,
            message="Label-source mapping contains a non-primary date.",
            details={"dates": unknown_dates},
        )

    digests = expected_digests or FROZEN_COHORT_DIGESTS
    windows = [
        check_historical_h1h5_label_source_window(
            repo_root=root,
            cache_dir=cache,
            outputs_dir=outputs,
            as_of_date=as_of_date,
            label_source_path=sources.get(as_of_date),
            expected_digests=digests[as_of_date],
        )
        for as_of_date in PRIMARY_WINDOWS
    ]
    blocked = [window for window in windows if window["status"].startswith(
        "blocked_"
    )]
    if blocked:
        status = "blocked"
        ready = False
    elif all(
        window["status"] == "ready_for_evaluator_dry_run"
        for window in windows
    ):
        status = "ready_for_evaluator_dry_run"
        ready = True
    else:
        status = "ready_to_build_label_sources"
        ready = True
    return {
        "status": status,
        "ready": ready,
        "research_only": True,
        "readiness_only": True,
        "provider_access": False,
        "provider_fallback_available": False,
        "cache_prewarm_executed": False,
        "labels_generated": all(
            window.get("labels_generated") is True for window in windows
        ),
        "labels_joined": False,
        "evaluator_run": False,
        "final_validation_outputs_written": False,
        "validation_outputs_read": False,
        "production_change": False,
        "validation_id": VALIDATION_ID,
        "evidence_level": EVIDENCE_LEVEL,
        "horizon_days": EXPECTED_HORIZON_DAYS,
        "benchmark": EXPECTED_BENCHMARK,
        "repo_root": str(root),
        "cache_dir": str(cache),
        "outputs_dir": str(outputs),
        "primary_window_count": len(PRIMARY_WINDOWS),
        "ready_to_build_count": sum(
            window["status"] == "ready_to_build_label_sources"
            for window in windows
        ),
        "ready_for_evaluator_count": sum(
            window["status"] == "ready_for_evaluator_dry_run"
            for window in windows
        ),
        "blocked_window_count": len(blocked),
        "windows": windows,
    }


def check_historical_h1h5_label_source_window(
    *,
    repo_root: str | Path,
    cache_dir: str | Path,
    outputs_dir: str | Path,
    as_of_date: str,
    label_source_path: str | Path | None,
    expected_digests: Mapping[str, str],
) -> dict[str, Any]:
    """Check one primary window using file names, digests, and trade dates."""

    _validate_primary_date(as_of_date)
    root = Path(repo_root)
    cache = Path(cache_dir)
    outputs = Path(outputs_dir)
    cohort_json = (
        outputs / "research" / f"opportunity_cohorts_{as_of_date}.json"
    )
    cohort_csv = cohort_json.with_suffix(".csv")
    base = {
        "as_of_date": as_of_date,
        "window_kind": "primary",
        "research_only": True,
        "readiness_only": True,
        "provider_access": False,
        "labels_generated": False,
        "labels_joined": False,
        "evaluator_run": False,
        "final_validation_outputs_written": False,
        "production_change": False,
        "frozen_cohort_json_path": str(cohort_json),
        "frozen_cohort_csv_path": str(cohort_csv),
        "expected_json_sha256": str(expected_digests.get("json", "")).upper(),
        "expected_csv_sha256": str(expected_digests.get("csv", "")).upper(),
        "label_source_path": None,
        "label_source_explicitly_provided": label_source_path is not None,
    }
    missing_cohorts = [
        str(path) for path in (cohort_json, cohort_csv) if not path.exists()
    ]
    if missing_cohorts:
        return _window_blocked(
            base,
            "blocked_missing_frozen_cohort",
            "Frozen Phase 3.9 cohort output is missing.",
            details={"missing_paths": missing_cohorts},
        )
    actual_json_digest = _sha256(cohort_json)
    actual_csv_digest = _sha256(cohort_csv)
    base.update(
        {
            "actual_json_sha256": actual_json_digest,
            "actual_csv_sha256": actual_csv_digest,
            "frozen_cohort_mutated": False,
        }
    )
    if (
        actual_json_digest != base["expected_json_sha256"]
        or actual_csv_digest != base["expected_csv_sha256"]
    ):
        base["frozen_cohort_mutated"] = True
        return _window_blocked(
            base,
            "blocked_frozen_digest_mismatch",
            "Frozen Phase 3.9 cohort digest does not match.",
        )
    try:
        frozen = load_frozen_cohort_output(
            cohort_json,
            as_of_date=as_of_date,
            expected_sha256=base["expected_json_sha256"],
        )
    except HistoricalH1H5EvaluatorError as exc:
        return _window_blocked(
            base,
            exc.status,
            exc.message,
            details=exc.details,
        )
    symbols = sorted(
        {
            str(record.get("symbol", "")).strip()
            for record in frozen.payload["records"]
            if str(record.get("symbol", "")).strip()
        }
    )
    base["cohort_symbol_count"] = len(symbols)

    conflicting_outputs = _existing_validation_outputs(
        outputs,
        as_of_date=as_of_date,
    )
    base["existing_validation_outputs"] = conflicting_outputs
    if conflicting_outputs:
        return _window_blocked(
            base,
            "blocked_existing_validation_output",
            "Existing validation output conflicts with sealed readiness.",
            details={"paths": conflicting_outputs},
        )

    benchmark = _benchmark_coverage(
        cache,
        as_of_date=as_of_date,
    )
    base["benchmark_cache"] = benchmark
    if benchmark["status"] != "covered":
        return _window_blocked(
            base,
            "blocked_missing_local_future_cache",
            "CSI300 cache does not cover 20 future trading days.",
            details={"benchmark_cache": benchmark},
        )
    required_future_end = str(benchmark["required_future_end"])
    base["required_future_end"] = required_future_end

    stock_coverage = _stock_cache_coverage(
        cache,
        symbols=symbols,
        as_of_date=as_of_date,
        required_future_end=required_future_end,
    )
    base["stock_cache"] = stock_coverage
    if stock_coverage["temporally_covered_symbol_count"] != len(symbols):
        return _window_blocked(
            base,
            "blocked_missing_local_future_cache",
            "Local stock cache does not cover the required future end.",
            details={"stock_cache": stock_coverage},
        )

    default_label_path = (
        outputs
        / "experiments"
        / f"historical_h1h5_label_source_{as_of_date}_20d.json"
    )
    label_path = (
        Path(label_source_path)
        if label_source_path is not None
        else default_label_path
    )
    base["label_source_path"] = str(label_path)
    base["label_source_exists"] = label_path.exists()
    if label_path.exists():
        base["labels_generated"] = True
    if label_source_path is not None and not label_path.exists():
        return _window_blocked(
            base,
            "blocked_missing_label_source",
            "Explicitly supplied label source does not exist.",
        )
    if not label_path.exists():
        return {
            **base,
            "status": "ready_to_build_label_sources",
            "ready": True,
            "message": (
                "Frozen cohorts and local cache are ready, but the explicit "
                "label source has not been built."
            ),
            "label_source_schema_status": "missing",
            "no_provider_access_needed": True,
        }

    try:
        label_payload = load_explicit_label_source(label_path)
        label_status = validate_explicit_label_source(
            label_payload,
            as_of_date=as_of_date,
            horizon_days=EXPECTED_HORIZON_DAYS,
            benchmark=EXPECTED_BENCHMARK,
        )
    except HistoricalH1H5EvaluatorError as exc:
        return _window_blocked(
            base,
            exc.status,
            exc.message,
            details=exc.details,
        )
    metadata = label_payload.get("metadata", {})
    if metadata.get("required_future_end") != required_future_end:
        return _window_blocked(
            base,
            "blocked_label_source_metadata_mismatch",
            "Label source required_future_end does not match local coverage.",
        )
    if not isinstance(metadata.get("cache_coverage"), Mapping):
        return _window_blocked(
            base,
            "blocked_label_source_metadata_mismatch",
            "Label source must record cache_coverage metadata.",
        )
    label_symbols = {
        str(record.get("symbol", "")).strip()
        for record in label_payload.get("records", [])
        if isinstance(record, Mapping)
        and str(record.get("symbol", "")).strip()
    }
    extra_symbols = sorted(label_symbols - set(symbols))
    if extra_symbols:
        return _window_blocked(
            base,
            "blocked_label_universe_mismatch",
            "Label source contains symbols outside the frozen universe.",
            details={"extra_symbols": extra_symbols[:50]},
        )
    missing_symbols = sorted(set(symbols) - label_symbols)
    if missing_symbols:
        return _window_blocked(
            base,
            "blocked_label_universe_mismatch",
            "Label source must preserve every frozen-universe symbol.",
            details={"missing_symbols": missing_symbols[:50]},
        )
    return {
        **base,
        "status": "ready_for_evaluator_dry_run",
        "ready": True,
        "message": "Explicit label source and frozen cohort are ready.",
        "label_source_schema_status": "safe",
        "label_source": label_status,
        "label_source_missing_frozen_symbols": 0,
        "no_provider_access_needed": True,
    }


def _benchmark_coverage(
    cache_dir: Path,
    *,
    as_of_date: str,
) -> dict[str, Any]:
    candidates = (
        cache_dir
        / "baostock"
        / "stock_daily"
        / "adjusted"
        / "sh.000300.csv",
        cache_dir
        / "baostock"
        / "stock_daily"
        / "adjusted"
        / "sz.399300.csv",
        cache_dir
        / "baostock"
        / "index_daily"
        / "raw"
        / "CSI300.csv",
    )
    all_dates: set[pd.Timestamp] = set()
    used_paths: list[str] = []
    for path in candidates:
        dates = _read_trade_dates(path)
        if dates:
            all_dates.update(dates)
            used_paths.append(str(path))
    cutoff = pd.Timestamp(as_of_date)
    future_dates = sorted(date for date in all_dates if date > cutoff)
    required_end = (
        future_dates[EXPECTED_HORIZON_DAYS - 1]
        if len(future_dates) >= EXPECTED_HORIZON_DAYS
        else None
    )
    return {
        "status": "covered" if required_end is not None else "missing",
        "source_paths": used_paths,
        "future_trade_date_count": len(future_dates),
        "required_future_end": (
            required_end.strftime("%Y-%m-%d")
            if required_end is not None
            else None
        ),
        "latest_trade_date": (
            max(all_dates).strftime("%Y-%m-%d") if all_dates else None
        ),
    }


def _stock_cache_coverage(
    cache_dir: Path,
    *,
    symbols: list[str],
    as_of_date: str,
    required_future_end: str,
) -> dict[str, Any]:
    adjusted = cache_dir / "baostock" / "stock_daily" / "adjusted"
    cutoff = pd.Timestamp(as_of_date)
    required_end = pd.Timestamp(required_future_end)
    missing_files: list[str] = []
    short_coverage: list[str] = []
    missing_entry: list[str] = []
    complete_20_rows = 0
    for symbol in symbols:
        path = adjusted / f"{symbol}.csv"
        dates = _read_trade_dates(path)
        if not dates:
            missing_files.append(symbol)
            continue
        date_set = set(dates)
        if cutoff not in date_set:
            missing_entry.append(symbol)
        if max(dates) < required_end:
            short_coverage.append(symbol)
        future_to_end = [
            date for date in dates if cutoff < date <= required_end
        ]
        if len(future_to_end) >= EXPECTED_HORIZON_DAYS:
            complete_20_rows += 1
    temporally_covered = (
        len(symbols)
        - len(set(missing_files) | set(short_coverage) | set(missing_entry))
    )
    return {
        "symbol_count": len(symbols),
        "cache_file_count": len(symbols) - len(missing_files),
        "temporally_covered_symbol_count": temporally_covered,
        "symbols_with_20_rows_to_required_end": complete_20_rows,
        "missing_cache_count": len(missing_files),
        "short_coverage_count": len(short_coverage),
        "missing_entry_date_count": len(missing_entry),
        "missing_cache_symbols": missing_files[:50],
        "short_coverage_symbols": short_coverage[:50],
        "missing_entry_date_symbols": missing_entry[:50],
    }


def _existing_validation_outputs(
    outputs_dir: Path,
    *,
    as_of_date: str,
) -> list[str]:
    candidates = (
        outputs_dir
        / "validation"
        / f"historical_h1h5_evaluation_{as_of_date}_20d.csv",
        outputs_dir
        / "validation"
        / f"historical_h1h5_evaluation_{as_of_date}_20d.json",
        outputs_dir
        / "validation"
        / f"walk_forward_predictions_{as_of_date}_20d.csv",
        outputs_dir
        / "validation"
        / "historical_h1h5_summary_"
        "h1h5-historical-sealed-v1.json",
    )
    return [str(path) for path in candidates if path.exists()]


def _read_trade_dates(path: Path) -> list[pd.Timestamp]:
    if not path.exists():
        return []
    try:
        frame = pd.read_csv(path, usecols=["trade_date"], dtype=str)
    except (OSError, ValueError, pd.errors.ParserError, UnicodeError):
        return []
    dates = pd.to_datetime(frame["trade_date"], errors="coerce").dropna()
    return sorted(set(pd.Timestamp(date).normalize() for date in dates))


def _validate_primary_date(as_of_date: str) -> None:
    if as_of_date in EXCLUDED_WINDOWS:
        raise HistoricalH1H5LabelReadinessError(
            "blocked_excluded_window",
            "Date is consumed evidence or reserved for prospective U3.",
        )
    if as_of_date not in PRIMARY_WINDOWS:
        raise HistoricalH1H5LabelReadinessError(
            "blocked_non_primary_window",
            "Label-source readiness accepts historical primary dates only.",
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _window_blocked(
    base: Mapping[str, Any],
    status: str,
    message: str,
    *,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        **base,
        "status": status,
        "ready": False,
        "message": message,
        "details": dict(details or {}),
        "no_provider_access_needed": True,
    }


def _blocked_report(
    *,
    root: Path,
    cache: Path,
    outputs: Path,
    status: str,
    message: str,
    details: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "status": status,
        "ready": False,
        "research_only": True,
        "readiness_only": True,
        "provider_access": False,
        "labels_generated": False,
        "labels_joined": False,
        "evaluator_run": False,
        "final_validation_outputs_written": False,
        "production_change": False,
        "validation_id": VALIDATION_ID,
        "evidence_level": EVIDENCE_LEVEL,
        "repo_root": str(root),
        "cache_dir": str(cache),
        "outputs_dir": str(outputs),
        "message": message,
        "details": dict(details),
        "windows": [],
    }
