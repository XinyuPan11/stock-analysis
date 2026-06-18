from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(TESTS_DIR))

from test_portfolio_simulator import write_portfolio_fixture

from stock_analysis.validation.forward_expansion import ControlledValidationBatchConfig, run_controlled_validation_batch


class ControlledValidationBatchTests(unittest.TestCase):
    def test_controlled_validation_defaults_to_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_portfolio_fixture(root)

            result = run_controlled_validation_batch(
                ControlledValidationBatchConfig(
                    as_of_date="2024-01-31",
                    horizon_days=60,
                    outputs_dir=root / "outputs",
                    cache_dir=root / "cache",
                    limit=10,
                )
            )

            self.assertEqual(result["status"], "dry_run")
            self.assertTrue(result["dry_run"])
            self.assertFalse(result["provider_access"])
            self.assertTrue(result["no_full_market_workflow"])
            self.assertEqual(result["outputs"]["walk_forward"], {})
            self.assertEqual(result["outputs"]["portfolio"], {})
            self.assertFalse((root / "outputs" / "portfolios").exists())

    def test_controlled_validation_cli_is_safe_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_portfolio_fixture(root)
            script = Path(__file__).resolve().parents[1] / "scripts" / "run_controlled_validation_batch.py"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--as-of-date",
                    "2024-01-31",
                    "--horizon-days",
                    "60",
                    "--outputs-dir",
                    str(root / "outputs"),
                    "--cache-dir",
                    str(root / "cache"),
                    "--limit",
                    "10",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "dry_run")
            self.assertTrue(payload["dry_run"])
            self.assertFalse(payload["provider_access"])
            self.assertFalse((root / "outputs" / "portfolios").exists())

    def test_run_guide_does_not_instruct_codex_to_run_full_market_long_tasks(self) -> None:
        guide = Path(__file__).resolve().parents[2] / "PHASE2_8_1_CONTROLLED_2024_FORWARD_EXPANSION_RUN_GUIDE.md"
        text = guide.read_text(encoding="utf-8")

        self.assertIn("Do not let Codex run full-year prewarm", text)
        self.assertIn("python backend\\scripts\\check_cache_coverage.py", text)
        self.assertIn("--limit 50", text)
        self.assertNotIn("Codex should run full-market workflow", text)


if __name__ == "__main__":
    unittest.main()
