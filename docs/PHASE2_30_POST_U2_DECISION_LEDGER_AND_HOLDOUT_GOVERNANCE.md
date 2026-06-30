# Phase 2.30 Post-U2 Decision Ledger And Holdout Governance

## Purpose

Phase 2.30 converts the completed U1 and U2 evidence into explicit research
decisions and future holdout rules. It is a governance record, not a model
change, validation run, or production launch.

The intended reader is the operator planning later research phases. The ledger
answers three questions for every list, factor, or hypothesis:

1. What did U1 and U2 actually establish?
2. What is its permitted research status now?
3. What new proof is required before any production consideration?

## Evidence Boundary

Consumed U1 windows:

```text
2024-02-29 20D
2024-05-31 20D
2024-08-30 20D
2024-11-29 20D
```

Consumed U2 windows:

```text
2025-02-28 20D
2025-05-30 20D
2025-08-29 20D
2025-11-28 20D
```

Permanently forbidden answer-key windows:

```text
2024-01-31 20D
2024-04-30 20D
2024-07-31 20D
2024-10-31 20D
```

U1 and U2 may explain the decisions below. They cannot validate a threshold,
formula, cohort, or hypothesis revised after either panel was opened.

## Decision Status Vocabulary

- `eligible_for_research_design`: evidence supports a new research design
  phase, but not implementation or production behavior.
- `research_only`: may remain in descriptive research; no stable production
  claim is established.
- `defensive_positioning_only`: may be designed as a defensive framing or
  monitoring view, not as a return-seeking promotion.
- `observation_only`: may remain visible for monitoring and evidence
  collection; it is not a stable positive or negative signal.
- `not_confirmed`: the preregistered interpretation failed, was contradicted,
  or did not meet its sample/direction gate.
- `untestable_without_external_data`: required historical point-in-time inputs
  do not exist.
- `blocked_until_frozen_cohort`: no future test is valid until a versioned,
  point-in-time-safe member-level cohort is committed before outcomes open.

None of these statuses authorizes a production change.

## Post-U2 Decision Ledger

| Item | U1 evidence | U2 evidence | Decision status | Production change allowed now | Required next proof before production consideration |
|---|---|---|---|---|---|
| `high_confidence_candidates` | Coverage and cleanliness were unstable; only 2/4 positive-excess windows | Coverage improved to 10-16 members, but excess was positive in only 2/4 windows and the mean was November-driven | `research_only` | No | Freeze a specific cleanliness-and-coverage claim, then confirm it on a new preregistered holdout with stable membership, excess sign, outperform rate, and drawdown |
| `long_term_stable` | Lowest full-list drawdown and positive excess in 3/4 windows, but mean excess remained negative | Shallower drawdown than three active lists in 4/4 windows; excess negative in 3/4 | `defensive_positioning_only` | No | Separate defensive monitoring from return seeking, freeze the presentation/measurement contract, then confirm drawdown behavior on a later unopened holdout and review turnover/status bias |
| `trend_leaders` | Positive excess in 1/4 windows; regime and crowding sensitivity remained plausible | Positive excess in 2/4, negative median window excess, and only one window above 50% outperform | `not_confirmed` | No | A new versioned hypothesis must define what stable trend leadership means and pass a new holdout; crowding attribution requires a frozen member-level cohort |
| `breakout_watch` | Alternating outcomes and elevated downside supported high variance | Alternating signs, 43.3% mean outperform, and elevated drawdown; top-10 right tail did not remove downside | `observation_only` | No | Preserve winner and failure tails under a frozen observation contract, then test on a new holdout without promoting from favorable pooled means |
| `accumulation_watch` | Mostly negative and high-drawdown observation behavior | Positive excess in 3/4 windows but weak outperform, negative mean, and a large contrary window | `observation_only` | No | Freeze persistence and contamination definitions before a new holdout; require stable coverage, downside, and transition behavior rather than return sign alone |
| `rebound_watch` | No positive-excess window and limited evidence | One positive window drove a positive mean; median window remained negative | `observation_only` | No | Accumulate adequate samples under a frozen rebound definition and confirm across a later holdout without changing thresholds after inspection |
| `high_risk_active` | Negative excess in every non-empty window, but only 20 member-window observations | Two negative and two positive windows; 28 observations, below the preregistered minimum of 30 | `not_confirmed` | No | A new preregistered holdout must meet the unchanged sample gate and show at least three negative windows plus worse disjoint downside; U1/U2 cannot be pooled to rescue R0 |
| `total_score` | Correlation and spread were negative in 3/4 windows | Correlation and spread again negative in 3/4 windows | `not_confirmed` | No | Do not reweight. Any future score hypothesis needs a separately versioned formula and a later holdout showing repeated positive correlation/spread without a severe contrary window |
| `low_position_revaluation_watch` | In-sample attribution suggested a possible missed-winner gap; no frozen unseen cohort | Not evaluated because no frozen member-level cohort existed before U2 | `blocked_until_frozen_cohort` | No | Commit point-in-time feature formulas, missing-data rules, membership logic, sample gates, and output version before selecting a new holdout |
| `trend_acceleration_with_crowding_guard` | Trend acceleration and crowding were diagnostic hypotheses only | Not evaluated; unchanged list results cannot substitute for the missing cohort | `blocked_until_frozen_cohort` | No | Freeze retained/warned cohorts and right-tail preservation rules, then test on a new holdout with warned winners and losers both reported |
| `right_tail_opportunity_watch` | Right-tail behavior was descriptive and explicitly observation-only | Not evaluated because no frozen U2 cohort existed | `blocked_until_frozen_cohort` | No | Freeze point-in-time entry features, severe-loss rules, minimum sample, and payoff/right-tail metrics before a later holdout; it cannot be labeled high confidence |
| `high_position_crowding_risk` | Same-period attribution suggested warning value but was not blind validation | Not evaluated because no frozen warning cohort existed | `blocked_until_frozen_cohort` | No | Version the warning definition and disjoint comparison before a new holdout; report incorrectly warned winners and severe-loss capture |
| `false_breakout_risk` | Proposed to explain breakout/accumulation pollution; no prospective frozen transition | Not evaluated before U2 opened | `blocked_until_frozen_cohort` | No | Freeze failure-state transitions, source-list membership, retained winner tail, and sample gates before a later holdout |
| `theme_event_gap_watch` | Case studies showed theme/event gaps, but the full snapshot lacked causal inputs | U2 could not test absent historical theme/event data | `untestable_without_external_data` | No | Obtain timestamped point-in-time theme/event data with provenance, freeze taxonomy and availability rules, then preregister a later holdout |
| `negative_event_or_status_risk` | Historical listing/ST/suspension/event status was current-snapshot limited | U2 retained the same data limitation | `untestable_without_external_data` | No | Build versioned historical event/status inputs, verify PIT availability, freeze the warning definition, and use a later holdout |

## Ledger Decisions

### Defensive positioning only

`long_term_stable` is the only item that may advance to a narrowly scoped
research design phase. The supported claim is drawdown behavior relative to
the active observation lists. The unsupported claim is stable excess return.

A future design must therefore use language such as defensive context,
stability monitoring, or lower observed drawdown. It must not present
`long_term_stable` as a return-seeking promotion or infer fundamental quality
from a 20D price label.

### Research and observation only

`high_confidence_candidates` remains a selective research baseline, but U1/U2
do not establish stable cleanliness and coverage together.

`breakout_watch`, `accumulation_watch`, and `rebound_watch` remain observation
lists. Their right tails or occasional favorable windows do not erase weak
outperform consistency, drawdown, contamination concerns, or sample
concentration.

### Not confirmed

`trend_leaders` must not be treated as a stable positive baseline.

`high_risk_active` cannot be promoted as a confirmed stable negative bucket.
U2 missed both its sample gate and sign-consistency gate. The deeper drawdown
remains a research observation, not confirmation.

`total_score` must not be reweighted from U1/U2 evidence. Two separate panels
both produced negative correlation and spread in three of four windows.

### Blocked or untestable

H1-H5 require frozen member-level cohorts before any new outcome is opened.
They cannot be retrofitted to consumed U1/U2 dates.

H6-H7 require historical external theme, event, listing, ST, suspension, or
status data with point-in-time timestamps and provenance. Price paths cannot
be used to manufacture those causal labels.

## Holdout Governance

### 1. Consumed evidence stays consumed

- U1 and U2 cannot be reused as sealed confirmation.
- Answer-key windows remain permanently development-only.
- U1 and U2 may be shown side by side for consistency, but pooling them does
  not create a new unseen test.
- Any output already opened for evaluation is consumed even if the result was
  inconvenient, mixed, or underpowered.

### 2. Every changed hypothesis receives a new version

A change to any of the following creates a new hypothesis version:

- feature formula or direction;
- score or factor weight;
- threshold or quantile;
- list membership rule;
- missing-data treatment;
- sample gate;
- success/failure interpretation;
- source data, taxonomy, or point-in-time availability rule.

The new version requires a new preregistered holdout. It cannot claim U2
confirmation.

### 3. Holdouts are selected before outcomes

Before generating or opening a future holdout:

1. commit the hypothesis version and decision question;
2. commit exact dates, horizons, universe limit, benchmark, and sample gates;
3. verify cache/as-of readiness without reading outcomes;
4. record forbidden and consumed windows;
5. freeze output names so earlier evidence cannot be overwritten;
6. record stop and replacement rules;
7. open results once and preserve contradictory windows.

A failed readiness check is an infrastructure blocker. A replacement date must
be preregistered before any result is inspected and must not be chosen for
expected performance.

### 4. Design, validation, and production remain separate

- A research design phase defines wording, cohorts, metrics, and UX/report
  presentation without changing production behavior.
- A validation phase evaluates the frozen design on an unopened holdout without
  editing it in place.
- A production phase, if later authorized, implements one approved change with
  tests, rollback, evidence labels, and a separate merge decision.

Passing a holdout does not automatically authorize production.

### 5. Mixed and failed results remain recorded

- Do not rename a failed hypothesis to preserve its narrative.
- Do not remove a contradictory window from an aggregate.
- Do not move a sample gate after seeing the count.
- Do not use favorable portfolio means to override list-level inconsistency.
- Record `mixed`, `not_confirmed`, `insufficient_data`, and
  `untestable_without_external_data` as valid outcomes.

### 6. No repeated tuning loop on U1/U2

Do not tune thresholds using U1/U2 and then report those same panels as
confirmation. Post-U2 revisions require a later holdout. If no suitable sealed
holdout remains, the correct state is `awaiting_new_holdout`, not validation by
recycling old evidence.

## Future Holdout Registry Template

Complete and commit this table before opening any later holdout:

| Field | Required value |
|---|---|
| Hypothesis ID/version | Immutable version identifier |
| Decision question | One falsifiable research question |
| Allowed inputs | Point-in-time fields available at as-of date |
| Cohort/list definition | Versioned member-level rule |
| Missing-data behavior | Explicit handling rule |
| Candidate dates | Exact preregistered dates |
| Horizon | Fixed before inspection |
| Universe and limit | Fixed before inspection |
| Benchmark | Fixed alias and coverage contract |
| Minimum sample | Fixed count gate |
| Confirmation rule | Fixed per-window direction/quality rule |
| Failure rule | Fixed contradictory or downside rule |
| Readiness commit | Commit hash before output generation |
| Opened windows | Initially none |
| Replacement policy | Infrastructure-only and preregistered |
| Production effect | Always none during validation |

## Requirements Before Production Consideration

No ledger row currently allows production change. A later production review
would require all of the following:

- a versioned design that does not reuse U1/U2 as proof;
- a new preregistered holdout with adequate samples and multiple regimes;
- PIT-safe features and member-level cohort construction;
- explicit current-snapshot bias disclosure or historical status repair;
- drawdown, severe-failure, right-tail, turnover, and cost analysis;
- evidence that favorable averages are not driven by one window;
- a separate implementation proposal, regression tests, rollback, and manual
  merge approval;
- research-only wording until that production review is complete.

## Recommended Next Phase

### Phase 2.31 Research-Only Defensive Positioning Design

The safe next phase should focus only on `long_term_stable` defensive framing
and dashboard/report presentation.

Permitted work:

- define the defensive claim as observed drawdown context, not excess-return
  expectation;
- specify evidence fields such as sample count, drawdown comparator, window
  coverage, excess-return caveat, and current-snapshot limitation;
- design research-only labels and report/dashboard wording;
- define an explicit separation from return-seeking candidate promotion;
- prepare a later holdout contract if the design changes any measurable
  hypothesis.

Not permitted in Phase 2.31:

- changing `long_term_stable` membership;
- changing scoring, ranking, factors, or thresholds;
- promoting it inside production candidate selection;
- launching portfolio recommendations;
- claiming fundamental quality from technical data;
- using U1/U2 again as confirmation for a revised design.

## Explicit Non-Goals

Phase 2.30 does not:

- launch a portfolio recommendation;
- change production candidate logic or list membership;
- add ranking weights or reweight `total_score`;
- change scoring, factor, or validation-label formulas;
- automate trading;
- provide public or personal investment advice;
- fetch provider data or run validation;
- modify generated outputs;
- select or inspect a new holdout.

## Phase Decision

The evidence supports one narrow design path: research-only defensive
positioning for `long_term_stable`. Every other item remains research-only,
observation-only, not confirmed, blocked pending a frozen cohort, or untestable
without external historical data.

Production scoring, ranking, factor formulas, validation math, candidate
selection, production lists, thresholds, and recommendation behavior remain
unchanged.
