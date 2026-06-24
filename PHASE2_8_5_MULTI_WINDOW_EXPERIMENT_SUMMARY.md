# Phase 2.8.5 Multi-Window Experiment Summary

Phase 2.8.5 adds a read-only summarizer for existing strategy family and
aggressive filter experiment outputs across controlled 2024 as-of and horizon
windows.

This phase is research-only. It does not replace production scoring, does not
change model thresholds, does not access BaoStock, does not prewarm cache, and
does not run a full workflow.

## Inputs

- outputs/experiments/strategy_family_experiments_<as_of_date>_<horizon>d.json
- outputs/experiments/aggressive_filter_experiments_<as_of_date>_<horizon>d.json
- outputs/validation/walk_forward_predictions_<as_of_date>_<horizon>d.csv
- outputs/experiments/multi_asof_validation_plan_2024.json

Default behavior:

- Read outputs/experiments/multi_asof_validation_plan_2024.json.
- Include every plan window where ready_for_comparison is true and comparison_eligible is true.
- Label included windows with quality_status, valid prediction count, and valid coverage ratio.
- Include low_coverage windows as exploratory comparison windows when valid count is sufficient.
- Exclude insufficient_valid_count windows from aggregate metrics and list them separately.
- Exclude and explain windows that are missing experiment outputs, blocked by missing as-of outputs, or deferred.
- Optional --windows can still be used to inspect an explicit subset.

## Outputs

- outputs/experiments/multi_window_experiment_summary_2024.json
- outputs/experiments/multi_window_experiment_summary_2024.md

## Manual Command

Dry-run summary:

    python backend/scripts/summarize_multi_window_experiments.py --outputs-dir outputs --plan-file outputs/experiments/multi_asof_validation_plan_2024.json --min-valid-count 50 --min-coverage-rate 0.7 --min-filter-sample-count 10

Write JSON and markdown outputs:

    python backend/scripts/summarize_multi_window_experiments.py --outputs-dir outputs --plan-file outputs/experiments/multi_asof_validation_plan_2024.json --min-valid-count 50 --min-coverage-rate 0.7 --min-filter-sample-count 10 --write-output

## Quality Gates

- `window_min_valid_count` / `--min-valid-count` checks whether a whole as-of/horizon window has enough valid labels for comparison.
- `filter_min_sample_count` / `--min-filter-sample-count` checks whether a specific aggressive filtered subset has enough observations for exploratory comparison.
- `comparison_eligible` is true only when valid_prediction_count >= min_valid_count.
- `high_quality_ready` is true only when comparison_eligible is true and valid coverage ratio >= min_coverage_rate.
- Low-coverage but comparison-eligible windows remain exploratory and are labeled clearly.
- Low-valid-count windows are not silently aggregated as normal evidence.
- Aggressive filters use `min_filter_sample_count` for `sample_too_small`; they do not inherit the window-level `min_valid_count`.

## Interpretation Rules

- Same-period results are exploratory only.
- Filters are not ranked only by average excess return.
- Filters with low sample counts are penalized.
- Filters that destroy right-tail preservation are penalized.
- Filters that improve one window but fail elsewhere remain context-dependent.
- No production scoring changes are recommended by this phase.

## Recommended Use

Use this report to reduce manual copy and paste while reviewing whether strategy
families and aggressive filters remain stable across comparison-eligible
controlled windows listed in the multi-as-of plan. Long-term stable and
conservative quality profiles may become stable baseline candidates only when
supported across windows. Momentum breakout remains an aggressive candidate only
when multi-window evidence supports it. Right-tail hunter requires filters
before candidate use. Volatility expansion remains observation-only unless
filtered results are stable with sufficient sample size.
