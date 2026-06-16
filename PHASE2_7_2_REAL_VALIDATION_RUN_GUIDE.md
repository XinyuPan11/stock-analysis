# Phase 2.7.2 Controlled Real Validation Run Guide

## Purpose

This guide explains how to prepare future-window cache data and run the Phase 2.7.2 walk-forward validation framework for the fixed as-of research view dated `2024-01-31`.

The validation remains read-only by default. It must not regenerate scores, labels, factors, or lists.

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

## Step 3: Prepare 20D Future-window Cache

For a controlled full-market 20D validation, use the resumable batch runner:

```powershell
python backend\scripts\prewarm_full_market_batches.py --provider baostock --start-date 2024-02-01 --end-date 2024-03-15 --cache-dir data\cache\daily-use --output-dir outputs\cache --batch-limit 500 --batch-size 20 --sleep-seconds 0.5 --retry 1 --resume --batch-timeout-seconds 1800
```

If a batch fails or stalls, resume later with the same command, or retry a single batch:

```powershell
python backend\scripts\prewarm_full_market_batches.py --provider baostock --start-date 2024-02-01 --end-date 2024-03-15 --cache-dir data\cache\daily-use --output-dir outputs\cache --offset 2000 --limit 500 --batch-size 20 --sleep-seconds 0.5 --retry 1 --resume --batch-timeout-seconds 1800
```

## Step 4: Run 20D Validation Dry-run

Dry-run is the default validation mode. It calculates summary metrics and writes no validation files.

```powershell
python backend\scripts\run_walk_forward_validation.py --as-of-date 2024-01-31 --horizon-days 20 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 0 --dry-run
```

Expected success criteria:

- `valid_future_count > 0`
- `insufficient_future_window` is low or zero
- `missing_price` count is understandable from failed symbols, suspended stocks, newly listed stocks, or data-source gaps
- No files are created under `outputs/validation` during dry-run

## Step 5: Write 20D Validation Outputs

Run this only after the dry-run looks healthy:

```powershell
python backend\scripts\run_walk_forward_validation.py --as-of-date 2024-01-31 --horizon-days 20 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 0 --write-output
```

Expected output files:

```text
outputs/validation/walk_forward_summary_2024-01-31_20d.json
outputs/validation/walk_forward_predictions_2024-01-31_20d.csv
outputs/validation/list_performance_2024-01-31_20d.json
outputs/validation/factor_effectiveness_2024-01-31_20d.json
outputs/validation/walk_forward_report_2024-01-31_20d.md
```

## Step 6: Prepare 60D Future-window Cache

The 60D horizon needs a longer future window:

```powershell
python backend\scripts\prewarm_full_market_batches.py --provider baostock --start-date 2024-02-01 --end-date 2024-05-31 --cache-dir data\cache\daily-use --output-dir outputs\cache --batch-limit 500 --batch-size 20 --sleep-seconds 0.5 --retry 1 --resume --batch-timeout-seconds 1800
```

## Step 7: Run 60D Validation Dry-run

```powershell
python backend\scripts\run_walk_forward_validation.py --as-of-date 2024-01-31 --horizon-days 60 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 0 --dry-run
```

Expected success criteria:

- `valid_future_count > 0`
- `insufficient_future_window` is low or zero
- `missing_price` count is explainable
- No files are created under `outputs/validation` during dry-run

## Step 8: Write 60D Validation Outputs

```powershell
python backend\scripts\run_walk_forward_validation.py --as-of-date 2024-01-31 --horizon-days 60 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 0 --write-output
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
- Confirm output files are generated only when `--write-output` is used.

## Out of Scope

- No Phase 2.7.3 portfolio simulation.
- No latest-date refresh.
- No scoring or factor logic changes.
- No financial, valuation, industry, news, or announcement data.
- No complex ML training.

