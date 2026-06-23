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
- outputs/experiments/multi_asof_validation_plan_2024.json

Default windows:

- 2024-01-31 20d
- 2024-01-31 60d
- 2024-01-31 120d
- 2024-04-30 20d
- 2024-04-30 60d

## Outputs

- outputs/experiments/multi_window_experiment_summary_2024.json
- outputs/experiments/multi_window_experiment_summary_2024.md

## Manual Command

Dry-run summary:

    python backend/scripts/summarize_multi_window_experiments.py --outputs-dir outputs --plan-file outputs/experiments/multi_asof_validation_plan_2024.json --min-valid-count 10

Write JSON and markdown outputs:

    python backend/scripts/summarize_multi_window_experiments.py --outputs-dir outputs --plan-file outputs/experiments/multi_asof_validation_plan_2024.json --min-valid-count 10 --write-output

## Interpretation Rules

- Same-period results are exploratory only.
- Filters are not ranked only by average excess return.
- Filters with low sample counts are penalized.
- Filters that destroy right-tail preservation are penalized.
- Filters that improve one window but fail elsewhere remain context-dependent.
- No production scoring changes are recommended by this phase.

## Recommended Use

Use this report to reduce manual copy and paste while reviewing whether strategy
families and aggressive filters remain stable across ready controlled windows.
Long-term stable and conservative quality profiles may become stable baseline
candidates only when supported across windows. Momentum breakout remains an
aggressive candidate only when multi-window evidence supports it. Right-tail
hunter requires filters before candidate use. Volatility expansion remains
observation-only unless filtered results are stable with sufficient sample size.
