# Phase 2 Full Market Batch Prewarm Execution

## Run Context

- Execution date: 2026-06-11
- Branch: `phase2-full-market-validation`
- Baseline commit: `949aa09 Add full market batch prewarm runner`
- Latest execution-report commit before offset 2000 run: `6927b96 Add full market batch prewarm execution report`
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

## Offset 2000 / Limit 500 Execution

### Command

```powershell
python backend\scripts\prewarm_full_market_batches.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --include-lookback-days 120 --cache-dir data\cache\daily-use --output-dir outputs\cache --offset 2000 --limit 500 --batch-size 20 --sleep-seconds 0.5 --retry 1 --resume
```

### Parameters

- Provider: `baostock`
- Start date: `2023-01-01`
- End date: `2024-01-31`
- Effective start date with lookback: `2022-09-03`
- Include lookback days: `120`
- Offset: `2000`
- Limit: `500`
- Batch size: `20`
- Retry: `1`
- Resume: enabled
- Batch timeout seconds: `1800`

### Batch Result

- Batch status: `warning`
- Started at: `2026-06-11T12:53:32`
- Finished at: `2026-06-11T13:19:43`
- Elapsed seconds: `1571.297`
- Attempted count: `314`
- Success count: `271`
- Failed count: `43`
- Cache hit count: `186`
- Skipped count: `186`
- Last symbol: `sz.000635`
- Timeout: no
- Error summary: `{"empty_market_data": 43}`

This batch did request BaoStock. Unlike the offset 1500 batch, `attempted_count > 0`, so it exercised the previously uncached range. The run completed without timeout, but the batch status is `warning` because BaoStock returned empty market data for 43 symbols.

### Failed Symbol Examples

Examples from `outputs/cache/cache_prewarm_errors_2024-01-31.csv`:

| symbol | name | error_type | can_retry |
| --- | --- | --- | --- |
| `sh.688411` | 海博思创 | `empty_market_data` | `True` |
| `sh.688449` | 联芸科技 | `empty_market_data` | `True` |
| `sh.688530` | 欧莱新材 | `empty_market_data` | `True` |
| `sh.688545` | 兴福电子 | `empty_market_data` | `True` |
| `sh.688583` | 思看科技 | `empty_market_data` | `True` |
| `sh.688584` | 上海合晶 | `empty_market_data` | `True` |
| `sh.688605` | 先锋精科 | `empty_market_data` | `True` |
| `sh.688615` | 合合信息 | `empty_market_data` | `True` |

### Comparison With Offset 1500 / Limit 500

| Batch | status | attempted | success | failed | cache_hit | skipped | elapsed_seconds | BaoStock requested |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| offset 1500 / limit 500 | `ok` | 0 | 0 | 0 | 500 | 500 | 15.703 | no |
| offset 2000 / limit 500 | `warning` | 314 | 271 | 43 | 186 | 186 | 1571.297 | yes |

### Coverage Summary After Offset 2000

- Total symbols in universe observed by runner: `5494`
- Planned batches in this invocation: `1`
- Completed batches recorded in batch file: `2`
- Failed batches recorded in batch file: `0`
- Full-market prewarm complete: `false`
- Last completed offset: `2000`
- Batch runner `next_offset`: `5494`

Note: `next_offset` is `5494` because this invocation was an explicit single-batch run with `--offset 2000 --limit 500`; it should not be interpreted as all later batches being complete.

### Can Continue To Offset 2500 / Limit 500

Yes, it is reasonable to continue to `offset 2500 / limit 500`, with caution.

Rationale:

- The batch did not timeout.
- The batch made real BaoStock requests.
- The process kept writing cache files until completion.
- The failure rate was non-trivial but all failures were classified as `empty_market_data`, which is retryable and consistent with newly listed or unavailable symbols.

Recommended command:

```powershell
python backend\scripts\prewarm_full_market_batches.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --include-lookback-days 120 --cache-dir data\cache\daily-use --output-dir outputs\cache --offset 2500 --limit 500 --batch-size 20 --sleep-seconds 0.5 --retry 1 --resume
```

Keep the same stopping rule: stop if CPU, cache files, and log/output files do not update for more than 30 minutes.

### Risks And Observations

- This batch was the first useful pressure test after the fully cached offset 1500 batch.
- BaoStock handled 314 attempted symbols and wrote 271 successful caches.
- The 43 `empty_market_data` failures should be reviewed before treating full-market cache coverage as complete.
- The batch runner's JSON, CSV, and log outputs updated at completion.
- The output file now contains records for both offset 1500 and offset 2000 because resume loaded the previous completed batch record.

## Offset 2500 / Limit 500 Execution

### Command

```powershell
python backend\scripts\prewarm_full_market_batches.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --include-lookback-days 120 --cache-dir data\cache\daily-use --output-dir outputs\cache --offset 2500 --limit 500 --batch-size 20 --sleep-seconds 0.5 --retry 1 --resume
```

### Parameters

- Provider: `baostock`
- Start date: `2023-01-01`
- End date: `2024-01-31`
- Effective start date with lookback: `2022-09-03`
- Include lookback days: `120`
- Offset: `2500`
- Limit: `500`
- Batch size: `20`
- Retry: `1`
- Resume: enabled
- Batch timeout seconds: `1800`
- Current baseline commit before run: `ebad766 Update full market batch prewarm execution report`

### Batch Result

- Batch status: `warning`
- Started at: `2026-06-11T13:29:09`
- Finished at: `2026-06-11T13:55:29`
- Elapsed seconds: `1579.844`
- Attempted count: `500`
- Success count: `474`
- Failed count: `26`
- Cache hit count: `0`
- Skipped count: `0`
- Last symbol: `sz.002165`
- Empty market data count: `26`
- Timeout: no
- Error summary: `{"empty_market_data": 26}`

This batch did request BaoStock for the whole 500-symbol slice. It completed without timeout and without process stall. The `warning` status is due to 26 `empty_market_data` failures, which should be treated as data-source coverage issues rather than a workflow blocker.

### Failed Symbol Examples

Examples from `outputs/cache/cache_prewarm_errors_2024-01-31.csv` after this batch:

| symbol | name | error_type | can_retry |
| --- | --- | --- | --- |
| `sz.001220` | 世盟股份 | `empty_market_data` | `True` |
| `sz.001221` | 悍高集团 | `empty_market_data` | `True` |
| `sz.001233` | 海安集团 | `empty_market_data` | `True` |
| `sz.001237` | 惠康科技 | `empty_market_data` | `True` |
| `sz.001257` | 盛龙股份 | `empty_market_data` | `True` |
| `sz.001277` | 速达股份 | `empty_market_data` | `True` |
| `sz.001279` | 强邦新材 | `empty_market_data` | `True` |
| `sz.001280` | 中国铀业 | `empty_market_data` | `True` |

### Comparison Across Validated Batches

| Batch | status | attempted | success | failed | empty_market_data | cache_hit | skipped | elapsed_seconds | BaoStock requested |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| offset 1500 / limit 500 | `ok` | 0 | 0 | 0 | 0 | 500 | 500 | 15.703 | no |
| offset 2000 / limit 500 | `warning` | 314 | 271 | 43 | 43 | 186 | 186 | 1571.297 | yes |
| offset 2500 / limit 500 | `warning` | 500 | 474 | 26 | 26 | 0 | 0 | 1579.844 | yes |

### Coverage Summary After Offset 2500

- Total symbols in universe observed by runner: `5494`
- Planned batches in this invocation: `1`
- Completed batches recorded in batch file: `3`
- Failed batches recorded in batch file: `0`
- Full-market prewarm complete: `false`
- Last completed offset: `2500`
- Batch runner `next_offset`: `5494`

Note: `next_offset` is `5494` because this invocation was an explicit single-batch run with `--offset 2500 --limit 500`; it should not be interpreted as all later batches being complete.

### Can Continue To Offset 3000 / Limit 500

Yes, it is reasonable to continue to `offset 3000 / limit 500`, with the same monitoring rule.

Rationale:

- The batch did not timeout.
- The batch made real BaoStock requests for all 500 symbols.
- Cache files continued updating through completion.
- The failed count decreased from 43 in the offset 2000 batch to 26 in the offset 2500 batch.
- All failures were `empty_market_data`, which remains a data coverage risk but is not a prewarm process failure.

Recommended next command:

```powershell
python backend\scripts\prewarm_full_market_batches.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --include-lookback-days 120 --cache-dir data\cache\daily-use --output-dir outputs\cache --offset 3000 --limit 500 --batch-size 20 --sleep-seconds 0.5 --retry 1 --resume
```

It is also reasonable to consider an automatic continuous run for remaining batches starting at offset 3000, as long as each batch still writes summary/log output and the run is monitored for stalls:

```powershell
python backend\scripts\prewarm_full_market_batches.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --include-lookback-days 120 --cache-dir data\cache\daily-use --output-dir outputs\cache --batch-limit 500 --batch-size 20 --sleep-seconds 0.5 --retry 1 --resume --start-offset 3000
```

For the next step, a single `offset 3000 / limit 500` run is still the more conservative option.

### Risks And Observations

- This batch is the strongest prewarm stability signal so far because every symbol required an attempted fetch.
- BaoStock remained responsive for the full batch duration.
- `empty_market_data` remains the main data-quality risk.
- The 26 failed symbols should be preserved for retry or alternate-provider investigation.
- No full-market workflow, daily research, or backtest was run.
