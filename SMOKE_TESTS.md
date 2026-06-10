# Smoke Tests

## 2026-06-09: Real A-Share Daily Data Through Provider Layer

Purpose:

- Verify that real A-share daily data can be fetched through replaceable providers.
- Verify that provider output is normalized to the unified DataFrame schema.
- Verify that analysis modules can consume normalized data without importing AKShare, BaoStock, or Tushare directly.
- Verify that local caching is wired into `MarketDataService`.

Environment note:

- Windows network access used local proxy `http://127.0.0.1:8668`.

## Offline Unit Tests

Command:

```powershell
python -m unittest discover -s backend\tests
```

Result:

- `Ran 3 tests`
- `OK`

## AKShare Smoke Test

Command:

```powershell
$env:HTTP_PROXY="http://127.0.0.1:8668"
$env:HTTPS_PROXY="http://127.0.0.1:8668"
$env:ALL_PROXY="http://127.0.0.1:8668"
python backend\scripts\smoke_market_data.py --provider akshare --symbol 000001 --index-code CSI300 --start-date 2024-01-01 --end-date 2024-01-31
```

Result summary:

- Provider: `akshare`
- Schema: `symbol, trade_date, open, high, low, close, volume, amount, adj_close, source`
- Stock: `000001`
- Stock rows: `22`
- Stock first trade date: `2024-01-02`
- Stock last trade date: `2024-01-31`
- Stock total return: `0.03267973856209161`
- Stock max drawdown: `-0.03084832904884316`
- Index: `CSI300`
- Index display name: `沪深300`
- Index rows: `22`
- Index total return: `-0.050496817814568606`
- Index max drawdown: `-0.050496817814568606`

## BaoStock Smoke Test

Command:

```powershell
$env:HTTP_PROXY="http://127.0.0.1:8668"
$env:HTTPS_PROXY="http://127.0.0.1:8668"
$env:ALL_PROXY="http://127.0.0.1:8668"
python backend\scripts\smoke_market_data.py --provider baostock --symbol sz.000001 --index-code CSI300 --start-date 2024-01-01 --end-date 2024-01-31 --cache-dir backend\.cache\baostock-fixed
```

Result summary:

- Provider: `baostock`
- Schema: `symbol, trade_date, open, high, low, close, volume, amount, adj_close, source`
- Stock: `sz.000001`
- Stock rows: `22`
- Stock first trade date: `2024-01-02`
- Stock last trade date: `2024-01-31`
- Stock total return: `0.0271444082518999`
- Stock max drawdown: `-0.025695931477516032`
- Index: `CSI300`
- Index display name: `沪深300`
- Index rows: `22`
- Index total return: `-0.05049693295340041`
- Index max drawdown: `-0.05049693295340041`

## Notes

- AKShare and BaoStock can produce different adjusted prices and volume units. This is expected and reinforces the need to keep `source` in the unified schema.
- BaoStock uses provider-specific query symbols such as `sh.000300`, but the normalized output now preserves the internal index code `CSI300`.
- The pandas/numexpr warning observed during tests is environment-level and does not block current data-layer validation.
