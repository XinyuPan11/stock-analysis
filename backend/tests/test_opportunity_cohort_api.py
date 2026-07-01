from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

from fastapi.testclient import TestClient


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.api.app import create_app


AS_OF_DATE = "2024-10-31"
COHORT_IDS = [
    "low_position_revaluation_watch",
    "trend_acceleration_with_crowding_guard",
    "right_tail_opportunity_watch",
    "high_position_crowding_risk",
    "false_breakout_risk",
]


class OpportunityCohortApiTests(unittest.TestCase):
    def test_missing_output_returns_unavailable_with_all_empty_groups(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/research/opportunity-cohorts")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertFalse(payload["available"])
        self.assertEqual(payload["status"], "unavailable")
        self.assertEqual(
            [group["cohort_id"] for group in payload["groups"]],
            COHORT_IDS,
        )
        self.assertTrue(all(group["empty"] for group in payload["groups"]))

    def test_safe_output_returns_h1_h5_and_preserves_source_context(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_opportunity_output(temp_dir, _safe_payload())
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/api/research/opportunity-cohorts")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["available"])
        self.assertTrue(payload["research_only"])
        self.assertFalse(payload["provider_access"])
        self.assertFalse(payload["labels_joined"])
        self.assertFalse(payload["production_change"])
        self.assertEqual(payload["config_version"], "phase3.1-smoke-v1")
        self.assertEqual(
            [group["display_id"] for group in payload["groups"]],
            ["H1", "H2", "H3", "H4", "H5"],
        )
        groups = {
            group["cohort_id"]: group for group in payload["groups"]
        }
        h2 = groups["trend_acceleration_with_crowding_guard"]
        self.assertEqual(h2["member_count"], 1)
        self.assertEqual(h2["items"][0]["symbol"], "sh.600016")
        self.assertEqual(h2["items"][0]["rank"], 7)
        self.assertTrue(h2["items"][0]["is_breakout_watch"])
        self.assertEqual(
            h2["items"][0]["captured_positive_lists"],
            "breakout_watch",
        )
        self.assertTrue(
            groups["right_tail_opportunity_watch"]["empty"]
        )
        self.assertEqual(
            groups["right_tail_opportunity_watch"]["items"],
            [],
        )
        self.assertTrue(
            any("Not validated" in caveat for caveat in payload["caveats"])
        )

    def test_requested_missing_date_returns_clear_unavailable_state(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_opportunity_output(temp_dir, _safe_payload())
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get(
                "/api/research/opportunity-cohorts",
                params={"as_of_date": "2025-01-31"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "unavailable")
        self.assertEqual(response.json()["as_of_date"], "2025-01-31")

    def test_future_label_and_outcome_fields_are_blocked(self) -> None:
        for field in ("future_return", "label", "outcome"):
            with self.subTest(field=field):
                with tempfile.TemporaryDirectory() as temp_dir:
                    payload = _safe_payload()
                    payload["records"][0][field] = 0.1
                    _write_opportunity_output(temp_dir, payload)
                    client = TestClient(create_app(outputs_dir=temp_dir))

                    response = client.get(
                        "/api/research/opportunity-cohorts"
                    )

                self.assertEqual(response.status_code, 409)
                blocked = response.json()
                self.assertEqual(
                    blocked["status"],
                    "blocked_unsafe_output",
                )
                self.assertTrue(all(
                    group["items"] == [] for group in blocked["groups"]
                ))
                self.assertIn(
                    f"forbidden_outcome_field:{field}",
                    blocked["safety_violations"],
                )

    def test_unsafe_metadata_is_blocked(self) -> None:
        cases = (
            ("research_only", False),
            ("provider_access", True),
            ("labels_joined", True),
            ("production_change", True),
        )
        for field, value in cases:
            with self.subTest(field=field):
                with tempfile.TemporaryDirectory() as temp_dir:
                    payload = _safe_payload()
                    payload["metadata"][field] = value
                    _write_opportunity_output(temp_dir, payload)
                    client = TestClient(create_app(outputs_dir=temp_dir))

                    response = client.get(
                        "/api/research/opportunity-cohorts"
                    )

                self.assertEqual(response.status_code, 409)
                self.assertEqual(
                    response.json()["status"],
                    "blocked_unsafe_output",
                )
                self.assertTrue(all(
                    group["items"] == []
                    for group in response.json()["groups"]
                ))

    def test_page_shows_research_only_groups_and_safe_wording(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_opportunity_output(temp_dir, _safe_payload())
            client = TestClient(create_app(outputs_dir=temp_dir))

            response = client.get("/research/opportunity-cohorts")

        self.assertEqual(response.status_code, 200)
        text = response.text
        for wording in (
            "Research-only opportunity cohorts",
            "Not validated",
            "Not investment advice",
            "Smoke counts are execution evidence only",
            "H1",
            "H2",
            "H3",
            "H4",
            "H5",
            "No members in this generated research cohort.",
        ):
            self.assertIn(wording, text)
        for wording in (
            "buy",
            "sell",
            "guaranteed return",
            "expected return",
            "validated alpha",
            "better cohort",
            "worse cohort",
        ):
            self.assertNotIn(wording, text.lower())


def _write_opportunity_output(
    outputs_dir: str,
    payload: dict[str, object],
) -> None:
    research_dir = Path(outputs_dir, "research")
    research_dir.mkdir(parents=True, exist_ok=True)
    Path(
        research_dir,
        f"opportunity_cohorts_{AS_OF_DATE}.json",
    ).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _safe_payload() -> dict[str, object]:
    summaries = [
        {
            "cohort_id": cohort_id,
            "cohort_role": (
                "opportunity_observation"
                if index < 3
                else "risk_annotation"
            ),
            "research_only": True,
            "input_row_count": 1,
            "member_count": 1 if index == 1 else 0,
            "blocked_row_count": 0,
            "caveat": f"{display_id} research caveat.",
        }
        for index, (display_id, cohort_id) in enumerate(
            zip(("H1", "H2", "H3", "H4", "H5"), COHORT_IDS)
        )
    ]
    base_record = {
        "as_of_date": AS_OF_DATE,
        "symbol": "sh.600016",
        "rank": 7,
        "captured_positive_lists": "breakout_watch",
        "captured_risk_lists": "",
        "is_breakout_watch": True,
        "is_accumulation_watch": False,
        "annotation_status": "not_in_cohort",
        "cohort_member": False,
        "evidence_fields": "{}",
        "counter_evidence_fields": "{}",
        "research_only": True,
    }
    records = []
    for index, cohort_id in enumerate(COHORT_IDS):
        record = deepcopy(base_record)
        record["cohort_id"] = cohort_id
        record["cohort_role"] = (
            "opportunity_observation" if index < 3 else "risk_annotation"
        )
        if index == 1:
            record["cohort_member"] = True
            record["annotation_status"] = "included"
        records.append(record)
    return {
        "metadata": {
            "status": "ok",
            "research_only": True,
            "provider_access": False,
            "labels_joined": False,
            "production_change": False,
            "as_of_date": AS_OF_DATE,
            "source_snapshot_path": (
                "research/inputs/"
                "member_level_asof_features_2024-10-31.csv"
            ),
            "config_version": "phase3.1-smoke-v1",
        },
        "cohorts": summaries,
        "records": records,
    }
