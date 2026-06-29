from __future__ import annotations

from typing import Any


KNOWN_BIAS_LIMITATIONS = (
    "historical_universe_membership_not_versioned",
    "historical_listing_delisting_status_not_versioned",
    "historical_st_status_not_versioned",
    "historical_suspension_status_not_fully_versioned",
    "controlled_validation_not_final_production_grade_historical_simulation",
)


def validation_bias_metadata() -> dict[str, Any]:
    """Return shared point-in-time protection and known-bias metadata."""

    return {
        "price_point_in_time_guard_applied": True,
        "feature_input_point_in_time_status": "guarded",
        "future_label_window_status": "explicit_future_only",
        "universe_point_in_time_status": "current_snapshot_limited",
        "listing_status_point_in_time_status": "current_snapshot_limited",
        "st_status_point_in_time_status": "current_snapshot_limited",
        "suspension_status_point_in_time_status": "current_snapshot_limited",
        "known_bias_limitations": list(KNOWN_BIAS_LIMITATIONS),
    }
