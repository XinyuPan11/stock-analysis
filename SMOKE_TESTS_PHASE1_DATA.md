# Phase 1 Data Smoke Tests

## 2026-06-09: A-Share Universe, Daily Bars, Cache, And Incremental Coverage

Scope:

- A-share stock universe.
- Single-stock daily bars.
- Benchmark index daily bars.
- Unified schema validation.
- Local CSV cache under `data/cache/`.
- Coverage metadata so known non-trading days are not refetched repeatedly.

## Unit Tests

Command:

```powershell
python -m unittest discover -s backend\tests
```

Result:

- `Ran 9 tests`
- `OK`

Covered:

- provider normalization;
- stock universe normalization;
- cache read/write;
- incremental tail update;
- non-trading-day coverage cache;
- stock universe cache;
- service error wrapping.

## AKShare Smoke Test

Command:

```powershell
$env:HTTP_PROXY="http://127.0.0.1:8668"
$env:HTTPS_PROXY="http://127.0.0.1:8668"
$env:ALL_PROXY="http://127.0.0.1:8668"
python backend\scripts\smoke_market_data.py --provider akshare --symbol 000001 --start-date 2024-01-01 --end-date 2024-01-31 --include-universe --cache-dir data\cache\smoke-akshare
```

Result:

- Failed at provider network call to Eastmoney through proxy.
- Failure was raised as a clear `ProviderDataError`.
- No silent fallback or partial success was reported.

## BaoStock Smoke Test

Command:

```powershell
$env:HTTP_PROXY="http://127.0.0.1:8668"
$env:HTTPS_PROXY="http://127.0.0.1:8668"
python backend\scripts\smoke_market_data.py --provider baostock --symbol sz.000001 --start-date 2024-01-01 --end-date 2024-01-31 --include-universe --cache-dir data\cache\smoke-baostock-v3
```

Result:

- Provider: `baostock`
- Stock universe rows: `5493`
- Stock universe schema: `symbol, name, exchange, listing_status, source`
- Stock daily schema: `symbol, trade_date, open, high, low, close, volume, amount, adj_close, source`
- Stock: `sz.000001`
- Stock daily rows: `22`
- Stock first trade date: `2024-01-02`
- Stock last trade date: `2024-01-31`
- Benchmark: `CSI300`
- Benchmark daily rows: `22`
- Cache directory: `data/cache/smoke-baostock-v3`

Second run of the same command:

- Returned the same data.
- Did not print BaoStock `login success`.
- Confirmed the request was served from local cache.

## Notes

- `data/cache/` is ignored by Git.
- AKShare remains the preferred provider in design, but BaoStock is currently the verified network smoke provider in this Windows proxy environment.
- The pandas/numexpr warning is environment-level and does not block the data layer.
