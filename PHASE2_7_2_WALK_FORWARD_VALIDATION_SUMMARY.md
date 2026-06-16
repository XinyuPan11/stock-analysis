# Phase 2.7.2 Walk-forward Validation Summary

## Status

Framework implemented; full validation not run by Codex.

## Implemented Files

- `backend/src/stock_analysis/validation/future_returns.py`
- `backend/src/stock_analysis/validation/list_performance.py`
- `backend/src/stock_analysis/validation/factor_effectiveness.py`
- `backend/src/stock_analysis/validation/walk_forward.py`
- `backend/scripts/run_walk_forward_validation.py`

## CLI Parameters

The new CLI is read-only by default:

```powershell
python backend\scripts\run_walk_forward_validation.py --as-of-date 2024-01-31 --horizon-days 20 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 50 --dry-run
```

Supported parameters:

- `--start-date`
- `--end-date`
- `--as-of-date`
- `--horizon-days`
- `--benchmark`
- `--outputs-dir`
- `--cache-dir`
- `--list-ids`
- `--limit`
- `--dry-run`
- `--write-output`

Use `--dry-run` for read-only checks that do not write files. When `--dry-run` is omitted, the CLI refreshes validation outputs under `outputs/validation`. `--write-output` is kept as a compatibility flag.

## Tests

New tests:

- `backend/tests/test_future_returns.py`
- `backend/tests/test_list_performance.py`
- `backend/tests/test_factor_effectiveness.py`
- `backend/tests/test_walk_forward_validation.py`

Covered behavior:

- Future return calculation.
- Benchmark excess return calculation.
- Insufficient future window.
- Missing single-stock price data.
- List average return and outperform rate.
- Empty list handling.
- Missing factor handling.
- Dry-run behavior.
- CLI short smoke without provider access.

## Short Smoke

The framework supports a small dry-run smoke on existing fixed historical outputs. It reads local outputs/cache only and does not trigger provider access, prewarm, daily workflow, or backtest.

Executed smoke:

```powershell
python backend\scripts\run_walk_forward_validation.py --as-of-date 2024-01-31 --horizon-days 20 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 50 --dry-run
```

Result:

- `status`: `dry_run`
- `symbol_count`: `50`
- `valid_future_count`: `0`
- `data_quality_counts`: `insufficient_future_window = 50`
- `list_count`: `7`
- `factor_count`: `10`

This is expected for the current fixed historical cache because it ends at the as-of date and does not contain post-2024-01-31 future windows.

## First Real Validation Observation

A first controlled real validation run completed and produced 60D output files, but the sample was still under-covered:

- `symbol_count`: `50`
- `valid_future_count`: `9`
- `insufficient_future_window`: `41`
- 60D outputs generated under `outputs/validation`

Issues found from that run:

- `average_excess_return` and `outperform_rate` were often `null` because the benchmark cache was not always mapped correctly.
- `best_cases` / `worst_cases` could contain `NaN` in JSON output when excess return was unavailable.
- `factor_effectiveness` could become all `missing_factor` because factor rows were not merged from all available Phase 2.7 output sources.
- Blind `prewarm_market_cache.py --limit N` can spend time on symbols outside the validation universe and still miss symbols needed by validation.

Fixes added after the first real validation:

- Benchmark aliases now map `CSI300` to cached symbols such as `sh.000300` before falling back to `CSI300`.
- Future labels now include explicit `benchmark_data_quality`, such as `ok` or `benchmark_missing`.
- JSON outputs sanitize `NaN`, `inf`, and `-inf` to `null`.
- Factor effectiveness now merges fields from `stock_labels`, `candidate_labels`, `daily candidates`, `daily factors`, and list items.
- A targeted cache plan tool was added to generate the exact symbols that need future-window cache refresh.

## Remaining Limitations

- This is a single as-of-date framework in the first pass.
- Full validation across many as-of dates has not been run by Codex.
- Signal metrics are descriptive; they are not portfolio simulation results.
- No financial, valuation, industry, news, or announcement data is used.
- No complex ML training is included.

## Next Step

Run controlled Phase 2.7.2 smoke validation on fixed historical outputs, then decide whether Phase 2.7.3 should add simulated portfolio validation for selected lists.

## Controlled Real Validation Guide

Added a run guide for preparing future-window cache data and running controlled 20D / 60D validation:

- `PHASE2_7_2_REAL_VALIDATION_RUN_GUIDE.md`

Key boundaries:

- `2024-01-31` signals, rankings, labels, and lists remain fixed.
- Future price data is used only for validation labels and list/factor evaluation.
- 20D validation should prepare cache through at least `2024-03-15`.
- 60D validation should prepare cache through preferably `2024-05-31`.
- Validation remains read-only only when `--dry-run` is explicitly passed; otherwise the CLI refreshes validation output files from existing local outputs/cache.
- Use `backend\scripts\generate_validation_cache_plan.py` before prewarm to avoid blindly refreshing unrelated symbols.
