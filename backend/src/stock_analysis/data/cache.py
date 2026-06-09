from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Callable

import pandas as pd

from stock_analysis.data.schemas import validate_market_data_frame, validate_stock_universe_frame


@dataclass(frozen=True)
class MissingDateRanges:
    ranges: list[tuple[str, str]]

    @property
    def is_empty(self) -> bool:
        return not self.ranges


class LocalCsvCache:
    """Local CSV cache for Phase 1 daily A-share research data.

    The storage location defaults to ``data/cache/`` at the repository root.
    Files are organized by provider and dataset so the implementation can later
    be swapped for parquet or a database-backed store without changing service
    callers.
    """

    def __init__(self, cache_dir: str | Path = "data/cache") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_market_data(
        self,
        *,
        provider: str,
        dataset: str,
        symbol: str,
        start_date: str,
        end_date: str,
        adjusted: bool,
        fetcher: Callable[[str, str], pd.DataFrame],
    ) -> pd.DataFrame:
        path = self._market_path(provider=provider, dataset=dataset, symbol=symbol, adjusted=adjusted)
        coverage_path = path.with_suffix(".coverage.json")
        cached = self._read_market(path)
        coverage = self._read_coverage(coverage_path)
        missing = self._missing_ranges(cached, start_date=start_date, end_date=end_date, coverage=coverage)

        if not missing.is_empty:
            fetched_frames = [fetcher(start, end) for start, end in missing.ranges]
            cached = self._merge_market_frames([cached, *fetched_frames])
            self._write_market(path, cached)
            self._write_coverage(coverage_path, start_date=start_date, end_date=end_date, existing=coverage)

        return self._slice_market(cached, start_date=start_date, end_date=end_date)

    def get_stock_universe(self, *, provider: str, fetcher: Callable[[], pd.DataFrame]) -> pd.DataFrame:
        path = self.cache_dir / provider / "stock_universe.csv"
        if path.exists():
            return validate_stock_universe_frame(pd.read_csv(path, dtype=str))

        frame = validate_stock_universe_frame(fetcher())
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False, encoding="utf-8")
        return frame.copy()

    def _market_path(self, *, provider: str, dataset: str, symbol: str, adjusted: bool) -> Path:
        safe_symbol = str(symbol).replace("/", "_").replace("\\", "_").replace(":", "_")
        adjust_key = "adjusted" if adjusted else "raw"
        return self.cache_dir / provider / dataset / adjust_key / f"{safe_symbol}.csv"

    def _read_market(self, path: Path) -> pd.DataFrame:
        if not path.exists():
            return pd.DataFrame()
        return validate_market_data_frame(pd.read_csv(path, dtype={"symbol": str, "trade_date": str, "source": str}))

    def _write_market(self, path: Path, frame: pd.DataFrame) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        validate_market_data_frame(frame).to_csv(path, index=False, encoding="utf-8")

    def _merge_market_frames(self, frames: list[pd.DataFrame]) -> pd.DataFrame:
        non_empty = [frame for frame in frames if frame is not None and not frame.empty]
        if not non_empty:
            return pd.DataFrame()
        return validate_market_data_frame(pd.concat(non_empty, ignore_index=True))

    def _slice_market(self, frame: pd.DataFrame, *, start_date: str, end_date: str) -> pd.DataFrame:
        if frame.empty:
            return frame
        valid = validate_market_data_frame(frame)
        return valid[(valid["trade_date"] >= start_date) & (valid["trade_date"] <= end_date)].reset_index(drop=True)

    def _missing_ranges(
        self,
        cached: pd.DataFrame,
        *,
        start_date: str,
        end_date: str,
        coverage: tuple[str, str] | None = None,
    ) -> MissingDateRanges:
        if coverage is not None:
            covered_start, covered_end = coverage
            ranges: list[tuple[str, str]] = []
            if start_date < covered_start:
                ranges.append((start_date, _date_offset(covered_start, -1)))
            if end_date > covered_end:
                ranges.append((_date_offset(covered_end, 1), end_date))
            return MissingDateRanges(ranges)

        if cached.empty:
            return MissingDateRanges([(start_date, end_date)])

        valid = validate_market_data_frame(cached)
        cached_start = str(valid["trade_date"].min())
        cached_end = str(valid["trade_date"].max())
        ranges: list[tuple[str, str]] = []

        if start_date < cached_start:
            previous_day = _date_offset(cached_start, -1)
            ranges.append((start_date, previous_day))
        if end_date > cached_end:
            next_day = _date_offset(cached_end, 1)
            ranges.append((next_day, end_date))

        return MissingDateRanges(ranges)

    def _read_coverage(self, path: Path) -> tuple[str, str] | None:
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        start = payload.get("covered_start")
        end = payload.get("covered_end")
        if not start or not end:
            return None
        return str(start), str(end)

    def _write_coverage(
        self,
        path: Path,
        *,
        start_date: str,
        end_date: str,
        existing: tuple[str, str] | None,
    ) -> None:
        if existing is None:
            covered_start, covered_end = start_date, end_date
        else:
            covered_start = min(existing[0], start_date)
            covered_end = max(existing[1], end_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump({"covered_start": covered_start, "covered_end": covered_end}, handle, ensure_ascii=False, indent=2)


def _date_offset(value: str, days: int) -> str:
    return (pd.Timestamp(value) + pd.Timedelta(days=days)).strftime("%Y-%m-%d")


# Backward-compatible alias for existing callers/tests from the first skeleton.
FileDataFrameCache = LocalCsvCache
