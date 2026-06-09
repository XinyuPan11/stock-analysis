# Data Source Strategy: Personal A-Share Daily Research MVP

## 1. Core Decision

Phase 1 focuses on daily after-close A-share individual stock research for personal use.

Market context is allowed, but recommendation targets are restricted:

- Primary analysis target: A-share individual stocks.
- Core benchmark indices: CSI 300, CSI 500, ChiNext Index, and STAR 50.
- Background context: industry indices, sector themes, market breadth, turnover, valuation percentile, liquidity, and China-related macro context.
- Optional later extension: China ETFs.
- Excluded from Phase 1 recommendations: US stocks, Hong Kong stocks, China ADRs, global equities, futures, options, FX, commodities, and ETFs.

## 2. Phase 1 Data Source Strategy

Phase 1 should use free or open-source data sources for prototype development, while keeping the architecture compatible with professional data vendors later.

Priority:

1. AKShare.
2. BaoStock.
3. Tushare Pro as an optional provider.

The data source can be inexpensive during the prototype phase, but the architecture must be professional. The application must not be tightly coupled to a single free interface.

Phase 1 does not integrate Wind, Choice, iFinD, real-time tick feeds, paid news feeds, or institutional data terminals. Those stay in Phase 6.

## 3. Provider Layer Requirements

Data-source calls must live behind a provider layer:

```text
backend/src/stock_analysis/data/providers/
  base.py
  akshare_provider.py
  baostock_provider.py
  tushare_provider.py
```

Rules:

- Do not call AKShare, BaoStock, or Tushare directly from analysis modules.
- Do not expose provider-specific column names to reports or future frontend code.
- Do not let recommendation logic depend on vendor response formats.
- Provider output must be normalized before storage, analysis, reporting, or backtesting.
- Future Wind, Choice, or iFinD adapters should be addable without rewriting analysis logic.

## 4. Unified DataFrame Schema

All providers must output this exact market-data DataFrame schema:

| Column | Meaning |
| --- | --- |
| `symbol` | Internal stock or index symbol |
| `trade_date` | Trading date as `YYYY-MM-DD` |
| `open` | Open price |
| `high` | High price |
| `low` | Low price |
| `close` | Close price |
| `volume` | Trading volume |
| `amount` | Trading amount |
| `adj_close` | Adjusted close price |
| `source` | Data source name |

Analysis modules must depend only on this schema.

## 5. Phase 1 Data Coverage

Implement first:

- A-share stock universe.
- A-share individual stock daily bars.
- CSI 300 index daily bars.
- CSI 500 index daily bars.
- ChiNext Index daily bars.
- STAR 50 index daily bars.
- Data source, data date, and update time metadata.

Reserve for later:

- Industry indices.
- ETFs.
- Financial statement data.
- Valuation metrics.
- Announcement and filing data.
- Wind provider.
- Choice provider.
- iFinD provider.
- Real-time or near-real-time data.

## 6. Local Cache And Incremental Update

Free data interfaces should not be queried repeatedly for the same request.

Requirements:

- Add a local DataFrame cache.
- Cache by provider, method, symbol/index code, date range, and adjustment flag.
- Use a TTL so stale prototype data can be refreshed.
- Keep cache implementation separate from provider implementation.
- Add an incremental update path for daily after-close data.
- Do not treat local cache as the final production storage layer.

The current prototype cache is file-based and intended for personal research and development. A database-backed historical store can be added later if Phase 2+ requires it.

## 7. Data Quality Rules

Each normalized provider response should be validated for:

- Required schema columns.
- Valid trading dates.
- Numeric OHLCV and amount fields.
- Non-empty source.
- Missing values.
- Sort order.
- Sufficient history for factor calculation and backtesting.

If minimum data is missing, the recommendation engine should return `数据不足` or `观察`, not a confident candidate label and never deterministic buy/sell advice.

## 8. Phase 1 Filter Data Requirements

Phase 1 filters need enough metadata and daily-bar history to:

- filter ST and *ST stocks;
- filter delisting-board or delisting-risk stocks;
- filter stocks listed fewer than 180 days;
- filter long-suspended stocks;
- filter stocks with low recent 20-day trading amount;
- handle limit-up and limit-down edge cases;
- handle adjusted prices;
- handle missing data;
- respect the A-share trading calendar.

If a free provider cannot supply one field reliably, the filter should either use a documented fallback or mark the stock as `数据不足`.

## 9. Current Implementation Status

Already implemented:

- `MarketDataProvider` base interface.
- `AkShareProvider`.
- `BaoStockProvider`.
- `TushareProvider`.
- Unified schema normalization and validation.
- File-based local DataFrame cache.
- `MarketDataService` as the provider-independent access layer.
- Example analysis module that depends only on the unified schema.
- Unit tests for schema normalization, cache behavior, and provider-independent analysis.
- Real-data smoke test CLI: `python backend/scripts/smoke_market_data.py --provider akshare --symbol 000001 --index-code CSI300`.
- Verified AKShare real-data smoke test for A-share `000001` and `CSI300`.
- Verified BaoStock real-data smoke test for A-share `sz.000001` and `CSI300`.

Planned next Phase 1 modules are documented in `PHASE1_TASKS.md`.

## 10. Smoke Test Command

Use the local Windows proxy when running network-backed data checks in this environment:

```powershell
$env:HTTP_PROXY="http://127.0.0.1:8668"
$env:HTTPS_PROXY="http://127.0.0.1:8668"
python backend/scripts/smoke_market_data.py --provider akshare --symbol 000001 --index-code CSI300 --start-date 2024-01-01 --end-date 2024-01-31
```

The command should return JSON containing:

- normalized schema columns;
- A-share stock row count and return summary;
- benchmark index row count and return summary;
- local cache directory path.
