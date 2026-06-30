# Phase 2.24 U1 Unseen Result Analysis

## Executive Summary

The four opened U1 20D windows passed the technical validation contract:
all 1,209 evaluated symbols received valid future labels, benchmark quality
was `ok`, `latest_input_date` equaled each `as_of_date`, and both
`leakage_guard_applied` and `no_future_leakage` were true.

The research result is less favorable than the pipeline result:

- No positive list produced stable positive excess return across all four
  windows.
- `long_term_stable` was the strongest defensive baseline. It had the lowest
  average drawdown among the full lists and positive excess return in three
  windows, but its four-window mean excess return was still negative because
  it lagged sharply in the August rally.
- `high_confidence_candidates` remained selective, but neither its cleanliness
  nor its coverage was stable. Its valid membership fell to five in November,
  and it had positive excess return in only two windows.
- `trend_leaders`, `breakout_watch`, and `accumulation_watch` were
  regime-dependent. Later-window underperformance and drawdown do not support
  treating them as stable positive baselines.
- `high_risk_active` was the clearest directional result. Every non-empty
  window had negative excess return, but the first two non-empty samples were
  very small.
- `total_score` was not stable: its top-minus-bottom spread was negative in
  three of four windows. The other requested factors were also mixed.

This is research-only U1 evidence from four controlled, limit-sized windows.
It is not a production-grade historical simulation, does not justify threshold
tuning, and does not authorize any production scoring, ranking, list, or
recommendation change.

## Evaluation Boundary

The evaluated windows were:

```text
2024-02-29 20D
2024-05-31 20D
2024-08-30 20D
2024-11-29 20D
```

The original Phase 2.18 development windows remain forbidden as proof:

```text
2024-01-31 20D
2024-04-30 20D
2024-07-31 20D
2024-10-31 20D
```

Phase 2.18 originally required two ready dates to be opened as U1 and the
remaining ready dates to stay sealed as U2. Validation outputs now exist for
all four candidate dates listed above. Therefore all four dates are consumed
evaluation evidence and none can be treated as sealed U2 confirmation.

No hypothesis definition or threshold may be revised and then re-evaluated on
these same four windows as unseen evidence.

## Technical Integrity

| As-of date | Status | Symbols | Valid labels | Benchmark | Latest feature date | Future rows excluded | Leakage guard | No future leakage |
|---|---:|---:|---:|---|---|---:|---|---|
| 2024-02-29 | ok | 305 | 305 | ok | 2024-02-29 | 170,799 | true | true |
| 2024-05-31 | ok | 300 | 300 | ok | 2024-05-31 | 149,699 | true | true |
| 2024-08-30 | ok | 300 | 300 | ok | 2024-08-30 | 130,499 | true | true |
| 2024-11-29 | ok | 304 | 304 | ok | 2024-11-29 | 114,607 | true | true |

Every window also reports:

```text
price_point_in_time_guard_applied = true
feature_input_point_in_time_status = guarded
future_label_window_status = explicit_future_only
```

The Phase 2.10.1 limitations remain active:

```text
universe_point_in_time_status = current_snapshot_limited
listing_status_point_in_time_status = current_snapshot_limited
st_status_point_in_time_status = current_snapshot_limited
suspension_status_point_in_time_status = current_snapshot_limited
```

The cache contains rows through 2026-06-24, but the reported feature input
ended at each as-of date. Future rows were excluded before feature, scoring,
ranking, and research-list calculation.

## Market Regimes

The benchmark 20D returns implied by the list outputs differed materially:

| As-of date | CSI300 20D return |
|---|---:|
| 2024-02-29 | +0.14% |
| 2024-05-31 | -2.84% |
| 2024-08-30 | +28.14% |
| 2024-11-29 | +1.65% |

The August window is especially important: most lists had strongly positive
absolute returns but negative excess returns. Raw return alone would therefore
give a misleading impression of list quality in that window.

## List-Level Results

Percentages below are unweighted means across windows. A window remains a
separate observation; pooled membership is not used to hide contradictory
results.

| List | Valid members by window | Excess return by window | Mean excess | Median excess | Positive windows | Mean outperform rate | Mean holding drawdown |
|---|---|---|---:|---:|---:|---:|---:|
| `high_confidence_candidates` | 20 / 17 / 18 / 5 | +1.14% / +4.24% / -8.80% / -3.66% | -1.77% | -1.26% | 2/4 | 43.1% | -8.37% |
| `trend_leaders` | 30 / 30 / 30 / 30 | +0.29% / -0.21% / -2.63% / -6.39% | -2.24% | -1.42% | 1/4 | 40.0% | -10.38% |
| `long_term_stable` | 30 / 30 / 30 / 30 | +0.53% / +0.84% / -4.69% / +0.01% | -0.83% | +0.27% | 3/4 | 40.0% | -6.42% |
| `breakout_watch` | 30 / 30 / 30 / 30 | +2.38% / +1.90% / -6.96% / -6.71% | -2.35% | -2.41% | 2/4 | 40.8% | -10.65% |
| `accumulation_watch` | 30 / 30 / 30 / 30 | +1.69% / -8.35% / -1.79% / -5.28% | -3.43% | -3.54% | 1/4 | 30.8% | -13.37% |
| `rebound_watch` | 11 / 14 / 21 / 18 | -2.85% / -6.88% / -0.16% / -1.28% | -2.79% | -2.07% | 0/4 | 30.6% | -10.66% |
| `high_risk_active` | 0 / 3 / 2 / 15 | n/a / -2.44% / -17.42% / -14.54% | -11.46% | -14.54% | 0/3 | 11.1% | -18.56% |

### High confidence: selective but not reliably clean

`high_confidence_candidates` covered only 60 member-window observations and
fell to five valid members in November. It performed well in February and May
but underperformed substantially in August and November. U1 therefore weakens
the claim that the unchanged list is consistently clean. It remains selective,
but its limited and unstable coverage must be shown alongside any favorable
window.

### Long-term stable: defensive behavior, not stable excess

`long_term_stable` had the shallowest mean drawdown of the full 30-name lists
and positive excess return in three windows. Its median window excess was
slightly positive. However, it underperformed by 4.69% in the August rally,
leaving its mean excess negative. U1 directionally supports its role as a
defensive/stability baseline, not as a broad 20D winner catcher or a proven
source of stable excess return.

The top-10 portfolio view was more favorable: mean excess return was +0.79%,
three of four windows were positive, mean outperform rate was 57.5%, and mean
drawdown was -5.44%. This remains a four-window, ten-name research result and
requires sealed confirmation.

### Trend leaders: usefulness weakened; crowding not directly measured

`trend_leaders` had positive excess return in only one window and its worst
result occurred in November, with -6.39% excess return and -15.68% average
holding drawdown. The top-10 portfolio was positive in two windows but had
negative mean excess return.

This weakens the broad usefulness claim. It is consistent with the frozen
concern about regime and crowding sensitivity, but the U1 outputs do not
contain the frozen member-level crowding annotation required to attribute the
underperformance to crowding. The cause must remain unproven.

### Breakout and accumulation: variance and downside remain material

`breakout_watch` was positive in the first two windows and negative in the
last two. Its top-10 portfolio had mean excess return of -5.85% and mean
drawdown of -11.17%. `accumulation_watch` was positive in only one window,
had a 30.8% mean outperform rate, and had the deepest mean drawdown among the
full positive/observation lists at -13.37%.

These results support retaining both as observation lists rather than stable
positive baselines. Direct winner-tail reach and loser-tail contamination were
not recomputed in Phase 2.24, so "pollution" is represented here by weak
outperform rates, negative excess returns, and drawdown, not by a newly
defined loser threshold.

### High risk: directionally stable negative warning

`high_risk_active` was empty in February and contained only three, two, and
15 names in the remaining windows. Every evaluable window had negative excess
return, and the mean holding drawdown was -18.56%. The corresponding
observation portfolio also had negative excess in every non-empty window.

This directionally supports `high_risk_active` as a risk-warning bucket. The
20 total member-window observations, including two very small windows, are not
enough to treat the magnitude as stable or production-grade.

## Factor Effectiveness

The table reports top-quantile minus bottom-quantile future-return spread.

| Factor | Spread by window | Positive windows | Mean spread | Interpretation |
|---|---|---:|---:|---|
| `total_score` | -4.02% / +9.79% / -5.59% / -5.64% | 1/4 | -1.36% | Unstable; U1 weakens a broad ranking claim |
| `risk_score` | -3.46% / +4.64% / -3.11% / +7.48% | 2/4 | +1.39% | Mixed and regime-dependent |
| `volatility` | +5.38% / -3.32% / +9.47% / -8.41% | 2/4 | +0.78% | Sign reverses; neither universal opportunity nor universal penalty |
| `liquidity_score` | -3.90% / +7.88% / -3.20% / +1.95% | 2/4 | +0.68% | Mixed |
| `amount` | -5.60% / +7.68% / -0.22% / -0.81% | 1/4 | +0.27% | Unstable; May dominates the mean |
| `volume` | -2.63% / +3.18% / +1.93% / +0.05% | 3/4 | +0.63% | Direction is more consistent, but magnitude and correlations remain weak |

`total_score` correlation with future return was negative in three windows and
positive only in May. Momentum, trend, and relative-strength spreads followed
a similar pattern. No requested factor is sufficiently stable to justify a
formula or weight change.

Volume had a positive spread in three windows, but one was nearly zero and its
correlations were small and sign-changing. It is a follow-up diagnostic, not
evidence for a production rule.

## Portfolio Validation

| Portfolio | Valid holdings by window | Mean excess | Positive windows | Mean outperform rate | Mean drawdown |
|---|---|---:|---:|---:|---:|
| `long_term_stable_top10` | 10 / 10 / 10 / 10 | +0.79% | 3/4 | 57.5% | -5.44% |
| `accumulation_watch_top10` | 10 / 10 / 10 / 10 | -0.47% | 2/4 | 32.5% | -12.28% |
| `trend_leaders_top10` | 10 / 10 / 10 / 10 | -1.40% | 2/4 | 45.0% | -9.20% |
| `high_confidence_top10` | 10 / 10 / 10 / 5 | -1.55% | 2/4 | 40.0% | -8.65% |
| `mixed_baseline` | 10 / 10 / 9 / 10 | -1.73% | 1/4 | 40.3% | -8.59% |
| `breakout_watch_top10` | 10 / 10 / 10 / 10 | -5.85% | 2/4 | 32.5% | -11.17% |
| `high_risk_active_observation` | 0 / 3 / 2 / 10 | -12.36% | 0/3 | 11.1% | -19.38% |

The portfolio view is consistent with the list view: only
`long_term_stable_top10` had positive mean excess return, while
`high_risk_active_observation` remained directionally negative. Turnover is
still a placeholder, and the outputs use a fixed transaction-cost assumption;
neither is a full multi-rebalance simulation.

The `strategy_experiments_<date>_20d.json` files contain experiment templates
whose `validation_result` remains `not_run`. They do not provide evidence that
the proposed risk filter, list allocation, or membership-stability experiment
worked.

## Frozen Hypothesis Decisions

### Directionally supported

- **B2 `long_term_stable` as a stability baseline:** supported on drawdown and
  three-of-four excess-return signs, but not as a stable excess-return source.
- **B4 `breakout_watch` as a high-variance observation list:** supported by
  sign reversal, weak later windows, and elevated drawdown.
- **B5 `accumulation_watch` as a broad observation list:** supported as a
  cautionary interpretation; U1 does not support it as a stable positive
  baseline.
- **R0 `high_risk_active` as a negative-risk warning:** directionally
  supported in every non-empty window, with a material small-sample caveat.

### Mixed, uncertain, or weakened

- **B1 `high_confidence_candidates`:** mixed and weakened. Selectivity
  remained, but cleanliness was not stable and November coverage was only five.
- **B3 `trend_leaders`:** weakened as a broad positive baseline. Crowding
  sensitivity remains plausible but was not directly tested.
- **B6 `rebound_watch`:** no positive-excess window; it remains
  observation-only and is not supported as a positive baseline.
- **`total_score`, volatility, risk, liquidity, amount, and volume:** all
  remain regime-dependent or too weak for formula changes.

### Not directly evaluated

The generated U1 outputs do not contain frozen, versioned cohorts for:

- H1 `low_position_revaluation_watch`
- H2 `trend_acceleration_with_crowding_guard`
- H3 `right_tail_opportunity_watch`
- H4 `high_position_crowding_risk`
- H5 `false_breakout_risk`

Existing list and factor results may provide context, but they cannot be used
as substitute tests for these hypotheses. Their U1 status is
`insufficient_data`, not supported or rejected.

H6 `theme_event_gap_watch` and H7 `negative_event_or_status_risk` remain
`not_testable_missing_external_data`. Price behavior must not be relabeled as
theme, event, or historical status evidence.

## Decision And U2 Recommendation

No production change is justified.

1. Preserve the current production formulas, rankings, thresholds, candidate
   lists, and recommendation behavior.
2. Record the four U1 dates as consumed. Do not reuse them to validate a
   revised hypothesis.
3. Pre-register a new U2 date manifest because the original four-date pool no
   longer contains sealed windows.
4. Freeze any member-level H1-H5 cohort implementation before opening U2.
5. Run the same point-in-time, cache-only readiness and bias checks before U2.
6. Require U2 to confirm the defensive `long_term_stable` behavior and the
   negative `high_risk_active` direction without relying on one market regime.
7. Keep H1-H5 research-only until their actual frozen cohorts are tested.

Phase 2.18 lists later 2025 dates as a candidate pool, not approved execution
dates. A separate plan must select and commit U2 dates before any outcomes are
opened. Readiness should be based on cache, as-of outputs, future-window
coverage, and leakage metadata, never on expected performance.

## Remaining Limitations

- Four 20D windows are a limited sample.
- The controlled universe is approximately 300 symbols per window, not a
  full-market historical simulation.
- Universe membership and listing, ST, and suspension status are not fully
  historical point-in-time.
- List memberships overlap, so list means are not independent portfolios.
- High-risk samples are empty or very small in three windows.
- Winner-tail capture, loser-tail contamination, crowding attribution, and
  H1-H5 member-level cohorts were not generated for this U1 panel.
- Turnover is not evaluated across rebalance dates.
- Extreme benchmark regimes, especially August, materially affect excess
  comparisons.
- The U1 evidence may reject or weaken a frozen claim, but it must not be used
  to tune a replacement and then claim validation on the same windows.

## Sources Reviewed

The analysis reads existing local outputs only:

```text
outputs/validation/walk_forward_summary_<date>_20d.json
outputs/validation/list_performance_<date>_20d.json
outputs/validation/factor_effectiveness_<date>_20d.json
outputs/portfolios/portfolio_summary_<date>_20d.json
outputs/reviews/portfolio_review_<date>_20d.json
outputs/experiments/strategy_experiments_<date>_20d.json
```

It also follows the frozen interpretation and guardrails in Phases 2.15
through 2.21. No provider was accessed, no validation was rerun, no labels
were recomputed, and no generated output under `outputs/` is part of this
documentation change.
