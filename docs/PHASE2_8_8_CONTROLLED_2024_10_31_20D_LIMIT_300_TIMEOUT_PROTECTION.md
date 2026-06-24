# Phase 2.8.8 Controlled 2024-10-31 20d Limit 300 Timeout Protection

## Goal

Recover and expand only this controlled validation window:

```text
as_of_date = 2024-10-31
horizon_days = 20
target_limit = 300
required_future_end_date = 2024-12-10
```

This phase is research-only. It does not change production scoring, ranking,
factor formulas, validation labels, or any 2025 data path.

## Strict Non-goals

- Do not enter 2025.
- Do not run full workflow.
- Do not run unrelated dates or horizons.
- Do not change production scoring.
- Do not change factor logic.
- Do not change validation math.
- Do not treat limit 300 as a final model-quality conclusion.

## Timeout Protection

`run_daily_research.py` now supports:

```text
--max-consecutive-symbol-timeouts
--min-successful-factor-rows
```

If consecutive symbol-level provider timeouts reach the cap, the daily research
run stops early, writes partial outputs, writes failed symbols, and reports:

```text
status = partial_timeout_protected
timeout_count
skipped_count
valid_factor_rows
partial_success
failed_symbols_path
```

Partial success means the recovery run produced enough valid factor rows for a
controlled follow-up decision. It does not mean the validation quality is final.


## Actual Manual Result

Phase 2.8.8 achieved the timeout-protection objective:

```text
2024-10-31 20d limit 300 daily research timeout protection works
symbols_file_symbol_count = 300
prediction_count = 300
required_future_end_date = 2024-12-10
insufficient_future_window_count = 0
no 2025 data needed
```

The remaining bottleneck is not scoring, ranking, factor calculation, validation
math, or future-window length. It is future-price cache coverage:

```text
valid_future_count = 58
missing_price_count = 245 before targeted chunk prewarm
missing_price_count = 242 after chunk_02 prewarm
valid_coverage_ratio ~= 0.1933
```

Manual chunked missing-price prewarm is inefficient for this window. In the
observed chunk_02 run, 30 symbols were attempted but only 3 validation
`missing_price` symbols recovered after many BaoStock login/logout cycles, and
the process can stall.

The diagnostic status for this condition is:

```text
status = expansion_incomplete_low_coverage
root_cause = missing_price_future_cache_coverage
```

If an older diagnostic returns `missing_cache`, interpret it the same way for
this Phase 2.8.8 limit 300 result: timeout protection succeeded, but limit 300
validation remains incomplete because future-price cache coverage is too low.

Recommended next phase: Phase 2.8.9 / Phase 2.9 should focus on prewarm timeout
protection or a raw cache catch-up pipeline for targeted future-price windows.

## Manual Commands

Optional controlled prewarm for the 2024-10-31 as-of lookback window:

```powershell
python backend\scripts\prewarm_market_cache.py --provider baostock --start-date 2023-10-31 --end-date 2024-10-31 --cache-dir data\cache\daily-use --output-dir outputs\cache --limit 300 --batch-size 10 --sleep-seconds 0.5 --retry 0 --resume --max-errors 20
```

Controlled daily research expansion with timeout protection:

```powershell
python backend\scripts\run_daily_research.py --provider baostock --end-date 2024-10-31 --lookback-years 1 --benchmark CSI300 --top-n 30 --limit 300 --cache-dir data\cache\daily-use --output-dir outputs\daily --error-output-dir outputs\errors --progress-log outputs\workflow\daily_research_2024-10-31_limit300.log --progress-every 1 --symbol-timeout-seconds 15 --max-consecutive-symbol-timeouts 3 --min-successful-factor-rows 50 --retry 0
```

Retry only timed-out or failed symbols after reviewing the failed-symbols CSV:

```powershell
python backend\scripts\prewarm_market_cache.py --provider baostock --start-date 2023-10-31 --end-date 2024-10-31 --cache-dir data\cache\daily-use --output-dir outputs\cache --failed-symbols-file outputs\errors\failed_symbols_2024-10-31.csv --retry-only --batch-size 5 --sleep-seconds 1.0 --retry 1 --resume --max-errors 20
```

Regenerate research views after daily outputs are acceptable:

```powershell
python backend\scripts\generate_research_views.py --date 2024-10-31 --outputs-dir outputs --cache-dir data\cache\daily-use
```

Refresh the multi-as-of plan for the target window:

```powershell
python backend\scripts\generate_multi_asof_validation_plan.py --outputs-dir outputs --cache-dir data\cache\daily-use --as-of-dates 2024-10-31 --horizons 20 --recommended-limit 300
```

Rerun controlled validation at limit 300:

```powershell
python backend\scripts\run_controlled_validation_batch.py --as-of-date 2024-10-31 --horizon-days 20 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 300 --write-output
```

Export validation `missing_price` symbols for targeted future-cache prewarm:

```powershell
python backend\scripts\diagnose_2024_10_31_20d_asof_recovery.py --outputs-dir outputs --cache-dir data\cache\daily-use --limit 300 --write-output
```

This writes:

```text
outputs/cache_plans/missing_price_symbols_2024-10-31_20d.csv
```

Targeted future-cache prewarm for validation `missing_price` symbols only:

```powershell
python backend\scripts\prewarm_market_cache.py --provider baostock --start-date 2024-10-31 --end-date 2024-12-10 --cache-dir data\cache\daily-use --output-dir outputs\cache --symbols-file outputs\cache_plans\missing_price_symbols_2024-10-31_20d.csv --batch-size 5 --sleep-seconds 1.0 --retry 1 --resume --max-errors 20
```

Rerun controlled validation after the targeted future-cache prewarm:

```powershell
python backend\scripts\run_controlled_validation_batch.py --as-of-date 2024-10-31 --horizon-days 20 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 300 --write-output
```

Regenerate optional experiment outputs:

```powershell
python backend\scripts\run_strategy_family_experiments.py --as-of-date 2024-10-31 --horizon-days 20 --outputs-dir outputs --cache-dir data\cache\daily-use --write-output
python backend\scripts\run_aggressive_filter_experiments.py --as-of-date 2024-10-31 --horizon-days 20 --outputs-dir outputs --cache-dir data\cache\daily-use --write-output
```

Diagnose final status:

```powershell
python backend\scripts\diagnose_2024_10_31_20d_asof_recovery.py --outputs-dir outputs --cache-dir data\cache\daily-use --limit 300 --write-output
```

## Expected Output Files

```text
outputs/daily/summary_2024-10-31.json
outputs/daily/factors_2024-10-31.csv
outputs/errors/failed_symbols_2024-10-31.csv
outputs/cache/cache_prewarm_summary_2024-10-31.json
outputs/cache_plans/missing_price_symbols_2024-10-31_20d.csv
outputs/validation/walk_forward_predictions_2024-10-31_20d.csv
outputs/validation/list_performance_2024-10-31_20d.json
outputs/validation/factor_effectiveness_2024-10-31_20d.json
outputs/experiments/strategy_family_experiments_2024-10-31_20d.json
outputs/experiments/aggressive_filter_experiments_2024-10-31_20d.json
outputs/experiments/asof_recovery_2024-10-31_20d.json
```

## Interpreting Partial Success

`partial_timeout_protected` is not a crash and not a model-quality conclusion.
It means the run stopped before more slow provider calls could stall the
recovery, while preserving partial daily outputs and a retryable failed-symbols
file.

Review daily-research timeout fields:

```text
timeout_count
skipped_count
valid_factor_rows
partial_success
failed_symbols_path
```

Review validation missing-price export fields:

```text
status
root_cause
diagnostic_interpretation
missing_price_symbols_count
missing_price_symbols_file
missing_price_symbols_file_written
missing_price_prewarm_command
insufficient_future_window_count
required_future_end_date
```

If `partial_success = true`, continue with review, retry-only prewarm, and then
rerun the controlled validation. If `partial_success = false`, retry failed
symbols before using the outputs for validation.
