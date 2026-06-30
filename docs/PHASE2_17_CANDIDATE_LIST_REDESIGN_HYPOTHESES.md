# Phase 2.17 Candidate List Redesign Hypotheses

## Status And Boundary

Phase 2.17 translates Phase 2.13-2.16 evidence into research hypotheses. It
does not implement, rename, remove, or reorder any production list.

The 2024 results are answer-key / in-sample evidence. These hypotheses cannot
be validated on the same 2024 windows used to derive them. The next proof must
use separate unseen windows. No threshold tuning should be performed against
the 2024 winners.

This phase changes no:

- production scoring or ranking
- factor or validation-label calculation
- candidate-selection logic
- list membership or list names
- thresholds
- recommendation logic

Every name below denotes a hypothesis or future experimental posture unless it
is explicitly identified as an unchanged existing list.

## Evidence Base

### Answer-key cases

The 30 researched cases contained 20 winners and 10 losers:

- 6/20 winners were captured by existing positive lists.
- 14/20 winners were missed.
- 1/10 losers entered a positive list.
- No winner entered `high_risk_active`.
- Missed winners concentrated in theme/policy, event revaluation,
  low-position reversal, distressed turnaround, and high-volatility right-tail
  archetypes.

This selected case set is useful for error explanation, not for estimating
population performance.

### Four-window member-level panel

The 2024 four-window 20D panel contained 1,335 point-in-time snapshot rows:

- winner tail: 134
- captured winners: 37
- missed winners: 97
- positive-list loser tail: 29
- `high_risk_active` mean excess return: about -7.26%
- disjoint non-high-risk mean excess return: about -1.28%

Captured winners had much stronger existing total score, trend score, and
20D/60D pre-move trend context than missed winners. Existing lists therefore
capture a relatively narrow established-score/trend subset.

Within positive lists, loser-tail rows were more volatile, had deeper
drawdowns, stronger prior trend and amount expansion, and a higher crowding
proxy than winner-tail rows. This is descriptive evidence for crowding and
false-breakout research, not a fitted filter.

### Existing list tail counts

| Existing list | Winner tail | Loser tail | Loser share among tails | Research reading |
|---|---:|---:|---:|---|
| `high_confidence_candidates` | 11 | 3 | 21.4% | Relatively clean, narrow established-profile baseline |
| `trend_leaders` | 15 | 6 | 28.6% | Useful established-trend baseline with crowding risk |
| `long_term_stable` | 9 | 1 | 10.0% | Cleanest observed tail ratio, limited winner coverage |
| `breakout_watch` | 14 | 14 | 50.0% | High-variance and ambiguous |
| `accumulation_watch` | 16 | 14 | 46.7% | Largest winner count, but substantial loser contamination |
| `rebound_watch` | 0 | 2 | 100.0% | Only two tail observations; insufficient evidence |

Counts overlap because one symbol may appear in several lists. They are not
independent portfolios.

## Current List Research Postures

No posture in this table changes production behavior.

| Existing list | Phase 2.17 posture | Possible future interpretation |
|---|---|---|
| `high_confidence_candidates` | Preserve and monitor | Established quality/trend baseline, not a broad 20D right-tail catcher |
| `long_term_stable` | Preserve and monitor | Stability baseline with narrow short-horizon capture |
| `trend_leaders` | Preserve and monitor | Established trend baseline; study crowding separately |
| `breakout_watch` | Downgrade/reinterpret in research | High-variance breakout observation rather than implicit confidence |
| `accumulation_watch` | Downgrade/reinterpret in research | Broad staging/observation list requiring persistence and contamination analysis |
| `rebound_watch` | Downgrade to observation-only | Insufficient sample; no general conclusion |
| `high_risk_active` | Preserve as risk-warning baseline | Stable negative-risk diagnostic, never a positive candidate source |

## A. Preserve And Monitor

### 1. `high_confidence_candidates`

**Motivation from evidence**

The list captured 11 winner-tail rows and 3 loser-tail rows. Captured winners
generally had much stronger existing scores and trend context than missed
winners. The list appears to represent an established profile rather than the
full set of short-horizon winners.

**Case-study examples**

Relevant captured archetypes include stable-quality compounder,
trend-continuation, high-dividend defensive, and established revaluation
cases. These examples are supplemental answer-key evidence only.

**Existing data support**

Total score, momentum, trend, relative strength, risk, liquidity, drawdown,
volatility, and existing list membership.

**Missing data support**

Historical fundamentals, valuation, industry context, announcements, and
point-in-time status metadata.

**Guardrails**

Preserve the current list unchanged. Do not broaden it to include known 2024
winners, and do not treat it as an explosive-winner list.

**Why it is not production-ready for redesign**

Its relative cleanliness and narrow capture come from the same four 2024
windows used to form this interpretation.

**Required unseen-window validation**

Compare unchanged membership, winner-tail capture, loser-tail contamination,
excess return, drawdown, and high-risk overlap across separate dates and
regimes.

### 2. `long_term_stable`

**Motivation from evidence**

The list had 9 winner-tail and 1 loser-tail observation, the cleanest observed
tail ratio, but limited short-horizon winner coverage.

**Case-study examples**

Relevant archetypes include stable-quality, high-dividend, and persistent
trend cases rather than event-driven right-tail moves.

**Existing data support**

Risk score, liquidity, trend, moving-average structure, volatility, and
drawdown.

**Missing data support**

Point-in-time fundamentals, dividend history, valuation, balance-sheet risk,
and historical status information.

**Guardrails**

Keep this as a stability research baseline. Do not infer long-term fundamental
quality from price-only evidence.

**Why it is not production-ready for redesign**

One observed loser does not establish a durable contamination rate, and 20D
labels do not prove long-term stability.

**Required unseen-window validation**

Use longer and multiple horizons on unseen dates, retaining downside,
drawdown, sample size, and benchmark-relative stability.

### 3. `trend_leaders`

**Motivation from evidence**

The list captured 15 winner-tail and 6 loser-tail rows. It has meaningful
capture, but positive-list losers often showed stronger prior trend,
volatility, amount expansion, and crowding characteristics.

**Case-study examples**

Trend-continuation and mature repricing cases support the winner side;
high-position crowding reversal and theme-fade cases illustrate the risk side.

**Existing data support**

Multi-horizon momentum, relative strength, moving-average alignment, amount,
volatility, drawdown, distance to highs, and crowding proxy.

**Missing data support**

Actual holder crowding, theme persistence, event validity, and industry
regime.

**Guardrails**

Keep the existing list unchanged. Study crowding as a separate attribution
layer rather than silently changing trend rank or eligibility.

**Why it is not production-ready for redesign**

The observed winner/loser separation is same-period and does not provide a
frozen crowding boundary.

**Required unseen-window validation**

Compare unchanged `trend_leaders` against a separately declared experimental
crowding annotation on unseen windows. Report retained sample size and right
tail preservation.

## B. Downgrade Or Reinterpret In Research

### 4. `breakout_watch`

**Motivation from evidence**

The list contained 14 winner-tail and 14 loser-tail rows. Earlier attribution
also found list-specific sensitivity to volatility and high-risk exclusions.

**Case-study examples**

High-volatility right-tail and theme acceleration illustrate potential upside;
theme fade, false breakout, and high-position reversal illustrate failure.

**Existing data support**

Recent momentum, relative strength, amount/volume change, volatility,
distance to highs, drawdown, acceleration, and crowding proxy.

**Missing data support**

Catalyst validity, announcement context, theme persistence, and genuine
crowding data.

**Guardrails**

Interpret as a high-variance research observation list. Do not promote its
membership to high confidence and do not apply a 2024-fitted volatility cap.

**Why it is not production-ready for redesign**

Equal winner/loser tail counts show useful reach but poor separation; no
existing proxy safely distinguishes valid from false breakouts.

**Required unseen-window validation**

Predeclare breakout-quality and false-breakout annotations, then test capture,
contamination, failure rates, drawdown, and right-tail preservation on unseen
dates.

### 5. `accumulation_watch`

**Motivation from evidence**

The list had the largest winner-tail count, 16, but also 14 loser-tail rows.
It is the closest existing list to a broad short-horizon catcher, not a clean
confidence list.

**Case-study examples**

Gradual accumulation, early repricing, low-position recovery, and event
response may enter this list; weak or fading participation may also persist.

**Existing data support**

Amount/volume change, trend, relative strength, moving-average state, list
membership, and the available controlled-date snapshots.

**Missing data support**

Durable daily list-history persistence, catalyst identity, theme persistence,
and fundamental confirmation.

**Guardrails**

Treat as staging/watchlist research only. Missing historical snapshots must
not be interpreted as non-membership or used to fabricate persistence.

**Why it is not production-ready for redesign**

High winner reach and high contamination coexist. Simple volume or amount
expansion did not explain the broad winner tail.

**Required unseen-window validation**

After a durable membership-history design is frozen, test persistence,
transition paths, retained sample size, and contamination on unseen dates.

### 6. `rebound_watch`

**Motivation from evidence**

The list had zero winner-tail and two loser-tail observations. The sample is
too small for either rejection or promotion.

**Case-study examples**

Oversold rebound and ST-risk rebound cases show that rebound outcomes can be
real, while value traps and status-risk cases show why price reversal alone is
unsafe.

**Existing data support**

Drawdown, distance to lows/highs, short/medium return reversal, volatility,
amount change, and risk membership.

**Missing data support**

Fundamental recovery, event resolution, historical ST/listing status, and
announcement confirmation.

**Guardrails**

Keep observation-only and label evidence as insufficient. Do not tune a
rebound threshold to recover the known examples.

**Why it is not production-ready for redesign**

Two loser-tail observations do not estimate the population and the relevant
winner causes are often external.

**Required unseen-window validation**

Collect a larger point-in-time sample across separate regimes before comparing
rebound archetypes or considering any candidate posture.

## C. New Research-Only Hypotheses

### 7. `low_position_revaluation_watch`

**Motivation from evidence**

Missed winners include low-position reversal, distressed restructuring,
state-owned asset revaluation, cyclical repair, and oversold recovery.
Captured winners had much stronger pre-60D trend, so early low-position cases
can remain outside established-score lists.

**Case-study examples**

`low_position_reversal`, `event_revaluation`,
`distressed_restructuring_repricing`, and
`low_position_large_cap_revaluation`.

**Existing data support**

Distance to 60D high/low, 60D drawdown, pre-20D/pre-60D return, acceleration,
relative-strength change, amount/volume change, and risk flags.

**Missing data support**

Event cause, valuation, fundamental repair, restructuring progress, and
historical status.

**Guardrails**

Watchlist-only hypothesis. Low position is not quality, and severe risk flags
must remain visible. No threshold is selected from the 2024 examples.

**Why it is not production-ready**

Price data can detect an emerging reversal but cannot distinguish revaluation
from a temporary rebound or value trap.

**Required unseen-window validation**

Freeze a continuous low-position/reversal feature definition, test it on
unseen windows, and report winner capture, failure rate, drawdown, and
high-risk overlap.

### 8. `trend_acceleration_with_crowding_guard`

**Motivation from evidence**

Captured winners favored established trend, while positive-list losers often
had even stronger prior trend, amount expansion, volatility, and crowding.
The hypothesis is a two-sided diagnostic: acceleration plus explicit reversal
risk, not simply more momentum.

**Case-study examples**

Trend continuation and semiconductor repricing illustrate acceleration;
high-position crowding reversal and theme fade illustrate the guardrail side.

**Existing data support**

Pre-5D/20D/60D return, momentum and trend scores, relative strength,
acceleration, amount change, volatility, drawdown, distance to highs, and
crowding proxy.

**Missing data support**

Holder crowding, theme persistence, event validity, and industry regime.

**Guardrails**

Research annotation only. It must not alter `trend_leaders` or
`breakout_watch`, and no combined score or cutoff is fitted here.

**Why it is not production-ready**

The same 2024 panel revealed both the acceleration and crowding patterns; it
cannot validate their combination.

**Required unseen-window validation**

Freeze feature direction and interaction form before testing. Compare against
unchanged trend and breakout baselines with sample, tail, drawdown, and
failure metrics.

### 9. `right_tail_opportunity_watch`

**Motivation from evidence**

High-volatility right-tail archetypes were common among missed winners, but the
broad winner tail did not simply have higher pre-move volatility or volume
expansion than losers.

**Case-study examples**

`high_volatility_right_tail`, speculative momentum, rapid technology
repricing, and event-driven surges.

**Existing data support**

Upside-return concentration, technical volatility, range/close behavior,
acceleration, amount/volume change, drawdown, and relative strength.

**Missing data support**

Catalyst confirmation, news/event identity, theme persistence, and
fundamental context.

**Guardrails**

Watchlist-only, explicitly high variance, with downside and sample-size
warnings. It must not be merged into stable or high-confidence lists.

**Why it is not production-ready**

The available proxies cannot safely separate asymmetric opportunity from
speculative noise before the event.

**Required unseen-window validation**

Predeclare right-tail and failure metrics, then test payoff ratio, extreme
loss, drawdown, sample sufficiency, and right-tail preservation on unseen
windows.

### 10. `high_position_crowding_risk`

**Motivation from evidence**

Positive-list losers were more crowded, more volatile, and had stronger prior
trend/amount expansion than positive-list winners.

**Case-study examples**

`high_position_crowding_reversal` and mature theme-fade losers.

**Existing data support**

Distance to rolling high, moving-average distance, pre-20D/60D return,
volatility, amount/volume change, recent drawdown, and crowding proxy.

**Missing data support**

Holder concentration, turnover structure, leverage, theme persistence, and
fund flows.

**Guardrails**

Risk-warning-only hypothesis. It must not become a negative recommendation or
an automatic exclusion from production lists.

**Why it is not production-ready**

Current crowding is a price-only proxy and may flag legitimate trend
consolidation.

**Required unseen-window validation**

Freeze a risk annotation and test whether it reduces loser-tail incidence
without destroying winner-tail capture on unseen dates.

### 11. `false_breakout_risk`

**Motivation from evidence**

`breakout_watch` had equal winner and loser tail counts. Positive-list losers
showed stronger pre-trend and amount expansion but worse volatility, drawdown,
and crowding context.

**Case-study examples**

Theme-fade, speculative breakout failure, and high-position reversal.

**Existing data support**

Failed-high behavior available by the as-of date, close location, distance to
high, acceleration decay, volatility, drawdown, amount change, and relative
strength.

**Missing data support**

Catalyst persistence, announcement validity, theme data, and actual crowding.

**Guardrails**

Risk-warning-only and retrospective-safe: a breakout may be called failed only
from evidence already visible by the as-of date, never from its future decline.

**Why it is not production-ready**

No frozen point-in-time failure definition has been tested outside the same
2024 panel.

**Required unseen-window validation**

Freeze the failure-state transition, test it prospectively on unseen dates,
and report both avoided losses and winners incorrectly warned.

### 12. `theme_event_gap_watch`

**Motivation from evidence**

Theme/policy and event-revaluation archetypes are concentrated among missed
winners, while existing price-only lists cannot identify the cause.

**Case-study examples**

`theme_policy_catalyst`, `event_revaluation`, industry partnership,
restructuring repricing, and regional policy repricing.

**Existing data support**

Only the market reaction: return, acceleration, relative strength, amount,
volume, volatility, and list transitions.

**Missing data support**

Point-in-time news, announcements, policy, concept/theme mapping, event
lifecycle, and source provenance.

**Guardrails**

External-data-required gap marker only. Do not synthesize a theme/event label
from price movement and do not create this list before point-in-time data
exists.

**Why it is not production-ready**

The defining causal variables are absent.

**Required unseen-window validation**

First build versioned, point-in-time external inputs. Freeze event taxonomy and
availability rules before testing on outcomes not used for taxonomy design.

### 13. `negative_event_or_status_risk`

**Motivation from evidence**

Loser archetypes include negative events, fundamental weakness, transaction
uncertainty, delisting risk, and theme fade. Current status metadata is not
fully historical point-in-time.

**Case-study examples**

`negative_event_loser`, `delisting_risk_loser`,
`cross_border_acquisition_uncertainty`, and
`fundamental_weakness_loser`.

**Existing data support**

Current risk labels, price deterioration, drawdown, volatility, liquidity,
and existing `high_risk_active` membership.

**Missing data support**

Historical ST/listing/suspension status, announcements, transaction lifecycle,
fundamentals, and event severity.

**Guardrails**

Risk-warning-only and external-data-required. Preserve
`current_snapshot_limited` bias flags and never backfill historical status from
a current snapshot.

**Why it is not production-ready**

Historical status and event timing are incomplete, creating survivorship and
lookback risk.

**Required unseen-window validation**

After point-in-time status/event history exists, validate warning coverage,
false-warning rate, severe-loss capture, and data availability on unseen
windows.

## Hypothesis Classification

### Existing-data hypotheses

- `low_position_revaluation_watch`
- `trend_acceleration_with_crowding_guard`
- `right_tail_opportunity_watch`
- `high_position_crowding_risk`
- `false_breakout_risk`

These may be prototyped later as read-only annotations using the Phase 2.14
snapshot schema. No threshold or list membership is defined in Phase 2.17.

### External-data-required hypotheses

- `theme_event_gap_watch`
- `negative_event_or_status_risk`

They must remain gap markers until point-in-time external data and provenance
exist.

### Risk-warning-only hypotheses

- unchanged `high_risk_active`
- `high_position_crowding_risk`
- `false_breakout_risk`
- `negative_event_or_status_risk`

Risk warnings must not be presented as action instructions.

### Watchlist-only hypotheses

- reinterpreted `breakout_watch`
- reinterpreted `accumulation_watch`
- observation-only `rebound_watch`
- `low_position_revaluation_watch`
- `right_tail_opportunity_watch`
- `theme_event_gap_watch`

### Possible future production consideration after validation

No hypothesis is currently approved for production. After separate unseen
validation, the following could be considered for a later decision:

- keeping `high_confidence_candidates`, `long_term_stable`, and
  `trend_leaders` as unchanged baselines
- evaluating a frozen low-position observation alongside, not inside, stable
  lists
- evaluating a frozen crowding/false-breakout warning as an annotation

Passing one unseen window would still be insufficient for production.

## Required Unseen-Window Test Contract

Before implementation, each hypothesis must have a versioned experiment card:

1. Freeze feature names, formulas, direction, missing-data behavior, and
   membership semantics.
2. Record that the 2024 four-window panel and 30-case answer key are development
   evidence only.
3. Select separate unseen as-of dates without inspecting their labels.
4. Materialize point-in-time features before joining future labels.
5. Compare against unchanged production-list baselines.
6. Report sample count and coverage before performance.
7. Report winner-tail capture, loser-tail contamination, average/median excess
   return, benchmark outperform rate, drawdown, and severe-failure rates.
8. For right-tail hypotheses, report payoff ratio and right-tail preservation.
9. For risk warnings, report both warned losers and incorrectly warned winners.
10. Report results by window and regime; do not rely only on pooled averages.
11. Preserve Phase 2.10/2.10.1 leakage and bias metadata.
12. Reject or retain hypotheses without changing production logic during the
    experiment.

## Anti-Overfitting Guardrails

- 2024 results are answer-key / in-sample evidence.
- These hypotheses cannot be validated on the same 2024 windows used to derive
  them.
- The next proof must use separate unseen windows.
- No threshold tuning should be performed against the 2024 winners.
- Do not hard-code known winner symbols, archetypes, list combinations, or
  outcomes.
- Do not use the 30 selected cases to estimate population hit rates.
- External causal labels must not be reverse-engineered from future price
  outcomes.
- No claim of production improvement is allowed in Phase 2.17.

## Decision

Phase 2.17 authorizes documentation and future experiment design only. The
existing production scoring, ranking, candidate selection, list construction,
thresholds, and recommendation behavior remain unchanged.
