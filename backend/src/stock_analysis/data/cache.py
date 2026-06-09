from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from time import time
from typing import Callable

import pandas as pd


@dataclass(frozen=True)
class CacheEntry:
    frame: pd.DataFrame
    created_at: float


class FileDataFrameCache:
    """Small local DataFrame cache for free-data providers.

    The cache uses pickle files so it does not require optional parquet engines.
    It is intended for local development and prototype data ingestion, not as a
    production market-data store.
    """

    def __init__(self, cache_dir: str | Path = ".cache/market_data", ttl_seconds: int = 3600) -> None:
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_or_fetch(self, key_parts: tuple[object, ...], fetcher: Callable[[], pd.DataFrame]) -> pd.DataFrame:
        cache_path = self._path_for(key_parts)
        if cache_path.exists():
            entry = pd.read_pickle(cache_path)
            if isinstance(entry, CacheEntry) and time() - entry.created_at <= self.ttl_seconds:
                return entry.frame.copy()

        frame = fetcher()
        pd.to_pickle(CacheEntry(frame=frame.copy(), created_at=time()), cache_path)
        return frame

    def _path_for(self, key_parts: tuple[object, ...]) -> Path:
        key = "|".join(str(part) for part in key_parts)
        digest = sha256(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.pkl"
