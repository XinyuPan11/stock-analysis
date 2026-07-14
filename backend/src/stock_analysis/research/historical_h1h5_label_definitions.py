"""Machine-checkable Phase 3.12 historical H1-H5 label contract.

This module validates definitions and future label-source schemas only. It
does not read price caches, generate labels, access a provider, join cohorts,
or run the evaluator.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "historical-h1h5-label-definitions-v1"
VALIDATION_ID = "h1h5-historical-sealed-v1"
EVIDENCE_LEVEL = "historical_sealed_not_prospective"
BENCHMARK = "CSI300"
HORIZON_DAYS = 20
PRIMARY_WINDOWS: tuple[str, ...] = (
    "2026-01-30",
    "2026-03-31",
    "2026-04-30",
)
PROHIBITED_WINDOWS: frozenset[str] = frozenset(
    {
        "2024-01-31",
        "2024-04-30",
        "2024-07-31",
        "2024-10-31",
        "2024-02-29",
        "2024-05-31",
        "2024-08-30",
        "2024-11-29",
        "2025-02-28",
        "2025-05-30",
        "2025-08-29",
        "2025-11-28",
        "2026-09-30",
        "2026-12-31",
    }
)
REQUIRED_CONTINUOUS_METRICS: frozenset[str] = frozenset(
    {
        "as_of_close",
        "future_end_close",
        "future_return_20d",
        "benchmark_return_20d",
        "excess_return_20d",
        "max_future_close_20d",
        "min_future_close_20d",
        "max_upside_20d",
        "max_drawdown_20d",
        "valid_label",
        "missing_label_reason",
    }
)
EXPECTED_CONTINUOUS_FORMULAS: dict[str, str] = {
    "as_of_close": "symbol_adj_close_on_as_of_date",
    "future_end_close": (
        "symbol_adj_close_on_20th_CSI300_trade_date_after_as_of"
    ),
    "future_return_20d": "future_end_close_div_as_of_close_minus_1",
    "benchmark_return_20d": (
        "CSI300_end_adj_close_div_CSI300_as_of_adj_close_minus_1"
    ),
    "excess_return_20d": (
        "future_return_20d_minus_benchmark_return_20d"
    ),
    "max_future_close_20d": (
        "max_symbol_adj_close_across_20_future_calendar_dates"
    ),
    "min_future_close_20d": (
        "min_symbol_adj_close_across_20_future_calendar_dates"
    ),
    "max_upside_20d": (
        "max_future_close_20d_div_as_of_close_minus_1"
    ),
    "max_drawdown_20d": (
        "min_price_div_running_max_minus_1_over_as_of_plus_20_future_closes"
    ),
    "valid_label": (
        "all_identity_calendar_price_benchmark_and_schema_gates_pass"
    ),
    "missing_label_reason": (
        "first_failure_by_frozen_missing_reason_priority"
    ),
}
REQUIRED_BOOLEAN_LABELS: frozenset[str] = frozenset(
    {"winner", "loser", "severe_drawdown", "right_tail"}
)
REQUIRED_LABEL_SOURCE_COLUMNS: tuple[str, ...] = (
    "validation_id",
    "evidence_level",
    "as_of_date",
    "horizon_days",
    "benchmark",
    "symbol",
    "valid_label",
    "missing_label_reason",
    "as_of_close",
    "future_end_close",
    "future_return_20d",
    "benchmark_return_20d",
    "excess_return_20d",
    "max_future_close_20d",
    "min_future_close_20d",
    "max_upside_20d",
    "max_drawdown_20d",
    "winner",
    "loser",
    "severe_drawdown",
    "right_tail",
    "label_future_rows_used_count",
    "label_window_start_date",
    "label_window_end_date",
    "price_field",
)
FORBIDDEN_LABEL_SOURCE_COLUMNS: frozenset[str] = frozenset(
    {
        "cohort_id",
        "cohort_role",
        "cohort_member",
        "cohort_assignment",
        "annotation_status",
        "membership_reason",
        "rank",
        "list_id",
        "list_name",
        "list_membership",
        "captured_positive_lists",
        "captured_risk_lists",
        "recommendation",
        "recommendation_level",
        "provider",
        "provider_source",
        "builder_score",
        "builder_decision",
    }
)
DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[4]
    / "research"
    / "configs"
    / "historical_h1h5_label_definitions.v1.json"
)


class HistoricalH1H5LabelDefinitionError(ValueError):
    """Fail-closed definition or schema error."""

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


def load_historical_h1h5_label_definitions(
    path: str | Path = DEFAULT_CONFIG_PATH,
) -> dict[str, Any]:
    """Load and validate the non-output Phase 3.12 definition file."""

    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HistoricalH1H5LabelDefinitionError(
            "blocked_invalid_definition_config",
            "Label definition config is missing or invalid JSON.",
            details={"path": str(source)},
        ) from exc
    if not isinstance(payload, dict):
        raise HistoricalH1H5LabelDefinitionError(
            "blocked_invalid_definition_config",
            "Label definition config must be a JSON object.",
        )
    validate_historical_h1h5_label_definitions(payload)
    return payload


def validate_historical_h1h5_label_definitions(
    payload: Mapping[str, Any],
) -> None:
    """Validate frozen identity, formula parameters, schema, and guardrails."""

    expected_identity = {
        "schema_version": SCHEMA_VERSION,
        "validation_id": VALIDATION_ID,
        "evidence_level": EVIDENCE_LEVEL,
        "benchmark": BENCHMARK,
        "horizon_days": HORIZON_DAYS,
    }
    mismatches = {
        key: {"expected": expected, "actual": payload.get(key)}
        for key, expected in expected_identity.items()
        if payload.get(key) != expected
    }
    if mismatches:
        _fail(
            "blocked_definition_identity_mismatch",
            "Label definition identity does not match Phase 3.12.",
            mismatches=mismatches,
        )
    if tuple(payload.get("primary_windows", ())) != PRIMARY_WINDOWS:
        _fail(
            "blocked_definition_window_mismatch",
            "Primary windows do not match the historical sealed contract.",
        )
    if frozenset(payload.get("prohibited_windows", ())) != PROHIBITED_WINDOWS:
        _fail(
            "blocked_definition_window_mismatch",
            "Consumed, answer-key, or U3 exclusions are incomplete.",
        )

    price = _mapping(payload, "price_and_horizon")
    expected_price = {
        "price_field": "adj_close",
        "allow_close_fallback": False,
        "calendar_source": BENCHMARK,
        "as_of_date_required": True,
        "future_dates_rule": (
            "first_20_CSI300_trade_dates_strictly_after_as_of_date"
        ),
        "symbol_requires_all_future_dates": True,
        "benchmark_requires_all_future_dates": True,
        "positive_finite_prices_required": True,
    }
    _require_exact_values(
        price,
        expected_price,
        status="blocked_price_or_horizon_definition_mismatch",
    )

    continuous = _mapping(payload, "continuous_metrics")
    if set(continuous) != REQUIRED_CONTINUOUS_METRICS:
        _fail(
            "blocked_continuous_metric_definition_mismatch",
            "Continuous metric definitions must match the frozen set exactly.",
            missing=sorted(REQUIRED_CONTINUOUS_METRICS - set(continuous)),
            unexpected=sorted(set(continuous) - REQUIRED_CONTINUOUS_METRICS),
        )
    for name, formula_id in EXPECTED_CONTINUOUS_FORMULAS.items():
        definition = continuous.get(name)
        if (
            not isinstance(definition, Mapping)
            or definition != {"formula_id": formula_id}
        ):
            _fail(
                "blocked_continuous_metric_definition_mismatch",
                f"Continuous metric {name} differs from its frozen formula.",
            )

    booleans = _mapping(payload, "boolean_labels")
    if set(booleans) != REQUIRED_BOOLEAN_LABELS:
        _fail(
            "blocked_boolean_label_definition_mismatch",
            "Boolean label definitions must match the frozen set exactly.",
        )
    _validate_boolean_definitions(booleans)

    schema = _mapping(payload, "label_source_schema")
    columns = tuple(schema.get("required_columns", ()))
    if columns != REQUIRED_LABEL_SOURCE_COLUMNS:
        _fail(
            "blocked_label_source_schema_mismatch",
            "Label-source columns do not match the frozen ordered schema.",
        )
    if frozenset(schema.get("forbidden_columns", ())) != (
        FORBIDDEN_LABEL_SOURCE_COLUMNS
    ):
        _fail(
            "blocked_label_source_schema_mismatch",
            "Forbidden label-source columns do not match the frozen set.",
        )
    if schema.get("exact_columns_only") is not True:
        _fail(
            "blocked_label_source_schema_mismatch",
            "Label-source schema must reject all undeclared columns.",
        )
    validate_label_source_schema(columns, as_of_date=PRIMARY_WINDOWS[0])

    guardrails = _mapping(payload, "guardrails")
    expected_guardrails = {
        "research_only": True,
        "local_cache_only": True,
        "provider_access": False,
        "validation_prediction_inputs": False,
        "labels_joined_by_builder": False,
        "cohort_membership_mutation": False,
        "production_change": False,
        "generate_labels_in_phase3_12": False,
        "run_evaluator_in_phase3_12": False,
        "write_evaluation_outputs_in_phase3_12": False,
    }
    _require_exact_values(
        guardrails,
        expected_guardrails,
        status="blocked_unsafe_definition_guardrail",
    )


def validate_label_source_schema(
    columns: Iterable[str],
    *,
    as_of_date: str,
) -> None:
    """Validate only a proposed future label-source column set and date."""

    validate_execution_date(as_of_date)
    normalized = tuple(str(column).strip() for column in columns)
    if len(normalized) != len(set(normalized)):
        _fail(
            "blocked_duplicate_label_source_columns",
            "Label-source columns must be unique.",
        )
    forbidden = sorted(set(normalized) & FORBIDDEN_LABEL_SOURCE_COLUMNS)
    if forbidden:
        _fail(
            "blocked_label_source_membership_fields",
            "Label source contains cohort, list, ranking, recommendation, "
            "provider, or mutable builder-side fields.",
            forbidden_fields=forbidden,
        )
    missing = sorted(set(REQUIRED_LABEL_SOURCE_COLUMNS) - set(normalized))
    unexpected = sorted(set(normalized) - set(REQUIRED_LABEL_SOURCE_COLUMNS))
    if missing or unexpected or normalized != REQUIRED_LABEL_SOURCE_COLUMNS:
        _fail(
            "blocked_label_source_schema_mismatch",
            "Label source must use the exact frozen ordered schema.",
            missing_fields=missing,
            unexpected_fields=unexpected,
        )


def validate_execution_date(as_of_date: str) -> None:
    """Allow only the three Phase 3.9 frozen primary dates."""

    value = str(as_of_date).strip()
    if value in PROHIBITED_WINDOWS:
        _fail(
            "blocked_prohibited_window",
            "Answer-key, consumed U1/U2, and prospective U3 dates are barred.",
            as_of_date=value,
        )
    if value not in PRIMARY_WINDOWS:
        _fail(
            "blocked_non_primary_window",
            "Only Phase 3.9 frozen primary windows are allowed.",
            as_of_date=value,
        )


def _validate_boolean_definitions(
    definitions: Mapping[str, Any],
) -> None:
    winner = _mapping(definitions, "winner")
    loser = _mapping(definitions, "loser")
    shared = {
        "fields": ["future_return_20d", "excess_return_20d"],
        "tail_fraction": 0.1,
        "minimum_tail_count": 10,
        "maximum_tail_share": 0.5,
        "count_rounding": "ceil",
        "valid_labels_only": True,
    }
    _require_exact_values(
        winner,
        {
            **shared,
            "method": "union_of_deterministic_top_tails",
            "sort": "metric_desc_symbol_asc",
        },
        status="blocked_boolean_label_definition_mismatch",
    )
    _require_exact_values(
        loser,
        {
            **shared,
            "method": "union_of_deterministic_bottom_tails",
            "sort": "metric_asc_symbol_asc",
        },
        status="blocked_boolean_label_definition_mismatch",
    )
    _require_exact_values(
        _mapping(definitions, "severe_drawdown"),
        {
            "method": "threshold_inclusive",
            "field": "max_drawdown_20d",
            "operator": "<=",
            "threshold": -0.2,
            "valid_labels_only": True,
        },
        status="blocked_boolean_label_definition_mismatch",
    )
    _require_exact_values(
        _mapping(definitions, "right_tail"),
        {
            "method": "quantile_threshold_inclusive",
            "field": "future_return_20d",
            "quantile": 0.8,
            "interpolation": "linear",
            "operator": ">=",
            "valid_labels_only": True,
        },
        status="blocked_boolean_label_definition_mismatch",
    )


def _mapping(parent: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = parent.get(key)
    if not isinstance(value, Mapping):
        _fail(
            "blocked_invalid_definition_config",
            f"Definition section {key} must be an object.",
        )
    return value


def _require_exact_values(
    actual: Mapping[str, Any],
    expected: Mapping[str, Any],
    *,
    status: str,
) -> None:
    mismatches = {
        key: {"expected": value, "actual": actual.get(key)}
        for key, value in expected.items()
        if actual.get(key) != value
    }
    unexpected = sorted(set(actual) - set(expected))
    if mismatches or unexpected:
        _fail(
            status,
            "Definition values differ from the frozen Phase 3.12 contract.",
            mismatches=mismatches,
            unexpected_fields=unexpected,
        )


def _fail(status: str, message: str, **details: Any) -> None:
    raise HistoricalH1H5LabelDefinitionError(
        status,
        message,
        details=details,
    )
