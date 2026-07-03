from __future__ import annotations

import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_analysis.research.feature_only_snapshot import find_outcome_columns
from stock_analysis.research.historical_asof_artifacts import (
    build_historical_asof_artifacts,
    write_historical_asof_artifacts,
)
from stock_analysis.research.historical_h1h5_readiness import (
    check_historical_window_readiness,
)
from stock_analysis.research.historical_source_snapshot_builder import (
    build_historical_source_snapshot,
    write_historical_source_snapshot_outputs,
)


AS_OF_DATE = "2026-01-30"


def test_safe_artifacts_feed_source_builder_and_readiness(
    tmp_path: Path,
) -> None:
    factors_path = tmp_path / "factors.csv"
    lists_path = tmp_path / "multi_lists.json"
    cache_dir = tmp_path / "cache"
    outputs_dir = tmp_path / "outputs"
    symbols = [f"sh.60{index:04d}" for index in range(100)]
    pd.DataFrame(
        [
            {
                "symbol": symbol,
                "as_of_date": AS_OF_DATE,
                "momentum_20d": 0.02,
                "volatility_20d": 0.01,
                "source": "cache_only_test",
            }
            for symbol in symbols
        ]
    ).to_csv(factors_path, index=False)
    lists_path.write_text(
        json.dumps(
            {
                "as_of_date": AS_OF_DATE,
                "lists": [
                    {
                        "list_id": "breakout_watch",
                        "list_name": "breakout",
                        "as_of_date": AS_OF_DATE,
                        "items": [
                            {
                                "symbol": symbols[0],
                                "rank": 1,
                                "total_score": 80,
                                "label_reason": "must be dropped",
                            }
                        ],
                    },
                    {
                        "list_id": "accumulation_watch",
                        "list_name": "accumulation",
                        "as_of_date": AS_OF_DATE,
                        "items": [
                            {
                                "symbol": symbols[1],
                                "rank": 2,
                                "total_score": 75,
                            }
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    for index, symbol in enumerate(symbols):
        _write_daily_cache(cache_dir, symbol, price_offset=index / 100)

    def forbidden_network(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"Unexpected network access: {args} {kwargs}")

    with patch.object(socket, "create_connection", forbidden_network):
        artifacts = build_historical_asof_artifacts(
            as_of_date=AS_OF_DATE,
            factors_file=factors_path,
            multi_list_file=lists_path,
        )
        artifact_paths = write_historical_asof_artifacts(
            artifacts,
            outputs_dir=outputs_dir,
        )
        source = build_historical_source_snapshot(
            as_of_date=AS_OF_DATE,
            factors_file=artifact_paths["factors_csv"],
            membership_file=artifact_paths["membership_csv"],
            cache_dir=cache_dir,
        )
        source_paths = write_historical_source_snapshot_outputs(
            source,
            outputs_dir=outputs_dir,
        )

    assert artifacts.metadata["dropped_unsafe_fields"] == ["label_reason"]
    assert find_outcome_columns(source.frame.columns) == []
    assert source.metadata["provider_access"] is False
    assert source.metadata["labels_joined"] is False
    assert len(source.frame) == 100
    generated = sorted(
        path.relative_to(outputs_dir).as_posix()
        for path in outputs_dir.rglob("*")
        if path.is_file()
    )
    assert generated == [
        f"experiments/historical_h1h5_factors_{AS_OF_DATE}.csv",
        f"experiments/historical_h1h5_membership_{AS_OF_DATE}.csv",
        f"experiments/historical_h1h5_source_snapshot_{AS_OF_DATE}.csv",
        f"experiments/historical_h1h5_source_snapshot_{AS_OF_DATE}.json",
    ]
    assert not list(outputs_dir.rglob("*feature*"))
    assert not list(outputs_dir.rglob("*cohort*"))

    configs = ROOT.parent / "research" / "configs"
    readiness = check_historical_window_readiness(
        expected_as_of_date=AS_OF_DATE,
        source_config_path=(
            configs / "opportunity_cohorts.phase3_1_smoke.json"
        ),
        historical_config_path=(
            configs / f"opportunity_cohorts.historical_{AS_OF_DATE}.json"
        ),
        source_snapshot_path=source_paths["csv"],
        feature_only_snapshot_path=tmp_path / "missing-feature-only.csv",
    )
    assert readiness["status"] == "blocked_missing_feature_only_snapshot"
    assert readiness["provider_access"] is False
    assert readiness["labels_joined"] is False
    assert readiness["validation_run"] is False


def _write_daily_cache(
    cache_dir: Path,
    symbol: str,
    *,
    price_offset: float,
) -> None:
    path = (
        cache_dir
        / "baostock"
        / "stock_daily"
        / "adjusted"
        / f"{symbol}.csv"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    dates = list(pd.bdate_range(end=AS_OF_DATE, periods=70))
    dates.extend(pd.bdate_range(start="2026-02-02", periods=2))
    pd.DataFrame(
        [
            {
                "symbol": symbol,
                "trade_date": trade_date.strftime("%Y-%m-%d"),
                "close": 10.0 + price_offset + index * 0.02,
                "adj_close": 10.0 + price_offset + index * 0.02,
                "amount": 1_000_000 + index * 10_000,
                "volume": 100_000 + index * 1_000,
                "source": "synthetic_safe_test",
            }
            for index, trade_date in enumerate(dates)
        ]
    ).to_csv(path, index=False)
