# Phase 2.7.3 Simulated Portfolio Review Plan

## Goal

Phase 2.7.3 adds a research-only simulated portfolio validation and review loop on top of Phase 2.7.2 walk-forward labels.

It answers first-pass questions:

- How do list-derived candidate portfolios behave over 20D / 60D future windows?
- Which list portfolios appear stronger or weaker versus CSI300 labels?
- Which price-only signals appear in success and failure cases?
- Which list rules, factor features, and portfolio construction hypotheses should be tested next?

This is a research-only simulated portfolio validation. It is not investment advice.

## Boundaries

- No provider access.
- No prewarm.
- No full workflow.
- No full-market backtest.
- No real trading function.
- No complex ML.
- No financial, valuation, industry, news, or announcement data.
- No future leakage.

Portfolio membership must be built only from fixed as-of list outputs. Future return labels are used only for after-the-fact validation.

## Inputs

Preferred static inputs:

- `outputs/validation/walk_forward_predictions_2024-01-31_60d.csv`
- `outputs/validation/list_performance_2024-01-31_60d.json`
- `outputs/lists/multi_lists_2024-01-31.json`
- `outputs/lists/{list_id}_2024-01-31.json`
- `outputs/labels/stock_labels_2024-01-31.json`
- `outputs/search/stock_index_2024-01-31.json`

The first implementation reads the walk-forward predictions CSV and list JSON files. It does not read provider data.

## Portfolio Types

Initial simulated portfolios:

- `high_confidence_top10`
- `high_confidence_top20`
- `trend_leaders_top10`
- `accumulation_watch_top10`
- `long_term_stable_top10`
- `breakout_watch_top10`
- `mixed_baseline`
- `high_risk_active_observation`

`high_risk_active_observation` is only for risk observation and is not treated as a stable candidate portfolio.

## Portfolio Rules

First-version rules:

- Equal-weight holdings.
- Top 10 / Top 20 list selection.
- 20D / 60D future validation windows.
- Default transaction cost: 10 bps.
- Benchmark: CSI300 labels when available.
- Use only as-of-date lists and labels for portfolio membership.
- Use future returns only for validation.

`mixed_baseline` uses list slots:

- `trend_leaders`: 40%
- `accumulation_watch`: 30%
- `long_term_stable`: 30%

## Metrics

Each simulated portfolio reports:

- `portfolio_id`
- `as_of_date`
- `horizon_days`
- `holding_count`
- `valid_future_count`
- `average_future_return`
- `average_excess_return`
- `median_future_return`
- `win_rate`
- `outperform_rate`
- `average_max_drawdown`
- `best_cases`
- `worst_cases`
- `turnover_placeholder`
- `transaction_cost_bps`
- `net_average_return`
- `notes`

Turnover needs multiple rebalance dates and remains a placeholder in this single-as-of slice.

## Review Logic

The review generator produces:

- Success cases.
- Failure cases.
- List rule improvement hypotheses.
- Factor feature improvement hypotheses.
- Portfolio construction improvement hypotheses.

Reasons are price-only. The current system must not invent financial, industry, valuation, news, or announcement explanations.

All improvement suggestions are marked as:

```text
hypothesis / next experiment
```

They are not validated conclusions.

## Experiment Config

The first version records pending experiment configs:

- `baseline_strategy`
- `experiment_v1`
- `experiment_v2`
- `experiment_v3`

All experiments default to:

```text
accepted_or_rejected = pending
```

## CLI

Dry-run:

```powershell
python backend\scripts\run_portfolio_validation.py --as-of-date 2024-01-31 --horizon-days 60 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 50 --dry-run
```

Write outputs:

```powershell
python backend\scripts\run_portfolio_validation.py --as-of-date 2024-01-31 --horizon-days 60 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 50
```

## Outputs

Non-dry-run writes:

- `outputs/portfolios/portfolio_summary_2024-01-31_60d.json`
- `outputs/portfolios/portfolio_holdings_2024-01-31_60d.csv`
- `outputs/portfolios/portfolio_report_2024-01-31_60d.md`
- `outputs/reviews/portfolio_review_2024-01-31_60d.json`
- `outputs/reviews/portfolio_review_2024-01-31_60d.md`
- `outputs/experiments/strategy_experiments_2024-01-31_60d.json`

Dry-run prints a summary and does not overwrite these formal outputs.

## Limitations

- Current validation is based on a limited Phase 2.7.2 smoke unless the user expands future labels manually.
- Price-only / technical-only.
- No sector or fundamentals.
- No multi-date turnover measurement yet.
- No complex ML.
- No real trading integration.

## Relationship To Later Work

Phase 2.7.3 provides a simulated portfolio review loop. Larger-sample and multi-date runs should be user-managed. Later phases can add controlled latest-date refresh, sector fields, fundamentals, valuation, news, and announcement data after the price-only validation loop is stable.

