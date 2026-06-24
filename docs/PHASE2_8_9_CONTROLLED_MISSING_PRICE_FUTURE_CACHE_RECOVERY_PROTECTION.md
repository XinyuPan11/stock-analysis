# Phase 2.8.9 Controlled Missing-Price Future Cache Recovery Protection

## Goal

Protect only the controlled 2024-10-31 20d missing-price future-cache recovery path.

```text
as_of_date = 2024-10-31
horizon_days = 20
future_cache_start = 2024-10-31
future_cache_end = 2024-12-10
symbols_source = outputs/cache_plans/missing_price_symbols_2024-10-31_20d.csv
```

This phase is research-only. It does not change production scoring, ranking,
factor formulas, validation math, recommendation wording, or any 2025 data path.

## Strict Non-goals

- Do not enter 2025.
- Do not run full workflow.
- Do not expand to unrelated as-of dates or horizons.
- Do not change production scoring.
- Do not change validation labels or factor formulas.
- Do not treat limit 300 as a final model-quality conclusion.

## What Changed

`prewarm_market_cache.py` now supports controlled symbol-level protection:

```text
--symbol-timeout-seconds
--max-consecutive-symbol-timeouts
--failed-symbols-output
--progress-log
```

For each symbol the prewarm loop reports:

```text
index
total
symbol
cache_hit
coverage_ok
fetch_attempted
status
error_type
```

On a symbol timeout the tool skips that symbol, records a retryable failed row,
preserves any cache files already written, and continues until the consecutive
symbol-timeout cap or max-error cap is reached.

## Safe Missing-Price Recovery Command

Run missing-price recovery in small chunks. This first chunk stays fully inside
late 2024 and does not touch 2025:

```powershell
python backend\scripts\prewarm_market_cache.py --provider baostock --start-date 2024-10-31 --end-date 2024-12-10 --cache-dir data\cache\daily-use --output-dir outputs\cache --symbols-file outputs\cache_plans\missing_price_symbols_2024-10-31_20d.csv --limit 30 --offset 0 --batch-size 5 --sleep-seconds 1.0 --retry 1 --resume --max-errors 20 --symbol-timeout-seconds 20 --max-consecutive-symbol-timeouts 3 --failed-symbols-output outputs\cache\missing_price_prewarm_failed_2024-10-31_20d_chunk01.csv --progress-log outputs\cache\missing_price_prewarm_2024-10-31_20d_chunk01.jsonl
```

Next chunks only change `--offset` and output filenames, for example chunk 02:

```powershell
python backend\scripts\prewarm_market_cache.py --provider baostock --start-date 2024-10-31 --end-date 2024-12-10 --cache-dir data\cache\daily-use --output-dir outputs\cache --symbols-file outputs\cache_plans\missing_price_symbols_2024-10-31_20d.csv --limit 30 --offset 30 --batch-size 5 --sleep-seconds 1.0 --retry 1 --resume --max-errors 20 --symbol-timeout-seconds 20 --max-consecutive-symbol-timeouts 3 --failed-symbols-output outputs\cache\missing_price_prewarm_failed_2024-10-31_20d_chunk02.csv --progress-log outputs\cache\missing_price_prewarm_2024-10-31_20d_chunk02.jsonl
```

Retry only a failed chunk after reviewing the failed-symbols CSV:

```powershell
python backend\scripts\prewarm_market_cache.py --provider baostock --start-date 2024-10-31 --end-date 2024-12-10 --cache-dir data\cache\daily-use --output-dir outputs\cache --failed-symbols-file outputs\cache\missing_price_prewarm_failed_2024-10-31_20d_chunk01.csv --retry-only --batch-size 3 --sleep-seconds 1.5 --retry 1 --resume --max-errors 10 --symbol-timeout-seconds 20 --max-consecutive-symbol-timeouts 2 --failed-symbols-output outputs\cache\missing_price_prewarm_retry_failed_2024-10-31_20d_chunk01.csv --progress-log outputs\cache\missing_price_prewarm_retry_2024-10-31_20d_chunk01.jsonl
```

## After Prewarm

Rerun only the controlled validation and diagnostic:

```powershell
python backend\scripts\run_controlled_validation_batch.py --as-of-date 2024-10-31 --horizon-days 20 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 300 --write-output
python backend\scripts\diagnose_2024_10_31_20d_asof_recovery.py --outputs-dir outputs --cache-dir data\cache\daily-use --limit 300 --write-output
```

## Expected Output Fields

Review the prewarm summary:

```text
timeout_count
consecutive_symbol_timeouts
max_consecutive_symbol_timeouts
stopped_early
stop_reason
failed_symbols_output
progress_log
symbol_timeout_seconds
error_type_counts
```

Review each failed-symbols CSV for:

```text
symbol
stage
error_type
error_message
provider
start_date
end_date
attempt_count
can_retry
```

## Interpretation

A stopped run with `stop_reason = max_consecutive_symbol_timeouts` is controlled
protection, not a scoring failure. It means the cache recovery preserved prior
successes, recorded retryable symbols, and avoided another long stall.

The desired validation improvement is a lower `missing_price_count` and a higher
`valid_future_count`. If coverage remains low, the correct conclusion is still:

```text
root_cause = missing_price_future_cache_coverage
```
