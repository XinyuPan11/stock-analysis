from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Callable

from stock_analysis.workflow.config import DailyWorkflowConfig


@dataclass(frozen=True)
class WorkflowStep:
    name: str
    command: list[str] | None
    output_paths: list[Path]
    critical: bool = False


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


CommandRunner = Callable[[list[str], Path], CommandResult]


def default_command_runner(command: list[str], cwd: Path) -> CommandResult:
    completed = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, check=False)
    return CommandResult(returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)


def start_dashboard(command: list[str], cwd: Path) -> CommandResult:
    subprocess.Popen(command, cwd=str(cwd))
    return CommandResult(returncode=0, stdout="Dashboard process started.", stderr="")


def prewarm_step(config: DailyWorkflowConfig) -> WorkflowStep:
    command = [
        config.python_executable,
        r"backend\scripts\prewarm_market_cache.py",
        "--provider",
        config.provider,
        "--start-date",
        config.start_date,
        "--end-date",
        config.end_date,
        "--include-lookback-days",
        str(config.include_lookback_days),
        "--batch-size",
        str(config.batch_size),
        "--cache-dir",
        str(config.cache_root),
        "--output-dir",
        str(config.cache_output_dir),
        "--sleep-seconds",
        str(config.sleep_seconds),
        "--retry",
        str(config.retry),
    ]
    _append_limit(command, config.limit)
    if config.resume:
        command.append("--resume")
    return WorkflowStep(
        name="prewarm",
        command=command,
        output_paths=[config.cache_output_dir / f"cache_prewarm_summary_{config.end_date}.json"],
        critical=False,
    )


def research_step(config: DailyWorkflowConfig) -> WorkflowStep:
    command = [
        config.python_executable,
        r"backend\scripts\run_daily_research.py",
        "--provider",
        config.provider,
        "--start-date",
        config.start_date,
        "--end-date",
        config.end_date,
        "--benchmark",
        config.benchmark,
        "--top-n",
        str(config.top_n),
        "--cache-dir",
        str(config.cache_root),
        "--output-dir",
        str(config.daily_output_dir),
        "--retry",
        str(config.retry),
    ]
    _append_limit(command, config.limit)
    return WorkflowStep(
        name="daily_research",
        command=command,
        output_paths=[
            config.daily_output_dir / f"candidates_{config.end_date}.json",
            config.daily_output_dir / f"summary_{config.end_date}.json",
            config.daily_output_dir / f"factors_{config.end_date}.json",
            config.daily_output_dir / f"factor_explanations_{config.end_date}.json",
        ],
        critical=True,
    )


def report_step(config: DailyWorkflowConfig) -> WorkflowStep:
    date = config.end_date
    return WorkflowStep(
        name="report_generation",
        command=[
            config.python_executable,
            r"backend\scripts\generate_research_report.py",
            "--candidates",
            str(config.daily_output_dir / f"candidates_{date}.json"),
            "--summary",
            str(config.daily_output_dir / f"summary_{date}.json"),
            "--factors",
            str(config.daily_output_dir / f"factors_{date}.json"),
            "--factor-explanations",
            str(config.daily_output_dir / f"factor_explanations_{date}.json"),
            "--output-dir",
            str(config.reports_output_dir),
        ],
        output_paths=[
            config.reports_output_dir / f"daily_report_{date}.md",
            config.reports_output_dir / f"daily_report_{date}.html",
        ],
        critical=False,
    )


def backtest_step(config: DailyWorkflowConfig) -> WorkflowStep:
    date = config.end_date
    command = [
        config.python_executable,
        r"backend\scripts\run_backtest.py",
        "--provider",
        config.provider,
        "--start-date",
        config.start_date,
        "--end-date",
        config.end_date,
        "--lookback-days",
        str(config.lookback_days),
        "--rebalance-frequency",
        config.rebalance_frequency,
        "--top-n",
        str(config.backtest_top_n),
        "--benchmark",
        config.benchmark,
        "--cache-dir",
        str(config.cache_root),
        "--output-dir",
        str(config.backtests_output_dir),
        "--transaction-cost-bps",
        str(config.transaction_cost_bps),
        "--retry",
        str(config.retry),
    ]
    _append_limit(command, config.limit)
    return WorkflowStep(
        name="backtest",
        command=command,
        output_paths=[
            config.backtests_output_dir / f"backtest_summary_{date}.json",
            config.backtests_output_dir / f"backtest_report_{date}.md",
            config.backtests_output_dir / f"backtest_report_{date}.html",
        ],
        critical=False,
    )


def dashboard_step(config: DailyWorkflowConfig) -> WorkflowStep:
    return WorkflowStep(
        name="dashboard",
        command=[
            config.python_executable,
            r"backend\scripts\run_api.py",
            "--outputs-dir",
            str(config.output_root),
            "--host",
            config.host,
            "--port",
            str(config.port),
        ],
        output_paths=[],
        critical=False,
    )


def command_text(command: list[str] | None) -> str:
    if not command:
        return ""
    return " ".join(command)


def _append_limit(command: list[str], limit: int | None) -> None:
    if limit is not None:
        command.extend(["--limit", str(limit)])
