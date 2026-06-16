# Phase 2 Full Market Prewarm Plan

## Background

The first true full-market workflow attempt on branch `phase2-full-market-validation` was launched without `--limit` for the fixed historical window:

- Provider: `baostock`
- Start date: `2023-01-01`
- End date: `2024-01-31`
- Include lookback days: `120`
- Lookback days: `120`

The workflow started correctly as a no-limit run, but it stalled during the `prewarm` step. Cache files continued updating for a while and then stopped after the latest observed symbol `sh.688620`. CPU usage, cache files, workflow output files, stdout, and stderr did not change for more than 30 minutes, so the run was stopped and recorded as incomplete.

The workflow did not reach `daily_research`, `report_generation`, `backtest`, or `output_health`.

## Why Batch Prewarm

Full-market prewarm is the largest and least predictable part of the workflow because it depends on many serial BaoStock calls. Running it as one monolithic workflow makes failures hard to observe and hard to resume safely.

Batch prewarm reduces that risk by:

- Running fixed offset / limit slices of the stock universe.
- Writing batch results after every completed batch.
- Skipping completed batches when `--resume` is enabled.
- Recording failed or timed-out batches with their `offset`, `limit`, and `last_symbol`.
- Allowing a single failed batch to be retried without restarting the whole full-market prewarm.

## New Runner

Use:

```powershell
python backend\scripts\prewarm_full_market_batches.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --include-lookback-days 120 --cache-dir data\cache\daily-use --output-dir outputs\cache --batch-limit 500 --batch-size 20 --sleep-seconds 0.5 --retry 1 --resume
```

The runner writes incremental files:

```text
outputs/cache/full_market_prewarm_batches_2024-01-31.json
outputs/cache/full_market_prewarm_batches_2024-01-31.csv
outputs/cache/full_market_prewarm_batches_2024-01-31.log
```

Each batch records:

```text
batch_index
offset
limit
started_at
finished_at
elapsed_seconds
status
attempted_count
success_count
failed_count
last_symbol
error_summary
```

The summary includes:

```text
full_market_prewarm_complete
completed_batches
failed_batches
total_attempted
total_success
total_failed
last_completed_offset
next_offset
```

## Recommended Batch Size

Use `--batch-limit 500` as the first stable operating point.

This is small enough that a BaoStock stall does not lose the entire run, while still large enough to avoid excessive manual orchestration overhead.

## Recommended Resume Point

The previous scale validation successfully completed `limit 1500`, and the first full-market attempt progressed beyond that before stalling. For a controlled continuation, start from offset `1500`:

```powershell
python backend\scripts\prewarm_full_market_batches.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --include-lookback-days 120 --cache-dir data\cache\daily-use --output-dir outputs\cache --batch-limit 500 --batch-size 20 --sleep-seconds 0.5 --retry 1 --resume --start-offset 1500
```

To run only one batch:

```powershell
python backend\scripts\prewarm_full_market_batches.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --include-lookback-days 120 --cache-dir data\cache\daily-use --output-dir outputs\cache --batch-limit 500 --batch-size 20 --sleep-seconds 0.5 --retry 1 --resume --start-offset 1500 --max-batches 1
```

To retry an exact batch:

```powershell
python backend\scripts\prewarm_full_market_batches.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --include-lookback-days 120 --cache-dir data\cache\daily-use --output-dir outputs\cache --batch-limit 500 --batch-size 20 --sleep-seconds 0.5 --retry 1 --resume --offset 1500 --limit 500
```

## Timeout Strategy

The batch runner invokes each batch through the existing `prewarm_market_cache.py` script as a child process. The default timeout is:

```text
--batch-timeout-seconds 1800
```

If a batch exceeds the timeout, the child process is stopped, the batch is recorded as failed, and the runner stops unless `--continue-on-error` is provided.

## Resume And Retry

Use `--resume` for normal operation.

Behavior:

- Completed batches are skipped.
- Failed batches are not treated as complete.
- A failed batch can be retried with `--offset N --limit 500`.
- Existing successful batch records are preserved.

## After Batch Prewarm Completes

Only after `full_market_prewarm_complete: true` should the real full-market workflow be retried without `--limit`:

```powershell
python backend\scripts\run_daily_workflow.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --top-n 150 --backtest-top-n 10 --benchmark CSI300 --cache-dir data\cache\daily-use --output-dir outputs --include-lookback-days 120 --lookback-days 120 --batch-size 20 --sleep-seconds 0.5 --retry 1 --resume
```

Do not proceed to the recent-date full-market validation until the historical full-market workflow completes successfully.

## Known Risks

- BaoStock may still stall or return empty market data for some symbols.
- Batch timeout values may need tuning after observing real runtimes.
- The runner improves prewarm observability but does not change data-source behavior.
- Full-market daily research and backtest remain dependent on cache completeness.
- This change does not alter scoring, factor calculation, backtest logic, Dashboard behavior, or investment-label policy.
