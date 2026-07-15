"""Local-cache-only builder for Phase 3.13 historical H1-H5 labels.

The builder reads the frozen Phase 3.9 universe and adjusted daily cache. It
does not call a provider, read validation predictions, join cohort membership,
or write final evaluation outputs.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from stock_analysis.research.historical_h1h5_label_definitions import (
    BENCHMARK,
    EVIDENCE_LEVEL,
    HORIZON_DAYS,
    REQUIRED_LABEL_SOURCE_COLUMNS,
    VALIDATION_ID,
    HistoricalH1H5LabelDefinitionError,
    load_historical_h1h5_label_definitions,
    validate_execution_date,
    validate_label_source_schema,
)
from stock_analysis.research.historical_h1h5_label_source_readiness import (
    FROZEN_COHORT_DIGESTS,
)


FROZEN_LABEL_DEFINITION_SHA256 = (
    "98282FC01C3F2CE73C97A3A5F66CE62B8C927D27631852B15108A83499245BAF"
)


class HistoricalH1H5LabelSourceError(ValueError):
    """Fail-closed label-source build error."""

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


@dataclass(frozen=True)
class HistoricalH1H5LabelSourceResult:
    frame: pd.DataFrame
    payload: dict[str, Any]
    metadata: dict[str, Any]


def build_historical_h1h5_label_source(
    *,
    as_of_date: str,
    horizon_days: int,
    benchmark: str,
    label_definition_config: str | Path,
    cache_dir: str | Path,
    outputs_dir: str | Path,
    cohort_output: str | Path | None = None,
    expected_cohort_sha256: str | None = None,
) -> HistoricalH1H5LabelSourceResult:
    """Build one label source in memory from explicit local files only."""

    _validate_identity(
        as_of_date=as_of_date,
        horizon_days=horizon_days,
        benchmark=benchmark,
    )
    config_path = Path(label_definition_config)
    actual_definition_sha = _normalized_text_sha256(config_path)
    if actual_definition_sha != FROZEN_LABEL_DEFINITION_SHA256:
        _fail(
            "blocked_label_definition_digest_mismatch",
            "Label definition config SHA-256 differs from Phase 3.12.",
            expected_sha256=FROZEN_LABEL_DEFINITION_SHA256,
            actual_sha256=actual_definition_sha,
        )
    try:
        definitions = load_historical_h1h5_label_definitions(config_path)
    except HistoricalH1H5LabelDefinitionError as exc:
        _fail(exc.status, exc.message, **exc.details)

    outputs = Path(outputs_dir)
    _reject_existing_final_outputs(outputs, as_of_date=as_of_date)
    cohort_path = (
        Path(cohort_output)
        if cohort_output is not None
        else outputs / "research" / f"opportunity_cohorts_{as_of_date}.json"
    )
    expected_digest = (
        str(expected_cohort_sha256).upper()
        if expected_cohort_sha256 is not None
        else FROZEN_COHORT_DIGESTS[as_of_date]["json"]
    )
    symbols, cohort_digest = _load_frozen_universe(
        cohort_path,
        as_of_date=as_of_date,
        expected_sha256=expected_digest,
    )

    cache = Path(cache_dir)
    benchmark_path = (
        cache
        / "baostock"
        / "stock_daily"
        / "adjusted"
        / "sh.000300.csv"
    )
    benchmark_prices = _read_required_adj_close(
        benchmark_path,
        status="blocked_missing_benchmark_cache",
        fatal=True,
    )
    calendar_dates, benchmark_values = _benchmark_window(
        benchmark_prices,
        as_of_date=as_of_date,
        horizon_days=horizon_days,
    )
    benchmark_return = (
        benchmark_values[-1] / benchmark_values[0]
    ) - 1.0

    adjusted_dir = cache / "baostock" / "stock_daily" / "adjusted"
    rows = [
        _build_symbol_row(
            symbol,
            adjusted_dir=adjusted_dir,
            as_of_date=as_of_date,
            future_dates=calendar_dates,
            benchmark_return=benchmark_return,
        )
        for symbol in symbols
    ]
    frame = pd.DataFrame(rows, columns=REQUIRED_LABEL_SOURCE_COLUMNS)
    _assign_boolean_labels(frame, definitions["boolean_labels"])
    _validate_built_frame(frame, as_of_date=as_of_date)

    valid_count = int(frame["valid_label"].sum())
    reason_counts = {
        str(key): int(value)
        for key, value in frame.loc[
            ~frame["valid_label"], "missing_label_reason"
        ].value_counts().sort_index().items()
    }
    metadata = {
        "status": "label_source_built_in_memory",
        "validation_id": VALIDATION_ID,
        "evidence_level": EVIDENCE_LEVEL,
        "as_of_date": as_of_date,
        "horizon_days": horizon_days,
        "benchmark": benchmark,
        "label_definition_sha256": actual_definition_sha,
        "label_definition_config": str(config_path),
        "label_window_complete": True,
        "required_future_start": calendar_dates[0],
        "required_future_end": calendar_dates[-1],
        "price_field": "adj_close",
        "row_count": int(len(frame)),
        "valid_label_count": valid_count,
        "missing_label_count": int(len(frame) - valid_count),
        "missing_label_reason_counts": reason_counts,
        "cache_coverage": {
            "cache_dir": str(cache),
            "benchmark_cache": str(benchmark_path),
            "frozen_universe_symbol_count": len(symbols),
            "complete_symbol_count": valid_count,
            "incomplete_symbol_count": len(symbols) - valid_count,
        },
        "frozen_cohort_path": str(cohort_path),
        "frozen_cohort_sha256": cohort_digest,
        "research_only": True,
        "local_cache_only": True,
        "provider_access": False,
        "validation_prediction_inputs": False,
        "labels_generated": True,
        "labels_joined": False,
        "labels_joined_by_builder": False,
        "cohort_membership_mutated": False,
        "evaluator_run": False,
        "final_validation_outputs_written": False,
        "production_change": False,
    }
    payload = {
        "metadata": metadata,
        "records": _json_safe(frame.to_dict(orient="records")),
    }
    return HistoricalH1H5LabelSourceResult(
        frame=frame,
        payload=payload,
        metadata=metadata,
    )


def write_historical_h1h5_label_source_outputs(
    result: HistoricalH1H5LabelSourceResult,
    *,
    outputs_dir: str | Path,
) -> dict[str, str]:
    """Write only the explicit label-source CSV/JSON pair."""

    as_of_date = str(result.metadata["as_of_date"])
    horizon_days = int(result.metadata["horizon_days"])
    experiments = Path(outputs_dir) / "experiments"
    stem = f"historical_h1h5_label_source_{as_of_date}_{horizon_days}d"
    csv_path = experiments / f"{stem}.csv"
    json_path = experiments / f"{stem}.json"
    existing = [str(path) for path in (csv_path, json_path) if path.exists()]
    if existing:
        _fail(
            "blocked_existing_label_source",
            "Label-source output already exists; implicit overwrite is barred.",
            paths=existing,
        )
    experiments.mkdir(parents=True, exist_ok=True)
    result.frame.to_csv(csv_path, index=False, encoding="utf-8-sig")
    csv_sha = _sha256(csv_path)
    payload = _json_safe(result.payload)
    payload["metadata"] = {
        **payload["metadata"],
        "csv_sha256": csv_sha,
        "outputs_written": True,
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "csv": str(csv_path),
        "json": str(json_path),
        "csv_sha256": csv_sha,
        "json_sha256": _sha256(json_path),
    }


def _validate_identity(
    *,
    as_of_date: str,
    horizon_days: int,
    benchmark: str,
) -> None:
    try:
        validate_execution_date(as_of_date)
    except HistoricalH1H5LabelDefinitionError as exc:
        _fail(exc.status, exc.message, **exc.details)
    if horizon_days != HORIZON_DAYS:
        _fail("blocked_horizon_mismatch", "Exactly 20 trading days are required.")
    if benchmark != BENCHMARK:
        _fail("blocked_benchmark_mismatch", "benchmark must equal CSI300.")


def _load_frozen_universe(
    path: Path,
    *,
    as_of_date: str,
    expected_sha256: str,
) -> tuple[list[str], str]:
    if not path.exists():
        _fail(
            "blocked_missing_frozen_cohort",
            "Frozen Phase 3.9 cohort JSON is missing.",
            path=str(path),
        )
    actual = _sha256(path)
    if actual != expected_sha256:
        _fail(
            "blocked_frozen_digest_mismatch",
            "Frozen Phase 3.9 cohort digest does not match.",
            expected_sha256=expected_sha256,
            actual_sha256=actual,
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HistoricalH1H5LabelSourceError(
            "blocked_invalid_frozen_cohort",
            "Frozen cohort JSON is invalid.",
        ) from exc
    metadata = payload.get("metadata", {})
    if (
        metadata.get("as_of_date") != as_of_date
        or metadata.get("provider_access") is not False
        or metadata.get("labels_joined") is not False
        or metadata.get("production_change") is not False
    ):
        _fail(
            "blocked_invalid_frozen_cohort",
            "Frozen cohort metadata violates the historical contract.",
        )
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        _fail("blocked_invalid_frozen_cohort", "Frozen cohort has no records.")
    symbols = sorted(
        {
            str(record.get("symbol", "")).strip()
            for record in records
            if isinstance(record, Mapping)
            and str(record.get("symbol", "")).strip()
        }
    )
    if not symbols:
        _fail("blocked_invalid_frozen_cohort", "Frozen universe is empty.")
    return symbols, actual


def _read_required_adj_close(
    path: Path,
    *,
    status: str,
    fatal: bool,
) -> pd.DataFrame | None:
    if not path.exists():
        if fatal:
            _fail(status, "Required local adjusted cache is missing.", path=str(path))
        return None
    try:
        frame = pd.read_csv(path, dtype={"trade_date": str, "symbol": str})
    except (OSError, UnicodeError, pd.errors.ParserError) as exc:
        if fatal:
            raise HistoricalH1H5LabelSourceError(
                status,
                "Required local adjusted cache cannot be parsed.",
                details={"path": str(path)},
            ) from exc
        return pd.DataFrame()
    if "trade_date" not in frame or "adj_close" not in frame:
        if fatal:
            _fail(
                "blocked_price_field_ambiguity",
                "Cache requires trade_date and adj_close; close fallback is barred.",
                path=str(path),
            )
        return pd.DataFrame()
    parsed = pd.to_datetime(frame["trade_date"], errors="coerce")
    if parsed.isna().any() or parsed.duplicated().any():
        if fatal:
            _fail(
                "blocked_invalid_cache_schema",
                "Cache trade_date values must be unique and parseable.",
                path=str(path),
            )
        return pd.DataFrame()
    result = frame.loc[:, ["trade_date", "adj_close"]].copy()
    result["trade_date"] = parsed.dt.strftime("%Y-%m-%d")
    result["adj_close"] = pd.to_numeric(result["adj_close"], errors="coerce")
    return result.sort_values("trade_date").reset_index(drop=True)


def _benchmark_window(
    frame: pd.DataFrame,
    *,
    as_of_date: str,
    horizon_days: int,
) -> tuple[list[str], list[float]]:
    by_date = frame.set_index("trade_date")["adj_close"]
    future_dates = [date for date in by_date.index if date > as_of_date]
    if as_of_date not in by_date.index:
        _fail(
            "blocked_missing_benchmark_data",
            "CSI300 cache lacks the exact as-of date.",
        )
    if len(future_dates) < horizon_days:
        _fail(
            "blocked_incomplete_benchmark_horizon",
            "CSI300 cache lacks 20 future trading dates.",
            future_date_count=len(future_dates),
        )
    selected = future_dates[:horizon_days]
    values = [by_date.loc[as_of_date], *[by_date.loc[date] for date in selected]]
    numeric = [float(value) for value in values]
    if any(not math.isfinite(value) or value <= 0 for value in numeric):
        _fail(
            "blocked_invalid_benchmark_price",
            "CSI300 adjusted prices must be finite and positive.",
        )
    return selected, numeric


def _build_symbol_row(
    symbol: str,
    *,
    adjusted_dir: Path,
    as_of_date: str,
    future_dates: list[str],
    benchmark_return: float,
) -> dict[str, Any]:
    base = {
        "validation_id": VALIDATION_ID,
        "evidence_level": EVIDENCE_LEVEL,
        "as_of_date": as_of_date,
        "horizon_days": HORIZON_DAYS,
        "benchmark": BENCHMARK,
        "symbol": symbol,
        "valid_label": False,
        "missing_label_reason": "",
        "as_of_close": None,
        "future_end_close": None,
        "future_return_20d": None,
        "benchmark_return_20d": None,
        "excess_return_20d": None,
        "max_future_close_20d": None,
        "min_future_close_20d": None,
        "max_upside_20d": None,
        "max_drawdown_20d": None,
        "winner": None,
        "loser": None,
        "severe_drawdown": None,
        "right_tail": None,
        "label_future_rows_used_count": 0,
        "label_window_start_date": future_dates[0],
        "label_window_end_date": future_dates[-1],
        "price_field": "adj_close",
    }
    path = adjusted_dir / f"{symbol}.csv"
    frame = _read_required_adj_close(
        path,
        status="missing_symbol_cache",
        fatal=False,
    )
    if frame is None:
        return {**base, "missing_label_reason": "missing_symbol_cache"}
    if frame.empty:
        return {**base, "missing_label_reason": "price_field_ambiguity"}
    by_date = frame.set_index("trade_date")["adj_close"]
    if as_of_date not in by_date.index:
        return {**base, "missing_label_reason": "missing_as_of_price"}
    missing_dates = [date for date in future_dates if date not in by_date.index]
    if missing_dates:
        return {
            **base,
            "missing_label_reason": "incomplete_20d_horizon",
            "label_future_rows_used_count": len(future_dates) - len(missing_dates),
        }
    values = [by_date.loc[as_of_date], *[by_date.loc[date] for date in future_dates]]
    numeric = [float(value) for value in values]
    if any(not math.isfinite(value) or value <= 0 for value in numeric):
        return {
            **base,
            "missing_label_reason": "nonpositive_or_nonfinite_price",
            "label_future_rows_used_count": HORIZON_DAYS,
        }
    entry = numeric[0]
    future = numeric[1:]
    future_return = future[-1] / entry - 1.0
    running_max = pd.Series([entry, *future]).cummax()
    drawdown = min(
        price / peak - 1.0
        for price, peak in zip([entry, *future], running_max)
    )
    return {
        **base,
        "valid_label": True,
        "as_of_close": entry,
        "future_end_close": future[-1],
        "future_return_20d": future_return,
        "benchmark_return_20d": benchmark_return,
        "excess_return_20d": future_return - benchmark_return,
        "max_future_close_20d": max(future),
        "min_future_close_20d": min(future),
        "max_upside_20d": max(future) / entry - 1.0,
        "max_drawdown_20d": float(drawdown),
        "label_future_rows_used_count": HORIZON_DAYS,
    }


def _assign_boolean_labels(
    frame: pd.DataFrame,
    definitions: Mapping[str, Any],
) -> None:
    valid = frame.loc[frame["valid_label"]].copy()
    if valid.empty:
        return
    n = len(valid)
    tail_count = min(max(10, math.ceil(0.10 * n)), max(1, n // 2))
    winner_indices: set[int] = set()
    loser_indices: set[int] = set()
    for field in ("future_return_20d", "excess_return_20d"):
        top = valid.sort_values(
            [field, "symbol"],
            ascending=[False, True],
            kind="stable",
        ).head(tail_count)
        bottom = valid.sort_values(
            [field, "symbol"],
            ascending=[True, True],
            kind="stable",
        ).head(tail_count)
        winner_indices.update(top.index)
        loser_indices.update(bottom.index)
    frame.loc[valid.index, "winner"] = False
    frame.loc[valid.index, "loser"] = False
    frame.loc[list(winner_indices), "winner"] = True
    frame.loc[list(loser_indices), "loser"] = True
    frame.loc[valid.index, "severe_drawdown"] = (
        valid["max_drawdown_20d"] <= definitions["severe_drawdown"]["threshold"]
    )
    threshold = valid["future_return_20d"].quantile(
        definitions["right_tail"]["quantile"],
        interpolation=definitions["right_tail"]["interpolation"],
    )
    frame.loc[valid.index, "right_tail"] = (
        valid["future_return_20d"] >= threshold
    )
    conflict = frame.loc[valid.index, "winner"].astype(bool) & frame.loc[
        valid.index, "loser"
    ].astype(bool)
    if conflict.any():
        _fail(
            "blocked_winner_loser_conflict",
            "A valid row cannot be both winner and loser.",
            symbols=frame.loc[conflict.index[conflict], "symbol"].tolist(),
        )


def _validate_built_frame(frame: pd.DataFrame, *, as_of_date: str) -> None:
    try:
        validate_label_source_schema(frame.columns, as_of_date=as_of_date)
    except HistoricalH1H5LabelDefinitionError as exc:
        _fail(exc.status, exc.message, **exc.details)
    if frame["symbol"].duplicated().any() or frame["symbol"].eq("").any():
        _fail("blocked_invalid_label_symbols", "Symbols must be unique and non-empty.")
    valid = frame["valid_label"]
    if frame.loc[valid, "missing_label_reason"].ne("").any():
        _fail("blocked_invalid_missing_reason", "Valid rows require an empty reason.")
    if frame.loc[~valid, "missing_label_reason"].eq("").any():
        _fail("blocked_invalid_missing_reason", "Invalid rows require a reason.")


def _reject_existing_final_outputs(outputs: Path, *, as_of_date: str) -> None:
    validation = outputs / "validation"
    candidates = (
        validation / f"historical_h1h5_evaluation_{as_of_date}_20d.csv",
        validation / f"historical_h1h5_evaluation_{as_of_date}_20d.json",
        validation / "historical_h1h5_summary_h1h5-historical-sealed-v1.json",
    )
    existing = [str(path) for path in candidates if path.exists()]
    if existing:
        _fail(
            "blocked_existing_validation_output",
            "Existing final evaluation output blocks sealed label generation.",
            paths=existing,
        )


def _normalized_text_sha256(path: Path) -> str:
    if not path.exists():
        _fail(
            "blocked_missing_label_definition_config",
            "Label definition config is missing.",
            path=str(path),
        )
    data = path.read_bytes().replace(bytes([13, 10]), bytes([10]))
    return hashlib.sha256(data).hexdigest().upper()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    if hasattr(value, "item"):
        return _json_safe(value.item())
    return value


def _fail(status: str, message: str, **details: Any) -> None:
    raise HistoricalH1H5LabelSourceError(status, message, details=details)
