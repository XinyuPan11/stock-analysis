# Phase 2.8.2 Strategy Family Experiment Framework

## Scope

Phase 2.8.2 adds a research-only strategy family experiment framework. It does not replace production scoring, candidate labels, list generation, portfolio validation, or any existing Phase 2.8.1 validation flow.

The framework reads existing local outputs and validation artifacts. It does not access BaoStock, prewarm cache, run the full workflow, run full-market validation, or enter 2025.

## Why This Exists

The current 2024-01-31, 120d, limit-1000 controlled validation shows conservative and stable lists performing better on average. That does not mean aggressive opportunity models should be removed or forced into conservative behavior.

Different strategy families need different evaluation objectives:

- Conservative families emphasize stable excess return, high outperform rate, and controlled drawdown.
- Aggressive families may tolerate lower hit rate if successful cases have much larger upside and failure losses are controlled.
- Risk-filter families are observation-only and help identify names that should remain excluded or separately monitored.

## Strategy Families

- `conservative_quality`: stable excess return, high outperform rate, controlled drawdown.
- `long_term_stable`: lower volatility, lower drawdown, persistent positive return.
- `momentum_breakout`: trend continuation with fake-breakout failure analysis.
- `volatility_expansion`: upside from volatility expansion, separated from noisy high volatility.
- `right_tail_hunter`: lower hit rate is acceptable only when upside tail is meaningfully larger than downside tail.
- `anti_high_risk_filter`: observation-only risk filter for exclusion and monitoring analysis.

## Metrics

Conservative families focus on:

- `average_excess_return`
- `outperform_rate`
- `win_rate`
- `max_drawdown_average`
- `negative_return_rate`
- `stability_score`

Aggressive and right-tail families also include:

- `hit_rate`
- `average_future_return`
- `top_decile_average_return`
- `top_5_average_return`
- `best_case_return`
- `worst_case_return`
- `payoff_ratio`
- `right_tail_ratio`
- `failure_rate_below_minus_10pct`
- `failure_rate_below_minus_20pct`

## Inputs

Primary inputs are existing local artifacts:

- `outputs/validation/walk_forward_predictions_2024-01-31_120d.csv`
- `outputs/validation/list_performance_2024-01-31_120d.json`
- `outputs/validation/factor_effectiveness_2024-01-31_120d.json`
- `outputs/portfolios/portfolio_summary_2024-01-31_120d.json`
- `outputs/lists/*_2024-01-31.json`

## Outputs

When run with `--write-output`, the framework writes:

- `outputs/experiments/strategy_family_experiments_2024-01-31_120d.json`
- `outputs/experiments/strategy_family_experiments_2024-01-31_120d.md`

The markdown report separates:

- Conservative strategy results
- Aggressive strategy results
- Right-tail opportunity results
- Failure/risk analysis
- Recommended next experiments

## Recommended Command

```powershell
python backend\scripts\run_strategy_family_experiments.py --as-of-date 2024-01-31 --horizon-days 120 --outputs-dir outputs --cache-dir data\cache\daily-use --write-output
```

Omit `--write-output` for dry-run summary only.

## Guardrails

- Research-only.
- No production scoring replacement.
- No BaoStock access.
- No prewarm.
- No full workflow.
- No full-market validation.
- No 2025 validation.
- Price-only / technical-only.
- No finance, valuation, industry, news, or announcement data.
- No automatic trading or public investment advice.

