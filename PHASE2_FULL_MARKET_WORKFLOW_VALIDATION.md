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
- `outputs\workflow\full_workflow_skip_prewarm_stdout_2024-01-31_20260614_200407.txt`
- `outputs\workflow\full_workflow_skip_prewarm_stderr_2024-01-31_20260614_200407.txt`

## Known Issues

- Running the full workflow without `--skip-prewarm` can still stall in the redundant
  prewarm step even after the fixed historical full-market cache has already been
  prepared.
- Backtest is now the longest completed stage and lacks detailed mid-step progress logs.
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

Stay in Phase 2.6. Add minimal backtest progress diagnostics before attempting additional
full-market validation runs, because the complete workflow now shows backtest as the
dominant long-running black-box step.
