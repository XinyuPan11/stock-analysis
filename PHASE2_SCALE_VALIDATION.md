# Phase 2 Scale Validation

Validation date: 2026-06-11

Current branch: `phase2-scale-validation`

Main merge commit: `2eb36e2a1709132c4147378622ecb91a1f31acc7`

Stable tag: `v0.2.5-workflow`

Tag status: created and pushed before this validation run; verified locally and on `origin`, and it points to `2eb36e2a1709132c4147378622ecb91a1f31acc7`.

Scope:

- Merge `phase2-workflow` into `main`.
- Verify `v0.2.5-workflow`.
- Create/use `phase2-scale-validation`.
- Run `limit=1000` and `limit=1500` workflow validation.
- Do not run full market.
- Do not modify scoring, factor, backtest, data source, or frontend logic.

## Merge And Tag

- `main` merge commit: `2eb36e2a1709132c4147378622ecb91a1f31acc7`
- `origin/main`: up to date.
- `v0.2.5-workflow`: exists on local and origin.
- `v0.2.5-workflow` target commit: `2eb36e2a1709132c4147378622ecb91a1f31acc7`
- `phase2-scale-validation`: created before this validation run and verified to track `origin/phase2-scale-validation`.

## Limit 1000

Command parameters:

- `--limit 1000`
- `--top-n 80`
- `--backtest-top-n 10`
- `--batch-size 20`
- `--resume`

Workflow result:

- Status: `ok`
- Elapsed seconds: `1119.7906`
- Elapsed time: about `18.7` minutes
- Step statuses: `environment_check=ok`, `prewarm=ok`, `daily_research=ok`, `report_generation=ok`, `backtest=ok`, `output_health=ok`
- Missing files: `0`
- Workflow warnings: `0`
- Workflow errors: `0`
- Report generation: successful
- Backtest: successful

Daily research:

- `attempted_count`: `1000`
- `successful_factor_count`: `928`
- `scored_count`: `80`
- `fetch_error_count`: `4`

Backtest metrics:

- `total_return`: `-0.0210711177`
- `net_total_return_after_cost`: `-0.0419930560`
- `max_drawdown`: `-0.2151309986`
- `number_of_rebalances`: `13`
- `average_holdings`: `10.0`

Dashboard/output health:

- Health status: `warning`
- Missing files: `0`
- Failed symbols count: `8`
- Blocking issues: none
- Non-blocking warnings: `empty_market_data`, `failed_symbols:8`, `listing_date_missing`
- Candidate count: `80`
- Stock report count: `107`

Notes:

- The workflow completed well under the 2 hour stop threshold.
- Empty market data appeared for newly listed or unavailable BaoStock symbols, but did not block candidates, reports, or backtest output.
- Existing pandas/numexpr and pandas FutureWarning messages were observed; they did not stop the workflow.

## Limit 1500

Command parameters:

- `--limit 1500`
- `--top-n 100`
- `--backtest-top-n 10`
- `--batch-size 20`
- `--resume`

Workflow result:

- Status: `ok`
- Elapsed seconds: `4076.001`
- Elapsed time: about `67.9` minutes
- Step statuses: `environment_check=ok`, `prewarm=ok`, `daily_research=ok`, `report_generation=ok`, `backtest=ok`, `output_health=ok`
- Missing files: `0`
- Workflow warnings: `0`
- Workflow errors: `0`
- Report generation: successful
- Backtest: successful

Daily research:

- `attempted_count`: `1500`
- `successful_factor_count`: `1345`
- `scored_count`: `100`
- `fetch_error_count`: `43`

Backtest metrics:

- `total_return`: `0.0040755105`
- `net_total_return_after_cost`: `-0.0178226569`
- `max_drawdown`: `-0.2202418252`
- `number_of_rebalances`: `13`
- `average_holdings`: `10.0`

Dashboard/output health:

- Health status: `warning`
- Missing files: `0`
- Failed symbols count: `86`
- Blocking issues: none
- Non-blocking warnings: `empty_market_data`, `failed_symbols:86`, `listing_date_missing`
- Candidate count: `100`
- Stock report count: `119`

Notes:

- The workflow completed within the 3 hour stop threshold.
- Runtime increased materially from `limit=1000`, mainly from prewarm and backtest.
- Failed symbols increased from `8` to `86`, dominated by `empty_market_data` and listing-date/data-availability issues.

## Summary Table

| Limit | Workflow | Elapsed | Attempted | Successful factors | Scored | Fetch errors | Missing files | Failed symbols | Health | Blocking issues |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 1000 | ok | 1119.7906s | 1000 | 928 | 80 | 4 | 0 | 8 | warning | none |
| 1500 | ok | 4076.001s | 1500 | 1345 | 100 | 43 | 0 | 86 | warning | none |

## Full Market Recommendation

Do not run full market immediately from this branch.

Rationale:

- `limit=1500` completed, but took about 68 minutes with warmed cache and `--resume`.
- Full market is likely several thousand symbols, so runtime could reasonably reach multiple hours.
- Failed symbols rose sharply by `limit=1500`, mostly due to `empty_market_data`; larger runs may produce more non-blocking data-quality noise.
- BaoStock stayed available during this validation, but the workload is long enough that provider stability and resume behavior remain important.

Estimated full-market risk:

- Runtime: likely several hours, especially if many symbols are not already cached.
- Provider stability: acceptable for this run, but long BaoStock runs remain exposed to transient network/provider failures.
- Cache: `--resume` is essential; without it, prewarm would be the main bottleneck.
- Batch/retry: keep `--batch-size 20`, `--retry 1`, and `--resume` for the next scale test.
- Data source strategy: consider AKShare/Tushare fallback only after workflow behavior is stable at larger BaoStock limits.

Recommended next step:

1. Do not merge `phase2-scale-validation` to `main` solely for validation outputs unless the report is desired in main.
2. Run one more time-boxed validation at `limit=2000` or `limit=2500` before full market.
3. Consider adding workflow history filenames that include limit/run timestamp so same-date summaries are not overwritten.
4. Track failed symbols by category before expanding to full market.
