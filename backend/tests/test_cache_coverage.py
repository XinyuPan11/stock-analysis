from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.validation.forward_expansion import CacheCoverageConfig, check_cache_coverage


class CacheCoverageTests(unittest.TestCase):
    def test_cache_coverage_reads_local_files_and_lists_missing_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_labels(root / "outputs", ["AAA", "BBB"])
            _write_price(root / "cache" / "baostock" / "stock_daily" / "adjusted" / "AAA.csv", "AAA", [("2024-02-01", 10), ("2024-05-31", 11)])

            report = check_cache_coverage(
                CacheCoverageConfig(
                    start_date="2024-02-01",
                    end_date="2024-05-31",
                    cache_dir=root / "cache",
                    outputs_dir=root / "outputs",
                    limit=2,
                )
            )

            self.assertFalse(report["provider_access"])
            self.assertEqual(report["symbol_count"], 2)
            self.assertEqual(report["covered_count"], 1)
            self.assertEqual(report["missing_count"], 1)
            self.assertEqual(report["missing_symbols"], ["BBB"])

    def test_missing_symbols_file_does_not_silently_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            with self.assertRaises(FileNotFoundError):
                check_cache_coverage(
                    CacheCoverageConfig(
                        start_date="2024-08-01",
                        end_date="2024-11-28",
                        cache_dir=root / "cache",
                        symbols_file=root / "missing_symbols.txt",
                        limit=300,
                    )
                )

    def test_empty_symbols_file_requires_explicit_allow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            symbols_file = root / "symbols.txt"
            symbols_file.write_text("", encoding="utf-8")

            with self.assertRaises(ValueError):
                check_cache_coverage(
                    CacheCoverageConfig(
                        start_date="2024-08-01",
                        end_date="2024-11-28",
                        cache_dir=root / "cache",
                        symbols_file=symbols_file,
                        limit=300,
                    )
                )

            report = check_cache_coverage(
                CacheCoverageConfig(
                    start_date="2024-08-01",
                    end_date="2024-11-28",
                    cache_dir=root / "cache",
                    symbols_file=symbols_file,
                    limit=300,
                    allow_empty_symbols=True,
                )
            )
            self.assertEqual(report["symbol_count"], 0)

    def test_cache_coverage_cli_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_symbols(root / "symbols.txt", ["AAA", "BBB"])
            _write_price(root / "cache" / "baostock" / "stock_daily" / "adjusted" / "AAA.csv", "AAA", [("2024-06-01", 10)])
            output_file = root / "outputs" / "expansion" / "coverage.json"
            script = Path(__file__).resolve().parents[1] / "scripts" / "check_cache_coverage.py"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--start-date",
                    "2024-06-01",
                    "--end-date",
                    "2024-08-31",
                    "--cache-dir",
                    str(root / "cache"),
                    "--symbols-file",
                    str(root / "symbols.txt"),
                    "--output-file",
                    str(output_file),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["missing_symbols"], ["BBB"])
            self.assertIn('"provider_access": false', completed.stdout)


def _write_labels(outputs_dir: Path, symbols: list[str]) -> None:
    path = outputs_dir / "labels" / "stock_labels_2024-01-31.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([{"symbol": symbol} for symbol in symbols]), encoding="utf-8")


def _write_symbols(path: Path, symbols: list[str]) -> None:
    path.write_text("\n".join(symbols) + "\n", encoding="utf-8")


def _write_price(path: Path, symbol: str, rows: list[tuple[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "symbol": [symbol] * len(rows),
            "trade_date": [row[0] for row in rows],
            "close": [row[1] for row in rows],
            "adj_close": [row[1] for row in rows],
        }
    ).to_csv(path, index=False, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
