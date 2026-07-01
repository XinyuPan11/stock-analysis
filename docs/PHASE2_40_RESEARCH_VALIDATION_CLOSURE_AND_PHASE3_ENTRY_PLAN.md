# Phase 2.40 Research Validation Closure and Phase 3 Entry Plan

## Closure Decision

Phase 2 is closed as a research-validation and governance phase.

It established point-in-time data boundaries, controlled U1/U2 evaluation,
honest verdicts for the existing lists, research-only presentation layers, and
fail-closed infrastructure for the future H1-H5 opportunity cohorts.

It did not establish a production-ready return model. No production scoring,
ranking, candidate-list, membership, threshold, or recommendation change is
authorized by Phase 2.

## What Phase 2 Established

### Controlled evidence was opened once and consumed

The preregistered U1 and U2 panels were completed and analyzed. Their
point-in-time and no-future-leakage checks passed under the controlled
validation contracts.

All U1 and U2 windows are now consumed evidence:

- they may be cited as historical research context;
- they may explain why a hypothesis exists;
- they may not be reused as sealed proof;
- they may not be used to tune a revised rule and then validate that revision
  on the same windows.

### Existing lists received stable interpretation boundaries

The evidence was strong enough to assign research roles, but not strong enough
to authorize production logic changes.

The clearest confirmed result was the defensive drawdown behavior of
`long_term_stable`: in U2 it had shallower average holding drawdown than the
three active lists in all four windows. Its excess return was negative in
three of four U2 windows, so this is defensive context rather than stable
excess-return evidence.

### Research governance became explicit

Phase 2 added:

- point-in-time feature slicing and leakage diagnostics;
- current-snapshot bias disclosures;
- controlled readiness, cache, and validation paths;
- answer-key versus unseen-evidence boundaries;
- U1/U2 preregistration and consumption rules;
- fail-closed research-only presentation;
- frozen H1-H5 input, builder, parameter, and config-schema contracts.

These controls are durable project infrastructure. They do not themselves
prove model effectiveness.

## What Phase 2 Did Not Establish

Phase 2 did not prove:

- stable excess return for any existing positive list;
- stable positive ranking power for `total_score`;
- a stable negative direction for `high_risk_active`;
- production-ready winner capture from H1-H5;
- production portfolio behavior, turnover, or cost robustness;
- historical point-in-time correctness for all universe, listing, ST, and
  suspension metadata;
- the external theme, event, fundamental, industry, or historical-status
  hypotheses that require unavailable versioned data.

H1-H5 were not present as frozen member-level cohorts before U1 or U2 opened.
They therefore remain unvalidated and cannot be retrofitted to those consumed
windows.

## Existing-List Decision Ledger

| Existing item | Phase 2 verdict | Permitted interpretation | Production change now |
|---|---|---|---|
| `long_term_stable` | `defensive_positioning_only` | Research-only defensive observation; shallower U2 drawdown with unstable excess return | No |
| `high_confidence_candidates` | `research_only` | Selective research candidates with unstable cleanliness and cross-window evidence | No |
| `trend_leaders` | `not_confirmed` | Trend context only; not a stable positive baseline | No |
| `breakout_watch` | `observation_only` | High-volatility opportunity observation with material downside and variance | No |
| `accumulation_watch` | `observation_only` | Broad active observation with unstable cross-window behavior | No |
| `rebound_watch` | `observation_only` | Limited, one-window-sensitive evidence | No |
| `high_risk_active` | `not_confirmed` | Risk-review context; not a confirmed stable negative bucket or automatic exclusion | No |
| `total_score` | `not_confirmed` | Existing descriptive score only; U1/U2 support no reweighting | No |

The table changes interpretation and presentation only. Existing list names,
members, order, ranks, and generation rules remain authoritative and
unchanged.

## Current Implementation State

| Capability | Current state | Boundary |
|---|---|---|
| Defensive presentation | Research-only defensive UI/API overlay exists for `long_term_stable` | Presentation only; fail closed when evidence is unavailable |
| Candidate tiering | Research-only API/UI exists at `/api/lists/tiers` and `/lists/tiers` | Static reading order over unchanged list payloads |
| H1-H5 specification | Frozen research roles, fields, caveats, and output contract exist | Not production eligible |
| Opportunity cohort builder | Feature-only, explicit-config, fail-closed builder exists | No outcome evaluation and no provider access |
| Feature-only snapshot export | Safe export path exists | Future/outcome fields are rejected or explicitly removed and audited |
| Parameter governance | Non-runnable preregistration template exists | All 18 H1-H5 parameters remain `null` |
| Config schema guard | Template and execution validation modes exist | Template mode is never runnable; execution requires a frozen holdout contract |
| Real H1-H5 outputs | Not generated | No real cohort membership has been opened |
| Final H1-H5 parameters | Not selected | No parameter set is frozen or production approved |

Generated research and validation outputs remain local artifacts and are not
part of this closure commit.

## Allowed Phase 3 Research Work

The following work may begin after the Phase 3 entry criteria are satisfied:

- design an explicit, versioned, research-only runnable H1-H5 config;
- justify parameters independently of U1/U2 and answer-key outcomes;
- run a feature-only snapshot dry-run or small smoke;
- generate label-free H1-H5 research cohort membership;
- expose frozen research cohorts through a research-only UI/API layer;
- preregister a genuinely unopened U3 holdout;
- evaluate frozen cohorts only after membership is sealed and labels are
  joined by a separate evaluator.

These permissions apply only to research surfaces. They do not authorize
production behavior.

## Still Prohibited

The following remain prohibited:

- reweighting production `total_score`;
- changing `high_confidence_candidates`, `trend_leaders`, or another existing
  list's membership logic;
- changing production scoring, ranking, factor, candidate, or threshold
  rules;
- treating `high_risk_active` as automatic exclusion;
- launching a portfolio recommendation;
- action-directed buy/sell language;
- claims of guaranteed return, stable profit, risk-free behavior, or
  validated alpha;
- tuning with U1/U2 and then presenting those same panels as validation;
- joining future labels inside the H1-H5 builder;
- opening U3 outcomes before the config, cohorts, evaluator contract, and
  holdout are frozen.

## Compressed Phase 3 Roadmap

### Phase 3.1 H1-H5 Runnable Research Config + Feature-only Smoke

Create one versioned research config with explicit finite parameters,
documented independent rationale, and a prospective unopened holdout contract.
Run schema-check and feature-only smoke only.

Exit gate:

- config passes execution schema;
- no parameter is derived from U1/U2 or answer-key outcomes;
- feature-only input contains no labels;
- no real outcome evaluation occurs.

### Phase 3.2 H1-H5 Research Cohort Output + UI/API Stub

Generate and seal label-free H1-H5 membership from the frozen config and
feature-only snapshot. Add research-only presentation without changing source
lists or production logic.

Exit gate:

- cohort output, config version, snapshot version, and checksums are frozen;
- H1-H3 remain opportunity observations;
- H4-H5 remain non-blocking risk annotations;
- no labels or performance conclusions appear in builder output.

### Phase 3.3 U3 Holdout Preregistration

Freeze the U3 evaluator manifest before outcomes are inspected. It must
reference the already frozen config and cohort output and define:

- exact dates, horizon, benchmark, and universe;
- minimum sample and coverage gates;
- success, mixed, failure, and insufficient-data rules;
- all metrics and disjoint comparisons;
- replacement-window policy;
- consumed-window exclusions.

The prospective holdout named in Phase 3.1 becomes formally sealed here. No
parameter may change between cohort freeze and U3 evaluation.

### Phase 3.4 U3 Validation Execution

The user manually runs readiness, cache-only preparation, controlled
validation, and the separate cohort evaluator. Codex prepares code, short
tests, commands, and diagnostics but does not run long jobs.

Exit gate:

- point-in-time and bias metadata are present;
- provider access follows the approved manual workflow;
- every preregistered U3 window is reported;
- no threshold is changed after opening outcomes.

### Phase 3.5 U3 Result Analysis

Analyze U3 once under the frozen rules. Report supported, mixed, rejected, and
insufficient hypotheses honestly, including contradictory windows, sample
limitations, false warnings, right-tail loss, and opportunity cost.

U3 becomes consumed immediately after analysis.

### Phase 3.6 Production Selection Logic Decision

Make a governance decision, not an automatic promotion:

- reject or retain each H1-H5 hypothesis;
- identify whether evidence supports research continuation only;
- require a separate later holdout for any post-U3 revision;
- document why production change is or is not allowed.

No implementation is implied by a favorable U3 result.

### Phase 3.7 Behind-Flag Production Logic Implementation

This phase is permitted only if Phase 3.6 explicitly authorizes it from
adequate evidence.

Any implementation must be:

- behind a default-off flag;
- separately reviewed and manually approved;
- covered by regression, rollback, monitoring, and wording safeguards;
- isolated from unchanged production behavior until activation is approved.

If evidence is insufficient, Phase 3.7 is skipped.

## Phase 3 Entry Criteria

Phase 3 may start only when all conditions are true:

- Phase 2.39 config schema guard is merged;
- Phase 2.40 is merged and tagged;
- H1-H5 parameters remain unfilled by outcome-driven tuning;
- no real H1-H5 cohort output has been generated before the next approved
  phase;
- generated `outputs/` artifacts remain uncommitted;
- production scoring, ranking, factors, validation math, candidate selection,
  list membership, thresholds, and recommendation logic remain unchanged;
- U1/U2 and answer-key windows remain marked consumed and excluded from proof.

## Immediate Next Phase

The recommended next phase is:

```text
Phase 3.1 H1-H5 Runnable Research Config + Feature-only Smoke
```

Phase 3.1 should remain small. It should freeze one independently justified
research config, verify the schema, and run only a feature-only smoke. It
should not evaluate outcomes, change existing lists, or make production
claims.

## Final Phase 2 Boundary

Phase 2 closes with a useful negative result and a useful engineering result:

- no production model change was justified;
- the existing lists now have honest research roles;
- the project has safer point-in-time, holdout, presentation, and cohort
  infrastructure;
- the next research hypothesis can be tested without quietly reusing consumed
  evidence.

That is sufficient closure. Further H1-H5 implementation and evidence work
belongs to Phase 3.
