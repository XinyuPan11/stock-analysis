# Phase 2.7.1 List Quality Cleanup Summary

## Background

Phase 2.7 introduced multi-label outputs, multi-list outputs, read-only APIs, list pages, label filtering, stock search, and stock research detail pages.

Phase 2.7.1 fixes the quality boundary between:

- the full-market stock search index,
- the full-market label universe,
- and the Top N research lists.

The current view remains an as-of `2024-01-31` research snapshot. Factors are calculated from historical data available on or before `2024-01-31`; no data after that observation date is used.

## Non-Stock Examples Found

The regenerated static outputs identified non-stock instruments from existing local outputs and cache metadata. Examples include:

- `sz.399001` - 深证成份指数(价格)
- `sz.399002` - 深证成份指数(收益)
- `sz.399003` - 深证成份B股指数
- `sz.399004` - 深证100指数(收益)
- `sz.399005` - 中小企业100指数
- `sz.399006` - 创业板指数(价格)
- `sz.399008` - 中小企业300指数
- `sz.399009` - 深证200指数
- `sz.399010` - 深证700指数

These are excluded from stock research lists and recorded in `excluded_non_stock`.

## Three-Layer Structure

Phase 2.7.1 separates the research view into three layers.

### 1. Stock Index

The stock index is the broad searchable layer. It is generated from local static outputs only:

- `outputs/daily/factors_2024-01-31.json`
- `outputs/daily/candidates_2024-01-31.json`
- `outputs/errors/failed_symbols_2024-01-31.csv`
- `outputs/reports/stocks/`
- cached `stock_universe.csv`

Output:

- `outputs/search/stock_index_2024-01-31.json`

Latest regenerated counts:

- `item_count`: 5494
- `stock_count`: 5208
- `excluded_non_stock_count`: 286

### 2. Label Universe

The label universe now covers the broader stock universe, not only the Top 150 candidates.

Compatible outputs:

- `outputs/labels/candidate_labels_2024-01-31.json`
- `outputs/labels/candidate_labels_2024-01-31.csv`

Additional explicit outputs:

- `outputs/labels/stock_labels_2024-01-31.json`
- `outputs/labels/stock_labels_2024-01-31.csv`

Latest regenerated label count:

- `label_count`: 5208

### 3. Lists

Lists are Top N research views filtered from the valid stock label universe.

The intended flow is:

```text
all valid stock labels -> eligible filter -> sort -> top_n list
```

Each list records:

- `source_universe_count`
- `eligible_count`
- `top_n`
- `excluded_count`

## Filtering Rules

Added stock-only research universe filtering for:

- index symbols and names,
- bond or bond-index names,
- fund / ETF names,
- convertible bond names,
- clear non-stock symbol patterns.

The filter does not exclude normal listed companies merely because their names include `国` or because they are state-owned enterprises.

Excluded outputs:

- `outputs/labels/excluded_non_stock_2024-01-31.json`
- `outputs/labels/excluded_non_stock_2024-01-31.csv`

Each excluded row includes:

- `symbol`
- `name`
- `instrument_type`
- `excluded_reason`
- `source`

## Multi-List Candidate Pool Adjustments

The multi-list generator now works from the full label universe instead of only the previous Top 150 candidate label set.

Regenerated list examples:

- `trend_leaders`: 30 items from 304 eligible rows.
- `long_term_stable`: 30 items from 460 eligible rows.
- `accumulation_watch`: 30 items from 2083 eligible rows.
- `high_risk_active`: 30 items from 614 eligible rows.
- `insufficient_data`: 30 items from 743 eligible rows.

## Accumulation Watch Adjustment

`accumulation_watch` is no longer a direct copy of total-score leaders.

It now:

- excludes high-risk rows,
- avoids the top decile by `total_score`,
- emphasizes trend, momentum, relative strength, and risk control,
- and avoids complete overlap with `trend_leaders`.

The regenerated `trend_leaders` and `accumulation_watch` lists are not identical.

## Search Fallback Logic

Search now uses this priority:

1. `stock_index`
2. label universe
3. factors
4. failed symbols
5. reports

Observed behavior:

- `300119` / `sz.300119`: found via stock index and shown as present in the static research universe, even when not in a main list.
- `688585` / `sh.688585`: found as `数据不足` when it lacks factor output.
- failed symbols such as `sh.600930`: returned as `数据不足` with failed-symbol context.
- non-stock instruments such as `sz.399001`: returned as `非股票标的` and excluded from stock lists.
- unknown symbols return `count=0` for search or a friendly 404 for detail.

When an unprefixed six-digit query can match both a stock and a non-stock instrument, the search result prioritizes the stock. A prefixed query keeps exact exchange matching.

## Stock Detail Fallback Logic

`/api/stocks/{symbol}/research` and `/stocks/{symbol}` now support:

- full label-universe stocks,
- factors-only stocks,
- failed-symbol rows,
- excluded non-stock instruments,
- and friendly not-found responses.

## Source Display Strategy

User-facing list, label, search, and stock detail tables do not default to noisy `source` / `source_file` columns.

Source tracing is retained in:

- generated metadata,
- `excluded_non_stock` output,
- stock detail data quality context,
- and local debug/source files.

## Regenerated Outputs

The static research view generator was rerun for the fixed historical date:

```powershell
python backend\scripts\generate_research_views.py --date 2024-01-31 --outputs-dir outputs --cache-dir data\cache\daily-use
```

No workflow, prewarm, backtest, latest-date data pull, or BaoStock access was run.

## Tests

Commands run:

```powershell
python -m unittest backend\tests\test_multi_label.py backend\tests\test_multi_list.py backend\tests\test_api.py
python -m unittest discover -s backend\tests
```

Results:

- Targeted tests: 81 tests OK
- Full discovery: 195 tests OK

Only the existing pandas / numexpr warning appeared.

## Remaining Limitations

- The system is still price-only / technical-only.
- There is no industry, sector, fundamentals, valuation, news, or announcement layer.
- Real industry logic and supply-chain style discovery remain deferred to later phases.
- The factor-derived labels for stocks outside the candidate set are research-view labels, not changes to the Phase 1 scoring engine.
- Search does not include pinyin matching.
- Phase 2.7.2 should use walk-forward validation to evaluate whether list membership has future usefulness across multiple observation dates.

## Next Step

Recommended next step:

- merge Phase 2.7.1 after review,
- then proceed to Phase 2.7.2 walk-forward list validation,
- and only afterward return to Phase 2.8 controlled latest-date refresh.

