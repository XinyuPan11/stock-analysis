from __future__ import annotations

import math
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.research.opportunity_cohorts import (
    build_research_opportunity_cohorts,
    load_opportunity_cohort_config,
    validate_opportunity_cohort_config,
)


AS_OF_DATE = "2024-10-31"
CONFIG_PATH = (
    ROOT.parent
    / "research"
    / "configs"
    / "opportunity_cohorts.phase3_1_smoke.json"
)


def test_phase3_1_smoke_config_passes_execution_schema() -> None:
    config = load_opportunity_cohort_config(CONFIG_PATH)
    validated = validate_opportunity_cohort_config(
        config,
        as_of_date=AS_OF_DATE,
        mode="execution",
    )
    parameters = [
        value
        for cohort in validated["cohorts"].values()
        for value in cohort["parameters"].values()
    ]

    assert validated["created_for_phase"] == "Phase 3.1"
    assert validated["research_only"] is True
    assert validated["labels_joined"] is False
    assert validated["production_change"] is False
    assert validated["effectiveness_claim"] is False
    assert validated["production_eligible"] is False
    assert validated["parameter_source"] == (
        "engineering_smoke_not_u1_u2_tuned"
    )
    assert "not_validated" in validated["parameter_status"]
    assert len(parameters) == 18
    assert all(
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
        for value in parameters
    )
    assert not _forbidden_governance_keys(validated)


def test_phase3_1_smoke_builder_output_is_label_free_and_research_only() -> None:
    config = load_opportunity_cohort_config(CONFIG_PATH)
    result = build_research_opportunity_cohorts(
        _feature_only_snapshot(),
        config,
        as_of_date=AS_OF_DATE,
        source_snapshot_path="research/inputs/synthetic_feature_only.csv",
        config_path=CONFIG_PATH,
    )

    metadata = result.report["metadata"]
    assert metadata["research_only"] is True
    assert metadata["provider_access"] is False
    assert metadata["labels_joined"] is False
    assert metadata["production_change"] is False
    assert metadata["config_version"] == "phase3.1-smoke-v1"
    assert not {
        "future_return",
        "future_excess_return",
        "benchmark_return",
        "realized_return",
        "winner",
        "loser",
        "label",
        "outcome",
    }.intersection({str(column).lower() for column in result.frame.columns})


def _forbidden_governance_keys(value: object) -> list[str]:
    forbidden: list[str] = []
    blocked_tokens = (
        "tuned_from_u1",
        "tuned_from_u2",
        "tuned_from_answer_key",
        "optimized",
        "calibrated",
        "fitted",
        "default",
    )

    def visit(item: object, path: str) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                normalized = str(key).strip().lower()
                child_path = f"{path}.{key}" if path else str(key)
                if any(token in normalized for token in blocked_tokens):
                    forbidden.append(child_path)
                visit(child, child_path)
        elif isinstance(item, list):
            for index, child in enumerate(item):
                visit(child, f"{path}[{index}]")

    visit(value, "")
    return forbidden


def _feature_only_snapshot() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "as_of_date": AS_OF_DATE,
                "symbol": "000001",
                "rank": 1,
                "latest_input_date": AS_OF_DATE,
                "max_raw_cache_date": "2026-06-30",
                "future_rows_excluded_count": 1,
                "leakage_guard_applied": True,
                "pre_5d_return": 0.02,
                "pre_20d_return": 0.06,
                "pre_60d_return": 0.08,
                "technical_volatility_20d": 0.16,
                "drawdown_60d": -0.12,
                "amount_change_20d": 0.31,
                "volume_change_20d": 0.25,
                "distance_to_60d_high": -0.04,
                "distance_to_60d_low": 0.30,
                "recent_acceleration_proxy": 0.04,
                "high_position_crowding_proxy": 0.72,
                "is_breakout_watch": True,
                "is_accumulation_watch": False,
            }
        ]
    )
