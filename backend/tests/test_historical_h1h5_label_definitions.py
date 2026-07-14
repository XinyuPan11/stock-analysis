from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.research.historical_h1h5_label_definitions import (
    FORBIDDEN_LABEL_SOURCE_COLUMNS,
    PRIMARY_WINDOWS,
    REQUIRED_BOOLEAN_LABELS,
    REQUIRED_CONTINUOUS_METRICS,
    REQUIRED_LABEL_SOURCE_COLUMNS,
    HistoricalH1H5LabelDefinitionError,
    load_historical_h1h5_label_definitions,
    validate_execution_date,
    validate_historical_h1h5_label_definitions,
    validate_label_source_schema,
)


CONFIG = (
    ROOT.parent
    / "research"
    / "configs"
    / "historical_h1h5_label_definitions.v1.json"
)


def test_label_definition_config_parses_and_matches_frozen_identity() -> None:
    config = load_historical_h1h5_label_definitions(CONFIG)

    assert config["validation_id"] == "h1h5-historical-sealed-v1"
    assert config["primary_windows"] == list(PRIMARY_WINDOWS)
    assert config["price_and_horizon"]["price_field"] == "adj_close"
    assert config["price_and_horizon"]["allow_close_fallback"] is False


def test_all_continuous_metrics_and_boolean_labels_are_defined() -> None:
    config = load_historical_h1h5_label_definitions(CONFIG)

    assert set(config["continuous_metrics"]) == REQUIRED_CONTINUOUS_METRICS
    assert set(config["boolean_labels"]) == REQUIRED_BOOLEAN_LABELS


def test_boolean_thresholds_and_symmetric_winner_loser_tails_are_frozen() -> None:
    config = load_historical_h1h5_label_definitions(CONFIG)
    winner = config["boolean_labels"]["winner"]
    loser = config["boolean_labels"]["loser"]

    assert winner["tail_fraction"] == loser["tail_fraction"] == 0.1
    assert winner["minimum_tail_count"] == loser["minimum_tail_count"] == 10
    assert config["boolean_labels"]["right_tail"]["quantile"] == 0.8
    assert config["boolean_labels"]["severe_drawdown"]["threshold"] == -0.2


def test_config_drift_fails_closed() -> None:
    config = load_historical_h1h5_label_definitions(CONFIG)
    changed = copy.deepcopy(config)
    changed["boolean_labels"]["winner"]["tail_fraction"] = 0.11

    with pytest.raises(
        HistoricalH1H5LabelDefinitionError,
        match="frozen Phase 3.12 contract",
    ):
        validate_historical_h1h5_label_definitions(changed)


def test_continuous_formula_drift_fails_closed() -> None:
    config = load_historical_h1h5_label_definitions(CONFIG)
    changed = copy.deepcopy(config)
    changed["continuous_metrics"]["future_return_20d"][
        "formula_id"
    ] = "different_formula"

    with pytest.raises(
        HistoricalH1H5LabelDefinitionError,
        match="differs from its frozen formula",
    ):
        validate_historical_h1h5_label_definitions(changed)


def test_exact_future_label_source_schema_is_accepted() -> None:
    validate_label_source_schema(
        REQUIRED_LABEL_SOURCE_COLUMNS,
        as_of_date=PRIMARY_WINDOWS[0],
    )


@pytest.mark.parametrize("field", sorted(FORBIDDEN_LABEL_SOURCE_COLUMNS))
def test_forbidden_membership_and_mutable_fields_are_rejected(
    field: str,
) -> None:
    columns = [*REQUIRED_LABEL_SOURCE_COLUMNS, field]

    with pytest.raises(
        HistoricalH1H5LabelDefinitionError,
        match="cohort, list, ranking",
    ):
        validate_label_source_schema(columns, as_of_date=PRIMARY_WINDOWS[0])


@pytest.mark.parametrize(
    "as_of_date",
    ["2026-09-30", "2026-12-31"],
)
def test_u3_dates_are_rejected(as_of_date: str) -> None:
    with pytest.raises(
        HistoricalH1H5LabelDefinitionError,
        match="prospective U3",
    ):
        validate_execution_date(as_of_date)


@pytest.mark.parametrize(
    "as_of_date",
    [
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
    ],
)
def test_answer_key_and_consumed_u1_u2_dates_are_rejected(
    as_of_date: str,
) -> None:
    with pytest.raises(
        HistoricalH1H5LabelDefinitionError,
        match="Answer-key",
    ):
        validate_execution_date(as_of_date)


def test_provider_access_cannot_be_enabled() -> None:
    config = load_historical_h1h5_label_definitions(CONFIG)
    changed = copy.deepcopy(config)
    changed["guardrails"]["provider_access"] = True

    with pytest.raises(
        HistoricalH1H5LabelDefinitionError,
        match="frozen Phase 3.12 contract",
    ):
        validate_historical_h1h5_label_definitions(changed)
