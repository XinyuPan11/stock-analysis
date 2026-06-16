# Phase 2.7.2 Walk-forward Validation Plan

## Goal

Phase 2.7.2 adds a read-only walk-forward validation framework for the Phase 2.7 research views. The goal is to test whether as-of-date scores, labels, and lists have useful future signal over fixed horizons such as 20 and 60 trading days.

This phase builds the framework and short tests only. It does not run a long full-market validation.

## Why Walk-forward Validation Is Needed

The Phase 2.7 lists are cross-sectional research views. They look at a fixed as-of date and rank stocks using information available up to that date. Walk-forward validation answers whether those lists and factor scores were followed by stronger future returns or excess returns.

The framework helps evaluate:

- Whether `total_score` has future signal.
- Whether list membership is associated with future excess return.
- Which lists, such as `trend_leaders`, `long_term_stable`, `accumulation_watch`, and `breakout_watch`, deserve further trust.
- Whether a list is only visually plausible but weak in later performance.

## Preventing Future Leakage

No future leakage.

The as-of list and labels must be loaded from existing outputs. Future return labels are calculated only after the as-of list is fixed. Future prices must never feed back into as-of factor calculation, labels, ranking, or list generation.

The validator only reads local `outputs/` and `data/cache/` files. It does not access a provider, trigger prewarm, run the daily workflow, or run portfolio simulation.

## As-of Date

An as-of date is a fixed historical research cut, for example `2024-01-31`. The list for that date may only use data available on or before that date.

## Future Return Label Definition

For each stock and horizon:

- `entry_price`: as-of date adjusted close.
- `exit_price`: adjusted close after `horizon_days` future trading rows.
- `future_return`: `exit_price / entry_price - 1`.
- `benchmark_return`: same calculation for the benchmark, default `CSI300`.
- `future_excess_return`: stock future return minus benchmark return.
- `outperformed_benchmark`: whether excess return is positive.
- `future_top_quantile`: whether the stock is in the top future-return quantile among evaluated symbols.
- `max_drawdown_during_holding`: worst drawdown during the future holding window.
- `data_quality`: `ok`, `missing_price`, `insufficient_future_window`, or another explicit status.

## List Performance Metrics

For each supported list and horizon:

- `item_count`
- `valid_future_count`
- `average_future_return`
- `average_excess_return`
- `median_future_return`
- `win_rate`
- `outperform_rate`
- `top_10_average_return`
- `top_20_average_return`
- `max_drawdown_average`
- `best_cases`
- `worst_cases`
- `notes`

Supported first-pass lists:

- `high_confidence_candidates`
- `trend_leaders`
- `long_term_stable`
- `breakout_watch`
- `accumulation_watch`
- `rebound_watch`
- `high_risk_active`

## Factor Effectiveness Metrics

The first pass evaluates simple factor effectiveness by joining as-of factors with future return labels:

- `correlation_with_future_return`
- `top_quantile_average_return`
- `bottom_quantile_average_return`
- `spread`
- `top_quantile_outperform_rate`
- `notes`

Missing factor columns are recorded as `missing_factor` rather than failing the whole run.

## Output File Design

For one as-of date and horizon, the optional write mode produces:

- `outputs/validation/walk_forward_summary_YYYY-MM-DD_20d.json`
- `outputs/validation/walk_forward_predictions_YYYY-MM-DD_20d.csv`
- `outputs/validation/list_performance_YYYY-MM-DD_20d.json`
- `outputs/validation/factor_effectiveness_YYYY-MM-DD_20d.json`
- `outputs/validation/walk_forward_report_YYYY-MM-DD_20d.md`

Dry-run mode prints a summary and writes no files.

## Out of Scope This Round

- No latest-date data refresh.
- No provider access.
- No prewarm.
- No full workflow.
- No full-market portfolio backtest.
- No financial, valuation, news, or announcement data.
- No complex ML training.
- No simulated portfolio validation.

## Relationship to Phase 2.7.3

Phase 2.7.2 validates static list and factor signal quality. Phase 2.7.3 can later add controlled simulated portfolio validation using the strongest lists and horizons identified here.

