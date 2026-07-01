# Phase 3.3 U3 Holdout Preregistration

## Purpose

Phase 3.3 preregisters the U3 holdout contract for the H1-H5
research-only opportunity cohorts before any U3 outcome is inspected.

This is a governance and documentation phase only. It does not run
validation, generate future labels, join labels, compute future returns,
access a provider, or change production behavior.

At the time of this preregistration:

- both U3 windows are future and unopened;
- no U3 outcome-bearing artifact has been inspected;
- no U3 future label has been generated;
- no H1-H5 parameter has been changed;
- U1, U2, and the 2024 answer-key windows remain consumed evidence.

## Why U3 Is Required

U1 and U2 evaluated the old lists and existing score interpretations. H1-H5
did not exist as frozen member-level cohorts before those outcomes were
opened, so U1 and U2 cannot validate H1-H5 retrospectively.

Phase 3.1 established engineering safety only: a finite research config could
run against a feature-only snapshot without future labels. Its smoke counts
are not performance evidence.

Phase 3.2 established presentation safety only: generated H1-H5 outputs could
be loaded through a fail-closed research-only API and UI. Displaying a cohort
does not validate it.

H1-H5 therefore have no prospective effectiveness evidence. A genuinely
unopened U3 holdout is required before any production selection-logic design
decision may be considered. Passing U3 would still not authorize production
implementation.

## Frozen U3 Holdout Manifest

| Field | Frozen value |
|---|---|
| Holdout ID | `u3-prospective-2026-h2-v1` |
| Registration status | `preregistered_unopened` |
| Opened windows | None |
| Window 1 as-of date | `2026-09-30` |
| Window 2 as-of date | `2026-12-31` |
| Horizon | 20 trading days after each as-of date |
| Benchmark | `CSI300` over the identical horizon |
| Universe | Same-date frozen member-level research universe with complete point-in-time H1-H5 feature coverage |
| Minimum valid universe sample | 100 per window |
| Minimum valid cohort sample | 20 per cohort per window |
| Consumed evidence excluded | 2024 answer-key windows, all U1 windows, all U2 windows |
| Replacement policy | Infrastructure-only; any replacement must be preregistered before any outcome inspection |
| Production effect | None |

Both dates are fixed before technical readiness, cohort membership, or
outcomes are opened. Calendar direction, expected market regime, convenience,
and expected performance are not valid reasons to replace either date.

## Frozen Inputs And Safety Boundary

### H1-H5 definitions

The exact frozen cohort identities and roles are:

| ID | Cohort ID | Frozen role |
|---|---|---|
| H1 | `low_position_revaluation_watch` | `opportunity_observation` |
| H2 | `trend_acceleration_with_crowding_guard` | `opportunity_observation` |
| H3 | `right_tail_opportunity_watch` | `opportunity_observation` |
| H4 | `high_position_crowding_risk` | `risk_annotation` |
| H5 | `false_breakout_risk` | `risk_annotation` |

H1-H3 remain observations. H4-H5 remain non-blocking annotations. The
evaluator must not reinterpret H4 or H5 as an automatic exclusion rule.

### Config and parameter freeze

The frozen parameter source is:

```text
research/configs/opportunity_cohorts.phase3_1_smoke.json
config_version = phase3.1-smoke-v1
parameter_source = engineering_smoke_not_u1_u2_tuned
```

All 18 parameter names, numeric values, comparison directions, feature
binding, cohort roles, and missing-data behavior are frozen. U3 readiness or
results must not change them.

The current config is explicitly bound to
`as_of_date=2024-10-31`, while the execution validator requires the config
date to equal the requested snapshot date. It therefore cannot be passed
directly to either U3 date under the current execution schema.

Before Phase 3.4, a separately reviewed date-binding mechanism or immutable
U3 execution manifest must:

- reference `phase3.1-smoke-v1` as the frozen parameter source;
- copy all 18 parameter values and roles exactly;
- bind only the U3 as-of date and version metadata;
- produce a checksum comparison proving that no parameter, feature binding,
  direction, or missing-data rule changed;
- be committed before any U3 outcome is inspected.

This is a technical readiness blocker, not permission to revise or tune the
config.

### Feature-only and builder boundary

Each U3 builder input must be a separately materialized feature-only snapshot
for its exact as-of date. It must contain only information available on or
before that date and must retain the point-in-time leakage diagnostics.

Each frozen builder output must state:

```text
research_only = true
provider_access = false
labels_joined = false
production_change = false
```

The builder input and output must not contain future, forward, realized,
target, outcome, winner/loser, label, future high/low, benchmark outcome, or
holding-period drawdown columns. `future_rows_excluded_count` remains an
allowed point-in-time diagnostic because it records excluded rows rather than
an outcome.

Provider access is forbidden during feature-only cohort generation and during
research output loading. Any future labels must be created and joined only by
a separate evaluator after the config, snapshot, and cohort membership are
frozen and checksummed.

## Evaluation Questions

The following questions are frozen before outcomes are opened.

### H1 low-position revaluation watch

Evaluate whether the low-position revaluation cohort improves opportunity
capture without excessive loser contamination or severe drawdown incidence.
Report the frozen cohort against the same-date eligible universe and relevant
unchanged rebound/accumulation research baselines.

### H2 trend acceleration with crowding guard

Evaluate whether trend-acceleration observations retain upside candidates
while the separate crowding annotation identifies risk. Report disjoint
acceleration members with and without the warning. The warning must not remove
or promote a member.

### H3 right-tail opportunity watch

Evaluate whether the right-tail opportunity observation captures asymmetric
upside while fully reporting loser contamination and drawdown risk. The
cohort name is a hypothesis label, not a future winner label.

### H4 high-position crowding risk

Evaluate whether the crowding-risk annotation explains severe drawdown or
loser contamination. Compare annotated members with a disjoint, eligible
unannotated group and report winners incorrectly warned.

### H5 false-breakout risk

Evaluate whether the false-breakout annotation explains failed observations
inside the unchanged same-date `breakout_watch` and
`accumulation_watch` domains. Report warned and unwarned members separately
for each source list, including retained winners and false warnings.

## Frozen Metric Set

Phase 3.3 freezes the metric names and denominator semantics but computes
nothing.

| Metric | Conceptual definition |
|---|---|
| Member count | Distinct symbols in the frozen cohort for one U3 as-of date |
| Valid future label count | Frozen members with a complete, unchanged 20-day evaluator label |
| Winner capture | Number and share of valid universe winners included in the frozen cohort; also report winner share within valid cohort labels |
| Loser contamination | Valid cohort members carrying the unchanged loser definition divided by valid cohort labels |
| Severe drawdown incidence | Valid cohort members crossing the unchanged severe-drawdown definition divided by members with valid drawdown labels |
| Benchmark excess return | Member 20-day return minus CSI300 return over the identical horizon; report window mean and median separately |
| Right-tail retention | Valid right-tail members retained after an annotation or guard divided by the relevant valid right-tail source domain |
| False warning rate | Warned valid members that later meet the unchanged winner/right-tail definition divided by warned valid members |
| Coverage | Valid future label count divided by frozen member count, with missing-label reasons reported |
| Empty-cohort rate | Number of empty preregistered cohort-windows divided by the two U3 windows |
| Sample sufficiency | Whether the frozen universe and per-cohort minimum gates are met without pooling away a weak window |

The separate evaluator must reuse existing label and benchmark definitions
without changing validation math. Exact winner, loser, right-tail, and severe
drawdown boundaries must be referenced from the committed evaluator contract
before U3 labels are generated. They may not be inferred, moved, or selected
from U3 results.

Every metric must be reported per window and per cohort before any pooled
summary. H2, H4, and H5 must also report their preregistered disjoint warned
and unwarned comparisons. A pooled average cannot hide an empty,
underpowered, or contradictory window.

## Sample Gates And Interpretation

### Window and cohort gates

- Each U3 window requires at least 100 valid universe rows.
- Each H1-H5 cohort requires at least 20 valid labeled members per window for
  its effectiveness interpretation.
- Missing labels do not count toward the valid cohort gate.
- Empty cohorts remain reported with `member_count=0`.
- A cohort below 20 valid members is `underpowered` for that window.
- A window below 100 valid universe rows is `underpowered` for every cohort.
- Underpowered windows must not be silently dropped, replaced, or pooled into
  an apparently adequate result.

### Cross-window status

Each H1-H5 hypothesis receives one of these preregistered statuses:

- `supported_research_only`: both windows are adequately powered, the primary
  metrics move in the hypothesized direction in both windows, and no material
  severe-drawdown, loser-contamination, or false-warning contradiction is
  hidden by aggregation;
- `mixed_research_only`: only one adequately powered window supports the
  hypothesis, metrics conflict within or across windows, or opportunity and
  risk evidence point in different directions;
- `not_confirmed`: both adequately powered windows fail to support the frozen
  question or show repeated opposite-direction evidence;
- `underpowered`: either required window or cohort gate prevents the frozen
  question from being evaluated;
- `invalid_execution`: a safety, leakage, config, or preregistration failure
  makes the result unusable.

Passing one window is never sufficient for production authorization. Mixed
results remain research-only. Even `supported_research_only` permits only a
later governance review; it does not authorize production logic.

## Failure And Invalidation Criteria

U3 execution is invalid, not merely underpowered, if any of the following
occurs:

- future leakage is detected;
- future labels are joined inside the H1-H5 builder input or output;
- provider access occurs during research output generation or loading;
- the exact-date feature-only snapshot is absent or not point-in-time safe;
- the config or any of its 18 values differs from the preregistered parameter
  source;
- a U3 outcome is inspected before this preregistration is merged and tagged;
- a cohort input or output contains a future, label, target, outcome,
  winner/loser, realized-return, benchmark-outcome, or holding-period field;
- a U3 date, horizon, benchmark, universe, sample gate, metric, comparison, or
  interpretation rule is changed after outcome inspection;
- production scoring, ranking, factors, candidate selection, list membership,
  thresholds, or recommendation behavior changes before validation;
- an empty, weak, failed, or contradictory window is omitted;
- U1, U2, the 2024 answer key, or Phase 3.1 smoke counts are used to tune the
  config or presented as U3 confirmation.

An invalid execution must be retained in the U3 ledger with its exact blocker.
It cannot be repaired by deleting the record or choosing a favorable
replacement date after outcomes are known.

## Readiness Failure And Replacement Policy

Technical readiness must inspect only cache coverage, point-in-time metadata,
schema compatibility, config identity, file existence, and checksums. It must
not inspect outcome-bearing columns or files.

If a preregistered date fails readiness:

1. record the exact infrastructure blocker;
2. do not generate or inspect its outcome labels;
3. attempt only a scope-approved infrastructure repair;
4. retain the failed date and blocker in the U3 ledger;
5. if replacement is unavoidable, preregister and merge the replacement
   before any outcome inspection;
6. preserve the 20-day horizon, CSI300 benchmark, universe contract, sample
   gates, and H1-H5 parameter values.

No replacement date is registered by Phase 3.3.

## Allowed Post-U3 Decisions

After U3 is opened once and fully reported, the allowed decisions are:

- keep one or more H1-H5 hypotheses research-only without revision;
- improve research-only display, caveats, data-quality explanations, or
  unavailable states without changing membership;
- mark a hypothesis `not_confirmed`, `mixed_research_only`, or `underpowered`;
- preregister a revised config version and a different unopened holdout;
- write a separate production selection-logic design only if evidence is
  sufficiently strong, stable across both windows, adequately powered, and
  free of unresolved safety failures.

A production design is only a proposal for later review. It requires its own
authorization, regression plan, rollback plan, monitoring contract, and
default-off implementation phase.

## Forbidden Post-U3 Decisions

U3 must not be used to:

- issue direct buy or sell recommendations;
- use guaranteed-return, stable-profit, risk-free, or validated-alpha
  language;
- reweight `total_score` without a separate versioned design and later
  holdout;
- automatically exclude `high_risk_active` or any H4/H5 annotated member;
- use Phase 3.1 smoke counts as effectiveness evidence;
- tune with U1/U2 outcomes and still claim U3 validation;
- change a threshold, feature, cohort role, missing-data rule, sample gate, or
  success rule after U3 outcomes are opened;
- promote one favorable window while suppressing a weak or contradictory
  window;
- treat a supported research result as automatic production approval.

## Phase 3.4 Readiness Checklist

Phase 3.4 must not begin until every item is complete:

- [ ] This U3 preregistration is merged and tagged.
- [ ] Both U3 dates remain unopened and the U3 ledger lists no opened window.
- [ ] The Phase 3.1 parameter source and all 18 values are checksum-verified.
- [ ] The config date-binding blocker is resolved without changing any
  parameter, role, feature binding, direction, or missing-data rule.
- [ ] Feature-only snapshots exist for `2026-09-30` and `2026-12-31`.
- [ ] Each snapshot passes point-in-time, leakage, schema, and outcome-column
  checks without reading results.
- [ ] Label-free H1-H5 outputs are generated for both dates with the frozen
  parameter source.
- [ ] Config version, execution manifest, snapshot, cohort output, and
  checksums are sealed before any label is generated.
- [ ] Builder outputs state `labels_joined=false`,
  `provider_access=false`, `research_only=true`, and
  `production_change=false`.
- [ ] The U3 evaluator is explicitly separate from the H1-H5 builder.
- [ ] The evaluator references unchanged label math, CSI300 benchmark
  handling, metrics, disjoint comparisons, and sample gates.
- [ ] Every output path is versioned and cannot overwrite U1, U2, smoke, or
  development artifacts.
- [ ] Generated snapshots, cohort files, labels, and validation results remain
  uncommitted unless an artifact is intentionally documented and approved.
- [ ] No production scoring, ranking, factor, candidate, list, threshold, or
  recommendation change is present.

Any unchecked item is a blocker. Phase 3.4 readiness is not permission to open
outcomes; the user must explicitly start the controlled validation workflow.

## Phase Decision

U3 is preregistered as two future, unopened 20-day windows:
`2026-09-30` and `2026-12-31`.

Phase 3.3 freezes governance only. It produces no U3 cohort output, future
label, validation result, performance conclusion, provider request, parameter
change, or production change.
