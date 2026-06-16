from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import time
from typing import Any

from stock_analysis.workflow.config import DailyWorkflowConfig
from stock_analysis.workflow.steps import (
    CommandRunner,
    CommandResult,
    WorkflowStep,
    backtest_step,
    command_text,
    dashboard_step,
    default_command_runner,
    prewarm_step,
    report_step,
    research_step,
    start_dashboard,
)
from stock_analysis.workflow.validation import daily_research_files, environment_snapshot, output_health


def run_daily_workflow(
    config: DailyWorkflowConfig,
    *,
    runner: CommandRunner | None = None,
    dashboard_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    runner = runner or default_command_runner
    dashboard_runner = dashboard_runner or start_dashboard
    config.workflow_output_dir.mkdir(parents=True, exist_ok=True)

    started_at = _now()
    started_timer = time.perf_counter()
    summary_path = config.workflow_output_dir / f"workflow_summary_{config.end_date}.json"
    log_path = config.workflow_output_dir / f"workflow_log_{config.end_date}.txt"
    log_lines: list[str] = [f"[{started_at}] workflow started"]
    _write_log(log_path, log_lines)
    steps: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []
    output_files: list[str] = []
    missing_files: list[str] = []
    stopped = False

    env_step = _environment_step(config)
    steps.append(env_step)
    warnings.extend(env_step.get("warnings", []))
    log_lines.append(_step_log_line(env_step))
    _write_log(log_path, log_lines)

    planned_steps = build_plan(config)
    if config.dry_run:
        for step in planned_steps:
            record = _planned_record(step)
            steps.append(record)
            log_lines.append(_step_log_line(record))
            _write_log(log_path, log_lines)
        health = output_health(config)
        missing_files = list(health["missing_files"])
        status = "planned"
    else:
        for step in planned_steps:
            if stopped:
                break
            if step.name == "report_generation":
                missing_inputs = [str(path) for path in daily_research_files(config) if not path.exists()]
                if missing_inputs:
                    record = _failed_record(
                        step,
                        f"Missing daily research outputs for report generation: {', '.join(missing_inputs)}",
                    )
                    steps.append(record)
                    errors.append(record["error_message"])
                    log_lines.append(_step_log_line(record))
                    _write_log(log_path, log_lines)
                    if step.critical and not config.continue_on_error:
                        stopped = True
                    continue
            command_runner = dashboard_runner if step.name == "dashboard" else runner
            log_lines.append(f"[{_now()}] {step.name} start {command_text(step.command)}")
            _write_log(log_path, log_lines)
            record = _run_step(step, config.repo_root, command_runner)
            steps.append(record)
            log_lines.append(_step_log_line(record))
            _write_log(log_path, log_lines)
            output_files.extend(record.get("output_paths", []))
            if record["status"] == "failed":
                errors.append(record["error_message"])
                if step.critical and not config.continue_on_error:
                    stopped = True

        health = output_health(config)
        missing_files = list(health["missing_files"])
        health_record = _health_record(health)
        steps.append(health_record)
        log_lines.append(_step_log_line(health_record))
        _write_log(log_path, log_lines)
        if missing_files:
            warnings.append(f"output_health_missing_files:{len(missing_files)}")
        status = _workflow_status(steps, missing_files)

    dashboard_url = config.dashboard_url if config.serve else ""
    if not config.serve:
        log_lines.append(f"Dashboard command: {command_text(dashboard_step(config).command)}")
        _write_log(log_path, log_lines)

    ended_at = _now()
    summary = {
        "status": status,
        "start_time": started_at,
        "end_time": ended_at,
        "elapsed_seconds": round(time.perf_counter() - started_timer, 4),
        "provider": config.provider,
        "start_date": config.start_date,
        "end_date": config.end_date,
        "benchmark": config.benchmark,
        "limit": config.limit,
        "full_market": config.limit is None,
        "top_n": config.top_n,
        "steps": steps,
        "step_statuses": {step["name"]: step["status"] for step in steps},
        "output_files": sorted(set(output_files + [str(path) for path in _existing_expected_outputs(config)])),
        "missing_files": missing_files,
        "warnings": sorted(set(warnings)),
        "errors": errors,
        "dashboard_url": dashboard_url,
        "dry_run": config.dry_run,
        "config": _serializable_config(config),
    }
    summary["summary_path"] = str(summary_path)
    summary["log_path"] = str(log_path)
    _write_summary(summary_path, summary)
    log_lines.append(f"[{ended_at}] workflow status: {status}")
    _write_log(log_path, log_lines)
    return summary


def build_plan(config: DailyWorkflowConfig) -> list[WorkflowStep]:
    steps: list[WorkflowStep] = []
    if not config.skip_prewarm:
        steps.append(prewarm_step(config))
    if not config.skip_research:
        steps.append(research_step(config))
    if not config.skip_report:
        steps.append(report_step(config))
    if not config.skip_backtest:
        steps.append(backtest_step(config))
    if config.serve:
        steps.append(dashboard_step(config))
    return steps


def _environment_step(config: DailyWorkflowConfig) -> dict[str, Any]:
    started = _now()
    timer = time.perf_counter()
    snapshot = environment_snapshot(config)
    warnings = list(snapshot.get("warnings", []))
    return {
        "name": "environment_check",
        "status": "warning" if warnings else "ok",
        "started_at": started,
        "ended_at": _now(),
        "elapsed_seconds": round(time.perf_counter() - timer, 4),
        "command_or_function": "environment_snapshot",
        "output_paths": [],
        "error_message": "",
        "warnings": warnings,
        "details": snapshot,
    }


def _run_step(step: WorkflowStep, cwd: Path, runner: CommandRunner) -> dict[str, Any]:
    started = _now()
    timer = time.perf_counter()
    command = step.command or []
    try:
        result = runner(command, cwd)
        status = "ok" if result.returncode == 0 else "failed"
        error = "" if status == "ok" else _command_error(result)
    except Exception as exc:
        result = CommandResult(returncode=1, stdout="", stderr=str(exc))
        status = "failed"
        error = str(exc)
    return {
        "name": step.name,
        "status": status,
        "started_at": started,
        "ended_at": _now(),
        "elapsed_seconds": round(time.perf_counter() - timer, 4),
        "command_or_function": command_text(command),
        "output_paths": [str(path) for path in step.output_paths if path.exists()],
        "error_message": error,
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-2000:],
    }


def _planned_record(step: WorkflowStep) -> dict[str, Any]:
    now = _now()
    return {
        "name": step.name,
        "status": "planned",
        "started_at": now,
        "ended_at": now,
        "elapsed_seconds": 0.0,
        "command_or_function": command_text(step.command),
        "output_paths": [str(path) for path in step.output_paths],
        "error_message": "",
    }


def _failed_record(step: WorkflowStep, message: str) -> dict[str, Any]:
    now = _now()
    return {
        "name": step.name,
        "status": "failed",
        "started_at": now,
        "ended_at": now,
        "elapsed_seconds": 0.0,
        "command_or_function": command_text(step.command),
        "output_paths": [],
        "error_message": message,
    }


def _health_record(health: dict[str, Any]) -> dict[str, Any]:
    now = _now()
    missing = health.get("missing_files", [])
    return {
        "name": "output_health",
        "status": "ok" if not missing else "warning",
        "started_at": now,
        "ended_at": now,
        "elapsed_seconds": 0.0,
        "command_or_function": "output_health",
        "output_paths": [],
        "error_message": "" if not missing else f"Missing files: {', '.join(missing)}",
    }


def _workflow_status(steps: list[dict[str, Any]], missing_files: list[str]) -> str:
    if any(step["status"] == "failed" for step in steps):
        return "failed"
    if missing_files or any(step["status"] == "warning" for step in steps):
        return "warning"
    return "ok"


def _command_error(result: CommandResult) -> str:
    stderr = result.stderr.strip()
    stdout = result.stdout.strip()
    if stderr:
        return stderr[-2000:]
    if stdout:
        return stdout[-2000:]
    return f"Command exited with code {result.returncode}."


def _step_log_line(step: dict[str, Any]) -> str:
    message = step.get("error_message") or ",".join(step.get("warnings", [])) or ""
    return f"[{step.get('ended_at')}] {step.get('name')} {step.get('status')} {message}".rstrip()


def _existing_expected_outputs(config: DailyWorkflowConfig) -> list[Path]:
    paths: list[Path] = []
    for item in output_health(config)["required_files"]:
        if item["exists"]:
            paths.append(Path(item["path"]))
    return paths


def _serializable_config(config: DailyWorkflowConfig) -> dict[str, Any]:
    payload = asdict(config)
    payload["repo_root"] = str(config.repo_root)
    return payload


def _write_summary(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_log(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")
