from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.validation.bias_metadata import validation_bias_metadata


class ValidationBiasMetadataTests(unittest.TestCase):
    def test_metadata_records_guarded_prices_and_snapshot_limited_statuses(self) -> None:
        metadata = validation_bias_metadata()

        self.assertTrue(metadata["price_point_in_time_guard_applied"])
        self.assertEqual(metadata["feature_input_point_in_time_status"], "guarded")
        self.assertEqual(metadata["future_label_window_status"], "explicit_future_only")
        self.assertEqual(metadata["universe_point_in_time_status"], "current_snapshot_limited")
        self.assertEqual(metadata["listing_status_point_in_time_status"], "current_snapshot_limited")
        self.assertEqual(metadata["st_status_point_in_time_status"], "current_snapshot_limited")
        self.assertEqual(metadata["suspension_status_point_in_time_status"], "current_snapshot_limited")
        self.assertIn(
            "controlled_validation_not_final_production_grade_historical_simulation",
            metadata["known_bias_limitations"],
        )

    def test_known_bias_limitations_list_is_not_shared_between_calls(self) -> None:
        first = validation_bias_metadata()
        first["known_bias_limitations"].append("test_only")

        self.assertNotIn("test_only", validation_bias_metadata()["known_bias_limitations"])


if __name__ == "__main__":
    unittest.main()
