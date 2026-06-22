# Phase 2.8.3 Aggressive Strategy Filter Optimization Framework

## Scope

Phase 2.8.3 adds a research-only framework for testing aggressive strategy filters. It does not replace production scoring and does not change current candidate-list generation.

The framework reads existing outputs only:

- `outputs/validation/walk_forward_predictions_<as_of_date>_<horizon>d.csv`
- `outputs/validation/list_performance_<as_of_date>_<horizon>d.json`
- `outputs/validation/factor_effectiveness_<as_of_date>_<horizon>d.json`
- `outputs/experiments/strategy_family_experiments_<as_of_date>_<horizon>d.json`
- `outputs/portfolios/portfolio_summary_<as_of_date>_<horizon>d.json`
- `outputs/daily/factors_<as_of_date>.csv`

No provider access, prewarm, full workflow, full-market validation, or 2025 validation is part of this phase.

## Source Families

The experiment focuses on aggressive/right-tail families from Phase 2.8.2:

- `momentum_breakout`
- `volatility_expansion`
- `right_tail_hunter`

`anti_high_risk_filter` remains a risk-control reference from Phase 2.8.2, not a replacement model.

## Filter Families

The default experiment profiles are:

- `baseline_aggressive`
- `aggressive_volatility_cap`
- `aggressive_drawdown_control`
- `aggressive_momentum_quality`
- `aggressive_liquidity_sanity`
- `aggressive_anti_lottery`
- `aggressive_combined_quality`

Filter inputs are restricted to as-of features such as total score, risk score, momentum score, trend score, liquidity score, volatility, drawdown, amount, and volume. Optional proxy features are reported as missing when unavailable; the framework does not invent them.

## Anti-Leakage Rules

- Future returns are labels/evaluation metrics only.
- Future excess return, future drawdown, benchmark outcome, best cases, and worst cases are not filter features.
- Same-period results are marked `exploratory_same_period`.
- Results can only move to `holdout_validated` after separate holdout dates are tested.
- Reports include a research-only disclaimer and an anti-leakage statement.

Supported validation statuses:

- `exploratory_same_period`
- `pre_registered_same_period`
- `holdout_validated`
- `insufficient_data`

## Metrics

Each result reports:

- source strategy family and filter ID
- symbol count before and after filtering
- valid future count
- average future return
- average excess return
- outperform rate
- top-decile and top-5 average return
- best and worst case return
- payoff ratio and right-tail ratio
- average future holding-window drawdown
- failure rates below -10% and -20%
- negative return rate
- right-tail preservation ratio versus same-family baseline
- left-tail reduction ratio versus same-family baseline
- notes and validation status

## Outputs

When `--write-output` is used, the script writes:

- `outputs/experiments/aggressive_filter_experiments_<as_of_date>_<horizon>d.json`
- `outputs/experiments/aggressive_filter_experiments_<as_of_date>_<horizon>d.md`

Default script mode is dry-run.

## Manual Command

```powershell
python backend\scripts\run_aggressive_filter_experiments.py --as-of-date 2024-01-31 --horizon-days 120 --outputs-dir outputs --cache-dir data\cache\daily-use --write-output
```

## Limitations

- Research-only; not investment advice.
- Does not replace production scoring.
- Same-period results are exploratory only.
- Only controlled 2024 as-of dates should be used in this phase.
- No holdout validation yet.
- Still price-only / technical-only.
- No full-market validation yet.
- No 2025 validation yet.
