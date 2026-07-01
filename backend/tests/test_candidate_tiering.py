from __future__ import annotations

from copy import deepcopy
import json
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.research.candidate_tiering import (
    CANDIDATE_TIERING_CONFIG,
    EXPECTED_TIER_MAPPING,
    build_candidate_tiering_display,
)


FORBIDDEN_WORDING = (
    "guaranteed gain",
    "stable profit",
    "must buy",
    "safe stock",
    "validated alpha",
    "production recommendation",
    "risk-free",
    "automatic exclusion",
    "confirmed short signal",
    "confirmed avoid signal",
)


class CandidateTieringTests(unittest.TestCase):
    def test_mapping_matches_phase_233_and_preserves_source_payloads(self) -> None:
        source_lists = _source_lists()
        original = deepcopy(source_lists)

        result = build_candidate_tiering_display(source_lists)

        self.assertTrue(result["ok"])
        self.assertTrue(result["research_only"])
        actual_mapping = tuple(
            (
                tier["tier_id"],
                tuple(tier["source_list_ids"]),
            )
            for tier in result["tiers"]
        )
        self.assertEqual(actual_mapping, EXPECTED_TIER_MAPPING)
        self.assertEqual(source_lists, original)
        for tier in result["tiers"]:
            for payload in tier["lists"]:
                source = original[payload["list_id"]]
                self.assertEqual(payload["items"], source["items"])
                self.assertEqual(
                    [item["rank"] for item in payload["items"]],
                    [item["rank"] for item in source["items"]],
                )

    def test_insufficient_data_is_separate_from_tiers(self) -> None:
        result = build_candidate_tiering_display(_source_lists())

        tiered_ids = {
            list_id
            for tier in result["tiers"]
            for list_id in tier["source_list_ids"]
        }
        self.assertNotIn("insufficient_data", tiered_ids)
        self.assertFalse(result["data_quality_state"]["tiered"])
        self.assertEqual(
            result["data_quality_state"]["list"]["list_id"],
            "insufficient_data",
        )

    def test_required_wording_is_present_and_forbidden_wording_is_absent(self) -> None:
        result = build_candidate_tiering_display(_source_lists())
        combined = json.dumps(result, ensure_ascii=False).lower()

        for wording in (
            "research-only tiering",
            "not investment advice",
            "not a buy recommendation",
            "no guaranteed return",
            "tier numbers indicate reading order only",
            "existing list logic is unchanged",
        ):
            self.assertIn(wording, combined)
        for wording in FORBIDDEN_WORDING:
            self.assertNotIn(wording, combined)

    def test_risk_tier_is_caution_only(self) -> None:
        result = build_candidate_tiering_display(_source_lists())
        risk_tier = result["tiers"][-1]
        combined = json.dumps(risk_tier, ensure_ascii=False).lower()

        self.assertEqual(risk_tier["tier_id"], "risk_warning")
        self.assertIn("manual risk review", combined)
        self.assertIn("does not change eligibility", combined)
        for wording in FORBIDDEN_WORDING:
            self.assertNotIn(wording, combined)

    def test_missing_or_incomplete_metadata_fails_closed(self) -> None:
        missing = build_candidate_tiering_display(_source_lists(), None)
        incomplete_config = deepcopy(CANDIDATE_TIERING_CONFIG)
        incomplete_config["tiers"].pop()
        incomplete = build_candidate_tiering_display(
            _source_lists(),
            incomplete_config,
        )

        for result in (missing, incomplete):
            self.assertFalse(result["ok"])
            self.assertFalse(result["available"])
            self.assertEqual(result["status"], "tier_metadata_unavailable")
            self.assertEqual(result["message"], "Tier metadata unavailable")
            self.assertEqual(result["tiers"], [])


def _source_lists() -> dict[str, dict[str, object]]:
    list_ids = [
        list_id
        for _, source_ids in EXPECTED_TIER_MAPPING
        for list_id in source_ids
    ] + ["insufficient_data"]
    return {
        list_id: {
            "ok": True,
            "list_id": list_id,
            "list_name": list_id,
            "item_count": 2,
            "items": [
                {"symbol": f"{list_id}.a", "rank": 1},
                {"symbol": f"{list_id}.b", "rank": 2},
            ],
        }
        for list_id in list_ids
    }


if __name__ == "__main__":
    unittest.main()
