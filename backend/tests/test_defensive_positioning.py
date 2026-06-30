from __future__ import annotations

from copy import deepcopy
import json
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.research.defensive_positioning import (
    DEFENSIVE_POSITIONING_CONFIG,
    build_defensive_positioning_display,
)


FORBIDDEN_WORDING = (
    "guaranteed gain",
    "safe stock",
    "stable profit",
    "must buy",
    "validated alpha",
    "risk-free",
)


class DefensivePositioningTests(unittest.TestCase):
    def test_builds_research_only_display_with_required_caveats(self) -> None:
        display = build_defensive_positioning_display("long_term_stable")

        self.assertIsNotNone(display)
        assert display is not None
        self.assertTrue(display["available"])
        self.assertTrue(display["research_only"])
        self.assertEqual(display["title"], "Research-only defensive observation")
        self.assertEqual(display["badge"], "Defensive observation")
        self.assertIn("shallower drawdown", display["evidence_note"])
        self.assertIn("negative in 3/4 U2 windows", display["caveat"])
        self.assertIn("Not investment advice", display["disclaimer"])
        self.assertIn("Not a buy recommendation", display["disclaimer"])
        self.assertIn("No guaranteed return", display["disclaimer"])
        combined = json.dumps(display, ensure_ascii=False).lower()
        for wording in FORBIDDEN_WORDING:
            self.assertNotIn(wording, combined)

    def test_non_defensive_list_has_no_display_overlay(self) -> None:
        self.assertIsNone(
            build_defensive_positioning_display("trend_leaders")
        )

    def test_missing_config_fails_closed_without_badge(self) -> None:
        display = build_defensive_positioning_display(
            "long_term_stable",
            None,
        )

        self.assertIsNotNone(display)
        assert display is not None
        self.assertFalse(display["available"])
        self.assertFalse(display["claim_supported"])
        self.assertEqual(display["status"], "defensive_evidence_unavailable")
        self.assertIsNone(display["badge"])
        self.assertEqual(display["message"], "Defensive evidence unavailable.")

    def test_incomplete_evidence_fails_closed(self) -> None:
        config = deepcopy(DEFENSIVE_POSITIONING_CONFIG)
        del config["evidence"]["negative_excess_window_count"]

        display = build_defensive_positioning_display(
            "long_term_stable",
            config,
        )

        self.assertIsNotNone(display)
        assert display is not None
        self.assertFalse(display["available"])
        self.assertFalse(display["claim_supported"])


if __name__ == "__main__":
    unittest.main()
