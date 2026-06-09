# Data Source Strategy: China A-Share Prototype With Professional Architecture

## Core Decision

Version 1 focuses on A-share individual stock analysis.

Market context is allowed, but recommendation targets are restricted:

- Primary analysis target: A-share individual stocks.
- Core benchmark indices: CSI 300, CSI 500, ChiNext Index, and STAR 50.
- Background context: industry indices, sector themes, market breadth, turnover, valuation percentile, liquidity, and China-related macro context.
- Optional extension: China ETFs.
- Excluded from version 1 recommendations: US stocks, Hong Kong stocks, China ADRs, global equities, futures, options, FX, and commodities.

## Prototype Data Source Strategy

The first version should use free or open-source data sources for prototype development, while keeping the architecture compatible with professional data vendors later.

Priority:

1. AKShare.
2. BaoStock.
3. Tushare Pro as an optional provider.

The data source can be inexpensive during the prototype phase, but the architecture must be professional. The application must not be tightly coupled to a single free interface.

## Provider Layer Requirements

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
- Do not expose provider-specific column names to the frontend.
- Do not let recommendation logic depend on vendor response formats.
- Provider output must be normalized before storage or analysis.
- A future Wind, Choice, or iFinD adapter should be addable without rewriting analysis logic.

## Unified DataFrame Schema

All providers must output this exact DataFrame schema:

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

## Version 1 Data Coverage

Implement first:

- A-share individual stock daily bars.
- CSI 300 index daily bars.
- CSI 500 index daily bars.
- ChiNext Index daily bars.
- STAR 50 index daily bars.

Reserve for later:

- Industry indices.
- ETFs.
- Financial statement data.
- Valuation metrics.
- Announcement and filing data.
- Wind provider.
- Choice provider.
- iFinD provider.

## Local Cache

Free data interfaces should not be queried repeatedly for the same request.

Requirements:

- Add a local DataFrame cache.
- Cache by provider, method, symbol/index code, date range, and adjustment flag.
- Use a TTL so stale prototype data can be refreshed.
- Keep cache implementation separate from provider implementation.
- Do not treat local cache as the final production storage layer.

The current prototype cache is file-based and intended for development. Production should later use database-backed historical data plus Redis for hot data.

## Data Quality Rules

Each normalized provider response should be validated for:

- Required schema columns.
- Valid trading dates.
- Numeric OHLCV and amount fields.
- Non-empty source.
- Missing values.
- Sort order.

If minimum data is missing, the recommendation engine should return `数据不足` or `观察`, not a confident buy/sell rating.

## Implementation Status

Implemented in the first data-layer skeleton:

- `MarketDataProvider` base interface.
- `AkShareProvider`.
- `BaoStockProvider`.
- `TushareProvider`.
- Unified schema normalization and validation.
- File-based local DataFrame cache.
- `MarketDataService` as the provider-independent access layer.
- Example analysis module that depends only on the unified schema.
- Unit tests for schema normalization, cache behavior, and provider-independent analysis.
