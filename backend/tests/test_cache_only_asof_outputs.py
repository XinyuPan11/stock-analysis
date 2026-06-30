from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pandas as pd
import pytest


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "src"))
sys.path.insert(0, str(BACKEND / "scripts"))

from generate_cache_only_asof_daily_outputs import main, parse_args
from stock_analysis.data.providers.baostock_provider import BaoStockProvider
from stock_analysis.research.cache_only_asof import (
    CacheOnlyAsOfConfig,
    CacheOnlyDataMissingError,
    generate_cache_only_asof_daily_outputs,
)


AS_OF_DATE = "2024-02-29"
SYMBOL = "sh.600000"


def test_provider_is_not_constructed_or_called(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_complete_fixture(tmp_path)

    def forbidden_provider_init(*args, **kwargs):
        raise AssertionError("provider construction is forbidden")

    monkeypatch.setattr(BaoStockProvider, "__init__", forbidden_provider_init)

    result = generate_cache_only_asof_daily_outputs(_config(tmp_path))

    assert result["status"] == "ok"
    assert result["provider_access"] is False
    assert result["provider_fallback_available"] is False


def test_missing_symbol_cache_fails_before_writing_outputs(tmp_path: Path) -> None:
    _write_complete_fixture(tmp_path, write_stock_cache=False)

    with pytest.raises(CacheOnlyDataMissingError) as exc_info:
        generate_cache_only_asof_daily_outputs(_config(tmp_path))

    assert exc_info.value.missing_symbols == [SYMBOL]
    assert exc_info.value.as_dict()["provider_access"] is False
    assert not (tmp_path / "outputs" / "daily").exists()


def test_missing_benchmark_cache_fails_closed(tmp_path: Path) -> None:
    _write_complete_fixture(tmp_path, write_benchmark_cache=False)

    with pytest.raises(CacheOnlyDataMissingError) as exc_info:
        generate_cache_only_asof_daily_outputs(_config(tmp_path))

    assert exc_info.value.benchmark_missing is True
    assert not (tmp_path / "outputs" / "daily").exists()


def test_index_daily_csi300_cache_is_recognized(tmp_path: Path) -> None:
    _write_complete_fixture(tmp_path, write_benchmark_cache=False)
    dates = pd.date_range("2023-01-02", "2024-03-05", freq="B").strftime(
        "%Y-%m-%d"
    ).tolist()
    _write_market_cache(
        tmp_path / "cache",
        dataset="index_daily",
        adjusted=False,
        symbol="CSI300",
        dates=dates,
        growth=1.0,
    )

    result = generate_cache_only_asof_daily_outputs(_config(tmp_path))

    assert result["benchmark_symbol"] == "CSI300"
    assert result["provider_access"] is False


def test_split_benchmark_alias_cache_covers_full_feature_window(
    tmp_path: Path,
) -> None:
    _write_complete_fixture(
        tmp_path,
        write_stock_cache=False,
        write_benchmark_cache=False,
    )
    stock_dates = pd.date_range("2023-01-02", "2024-12-10", freq="B").strftime(
        "%Y-%m-%d"
    ).tolist()
    early_benchmark_dates = pd.date_range(
        "2022-09-05", "2024-10-31", freq="B"
    ).strftime("%Y-%m-%d").tolist()
    recent_benchmark_dates = pd.date_range(
        "2024-02-01", "2024-12-10", freq="B"
    ).strftime("%Y-%m-%d").tolist()
    _write_market_cache(
        tmp_path / "cache",
        dataset="stock_daily",
        adjusted=True,
        symbol=SYMBOL,
        dates=stock_dates,
        growth=1.4,
    )
    _write_market_cache(
        tmp_path / "cache",
        dataset="index_daily",
        adjusted=False,
        symbol="CSI300",
        dates=early_benchmark_dates,
        growth=1.0,
    )
    _write_market_cache(
        tmp_path / "cache",
        dataset="stock_daily",
        adjusted=True,
        symbol="sh.000300",
        dates=recent_benchmark_dates,
        growth=1.0,
    )
    config = CacheOnlyAsOfConfig(
        as_of_date="2024-11-29",
        outputs_dir=tmp_path / "outputs",
        cache_dir=tmp_path / "cache",
        limit=1,
        top_n=1,
    )

    result = generate_cache_only_asof_daily_outputs(config)

    assert result["benchmark_symbol"] == "sh.000300"
    assert result["latest_input_date"] == "2024-11-29"
    assert result["provider_access"] is False


@pytest.mark.parametrize(
    "forbidden_date",
    ["2024-01-31", "2024-04-30", "2024-07-31", "2024-10-31"],
)
def test_forbidden_answer_key_dates_are_rejected(forbidden_date: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Forbidden answer-key date"):
        generate_cache_only_asof_daily_outputs(
            CacheOnlyAsOfConfig(
                as_of_date=forbidden_date,
                outputs_dir=tmp_path / "outputs",
                cache_dir=tmp_path / "cache",
            )
        )


def test_point_in_time_guard_excludes_future_cache_rows(tmp_path: Path) -> None:
    _write_complete_fixture(tmp_path)

    result = generate_cache_only_asof_daily_outputs(_config(tmp_path))
    summary = json.loads(
        Path(result["output_paths"]["summary_json"]).read_text(encoding="utf-8")
    )
    factors = pd.read_csv(result["output_paths"]["factors_csv"])

    assert result["latest_input_date"] <= AS_OF_DATE
    assert result["max_raw_cache_date"] > AS_OF_DATE
    assert result["future_rows_excluded_count"] >= 2
    assert result["point_in_time_guard_applied"] is True
    assert not factors.empty
    assert factors["as_of_date"].eq(AS_OF_DATE).all()
    assert summary["latest_input_date"] <= AS_OF_DATE
    assert summary["cache_only"] is True


def test_metadata_and_outputs_have_no_performance_fields(tmp_path: Path) -> None:
    _write_complete_fixture(tmp_path)

    result = generate_cache_only_asof_daily_outputs(_config(tmp_path))
    forbidden = {
        "future_return",
        "future_excess_return",
        "average_future_return",
        "average_excess_return",
        "winner_capture_rate",
        "loser_contamination_rate",
        "hypothesis_result",
    }

    assert result["cache_only"] is True
    assert result["provider_access"] is False
    assert result["missing_cache_count"] == 0
    assert result["symbol_count"] == 1
    assert result["future_labels_calculated"] is False
    assert result["validation_outputs_generated"] is False
    assert not (_all_keys(result) & forbidden)
    assert Path(result["output_paths"]["candidates_json"]).exists()
    assert Path(result["output_paths"]["factors_json"]).exists()
    assert not (tmp_path / "outputs" / "validation").exists()


def test_cli_argument_validation(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        parse_args([])
    capsys.readouterr()

    exit_code = main(
        [
            "--date",
            "not-a-date",
            "--outputs-dir",
            str(tmp_path / "outputs"),
            "--cache-dir",
            str(tmp_path / "cache"),
        ]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["status"] == "blocked_invalid_request"
    assert payload["provider_access"] is False


def _config(root: Path) -> CacheOnlyAsOfConfig:
    return CacheOnlyAsOfConfig(
        as_of_date=AS_OF_DATE,
        outputs_dir=root / "outputs",
        cache_dir=root / "cache",
        limit=1,
        top_n=1,
    )


def _write_complete_fixture(
    root: Path,
    *,
    write_stock_cache: bool = True,
    write_benchmark_cache: bool = True,
) -> None:
    cache_dir = root / "cache"
    universe_path = cache_dir / "baostock" / "stock_universe.csv"
    universe_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "symbol": SYMBOL,
                "name": "Pudong Bank",
                "exchange": "SSE",
                "listing_status": "listed",
                "listing_date": "1999-11-10",
                "delisting_date": "",
                "is_st": "",
                "source": "unit",
            }
        ]
    ).to_csv(universe_path, index=False, encoding="utf-8")
    dates = pd.date_range("2023-01-02", "2024-03-05", freq="B").strftime(
        "%Y-%m-%d"
    ).tolist()
    if write_stock_cache:
        _write_market_cache(
            cache_dir,
            dataset="stock_daily",
            adjusted=True,
            symbol=SYMBOL,
            dates=dates,
            growth=1.4,
        )
    if write_benchmark_cache:
        _write_market_cache(
            cache_dir,
            dataset="index_daily",
            adjusted=False,
            symbol="sh.000300",
            dates=dates,
            growth=1.0,
        )


def _write_market_cache(
    cache_dir: Path,
    *,
    dataset: str,
    adjusted: bool,
    symbol: str,
    dates: list[str],
    growth: float,
) -> None:
    adjust_key = "adjusted" if adjusted else "raw"
    path = cache_dir / "baostock" / dataset / adjust_key / f"{symbol}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    prices = [10.0 + growth * index / 100 for index in range(len(dates))]
    frame = pd.DataFrame(
        {
            "symbol": [symbol] * len(dates),
            "trade_date": dates,
            "open": prices,
            "high": [value + 0.2 for value in prices],
            "low": [value - 0.2 for value in prices],
            "close": prices,
            "volume": [10_000_000] * len(dates),
            "amount": [100_000_000] * len(dates),
            "adj_close": prices,
            "source": ["unit"] * len(dates),
        }
    )
    frame.to_csv(path, index=False, encoding="utf-8")
    path.with_suffix(".coverage.json").write_text(
        json.dumps(
            {
                "covered_start": min(dates),
                "covered_end": max(dates),
            }
        ),
        encoding="utf-8",
    )


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for item in value.values():
            keys.update(_all_keys(item))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for item in value:
            keys.update(_all_keys(item))
        return keys
    return set()
