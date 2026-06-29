# Phase 2.11A Controlled Walk-forward Validation Runbook

## Goal

Prepare and run the first controlled walk-forward validation panel after the raw-cache catch-up, point-in-time price guard, and validation bias flags.

The first panel is intentionally limited to:

```text
as_of_date = 2024-10-31
horizon_days = 20
limit = 300
benchmark = CSI300
```

This phase does not change scoring, ranking, factor, or validation-label formulas. All commands read existing local outputs and cache files. They do not access BaoStock.

## Why The First Panel Uses 20D Only

The 2024-10-31 20D future window ends on 2024-12-10 and is already covered by the controlled cache recovery.

A 60D window from 2024-10-31 requires data in 2025 under the existing buffered validation-window planning rule. It is outside this first panel and must not be silently combined with the 20D run.

## First Completed Panel Result

The user manually completed the first controlled panel with:

```text
as_of_date = 2024-10-31
horizon_days = 20
benchmark = CSI300
limit = 300
prediction_count = 300
valid_future_count = 300
benchmark_data_quality = ok
latest_input_date = 2024-10-31
max_raw_cache_date = 2026-06-24
future_rows_excluded_count = 119399
leakage_guard_applied = true
no_future_leakage = true
```

The Phase 2.10 guard excluded raw-cache rows after the as-of date from feature, factor, scoring, filtering, and ranking inputs. Future rows were available only to explicit validation labels. Phase 2.10.1 bias flags were also present, including the `current_snapshot_limited` universe and status qualifications.

### List-level Observations

| List | Average future return | Average excess return | Outperform rate |
| --- | ---: | ---: | ---: |
| `trend_leaders` | approximately 2.57% | approximately 3.04% | approximately 66.7% |
| `high_confidence_candidates` | approximately 2.15% | approximately 2.62% | approximately 61.9% |
| `breakout_watch` | approximately 2.32% | approximately 2.79% | approximately 61.5% |
| `high_risk_active` | approximately -3.64% | approximately -3.17% | not highlighted |

These are controlled single-panel observations. They may justify continued validation of list construction, but they do not establish stable performance across dates or horizons.

### Factor And Ranking Caution

The `total_score` result was:

```text
correlation_with_future_return = approximately -0.060
top_quantile_average_return = approximately 0.87%
bottom_quantile_average_return = approximately 1.61%
spread = approximately -0.74%
```

The negative spread means this panel does not establish that the current total-score ordering ranked stronger future outcomes above weaker ones. The list-level observations and the factor-ranking result should therefore be kept separate:

- some lists showed positive average excess return and outperform rates;
- the aggregate total-score ranking was not validated by this panel;
- no scoring, ranking, or factor formula should be changed from one as-of date;
- later panels must test whether either pattern persists across dates and horizons.

### Interpretation Boundary

The first panel confirms that the controlled validation chain can run with complete price-label coverage and the Phase 2.10 leakage guard. It does not remove the Phase 2.10.1 limitations:

```text
universe_point_in_time_status = current_snapshot_limited
listing_status_point_in_time_status = current_snapshot_limited
st_status_point_in_time_status = current_snapshot_limited
suspension_status_point_in_time_status = current_snapshot_limited
```

The result is research-only controlled validation, not a final production-grade historical simulation or a model-effectiveness conclusion.

The remaining commands in this runbook are retained as the reproducible procedure for refreshing or checking this panel.

## Step 1: Read-only Readiness Check

Run:

```powershell
python backend\scripts\check_validation_window_readiness.py --as-of-date 2024-10-31 --horizon-days 20 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 300 --benchmark CSI300 --min-valid-count 50 --min-coverage-rate 0.7
```

This command:

- does not access providers;
- does not run validation;
- does not prewarm cache;
- checks as-of outputs, symbol plan, cache coverage, existing predictions, and quality thresholds.

Continue only when the result is equivalent to:

```text
execution_status = executable_ready
comparison_eligible = true
high_quality_ready = true
quality_status = high_quality
symbol_count = 300
covered_count = 300
missing_count = 0
```

## Step 2: Walk-forward Dry-run

Run the calculation without refreshing files:

```powershell
python backend\scripts\run_walk_forward_validation.py --as-of-date 2024-10-31 --horizon-days 20 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 300 --dry-run
```

Check the console summary before writing outputs:

```text
status = dry_run
as_of_date = 2024-10-31
horizon_days = 20
benchmark_data_quality = ok
valid_future_count >= 50
price_point_in_time_guard_applied = true
feature_input_point_in_time_status = guarded
future_label_window_status = explicit_future_only
universe_point_in_time_status = current_snapshot_limited
listing_status_point_in_time_status = current_snapshot_limited
st_status_point_in_time_status = current_snapshot_limited
suspension_status_point_in_time_status = current_snapshot_limited
```

`latest_input_date` must be on or before 2024-10-31. Future prices may appear only in label-window diagnostics.

## Step 3: Write The Controlled Panel

After the dry-run passes, refresh the official validation outputs:

```powershell
python backend\scripts\run_walk_forward_validation.py --as-of-date 2024-10-31 --horizon-days 20 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 300 --write-output
```

Output writing is the CLI default unless `--dry-run` is used. `--write-output` is retained here to make the operator's intent explicit.

Expected files:

```text
outputs/validation/walk_forward_summary_2024-10-31_20d.json
outputs/validation/walk_forward_predictions_2024-10-31_20d.csv
outputs/validation/list_performance_2024-10-31_20d.json
outputs/validation/factor_effectiveness_2024-10-31_20d.json
outputs/validation/walk_forward_report_2024-10-31_20d.md
```

The files provide:

| Requirement | Output |
| --- | --- |
| As-of date, horizon, valid count, benchmark quality | `walk_forward_summary` |
| Price/factor point-in-time diagnostics | `walk_forward_summary` and Markdown report |
| Universe/status bias flags | `walk_forward_summary` and Markdown report |
| Per-symbol future return, excess return, benchmark result, drawdown, data quality | `walk_forward_predictions` |
| List-level average return, excess return, outperform rate, coverage notes | `list_performance` |
| Correlation, top/bottom quantile return, spread, top-quantile outperform rate | `factor_effectiveness` |

## Step 4: Explicit Quality Diagnostic

Run the existing target-locked diagnostic:

```powershell
python backend\scripts\diagnose_2024_10_31_20d_asof_recovery.py --outputs-dir outputs --cache-dir data\cache\daily-use --benchmark CSI300 --limit 300 --min-valid-count 50 --min-coverage-rate 0.7 --write-output
```

Expected diagnostic output:

```text
outputs/experiments/asof_recovery_2024-10-31_20d.json
```

This is the canonical compact source for:

```text
candidate_count
prediction_count
valid_future_count
valid_coverage_ratio
missing_price_count
insufficient_future_window_count
data_quality_counts
required_future_end_date
quality_status
comparison_eligible
high_quality_ready
```

For the first panel, the expected final status is `recovered_valid`.

## Optional Existing Summarizer

If strategy-family and aggressive-filter outputs already exist for this window, regenerate the multi-as-of plan and the existing cross-window research summary:

```powershell
python backend\scripts\generate_multi_asof_validation_plan.py --outputs-dir outputs --cache-dir data\cache\daily-use
python backend\scripts\summarize_multi_window_experiments.py --outputs-dir outputs --plan-file outputs\experiments\multi_asof_validation_plan_2024.json --min-valid-count 50 --min-coverage-rate 0.7 --min-filter-sample-count 10 --write-output
```

Expected summary files:

```text
outputs/experiments/multi_window_experiment_summary_2024.json
outputs/experiments/multi_window_experiment_summary_2024.md
```

This step summarizes existing experiment outputs only. It does not run market-data downloads, validation, scoring, or the full workflow.

## Success Criteria

The panel succeeds when all of the following hold:

1. `execution_status = executable_ready`.
2. `valid_future_count >= 50`.
3. `valid_future_count / prediction_count >= 0.7`.
4. `missing_price_count = 0`.
5. `insufficient_future_window_count = 0`.
6. `benchmark_data_quality = ok`.
7. List excess-return and outperform metrics are populated where list coverage is valid.
8. Factor top-quantile metrics are populated for available factors.
9. `latest_input_date <= 2024-10-31`.
10. Price/feature guard fields show guarded/explicit-future-only status.
11. Universe, listing, ST, and suspension fields remain visibly `current_snapshot_limited`.
12. The report describes the result as controlled validation, not a final production-grade historical simulation.

## Stop Conditions

Stop and report the output without expanding the run when any of these occur:

- `blocked_missing_as_of_outputs`, `missing_symbols_file`, `missing_cache`, or `deferred`;
- benchmark data quality is not `ok`;
- valid count is below 50;
- valid coverage is below 0.7;
- any future-feature leakage diagnostic fails or is missing after output refresh;
- bias limitation flags are absent after output refresh;
- the requested future window crosses into 2025;
- a command attempts provider access or prewarm;
- output counts unexpectedly differ between dry-run and write-output.

Do not respond to a stop condition by running BaoStock, the full workflow, or a broader validation panel.

## Results To Paste Back

Paste the readiness JSON and diagnostic JSON, then run these compact PowerShell views:

```powershell
Get-Content outputs\validation\walk_forward_summary_2024-10-31_20d.json

$lists = Get-Content -Raw outputs\validation\list_performance_2024-10-31_20d.json | ConvertFrom-Json
$lists | Select-Object list_id,item_count,valid_future_count,average_future_return,average_excess_return,outperform_rate,notes | Format-Table -AutoSize

$factors = Get-Content -Raw outputs\validation\factor_effectiveness_2024-10-31_20d.json | ConvertFrom-Json
$factors | Select-Object factor_name,correlation_with_future_return,top_quantile_average_return,bottom_quantile_average_return,spread,top_quantile_outperform_rate,notes | Format-Table -AutoSize
```

Also paste:

```text
status
prediction_count
valid_future_count
valid_coverage_ratio
missing_price_count
insufficient_future_window_count
benchmark_data_quality
latest_input_date
max_raw_cache_date
future_rows_excluded_count
price_point_in_time_guard_applied
feature_input_point_in_time_status
future_label_window_status
universe_point_in_time_status
known_bias_limitations
```

Interpretation must retain the Phase 2.10.1 limitation: historical universe and security-status metadata are not yet fully point-in-time, even when price/factor timing and future-label boundaries are guarded.
