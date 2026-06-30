from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_analysis.validation.unseen_window_readiness import (
    CONSUMED_U1_WINDOWS,
    FORBIDDEN_ANSWER_KEY_WINDOWS,
    PROPOSED_U1_WINDOWS,
    PROPOSED_U2_WINDOWS,
    UnseenWindowReadinessConfig,
    check_unseen_window_readiness,
    markdown_unseen_window_readiness,
    validate_unseen_window_candidate,
    write_unseen_window_readiness,
)


def test_forbidden_answer_key_windows_are_rejected() -> None:
    for as_of_date, horizon_days in FORBIDDEN_ANSWER_KEY_WINDOWS:
        result = validate_unseen_window_candidate(as_of_date, horizon_days)
        assert result["accepted"] is False
        assert result["candidate_status"] == "rejected_forbidden_answer_key_window"


def test_proposed_u1_windows_are_accepted() -> None:
    for as_of_date, horizon_days in PROPOSED_U1_WINDOWS:
        result = validate_unseen_window_candidate(as_of_date, horizon_days)
        assert result["accepted"] is True
        assert result["candidate_status"] == "accepted_proposed_u1_candidate"


def test_u2_2025_window_set_uses_only_preregistered_windows(tmp_path: Path) -> None:
    result = check_unseen_window_readiness(_config(tmp_path, window_set="u2-2025"))

    actual = tuple(
        (item["as_of_date"], item["horizon_days"]) for item in result["windows"]
    )
    assert actual == PROPOSED_U2_WINDOWS
    assert not (set(actual) & set(CONSUMED_U1_WINDOWS))
    assert result["window_set"] == "u2-2025"
    assert result["provider_access"] is False
    assert result["outcomes_inspected"] is False


def test_u2_rejects_consumed_u1_and_forbidden_answer_key_windows() -> None:
    for as_of_date, horizon_days in CONSUMED_U1_WINDOWS:
        result = validate_unseen_window_candidate(
            as_of_date, horizon_days, window_set="u2-2025"
        )
        assert result["accepted"] is False
        assert result["candidate_status"] == "rejected_consumed_u1_window"

    for as_of_date, horizon_days in FORBIDDEN_ANSWER_KEY_WINDOWS:
        result = validate_unseen_window_candidate(
            as_of_date, horizon_days, window_set="u2-2025"
        )
        assert result["accepted"] is False
        assert result["candidate_status"] == "rejected_forbidden_answer_key_window"


def test_missing_u2_as_of_outputs_block_without_generation_or_fetch(
    tmp_path: Path,
) -> None:
    result = check_unseen_window_readiness(_config(tmp_path, window_set="u2-2025"))

    assert all(
        item["readiness_status"] == "blocked_missing_as_of_outputs"
        for item in result["windows"]
    )
    assert all(item["provider_access"] is False for item in result["windows"])
    assert result["provider_fetch_executed"] is False
    assert result["labels_calculated"] is False
    assert result["future_returns_recomputed"] is False


def test_ready_u2_fixture_is_not_deferred_by_2024_policy(tmp_path: Path) -> None:
    for as_of_date, _ in PROPOSED_U2_WINDOWS:
        _write_as_of_outputs(tmp_path / "outputs", as_of_date, ["sh.600000"])
    _write_cache(
        tmp_path / "cache",
        "stock_daily",
        "adjusted",
        "sh.600000",
        ["2024-01-02", "2026-06-24"],
    )
    _write_cache(
        tmp_path / "cache",
        "index_daily",
        "raw",
        "sh.000300",
        ["2024-01-02", "2026-06-24"],
    )

    result = check_unseen_window_readiness(_config(tmp_path, window_set="u2-2025"))

    assert all(item["readiness_status"] == "ready_for_dry_run" for item in result["windows"])
    assert all(item["benchmark_cache"]["status"] == "covered" for item in result["windows"])
    assert result["provider_access"] is False


def test_existing_u2_summary_is_presence_checked_but_not_opened(tmp_path: Path) -> None:
    as_of_date, horizon_days = PROPOSED_U2_WINDOWS[0]
    output = (
        tmp_path
        / "outputs"
        / "validation"
        / f"walk_forward_summary_{as_of_date}_{horizon_days}d.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("not valid json and must not be opened", encoding="utf-8")

    result = check_unseen_window_readiness(_config(tmp_path, window_set="u2-2025"))
    item = result["windows"][0]

    assert item["readiness_status"] == "blocked_existing_unseen_outputs"
    assert item["point_in_time_guard"]["status"] == "not_inspected_existing_validation_outputs"
    assert item["point_in_time_guard"]["outcome_fields_read"] == []
    assert result["outcomes_inspected"] is False


def test_u2_readiness_has_no_performance_fields(tmp_path: Path) -> None:
    result = check_unseen_window_readiness(_config(tmp_path, window_set="u2-2025"))
    forbidden_keys = {
        "average_future_return",
        "average_excess_return",
        "outperform_rate",
        "winner_capture_rate",
        "loser_contamination_rate",
        "hypothesis_result",
    }

    assert not (_all_keys(result) & forbidden_keys)


def test_missing_as_of_outputs_are_blocked_without_provider_access(
    tmp_path: Path,
) -> None:
    result = check_unseen_window_readiness(_config(tmp_path))

    assert result["provider_access"] is False
    assert result["provider_fetch_executed"] is False
    assert result["outcomes_inspected"] is False
    assert all(item["stock_cache"]["provider_fetch_required"] is None for item in result["windows"])
    assert all(
        item["readiness_status"] == "blocked_missing_as_of_outputs"
        for item in result["windows"]
    )
    assert all(item["prediction_rows_opened"] is False for item in result["windows"])


def test_ready_fixture_uses_cache_metadata_only(tmp_path: Path) -> None:
    for as_of_date, horizon_days in PROPOSED_U1_WINDOWS:
        _write_as_of_outputs(tmp_path / "outputs", as_of_date, ["sh.600000"])
        _write_cache(
            tmp_path / "cache",
            "stock_daily",
            "adjusted",
            "sh.600000",
            ["2024-01-02", "2026-06-24"],
        )
    _write_cache(
        tmp_path / "cache",
        "index_daily",
        "raw",
        "sh.000300",
        ["2024-01-02", "2026-06-24"],
    )

    result = check_unseen_window_readiness(_config(tmp_path))

    assert all(item["readiness_status"] == "ready_for_dry_run" for item in result["windows"])
    assert all(item["stock_cache"]["future_window_status"] == "covered" for item in result["windows"])
    assert all(item["benchmark_cache"]["status"] == "covered" for item in result["windows"])
    assert result["performance_metrics_computed"] is False
    assert result["future_returns_recomputed"] is False


def test_existing_validation_output_blocks_sealed_window_without_reading_it(
    tmp_path: Path,
) -> None:
    as_of_date = PROPOSED_U1_WINDOWS[0][0]
    _write_as_of_outputs(tmp_path / "outputs", as_of_date, ["sh.600000"])
    output = (
        tmp_path
        / "outputs"
        / "validation"
        / f"walk_forward_predictions_{as_of_date}_20d.csv"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "symbol,future_return\nsh.600000,999\n",
        encoding="utf-8",
    )

    result = check_unseen_window_readiness(_config(tmp_path))
    item = result["windows"][0]

    assert item["readiness_status"] == "blocked_existing_unseen_outputs"
    assert item["prediction_rows_opened"] is False
    assert result["outcomes_inspected"] is False


def test_readiness_output_has_no_performance_metric_fields(tmp_path: Path) -> None:
    result = check_unseen_window_readiness(_config(tmp_path))
    forbidden_keys = {
        "average_future_return",
        "average_excess_return",
        "outperform_rate",
        "winner_capture_rate",
        "loser_contamination_rate",
        "hypothesis_result",
    }

    assert not (_all_keys(result) & forbidden_keys)


def test_report_guardrails_and_output_paths(tmp_path: Path) -> None:
    result = check_unseen_window_readiness(_config(tmp_path))
    markdown = markdown_unseen_window_readiness(result)

    assert "readiness only, not validation" in markdown
    assert "have not been evaluated" in markdown
    assert "permanently forbidden as proof" in markdown
    assert "No unseen outcomes" in markdown
    paths = write_unseen_window_readiness(result, tmp_path / "outputs")
    assert Path(paths["json"]).name == "unseen_window_readiness_2024.json"
    assert Path(paths["markdown"]).name == "unseen_window_readiness_2024.md"
    payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert payload["provider_access"] is False


def test_u2_report_guardrails_and_output_paths_are_separate(tmp_path: Path) -> None:
    result = check_unseen_window_readiness(_config(tmp_path, window_set="u2-2025"))
    markdown = markdown_unseen_window_readiness(result)

    assert "U2 results remain sealed" in markdown
    assert "readiness only, not validation" in markdown
    assert "No unseen outcomes" in markdown
    paths = write_unseen_window_readiness(result, tmp_path / "outputs")
    assert Path(paths["json"]).name == "u2_window_readiness_2025.json"
    assert Path(paths["markdown"]).name == "u2_window_readiness_2025.md"
    assert Path(paths["json"]).name != "unseen_window_readiness_2024.json"


def _config(
    root: Path,
    *,
    window_set: str = "u1-2024",
) -> UnseenWindowReadinessConfig:
    return UnseenWindowReadinessConfig(
        outputs_dir=root / "outputs",
        cache_dir=root / "cache",
        limit=300,
        window_set=window_set,
    )


def _write_as_of_outputs(
    outputs_dir: Path,
    as_of_date: str,
    symbols: list[str],
) -> None:
    labels_dir = outputs_dir / "labels"
    daily_dir = outputs_dir / "daily"
    lists_dir = outputs_dir / "lists"
    labels_dir.mkdir(parents=True, exist_ok=True)
    daily_dir.mkdir(parents=True, exist_ok=True)
    lists_dir.mkdir(parents=True, exist_ok=True)
    rows = [{"symbol": symbol} for symbol in symbols]
    (labels_dir / f"stock_labels_{as_of_date}.json").write_text(
        json.dumps(rows), encoding="utf-8"
    )
    _write_symbol_csv(labels_dir / f"stock_labels_{as_of_date}.csv", symbols)
    _write_symbol_csv(daily_dir / f"factors_{as_of_date}.csv", symbols)
    list_ids = (
        "high_confidence_candidates",
        "trend_leaders",
        "long_term_stable",
        "breakout_watch",
        "accumulation_watch",
        "rebound_watch",
        "high_risk_active",
    )
    for list_id in list_ids:
        (lists_dir / f"{list_id}_{as_of_date}.json").write_text(
            json.dumps({"items": rows}), encoding="utf-8"
        )
    (lists_dir / f"multi_lists_{as_of_date}.json").write_text(
        json.dumps({"lists": {list_id: {"items": rows} for list_id in list_ids}}),
        encoding="utf-8",
    )


def _write_symbol_csv(path: Path, symbols: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["symbol"])
        writer.writeheader()
        writer.writerows({"symbol": symbol} for symbol in symbols)


def _write_cache(
    cache_dir: Path,
    dataset: str,
    adjust_key: str,
    symbol: str,
    dates: list[str],
) -> None:
    path = cache_dir / "baostock" / dataset / adjust_key / f"{symbol}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["symbol", "trade_date", "close"])
        writer.writeheader()
        writer.writerows(
            {"symbol": symbol, "trade_date": trade_date, "close": 10.0}
            for trade_date in dates
        )


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        result = set(value)
        for item in value.values():
            result.update(_all_keys(item))
        return result
    if isinstance(value, list):
        result: set[str] = set()
        for item in value:
            result.update(_all_keys(item))
        return result
    return set()
