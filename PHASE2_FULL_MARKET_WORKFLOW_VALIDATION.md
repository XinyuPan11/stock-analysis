# Phase 2.6 Full Market Workflow Validation

## Validation Date

2026-06-14

## Current Branch

`phase2-full-market-validation`

## Baseline Commit

`7f68806 Add daily research progress diagnostics`

## Commands Run

Initial exact full workflow command was started without `--skip-backtest` and without
`--skip-prewarm`, but it stayed in the redundant `prewarm` step with no output refresh
and very low CPU growth. Because the fixed historical cache prewarm had already been
completed, that attempt was stopped and recorded as a redundant prewarm bottleneck.

The validated full workflow command skipped the already-completed prewarm step, but did
not skip backtest:

```powershell
python backend\scripts\run_daily_workflow.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --top-n 150 --backtest-top-n 10 --benchmark CSI300 --cache-dir data\cache\daily-use --output-dir outputs --include-lookback-days 120 --lookback-days 120 --batch-size 20 --sleep-seconds 0.5 --retry 1 --resume --skip-prewarm
```

After full-market cache prewarm is complete, this is the canonical full fixed-historical
workflow command. Running without `--skip-prewarm` may enter redundant prewarm and stall.

## Data Range

- Start date: `2023-01-01`
- End date: `2024-01-31`
- Include lookback days: `120`
- Backtest lookback days: `120`
- Cache directory: `data\cache\daily-use`
- Full market: `true`
- Limit: `null`

## Skip-Backtest Result

Previous skip-backtest full-market workflow completed successfully after the progress
diagnostics were added.

- Status: `ok`
- Total elapsed seconds: about `2940`
- Universe count: `5494`
- Attempted count: `5494`
- Successful factor count: `4810`
- Scored candidate count: `150`
- Fetch error count: `190`
- Main bottleneck: cache coverage / loading

## Full Workflow Result

- Workflow status: `ok`
- Total elapsed seconds: `5518.8283`
- Step statuses:
  - `environment_check`: `ok`
  - `daily_research`: `ok`
  - `report_generation`: `ok`
  - `backtest`: `ok`
  - `output_health`: `ok`

## Step Durations

- Daily research elapsed seconds: `1648.8552`
- Report generation elapsed seconds: `3.3843`
- Backtest elapsed seconds: `3866.5832`

Backtest is the dominant remaining runtime bottleneck in the full fixed historical
workflow. It completed successfully, but it writes outputs only at the end of the step,
so it has weaker mid-step observability than daily research.

## Full Workflow With Daily Symbol Timeout

Validation run started on `2026-06-15` after adding per-symbol daily research fetch
timeouts.

Command used:

```powershell
python backend\scripts\run_daily_workflow.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --top-n 150 --backtest-top-n 10 --benchmark CSI300 --cache-dir data\cache\daily-use --output-dir outputs --include-lookback-days 120 --lookback-days 120 --batch-size 20 --sleep-seconds 0.5 --retry 1 --resume --skip-prewarm --daily-progress-every 1 --symbol-timeout-seconds 60
```

Result:

- Workflow status: `failed`
- Total elapsed seconds: `28748.1372`
- `daily_research`: `ok`
- `report_generation`: `ok`
- `backtest`: `failed`
- `output_health`: `ok`
- Full market: `true`
- Limit: `null`

Daily research result:

- Elapsed seconds: `5800.5741`
- Candidate count: `150`
- Factor rows: `4810`
- Fetch error count: `190`
- Per-symbol timeout behavior: confirmed
- Timeout examples: `sz.301538`, `sz.301557`, `sz.301560`, `sz.301590`, `sz.301599`, `sz.301600`, `sz.301601`

The daily research stall root cause is no longer a single permanent stuck symbol. It is
a set of post-period or BaoStock-uncovered symbols whose provider calls can be slow or
occasionally fail to return promptly. The new timeout records those as `symbol_timeout`
and continues processing.

Backtest result:

- Backtest elapsed seconds before failure: `22943.7886`
- Last progress checkpoint: `processed=2700 total=5494 loaded_frames=2614 fetch_errors=86 last_symbol=sz.000958`
- Backtest outputs were not refreshed by this run; existing backtest output files remain
  from the earlier successful `2026-06-14` validation.
- Observed failure signal: repeated BaoStock socket errors, including `WinError 10057`.

Conclusion: the daily research timeout hardening is effective, but Phase 2.6 cannot be
fully closed on this run because the backtest stock-history loading path can still spend
hours in BaoStock/cache recovery and fail before rebalance construction. The next
minimal Phase 2.6 step should apply equivalent timeout or cache-only safeguards to
backtest history loading, without changing backtest scoring, portfolio construction, or
result semantics.

## Daily Research Result

- Universe count: `5494`
- Attempted count: `5494`
- Successful factor count: `4810`
- Scored candidate count: `150`
- Fetch error count: `190`
- Top N: `150`
- Full market: `true`
- Limit: `null`
- Candidate output status: generated

## Reports Generated

- `outputs\reports\daily_report_2024-01-31.md`
- `outputs\reports\daily_report_2024-01-31.html`
- Stock reports under `outputs\reports\stocks`

## Backtest Result

- Backtest output status: generated
- Backtest top N: `10`
- Rebalance frequency: `monthly`
- Number of rebalances: `13`
- Total return: `0.09472590163434669`
- Benchmark total return: `-0.1729847831445842`
- Excess return: `0.24297148204635854`
- Max drawdown: `-0.1576613365814321`
- Sharpe ratio: `0.4054760517758836`
- Net total return after cost: `0.06998669890177434`

Backtest outputs:

- `outputs\backtests\backtest_summary_2024-01-31.json`
- `outputs\backtests\backtest_equity_curve_2024-01-31.csv`
- `outputs\backtests\backtest_rebalance_log_2024-01-31.csv`
- `outputs\backtests\backtest_report_2024-01-31.md`
- `outputs\backtests\backtest_report_2024-01-31.html`

## Workflow Logs

- `outputs\workflow\workflow_log_2024-01-31.txt`
- `outputs\workflow\workflow_summary_2024-01-31.json`
- `outputs\workflow\daily_research_progress_2024-01-31.log`
- `outputs\workflow\backtest_progress_2024-01-31.log` after the backtest progress
  diagnostics change
- `outputs\workflow\full_workflow_skip_prewarm_stdout_2024-01-31_20260614_200407.txt`
- `outputs\workflow\full_workflow_skip_prewarm_stderr_2024-01-31_20260614_200407.txt`

## Known Issues

- Running the full workflow without `--skip-prewarm` can still stall in the redundant
  prewarm step even after the fixed historical full-market cache has already been
  prepared.
- Backtest is now the longest completed stage. Backtest progress diagnostics were added
  after this validation run so future runs can show mid-step progress.
- Daily research now has per-symbol provider fetch timeout protection, but backtest
  history loading still needs equivalent protection after the `2026-06-15` run failed
  at `processed=2700`.
- `fetch_error_count` remains `190` for the fixed historical full-market run.
- Backtest warnings include monthly `listing_date_missing` entries.
- Recursive listing of all `outputs` can be slow because the report directory contains
  many generated files.

## Tests Run

Before this validation run:

```powershell
python -m unittest discover -s backend\tests
```

Result: `152 tests OK`.

After writing this report, run the relevant or full test suite again before merging this
validation branch.

## Recommended Next Step

Stay in Phase 2.6. Use the canonical `--skip-prewarm` full fixed-historical workflow
command for future validation runs. If another full run is needed, inspect
`outputs\workflow\backtest_progress_2024-01-31.log` while the backtest step is active.
