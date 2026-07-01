# Phase 2.35 Research-Only Opportunity Cohort Specification

## Purpose

Phase 2.35 freezes the proposed research contract for five opportunity and
risk cohorts before implementation or validation:

- H1 `low_position_revaluation_watch`
- H2 `trend_acceleration_with_crowding_guard`
- H3 `right_tail_opportunity_watch`
- H4 `high_position_crowding_risk`
- H5 `false_breakout_risk`

This is an explanation and reference specification for a future builder. It
does not implement membership, select symbols, write cohort outputs, or change
any existing list.

H1-H5 remain `blocked_until_frozen_cohort` until a later implementation
commits exact point-in-time formulas, parameter names, missing-data behavior,
and output versions before any new holdout outcome is opened.

## Research Boundary

H1-H5 are a separate research layer beside the unchanged existing lists and
the Phase 2.34 tiering view. They are not replacements for:

- `high_confidence_candidates`
- `trend_leaders`
- `long_term_stable`
- `breakout_watch`
- `accumulation_watch`
- `rebound_watch`
- `high_risk_active`

No H1-H5 cohort may feed production scoring, ranking, candidate selection,
list membership, daily recommendations, or portfolio construction.

The 2024 answer-key cases, Phase 2.15/2.16 attribution, U1, and U2 explain why
these hypotheses exist. They cannot validate an implementation derived from
them. U1 and U2 are consumed evidence.

## Cohort Roles

| ID | Research name | Role | Permitted interpretation |
|---|---|---|---|
| H1 | `low_position_revaluation_watch` | Opportunity observation | Low-position recovery structure visible from as-of price and activity data |
| H2 | `trend_acceleration_with_crowding_guard` | Opportunity observation plus warning | Improving acceleration with a separate crowding caution |
| H3 | `right_tail_opportunity_watch` | High-variance opportunity observation | Pre-as-of technical structure that may support asymmetric outcomes |
| H4 | `high_position_crowding_risk` | Risk warning | High-position and overheated price/participation structure |
| H5 | `false_breakout_risk` | Risk explanation | Breakout or accumulation membership with as-of technical failure risk |

H1-H3 must remain observation cohorts. H4-H5 must remain warning annotations.
None is an action instruction.

## Allowed Input Contract

The first implementation may consume only fields that exist at or before
`as_of_date`.

### Identity and point-in-time diagnostics

- `as_of_date`
- `symbol`
- `data_quality`
- `latest_input_date`
- `max_raw_cache_date`
- `future_rows_excluded_count`
- `leakage_guard_applied`
- `missing_feature_flags`

### Phase 2.14 technical fields

- `pre_5d_return`
- `pre_20d_return`
- `pre_60d_return`
- `technical_volatility_20d`
- existing `volatility_20d` when already present
- `drawdown_60d`
- `amount_change_20d`
- `volume_change_20d`
- `distance_to_60d_high`
- `distance_to_60d_low`
- `recent_acceleration_proxy`
- `high_position_crowding_proxy`

### Existing factors and scores

Existing momentum, trend, relative-strength, risk, liquidity, drawdown,
amount, and volume fields may be copied without recalculation or reweighting.
Existing scores may be used as descriptive inputs or baseline context only.

### Existing list context

- high-confidence membership
- trend-leader membership
- long-term-stable membership
- breakout membership
- accumulation membership
- rebound membership
- high-risk-active membership
- captured positive and risk-list IDs
- membership source-file date
- `membership_history_available`

A missing list file is missing data. It is not negative membership.

### Same-date cross-sectional ranks

A later builder may calculate continuous ranks or quantiles using only the
eligible universe materialized for the same `as_of_date`. It must record the
universe definition, valid count, tie handling, missing-value policy, and
parameter version.

No rank boundary is selected in Phase 2.35.

## Forbidden Input Contract

The cohort builder must never read or derive membership from:

- `future_return`
- `benchmark_return`
- `future_excess_return`
- `outperformed_benchmark`
- `future_top_quantile`
- `max_drawdown_during_holding`
- future highs, lows, closes, amount, volume, or volatility
- realized winner or loser labels
- known case-study outcomes or manually researched archetypes
- symbols selected because they were known winners or losers
- U1 or U2 performance results
- later list snapshots or reconstructed future membership
- theme, concept, policy, news, or announcement information
- restructuring, control-change, or transaction information
- fundamentals, valuation, industry, or sector attribution
- historical listing, ST, suspension, or event status that is not available
  as a versioned point-in-time input
- current status snapshots backfilled into historical dates

Price and volume behavior may describe a market response. It must not be
relabeled as a catalyst, theme, restructuring, fundamental change, or
historical status event.

## Point-In-Time And Snapshot Contract

A future cohort builder must operate on one row per
`(as_of_date, symbol)` from a frozen member-level snapshot.

Every eligible row must satisfy:

```text
latest_input_date <= as_of_date
leakage_guard_applied = true
```

The builder must also record:

- snapshot schema version;
- cohort definition version;
- source file paths and dates;
- minimum-history status for each feature family;
- raw-cache maximum date;
- excluded future-row count;
- list-membership availability;
- current-snapshot universe/status limitations.

The raw cache may extend beyond the as-of date. All feature calculations must
end at the latest completed trading date on or before `as_of_date`.

Cross-sectional ranks must use only the same as-of snapshot. Lagged values or
prior memberships may be used only when their source snapshot date is on or
before the current as-of date.

## Parameter Freeze Policy

Phase 2.35 sets no numeric threshold.

Any threshold-like boundary needed by a future builder must use a named
parameter and be preregistered before holdout outcomes are opened. Examples:

- `low_position_rank_parameter`
- `recovery_confirmation_rank_parameter`
- `activity_confirmation_rank_parameter`
- `acceleration_rank_parameter`
- `crowding_warning_rank_parameter`
- `volatility_context_rank_parameter`
- `failure_risk_rank_parameter`
- `minimum_history_parameter`
- `minimum_cohort_sample_parameter`

The future implementation plan must freeze:

- parameter direction;
- rank or quantile reference universe;
- inclusive/exclusive behavior;
- tie handling;
- missing-data behavior;
- interaction logic;
- minimum sample gate;
- success and failure interpretation.

Placeholder names in this document are not final values and must not be fitted
to the 2024 answer key, U1, or U2.

## Common Research Output Contract

A later implementation must write separate research outputs, never production
list files.

### Cohort metadata

- `cohort_id`
- `cohort_version`
- `cohort_role`
- `research_only = true`
- `as_of_date`
- `snapshot_version`
- `parameter_version`
- `status`
- `provider_access = false`
- `leakage_guard_applied`
- known bias limitations

### Member fields

- `symbol`
- `included`
- `data_quality`
- `latest_input_date`
- raw allowed feature values
- same-date feature ranks when configured
- existing list memberships
- `evidence_fields`
- `counter_evidence_fields`
- `risk_flags`
- `missing_required_fields`
- `membership_reason`
- `research_caveat`

The builder output must not contain future labels. A later evaluator may join
frozen membership to labels by `(as_of_date, symbol)` after the cohort file is
written and sealed.

### Summary fields

- source universe count
- eligible input count
- cohort member count
- missing and blocked counts
- feature coverage by field
- list-overlap counts
- high-risk overlap
- point-in-time diagnostic summary
- unresolved data limitations

No output may contain a new production score, target return, position size, or
action instruction.

## Common Fail-Closed Behavior

The future builder must not silently impute, infer, or broaden membership.

| Condition | Required behavior |
|---|---|
| Required feature column missing | `blocked_missing_required_feature` |
| Required feature value missing for one symbol | Exclude that symbol from membership and record the field |
| `latest_input_date > as_of_date` | `blocked_point_in_time_violation` |
| Leakage metadata absent or false | `blocked_unverified_leakage_guard` |
| Required list file missing | `blocked_missing_membership_source` for list-dependent cohorts |
| Membership history unavailable | Disable history-dependent logic; do not treat as no prior membership |
| Parameter/config missing | `blocked_missing_frozen_parameter` |
| Snapshot or definition version missing | `blocked_unversioned_input` |
| Eligible sample below frozen gate | `insufficient_sample` |

Fail-closed output may explain the blocker. It must not substitute a looser
cohort or fall back to production list logic.

## H1 Low-Position Revaluation Watch

### Purpose

Identify price structures that remain low relative to their trailing context
but show an as-of recovery and participation improvement. This observes a
possible revaluation response; it does not identify the cause of revaluation.

### Allowed inputs

- `distance_to_60d_high`
- `distance_to_60d_low`
- `drawdown_60d`
- `pre_5d_return`, `pre_20d_return`, `pre_60d_return`
- `recent_acceleration_proxy`
- `amount_change_20d`, `volume_change_20d`
- existing relative-strength, trend, risk, and liquidity context
- existing rebound or accumulation membership as context

### Proposed high-level definition

Membership requires all three concepts:

1. low-position or material prior-drawdown context;
2. recovery or acceleration visible by the as-of date;
3. improving activity or relative-strength confirmation.

The exact interaction and rank boundaries remain future frozen parameters.
Low position alone is never sufficient.

### Forbidden inputs

Future rebound magnitude, eventual low/high, known turnaround outcome,
restructuring cause, fundamental repair, valuation, or historical status data
that is not point-in-time available.

### Member-level requirements and fail-closed rules

Price-position, drawdown, recovery, and activity fields are required. Missing
any required family blocks membership for that symbol. A short history cannot
be filled from later bars.

### UI/report evidence

- low-position and drawdown context;
- recovery and acceleration context;
- amount/volume confirmation;
- relative-strength and existing-list context;
- high-risk overlap;
- missing external explanation.

### Risk caveat

Low position is not quality. The structure may represent a temporary rebound,
value trap, status risk, or unresolved fundamental weakness.

### Future holdout validation

Report by window:

- sample and feature coverage;
- winner-tail capture and loser-tail contamination;
- average and median excess return;
- benchmark outperform rate;
- holding-period drawdown and severe-failure rate;
- high-risk overlap;
- comparison with unchanged rebound, accumulation, and core research lists.

The holdout must test a frozen cohort generated before labels are opened.

## H2 Trend Acceleration With Crowding Guard

### Purpose

Identify improving trend acceleration while retaining a separate warning for
high-position or crowded structures. This is a two-sided annotation, not a
stronger momentum score.

### Allowed inputs

- `pre_5d_return`, `pre_20d_return`, `pre_60d_return`
- `recent_acceleration_proxy`
- existing momentum, trend, and relative-strength fields
- `amount_change_20d`, `volume_change_20d`
- `technical_volatility_20d`
- `distance_to_60d_high`
- `drawdown_60d`
- `high_position_crowding_proxy`
- trend, breakout, accumulation, and high-risk memberships

### Proposed high-level definition

The opportunity annotation requires improving acceleration plus trend or
relative-strength support. A separate `crowding_warning` is attached when
high-position, volatility, participation, and prior-trend context indicate
possible overheating.

The crowding warning must not automatically remove or promote a member. The
future output should distinguish:

- acceleration observed without a crowding warning;
- acceleration observed with a crowding warning;
- insufficient evidence.

### Forbidden inputs

Future trend continuation, later reversal, known crowding outcomes, holder
concentration, future fund flow, theme persistence, or later list membership.

### Member-level requirements and fail-closed rules

Acceleration and trend context are required for opportunity membership.
Crowding fields are required before the output may claim the guard was
evaluated. If crowding data is missing, report
`crowding_guard_unavailable`; do not treat the member as uncrowded.

### UI/report evidence

- acceleration and trend evidence;
- activity confirmation;
- position, volatility, and crowding warning evidence;
- unchanged source-list memberships;
- whether the guard was available;
- explicit counter-evidence.

### Risk caveat

Strong prior trend can be mature rather than early. Price-only crowding may
also flag legitimate consolidation, so the warning is not a conclusion.

### Future holdout validation

Compare frozen acceleration members with and without the warning:

- sample and coverage;
- excess return and outperform rate;
- winner-tail retention;
- loser-tail and severe-loss incidence;
- right-tail preservation;
- drawdown;
- members incorrectly warned;
- unchanged `trend_leaders` and `breakout_watch` baselines.

## H3 Right-Tail Opportunity Watch

### Purpose

Identify pre-as-of high-variance technical structures that may support
asymmetric outcomes. The cohort observes opportunity and risk together; it
does not label a future right-tail result.

### Allowed inputs

- `technical_volatility_20d` and existing volatility context
- `pre_5d_return`, `pre_20d_return`, `pre_60d_return`
- `recent_acceleration_proxy`
- `amount_change_20d`, `volume_change_20d`
- `drawdown_60d`
- distance to the trailing high and low
- existing momentum and relative-strength context
- breakout, accumulation, rebound, and high-risk memberships
- other pre-as-of upside/downside concentration fields only after they are
  separately defined from completed bars

### Proposed high-level definition

Membership requires elevated variance context plus evidence of positive
acceleration or participation. The output must retain drawdown, high-risk
overlap, and counter-evidence.

Volatility alone is never sufficient. The name describes the research
hypothesis, not a known future outcome.

### Forbidden inputs

Future top-quantile status, future maximum return, future high, realized
payoff ratio, known winner status, event or theme cause, or cutoffs selected
from known right-tail cases.

### Member-level requirements and fail-closed rules

Volatility, acceleration/participation, and downside context are required. If
the pre-as-of asymmetry feature family is not implemented, the output must say
`right_tail_structure_proxy_limited` rather than infer it from later returns.

### UI/report evidence

- volatility context;
- acceleration and activity evidence;
- price-position and drawdown context;
- existing opportunity-list overlaps;
- high-risk overlap;
- sample-size and proxy limitations.

### Risk caveat

The same structure may produce speculative spikes, false breakouts, unstable
small samples, and severe drawdowns. This cohort remains observation-only.

### Future holdout validation

Predeclare and report:

- cohort size and coverage;
- average/median excess return and outperform rate;
- payoff ratio;
- right-tail preservation;
- extreme positive and negative tails;
- failure rates below frozen loss boundaries;
- drawdown;
- high-risk overlap;
- stability across windows and regimes.

No favorable pooled mean may override a severe contrary window or inadequate
sample.

## H4 High-Position Crowding Risk

### Purpose

Identify high-position, stretched, volatile, or overheated technical
structures for risk explanation. It is a warning annotation only.

### Allowed inputs

- `distance_to_60d_high`
- `pre_20d_return`, `pre_60d_return`
- `high_position_crowding_proxy`
- `technical_volatility_20d`
- `amount_change_20d`, `volume_change_20d`
- `drawdown_60d`
- existing momentum/trend context
- trend, breakout, accumulation, and high-risk memberships

### Proposed high-level definition

The warning requires high-position context plus a preregistered combination of
crowding, participation, volatility, or stretched-trend evidence.

The output records warning strength components separately. It does not remove
the symbol from any source list.

### Forbidden inputs

Future reversal, future drawdown, later failed-high status, actual holder
concentration, leverage, future fund flow, theme fade, or known loser status.

### Member-level requirements and fail-closed rules

Position and crowding context are required. If either is unavailable, the
warning is `not_evaluated_missing_context`, not false.

### UI/report evidence

- position relative to the trailing range;
- crowding proxy;
- prior trend and participation;
- volatility and current drawdown;
- source-list memberships;
- reasons the warning may be a false positive.

### Risk caveat

Price-only crowding is not actual holder crowding. Legitimate strong trends
and consolidations may be warned incorrectly.

### Future holdout validation

Evaluate:

- warning coverage and sample size;
- loser-tail and severe-loss capture;
- average drawdown of warned versus disjoint unwarned cohorts;
- winner-tail members incorrectly warned;
- right-tail preservation;
- stability by window;
- overlap with existing high-risk and active lists.

The evaluator must report both avoided downside hypotheses and opportunity
cost.

## H5 False-Breakout Risk

### Purpose

Explain possible pollution inside existing `breakout_watch` and
`accumulation_watch` using only technical evidence already visible by the
as-of date.

### Allowed inputs

- breakout and accumulation membership at the same as-of date
- `distance_to_60d_high`
- `pre_5d_return`, `pre_20d_return`, `pre_60d_return`
- `recent_acceleration_proxy`
- `technical_volatility_20d`
- `drawdown_60d`
- `amount_change_20d`, `volume_change_20d`
- `high_position_crowding_proxy`
- existing trend and relative-strength context
- failed-high or close-location fields only when computed solely from bars
  completed by the as-of date

### Proposed high-level definition

The evaluation domain is the union of the unchanged breakout and accumulation
source memberships, with overlaps preserved.

A warning requires preregistered evidence of an as-of technical mismatch,
such as high position with deceleration, activity without sustained price
confirmation, or a failed high already observable by the as-of date.

The warning explains risk. It does not change either source list.

### Forbidden inputs

Future decline, future maximum drawdown, eventual breakout failure, later
membership transitions, theme fade, catalyst validity, or known loser status.

### Member-level requirements and fail-closed rules

Same-date source membership and the selected mismatch feature families are
required. Missing breakout or accumulation files block the cohort. Missing
activity or price-position context produces `risk_not_evaluated`, not a clean
result.

### UI/report evidence

- source list and original rank;
- price-position and acceleration evidence;
- activity confirmation or mismatch;
- volatility, drawdown, and crowding context;
- risk explanation;
- false-warning limitation.

### Risk caveat

A pause, consolidation, or volatile retest can later continue successfully.
The warning must not be treated as a removal instruction.

### Future holdout validation

Report:

- eligible source-list sample and warning coverage;
- loser-tail and severe-loss capture;
- positive-list contamination before and after annotation;
- winner-tail members incorrectly warned;
- retained right tail;
- drawdown and excess return for warned and unwarned disjoint cohorts;
- results separately for breakout and accumulation members;
- cross-window sign and sample stability.

## Expected UI And Report Structure

A future research report should show:

1. cohort identity, version, role, and as-of date;
2. PIT and data-quality status before membership counts;
3. source universe, eligible count, included count, and blocked count;
4. raw evidence and counter-evidence;
5. existing list overlaps without changing those lists;
6. missing feature and external-data limitations;
7. risk caveat at the same visual level as opportunity evidence;
8. `Research-only` and `Not investment advice` labels.

H1-H3 should appear under an opportunity-research section. H4-H5 should
appear under a risk-annotation section. They must not be inserted into the
five production-adjacent list tiers as if they were validated lists.

## Forbidden Wording

Future cohort outputs, reports, and UI must not say or imply:

- `guaranteed gain`
- `stable profit`
- `must buy`
- `safe stock`
- `validated alpha`
- `production recommendation`
- `risk-free`
- `automatic exclusion`
- `confirmed avoid signal`
- `confirmed short signal`

H1-H3 are not return promises. H4-H5 are not action or exclusion signals.

## Future Holdout Contract

Before implementation results are opened:

1. commit the builder and cohort-definition version;
2. freeze every allowed field, transformation, interaction, and parameter;
3. freeze missing-data and fail-closed behavior;
4. freeze exact holdout dates, horizons, benchmark, universe, and minimum
   samples;
5. materialize and seal cohort membership without future labels;
6. verify PIT diagnostics and current-snapshot bias flags;
7. join future labels only in a separate evaluator;
8. report every window, including contradictory and empty windows;
9. preserve source baselines and disjoint comparisons;
10. prohibit threshold edits after outcomes open.

U1, U2, the 2024 answer key, and attribution panels cannot serve as the new
holdout.

## Production Eligibility Requirements

No H1-H5 cohort is currently production eligible.

Any later production consideration requires:

- an implemented, versioned, fail-closed research builder;
- complete point-in-time diagnostics;
- an unopened preregistered holdout with adequate samples and multiple
  regimes;
- stable per-window evidence rather than one favorable pooled average;
- explicit downside, right-tail, false-warning, and opportunity-cost analysis;
- comparison against unchanged source lists;
- historical universe/status limitations disclosed or repaired;
- turnover and cost analysis where portfolio interpretation is proposed;
- a new holdout after any post-result formula or parameter revision;
- a separate production proposal, regression tests, rollback plan, and manual
  approval.

H1-H3 must first remain research observation outputs. H4-H5 must first remain
non-blocking warning annotations. Passing one holdout does not automatically
authorize list, rank, score, threshold, or recommendation changes.

## Future Implementation Boundary

H1-H5 may be implemented only in a later phase. The first implementation must:

- be research-only;
- read a frozen member-level as-of snapshot;
- make no provider request;
- write separate files under a research/experiment output namespace;
- avoid existing production list filenames;
- leave existing list generation and ranking unchanged;
- leave daily recommendation behavior unchanged;
- emit no portfolio recommendation;
- keep labels out of builder inputs;
- fail closed on missing metadata, features, or PIT verification.

## Recommended Next Phase

The recommended next phase is:

`Phase 2.36 Frozen Cohort Builder Readiness Check`

That phase should verify field availability, missingness, snapshot coverage,
parameter placeholders, and output schema without implementing membership or
opening holdout outcomes.

If readiness is already demonstrably complete, a separately approved
`Phase 2.36 Research-Only Opportunity Cohort Implementation Plan` may define
the builder architecture. It still must not evaluate outcomes.

## Explicit Non-Goals

Phase 2.35 does not:

- implement H1-H5;
- choose numeric thresholds;
- generate cohort members or outputs;
- run validation or inspect a new outcome;
- change existing lists, scores, ranks, factors, or labels;
- create production or portfolio recommendations;
- access a provider;
- modify generated outputs.

## Phase Decision

H1-H5 now have a common research boundary and high-level cohort specification.
They remain blocked until a later phase freezes implementable formulas,
parameters, missing-data behavior, and a new holdout contract.

No production scoring, ranking, factor formulas, validation math, candidate
selection, list membership, thresholds, recommendation logic, or portfolio
behavior is authorized or changed by Phase 2.35.
