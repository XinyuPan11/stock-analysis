# Phase 2.29 U2 Sealed Confirmation Result Analysis

## Executive Summary

The four preregistered U2 windows passed the technical validation contract.
All 1,219 evaluated symbols received valid 20D labels, benchmark quality was
`ok`, each `latest_input_date` equaled its `as_of_date`, and both
`leakage_guard_applied` and `no_future_leakage` were true.

U2 does not support a broad production change:

- `long_term_stable` confirmed its defensive behavior: its average holding
  drawdown was shallower than `trend_leaders`, `breakout_watch`, and
  `accumulation_watch` in all four windows. Its excess return was nevertheless
  negative in three windows.
- `high_risk_active` did not confirm the U1 stable-negative interpretation.
  It had two negative and two positive excess-return windows, and its 28 total
  member-window observations missed the preregistered minimum of 30.
- `high_confidence_candidates` had better coverage than U1, but failed the
  preregistered cleanliness tests. Its favorable mean was dominated by the
  November window.
- `trend_leaders` remained regime-dependent rather than a stable positive
  baseline.
- `breakout_watch` and `accumulation_watch` retained observation-list risk:
  signs and payoff varied materially, outperform rates were weak, and drawdown
  remained elevated.
- `total_score` again had negative correlation and negative top-minus-bottom
  spread in three of four windows. U2 supports the frozen no-reweighting
  decision.

This is one research-only analysis of four limit-sized U2 windows under the
Phase 2.25 rules. U2 is now consumed. It must not be reused for threshold
tuning or for validating a post-U2 revision.

## Frozen Evaluation Boundary

U2 windows opened once in Phase 2.28 and analyzed here:

```text
2025-02-28 20D
2025-05-30 20D
2025-08-29 20D
2025-11-28 20D
```

The following remain permanently forbidden as proof:

```text
2024-01-31 20D
2024-04-30 20D
2024-07-31 20D
2024-10-31 20D
```

The following are consumed U1 evidence and are not new confirmation windows:

```text
2024-02-29 20D
2024-05-31 20D
2024-08-30 20D
2024-11-29 20D
```

No threshold, formula, cohort, or hypothesis definition was changed while
interpreting U2.

## Execution And Leakage Guardrails

| As-of date | Status | Symbols | Valid labels | Benchmark | Latest feature date | Future rows excluded | Leakage guard | No future leakage |
|---|---:|---:|---:|---|---|---:|---|---|
| 2025-02-28 | ok | 303 | 303 | ok | 2025-02-28 | 96,656 | true | true |
| 2025-05-30 | ok | 304 | 304 | ok | 2025-05-30 | 78,431 | true | true |
| 2025-08-29 | ok | 306 | 306 | ok | 2025-08-29 | 59,363 | true | true |
| 2025-11-28 | ok | 306 | 306 | ok | 2025-11-28 | 41,309 | true | true |

Across the panel:

```text
symbol_count = 1,219
valid_future_count = 1,219
valid coverage = 100%
future_rows_excluded_count = 275,759
```

Every window reports:

```text
price_point_in_time_guard_applied = true
feature_input_point_in_time_status = guarded
future_label_window_status = explicit_future_only
```

The known bias limitations remain:

```text
universe_point_in_time_status = current_snapshot_limited
listing_status_point_in_time_status = current_snapshot_limited
st_status_point_in_time_status = current_snapshot_limited
suspension_status_point_in_time_status = current_snapshot_limited
```

The raw cache extended through 2026-06-24, but features ended at each as-of
date. Future data was used only by explicit label/evaluation paths.

## Market Context

The CSI300 20D returns implied by the list outputs were:

| As-of date | CSI300 20D return |
|---|---:|
| 2025-02-28 | +0.65% |
| 2025-05-30 | +2.50% |
| 2025-08-29 | +1.19% |
| 2025-11-28 | +2.88% |

All four benchmark windows were positive, but their magnitudes were far less
extreme than the U1 August rally. Excess return remains the controlling
cross-window comparison.

## List-Level Results

The table keeps every window visible. Cross-window means are unweighted and do
not replace the per-window evidence.

| List | Valid members by window | Excess return by window | Mean excess | Median excess | Positive windows | Mean outperform rate | Mean drawdown |
|---|---|---|---:|---:|---:|---:|---:|
| `high_confidence_candidates` | 10 / 16 / 12 / 14 | -0.04% / -2.18% / +1.60% / +14.41% | +3.45% | +0.78% | 2/4 | 48.9% | -9.01% |
| `trend_leaders` | 30 / 30 / 30 / 30 | +1.07% / -2.46% / -4.19% / +9.14% | +0.89% | -0.69% | 2/4 | 41.7% | -10.73% |
| `long_term_stable` | 30 / 30 / 30 / 30 | +2.79% / -1.42% / -2.41% / -3.31% | -1.09% | -1.92% | 1/4 | 34.2% | -4.04% |
| `breakout_watch` | 30 / 30 / 30 / 30 | -0.92% / +1.49% / -3.80% / +7.71% | +1.12% | +0.29% | 2/4 | 43.3% | -11.45% |
| `accumulation_watch` | 30 / 30 / 30 / 30 | +2.61% / +0.81% / +1.16% / -5.28% | -0.18% | +0.98% | 3/4 | 36.7% | -10.16% |
| `rebound_watch` | 10 / 19 / 18 / 16 | -2.55% / +7.23% / -0.28% / -3.26% | +0.28% | -1.42% | 1/4 | 33.8% | -7.32% |
| `high_risk_active` | 10 / 4 / 8 / 6 | -9.02% / +8.63% / -7.50% / +6.71% | -0.29% | -0.39% | 2/4 | 30.6% | -15.93% |

### R0 high risk: not confirmed

The preregistered R0 gate required at least three non-empty windows, at least
30 total member-window observations, negative excess return in at least three
eligible windows, and worse downside than a relevant disjoint comparison when
available.

U2 had four non-empty windows but only 28 member-window observations. Excess
return was negative in February and August and positive in May and November.
The bucket retained the deepest mean drawdown among the full lists, but it did
not satisfy the count or sign-consistency gates.

R0 is therefore `insufficient_data` with mixed direction, not directionally
confirmed. U2 weakens the stable-negative interpretation from U1. The result
must not be rescued by pooling U1 and U2 or by changing the threshold.

### B2 long-term stable: defensive behavior confirmed

The preregistered defensive test required `long_term_stable` to have shallower
average holding drawdown than `trend_leaders`, `breakout_watch`, and
`accumulation_watch` in at least three windows. It was shallower than all three
comparators in all four U2 windows.

This confirms the defensive behavior question. It does not confirm stable
excess return: only February was positive, and the four-window mean excess was
-1.09%. The top-10 portfolio also had negative excess in three windows while
retaining a shallow -4.03% mean drawdown.

### B1 high confidence: coverage improved, stability did not

Valid membership was 10, 16, 12, and 14, so U2 did not repeat U1's five-name
coverage collapse. Valid future coverage was complete.

The other preregistered promotion gates failed: excess return was positive in
only two windows, and outperform rate exceeded 50% only in November. The
+14.41% November result lifted the mean while the per-window evidence remained
mixed. B1 remains `mixed_or_regime_dependent`; no promotion is supported.

### B3 trend leaders: stable positive baseline rejected

The frozen positive-baseline gate required positive excess return and an
outperform rate above 50% in at least three windows without severe drawdown
deterioration. U2 produced positive excess in two windows and outperform above
50% only in November. Median window excess was negative.

The stable-positive interpretation is not supported. U2 is consistent with
the U1 regime-dependent posture. Crowding was not directly measured, so the
result cannot be causally attributed to crowding.

### B4 breakout: high variance confirmed

`breakout_watch` alternated negative and positive excess-return windows. Its
+1.12% mean excess was accompanied by a 43.3% mean outperform rate and -11.45%
mean drawdown. The top-10 portfolio was positive in three windows but had an
even deeper -13.89% mean drawdown and only a 45% mean outperform rate.

U2 confirms the high-variance observation-list interpretation. The favorable
right tail does not justify promotion.

### B5 accumulation: U1 direction weakened, observation posture retained

`accumulation_watch` had positive excess in three U2 windows, unlike its mostly
negative U1 result. This weakens the U1 directional return finding.

However, the November loss left mean excess slightly negative, mean outperform
rate was only 36.7%, and mean drawdown was -10.16%. The top-10 portfolio was
positive in only one window. U2 therefore does not establish a stable positive
list. The broad, high-variance observation posture remains appropriate.

### Rebound: one-window concentration remains

`rebound_watch` had positive excess only in May. Its positive mean was caused
by that single +7.23% window while the median window was negative. It remains
observation-only.

## Factor Effectiveness

The table reports top-quantile minus bottom-quantile future-return spread.

| Factor | Spread by window | Positive windows | Mean spread | U2 interpretation |
|---|---|---:|---:|---|
| `total_score` | -3.20% / -1.26% / -4.61% / +11.17% | 1/4 | +0.53% | Negative in 3/4; mean rescued by November |
| `risk_score` | +2.51% / -2.56% / -1.81% / -2.28% | 1/4 | -1.03% | Mostly negative |
| `volatility` | -5.20% / +2.74% / -1.45% / +9.02% | 2/4 | +1.28% | Sign-changing |
| `liquidity_score` | -3.43% / -2.15% / -5.02% / +9.44% | 1/4 | -0.29% | Negative in 3/4 |
| `amount` | -3.87% / -0.69% / -3.36% / +8.11% | 1/4 | +0.05% | Negative in 3/4; November dominates mean |
| `volume` | -5.40% / -2.39% / -0.64% / +1.17% | 1/4 | -1.82% | Negative in 3/4 |
| `drawdown` | +1.22% / -3.33% / +1.83% / -1.06% | 2/4 | -0.34% | Mixed |

`total_score` correlation with future return was also negative in the first
three windows and positive only in November. The preregistered strong-opposite
evidence gate required positive correlation and positive spread in at least
three windows. U2 produced only one of each.

F0 therefore supports no reweighting. Momentum, trend, relative strength,
liquidity, amount, and volume show the same broad pattern of weak or
regime-dependent signs. No factor change is justified.

## Portfolio Validation

| Portfolio | Valid holdings by window | Mean excess | Positive windows | Mean outperform rate | Mean drawdown |
|---|---|---:|---:|---:|---:|
| `trend_leaders_top10` | 10 / 10 / 10 / 10 | +5.25% | 2/4 | 55.0% | -9.74% |
| `high_confidence_top10` | 10 / 10 / 10 / 10 | +4.23% | 2/4 | 45.0% | -9.08% |
| `breakout_watch_top10` | 10 / 10 / 10 / 10 | +2.52% | 3/4 | 45.0% | -13.89% |
| `mixed_baseline` | 10 / 10 / 10 / 10 | +2.32% | 2/4 | 40.0% | -8.31% |
| `accumulation_watch_top10` | 10 / 10 / 10 / 10 | -1.99% | 1/4 | 32.5% | -10.05% |
| `long_term_stable_top10` | 10 / 10 / 10 / 10 | -2.22% | 1/4 | 30.0% | -4.03% |
| `high_risk_active_observation` | 10 / 4 / 8 / 6 | -0.29% | 2/4 | 30.6% | -15.93% |

Positive portfolio means for trend, high confidence, breakout, and the mixed
baseline were concentrated in a subset of windows, especially November. The
per-window sign and drawdown evidence does not support a stable portfolio
claim. Turnover remains a placeholder rather than a multi-rebalance result.

The `strategy_experiments_2025-*_20d.json` files remain templates with
`validation_result = not_run` and `accepted_or_rejected = pending`. They do
not validate a filter, alternative allocation, or membership-stability
experiment.

## U1 Versus U2

| Research question | U1 | U2 | Combined interpretation |
|---|---|---|---|
| R0 high-risk warning | Negative in every non-empty window, but only 20 observations | Two negative and two positive windows; 28 observations | U2 does not confirm stable negative direction; retain as research-only and insufficient |
| B2 long-term stable | Defensive drawdown, excess mixed | Shallowest drawdown in 4/4 comparator tests, excess negative in 3/4 | Defensive behavior confirmed; excess-return claim rejected |
| B1 high confidence | Coverage and cleanliness unstable | Coverage improved, performance still 2/4 positive and November-heavy | Mixed; no promotion |
| B3 trend leaders | Weak/regime-dependent | Positive in 2/4 with negative median window excess | Regime dependence confirmed; stable positive baseline unsupported |
| B4 breakout | High variance and elevated downside | Alternating signs, elevated drawdown, right-tail concentration | High-variance observation posture confirmed |
| B5 accumulation | Mostly negative | Positive in 3/4, but low outperform rate and one large negative window | U1 return direction weakened; observation posture retained |
| F0 total score | Negative spread in 3/4 | Negative spread and correlation in 3/4 | No-reweighting decision confirmed |

U1 and U2 may be compared for consistency, but they must not be pooled and
relabeled as a new unseen test.

## Frozen Hypothesis Decisions

### Confirmed by U2

- **B2:** `long_term_stable` confirmed defensive drawdown behavior, not stable
  excess return.
- **B3:** the unchanged `trend_leaders` list is not a stable positive baseline.
- **B4:** `breakout_watch` remains a high-variance observation list.
- **F0:** `total_score` does not provide the strong opposite evidence required
  for reweighting.

### Mixed or weakened by U2

- **R0:** `high_risk_active` is `insufficient_data` and directionally mixed;
  U2 weakens the U1 stable-negative interpretation.
- **B1:** `high_confidence_candidates` coverage improved but performance
  remained unstable.
- **B5:** U2 weakened the mostly-negative U1 return direction, while retaining
  the high-variance observation interpretation.
- **B6:** `rebound_watch` remained one-window-dependent and observation-only.
- **Other factors:** risk, volatility, liquidity, amount, volume, momentum,
  trend, relative strength, and drawdown remained mixed or unstable.

### Contradicted or rejected

- Stable positive excess-return interpretations for `long_term_stable` and
  `trend_leaders` are not supported.
- The U1 claim that `high_risk_active` was directionally stable negative was
  not confirmed under its preregistered U2 gate.
- No Phase 2.17 candidate redesign hypothesis receives production approval.

### Still not evaluated or untestable

H1-H5 remain `insufficient_data_not_evaluated` because their frozen,
versioned member-level cohorts were not implemented before U2 opened:

```text
H1 low_position_revaluation_watch
H2 trend_acceleration_with_crowding_guard
H3 right_tail_opportunity_watch
H4 high_position_crowding_risk
H5 false_breakout_risk
```

They cannot be retrofitted to these consumed U2 windows.

H6 `theme_event_gap_watch` and H7 `negative_event_or_status_risk` remain
`not_testable_missing_external_data`.

## Production Design Consideration

No production change is authorized.

The only result eligible for a later, separate design review is the confirmed
defensive posture of `long_term_stable`. That review must preserve the fact
that its excess return was negative in three U2 windows and must not convert a
20D price-defense result into a claim of fundamental quality.

`high_risk_active`, `high_confidence_candidates`, `trend_leaders`,
`breakout_watch`, `accumulation_watch`, and all factor-weight ideas remain
research-only.

## Remaining Limitations

- U2 contains four 20D, approximately 300-symbol controlled windows.
- This is not a full-market or production-grade historical simulation.
- Historical universe membership and listing, ST, and suspension status remain
  current-snapshot limited.
- Lists overlap and are not independent portfolios.
- R0 had only 28 member-window observations, below its frozen minimum of 30.
- H1-H5 member-level cohorts were not available before U2 opened.
- H6-H7 require historical external data.
- Direct winner-tail pollution and crowding attribution were not recomputed.
- Portfolio turnover remains unvalidated.
- November materially lifts several cross-window means.
- U2 is consumed and cannot validate any threshold or hypothesis revision
  inspired by this report.

## Decision And Recommended Next Phase

1. Keep production scoring, ranking, factors, candidate selection, lists,
   thresholds, and recommendation behavior unchanged.
2. Record all four U2 windows as consumed.
3. Do not tune R0, B1-B5, or F0 against U2 and rerun them on the same dates.
4. If pursuing `long_term_stable`, open a documentation/design phase that
   defines defensive monitoring separately from excess-return claims; do not
   implement production behavior yet.
5. If any hypothesis is revised, preregister a later unopened holdout before
   implementation or result inspection.
6. Keep H1-H5 deferred unless their versioned point-in-time cohorts can be
   frozen before a new holdout.

The recommended next phase is a post-U2 decision ledger and holdout governance
phase. Its purpose should be to freeze what is retained, rejected, or deferred
and to reserve a later holdout, not to tune the model.

## Sources Reviewed

This report reads existing local U2 outputs only:

```text
outputs/validation/walk_forward_summary_<date>_20d.json
outputs/validation/list_performance_<date>_20d.json
outputs/validation/factor_effectiveness_<date>_20d.json
outputs/portfolios/portfolio_summary_<date>_20d.json
outputs/reviews/portfolio_review_<date>_20d.json
outputs/experiments/strategy_experiments_<date>_20d.json
```

No provider was accessed, no validation was run, no label was recomputed, and
no generated file under `outputs/` was modified.
