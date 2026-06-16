# Phase 2.7.2 Controlled Real Validation Run Guide

## Purpose

This guide explains how to prepare future-window cache data and run the Phase 2.7.2 walk-forward validation framework for the fixed as-of research view dated `2024-01-31`.

Use `--dry-run` for read-only validation checks. When `--dry-run` is omitted, the validation CLI refreshes files under `outputs/validation`; it still must not regenerate scores, labels, factors, or lists.

## No Future Leakage Boundary

No future leakage.

- The signals, scores, rankings, labels, and lists are fixed as of `2024-01-31`.
- Files under `outputs/daily`, `outputs/labels`, and `outputs/lists` for `2024-01-31` are the as-of research view.
- Future price data is used only to calculate future return labels and evaluate the already-fixed research view.
- Do not rerun `run_daily_workflow.py`, `run_daily_research.py`, or `generate_research_views.py` after adding future-window cache data unless the goal is a separate as-of-date refresh.

## Recommended Future Cache Windows

For `as-of-date=2024-01-31`:

- 20D validation: cache should extend to at least `2024-03-15`.
- 60D validation: cache should preferably extend to `2024-05-31`.

These dates give enough room for trading-day holidays and suspended symbols. If the future window is still too short for a symbol, the validator reports `insufficient_future_window`.

## Step 1: Set Proxy If Needed

Only the cache preparation commands access the data provider. The validator itself does not.

```powershell
$env:HTTP_PROXY="http://127.0.0.1:8668"
$env:HTTPS_PROXY="http://127.0.0.1:8668"
```

## Step 2: Optional Small Future-window Cache Smoke

Use this only to verify the command path with a short run. It refreshes a small slice of local cache and does not rerun scoring or list generation.

```powershell
python backend\scripts\prewarm_market_cache.py --provider baostock --start-date 2024-02-01 --end-date 2024-03-15 --limit 50 --offset 0 --batch-size 10 --cache-dir data\cache\daily-use --output-dir outputs\cache --sleep-seconds 0.5 --retry 1 --resume
```

Expected result:

- Cache files for the selected symbols include rows after `2024-01-31`.
- `outputs/cache/cache_prewarm_summary_2024-03-15.json` is generated or refreshed.
- No daily research, report generation, or backtest runs.

## Step 3: Generate a Targeted Cache Plan

Before refreshing future-window cache, generate the exact symbol list needed by validation. This command does not access BaoStock or any provider.

20D example:

```powershell
python backend\scripts\generate_validation_cache_plan.py --as-of-date 2024-01-31 --horizon-days 20 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 50 --benchmark CSI300 --output-file outputs\validation\cache_plan_2024-01-31_20d_limit50.txt
```

60D example:

```powershell
python backend\scripts\generate_validation_cache_plan.py --as-of-date 2024-01-31 --horizon-days 60 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 50 --benchmark CSI300 --output-file outputs\validation\cache_plan_2024-01-31_60d_limit50.txt
```

The plan writes:

```text
outputs/validation/cache_plan_2024-01-31_20d_limit50.txt
outputs/validation/cache_plan_2024-01-31_20d_limit50.json
outputs/validation/cache_plan_2024-01-31_60d_limit50.txt
outputs/validation/cache_plan_2024-01-31_60d_limit50.json
```

The `.txt` file is a one-symbol-per-line list for `prewarm_market_cache.py --symbols-file`. The `.json` file records:

- `as_of_date`
- `horizon_days`
- `target_end_date`
- `symbol_count`
- `missing_future_count`
- `ok_count`
- `benchmark_symbol`
- `symbols_to_prewarm`

`CSI300` is mapped to the cached benchmark symbol, normally `sh.000300`, when available.

## Step 4: Prepare 20D Future-window Cache

For a controlled targeted 20D validation, use the generated symbols file:

```powershell
python backend\scripts\prewarm_market_cache.py --provider baostock --start-date 2024-02-01 --end-date 2024-03-15 --cache-dir data\cache\daily-use --output-dir outputs\cache --symbols-file outputs\validation\cache_plan_2024-01-31_20d_limit50.txt --batch-size 10 --sleep-seconds 0.5 --retry 1 --resume
```

For a larger full validation universe, generate the plan with `--limit 0`, then use the generated `limitall` symbols file.

## Step 5: Run 20D Validation Dry-run

Dry-run mode calculates summary metrics and writes no validation files. Use `--dry-run` when you only want a read-only check.

```powershell
python backend\scripts\run_walk_forward_validation.py --as-of-date 2024-01-31 --horizon-days 20 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 0 --dry-run
```

Expected success criteria:

- `valid_future_count > 0`
- `insufficient_future_window` is low or zero
- `missing_price` count is understandable from failed symbols, suspended stocks, newly listed stocks, or data-source gaps
- No files are created under `outputs/validation` during dry-run

## Step 6: Write 20D Validation Outputs

Run this only after the dry-run looks healthy. Do not pass `--dry-run`; the CLI refreshes validation outputs by default.

```powershell
python backend\scripts\run_walk_forward_validation.py --as-of-date 2024-01-31 --horizon-days 20 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 0
```

Expected output files:

```text
outputs/validation/walk_forward_summary_2024-01-31_20d.json
outputs/validation/walk_forward_predictions_2024-01-31_20d.csv
outputs/validation/list_performance_2024-01-31_20d.json
outputs/validation/factor_effectiveness_2024-01-31_20d.json
outputs/validation/walk_forward_report_2024-01-31_20d.md
```

## Step 7: Prepare 60D Future-window Cache

The 60D horizon needs a longer future window and should also use a targeted symbols file:

```powershell
python backend\scripts\prewarm_market_cache.py --provider baostock --start-date 2024-02-01 --end-date 2024-05-31 --cache-dir data\cache\daily-use --output-dir outputs\cache --symbols-file outputs\validation\cache_plan_2024-01-31_60d_limit50.txt --batch-size 10 --sleep-seconds 0.5 --retry 1 --resume
```

## Step 8: Run 60D Validation Dry-run

```powershell
python backend\scripts\run_walk_forward_validation.py --as-of-date 2024-01-31 --horizon-days 60 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 0 --dry-run
```

Expected success criteria:

- `valid_future_count > 0`
- `insufficient_future_window` is low or zero
- `missing_price` count is explainable
- No files are created under `outputs/validation` during dry-run

## Step 9: Write 60D Validation Outputs

```powershell
python backend\scripts\run_walk_forward_validation.py --as-of-date 2024-01-31 --horizon-days 60 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 0
```

Expected output files:

```text
outputs/validation/walk_forward_summary_2024-01-31_60d.json
outputs/validation/walk_forward_predictions_2024-01-31_60d.csv
outputs/validation/list_performance_2024-01-31_60d.json
outputs/validation/factor_effectiveness_2024-01-31_60d.json
outputs/validation/walk_forward_report_2024-01-31_60d.md
```

## Validation Checklist

Before trusting the result:

- Confirm the as-of outputs are still the fixed `2024-01-31` outputs.
- Confirm future cache preparation did not rerun scoring, list generation, reports, workflow, or backtest.
- Confirm `valid_future_count > 0`.
- Confirm `insufficient_future_window` is low or zero after the relevant future cache window is prepared.
- Review `missing_price` symbols and decide whether they are normal data gaps or blocking coverage issues.
- Confirm `average_excess_return` and `outperform_rate` are populated when benchmark cache exists.
- Confirm `factor_effectiveness` is not all `missing_factor` when score/factor fields exist.
- Confirm output files are generated only when `--dry-run` is omitted. `--write-output` is kept as a compatibility flag for older notes.

## Out of Scope

- No Phase 2.7.3 portfolio simulation.
- No latest-date refresh.
- No scoring or factor logic changes.
- No financial, valuation, industry, news, or announcement data.
- No complex ML training.
