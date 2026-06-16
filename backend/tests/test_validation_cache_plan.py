from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.validation.cache_plan import build_validation_cache_plan


class ValidationCachePlanTests(unittest.TestCase):
    def test_cache_plan_outputs_missing_future_symbols_and_benchmark(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_fixture(root)

            plan = build_validation_cache_plan(
                as_of_date="2024-01-31",
                horizon_days=1,
                outputs_dir=root / "outputs",
                cache_dir=root / "cache",
                benchmark="CSI300",
                limit=2,
            )

        self.assertEqual(plan["benchmark_symbol"], "sh.000300")
        self.assertIn("BBB", plan["symbols_to_prewarm"])
        self.assertIn("sh.000300", plan["symbols_to_prewarm"])
        self.assertEqual(plan["missing_future_count"], 2)

    def test_cache_plan_cli_does_not_access_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_fixture(root)
            script = Path(__file__).resolve().parents[1] / "scripts" / "generate_validation_cache_plan.py"
            output_file = root / "outputs" / "validation" / "cache_plan.txt"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--as-of-date",
                    "2024-01-31",
                    "--horizon-days",
                    "1",
                    "--outputs-dir",
                    str(root / "outputs"),
                    "--cache-dir",
                    str(root / "cache"),
                    "--limit",
                    "2",
                    "--output-file",
                    str(output_file),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(output_file.exists())
            self.assertIn("sh.000300", output_file.read_text(encoding="utf-8"))


def _write_fixture(root: Path) -> None:
    outputs = root / "outputs"
    cache = root / "cache"
    (outputs / "labels").mkdir(parents=True)
    _write_json(outputs / "labels" / "stock_labels_2024-01-31.json", [{"symbol": "AAA"}, {"symbol": "BBB"}])
    _write_price(cache / "baostock" / "stock_daily" / "adjusted" / "AAA.csv", "AAA", [("2024-01-31", 100), ("2024-02-01", 101)])


def _write_price(path: Path, symbol: str, rows: list[tuple[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "symbol": [symbol] * len(rows),
            "trade_date": [row[0] for row in rows],
            "open": [row[1] for row in rows],
            "high": [row[1] for row in rows],
            "low": [row[1] for row in rows],
            "close": [row[1] for row in rows],
            "volume": [1000] * len(rows),
            "amount": [10000] * len(rows),
            "adj_close": [row[1] for row in rows],
            "source": ["unit"] * len(rows),
        }
    ).to_csv(path, index=False, encoding="utf-8")


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
