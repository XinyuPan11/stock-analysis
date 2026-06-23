from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.validation.multi_window_experiment_summary import (
    MultiWindowSummaryConfig,
    build_multi_window_experiment_summary,
    write_multi_window_experiment_summary_outputs,
)


def test_multi_window_summary_aggregates_ready_windows(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs"
    experiments_dir = outputs_dir / "experiments"
    experiments_dir.mkdir(parents=True)
    plan_file = experiments_dir / "multi_asof_validation_plan_2024.json"
    _write_plan(plan_file, [("2024-01-31", 20), ("2024-01-31", 60)])
    _write_window(experiments_dir, "2024-01-31", 20, excess=0.04, sample=30)
    _write_window(experiments_dir, "2024-01-31", 60, excess=0.06, sample=35)

    summary = build_multi_window_experiment_summary(
        MultiWindowSummaryConfig(
            outputs_dir=outputs_dir,
            plan_file=plan_file,
            windows=(("2024-01-31", 20), ("2024-01-31", 60)),
            min_valid_count=10,
        )
    )

    assert summary["summary"]["provider_access"] is False
    assert summary["summary"]["production_scoring_changed"] is False
    assert summary["summary"]["ready_window_count"] == 2
    strategy = summary["strategy_family_stability"][0]
    assert strategy["profile_id"] == "conservative_quality"
    assert strategy["positive_excess_window_count"] == 2
    assert strategy["classification"] == "robust_candidate"
    aggressive = summary["aggressive_filter_stability"][0]
    assert aggressive["filter_id"] == "volatility_cap_filter"
    assert aggressive["classification"] == "strong_filter_candidate"


def test_multi_window_summary_tracks_missing_outputs(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs"
    experiments_dir = outputs_dir / "experiments"
    experiments_dir.mkdir(parents=True)
    plan_file = experiments_dir / "multi_asof_validation_plan_2024.json"
    _write_plan(plan_file, [("2024-01-31", 20), ("2024-04-30", 60)])
    _write_window(experiments_dir, "2024-01-31", 20, excess=0.04, sample=30)

    summary = build_multi_window_experiment_summary(
        MultiWindowSummaryConfig(
            outputs_dir=outputs_dir,
            plan_file=plan_file,
            windows=(("2024-01-31", 20), ("2024-04-30", 60)),
            min_valid_count=10,
        )
    )

    assert summary["summary"]["ready_window_count"] == 1
    assert summary["summary"]["missing_window_count"] == 1
    missing = summary["excluded_or_missing_windows"][0]
    assert missing["status"] == "missing_experiment_outputs"
    assert missing["as_of_date"] == "2024-04-30"


def test_multi_window_summary_reads_nested_multi_asof_plan(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs"
    experiments_dir = outputs_dir / "experiments"
    experiments_dir.mkdir(parents=True)
    plan_file = experiments_dir / "multi_asof_validation_plan_2024.json"
    plan_file.write_text(
        json.dumps(
            {
                "as_of_plan": [
                    {
                        "as_of_date": "2024-01-31",
                        "horizons": [
                            {
                                "horizon_days": 20,
                                "ready_for_comparison": True,
                                "missing_outputs": {},
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    _write_window(experiments_dir, "2024-01-31", 20, excess=0.04, sample=30)

    summary = build_multi_window_experiment_summary(
        MultiWindowSummaryConfig(
            outputs_dir=outputs_dir,
            plan_file=plan_file,
            windows=(("2024-01-31", 20),),
            min_valid_count=10,
        )
    )

    ready = summary["ready_windows_used"][0]
    assert ready["plan_ready"] is True
    assert ready["plan_status"] == "ready_for_comparison"

def test_aggressive_filter_penalizes_small_n_and_right_tail_destruction(
    tmp_path: Path,
) -> None:
    outputs_dir = tmp_path / "outputs"
    experiments_dir = outputs_dir / "experiments"
    experiments_dir.mkdir(parents=True)
    plan_file = experiments_dir / "multi_asof_validation_plan_2024.json"
    _write_plan(plan_file, [("2024-01-31", 20), ("2024-01-31", 60)])
    _write_window(
        experiments_dir,
        "2024-01-31",
        20,
        excess=0.10,
        sample=8,
        right_tail=0.9,
    )
    _write_window(
        experiments_dir,
        "2024-01-31",
        60,
        excess=0.08,
        sample=9,
        right_tail=0.9,
    )

    summary = build_multi_window_experiment_summary(
        MultiWindowSummaryConfig(
            outputs_dir=outputs_dir,
            plan_file=plan_file,
            windows=(("2024-01-31", 20), ("2024-01-31", 60)),
            min_valid_count=10,
        )
    )
    aggressive = summary["aggressive_filter_stability"][0]
    assert aggressive["classification"] == "sample_too_small"

    _write_window(
        experiments_dir,
        "2024-01-31",
        20,
        excess=0.10,
        sample=30,
        right_tail=0.5,
    )
    _write_window(
        experiments_dir,
        "2024-01-31",
        60,
        excess=0.08,
        sample=30,
        right_tail=0.55,
    )
    summary = build_multi_window_experiment_summary(
        MultiWindowSummaryConfig(
            outputs_dir=outputs_dir,
            plan_file=plan_file,
            windows=(("2024-01-31", 20), ("2024-01-31", 60)),
            min_valid_count=10,
        )
    )
    aggressive = summary["aggressive_filter_stability"][0]
    assert aggressive["classification"] == "right_tail_destructive"


def test_write_outputs_and_cli_dry_run(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs"
    experiments_dir = outputs_dir / "experiments"
    experiments_dir.mkdir(parents=True)
    plan_file = experiments_dir / "multi_asof_validation_plan_2024.json"
    _write_plan(plan_file, [("2024-01-31", 20)])
    _write_window(experiments_dir, "2024-01-31", 20, excess=0.04, sample=30)

    summary = build_multi_window_experiment_summary(
        MultiWindowSummaryConfig(
            outputs_dir=outputs_dir,
            plan_file=plan_file,
            windows=(("2024-01-31", 20),),
            min_valid_count=10,
        )
    )
    outputs = write_multi_window_experiment_summary_outputs(summary, outputs_dir)
    assert Path(outputs["json"]).exists()
    assert Path(outputs["markdown"]).exists()
    assert "Research-only" in Path(outputs["markdown"]).read_text(encoding="utf-8")

    script = ROOT / "scripts" / "summarize_multi_window_experiments.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--outputs-dir",
            str(outputs_dir),
            "--plan-file",
            str(plan_file),
            "--windows",
            "2024-01-31:20",
            "--min-valid-count",
            "10",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["ready_window_count"] == 1


def _write_plan(path: Path, windows: list[tuple[str, int]]) -> None:
    path.write_text(
        json.dumps(
            {
                "validation_windows": [
                    {
                        "as_of_date": as_of_date,
                        "horizon_days": horizon,
                        "status": "ready",
                        "ready_for_comparison": True,
                    }
                    for as_of_date, horizon in windows
                ]
            }
        ),
        encoding="utf-8",
    )


def _write_window(
    experiments_dir: Path,
    as_of_date: str,
    horizon_days: int,
    *,
    excess: float,
    sample: int,
    right_tail: float = 0.9,
) -> None:
    strategy_payload = {
        "summary": {
            "research_only": True,
            "no_future_leakage": True,
        },
        "strategy_family_results": [
            {
                "profile_id": "conservative_quality",
                "family_type": "conservative",
                "as_of_date": as_of_date,
                "horizon_days": horizon_days,
                "valid_future_count": sample,
                "average_excess_return": excess,
                "outperform_rate": 0.7,
                "top_5_average_return": 0.2,
                "payoff_ratio": 1.5,
                "failure_rate_below_minus_20pct": 0.0,
            }
        ],
    }
    aggressive_payload = {
        "summary": {
            "research_only": True,
            "no_future_leakage": True,
            "production_scoring_replaced": False,
        },
        "aggressive_filter_results": [
            {
                "source_strategy_family": "momentum_breakout",
                "filter_id": "volatility_cap_filter",
                "as_of_date": as_of_date,
                "horizon_days": horizon_days,
                "valid_future_count": sample,
                "symbol_count_after_filter": sample,
                "average_excess_return": excess,
                "outperform_rate": 0.65,
                "top_5_average_return": 0.3,
                "right_tail_preservation_ratio": right_tail,
                "left_tail_reduction_ratio": 0.8,
                "payoff_ratio": 1.6,
                "failure_rate_below_minus_20pct": 0.05,
                "validation_status": "exploratory_same_period",
            }
        ],
    }
    (
        experiments_dir
        / f"strategy_family_experiments_{as_of_date}_{horizon_days}d.json"
    ).write_text(json.dumps(strategy_payload), encoding="utf-8")
    (
        experiments_dir
        / f"aggressive_filter_experiments_{as_of_date}_{horizon_days}d.json"
    ).write_text(json.dumps(aggressive_payload), encoding="utf-8")

