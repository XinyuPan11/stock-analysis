from __future__ import annotations

import os
import socket
from pathlib import Path
from typing import Any

from stock_analysis.workflow.config import DailyWorkflowConfig


def environment_snapshot(config: DailyWorkflowConfig) -> dict[str, Any]:
    warnings: list[str] = []
    proxy = {
        "HTTP_PROXY": os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy") or "",
        "HTTPS_PROXY": os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or "",
    }
    if config.check_proxy:
        warnings.extend(_proxy_warnings(proxy))
    return {
        "cwd": str(config.repo_root),
        "outputs_dir": str(config.output_root),
        "cache_dir": str(config.cache_root),
        "proxy": proxy,
        "warnings": warnings,
    }


def output_health(config: DailyWorkflowConfig) -> dict[str, Any]:
    required = required_output_files(config)
    missing = [str(path) for path in required if not path.exists()]
    status = "ok" if not missing else "failed"
    return {
        "status": status,
        "required_files": [{"path": str(path), "exists": path.exists()} for path in required],
        "missing_files": missing,
    }


def required_output_files(config: DailyWorkflowConfig) -> list[Path]:
    date = config.end_date
    return [
        config.daily_output_dir / f"candidates_{date}.json",
        config.daily_output_dir / f"summary_{date}.json",
        config.daily_output_dir / f"factors_{date}.json",
        config.daily_output_dir / f"factor_explanations_{date}.json",
        config.reports_output_dir / f"daily_report_{date}.md",
        config.reports_output_dir / f"daily_report_{date}.html",
        config.backtests_output_dir / f"backtest_summary_{date}.json",
        config.backtests_output_dir / f"backtest_report_{date}.md",
        config.backtests_output_dir / f"backtest_report_{date}.html",
    ]


def daily_research_files(config: DailyWorkflowConfig) -> list[Path]:
    date = config.end_date
    return [
        config.daily_output_dir / f"candidates_{date}.json",
        config.daily_output_dir / f"summary_{date}.json",
        config.daily_output_dir / f"factors_{date}.json",
        config.daily_output_dir / f"factor_explanations_{date}.json",
    ]


def _proxy_warnings(proxy: dict[str, str]) -> list[str]:
    warnings: list[str] = []
    if not proxy["HTTP_PROXY"]:
        warnings.append("HTTP_PROXY is not set.")
    if not proxy["HTTPS_PROXY"]:
        warnings.append("HTTPS_PROXY is not set.")
    try:
        with socket.create_connection(("127.0.0.1", 8668), timeout=1.0):
            pass
    except OSError as exc:
        warnings.append(f"Proxy 127.0.0.1:8668 is not reachable: {exc}")
    return warnings
