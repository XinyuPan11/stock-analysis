from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.validation.walk_forward import WalkForwardConfig, run_walk_forward_validation


class WalkForwardValidationTests(unittest.TestCase):
    def test_dry_run_reads_static_outputs_and_writes_no_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_fixture(root)

            result = run_walk_forward_validation(
                WalkForwardConfig(
                    as_of_date="2024-01-31",
                    horizon_days=1,
                    outputs_dir=root / "outputs",
                    cache_dir=root / "cache",
                    list_ids=("trend_leaders",),
                    limit=2,
                    dry_run=True,
                )
            )

            self.assertEqual(result["summary"]["status"], "dry_run")
            self.assertTrue(result["summary"]["no_future_leakage"])
            self.assertEqual(result["summary"]["symbol_count"], 2)
            self.assertEqual(result["outputs"], {})
            self.assertFalse((root / "outputs" / "validation").exists())

    def test_cli_dry_run_does_not_default_to_long_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_fixture(root)
            script = Path(__file__).resolve().parents[1] / "scripts" / "run_walk_forward_validation.py"

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
                    "--list-ids",
                    "trend_leaders",
                    "--limit",
                    "1",
                    "--dry-run",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn('"status": "dry_run"', completed.stdout)
            self.assertFalse((root / "outputs" / "validation").exists())

    def test_write_output_json_contains_no_nan_or_infinity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_fixture(root, benchmark_symbol="sh.000300")

            result = run_walk_forward_validation(
                WalkForwardConfig(
                    as_of_date="2024-01-31",
                    horizon_days=1,
                    outputs_dir=root / "outputs",
                    cache_dir=root / "cache",
                    list_ids=("trend_leaders",),
                    limit=2,
                    dry_run=False,
                )
            )

            for path in result["outputs"].values():
                if str(path).endswith(".json"):
                    text = Path(path).read_text(encoding="utf-8")
                    self.assertNotIn("NaN", text)
                    self.assertNotIn("Infinity", text)

            labels = {row["symbol"]: row for row in result["future_labels"]}
            self.assertEqual(labels["AAA"]["benchmark_data_quality"], "ok")
            self.assertIsNotNone(labels["AAA"]["future_excess_return"])


def _write_fixture(root: Path, *, benchmark_symbol: str = "CSI300") -> None:
    outputs = root / "outputs"
    cache = root / "cache"
    (outputs / "labels").mkdir(parents=True)
    (outputs / "lists").mkdir(parents=True)
    (outputs / "daily").mkdir(parents=True)
    _write_json(
        outputs / "labels" / "stock_labels_2024-01-31.json",
        [
            {"symbol": "AAA", "total_score": 90, "momentum_score": 80, "trend_score": 70, "relative_strength_score": 60, "risk_score": 50, "liquidity_score": 40},
            {"symbol": "BBB", "total_score": 50, "momentum_score": 40, "trend_score": 30, "relative_strength_score": 20, "risk_score": 60, "liquidity_score": 70},
        ],
    )
    _write_json(
        outputs / "lists" / "trend_leaders_2024-01-31.json",
        {"list_id": "trend_leaders", "as_of_date": "2024-01-31", "items": [{"symbol": "AAA"}, {"symbol": "BBB"}]},
    )
    _write_json(
        outputs / "daily" / "factors_2024-01-31.json",
        [{"symbol": "AAA", "total_score": 90}, {"symbol": "BBB", "total_score": 50}],
    )
    _write_price(cache / "baostock" / "stock_daily" / "adjusted" / "AAA.csv", "AAA", [("2024-01-31", 100), ("2024-02-01", 110)])
    _write_price(cache / "baostock" / "stock_daily" / "adjusted" / "BBB.csv", "BBB", [("2024-01-31", 100), ("2024-02-01", 95)])
    _write_price(cache / "baostock" / "index_daily" / "raw" / f"{benchmark_symbol}.csv", benchmark_symbol, [("2024-01-31", 1000), ("2024-02-01", 1010)])


def _write_price(path: Path, symbol: str, rows: list[tuple[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
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
    )
    frame.to_csv(path, index=False, encoding="utf-8")


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
