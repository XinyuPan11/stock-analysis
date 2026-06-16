from __future__ import annotations

import importlib.util
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
            "full_market",
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

    def test_workflow_without_limit_does_not_pass_limit_to_child_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _config(temp_dir, limit=None)
            commands: list[list[str]] = []

            def runner(command: list[str], cwd: Path) -> CommandResult:
                commands.append(command.copy())
                _materialize_outputs(config, Path(command[1]).name)
                return CommandResult(returncode=0)

            summary = run_daily_workflow(config, runner=runner)

        limited_scripts = {"prewarm_market_cache.py", "run_daily_research.py", "run_backtest.py"}
        for command in commands:
            if Path(command[1]).name in limited_scripts:
                self.assertNotIn("--limit", command)
        self.assertIsNone(summary["limit"])
        self.assertTrue(summary["full_market"])

    def test_workflow_with_limit_passes_limit_to_child_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _config(temp_dir, limit=1500)
            commands: list[list[str]] = []

            def runner(command: list[str], cwd: Path) -> CommandResult:
                commands.append(command.copy())
                _materialize_outputs(config, Path(command[1]).name)
                return CommandResult(returncode=0)

            summary = run_daily_workflow(config, runner=runner)

        limited_scripts = {"prewarm_market_cache.py", "run_daily_research.py", "run_backtest.py"}
        for command in commands:
            if Path(command[1]).name in limited_scripts:
                self.assertIn("--limit", command)
                limit_index = command.index("--limit")
                self.assertEqual(command[limit_index + 1], "1500")
        self.assertEqual(summary["limit"], 1500)
        self.assertFalse(summary["full_market"])

    def test_daily_research_command_includes_progress_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _config(temp_dir, skip_prewarm=True, skip_backtest=True, daily_progress_every=1, symbol_timeout_seconds=60.0)
            commands: list[list[str]] = []

            def runner(command: list[str], cwd: Path) -> CommandResult:
                commands.append(command.copy())
                _materialize_outputs(config, Path(command[1]).name)
                return CommandResult(returncode=0)

            run_daily_workflow(config, runner=runner)

        research_command = next(command for command in commands if Path(command[1]).name == "run_daily_research.py")
        self.assertIn("--progress-log", research_command)
        progress_log_index = research_command.index("--progress-log")
        self.assertTrue(research_command[progress_log_index + 1].endswith("daily_research_progress_2024-01-31.log"))
        self.assertIn("--progress-every", research_command)
        progress_every_index = research_command.index("--progress-every")
        self.assertEqual(research_command[progress_every_index + 1], "1")
        self.assertIn("--symbol-timeout-seconds", research_command)
        timeout_index = research_command.index("--symbol-timeout-seconds")
        self.assertEqual(research_command[timeout_index + 1], "60.0")

    def test_backtest_command_includes_progress_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _config(temp_dir, skip_prewarm=True, skip_research=True, skip_report=True)
            commands: list[list[str]] = []

            def runner(command: list[str], cwd: Path) -> CommandResult:
                commands.append(command.copy())
                _materialize_outputs(config, Path(command[1]).name)
                return CommandResult(returncode=0)

            run_daily_workflow(config, runner=runner)

        backtest_command = next(command for command in commands if Path(command[1]).name == "run_backtest.py")
        self.assertIn("--progress-log", backtest_command)
        progress_log_index = backtest_command.index("--progress-log")
        self.assertTrue(backtest_command[progress_log_index + 1].endswith("backtest_progress_2024-01-31.log"))
        self.assertIn("--progress-every", backtest_command)

    def test_script_parsers_default_limit_to_none_and_keep_explicit_limit(self) -> None:
        script_args = {
            "run_daily_workflow.py": ["--start-date", "2023-01-01", "--end-date", "2024-01-31"],
            "prewarm_market_cache.py": ["--start-date", "2023-01-01", "--end-date", "2024-01-31"],
            "run_daily_research.py": ["--start-date", "2023-01-01", "--end-date", "2024-01-31"],
            "run_backtest.py": ["--start-date", "2023-01-01", "--end-date", "2024-01-31"],
        }

        for script_name, args in script_args.items():
            with self.subTest(script=script_name):
                module = _load_script_module(script_name)
                self.assertIsNone(module.parse_args(args).limit)
                self.assertEqual(module.parse_args([*args, "--limit", "1500"]).limit, 1500)

    def test_daily_workflow_parser_supports_daily_progress_and_symbol_timeout(self) -> None:
        module = _load_script_module("run_daily_workflow.py")
        args = module.parse_args(
            [
                "--start-date",
                "2023-01-01",
                "--end-date",
                "2024-01-31",
                "--daily-progress-every",
                "1",
                "--symbol-timeout-seconds",
                "45",
            ]
        )

        self.assertEqual(args.daily_progress_every, 1)
        self.assertEqual(args.symbol_timeout_seconds, 45.0)


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


def _load_script_module(script_name: str):
    path = Path(__file__).resolve().parents[1] / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(f"test_{Path(script_name).stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load script module: {script_name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
