# Phase 2.13B Positive List Weakness Attribution

## Goal

Explain why existing positive research lists show only mild or mixed
outperformance, using current memberships, validation labels, factor outputs,
and risk-bucket evidence.

This phase is read-only. It does not access BaoStock, recompute labels, run the
full workflow, or change scoring, ranking, factors, validation math, or
production recommendations.

## Inputs

For the four controlled 2024 20D windows:

```text
outputs/validation/walk_forward_predictions_<date>_20d.csv
outputs/validation/factor_effectiveness_<date>_20d.json
outputs/lists/<list_id>_<date>.json
outputs/lists/high_risk_active_<date>.json
outputs/daily/factors_<date>.csv
outputs/labels/stock_labels_<date>.csv
```

## Available Attribution

The existing outputs support member-level diagnostics for:

- overlap with `high_risk_active`
- `volatility_20d`
- `max_drawdown_20d`
- `risk_score`
- `total_score`
- `liquidity_score`
- `avg_amount_20d`
- `avg_volume_20d`
- benchmark return regime
- full-list versus top-ten breadth dilution

Each window derives percentile warning thresholds from that window's evaluated
symbols. These are attribution diagnostics, not new model thresholds.

## Compared Variants

For every positive list:

- original membership
- excluding `high_risk_active`
- excluding the highest-volatility quantile
- excluding the weakest historical-drawdown quantile
- excluding the lowest `risk_score` quantile
- excluding any available risk warning

The report keeps removed and retained sample counts visible and compares return,
excess return, win rate, benchmark outperform rate, future drawdown, failure
rate below -10%, top-ten performance, and member-level factor exposure.

## Commands

Dry-run:

```powershell
python backend\scripts\summarize_positive_list_attribution.py --outputs-dir outputs --windows 2024-01-31:20,2024-04-30:20,2024-07-31:20,2024-10-31:20 --list-ids high_confidence_candidates,trend_leaders,long_term_stable,breakout_watch,accumulation_watch --warning-quantile 0.20 --min-variant-sample 5
```

Write reports:

```powershell
python backend\scripts\summarize_positive_list_attribution.py --outputs-dir outputs --windows 2024-01-31:20,2024-04-30:20,2024-07-31:20,2024-10-31:20 --list-ids high_confidence_candidates,trend_leaders,long_term_stable,breakout_watch,accumulation_watch --warning-quantile 0.20 --min-variant-sample 5 --write-output
```

## Outputs

```text
outputs/experiments/positive_list_weakness_attribution_2024.json
outputs/experiments/positive_list_weakness_attribution_2024.md
```

## Interpretation

An exclusion is marked improved only as an exploratory result. Review:

- whether improvement appears in most windows
- whether the retained sample remains adequate
- whether drawdown improves alongside excess return
- whether the effect survives different benchmark regimes
- whether factor spread signs remain unstable

This report can identify the next risk-aware candidate-construction hypothesis.
It does not justify changing production scoring from the same four windows.

## Initial Four-Window Finding

The controlled 2024 report found:

- Excluding `high_risk_active` improved only `breakout_watch`, and that result
  remained mixed across windows. The other four positive lists had little or
  no high-risk overlap, so high-risk contamination is not the general cause of
  weak positive-list performance.
- Excluding the highest-volatility quantile improved `breakout_watch` by about
  3.78 percentage points of average excess return and `trend_leaders` by about
  0.58 percentage points. Both improved in three of four windows and are
  classified `improved_consistently_exploratory`.
- The same volatility exclusion slightly weakened
  `high_confidence_candidates`, was neutral for `long_term_stable`, and was
  mixed for `accumulation_watch`. It is therefore a list-specific hypothesis,
  not a universal filter.
- `volatility` factor spread was negative in three of four windows, while
  `risk_score` was positive in three of four. `total_score`,
  `liquidity_score`, `amount`, and `volume` remained mixed.
- One panel window had a positive benchmark return and three had negative
  benchmark returns. Regime context must remain visible in later holdout work.
- Member-level volatility, historical drawdown, amount, volume, total score,
  risk score, and liquidity score were available in all four windows.

The next useful experiment is a holdout validation of volatility-aware
construction for `breakout_watch` and `trend_leaders`. No production formula
change is recommended from this same-period attribution.

## Remaining Limitations

- Only four 2024 windows are included.
- Lists overlap with each other.
- Historical industry, sector, and market-cap fields remain unavailable.
- Universe and status metadata retain current-snapshot limitations.
- New thresholds require separate holdout validation before any production use.
