from __future__ import annotations

from collections.abc import Mapping
from typing import Any


DEFENSIVE_POSITIONING_CONFIG: dict[str, Any] = {
    "list_id": "long_term_stable",
    "title": "Research-only defensive observation",
    "badge": "Defensive observation",
    "evidence_note": (
        "U2 controlled windows showed shallower drawdown than active lists "
        "in 4/4 windows."
    ),
    "caveat": (
        "Excess return was unstable and negative in 3/4 U2 windows."
    ),
    "disclaimer": (
        "Research-only. Not investment advice. Not a buy recommendation. "
        "No guaranteed return."
    ),
    "data_limitation": (
        "Controlled validation remains limited and uses current-snapshot "
        "universe, listing, ST, and suspension-status constraints."
    ),
    "why_included": (
        "Membership comes from the unchanged long_term_stable list for the "
        "selected as-of date. This presentation does not change eligibility, "
        "score, rank, or membership."
    ),
    "why_not_a_recommendation": (
        "The evidence is group-level and historical. It does not establish "
        "lower risk or expected return for an individual member."
    ),
    "evidence": {
        "panel": "U2 controlled 20D windows",
        "window_count": 4,
        "shallower_drawdown_window_count": 4,
        "negative_excess_window_count": 3,
        "comparison_list_ids": [
            "trend_leaders",
            "breakout_watch",
            "accumulation_watch",
        ],
    },
}

_REQUIRED_TEXT_FIELDS = (
    "title",
    "badge",
    "evidence_note",
    "caveat",
    "disclaimer",
    "data_limitation",
    "why_included",
    "why_not_a_recommendation",
)

_REQUIRED_EVIDENCE_FIELDS = (
    "panel",
    "window_count",
    "shallower_drawdown_window_count",
    "negative_excess_window_count",
    "comparison_list_ids",
)


def build_defensive_positioning_display(
    list_id: str,
    config: Mapping[str, Any] | None = DEFENSIVE_POSITIONING_CONFIG,
) -> dict[str, Any] | None:
    """Build presentation-only metadata for the unchanged defensive list."""
    if list_id != "long_term_stable":
        return None

    if not _has_required_evidence(config):
        return {
            "available": False,
            "research_only": True,
            "claim_supported": False,
            "status": "defensive_evidence_unavailable",
            "title": "Research-only defensive observation",
            "badge": None,
            "message": "Defensive evidence unavailable.",
        }

    assert config is not None
    evidence = config["evidence"]
    return {
        "available": True,
        "research_only": True,
        "claim_supported": True,
        "status": "research_only_defensive_observation",
        "list_id": "long_term_stable",
        "title": str(config["title"]),
        "badge": str(config["badge"]),
        "evidence_note": str(config["evidence_note"]),
        "caveat": str(config["caveat"]),
        "disclaimer": str(config["disclaimer"]),
        "data_limitation": str(config["data_limitation"]),
        "why_included": str(config["why_included"]),
        "why_not_a_recommendation": str(config["why_not_a_recommendation"]),
        "evidence": {
            "panel": str(evidence["panel"]),
            "window_count": int(evidence["window_count"]),
            "shallower_drawdown_window_count": int(
                evidence["shallower_drawdown_window_count"]
            ),
            "negative_excess_window_count": int(
                evidence["negative_excess_window_count"]
            ),
            "comparison_list_ids": [
                str(item) for item in evidence["comparison_list_ids"]
            ],
        },
    }


def _has_required_evidence(config: Mapping[str, Any] | None) -> bool:
    if not isinstance(config, Mapping):
        return False
    if config.get("list_id") != "long_term_stable":
        return False
    if any(not str(config.get(field, "")).strip() for field in _REQUIRED_TEXT_FIELDS):
        return False
    evidence = config.get("evidence")
    if not isinstance(evidence, Mapping):
        return False
    if any(field not in evidence for field in _REQUIRED_EVIDENCE_FIELDS):
        return False
    comparison_ids = evidence.get("comparison_list_ids")
    if not isinstance(comparison_ids, list) or not comparison_ids:
        return False
    try:
        window_count = int(evidence["window_count"])
        shallower_count = int(evidence["shallower_drawdown_window_count"])
        negative_excess_count = int(evidence["negative_excess_window_count"])
    except (TypeError, ValueError):
        return False
    return (
        window_count > 0
        and 0 <= shallower_count <= window_count
        and 0 <= negative_excess_count <= window_count
    )
