# Phase 2 Full Market Validation

## Run Context

- Validation date: 2026-06-11
- Branch: `phase2-full-market-validation`
- Baseline commit: `1d2fa8f Allow full market workflow without limit`
- Command used: `python backend\scripts\run_daily_workflow.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --top-n 150 --backtest-top-n 10 --benchmark CSI300 --cache-dir data\cache\daily-use --output-dir outputs --include-lookback-days 120 --lookback-days 120 --batch-size 20 --sleep-seconds 0.5 --retry 1 --resume`
- `--limit` omitted: yes
- Expected workflow config semantics: `limit: null`, `full_market: true`
- Completed workflow summary for this run: no

This was the first true full-market validation attempt after fixing the workflow CLI limit semantics. The launched command intentionally omitted `--limit`. Because the process was stopped during the prewarm step, no new `outputs/workflow/workflow_summary_2024-01-31.json` was written for this run. Existing workflow, daily, backtest, cache, and failed-symbol files with timestamps before this run are from the earlier `limit 1500` validation and are not treated as completed full-market results.

## Date Range And Parameters

- Provider: `baostock`
- Start date: `2023-01-01`
- End date: `2024-01-31`
- Include lookback days: `120`
- Backtest lookback days: `120`
- Top N: `150`
- Backtest Top N: `10`
- Batch size: `20`
- Sleep seconds: `0.5`
- Retry: `1`
- Resume: enabled
- Cache directory: `data\cache\daily-use`
- Output directory: `outputs`

## Workflow Result

- Overall status: stopped / incomplete
- Stop reason: prewarm progress stalled for more than 30 minutes
- Process start time: 2026-06-11 11:17:08
- Last observed cache write: 2026-06-11 11:51:51
- Stop decision time: 2026-06-11 12:22:13
- Total wall-clock time until stop: about 65 minutes
- Active cache progress window: about 35 minutes
- No-progress window before stop: about 30 minutes

Step statuses for this run:

| Step | Status | Notes |
| --- | --- | --- |
| environment_check | not persisted | The workflow did not write a completed summary. |
| prewarm | stalled / stopped | Cache files advanced until `sh.688620`, then stopped updating. |
| daily_research | not run | The workflow did not reach this step. |
| report_generation | not run | The workflow did not reach this step. |
| backtest | not run | The workflow did not reach this step. |
| output_health | not run | The workflow did not reach this step. |

## Observed Progress

- Cache CSV count at 2026-06-11 11:22:26: `1484`
- Cache CSV count at 2026-06-11 11:27:44: `1589`
- Cache CSV count at 2026-06-11 11:38:03: `1805`
- Cache CSV count at 2026-06-11 11:53:21: `2143`
- Cache CSV count at stop: `2143`
- Last updated cache file: `data\cache\daily-use\baostock\stock_daily\adjusted\sh.688620.csv`
- `outputs/workflow/full_market_stdout_2024-01-31.txt`: empty
- `outputs/workflow/full_market_stderr_2024-01-31.txt`: empty

## Metrics

Because the workflow was stopped during prewarm, full-market daily research and backtest metrics were not generated.

| Metric | Value |
| --- | --- |
| attempted stock count | not available for this run |
| successful factor count | not available for this run |
| scored candidates count | not available for this run |
| fetch_error_count | not available for this run |
| failed symbols count | not available for this run |
| missing_files | not evaluated for this run |
| backtest success | no, backtest did not run |
| Dashboard health available | no, output health did not run for this attempt |

Reference only: existing `outputs/daily/summary_2024-01-31.json`, `outputs/backtests/backtest_summary_2024-01-31.json`, `outputs/cache/cache_prewarm_summary_2024-01-31.json`, and `outputs/errors/failed_symbols_2024-01-31.csv` were last written before this attempt and still represent the earlier `limit 1500` validation.

## Warnings And Errors

Warnings:

- BaoStock full-market prewarm did not complete in this run.
- Cache writes stopped for more than 30 minutes after reaching `sh.688620`.
- The workflow only writes `workflow_summary` and `workflow_log` after completion, so no completed full-market summary exists for this attempt.
- Existing output health is stale and belongs to the previous limited validation.

Errors:

- No Python stderr was emitted to `outputs/workflow/full_market_stderr_2024-01-31.txt`.
- No explicit workflow error was persisted because the process was stopped after the no-progress threshold.

## Full Market Limit Verification

- The launched command did not include `--limit`.
- Commit `1d2fa8f` changes omitted `--limit` to `limit=None`.
- Under this commit, `limit=None` maps to `full_market=True` in workflow summary generation.
- This run did not write a completed summary, so there is no persisted full-market summary field from the stopped attempt.

Conclusion: the run was a true no-limit launch, but it did not complete and therefore does not validate end-to-end full-market output generation.

## Failed Symbols

No failed-symbol CSV was produced by this stopped full-market attempt. The existing `outputs/errors/failed_symbols_2024-01-31.csv` is stale from the prior `limit 1500` run and contained 43 rows at last inspection.

## Missing Files

No new output health result was produced for this stopped attempt. Missing files for this run cannot be evaluated from a completed workflow summary. Existing required output files from the prior limited run remained present, but they are not evidence of full-market completion.

## Conclusion

Do not proceed directly to the second full-market recent-date validation yet.

The workflow now correctly starts without `--limit`, but the first no-limit historical run stalled during BaoStock prewarm before daily research, report generation, backtest, or output health could run. This should be treated as a BaoStock stability / long-running prewarm risk rather than a successful full-market validation.

## Risks

- BaoStock stability: the provider can stop making progress mid-prewarm without producing stderr.
- Runtime: full-market prewarm is materially longer than limit-based validation and may exceed practical interactive run windows.
- Cache dependency: resume helps, but the cache must continue from the stalled symbol range reliably.
- Observability: workflow summary/log are written only at the end, so mid-run visibility depends on cache file timestamps and process monitoring.
- Failed symbols: full-market failed-symbol counts are not available until the workflow reaches later output-writing stages.
- Listing-date and empty-market-data issues are expected to increase with full-market coverage.

## Next Recommendations

1. Do not merge this validation as a successful full-market result.
2. Re-run prewarm only with resume and stronger observability before attempting the full workflow again.
3. Consider splitting full-market prewarm into explicit batches or ranges so a BaoStock stall has a smaller blast radius.
4. Consider adding periodic progress logging or intermediate workflow state files before the next full-market run.
5. Consider evaluating a secondary provider such as Tushare or AKShare for symbols that repeatedly stall or return empty market data.
