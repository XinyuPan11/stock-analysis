"""Safe as-of factors and membership projections for historical H1-H5."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable

import pandas as pd

from stock_analysis.research.feature_only_snapshot import (
    find_outcome_columns,
)
from stock_analysis.research.historical_h1h5_readiness import (
    HISTORICAL_EXCLUDED_WINDOWS,
    HISTORICAL_PRIMARY_WINDOWS,
    HISTORICAL_VALIDATION_ID,
    MINIMUM_VALID_UNIVERSE_ROWS,
)


HISTORICAL_EVIDENCE_LEVEL = "historical_sealed_not_prospective"
LIST_FIELD_MAP: dict[str, str] = {
    "high_confidence_candidates": "is_high_confidence",
    "trend_leaders": "is_trend_leader",
    "long_term_stable": "is_long_term_stable",
    "breakout_watch": "is_breakout_watch",
    "accumulation_watch": "is_accumulation_watch",
    "rebound_watch": "is_rebound_watch",
    "high_risk_active": "is_high_risk_active",
}
POSITIVE_LIST_IDS: frozenset[str] = frozenset(
    list_id
    for list_id in LIST_FIELD_MAP
    if list_id != "high_risk_active"
)
SAFE_ITEM_CONTEXT_FIELDS: tuple[str, ...] = (
    "rank",
    "total_score",
    "momentum_score",
    "trend_score",
    "relative_strength_score",
    "risk_score",
    "liquidity_score",
    "primary_type",
    "research_status",
    "risk_level",
)
AUDITED_DROPPABLE_FIELDS: frozenset[str] = frozenset(
    {
        "label",
        "label_reason",
        "research_label",
        "source_label",
    }
)
FORBIDDEN_INPUT_PATH_PATTERN = re.compile(
    r"(^|[\\/_.-])("
    r"validation|walk_forward_predictions|list_performance|"
    r"factor_effectiveness|strategy_experiments|future_labels?"
    r")([\\/_.-]|$)",
    re.IGNORECASE,
)


class HistoricalAsOfArtifactError(ValueError):
    def __init__(
        self,
        status: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.details = dict(details or {})


@dataclass
class HistoricalAsOfArtifactResult:
    factors: pd.DataFrame
    membership: pd.DataFrame
    metadata: dict[str, Any]


def build_historical_asof_artifacts(
    *,
    as_of_date: str,
    factors_file: str | Path,
    multi_list_file: str | Path,
) -> HistoricalAsOfArtifactResult:
    _validate_primary_date(as_of_date)
    factors_path = _validate_input_path(factors_file, role="factors")
    lists_path = _validate_input_path(
        multi_list_file,
        role="multi_list",
        suffix=".json",
    )
    factors = _load_factors(factors_path, as_of_date=as_of_date)
    payload = _load_multi_list(lists_path, as_of_date=as_of_date)
    dropped_fields = sorted(
        set(_forbidden_json_keys(payload)).intersection(
            AUDITED_DROPPABLE_FIELDS
        )
    )
    unsafe_fields = sorted(
        set(_forbidden_json_keys(payload))
        - AUDITED_DROPPABLE_FIELDS
    )
    if unsafe_fields:
        raise HistoricalAsOfArtifactError(
            "blocked_unsafe_multi_list_fields",
            "Multi-list artifact contains non-droppable outcome fields.",
            details={"forbidden_fields": unsafe_fields},
        )

    membership, ignored_symbols = _project_membership(
        factors,
        payload,
        as_of_date=as_of_date,
    )
    safe_factors = factors.copy()
    for frame in (safe_factors, membership):
        frame["research_only"] = True
        frame["provider_access"] = False
        frame["labels_joined"] = False
        frame["production_change"] = False
        frame["validation_id"] = HISTORICAL_VALIDATION_ID
        frame["evidence_level"] = HISTORICAL_EVIDENCE_LEVEL
    _reject_unsafe_output(safe_factors, role="safe_factors")
    _reject_unsafe_output(membership, role="safe_membership")

    metadata = {
        "status": "ok",
        "research_only": True,
        "safe_as_of_projection": True,
        "provider_access": False,
        "provider_fallback_available": False,
        "labels_joined": False,
        "production_change": False,
        "validation_run": False,
        "validation_outputs_read": False,
        "evaluator_called": False,
        "future_labels_generated": False,
        "future_returns_computed": False,
        "h1h5_cohort_builder_called": False,
        "feature_only_snapshot_generated": False,
        "validation_id": HISTORICAL_VALIDATION_ID,
        "evidence_level": HISTORICAL_EVIDENCE_LEVEL,
        "as_of_date": as_of_date,
        "source_factors_path": str(factors_path),
        "source_multi_list_path": str(lists_path),
        "factor_row_count": int(len(safe_factors)),
        "membership_row_count": int(len(membership)),
        "dropped_unsafe_fields": dropped_fields,
        "ignored_list_symbol_count": len(ignored_symbols),
        "ignored_list_symbols": ignored_symbols[:50],
        "list_ids": sorted(LIST_FIELD_MAP),
        "output_paths": {},
    }
    return HistoricalAsOfArtifactResult(
        factors=safe_factors,
        membership=membership,
        metadata=metadata,
    )


def write_historical_asof_artifacts(
    result: HistoricalAsOfArtifactResult,
    *,
    outputs_dir: str | Path,
) -> dict[str, str]:
    experiments_dir = Path(outputs_dir) / "experiments"
    experiments_dir.mkdir(parents=True, exist_ok=True)
    as_of_date = str(result.metadata["as_of_date"])
    factors_path = (
        experiments_dir / f"historical_h1h5_factors_{as_of_date}.csv"
    )
    membership_path = (
        experiments_dir / f"historical_h1h5_membership_{as_of_date}.csv"
    )
    _reject_unsafe_output(result.factors, role="safe_factors")
    _reject_unsafe_output(result.membership, role="safe_membership")
    result.factors.to_csv(factors_path, index=False, encoding="utf-8-sig")
    result.membership.to_csv(
        membership_path,
        index=False,
        encoding="utf-8-sig",
    )
    paths = {
        "factors_csv": str(factors_path),
        "membership_csv": str(membership_path),
    }
    result.metadata["output_paths"] = paths
    return paths


def _validate_primary_date(as_of_date: str) -> None:
    if as_of_date in HISTORICAL_EXCLUDED_WINDOWS:
        raise HistoricalAsOfArtifactError(
            "blocked_excluded_window",
            "The date is consumed evidence or reserved for prospective U3.",
        )
    if as_of_date not in HISTORICAL_PRIMARY_WINDOWS:
        raise HistoricalAsOfArtifactError(
            "blocked_non_primary_window",
            "Phase 3.7.3 permits primary historical windows only.",
        )


def _validate_input_path(
    value: str | Path,
    *,
    role: str,
    suffix: str = ".csv",
) -> Path:
    path = Path(value)
    normalized = str(path).replace("\\", "/")
    if FORBIDDEN_INPUT_PATH_PATTERN.search(normalized):
        raise HistoricalAsOfArtifactError(
            "blocked_forbidden_input_artifact",
            f"{role} path names a validation or outcome artifact.",
            details={"path": str(path), "role": role},
        )
    if not path.exists():
        raise HistoricalAsOfArtifactError(
            "blocked_missing_as_of_artifact",
            f"Required {role} artifact is missing.",
            details={"path": str(path), "role": role},
        )
    if path.suffix.lower() != suffix:
        raise HistoricalAsOfArtifactError(
            "blocked_invalid_as_of_artifact",
            f"{role} artifact must use {suffix}.",
            details={"path": str(path), "role": role},
        )
    return path


def _load_factors(path: Path, *, as_of_date: str) -> pd.DataFrame:
    try:
        header = list(pd.read_csv(path, nrows=0).columns)
    except (OSError, pd.errors.ParserError, UnicodeError) as exc:
        raise HistoricalAsOfArtifactError(
            "blocked_invalid_factors",
            "Factors header cannot be read.",
            details={"path": str(path)},
        ) from exc
    forbidden = find_outcome_columns(header)
    if forbidden:
        raise HistoricalAsOfArtifactError(
            "blocked_unsafe_factors",
            "Factors artifact contains outcome or label columns.",
            details={"forbidden_columns": forbidden},
        )
    missing = sorted({"symbol", "as_of_date"} - set(header))
    if missing:
        raise HistoricalAsOfArtifactError(
            "blocked_missing_factor_columns",
            "Factors artifact is missing identity columns.",
            details={"missing_columns": missing},
        )
    try:
        frame = pd.read_csv(path, dtype={"symbol": str})
    except (OSError, pd.errors.ParserError, UnicodeError) as exc:
        raise HistoricalAsOfArtifactError(
            "blocked_invalid_factors",
            "Factors artifact cannot be read.",
        ) from exc
    if len(frame) < MINIMUM_VALID_UNIVERSE_ROWS:
        raise HistoricalAsOfArtifactError(
            "blocked_insufficient_factor_universe",
            "Factors artifact is below the 100-row gate.",
            details={"row_count": int(len(frame))},
        )
    dates = frame["as_of_date"].astype(str).str.strip()
    if not dates.eq(as_of_date).all():
        raise HistoricalAsOfArtifactError(
            "blocked_factor_as_of_mismatch",
            "Factors artifact contains a mixed or wrong as-of date.",
        )
    frame["symbol"] = frame["symbol"].astype(str).str.strip()
    duplicates = sorted(
        frame.loc[frame["symbol"].duplicated(), "symbol"].unique()
    )
    if frame["symbol"].eq("").any() or duplicates:
        raise HistoricalAsOfArtifactError(
            "blocked_invalid_factor_symbols",
            "Factors require one non-empty row per symbol.",
            details={"duplicate_symbols": duplicates},
        )
    return frame.reset_index(drop=True)


def _load_multi_list(path: Path, *, as_of_date: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise HistoricalAsOfArtifactError(
            "blocked_invalid_multi_list",
            "Multi-list artifact cannot be read.",
        ) from exc
    if not isinstance(payload, dict) or not isinstance(
        payload.get("lists"),
        list,
    ):
        raise HistoricalAsOfArtifactError(
            "blocked_invalid_multi_list",
            "Multi-list artifact must contain a lists array.",
        )
    if str(payload.get("as_of_date", "")).strip() != as_of_date:
        raise HistoricalAsOfArtifactError(
            "blocked_multi_list_as_of_mismatch",
            "Multi-list artifact as_of_date does not match.",
        )
    return payload


def _project_membership(
    factors: pd.DataFrame,
    payload: dict[str, Any],
    *,
    as_of_date: str,
) -> tuple[pd.DataFrame, list[str]]:
    symbols = factors["symbol"].astype(str).tolist()
    symbol_set = set(symbols)
    rows: dict[str, dict[str, Any]] = {
        symbol: {
            "symbol": symbol,
            "as_of_date": as_of_date,
            **{field: False for field in LIST_FIELD_MAP.values()},
            "captured_positive_lists": "",
            "captured_risk_lists": "",
            "captured_list_names": "",
        }
        for symbol in symbols
    }
    captured_ids: dict[str, list[str]] = {symbol: [] for symbol in symbols}
    captured_names: dict[str, list[str]] = {symbol: [] for symbol in symbols}
    ignored: set[str] = set()
    seen_list_ids: set[str] = set()
    for list_payload in payload["lists"]:
        if not isinstance(list_payload, dict):
            raise HistoricalAsOfArtifactError(
                "blocked_invalid_multi_list",
                "Every lists entry must be an object.",
            )
        list_id = str(list_payload.get("list_id", "")).strip()
        if list_id not in LIST_FIELD_MAP:
            continue
        if list_id in seen_list_ids:
            raise HistoricalAsOfArtifactError(
                "blocked_duplicate_list_id",
                "Multi-list artifact contains a duplicate list_id.",
                details={"list_id": list_id},
            )
        seen_list_ids.add(list_id)
        if str(list_payload.get("as_of_date", "")).strip() != as_of_date:
            raise HistoricalAsOfArtifactError(
                "blocked_multi_list_as_of_mismatch",
                "A list entry contains the wrong as-of date.",
                details={"list_id": list_id},
            )
        list_name = str(list_payload.get("list_name", "")).strip()
        items = list_payload.get("items", [])
        if not isinstance(items, list):
            raise HistoricalAsOfArtifactError(
                "blocked_invalid_multi_list",
                "List items must be an array.",
                details={"list_id": list_id},
            )
        for item in items:
            if not isinstance(item, dict):
                raise HistoricalAsOfArtifactError(
                    "blocked_invalid_multi_list",
                    "Every list item must be an object.",
                )
            symbol = str(item.get("symbol", "")).strip()
            if not symbol:
                raise HistoricalAsOfArtifactError(
                    "blocked_invalid_list_symbol",
                    "List item contains an empty symbol.",
                )
            if symbol not in symbol_set:
                ignored.add(symbol)
                continue
            row = rows[symbol]
            row[LIST_FIELD_MAP[list_id]] = True
            captured_ids[symbol].append(list_id)
            if list_name:
                captured_names[symbol].append(list_name)
            _merge_safe_item_context(row, item)
    missing_required_lists = sorted(
        {"breakout_watch", "accumulation_watch"} - seen_list_ids
    )
    if missing_required_lists:
        raise HistoricalAsOfArtifactError(
            "blocked_missing_required_lists",
            "Multi-list artifact omits required H1-H5 source lists.",
            details={"missing_list_ids": missing_required_lists},
        )
    for symbol, row in rows.items():
        positive = [
            item for item in captured_ids[symbol] if item in POSITIVE_LIST_IDS
        ]
        risk = [
            item for item in captured_ids[symbol] if item not in POSITIVE_LIST_IDS
        ]
        row["captured_positive_lists"] = ";".join(positive)
        row["captured_risk_lists"] = ";".join(risk)
        row["captured_list_names"] = ";".join(captured_names[symbol])
    return pd.DataFrame([rows[symbol] for symbol in symbols]), sorted(ignored)


def _merge_safe_item_context(
    row: dict[str, Any],
    item: dict[str, Any],
) -> None:
    candidate_rank = _finite_number(item.get("rank"))
    current_rank = _finite_number(row.get("rank"))
    use_candidate = (
        current_rank is None
        or (
            candidate_rank is not None
            and candidate_rank < current_rank
        )
    )
    if not use_candidate:
        return
    for field in SAFE_ITEM_CONTEXT_FIELDS:
        value = item.get(field)
        if field == "rank":
            row[field] = candidate_rank
        elif value is not None:
            row[field] = value


def _forbidden_json_keys(value: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            keys.append(str(key))
            keys.extend(_forbidden_json_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.extend(_forbidden_json_keys(item))
    return find_outcome_columns(keys)


def _reject_unsafe_output(frame: pd.DataFrame, *, role: str) -> None:
    forbidden = find_outcome_columns(frame.columns)
    if forbidden:
        raise HistoricalAsOfArtifactError(
            "blocked_unsafe_projected_output",
            f"{role} contains an unsafe projected column.",
            details={"forbidden_columns": forbidden},
        )


def _finite_number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None
