# Phase 2.21 Fail-Closed Cache-Only As-Of Output Path

## Purpose

Phase 2.21 adds a dedicated way to generate one historical as-of
`candidates`/`factors` set without provider access. It exists because
`run_daily_research.py` is cache-first, not provider-disabled: missing cache
can trigger its configured market-data provider.

The new path has no provider object and no fetch callback. Missing stock,
benchmark, universe, or coverage metadata blocks the run before daily outputs
are written.

## Scope

This path:

- reads one explicit historical date
- reads the cached stock universe and daily CSV files
- checks metadata and actual CSV coverage consistency
- applies the existing Phase 2.10 point-in-time guard
- reuses unchanged filters, factors, scoring, and ranking
- writes daily candidates, factors, factor explanations, and safety metadata

It does not:

- calculate future-return labels
- write walk-forward predictions
- summarize list or factor performance
- identify winners or losers
- evaluate Phase 2.17 hypotheses
- generate research lists automatically
- run for all U1 dates automatically
- access BaoStock or any other provider

## Forbidden Answer-Key Dates

The CLI rejects:

```text
2024-01-31
2024-04-30
2024-07-31
2024-10-31
```

The internal override is available only to deterministic unit tests and is
not exposed by the CLI.

## Fail-Closed Contract

Before invoking the existing research pipeline, the generator:

1. validates the explicit date and controlled limit;
2. loads `data/cache/daily-use/baostock/stock_universe.csv`;
3. selects the requested symbols from that cached universe;
4. requires complete stock cache coverage for the one-year feature lookback
   through the as-of date;
5. resolves `CSI300` through established benchmark aliases and requires its
   cache coverage;
6. stops before writing outputs when any prerequisite is missing.

`LocalCsvCache.market_data_coverage_details()` checks both coverage metadata
and the actual CSV end date. Stale metadata cannot make a missing CSV range
look complete.

The cache-only service deliberately returns physical cache rows after the
as-of date to the existing research pipeline. The Phase 2.10 guard immediately
removes them before filtering, factors, scoring, and ranking. This retains
auditable diagnostics:

```text
latest_input_date <= as_of_date
max_raw_cache_date
future_rows_excluded_count
point_in_time_guard_applied = true
```

## Output Metadata

`outputs/daily/summary_<date>.json` includes:

```text
provider_access = false
cache_only = true
provider_fallback_available = false
as_of_date
latest_input_date
max_raw_cache_date
future_rows_excluded_count
point_in_time_guard_applied = true
missing_cache_count
symbol_count
benchmark_symbol
outcomes_inspected = false
future_labels_calculated = false
validation_outputs_generated = false
performance_metrics_computed = false
```

## Future Manual Command: First U1 Date

Run one date only after this phase is merged:

```powershell
python backend\scripts\generate_cache_only_asof_daily_outputs.py `
    --date 2024-02-29 `
    --outputs-dir outputs `
    --cache-dir data\cache\daily-use `
    --provider baostock `
    --benchmark CSI300 `
    --limit 300 `
    --top-n 20
```

Expected daily outputs:

```text
outputs/daily/candidates_2024-02-29.csv
outputs/daily/candidates_2024-02-29.json
outputs/daily/factors_2024-02-29.csv
outputs/daily/factors_2024-02-29.json
outputs/daily/factor_explanations_2024-02-29.csv
outputs/daily/factor_explanations_2024-02-29.json
outputs/daily/summary_2024-02-29.json
```

If the command reports `blocked_missing_cache`, stop. Do not prewarm or
substitute `run_daily_research.py` in this phase.

## Optional Symbols File

Use a plain-text symbol file or a CSV containing a `symbol` column:

```powershell
python backend\scripts\generate_cache_only_asof_daily_outputs.py `
    --date 2024-02-29 `
    --outputs-dir outputs `
    --cache-dir data\cache\daily-use `
    --provider baostock `
    --benchmark CSI300 `
    --limit 300 `
    --symbols-file outputs\cache_plans\u1_symbols_2024-02-29.txt
```

Symbols absent from the cached universe are rejected.

## Generate Research Views Afterwards

Only after the daily summary confirms the cache-only and point-in-time
contract:

```powershell
python backend\scripts\generate_research_views.py `
    --date 2024-02-29 `
    --outputs-dir outputs `
    --cache-dir data\cache\daily-use `
    --top-n 30
```

This creates the as-of research labels and list artifacts required by Phase
2.19. These are research classifications, not future-return labels.

## Re-Run Phase 2.19 Readiness

```powershell
python backend\scripts\check_unseen_window_readiness.py `
    --outputs-dir outputs `
    --cache-dir data\cache\daily-use `
    --provider baostock `
    --benchmark CSI300 `
    --limit 300 `
    --write-output
```

Review readiness status and missing prerequisites only. Do not open prediction
rows or performance outputs.

## Stop Conditions

Stop when:

- the date is one of the four answer-key dates;
- the stock-universe cache is missing;
- any selected stock cache is missing, incomplete, or metadata-inconsistent;
- benchmark cache is missing or incomplete;
- `latest_input_date > as_of_date`;
- the point-in-time guard is absent;
- any command attempts provider fallback;
- validation or outcome outputs unexpectedly appear.

A cache blocker is an infrastructure result. Do not change thresholds,
hypotheses, formulas, or lists to bypass it.

## Interpretation Boundary

Phase 2.21 makes provider access impossible in this dedicated path by
construction. The provider name selects a cache namespace only.

The path reuses production research calculations but does not modify their
formulas. It generates no validation labels, list performance, winner/loser
metrics, hypothesis results, or production recommendation changes. U1 remains
sealed until the separate evaluation protocol is frozen and intentionally
executed.
