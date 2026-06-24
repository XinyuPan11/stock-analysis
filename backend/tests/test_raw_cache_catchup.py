from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.data.raw_cache_catchup import (  # noqa: E402
    RawCacheCatchupPlanConfig,
    RawCacheCoverageConfig,
    build_raw_cache_coverage_report,
    generate_raw_cache_catchup_plan,
    stock_daily_adjusted_cache_path,
)


class RawCacheCatchupTests(unittest.TestCase):
    def test_coverage_report_parses_sample_cache_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            cache_path = stock_daily_adjusted_cache_path(root / "cache", "baostock")
            _write_price(cache_path / "AAA.csv", "AAA", ["2024-12-11", "2026-06-24"])
            _write_price(cache_path / "BBB.csv", "BBB", ["2024-12-11", "2026-06-20"])
            symbols_file = root / "symbols.txt"
            symbols_file.write_text("AAA\nBBB\nCCC\n", encoding="utf-8")

            report = build_raw_cache_coverage_report(
                RawCacheCoverageConfig(
                    cache_dir=root / "cache",
                    provider="baostock",
                    target_end_date="2026-06-24",
                    symbols_file=symbols_file,
                )
            )

            self.assertFalse(report["provider_access"])
            self.assertEqual(report["cache_layout"], str(cache_path))
            self.assertEqual(report["total_stock_csv_files"], 2)
            self.assertEqual(report["complete_symbol_count"], 1)
            self.assertEqual(report["stale_incomplete_symbol_count"], 1)
            self.assertEqual(report["missing_symbol_count"], 1)
            self.assertEqual(report["missing_symbols"], ["CCC"])
            by_symbol = {row["symbol"]: row for row in report["symbols"]}
            self.assertEqual(by_symbol["AAA"]["earliest_cached_date"], "2024-12-11")
            self.assertEqual(by_symbol["AAA"]["latest_cached_date"], "2026-06-24")
            self.assertTrue(by_symbol["AAA"]["reaches_target_end_date"])
            self.assertFalse(by_symbol["BBB"]["reaches_target_end_date"])

    def test_chunk_plan_starts_after_confirmed_smoke_and_names_outputs(self) -> None:
        plan = generate_raw_cache_catchup_plan(
            RawCacheCatchupPlanConfig(
                start_date="2024-12-11",
                end_date="2026-06-24",
                cache_dir="data/cache/daily-use",
                output_dir="outputs/cache",
                chunk_size=500,
                start_offset=250,
                chunk_count=2,
            )
        )

        self.assertFalse(plan["provider_access"])
        self.assertFalse(plan["full_workflow_executed"])
        self.assertFalse(plan["production_scoring_changed"])
        self.assertEqual(plan["confirmed_smoke_coverage"]["confirmed_successful_symbols"], 250)
        self.assertEqual(len(plan["chunk_commands"]), 2)
        first = plan["chunk_commands"][0]
        second = plan["chunk_commands"][1]
        self.assertEqual(first["offset"], 250)
        self.assertEqual(first["limit"], 500)
        self.assertEqual(second["offset"], 750)
        self.assertIn("raw_catchup_2024-12-11_2026-06-24_offset250_limit500", first["chunk_id"])
        self.assertIn("--symbol-timeout-seconds 20", first["command"])
        self.assertIn("--max-consecutive-symbol-timeouts 3", first["command"])
        self.assertIn("--failed-symbols-output", first["command"])
        self.assertIn("--progress-log", first["command"])


    def test_report_script_summary_only_omits_symbol_rows(self) -> None:
        from backend.scripts.report_raw_cache_catchup import _summary_only

        summary = _summary_only({"symbols": [{"symbol": "AAA"}], "stale_incomplete_symbols": [], "missing_symbols": [], "total_stock_csv_files": 1})

        self.assertNotIn("symbols", summary)
        self.assertNotIn("stale_incomplete_symbols", summary)
        self.assertNotIn("missing_symbols", summary)
        self.assertTrue(summary["details_omitted_from_console"])

    def test_retry_command_uses_smaller_batch_and_longer_timeout(self) -> None:
        plan = generate_raw_cache_catchup_plan(
            RawCacheCatchupPlanConfig(
                failed_symbols_file="outputs/cache/raw_catchup_failed_offset250.csv",
            )
        )

        command = plan["retry_command"]
        self.assertIn("--failed-symbols-file outputs\\cache\\raw_catchup_failed_offset250.csv", command)
        self.assertIn("--retry-only", command)
        self.assertIn("--batch-size 1", command)
        self.assertIn("--sleep-seconds 2.0", command)
        self.assertIn("--retry 2", command)
        self.assertIn("--symbol-timeout-seconds 40", command)
        self.assertIn("--max-consecutive-symbol-timeouts 2", command)

    def test_generated_commands_do_not_run_validation_or_scoring_workflows(self) -> None:
        plan = generate_raw_cache_catchup_plan(RawCacheCatchupPlanConfig(chunk_count=1))
        commands = [row["command"] for row in plan["chunk_commands"]]
        if plan["retry_command"]:
            commands.append(plan["retry_command"])
        joined = "\n".join(commands)

        self.assertIn("prewarm_market_cache.py", joined)
        self.assertNotIn("run_daily_research.py", joined)
        self.assertNotIn("run_controlled_validation_batch.py", joined)
        self.assertNotIn("run_walk_forward_validation.py", joined)
        self.assertNotIn("run_strategy_family_experiments.py", joined)
        self.assertNotIn("run_aggressive_filter_experiments.py", joined)


def _write_price(path: Path, symbol: str, dates: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "symbol": [symbol] * len(dates),
            "trade_date": dates,
            "open": [10.0] * len(dates),
            "high": [10.5] * len(dates),
            "low": [9.5] * len(dates),
            "close": [10.0] * len(dates),
            "volume": [1000] * len(dates),
            "amount": [100000] * len(dates),
            "adj_close": [10.0] * len(dates),
            "source": ["unit"] * len(dates),
        }
    ).to_csv(path, index=False)


if __name__ == "__main__":
    unittest.main()
