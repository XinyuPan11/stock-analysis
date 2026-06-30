from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from stock_analysis.validation.bias_metadata import validation_bias_metadata
from stock_analysis.validation.cache_plan import recommended_target_end_date
from stock_analysis.validation.future_returns import benchmark_aliases


PROPOSED_U1_WINDOWS: tuple[tuple[str, int], ...] = (
    ("2024-02-29", 20),
    ("2024-05-31", 20),
    ("2024-08-30", 20),
    ("2024-11-29", 20),
)
PROPOSED_U2_WINDOWS: tuple[tuple[str, int], ...] = (
    ("2025-02-28", 20),
    ("2025-05-30", 20),
    ("2025-08-29", 20),
    ("2025-11-28", 20),
)
CONSUMED_U1_WINDOWS: tuple[tuple[str, int], ...] = PROPOSED_U1_WINDOWS
FORBIDDEN_ANSWER_KEY_WINDOWS: tuple[tuple[str, int], ...] = (
    ("2024-01-31", 20),
    ("2024-04-30", 20),
    ("2024-07-31", 20),
    ("2024-10-31", 20),
)
DEFAULT_WINDOW_SET = "u1-2024"
WINDOW_SET_SPECS: dict[str, dict[str, Any]] = {
    "u1-2024": {
        "phase": "2.19",
        "label": "U1",
        "windows": PROPOSED_U1_WINDOWS,
        "output_stem": "unseen_window_readiness_2024",
        "accepted_status": "accepted_proposed_u1_candidate",
        "accepted_reason": "phase_2_18_proposed_candidate",
        "outside_status": "rejected_outside_frozen_u1_candidate_pool",
        "outside_reason": "not_in_phase_2_18_proposed_u1_pool",
    },
    "u2-2025": {
        "phase": "2.26",
        "label": "U2",
        "windows": PROPOSED_U2_WINDOWS,
        "output_stem": "u2_window_readiness_2025",
        "accepted_status": "accepted_preregistered_u2_candidate",
        "accepted_reason": "phase_2_25_preregistered_u2_candidate",
        "outside_status": "rejected_outside_frozen_u2_candidate_pool",
        "outside_reason": "not_in_phase_2_25_preregistered_u2_pool",
    },
}
WINDOW_SET_NAMES: tuple[str, ...] = tuple(WINDOW_SET_SPECS)
DISCLAIMER = (
    "Readiness-only inspection. Proposed U1 windows have not been evaluated. "
    "No unseen outcomes or performance metrics are read or computed."
)


@dataclass(frozen=True)
class UnseenWindowReadinessConfig:
    outputs_dir: str | Path = "outputs"
    cache_dir: str | Path = "data\\cache\\daily-use"
    provider: str = "baostock"
    benchmark: str = "CSI300"
    limit: int = 300
    window_set: str = DEFAULT_WINDOW_SET


def check_unseen_window_readiness(
    config: UnseenWindowReadinessConfig,
) -> dict[str, Any]:
    spec = _window_set_spec(config.window_set)
    selected_windows = tuple(spec["windows"])
    windows = [
        _check_window(config, as_of_date, horizon)
        for as_of_date, horizon in selected_windows
    ]
    status_counts: dict[str, int] = {}
    for item in windows:
        status = str(item["readiness_status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    selected_payload = [
        {"as_of_date": as_of_date, "horizon_days": horizon}
        for as_of_date, horizon in selected_windows
    ]
    report = {
        "phase": spec["phase"],
        "status": "readiness_complete",
        "window_set": config.window_set,
        "window_set_label": spec["label"],
        "output_stem": spec["output_stem"],
        "readiness_only": True,
        "provider_access": False,
        "provider_fetch_executed": False,
        "labels_calculated": False,
        "future_returns_recomputed": False,
        "outcomes_inspected": False,
        "performance_metrics_computed": False,
        "production_logic_changed": False,
        "disclaimer": _disclaimer(config.window_set),
        "selected_windows": selected_payload,
        "forbidden_answer_key_windows": [
            {"as_of_date": as_of_date, "horizon_days": horizon}
            for as_of_date, horizon in FORBIDDEN_ANSWER_KEY_WINDOWS
        ],
        "consumed_u1_windows": [
            {"as_of_date": as_of_date, "horizon_days": horizon}
            for as_of_date, horizon in CONSUMED_U1_WINDOWS
        ],
        "forbidden_windows_excluded": not (
            set(selected_windows) & set(FORBIDDEN_ANSWER_KEY_WINDOWS)
        ),
        "consumed_u1_windows_excluded": not (
            set(selected_windows) & set(CONSUMED_U1_WINDOWS)
        ),
        "status_counts": status_counts,
        "windows": windows,
        "guardrails": [
            "This is readiness only, not validation.",
            "The original answer-key windows remain forbidden as proof.",
            "Consumed U1 windows are excluded from the U2 window set.",
            "Prediction rows and future-return fields are not opened.",
            "Unseen outcomes, list performance, winner/loser groups, and hypotheses are not evaluated.",
            "Provider access remains false.",
        ],
    }
    selected_key = "proposed_u1_windows" if config.window_set == "u1-2024" else "proposed_u2_windows"
    report[selected_key] = selected_payload
    return report


def validate_unseen_window_candidate(
    as_of_date: str,
    horizon_days: int,
    window_set: str = DEFAULT_WINDOW_SET,
) -> dict[str, Any]:
    spec = _window_set_spec(window_set)
    key = (as_of_date, int(horizon_days))
    if key in FORBIDDEN_ANSWER_KEY_WINDOWS:
        return {
            "accepted": False,
            "candidate_status": "rejected_forbidden_answer_key_window",
            "reason": "permanently_forbidden_as_proof",
        }
    if window_set == "u2-2025" and key in CONSUMED_U1_WINDOWS:
        return {
            "accepted": False,
            "candidate_status": "rejected_consumed_u1_window",
            "reason": "consumed_u1_not_eligible_for_sealed_u2",
        }
    if key not in spec["windows"]:
        return {
            "accepted": False,
            "candidate_status": spec["outside_status"],
            "reason": spec["outside_reason"],
        }
    return {
        "accepted": True,
        "candidate_status": spec["accepted_status"],
        "reason": spec["accepted_reason"],
    }


def write_unseen_window_readiness(
    report: dict[str, Any],
    outputs_dir: str | Path,
) -> dict[str, str]:
    output_dir = Path(outputs_dir) / "experiments"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_stem = str(report.get("output_stem") or "unseen_window_readiness_2024")
    json_path = output_dir / f"{output_stem}.json"
    markdown_path = output_dir / f"{output_stem}.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    markdown_path.write_text(markdown_unseen_window_readiness(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path)}


def markdown_unseen_window_readiness(report: dict[str, Any]) -> str:
    label = str(report.get("window_set_label") or "U1")
    is_u2 = report.get("window_set") == "u2-2025"
    state_line = (
        "The U2 results remain sealed and have not been evaluated."
        if is_u2
        else "The U1 windows are proposed and have not been evaluated."
    )
    lines = [
        f"# {label} Window Readiness Check",
        "",
        str(report.get("disclaimer", DISCLAIMER)),
        "",
        f"This is readiness only, not validation. {state_line}",
        "The four original answer-key windows remain permanently forbidden as proof.",
        "Consumed U1 windows are excluded from sealed U2 confirmation.",
        "No unseen outcomes, list performance, winner/loser metrics, or hypothesis results were inspected.",
        "",
        "## Guardrails",
        "",
        f"- Provider access: `{str(report.get('provider_access')).lower()}`",
        f"- Outcomes inspected: `{str(report.get('outcomes_inspected')).lower()}`",
        f"- Performance metrics computed: `{str(report.get('performance_metrics_computed')).lower()}`",
        f"- Forbidden windows excluded: `{str(report.get('forbidden_windows_excluded')).lower()}`",
        f"- Consumed U1 windows excluded: `{str(report.get('consumed_u1_windows_excluded')).lower()}`",
        "",
        f"## Proposed {label} Readiness",
        "",
        "| As-of date | Horizon | Status | Future end | Symbols | As-of cache | Future cache | Benchmark | Missing as-of outputs | Existing validation outputs |",
        "|---|---:|---|---|---:|---|---|---|---|---|",
    ]
    for item in report.get("windows", []):
        if not isinstance(item, dict):
            continue
        stock_cache = item.get("stock_cache", {})
        benchmark_cache = item.get("benchmark_cache", {})
        lines.append(
            "| {date} | {horizon}D | {status} | {end} | {symbols} | {asof_cache} | "
            "{future_cache} | {benchmark} | {missing_asof} | {existing_validation} |".format(
                date=item.get("as_of_date", ""),
                horizon=item.get("horizon_days", ""),
                status=item.get("readiness_status", ""),
                end=item.get("required_future_end_date", ""),
                symbols=item.get("symbol_count", 0),
                asof_cache=stock_cache.get("as_of_status", ""),
                future_cache=stock_cache.get("future_window_status", ""),
                benchmark=benchmark_cache.get("status", ""),
                missing_asof=len(item.get("missing_as_of_outputs", {})),
                existing_validation=len(item.get("existing_validation_outputs", {})),
            )
        )
    lines.extend(
        [
            "",
            "## Readiness Meaning",
            "",
            "- `ready_for_dry_run`: local prerequisites are present; this does not validate a hypothesis.",
            "- `blocked_missing_as_of_outputs`: generate the missing historical as-of artifacts first.",
            "- `blocked_missing_symbols`: no non-empty as-of symbol set can be formed safely.",
            "- `blocked_stock_cache`: local stock cache does not cover the required dates.",
            "- `blocked_benchmark_cache`: local benchmark cache does not cover the required dates.",
            "- `blocked_existing_unseen_outputs`: output presence must be audited because the sealed window may already be consumed.",
            "",
            "Missing validation outputs are expected before an unseen run. Point-in-time and leakage metadata become per-window verifiable only after a controlled dry-run/write-output; their required contract is checked here without reading outcome fields.",
            "",
            "## Missing Prerequisites",
            "",
        ]
    )
    any_missing = False
    for item in report.get("windows", []):
        if not isinstance(item, dict):
            continue
        prerequisites = item.get("missing_prerequisites", [])
        if prerequisites:
            any_missing = True
            lines.append(f"### {item.get('as_of_date')} {item.get('horizon_days')}D")
            lines.append("")
            lines.extend(f"- {value}" for value in prerequisites)
            lines.append("")
    if not any_missing:
        lines.extend(["No missing technical prerequisites were detected.", ""])
    lines.extend(
        [
            "## Later Manual Commands",
            "",
            f"Run validation only after the {label} selection and readiness state are committed. Commands in this report were not executed by the checker.",
            "",
        ]
    )
    for item in report.get("windows", []):
        if not isinstance(item, dict):
            continue
        lines.extend(
            [
                f"### {item.get('as_of_date')} {item.get('horizon_days')}D",
                "",
                "~~~powershell",
                str(item.get("next_manual_command", "No command while blocked.")),
                "~~~",
                "",
            ]
        )
    lines.extend(
        [
            "## Interpretation Boundary",
            "",
            "A ready status proves only that a later controlled run is technically feasible from local inputs. It is not validation evidence, does not consume or interpret unseen outcomes, and does not support production changes.",
            "",
        ]
    )
    return "\n".join(lines)


def _check_window(
    config: UnseenWindowReadinessConfig,
    as_of_date: str,
    horizon_days: int,
) -> dict[str, Any]:
    candidate = validate_unseen_window_candidate(
        as_of_date, horizon_days, window_set=config.window_set
    )
    outputs_dir = Path(config.outputs_dir)
    required_future_end = recommended_target_end_date(as_of_date, horizon_days)
    as_of_outputs = _as_of_output_presence(outputs_dir, as_of_date)
    missing_as_of = {
        key: value for key, value in as_of_outputs.items() if not value["exists"]
    }
    validation_outputs = _validation_output_presence(outputs_dir, as_of_date, horizon_days)
    existing_validation = {
        key: value for key, value in validation_outputs.items() if value["exists"]
    }
    symbols = _load_as_of_symbols(outputs_dir, as_of_date, config.limit)
    stock_cache = _stock_cache_readiness(
        Path(config.cache_dir),
        config.provider,
        symbols,
        as_of_date,
        required_future_end,
    )
    benchmark_cache = _benchmark_cache_readiness(
        Path(config.cache_dir),
        config.provider,
        config.benchmark,
        as_of_date,
        required_future_end,
    )
    if existing_validation:
        guard_metadata = {
            "status": "not_inspected_existing_validation_outputs",
            "metadata_verified": False,
            "outcome_fields_read": [],
        }
    else:
        guard_metadata = _guard_metadata_presence(
            outputs_dir, as_of_date, horizon_days
        )
    member_snapshot = _member_snapshot_feasibility(
        as_of_outputs, validation_outputs, stock_cache, symbols
    )
    readiness_status, missing_prerequisites = _readiness_status(
        candidate,
        missing_as_of,
        symbols,
        stock_cache,
        benchmark_cache,
        existing_validation,
    )
    provider_fetch_flags = (
        stock_cache.get("provider_fetch_required"),
        benchmark_cache.get("provider_fetch_required"),
    )
    provider_fetch_required: bool | None
    if any(value is True for value in provider_fetch_flags):
        provider_fetch_required = True
    elif any(value is None for value in provider_fetch_flags):
        provider_fetch_required = None
    else:
        provider_fetch_required = False
    return {
        "as_of_date": as_of_date,
        "horizon_days": horizon_days,
        "required_future_end_date": required_future_end,
        **candidate,
        "provider_access": False,
        "provider_fetch_required": provider_fetch_required,
        "as_of_outputs": as_of_outputs,
        "missing_as_of_outputs": missing_as_of,
        "validation_output_presence": validation_outputs,
        "existing_validation_outputs": existing_validation,
        "validation_outputs_expected_before_evaluation": False,
        "symbol_count": len(symbols),
        "symbol_source": "as_of_outputs_only",
        "stock_cache": stock_cache,
        "benchmark_cache": benchmark_cache,
        "member_level_snapshot": member_snapshot,
        "point_in_time_guard": guard_metadata,
        "future_labels_separated_from_as_of_features": True,
        "feature_window_rule": "trade_date <= as_of_date",
        "label_window_rule": "trade_date > as_of_date; explicit validation labels only",
        "prediction_rows_opened": False,
        "readiness_status": readiness_status,
        "missing_prerequisites": missing_prerequisites,
        "next_manual_command": _next_manual_command(
            config, as_of_date, horizon_days, readiness_status
        ),
    }


def _as_of_output_presence(outputs_dir: Path, as_of_date: str) -> dict[str, dict[str, Any]]:
    paths = {
        "stock_labels_json": outputs_dir / "labels" / f"stock_labels_{as_of_date}.json",
        "stock_labels_csv": outputs_dir / "labels" / f"stock_labels_{as_of_date}.csv",
        "factors": outputs_dir / "daily" / f"factors_{as_of_date}.csv",
        "high_confidence_candidates": outputs_dir / "lists" / f"high_confidence_candidates_{as_of_date}.json",
        "trend_leaders": outputs_dir / "lists" / f"trend_leaders_{as_of_date}.json",
        "long_term_stable": outputs_dir / "lists" / f"long_term_stable_{as_of_date}.json",
        "breakout_watch": outputs_dir / "lists" / f"breakout_watch_{as_of_date}.json",
        "accumulation_watch": outputs_dir / "lists" / f"accumulation_watch_{as_of_date}.json",
        "rebound_watch": outputs_dir / "lists" / f"rebound_watch_{as_of_date}.json",
        "high_risk_active": outputs_dir / "lists" / f"high_risk_active_{as_of_date}.json",
        "multi_lists": outputs_dir / "lists" / f"multi_lists_{as_of_date}.json",
    }
    return {
        key: {"path": str(path), "exists": path.exists()} for key, path in paths.items()
    }


def _validation_output_presence(
    outputs_dir: Path,
    as_of_date: str,
    horizon_days: int,
) -> dict[str, dict[str, Any]]:
    suffix = f"{as_of_date}_{horizon_days}d"
    paths = {
        "walk_forward_summary": outputs_dir / "validation" / f"walk_forward_summary_{suffix}.json",
        "walk_forward_predictions": outputs_dir / "validation" / f"walk_forward_predictions_{suffix}.csv",
        "list_performance": outputs_dir / "validation" / f"list_performance_{suffix}.json",
        "factor_effectiveness": outputs_dir / "validation" / f"factor_effectiveness_{suffix}.json",
        "walk_forward_report": outputs_dir / "validation" / f"walk_forward_report_{suffix}.md",
        "portfolio_summary": outputs_dir / "portfolios" / f"portfolio_summary_{suffix}.json",
    }
    return {
        key: {"path": str(path), "exists": path.exists()} for key, path in paths.items()
    }


def _load_as_of_symbols(outputs_dir: Path, as_of_date: str, limit: int) -> list[str]:
    symbols: list[str] = []
    labels_json = outputs_dir / "labels" / f"stock_labels_{as_of_date}.json"
    if labels_json.exists():
        symbols.extend(_symbols_from_json(labels_json))
    labels_csv = outputs_dir / "labels" / f"stock_labels_{as_of_date}.csv"
    factors_csv = outputs_dir / "daily" / f"factors_{as_of_date}.csv"
    for path in (labels_csv, factors_csv):
        if path.exists():
            symbols.extend(_symbols_from_csv(path))
    for path in sorted((outputs_dir / "lists").glob(f"*_{as_of_date}.json")):
        symbols.extend(_symbols_from_json(path))
    result = _dedupe(symbols)
    return result[:limit] if limit > 0 else result


def _symbols_from_csv(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "symbol" not in reader.fieldnames:
            return []
        return [
            str(row.get("symbol", "")).strip()
            for row in reader
            if str(row.get("symbol", "")).strip()
        ]


def _symbols_from_json(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    symbols: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            symbol = value.get("symbol")
            if symbol:
                symbols.append(str(symbol).strip())
            for key in ("items", "lists"):
                if key in value:
                    visit(value[key])

    visit(payload)
    return symbols


def _stock_cache_readiness(
    cache_dir: Path,
    provider: str,
    symbols: list[str],
    as_of_date: str,
    future_end_date: str,
) -> dict[str, Any]:
    if not symbols:
        return {
            "status": "not_evaluated_missing_symbols",
            "as_of_status": "not_evaluated",
            "future_window_status": "not_evaluated",
            "symbol_count": 0,
            "as_of_covered_count": 0,
            "future_end_covered_count": 0,
            "provider_fetch_required": None,
            "missing_or_stale_symbols": [],
        }
    rows = []
    for symbol in symbols:
        path = cache_dir / provider / "stock_daily" / "adjusted" / f"{symbol}.csv"
        bounds = _cached_date_bounds(path)
        latest = bounds.get("latest_date")
        rows.append(
            {
                "symbol": symbol,
                "exists": bounds["exists"],
                "latest_date": latest,
                "covers_as_of": bool(latest and latest >= as_of_date),
                "covers_future_end": bool(latest and latest >= future_end_date),
                "date_status": bounds["status"],
            }
        )
    as_of_count = sum(1 for row in rows if row["covers_as_of"])
    future_count = sum(1 for row in rows if row["covers_future_end"])
    missing = [row for row in rows if not row["covers_future_end"]]
    return {
        "status": "covered" if future_count == len(symbols) else "incomplete",
        "as_of_status": "covered" if as_of_count == len(symbols) else "incomplete",
        "future_window_status": "covered" if future_count == len(symbols) else "incomplete",
        "symbol_count": len(symbols),
        "as_of_covered_count": as_of_count,
        "future_end_covered_count": future_count,
        "missing_or_stale_count": len(missing),
        "missing_or_stale_symbols": [row["symbol"] for row in missing[:50]],
        "missing_or_stale_symbols_truncated": len(missing) > 50,
        "provider_fetch_required": bool(missing),
    }


def _benchmark_cache_readiness(
    cache_dir: Path,
    provider: str,
    benchmark: str,
    as_of_date: str,
    future_end_date: str,
) -> dict[str, Any]:
    candidates: list[tuple[str, Path]] = []
    for alias in _dedupe([benchmark, *benchmark_aliases(benchmark)]):
        candidates.extend(
            [
                (alias, cache_dir / provider / "index_daily" / "raw" / f"{alias}.csv"),
                (alias, cache_dir / provider / "stock_daily" / "adjusted" / f"{alias}.csv"),
            ]
        )
    available = []
    for alias, path in candidates:
        bounds = _cached_date_bounds(path)
        if bounds["exists"] and bounds.get("latest_date"):
            available.append({"symbol": alias, "path": str(path), **bounds})
    latest = max((str(row["latest_date"]) for row in available), default=None)
    resolved = next(
        (row["symbol"] for row in available if row.get("latest_date") == latest),
        benchmark_aliases(benchmark)[0],
    )
    as_of_covered = bool(latest and latest >= as_of_date)
    future_covered = bool(latest and latest >= future_end_date)
    return {
        "status": "covered" if as_of_covered and future_covered else "incomplete",
        "requested_benchmark": benchmark,
        "resolved_symbol": resolved,
        "latest_cached_date": latest,
        "covers_as_of": as_of_covered,
        "covers_future_end": future_covered,
        "provider_fetch_required": not (as_of_covered and future_covered),
    }


def _cached_date_bounds(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "status": "missing_file", "earliest_date": None, "latest_date": None}
    values: list[str] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or "trade_date" not in reader.fieldnames:
                return {"exists": True, "status": "missing_trade_date", "earliest_date": None, "latest_date": None}
            for row in reader:
                value = str(row.get("trade_date", "")).strip()
                if not value:
                    continue
                try:
                    values.append(date.fromisoformat(value).isoformat())
                except ValueError:
                    return {"exists": True, "status": "malformed_trade_date", "earliest_date": None, "latest_date": None}
    except (OSError, UnicodeError, csv.Error):
        return {"exists": True, "status": "read_error", "earliest_date": None, "latest_date": None}
    if not values:
        return {"exists": True, "status": "empty", "earliest_date": None, "latest_date": None}
    return {
        "exists": True,
        "status": "ok",
        "earliest_date": min(values),
        "latest_date": max(values),
    }


def _guard_metadata_presence(
    outputs_dir: Path,
    as_of_date: str,
    horizon_days: int,
) -> dict[str, Any]:
    path = outputs_dir / "validation" / f"walk_forward_summary_{as_of_date}_{horizon_days}d.json"
    expected = validation_bias_metadata()
    if not path.exists():
        return {
            "status": "not_yet_available_pre_validation",
            "summary_path": str(path),
            "summary_exists": False,
            "metadata_verified": False,
            "expected_contract": {
                "price_point_in_time_guard_applied": expected["price_point_in_time_guard_applied"],
                "feature_input_point_in_time_status": expected["feature_input_point_in_time_status"],
                "future_label_window_status": expected["future_label_window_status"],
                "leakage_guard_applied": True,
                "no_future_leakage": True,
            },
        }
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    source = payload.get("summary", payload) if isinstance(payload, dict) else {}
    allowed = {
        key: source.get(key)
        for key in (
            "as_of_date",
            "horizon_days",
            "latest_input_date",
            "max_raw_cache_date",
            "future_rows_excluded_count",
            "leakage_guard_applied",
            "no_future_leakage",
            "price_point_in_time_guard_applied",
            "feature_input_point_in_time_status",
            "future_label_window_status",
            "universe_point_in_time_status",
            "listing_status_point_in_time_status",
            "st_status_point_in_time_status",
            "suspension_status_point_in_time_status",
        )
    }
    verified = (
        allowed.get("as_of_date") == as_of_date
        and int(allowed.get("horizon_days") or -1) == horizon_days
        and bool(allowed.get("leakage_guard_applied"))
        and bool(allowed.get("no_future_leakage"))
        and bool(allowed.get("price_point_in_time_guard_applied"))
        and allowed.get("feature_input_point_in_time_status") == "guarded"
        and allowed.get("future_label_window_status") == "explicit_future_only"
        and bool(allowed.get("latest_input_date"))
        and str(allowed.get("latest_input_date")) <= as_of_date
    )
    return {
        "status": "verified_existing_metadata" if verified else "existing_metadata_not_verified",
        "summary_path": str(path),
        "summary_exists": True,
        "metadata_verified": verified,
        "metadata_fields": allowed,
        "outcome_fields_read": [],
    }


def _member_snapshot_feasibility(
    as_of_outputs: dict[str, dict[str, Any]],
    validation_outputs: dict[str, dict[str, Any]],
    stock_cache: dict[str, Any],
    symbols: list[str],
) -> dict[str, Any]:
    factors_ready = bool(as_of_outputs["factors"]["exists"])
    lists_ready = bool(as_of_outputs["multi_lists"]["exists"])
    predictions_ready = bool(validation_outputs["walk_forward_predictions"]["exists"])
    cache_ready = stock_cache.get("as_of_status") == "covered"
    if factors_ready and lists_ready and predictions_ready and cache_ready and symbols:
        status = "feasible_after_validation"
    elif factors_ready and lists_ready and cache_ready and symbols:
        status = "pending_validation_predictions"
    else:
        status = "blocked_missing_snapshot_prerequisites"
    return {
        "status": status,
        "factors_available": factors_ready,
        "list_membership_available": lists_ready,
        "prediction_file_present": predictions_ready,
        "as_of_cache_available": cache_ready,
        "snapshot_executed": False,
        "labels_recomputed": False,
    }


def _readiness_status(
    candidate: dict[str, Any],
    missing_as_of: dict[str, Any],
    symbols: list[str],
    stock_cache: dict[str, Any],
    benchmark_cache: dict[str, Any],
    existing_validation: dict[str, Any],
) -> tuple[str, list[str]]:
    if not candidate["accepted"]:
        return str(candidate["candidate_status"]), [str(candidate["reason"])]
    if existing_validation:
        return (
            "blocked_existing_unseen_outputs",
            ["audit_existing_validation_outputs_without_opening_outcomes"],
        )
    if missing_as_of:
        return (
            "blocked_missing_as_of_outputs",
            [f"missing_as_of_output:{key}" for key in missing_as_of],
        )
    if not symbols:
        return "blocked_missing_symbols", ["no_symbols_loaded_from_as_of_outputs"]
    if stock_cache.get("as_of_status") != "covered":
        return "blocked_stock_cache", ["stock_cache_does_not_cover_as_of_date"]
    if stock_cache.get("future_window_status") != "covered":
        return "blocked_stock_cache", ["stock_cache_does_not_cover_required_future_end"]
    if benchmark_cache.get("status") != "covered":
        return "blocked_benchmark_cache", ["benchmark_cache_does_not_cover_required_dates"]
    return "ready_for_dry_run", []


def _next_manual_command(
    config: UnseenWindowReadinessConfig,
    as_of_date: str,
    horizon_days: int,
    readiness_status: str,
) -> str:
    if readiness_status == "ready_for_dry_run":
        return (
            "python backend\\scripts\\run_controlled_validation_batch.py "
            f"--as-of-date {as_of_date} --horizon-days {horizon_days} "
            f"--benchmark {config.benchmark} --outputs-dir {config.outputs_dir} "
            f"--cache-dir {config.cache_dir} --limit {config.limit}"
        )
    if readiness_status == "blocked_existing_unseen_outputs":
        return "No command: audit whether this sealed window has already been consumed."
    if readiness_status == "blocked_missing_as_of_outputs":
        return (
            "No validation command: create the missing cache-only as-of artifacts, "
            f"then rerun Phase {_window_set_spec(config.window_set)['phase']} readiness."
        )
    if readiness_status in {"blocked_stock_cache", "blocked_benchmark_cache"}:
        return (
            "No validation command: local cache coverage is incomplete; "
            f"provider access is not allowed in Phase {_window_set_spec(config.window_set)['phase']}."
        )
    return "No command while this window is blocked."


def _window_set_spec(window_set: str) -> dict[str, Any]:
    try:
        return WINDOW_SET_SPECS[window_set]
    except KeyError as exc:
        raise ValueError(
            f"Unknown window set: {window_set}. Expected one of: {', '.join(WINDOW_SET_NAMES)}"
        ) from exc


def _disclaimer(window_set: str) -> str:
    if window_set == "u2-2025":
        return (
            "Readiness-only inspection. Preregistered U2 results remain sealed. "
            "No unseen outcomes or performance metrics are read or computed."
        )
    return DISCLAIMER


def _dedupe(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result
