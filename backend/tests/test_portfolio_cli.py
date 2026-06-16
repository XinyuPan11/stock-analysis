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


class PortfolioCliTests(unittest.TestCase):
    def test_cli_dry_run_writes_no_formal_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_portfolio_fixture(root)
            script = Path(__file__).resolve().parents[1] / "scripts" / "run_portfolio_validation.py"

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
                    str(root / "does-not-matter"),
                    "--portfolio-ids",
                    "high_confidence_top10",
                    "--limit",
                    "50",
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn('"status": "dry_run"', completed.stdout)
            self.assertFalse((root / "outputs" / "portfolios").exists())

    def test_cli_non_dry_run_writes_portfolio_review_and_experiment_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_portfolio_fixture(root)
            script = Path(__file__).resolve().parents[1] / "scripts" / "run_portfolio_validation.py"
            summary_path = root / "outputs" / "portfolios" / "portfolio_summary_2024-01-31_60d.json"
            summary_path.parent.mkdir(parents=True)
            summary_path.write_text(json.dumps({"summary": {"status": "stale"}}), encoding="utf-8")

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
                    str(root / "does-not-matter"),
                    "--portfolio-ids",
                    "high_confidence_top10",
                    "--limit",
                    "50",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn('"status": "ok"', completed.stdout)
            self.assertTrue((root / "outputs" / "portfolios" / "portfolio_summary_2024-01-31_60d.json").exists())
            self.assertTrue((root / "outputs" / "reviews" / "portfolio_review_2024-01-31_60d.json").exists())
            self.assertTrue((root / "outputs" / "experiments" / "strategy_experiments_2024-01-31_60d.json").exists())
            summary = json.loads((root / "outputs" / "portfolios" / "portfolio_summary_2024-01-31_60d.json").read_text(encoding="utf-8"))
            self.assertNotEqual(summary["summary"]["status"], "stale")
            self.assertFalse(summary["summary"]["dry_run"])
            self.assertTrue(summary["summary"]["no_future_leakage"])

    def test_cli_dry_run_does_not_overwrite_existing_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_portfolio_fixture(root)
            summary_path = root / "outputs" / "portfolios" / "portfolio_summary_2024-01-31_60d.json"
            summary_path.parent.mkdir(parents=True)
            stale = json.dumps({"summary": {"status": "stale"}})
            summary_path.write_text(stale, encoding="utf-8")
            script = Path(__file__).resolve().parents[1] / "scripts" / "run_portfolio_validation.py"

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
                    str(root / "does-not-matter"),
                    "--portfolio-ids",
                    "high_confidence_top10",
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn('"status": "dry_run"', completed.stdout)
            self.assertEqual(summary_path.read_text(encoding="utf-8"), stale)


if __name__ == "__main__":
    unittest.main()
