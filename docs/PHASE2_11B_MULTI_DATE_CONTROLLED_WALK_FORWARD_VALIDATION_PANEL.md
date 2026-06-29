# Phase 2.11B Multi-date Controlled Walk-forward Validation Panel

## Scope

Branch:

`phase2-11b-multi-date-controlled-validation-panel`

This phase checks whether the Phase 2.11A observations persist across several
controlled as-of dates. It does not change scoring, ranking, factor formulas,
validation labels, or production recommendations.

All commands below are manual commands. Codex does not run BaoStock, prewarm,
the full workflow, or long validation jobs.

## Candidate Panel Readiness

The requested dates are price-cache feasible for a 20D horizon:

| as_of_date | required target end | Local price-cache feasibility | As-of output readiness |
| --- | --- | --- | --- |
| 2024-10-31 | 2024-12-10 | Within cache | Ready |
| 2024-12-31 | 2025-02-09 | Within cache | Missing labels/factors/lists |
| 2025-03-31 | 2025-05-10 | Within cache | Missing labels/factors/lists |
| 2025-06-30 | 2025-08-09 | Within cache | Missing labels/factors/lists |
| 2025-09-30 | 2025-11-09 | Within cache | Missing labels/factors/lists |
| 2025-12-31 | 2026-02-09 | Within cache | Missing labels/factors/lists |
| 2026-03-31 | 2026-05-10 | Within cache | Missing labels/factors/lists |

The target end dates use
`validation.cache_plan.recommended_target_end_date()`. They remain before the
raw-cache target date `2026-06-24`.

The Phase 2.8.4 multi-as-of planner and readiness checker are still scoped to
2024 and mark windows crossing the 2024 boundary as deferred. Do not use that
legacy `deferred_crosses_2025` result as evidence that the local price cache is
insufficient for this phase. The later dates are blocked because historical
as-of research outputs have not been generated, not because their 20D price
windows exceed the cache.

## First Controlled Panel

Use the nearest already-prepared panel first:

```text
2024-01-31 20D
2024-04-30 20D
2024-07-31 20D
2024-10-31 20D
```

All four dates currently have stock labels, factor rows, lists, core validation
outputs, strategy-family outputs, and aggressive-filter outputs. Re-running
the core validation refreshes the Phase 2.10 point-in-time diagnostics and
Phase 2.10.1 bias-limitation metadata under the current code.

## Readiness Checks

Generate the existing 2024 plan without provider access:

```powershell
python backend\scripts\generate_multi_asof_validation_plan.py --outputs-dir outputs --cache-dir data\cache\daily-use --as-of-dates 2024-01-31,2024-04-30,2024-07-31,2024-10-31 --horizons 20 --recommended-limit 300
```

Check each 20D window:

```powershell
$dates = @("2024-01-31", "2024-04-30", "2024-07-31", "2024-10-31")
foreach ($date in $dates) {
    python backend\scripts\check_validation_window_readiness.py --as-of-date $date --horizon-days 20 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 300 --benchmark CSI300 --min-valid-count 50 --min-coverage-rate 0.7
}
```

These commands read the local cache and existing outputs only. Do not run any
suggested prewarm command during Phase 2.11B. Stop if a window reports missing
cache or missing as-of outputs.

For the requested 2025-2026 dates, use this no-provider prerequisite check
until the old 2024-only planner is replaced in a later phase:

```powershell
$dates = @("2024-12-31", "2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31")
foreach ($date in $dates) {
    [pscustomobject]@{
        as_of_date = $date
        stock_labels = Test-Path "outputs\labels\stock_labels_$date.json"
        factors = Test-Path "outputs\daily\factors_$date.csv"
        high_confidence_list = Test-Path "outputs\lists\high_confidence_candidates_$date.json"
        multi_lists = Test-Path "outputs\lists\multi_lists_$date.json"
    }
}
```

Do not run validation for a date unless all four prerequisite fields are true.

## Validation Dry-run

Run one date first and inspect the console JSON:

```powershell
python backend\scripts\run_controlled_validation_batch.py --as-of-date 2024-01-31 --horizon-days 20 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 300
```

Then dry-run the remaining dates:

```powershell
$dates = @("2024-04-30", "2024-07-31", "2024-10-31")
foreach ($date in $dates) {
    python backend\scripts\run_controlled_validation_batch.py --as-of-date $date --horizon-days 20 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 300
}
```

The controlled batch does not access a provider. Without `--write-output`, it
does not refresh validation files.

## Write Outputs

After every dry-run passes:

```powershell
$dates = @("2024-01-31", "2024-04-30", "2024-07-31", "2024-10-31")
foreach ($date in $dates) {
    python backend\scripts\run_controlled_validation_batch.py --as-of-date $date --horizon-days 20 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 300 --write-output
}
```

Refresh the optional experiment outputs from the completed core validation:

```powershell
$dates = @("2024-01-31", "2024-04-30", "2024-07-31", "2024-10-31")
foreach ($date in $dates) {
    python backend\scripts\run_strategy_family_experiments.py --as-of-date $date --horizon-days 20 --outputs-dir outputs --cache-dir data\cache\daily-use --write-output
    python backend\scripts\run_aggressive_filter_experiments.py --as-of-date $date --horizon-days 20 --outputs-dir outputs --cache-dir data\cache\daily-use --write-output
}
```

The experiment scripts read existing outputs only. Their same-period results
remain exploratory.

## Summarization

Summarize the four explicit windows:

```powershell
python backend\scripts\summarize_multi_window_experiments.py --outputs-dir outputs --plan-file outputs\experiments\multi_asof_validation_plan_2024.json --windows 2024-01-31:20,2024-04-30:20,2024-07-31:20,2024-10-31:20 --min-valid-count 50 --min-coverage-rate 0.7 --min-filter-sample-count 10 --write-output
```

This summarizes strategy-family and aggressive-filter stability. List
performance and factor effectiveness remain explicit per-window evidence and
must be reviewed from their individual files; they are not silently collapsed
into one score.

## Expected Outputs

For each `<date>`:

```text
outputs/validation/walk_forward_summary_<date>_20d.json
outputs/validation/walk_forward_predictions_<date>_20d.csv
outputs/validation/list_performance_<date>_20d.json
outputs/validation/factor_effectiveness_<date>_20d.json
outputs/validation/walk_forward_report_<date>_20d.md
outputs/portfolios/portfolio_summary_<date>_20d.json
outputs/experiments/strategy_family_experiments_<date>_20d.json
outputs/experiments/aggressive_filter_experiments_<date>_20d.json
```

Cross-window outputs:

```text
outputs/experiments/multi_window_experiment_summary_2024.json
outputs/experiments/multi_window_experiment_summary_2024.md
```

## Completed 2024 Panel Result

The four controlled 20D windows completed with full valid-label coverage:

| as_of_date | valid_future_count | benchmark quality | point-in-time result |
| --- | ---: | --- | --- |
| 2024-01-31 | 435 / 435 | ok | latest input equals as-of date |
| 2024-04-30 | 300 / 300 | ok | latest input equals as-of date |
| 2024-07-31 | 300 / 300 | ok | latest input equals as-of date |
| 2024-10-31 | 300 / 300 | ok | latest input equals as-of date |

Every window reported `no_future_leakage = true` and
`leakage_guard_applied = true`.

List-level interpretation:

- `high_confidence_candidates` had mildly positive average excess return
  across the panel, but was not uniformly strong.
- `trend_leaders` also had mildly positive average excess return and remained
  regime-dependent.
- `long_term_stable` was slightly positive, but not strong enough to establish
  a stable baseline.
- `breakout_watch` and `accumulation_watch` were mixed.
- `high_risk_active` was the clearest directional result: strongly negative
  average excess return across the panel, supporting its use as a risk bucket.

Factor-level interpretation:

- `total_score` top-minus-bottom spread was positive on `2024-01-31` and
  `2024-04-30`, then negative on `2024-07-31` and `2024-10-31`.
- `total_score` therefore appears regime-dependent and does not support a
  production scoring change.
- `volatility` often had a negative top-quantile spread and may be useful as a
  risk warning, subject to further controlled validation.
- `liquidity_score`, `amount`, and `volume` were unstable and require
  attribution before interpretation.

This panel strengthens the evidence that risk separation is useful, while the
positive-list and factor-ranking results remain conditional. It is controlled,
research-only evidence and does not establish final model effectiveness.

## Success Criteria

For every included window:

- `benchmark_data_quality = ok`
- `valid_future_count >= 50`
- `valid_future_count / prediction_count >= 0.7`
- `missing_price_count` and `insufficient_future_window_count` are explicitly reported
- `latest_input_date <= as_of_date`
- `leakage_guard_applied = true`
- `no_future_leakage = true`
- `price_point_in_time_guard_applied = true`
- `feature_input_point_in_time_status = guarded`
- `future_label_window_status = explicit_future_only`
- universe/listing/ST/suspension limitations remain marked
  `current_snapshot_limited`
- list performance, factor effectiveness, and benchmark excess metrics are
  populated where data quality permits

Treat a window with at least 50 valid predictions but coverage below 0.7 as
comparison-eligible low coverage, not as high-quality evidence.

## Stop Conditions

Stop the panel and paste the console JSON back when any of these occurs:

- missing as-of labels, factors, or lists
- readiness reports `missing_cache`
- any command attempts provider access or suggests prewarm
- `benchmark_data_quality != ok`
- `leakage_guard_applied != true`
- `no_future_leakage != true`
- `latest_input_date > as_of_date`
- `valid_future_count < 50`
- malformed or absent bias-limitation metadata

Do not broaden dates, increase the limit, change formulas, or infer production
effectiveness to work around a stopped window.

## Interpretation Guardrails

This is controlled, research-only validation. Price and factor inputs are
point-in-time guarded, but historical universe membership and listing, ST, and
suspension states remain current-snapshot limited.

The Phase 2.11A 20D result is a hypothesis to test, not a target to reproduce.
Do not change scoring or ranking because one list or factor performs well or
poorly in this panel. Require consistency across dates and retain contradictory
windows in the report.

## Later Panel Expansion

After the four-date panel is reviewed, prepare the missing historical as-of
outputs one date at a time, beginning with `2024-12-31`. The cache-first daily
research command can still call its configured provider if cache coverage is
missing; therefore it is not included as a guaranteed offline command in this
runbook. Add or verify a hard cache-only research path before generating the
2025-2026 as-of views under a no-provider requirement.
