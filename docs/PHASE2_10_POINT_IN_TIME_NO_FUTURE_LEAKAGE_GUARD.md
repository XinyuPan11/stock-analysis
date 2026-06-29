# Phase 2.10 Point-in-time Data Access and No Future Leakage Guard

## Purpose

Phase 2.9 extended the local daily cache through 2026-06-24. Historical research dates such as 2024-10-31 therefore share cache files with later observations. Phase 2.10 makes the date boundary explicit at every research and validation boundary so a larger cache cannot change historical features, scores, rankings, or candidate filtering.

This phase does not change scoring formulas, ranking formulas, factor formulas, or validation label definitions.

## Point-in-time Rule

For an `as_of_date`:

```text
feature / filter / factor / score / rank input: trade_date <= as_of_date
future-return label input:                    trade_date > as_of_date
```

The feature frame ends on `as_of_date` or the latest trading date before it. A future-return label may read later rows only inside its explicit evaluation window. Label rows are never passed back into candidate generation, factors, scoring, or ranking.

## Audited Paths

| Path | Point-in-time boundary |
| --- | --- |
| `data/cache.py` | `LocalCsvCache.get_market_data()` returns only the requested `start_date..end_date` range. |
| `research/pipeline.py` | Stock and benchmark frames are guarded again at `config.end_date` before filtering, factors, scoring, and ranking. |
| `research/ashare_filters.py` | The full daily frame is guarded before price-history and liquidity filters run. |
| `research/factors.py` | Stock and benchmark inputs are guarded before factor preparation whenever `as_of_date` is supplied. |
| `backtesting/walk_forward.py` | Stock and benchmark histories are guarded at each rebalance date before candidate generation. |
| `validation/future_returns.py` | One explicit split produces a feature frame at or before as-of and a label frame after as-of. |
| `validation/walk_forward.py` | Validation summaries retain the anti-leakage boundary and aggregate guard diagnostics. |

The cache range filter remains the first boundary. The research, factor, filter, backtest, and label guards are defense-in-depth boundaries for fake services, direct calls, and future changes that may return broader frames.

## Shared Guard

`stock_analysis.data.point_in_time` provides:

```text
slice_daily_as_of(frame, as_of_date)
split_daily_point_in_time(frame, as_of_date)
```

The utility:

- accepts normalized daily OHLCV data and an as-of date;
- preserves input row order;
- returns only rows whose date is on or before as-of for feature use;
- exposes future rows separately only for validation labels;
- raises a clear error when the date column is missing or malformed;
- reports the effective latest feature date and the maximum date observed at the guard boundary.

## Validation Boundary

Future-return calculation keeps the existing semantics:

1. The entry row must match `as_of_date`.
2. The feature side contains only `trade_date <= as_of_date`.
3. The label side contains only `trade_date > as_of_date`.
4. The first `horizon_days` trading rows after as-of form the evaluation window.
5. Benchmark labels use the same boundary.

The following diagnostic rules are emitted:

```text
feature_window_rule = trade_date <= as_of_date
label_window_rule = trade_date > as_of_date; first horizon_days trading rows
```

## Diagnostics

Research and validation summaries expose these fields where the path has an explicit as-of boundary:

| Field | Meaning |
| --- | --- |
| `as_of_date` | Historical feature cutoff. |
| `latest_input_date` | Latest date actually used by the feature side. |
| `max_raw_cache_date` | Maximum date observed in the frame presented to the guard. |
| `future_rows_excluded_count` | Rows after as-of excluded from feature use. |
| `leakage_guard_applied` | `true` when the point-in-time guard ran. |

`max_raw_cache_date` describes the frame visible at that boundary. `LocalCsvCache` may already have sliced a physical cache file, so it is not always the maximum date stored on disk.

## Regression Tests

The targeted tests cover:

- direct slicing with rows before and after as-of;
- malformed date rejection;
- a temporary daily CSV containing a deliberately future-dated row;
- factor results remaining unchanged when a future price spike is appended;
- liquidity filtering not using future turnover;
- research pipeline filtering, factors, scoring, and ranking receiving guarded frames;
- walk-forward candidate generation using only rebalance-date history;
- future-return labels using only the explicit post-as-of evaluation window;
- walk-forward summaries retaining anti-leakage diagnostics.

Run the short suite:

```powershell
python -m pytest backend\tests\test_point_in_time.py backend\tests\test_factors.py backend\tests\test_ashare_filters.py backend\tests\test_research_pipeline.py backend\tests\test_future_returns.py backend\tests\test_walk_forward_validation.py backend\tests\test_backtesting.py -q
```

No BaoStock access, prewarm, full workflow, or long validation is required.

## Safety and Non-goals

This phase:

- does not alter production scoring;
- does not alter recommendation ranking;
- does not alter factor calculations;
- does not alter future-return label definitions;
- does not generate new recommendations;
- does not make model-effectiveness claims.

## Remaining Limitations

1. The cached stock-universe file is a current snapshot. Historical listing, delisting, ST, and security-identity status are not yet versioned as point-in-time universe snapshots.
2. Historical labels, lists, factors, and experiment outputs are trusted by their dated filenames and existing generation contract. This phase does not add immutable provenance hashes.
3. `max_raw_cache_date` observes the frame at the guard boundary, not necessarily every row in the physical cache file.
4. This phase covers daily price/volume research paths. Financial statements, valuation, industry data, news, announcements, and policy data are outside the current price-only / technical-only scope.
5. No long full-market historical validation was run as part of this guard patch.
