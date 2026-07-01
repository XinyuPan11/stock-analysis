from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any


EXPECTED_TIER_MAPPING: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("defensive_observation", ("long_term_stable",)),
    ("core_research_candidates", ("high_confidence_candidates",)),
    ("trend_observation", ("trend_leaders",)),
    (
        "active_opportunity_observation",
        ("breakout_watch", "accumulation_watch", "rebound_watch"),
    ),
    ("risk_warning", ("high_risk_active",)),
)

TIER_SOURCE_LIST_IDS: tuple[str, ...] = tuple(
    list_id
    for _, list_ids in EXPECTED_TIER_MAPPING
    for list_id in list_ids
)

CANDIDATE_TIERING_CONFIG: dict[str, Any] = {
    "metadata_version": "phase2.34.v1",
    "title": "Research-only tiering",
    "reading_order_note": "Tier numbers indicate reading order only.",
    "unchanged_logic_note": "Existing list logic is unchanged.",
    "disclaimer": (
        "Research-only tiering. Not investment advice. "
        "Not a buy recommendation. No guaranteed return."
    ),
    "tiers": [
        {
            "tier_order": 1,
            "tier_id": "defensive_observation",
            "tier_name": "Defensive Observation",
            "tier_badge": "Defensive observation",
            "tier_description": (
                "Historical group-level drawdown context for the unchanged "
                "long_term_stable list."
            ),
            "evidence_note": (
                "U2 controlled windows showed shallower drawdown than three "
                "active lists in 4/4 windows."
            ),
            "caveat": (
                "Excess return was unstable and negative in 3/4 U2 windows."
            ),
            "forbidden_action_note": (
                "This context does not establish safety or expected return "
                "for an individual member."
            ),
            "source_list_ids": ["long_term_stable"],
            "research_only": True,
        },
        {
            "tier_order": 2,
            "tier_id": "core_research_candidates",
            "tier_name": "Core Research Candidates",
            "tier_badge": "Core research",
            "tier_description": (
                "The unchanged selective research baseline."
            ),
            "evidence_note": (
                "U1 and U2 did not establish stable cleanliness, coverage, "
                "and excess return together."
            ),
            "caveat": (
                "Cross-window evidence remains mixed and requires "
                "counter-evidence to stay visible."
            ),
            "forbidden_action_note": (
                "Core means central to research, not approved for action."
            ),
            "source_list_ids": ["high_confidence_candidates"],
            "research_only": True,
        },
        {
            "tier_order": 3,
            "tier_id": "trend_observation",
            "tier_name": "Trend Observation",
            "tier_badge": "Trend observation",
            "tier_description": (
                "Trend, momentum, and relative-strength context from the "
                "unchanged trend_leaders list."
            ),
            "evidence_note": (
                "U2 did not support trend_leaders as a stable positive baseline."
            ),
            "caveat": (
                "Trend evidence was regime-dependent, and crowding was not "
                "directly established as the cause."
            ),
            "forbidden_action_note": (
                "Trend context is descriptive and does not establish future "
                "outperformance."
            ),
            "source_list_ids": ["trend_leaders"],
            "research_only": True,
        },
        {
            "tier_order": 4,
            "tier_id": "active_opportunity_observation",
            "tier_name": "Active Opportunity Observation",
            "tier_badge": "Active observation",
            "tier_description": (
                "Higher-variance discovery views kept as three separate "
                "unchanged source lists."
            ),
            "evidence_note": (
                "Breakout, accumulation, and rebound evidence remained mixed, "
                "high-variance, or sample-limited."
            ),
            "caveat": (
                "Opportunity discovery must retain downside, failure, and "
                "sample-size warnings."
            ),
            "forbidden_action_note": (
                "This tier does not raise confidence or combine members into "
                "a new list."
            ),
            "source_list_ids": [
                "breakout_watch",
                "accumulation_watch",
                "rebound_watch",
            ],
            "research_only": True,
        },
        {
            "tier_order": 5,
            "tier_id": "risk_warning",
            "tier_name": "Risk Warning",
            "tier_badge": "Risk warning",
            "tier_description": (
                "A caution and manual risk-review layer for the unchanged "
                "high_risk_active list."
            ),
            "evidence_note": (
                "U2 evidence was directionally mixed and below the "
                "preregistered sample gate."
            ),
            "caveat": (
                "The stable-negative interpretation was not confirmed."
            ),
            "forbidden_action_note": (
                "Membership only prompts manual risk review; it does not "
                "change eligibility or produce an action signal."
            ),
            "source_list_ids": ["high_risk_active"],
            "research_only": True,
        },
    ],
}

_REQUIRED_TIER_FIELDS = (
    "tier_order",
    "tier_id",
    "tier_name",
    "tier_badge",
    "tier_description",
    "evidence_note",
    "caveat",
    "forbidden_action_note",
    "source_list_ids",
    "research_only",
)


def build_candidate_tiering_display(
    source_lists: Mapping[str, Mapping[str, Any]],
    config: Mapping[str, Any] | None = CANDIDATE_TIERING_CONFIG,
) -> dict[str, Any]:
    """Group existing list payloads without changing their contents or order."""
    if not _valid_config(config):
        return {
            "ok": False,
            "available": False,
            "research_only": True,
            "status": "tier_metadata_unavailable",
            "title": "Research-only tiering",
            "message": "Tier metadata unavailable",
            "tiers": [],
        }

    assert config is not None
    tiers: list[dict[str, Any]] = []
    for tier_config in config["tiers"]:
        list_ids = list(tier_config["source_list_ids"])
        source_payloads: list[dict[str, Any]] = []
        missing_source_list_ids: list[str] = []
        for list_id in list_ids:
            payload = source_lists.get(str(list_id))
            if isinstance(payload, Mapping) and payload.get("ok"):
                source_payloads.append(deepcopy(dict(payload)))
            else:
                missing_source_list_ids.append(str(list_id))
        tiers.append(
            {
                **deepcopy(dict(tier_config)),
                "lists": source_payloads,
                "missing_source_list_ids": missing_source_list_ids,
            }
        )

    insufficient_payload = source_lists.get("insufficient_data")
    data_quality_state = None
    if isinstance(insufficient_payload, Mapping) and insufficient_payload.get("ok"):
        data_quality_state = {
            "tiered": False,
            "status_name": "Data insufficient",
            "list": deepcopy(dict(insufficient_payload)),
        }

    return {
        "ok": True,
        "available": True,
        "research_only": True,
        "status": "research_only_candidate_tiering",
        "metadata_version": str(config["metadata_version"]),
        "title": str(config["title"]),
        "reading_order_note": str(config["reading_order_note"]),
        "unchanged_logic_note": str(config["unchanged_logic_note"]),
        "disclaimer": str(config["disclaimer"]),
        "tiers": tiers,
        "data_quality_state": data_quality_state,
    }


def _valid_config(config: Mapping[str, Any] | None) -> bool:
    if not isinstance(config, Mapping):
        return False
    for field in (
        "metadata_version",
        "title",
        "reading_order_note",
        "unchanged_logic_note",
        "disclaimer",
    ):
        if not str(config.get(field, "")).strip():
            return False
    tiers = config.get("tiers")
    if not isinstance(tiers, Sequence) or isinstance(tiers, (str, bytes)):
        return False
    if len(tiers) != len(EXPECTED_TIER_MAPPING):
        return False

    actual_mapping: list[tuple[str, tuple[str, ...]]] = []
    for expected_order, tier in enumerate(tiers, start=1):
        if not isinstance(tier, Mapping):
            return False
        if any(field not in tier for field in _REQUIRED_TIER_FIELDS):
            return False
        if tier.get("research_only") is not True:
            return False
        try:
            if int(tier["tier_order"]) != expected_order:
                return False
        except (TypeError, ValueError):
            return False
        list_ids = tier.get("source_list_ids")
        if not isinstance(list_ids, list) or not list_ids:
            return False
        if "insufficient_data" in list_ids:
            return False
        for text_field in (
            "tier_id",
            "tier_name",
            "tier_badge",
            "tier_description",
            "evidence_note",
            "caveat",
            "forbidden_action_note",
        ):
            if not str(tier.get(text_field, "")).strip():
                return False
        actual_mapping.append(
            (
                str(tier["tier_id"]),
                tuple(str(list_id) for list_id in list_ids),
            )
        )
    return tuple(actual_mapping) == EXPECTED_TIER_MAPPING
