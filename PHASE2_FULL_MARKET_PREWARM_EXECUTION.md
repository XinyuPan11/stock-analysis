# Phase 2 Full Market Batch Prewarm Execution

## Run Context

- Execution date: 2026-06-11
- Branch: `phase2-full-market-validation`
- Baseline commit: `949aa09 Add full market batch prewarm runner`
- Run type: batch prewarm only
- Full-market workflow run: no
- Daily research run: no
- Backtest run: no
- Code changes during run: none

## Command

```powershell
python backend\scripts\prewarm_full_market_batches.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --include-lookback-days 120 --cache-dir data\cache\daily-use --output-dir outputs\cache --offset 1500 --limit 500 --batch-size 20 --sleep-seconds 0.5 --retry 1 --resume
```

## Parameters

- Provider: `baostock`
- Start date: `2023-01-01`
- End date: `2024-01-31`
- Effective start date with lookback: `2022-09-03`
- Include lookback days: `120`
- Offset: `1500`
- Limit: `500`
- Batch size: `20`
- Retry: `1`
- Resume: enabled
- Batch timeout seconds: `1800`

## Batch Result

- Batch status: `ok`
- Started at: `2026-06-11T12:48:45`
- Finished at: `2026-06-11T12:49:01`
- Elapsed seconds: `15.703`
- Attempted count: `0`
- Success count: `0`
- Failed count: `0`
- Cache hit count: `500`
- Skipped count: `500`
- Last symbol: `sh.688336`
- Timeout: no
- Error summary: none

The batch completed quickly because all 500 symbols in `offset=1500, limit=500` already had cache coverage and were skipped under `--resume`. This validates the batch runner's offset/limit path, resume behavior, and output reporting for this range. It does not represent a fresh BaoStock fetch stress test for all 500 symbols.

## Output Files

- `outputs/cache/full_market_prewarm_batches_2024-01-31.json`
- `outputs/cache/full_market_prewarm_batches_2024-01-31.csv`
- `outputs/cache/full_market_prewarm_batches_2024-01-31.log`
- `outputs/cache/cache_prewarm_summary_2024-01-31.json`
- `outputs/cache/cache_prewarm_errors_2024-01-31.csv`

## Failed Symbols

No failed symbols were recorded for this batch.

`outputs/cache/cache_prewarm_errors_2024-01-31.csv` contains only the header row for this run.

## Coverage Summary

- Total symbols in universe observed by runner: `5494`
- Planned batches in this invocation: `1`
- Completed batches: `1`
- Failed batches: `0`
- Full-market prewarm complete: `false`
- Last completed offset: `1500`
- Batch runner `next_offset`: `5494`

Note: `next_offset` is `5494` because this invocation was an explicit single-batch run with `--offset 1500 --limit 500`; it should not be interpreted as all later batches being complete.

## Can Continue To Offset 2000 / Limit 500

Yes, it is reasonable to continue with:

```powershell
python backend\scripts\prewarm_full_market_batches.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --include-lookback-days 120 --cache-dir data\cache\daily-use --output-dir outputs\cache --offset 2000 --limit 500 --batch-size 20 --sleep-seconds 0.5 --retry 1 --resume
```

The next batch is more likely to exercise real BaoStock fetches because the previous full-market attempt stalled after cache progress around `sh.688620`. It should be run with the same monitoring rule: stop if CPU, cache files, and log/output files do not update for more than 30 minutes.

## Risks And Observations

- Resume behavior worked as intended for the already cached 1500-1999 range.
- This run did not validate BaoStock freshness for this range because no provider calls were needed.
- The prior full-market stall risk remains for uncached symbols after the observed cache frontier.
- The batch runner produced JSON, CSV, and log outputs promptly.
- No deterministic investment-advice expressions were introduced.
