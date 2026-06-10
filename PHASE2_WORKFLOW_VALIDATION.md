# Phase 2.5 Workflow Validation

Validation date: 2026-06-10

Branch: `phase2-workflow`

Baseline commit before this validation report: `b229a43c890626984ce9abef7748d1e1be6304f2`

Scope:

- Validate the local one-click daily workflow at `limit=100`, `limit=300`, and `limit=500`.
- Do not run full market validation in this round.
- Do not change scoring, factor, data source, report, or backtest logic.
- Dashboard remains a local read-only UI over `outputs/`.

## Bug Fix Status

The `/compare` empty numeric query parameter bug was already fixed before this validation run.

Fixed behavior:

- `/compare?min_score=&limit=` returns HTML instead of FastAPI 422.
- `/api/candidates?min_score=&limit=` returns 200 and treats empty values as unset.
- `/api/compare?min_score=&limit=` returns 200 and treats empty values as unset.
- Invalid numeric values such as `min_score=abc` return a clear 400 response instead of crashing.

Fix commit: `b229a43 Handle empty dashboard filter params`

## Validation Commands

Common date range and provider:

```powershell
$env:HTTP_PROXY="http://127.0.0.1:8668"
$env:HTTPS_PROXY="http://127.0.0.1:8668"
```

The workflow command was run with BaoStock, `2023-01-01` to `2024-01-31`, `CSI300`, `include-lookback-days=120`, `lookback-days=120`, `retry=1`, and `resume`.

## Limit 100 Result

Command parameters:

- `--limit 100`
- `--top-n 20`
- `--backtest-top-n 10`
- `--batch-size 10`

Workflow:

- Status: `ok`
- Elapsed seconds: `413.4934` (~6.9 minutes)
- Step statuses: `environment_check=ok`, `prewarm=ok`, `daily_research=ok`, `report_generation=ok`, `backtest=ok`, `output_health=ok`
- Missing files: `0`
- Workflow warnings: `0`
- Workflow errors: `0`

Prewarm:

- Total symbols: `100`
- Attempted: `50`
- Cache hits: `50`
- Success: `50`
- Skipped: `50`
- Errors: `0`

Daily research:

- Attempted count: `100`
- Successful factor count: `92`
- Scored count: `20`
- Fetch error count: `0`

Backtest:

- Status: successful
- Total return: `0.1175689047`
- Net total return after cost: `0.0991618611`
- Max drawdown: `-0.1853415877`
- Rebalances: `13`

Dashboard health:

- `/health/outputs`: `200`
- `/`: `200`
- `/compare`: `200`
- `/compare?min_score=&limit=`: `200`
- Health status: `warning`
- Missing files: `0`
- Non-blocking warnings: `failed_symbols:2`, `listing_date_missing`
- Candidate count: `20`
- Stock report count: `21`
- Prohibited deterministic trading terms scan: no hits

## Limit 300 Result

Command parameters:

- `--limit 300`
- `--top-n 30`
- `--backtest-top-n 10`
- `--batch-size 20`

Workflow:

- Status: `ok`
- Elapsed seconds: `1367.2251` (~22.8 minutes)
- Step statuses: `environment_check=ok`, `prewarm=ok`, `daily_research=ok`, `report_generation=ok`, `backtest=ok`, `output_health=ok`
- Missing files: `0`
- Workflow warnings: `0`
- Workflow errors: `0`

Prewarm:

- Total symbols: `300`
- Attempted: `200`
- Cache hits: `100`
- Success: `200`
- Skipped: `100`
- Errors: `0`

Daily research:

- Attempted count: `300`
- Successful factor count: `274`
- Scored count: `30`
- Fetch error count: `0`

Backtest:

- Status: successful
- Total return: `-0.1138091162`
- Net total return after cost: `-0.1305141327`
- Max drawdown: `-0.2714709383`
- Rebalances: `13`

Dashboard health:

- `/health/outputs`: `200`
- `/`: `200`
- `/compare`: `200`
- `/compare?min_score=&limit=`: `200`
- Health status: `warning`
- Missing files: `0`
- Non-blocking warnings: `failed_symbols:2`, `listing_date_missing`
- Candidate count: `30`
- Stock report count: `33`
- Prohibited deterministic trading terms scan: no hits

## Limit 500 Result

Command parameters:

- `--limit 500`
- `--top-n 50`
- `--backtest-top-n 10`
- `--batch-size 20`

Workflow:

- Status: `ok`
- Elapsed seconds: `1494.0102` (~24.9 minutes)
- Step statuses: `environment_check=ok`, `prewarm=ok`, `daily_research=ok`, `report_generation=ok`, `backtest=ok`, `output_health=ok`
- Missing files: `0`
- Workflow warnings: `0`
- Workflow errors: `0`

Prewarm:

- Total symbols: `500`
- Attempted: `200`
- Cache hits: `300`
- Success: `200`
- Skipped: `300`
- Errors: `0`

Daily research:

- Attempted count: `500`
- Successful factor count: `459`
- Scored count: `50`
- Fetch error count: `0`

Backtest:

- Status: successful
- Total return: `-0.0900732961`
- Net total return after cost: `-0.1078717263`
- Max drawdown: `-0.2200310033`
- Rebalances: `13`

Dashboard health:

- `/health/outputs`: `200`
- `/`: `200`
- `/compare`: `200`
- `/compare?min_score=&limit=`: `200`
- Health status: `warning`
- Missing files: `0`
- Non-blocking warnings: `failed_symbols:2`, `listing_date_missing`
- Candidate count: `50`
- Stock report count: `50`
- Prohibited deterministic trading terms scan: no hits

## Summary Table

| Limit | Workflow status | Elapsed | Attempted | Successful factors | Scored | Fetch errors | Missing files | Backtest | Health |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 100 | ok | 413.4934s | 100 | 92 | 20 | 0 | 0 | ok | warning |
| 300 | ok | 1367.2251s | 300 | 274 | 30 | 0 | 0 | ok | warning |
| 500 | ok | 1494.0102s | 500 | 459 | 50 | 0 | 0 | ok | warning |

## Full Market Feasibility

Do not run full market yet from this validation alone.

Observations:

- BaoStock was stable across all three runs with proxy enabled.
- `--resume` materially reduced later prewarm work: limit 500 only attempted 200 new symbols because 300 were already cached.
- Cache reuse is essential. Without cache, full-market prewarm would likely take much longer and be more exposed to provider instability.
- The workflow is functionally ready for larger runs, but full market should be attempted as a separate, time-boxed validation.

Estimated full-market risk:

- With about 5,000 to 5,500 symbols and the observed prewarm pace, an uncached full-market run may take several hours.
- BaoStock login/logout per symbol is a potential throughput bottleneck.
- Larger backtests will also grow materially, though less dramatically than uncached prewarm.
- Resume, batching, and retry are necessary for full-market operation.

Recommendation:

- Next run should be a time-boxed `limit=1000` or `limit=1500` validation before full market.
- Keep `--resume`.
- Keep `--batch-size 20` initially; only increase after checking BaoStock stability.
- Consider supplementing BaoStock with AKShare/Tushare as fallback data sources if full-market runs become slow or fragile.

## Known Limitations

- Health status remains `warning` because of non-blocking data quality items: `failed_symbols:2` and `listing_date_missing`.
- `workflow_summary_2024-01-31.json` is valid JSON, but PowerShell `ConvertFrom-Json` can be fragile on long captured stdout/stderr tails; Python `json` parsed it successfully.
- Output files are overwritten for the same `YYYY-MM-DD` after each limit run, so the validation report records each run's metrics immediately after completion.
- This validation does not prove full-market runtime or provider reliability.

## Next Steps

1. Commit this validation report to `phase2-workflow`.
2. If merging Phase 2.5 soon, keep it clearly marked as local workflow automation only.
3. Run a separate `limit=1000` or `limit=1500` validation before attempting full market.
4. Consider improving workflow history retention so summaries for different limit runs are not overwritten by date alone.
