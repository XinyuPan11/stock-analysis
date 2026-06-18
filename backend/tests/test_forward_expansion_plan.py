from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.validation.forward_expansion import ForwardExpansionConfig, build_forward_expansion_plan, write_forward_expansion_plan


class ForwardExpansionPlanTests(unittest.TestCase):
    def test_forward_plan_generates_three_controlled_batches(self) -> None:
        plan = build_forward_expansion_plan(ForwardExpansionConfig(cache_dir="data\\cache\\daily-use"))

        self.assertEqual(plan["provider_access"], False)
        self.assertTrue(plan["no_full_market_default"])
        self.assertEqual([batch["batch_id"] for batch in plan["batches"]], ["batch_1", "batch_2", "batch_3"])
        self.assertEqual(plan["batches"][0]["start_date"], "2024-02-01")
        self.assertEqual(plan["batches"][2]["end_date"], "2024-12-31")
        self.assertIn("--limit 50", plan["batches"][0]["manual_prewarm_command"])
        self.assertNotIn("run_daily_workflow.py", json.dumps(plan, ensure_ascii=False))

    def test_forward_plan_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plan = build_forward_expansion_plan(ForwardExpansionConfig(outputs_dir=Path(temp_dir) / "outputs"))
            paths = write_forward_expansion_plan(plan, Path(temp_dir) / "outputs")

            json_path = Path(paths["json"])
            md_path = Path(paths["markdown"])
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["batches"]), 3)
            self.assertIn("Do not let Codex run full-market workflow", md_path.read_text(encoding="utf-8"))

    def test_plan_cli_does_not_access_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            script = Path(__file__).resolve().parents[1] / "scripts" / "generate_forward_expansion_plan.py"
            completed = subprocess.run(
                [sys.executable, str(script), "--outputs-dir", str(Path(temp_dir) / "outputs"), "--cache-dir", str(Path(temp_dir) / "cache")],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn('"provider_access": false', completed.stdout)
            self.assertTrue((Path(temp_dir) / "outputs" / "expansion" / "forward_expansion_plan_2024.json").exists())


if __name__ == "__main__":
    unittest.main()
