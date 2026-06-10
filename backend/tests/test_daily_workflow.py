from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.workflow.config import DailyWorkflowConfig
from stock_analysis.workflow.daily_workflow import run_daily_workflow
from stock_analysis.workflow.steps import CommandResult
from stock_analysis.workflow.validation import output_health


class DailyWorkflowTests(unittest.TestCase):
    def test_dry_run_does_not_execute_steps_and_returns_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _config(temp_dir, dry_run=True)

            def runner(command: list[str], cwd: Path) -> CommandResult:
                raise AssertionError(f"dry-run executed command: {command}")

            summary = run_daily_workflow(config, runner=runner)

            self.assertEqual(summary["status"], "planned")
            self.assertEqual(summary["step_statuses"]["prewarm"], "planned")
            self.assertEqual(summary["step_statuses"]["daily_research"], "planned")
            self.assertTrue(Path(summary["summary_path"]).exists())
            self.assertTrue(Path(summary["log_path"]).exists())

    def test_workflow_calls_steps_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _config(temp_dir)
            calls: list[str] = []

            summary = run_daily_workflow(config, runner=_successful_runner(config, calls))

        self.assertEqual(calls, ["prewarm_market_cache.py", "run_daily_research.py", "generate_research_report.py", "run_backtest.py"])
        self.assertEqual(summary["step_statuses"]["prewarm"], "ok")
        self.assertEqual(summary["step_statuses"]["daily_research"], "ok")
        self.assertEqual(summary["step_statuses"]["report_generation"], "ok")
        self.assertEqual(summary["step_statuses"]["backtest"], "ok")
        self.assertEqual(summary["step_statuses"]["output_health"], "ok")

    def test_skip_prewarm_skips_prewarm(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _config(temp_dir, skip_prewarm=True)
            calls: list[str] = []

            run_daily_workflow(config, runner=_successful_runner(config, calls))

        self.assertNotIn("prewarm_market_cache.py", calls)
        self.assertEqual(calls[0], "run_daily_research.py")

    def test_skip_backtest_skips_backtest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _config(temp_dir, skip_backtest=True)
            calls: list[str] = []

            summary = run_daily_workflow(config, runner=_successful_runner(config, calls))

        self.assertNotIn("run_backtest.py", calls)
        self.assertNotIn("backtest", summary["step_statuses"])

    def test_step_failure_records_failed_in_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _config(temp_dir)

            def runner(command: list[str], cwd: Path) -> CommandResult:
                if "run_daily_research.py" in command[1]:
                    return CommandResult(returncode=2, stderr="research failed")
                return CommandResult(returncode=0)

            summary = run_daily_workflow(config, runner=runner)

        self.assertEqual(summary["status"], "failed")
        self.assertEqual(summary["step_statuses"]["daily_research"], "failed")
        self.assertIn("research failed", "\n".join(summary["errors"]))

    def test_continue_on_error_continues_after_critical_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _config(temp_dir, continue_on_error=True)
            calls: list[str] = []

            def runner(command: list[str], cwd: Path) -> CommandResult:
                script = Path(command[1]).name
                calls.append(script)
                if script == "run_daily_research.py":
                    return CommandResult(returncode=2, stderr="research failed")
                _materialize_outputs(config, script)
                return CommandResult(returncode=0)

            summary = run_daily_workflow(config, runner=runner)

        self.assertEqual(summary["step_statuses"]["daily_research"], "failed")
        self.assertEqual(summary["step_statuses"]["report_generation"], "failed")
        self.assertIn("run_backtest.py", calls)

    def test_output_health_detects_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _config(temp_dir)

            health = output_health(config)

        self.assertEqual(health["status"], "failed")
        self.assertTrue(any("candidates_2024-01-31.json" in path for path in health["missing_files"]))

    def test_workflow_summary_json_fields_are_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _config(temp_dir)
            summary = run_daily_workflow(config, runner=_successful_runner(config, []))
            saved = json.loads(Path(summary["summary_path"]).read_text(encoding="utf-8"))

        for field in [
            "status",
            "start_time",
            "end_time",
            "elapsed_seconds",
            "provider",
            "start_date",
            "end_date",
            "benchmark",
            "limit",
            "top_n",
            "steps",
            "step_statuses",
            "output_files",
            "missing_files",
            "warnings",
            "errors",
            "dashboard_url",
        ]:
            self.assertIn(field, saved)

    def test_workflow_log_generated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _config(temp_dir)
            summary = run_daily_workflow(config, runner=_successful_runner(config, []))

            log_text = Path(summary["log_path"]).read_text(encoding="utf-8")

        self.assertIn("workflow started", log_text)
        self.assertIn("daily_research ok", log_text)


def _config(root: str, **overrides: object) -> DailyWorkflowConfig:
    kwargs = {
        "repo_root": Path(root),
        "provider": "baostock",
        "start_date": "2023-01-01",
        "end_date": "2024-01-31",
        "benchmark": "CSI300",
        "limit": 50,
        "top_n": 10,
        "backtest_top_n": 5,
        "cache_dir": "data/cache/daily-use",
        "output_dir": "outputs",
    }
    kwargs.update(overrides)
    return DailyWorkflowConfig(**kwargs)


def _successful_runner(config: DailyWorkflowConfig, calls: list[str]):
    def runner(command: list[str], cwd: Path) -> CommandResult:
        script = Path(command[1]).name
        calls.append(script)
        _materialize_outputs(config, script)
        return CommandResult(returncode=0, stdout=f"{script} ok")

    return runner


def _materialize_outputs(config: DailyWorkflowConfig, script: str) -> None:
    date = config.end_date
    if script == "prewarm_market_cache.py":
        _write_json(config.cache_output_dir / f"cache_prewarm_summary_{date}.json", {"status": "ok"})
    if script == "run_daily_research.py":
        _write_json(config.daily_output_dir / f"candidates_{date}.json", [])
        _write_json(config.daily_output_dir / f"summary_{date}.json", {"as_of_date": date})
        _write_json(config.daily_output_dir / f"factors_{date}.json", [])
        _write_json(config.daily_output_dir / f"factor_explanations_{date}.json", [])
    if script == "generate_research_report.py":
        _write_text(config.reports_output_dir / f"daily_report_{date}.md", "# Daily Report")
        _write_text(config.reports_output_dir / f"daily_report_{date}.html", "<h1>Daily Report</h1>")
    if script == "run_backtest.py":
        _write_json(config.backtests_output_dir / f"backtest_summary_{date}.json", {"as_of_date": date})
        _write_text(config.backtests_output_dir / f"backtest_report_{date}.md", "# Backtest")
        _write_text(config.backtests_output_dir / f"backtest_report_{date}.html", "<h1>Backtest</h1>")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
