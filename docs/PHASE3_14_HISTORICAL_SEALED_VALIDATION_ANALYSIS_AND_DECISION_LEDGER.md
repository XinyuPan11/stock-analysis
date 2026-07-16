# Phase 3.14 Historical Sealed Validation Analysis And Decision Ledger

## Decision

Phase 3.14 completed the authorized final evaluator write-out for the three
frozen primary windows and reviewed the preregistered H1-H5 metrics. The
historical sealed evidence does **not** provide strong, consistent, and
decision-relevant support for any cohort.

The next phase is therefore:

```text
Phase 3.15 H1-H5 Research-Only Closure
```

This is not a production-design handoff. No production scoring, ranking,
selection, list, threshold, recommendation, API, UI, or U3 change is
authorized.

## Frozen Evidence Identity

```text
validation_id = h1h5-historical-sealed-v1
evidence_level = historical_sealed_not_prospective
benchmark = CSI300
horizon = 20 trading days
primary windows = 2026-01-30, 2026-03-31, 2026-04-30
minimum valid labels per cohort per window = 20
research_only = true
production_change = false
```

Historical sealed results remain weaker than prospective U3 evidence and are
not U3 proof. The future U3 windows and runbook were not changed or executed.

## Execution Integrity

All three final evaluator runs completed with:

- the committed frozen cohort SHA-256 verified before label load;
- 276 valid label rows and zero missing label rows per window;
- labels joined only inside the evaluator;
- unchanged frozen membership;
- `provider_access=false`;
- `builder_labels_joined=false`;
- `production_change=false`.

The final artifacts are:

| Window | CSV SHA-256 | JSON SHA-256 |
|---|---|---|
| 2026-01-30 | `844B6F62B3BB83214DA5958483F64E4B409BD63519514680E122E5BA5F62D0B1` | `24A25BF9AC1B6DD9ABA8BCCE0496C62B705D6812B109D5F7B01FB074855BDE9B` |
| 2026-03-31 | `7EA861F9599410CA83D9757E946C4884ADF5747B452ADA602D527A81127B1944` | `3A694FE7B049233DC2A4763D6DE474F1DF2F4BE4AA429687422E20AD965160A0` |
| 2026-04-30 | `49FABCACE3496861A261D502A8CAF13E6AB960975B5F438A39EE255C1D9EB358` | `A449EA959A7D62786B6885810D01F024B25F6BF64C730D30CC49264582BDB9CE` |

Cross-window decisions are recorded in:

```text
outputs/validation/historical_h1h5_summary_h1h5-historical-sealed-v1.json
```

## Interpretation Boundary

The only frozen numeric interpretation gate is the minimum of 20 valid
labels for one cohort in one window. Phase 3.10 deliberately assigned an
adequately powered result the conservative `mixed_research_only` default
until later interpretation rules were preregistered. No numeric performance
threshold for a stronger support claim was frozen before outcomes were
opened.

Phase 3.14 therefore does not invent a post-outcome winner-capture, excess
return, contamination, drawdown, or false-warning threshold. A cohort with
no adequately powered primary window remains `underpowered`. H2 retains the
evaluator's `mixed_research_only` status because only one window is powered;
the other two are underpowered and the observed directions are not
consistent. `supported_research_only` and `not_confirmed` are not assigned
without a preregistered stronger interpretation rule.

This conservative handling prevents a small or selectively favorable result
from becoming a retrospective production-design authorization.

## Window-Level Sample Sufficiency

| Cohort | Role | 2026-01-30 | 2026-03-31 | 2026-04-30 | Powered windows |
|---|---|---:|---:|---:|---:|
| H1 low-position revaluation watch | Opportunity observation | 0 | 1 | 9 | 0 |
| H2 trend acceleration with crowding guard | Opportunity observation | 15 | 15 | 25 | 1 |
| H3 right-tail opportunity watch | Opportunity observation | 0 | 0 | 0 | 0 |
| H4 high-position crowding risk | Risk annotation | 0 | 0 | 0 | 0 |
| H5 false-breakout risk | Risk annotation | 9 | 9 | 13 | 0 |

Fourteen of the fifteen cohort-window observations are underpowered. Only H2
on 2026-04-30 clears the frozen 20-label gate. H3 and H4 are empty in every
window. Empty cohorts remain visible and are not treated as zero-risk or
negative evidence.

## H1 Low-Position Revaluation Watch

**Final status: `underpowered`. Production-design eligibility:
`not_allowed`.**

H1 has 0, 1, and 9 valid members. The one-member March observation has
-14.81% mean/median excess return and 100% loser contamination; the
nine-member April observation has -3.06% mean excess return, -6.40% median
excess return, and 33.33% severe-drawdown incidence. These figures are
descriptive only because every window is below the frozen gate.

H1 cannot be supported or rejected from this evidence and cannot proceed to
production design.

## H2 Trend Acceleration With Crowding Guard

**Final status: `mixed_research_only`. Production-design eligibility:
`allowed_for_research_display_only`.**

| Window | Valid n | Winner capture | Loser contamination | Severe drawdown | Mean excess | Median excess | Right-tail retention |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2026-01-30 | 15 | 7.14% | 13.33% | 6.67% | +4.60% | +3.58% | 7.14% |
| 2026-03-31 | 15 | 7.14% | 46.67% | 26.67% | -10.67% | -14.38% | 5.36% |
| 2026-04-30 | 25 | 7.14% | 20.00% | 24.00% | -5.89% | -10.13% | 10.71% |

Only April is adequately powered. In that window both mean and median excess
returns are negative, while loser contamination and severe-drawdown
incidence remain material. January is directionally favorable but
underpowered; March is directionally adverse and underpowered. Winner capture
is unchanged at 7.14% across windows, while right-tail retention remains low.

The pattern is neither strong nor consistent. H2 may remain visible in
research-only analysis, but it cannot authorize production design or a
selection/recommendation change.

## H3 Right-Tail Opportunity Watch

**Final status: `underpowered`. Production-design eligibility:
`not_allowed`.**

H3 is empty in all three frozen windows. Winner capture and right-tail
retention values of zero are mechanical empty-cohort outputs, not evidence
that the hypothesis was tested and failed. There is no usable historical
sample and no production-design basis.

## H4 High-Position Crowding Risk

**Final status: `underpowered`. Production-design eligibility:
`not_allowed`.**

H4 is empty in all three windows. False-warning rate, loser contamination,
severe-drawdown incidence, and excess-return behavior therefore cannot be
evaluated. The absence of warnings must not be read as good warning quality.
No risk-annotation design is authorized.

## H5 False-Breakout Risk

**Final status: `underpowered`. Production-design eligibility:
`allowed_for_research_display_only`.**

| Window | Valid n | False-warning rate | Loser contamination | Severe drawdown | Mean excess | Median excess |
|---|---:|---:|---:|---:|---:|---:|
| 2026-01-30 | 9 | 33.33% | 22.22% | 0.00% | +7.01% | +7.55% |
| 2026-03-31 | 9 | 33.33% | 44.44% | 22.22% | +0.47% | -7.93% |
| 2026-04-30 | 13 | 15.38% | 30.77% | 53.85% | -11.58% | -12.09% |

H5 shows some descriptive warning behavior, especially the lower April
false-warning rate alongside higher drawdown incidence. The pattern is not
stable across windows, however, and all three samples are below the frozen
gate. It can remain visible as a non-blocking research annotation only. It
cannot authorize risk-annotation production design.

## Final Decision Ledger

| Hypothesis | Final status | Production-design eligibility | Decision |
|---|---|---|---|
| H1 | `underpowered` | `not_allowed` | No adequately powered window. |
| H2 | `mixed_research_only` | `allowed_for_research_display_only` | One powered window; negative excess-return evidence and cross-window inconsistency. |
| H3 | `underpowered` | `not_allowed` | Empty in all windows. |
| H4 | `underpowered` | `not_allowed` | Empty in all windows; warning usefulness untested. |
| H5 | `underpowered` | `allowed_for_research_display_only` | Descriptive risk behavior only; all windows below gate. |

No cohort receives `supported_research_only`. No cohort is eligible for
production-design review. The outcome is closure of this historical
research-only line, not parameter tuning or a search for replacement
windows.

## Explicit Non-Changes

Phase 3.14 did not:

- regenerate or mutate frozen cohort membership;
- change H1-H5 parameters or choose replacement parameters;
- create or preregister additional historical windows;
- use U1/U2 as sealed proof;
- execute or alter the prospective U3 runbook or dates;
- change production scoring, factor weights, ranking, candidate selection,
  list logic, thresholds, recommendations, API, or UI;
- access a provider or prewarm cache;
- create walk-forward predictions for the historical windows.

## Next Phase

Phase 3.15 should close H1-H5 as research-only evidence, retain the generated
artifacts and caveats for audit, and leave U3 sealed for its future execution
dates. It must not reinterpret this outcome as authorization to tune the
cohorts or implement production behavior.
