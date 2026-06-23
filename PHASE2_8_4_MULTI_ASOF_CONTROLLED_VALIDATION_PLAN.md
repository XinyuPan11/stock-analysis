# Phase 2.8.4 Multi-As-Of Controlled Validation Plan

## Scope

Phase 2.8.4 prepares a research-only planning framework for validating existing strategy families and aggressive filters across multiple controlled 2024 as-of dates.

This phase does not:

- change production scoring
- add new model thresholds
- access BaoStock automatically
- prewarm automatically
- run full workflow
- run full-market validation
- enter 2025 validation
- run long data jobs

## Controlled Dates And Horizons

Candidate as-of dates:

- `2024-01-31`
- `2024-04-30`
- `2024-07-31`
- `2024-10-31`

Validation horizons:

- `20d`
- `60d`
- `120d`

## Anti-Leakage Rules

For each as-of date, features, lists, filters, and dynamic states must use only data available on or before that as-of date.

Future returns, future drawdowns, and benchmark outcomes are labels/evaluation metrics only.

Do not tune filters on one as-of date and report the same date as validated. Same-period findings remain research-only until they are checked on separate as-of dates.

Future window target end dates reuse the existing validation cache plan logic in backend/src/stock_analysis/validation/cache_plan.py. The planner does not use a simple calendar-day horizon as the cache end date.

If required as-of labels, factor rows, or list outputs are missing, cache requirements are marked blocked_missing_as_of_outputs. A zero symbol_count in that state is blocked, not cache-complete.

Any horizon window that requires 2025 future data is listed as deferred. Phase 2.8.4 does not generate prewarm or validation commands for 2025 windows.

## Planned Comparisons

The framework prepares comparisons for:

- Phase 2.8.2 strategy family metrics
- Phase 2.8.3 aggressive filter experiments
- dynamic aggressive state history

Focus filters:

- `volatility_cap_filter`
- `drawdown_control_filter`
- `combined_aggressive_quality_filter`

Primary comparison metrics:

- `right_tail_preservation_ratio`
- `left_tail_reduction_ratio`
- `payoff_ratio`
- `right_tail_ratio`
- `failure_rate_below_minus_10pct`
- `failure_rate_below_minus_20pct`

## Dynamic State History

The framework prepares state history tracking for:

- `eligible`
- `watch_only`
- `blocked_now`
- `cooldown`
- `re_entry_candidate`

Phase 2.8.4 does not implement full dynamic add/reduce/exit logic. `cooldown` and `re_entry_candidate` require previous as-of state history before they can be fully validated.

## Outputs

The planning script writes:

- `outputs/experiments/multi_asof_validation_plan_2024.json`
- `outputs/experiments/multi_asof_cache_plan_2024.json`
- `outputs/experiments/multi_asof_validation_summary_2024.md`

These outputs are planning artifacts. They do not mean cache prewarm, market data fetching, or validation jobs have been run.

## Manual Command

```powershell
python backend\scripts\generate_multi_asof_validation_plan.py --outputs-dir outputs --cache-dir data\cache\daily-use
```

## Known Limitations

- Research-only.
- Does not replace production scoring.
- Does not run long data jobs automatically.
- Requires user-controlled cache prewarm for missing windows.
- Requires per-as-of list/label outputs before full comparison.
- No 2025 validation yet.


