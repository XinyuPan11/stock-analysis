# Phase 3.6 Historical Sealed H1-H5 Validation Preregistration

## Purpose

Phase 3.6 preregisters a historical sealed validation plan for the
research-only H1-H5 opportunity cohorts. It uses already-available historical
dates only if their H1-H5 outcomes remain unopened and all contamination and
readiness gates pass.

This is a governance and documentation phase only. It does not run
validation, inspect outcomes, generate or join future labels, compute future
returns, access a provider, build real H1-H5 memberships, or change any
config, parameter, formula, production rule, or generated output.

Historical sealed evidence is weaker than genuinely prospective evidence.
This plan is independent of U3 and must never be presented as prospective U3
proof.

## Historical Sealed Validation Identity

| Field | Frozen value |
|---|---|
| Validation ID | `h1h5-historical-sealed-v1` |
| Registration status | `preregistered_not_executed_pending_readiness_and_contamination_audit` |
| Evidence level | `historical_sealed_not_prospective` |
| Benchmark | `CSI300` |
| Horizon | 20 trading days after each as-of date |
| Config source | `phase3.1-smoke-v1` parameter block |
| Parameter count | 18 |
| Parameter change | `false` |
| Tuning change | `false` |
| Production change | `false` |
| Builder labels joined | `false` |
| Provider access | `false` |

The identity is also frozen in key-value form:

```text
validation_id = h1h5-historical-sealed-v1
evidence_level = historical_sealed_not_prospective
benchmark = CSI300
horizon = 20 trading days
config_source = phase3.1-smoke-v1 parameter block
parameter_change = false
tuning_change = false
production_change = false
labels_joined = false
```

The parameter source is:

```text
research/configs/opportunity_cohorts.phase3_1_smoke.json
config_version = phase3.1-smoke-v1
parameter_source = engineering_smoke_not_u1_u2_tuned
```

The frozen reference parameter digest recorded by Phase 3.4 is:

```text
163b90128233383d9965c17fa2e1065c50222e4db706c93787326053ef8fca46
```

All 18 numeric values, comparison directions, feature bindings, missing-data
behavior, cohort identities, and cohort roles remain unchanged. H1-H3 remain
opportunity observations. H4-H5 remain non-blocking risk annotations.

Phase 3.7 may create separate historical date-bound execution configs only
after this preregistration is merged and tagged. Those configs must copy the
frozen parameter block and logic exactly, use the historical validation
identity and namespace, and must not reuse or modify either U3 config.

## Evidence Boundary Versus Prospective U3

Historical sealed validation and prospective U3 are separate evidence tracks.

| Boundary | Historical sealed track | Prospective U3 track |
|---|---|---|
| Identity | `h1h5-historical-sealed-v1` | `u3-prospective-2026-h2-v1` |
| Evidence level | `historical_sealed_not_prospective` | Prospective unopened holdout |
| Dates | Historical windows frozen below | `2026-09-30`, `2026-12-31` |
| Configs | Future historical date-bound configs | Existing U3 date-bound configs |
| Readiness | Separate historical readiness path in Phase 3.7 | Existing U3 readiness path |
| Artifacts and ledger | Historical-only namespace and records | U3-only namespace and records |
| Interpretation | Research-only historical evidence | Separate prospective confirmation |

Historical results must not be pooled with U3, substituted for a U3 window,
used to make U3 readiness pass, or described as prospective confirmation.
U3 remains untouched and future.

## Preregistered Historical Windows

### Primary windows

The primary windows are frozen in this order:

| Priority | As-of date | Horizon | Current preregistration state |
|---|---|---|---|
| P1 | `2026-01-30` | 20 trading days | Candidate pending contamination and readiness audit |
| P2 | `2026-03-31` | 20 trading days | Candidate pending contamination and readiness audit |
| P3 | `2026-04-30` | 20 trading days | Candidate pending contamination and readiness audit |

These dates are preregistered candidates, not declarations that clean inputs,
complete labels, or adequate samples already exist. Phase 3.6 does not inspect
those facts.

### Backup windows

Backups may be activated only when a primary window is blocked by missing
local data or contamination:

| Backup priority | As-of date | Horizon | Additional condition |
|---|---|---|---|
| B1 | `2026-02-27` | 20 trading days | Use only as the first eligible replacement |
| B2 | `2026-05-29` | 20 trading days | Use only if complete 20D future coverage already exists locally without provider fetch |

Backups are not extra favorable windows and must not increase the panel after
results are known. Replacement uses the frozen order, preserves the blocked
primary date and reason in the ledger, and is decided from contamination and
technical readiness only. No H1-H5 outcome, return, label, or performance
metric may be inspected when selecting a replacement.

If neither backup is eligible, retain the blocked or underpowered panel. Do
not discover a new date during execution.

## Permanently Excluded Or Reserved Windows

| Category | Excluded dates | Reason |
|---|---|---|
| Original answer-key windows | `2024-01-31`, `2024-04-30`, `2024-07-31`, `2024-10-31` | Development and answer-key outcomes were used; they are consumed and permanently ineligible as sealed proof |
| Consumed U1 windows | `2024-02-29`, `2024-05-31`, `2024-08-30`, `2024-11-29` | U1 outputs were opened and analyzed |
| Consumed U2 windows | `2025-02-28`, `2025-05-30`, `2025-08-29`, `2025-11-28` | U2 outputs were opened and analyzed |
| Prospective U3 windows | `2026-09-30`, `2026-12-31` | Reserved exclusively for future prospective U3 proof |

`2024-10-31` is also the Phase 3.1 engineering smoke date. Its feature-only
smoke counts and generated membership facts are execution diagnostics only
and can never become validation evidence.

## Contamination Rules

A candidate or backup window is invalid for
`h1h5-historical-sealed-v1` if any of the following is true:

- H1-H5 future outcomes for that date were already inspected.
- Any H1-H5 parameter, direction, feature binding, role, or missing-data rule
  was tuned using that date.
- Validation, list-performance, or factor-effectiveness outputs for that date
  were opened and used in a way that informs H1-H5 expectations or decisions.
- Future labels were joined before the no-label cohort membership was frozen
  and checksummed.
- The builder input or output contains a label, target, future, forward,
  realized, winner/loser, outcome, benchmark-outcome, or holding-period field.
- Production scoring, ranking, factor, candidate selection, list membership,
  threshold, or recommendation logic changed before this validation.
- A provider fetch is required to fill historical feature data or future data
  for the sealed window.
- An execution artifact was overwritten, regenerated after outcomes were
  opened, or cannot be tied to its frozen config and snapshot checksums.
- A blocked, empty, weak, contradictory, or underpowered window is hidden or
  replaced after inspecting its results.

Contamination produces `invalid_execution`, not `underpowered`. Record the
date, exact reason, discovery time, and affected artifacts in the historical
ledger. Do not repair contamination by deleting evidence or choosing a date
with more favorable expected performance.

The contamination audit may inspect file existence, names, metadata,
checksums, prior-use records, and access history. It must not open
outcome-bearing values.

## Readiness Requirements

Phase 3.7 must implement a separate fail-closed historical readiness path.
The current U3 readiness checker is fixed to the U3 identity and dates and
must not be repurposed as proof that a historical window is ready.

The sample gates are frozen as:

```text
minimum_valid_universe_rows_per_window >= 100
minimum_valid_labeled_members_per_cohort_per_window >= 20 where applicable
```

### Before label-free cohort generation

Each selected window must satisfy all of the following:

- this preregistration is merged and tagged;
- its contamination audit passes without inspecting outcomes;
- the exact source as-of snapshot exists or can be built entirely from
  existing local cached data without provider access;
- the feature-only snapshot can be exported for the exact as-of date;
- every exported row is point-in-time safe and has
  `leakage_guard_applied=true`;
- no input date used by a feature exceeds the as-of date;
- the feature-only snapshot contains no future, outcome, label, target,
  winner/loser, realized-return, benchmark-outcome, or holding-period field;
- the historical date-bound config passes execution-mode schema validation;
- the parameter digest exactly matches `phase3.1-smoke-v1`;
- all 18 values, roles, directions, documentation, and feature bindings match
  the frozen source;
- `research_only=true`, `provider_access=false`, `labels_joined=false`, and
  `production_change=false`;
- the valid feature-only universe contains at least 100 rows;
- U3 configs and U3 artifacts remain unchanged.

Failure of the 100-row universe gate makes the window underpowered and blocks
normal builder write-output unless a later phase explicitly defines how to
freeze and report the failed attempt. It never permits a threshold change.

### After cohort freeze and during separate evaluation

The separate evaluator must require at least 20 valid labeled members per
cohort per window where that cohort-level metric applies. Missing labels do
not count toward this gate.

An empty or below-20 cohort is still reported. It receives an underpowered
interpretation for that window and must not be dropped, hidden, pooled away,
or replaced based on its result. Readiness and evaluation reports must expose
empty-cohort and underpowered rates explicitly.

## Frozen Evaluation Goals

| ID | Cohort | Frozen evaluation goal |
|---|---|---|
| H1 | `low_position_revaluation_watch` | Assess low-position revaluation opportunity capture against loser contamination and severe downside |
| H2 | `trend_acceleration_with_crowding_guard` | Assess upside retention while interpreting crowding risk separately and without excluding warned members |
| H3 | `right_tail_opportunity_watch` | Assess asymmetric upside capture while fully disclosing drawdown and loser contamination |
| H4 | `high_position_crowding_risk` | Assess whether the annotation explains severe drawdown or loser contamination, including retained winners and false warnings |
| H5 | `false_breakout_risk` | Assess failed-breakout or failed-accumulation risk inside the unchanged source-list domains, with warned and unwarned members reported separately |

These are research questions, not directional promises. H4 and H5 remain
annotations and cannot automatically remove, demote, or block a symbol.

## Frozen Conceptual Metrics

Phase 3.6 names the metrics but computes none.

| Metric | Conceptual definition |
|---|---|
| Member count | Distinct symbols in a frozen cohort for one window |
| Valid label count | Frozen cohort members with a complete unchanged 20D label |
| Winner capture | Valid universe winners included in the cohort, reported as a count and share; also report winner share within valid cohort labels |
| Loser contamination | Valid cohort members meeting the unchanged loser definition divided by valid cohort labels |
| Severe drawdown incidence | Valid cohort members meeting the unchanged severe-drawdown definition divided by members with valid drawdown labels |
| Benchmark excess return | Member 20D return minus CSI300 return over the identical horizon; report mean and median separately |
| Right-tail retention | Valid right-tail members retained in the relevant cohort or warned/unwarned comparison divided by the valid right-tail source domain |
| False warning rate | Warned valid members that meet the unchanged winner or right-tail definition divided by warned valid members |
| Coverage | Valid label count divided by frozen member count, with missing-label reasons retained |
| Empty-cohort rate | Empty preregistered cohort-windows divided by all executed preregistered cohort-windows |
| Underpowered rate | Cohort-windows failing the frozen valid-sample gate divided by all executed preregistered cohort-windows |

All metrics must be reported per window and per cohort before any pooled
summary. H2, H4, and H5 must preserve disjoint warned and unwarned comparisons
where applicable. No pooled statistic may conceal a contradictory, empty,
invalid, or underpowered window.

Exact winner, loser, right-tail, severe-drawdown, return, and benchmark label
math must be referenced from an unchanged committed evaluator contract before
labels are generated. Phase 3.6 does not define, revise, or compute those
labels.

## Result Statuses

Every H1-H5 conclusion must use one of these statuses:

- `supported_research_only`: adequately powered historical windows support
  the frozen research question without a material hidden contradiction;
- `mixed_research_only`: adequately powered windows or metrics disagree, or
  opportunity and risk evidence point in different directions;
- `not_confirmed`: adequately powered evidence does not support the frozen
  question or repeatedly moves in the opposite direction;
- `underpowered`: the frozen universe, cohort, label, coverage, or
  empty-cohort gates prevent a reliable interpretation;
- `invalid_execution`: contamination, leakage, config drift, provider access,
  premature label joining, or another governance failure makes the evidence
  unusable.

No historical sealed status alone authorizes a production change. Strong
historical results may justify building the separate evaluator carefully and
later seeking prospective U3 confirmation. Mixed, not-confirmed, and
underpowered results remain research-only and must be retained.

## Later Execution Order

The frozen order for later phases is:

1. merge and tag this Phase 3.6 preregistration;
2. audit contamination and local source availability without opening outcome
   values;
3. select primary windows or activate backups only under the frozen
   replacement rules, recording every blocker;
4. create and export exact-date feature-only snapshots from existing local
   cached data;
5. run the separate historical readiness check;
6. run date-specific builder dry-runs;
7. after review, run builder write-output;
8. freeze and checksum all no-label cohort outputs, configs, snapshots, and
   execution records;
9. only then run a separately designed evaluator that joins unchanged labels;
10. analyze and report every selected, blocked, invalid, empty, and
    underpowered window;
11. keep prospective U3 configs, artifacts, outcomes, and evidence untouched.

No step may be reordered to inspect labels before membership freeze.

## Forbidden Decisions

Historical sealed results must not be used to:

- issue buy or sell recommendations;
- use guaranteed-return, stable-profit, risk-free, or validated-alpha
  language;
- reweight `total_score`;
- automatically exclude `high_risk_active` or an H4/H5 annotated member;
- launch or authorize a production recommendation path;
- change production scoring, ranking, factor, candidate, list, threshold, or
  recommendation logic;
- change validation-label math after results are inspected;
- tune the 18 H1-H5 parameters or reuse the same historical windows as proof
  after a revision;
- use smoke membership counts as validation evidence;
- omit weak, contradictory, empty, invalid, or underpowered results;
- present historical sealed evidence as prospective U3 proof.

## Recommended Next Phase

The next phase is:

```text
Phase 3.7 Historical Sealed H1-H5 Execution Readiness and Feature Snapshot Preparation
```

Phase 3.7 should remain label-free and provider-free. It may add separate
historical date-bound configs, contamination/readiness records, and
feature-only snapshot preparation for the frozen candidate windows. It must
not run the evaluator, generate labels, inspect outcomes, or modify U3.

## Phase Decision

Phase 3.6 preregisters three primary and two conditional backup historical
windows under `h1h5-historical-sealed-v1`.

The dates remain candidates until their contamination and readiness gates
pass. No historical window is declared clean merely because it is available,
and no result is opened by this phase.

This preregistration changes documentation only. It authorizes no validation
execution, provider access, future-label generation, outcome inspection,
parameter tuning, config change, real cohort output, or production behavior.
