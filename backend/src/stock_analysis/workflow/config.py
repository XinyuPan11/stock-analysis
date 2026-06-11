from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DailyWorkflowConfig:
    repo_root: Path
    provider: str = "baostock"
    start_date: str = "2023-01-01"
    end_date: str = "2024-01-31"
    benchmark: str = "CSI300"
    limit: int | None = None
    top_n: int = 10
    backtest_top_n: int = 5
    lookback_days: int = 120
    include_lookback_days: int = 120
    rebalance_frequency: str = "monthly"
    transaction_cost_bps: float = 10.0
    batch_size: int = 10
    sleep_seconds: float = 0.5
    retry: int = 1
    resume: bool = False
    cache_dir: str = "data/cache/daily-use"
    output_dir: str = "outputs"
    check_proxy: bool = False
    skip_prewarm: bool = False
    skip_research: bool = False
    skip_report: bool = False
    skip_backtest: bool = False
    serve: bool = False
    host: str = "127.0.0.1"
    port: int = 8000
    dry_run: bool = False
    continue_on_error: bool = False
    python_executable: str = "python"

    @property
    def output_root(self) -> Path:
        return self._resolve_path(self.output_dir)

    @property
    def cache_root(self) -> Path:
        return self._resolve_path(self.cache_dir)

    @property
    def daily_output_dir(self) -> Path:
        return self.output_root / "daily"

    @property
    def reports_output_dir(self) -> Path:
        return self.output_root / "reports"

    @property
    def backtests_output_dir(self) -> Path:
        return self.output_root / "backtests"

    @property
    def cache_output_dir(self) -> Path:
        return self.output_root / "cache"

    @property
    def workflow_output_dir(self) -> Path:
        return self.output_root / "workflow"

    @property
    def errors_output_dir(self) -> Path:
        return self.output_root / "errors"

    @property
    def dashboard_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def _resolve_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return self.repo_root / path
