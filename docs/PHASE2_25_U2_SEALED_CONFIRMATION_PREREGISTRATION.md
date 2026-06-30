# Phase 2.25 U2 Sealed Confirmation Preregistration

## Purpose

Phase 2.25 freezes the proposed U2 confirmation windows, evaluation questions,
interpretation rules, and operating guardrails before any U2 result is
generated or inspected.

This is a preregistration document only. It does not authorize validation,
provider access, threshold tuning, or production changes.

## Evidence Boundary

### Permanently forbidden answer-key windows

The following development and answer-key windows remain permanently forbidden
as proof:

```text
2024-01-31 20D
2024-04-30 20D
2024-07-31 20D
2024-10-31 20D
```

They may be used only as pipeline regression fixtures with an explicit
`development_only` label.

### Consumed U1 windows

The following windows have been opened and analyzed. They are consumed U1
evidence and cannot be reused as sealed confirmation:

```text
2024-02-29 20D
2024-05-31 20D
2024-08-30 20D
2024-11-29 20D
```

No revised hypothesis, threshold, cohort definition, or list interpretation
may use these windows as new unseen evidence.

## Proposed Sealed U2 Windows

The proposed U2 candidate manifest is:

```text
2025-02-28 20D
2025-05-30 20D
2025-08-29 20D
2025-11-28 20D
```

These dates are preregistered candidates, not executed or technically approved
windows. Each date remains sealed until a later readiness-only review verifies
the trading-date convention, local cache coverage, historical as-of outputs,
benchmark coverage, and point-in-time metadata without inspecting outcomes.

The dates were chosen because they:

- move confirmation outside the heavily used 2024 evidence set;
- provide approximately quarterly spacing across 2025;
- use late-month business-day candidates rather than selecting dates from
  observed market performance;
- preserve one common 20D horizon for comparison with U1;
- leave multiple regimes available without choosing windows by expected
  outcome quality.

Calendar spacing is a design reason, not evidence that a date is technically
ready. A readiness blocker must be recorded rather than bypassed.

## Sealed-State Rules

A proposed U2 window remains sealed only while:

- no walk-forward prediction, list-performance, factor-effectiveness,
  portfolio-performance, or hypothesis-result output has been opened;
- no future-return value or winner/loser classification has been inspected;
- date selection has not been changed in response to expected or observed
  performance;
- any generated as-of files are reviewed only for presence, cache provenance,
  point-in-time metadata, and provider-access status;
- the exact validation command, limit, horizon, benchmark, and interpretation
  rules remain frozen.

If outcome-bearing files already exist unexpectedly, stop and classify that
window as potentially consumed. Do not overwrite or silently reuse it.

## U1 Findings To Confirm Or Challenge

U2 tests the following unchanged research interpretations.

| ID | Frozen U1 interpretation | U2 confirmation question |
|---|---|---|
| R0 | `high_risk_active` was the strongest negative warning, with small samples | Does the bucket remain negative or risk-isolating in adequately populated U2 windows? |
| B2 | `long_term_stable` was directionally defensive while excess return remained mixed | Does it continue to limit drawdown relative to the more active observation lists? |
| B1 | `high_confidence_candidates` was selective but its cleanliness and coverage were unstable | Do both cleanliness and usable coverage become consistent, or does instability persist? |
| B3 | `trend_leaders` weakened as a stable positive baseline | Does U2 provide broad, repeated contrary evidence, or confirm regime sensitivity? |
| B4 | `breakout_watch` remained a high-variance observation list | Do variance, drawdown, and weak-window behavior remain material? |
| B5 | `accumulation_watch` remained a broad, high-variance observation list | Does winner reach continue to arrive with weak outperform consistency or downside? |
| F0 | `total_score` had a negative spread in three of four U1 windows | Does U2 show strong, repeated opposite evidence, or confirm ranking instability? |

U2 does not begin with a presumption that U1 was correct. Contradictory
windows must remain visible.

## Hypotheses Not Yet Eligible For U2 Evaluation

H1-H5 were not directly evaluated in U1:

```text
H1 low_position_revaluation_watch
H2 trend_acceleration_with_crowding_guard
H3 right_tail_opportunity_watch
H4 high_position_crowding_risk
H5 false_breakout_risk
```

They may be evaluated in U2 only if, before any U2 outcome is opened:

1. feature names and formulas are versioned;
2. point-in-time inputs and missing-data behavior are frozen;
3. member-level cohort construction is implemented and tested;
4. sample and interpretation rules are committed;
5. output names cannot overwrite U1 or development artifacts.

If that work is not completed first, H1-H5 must remain
`insufficient_data_not_evaluated`. Existing list or factor results cannot act
as substitute tests.

H6 `theme_event_gap_watch` and H7 `negative_event_or_status_risk` remain
`not_testable_missing_external_data`. Price movement must not be used to
manufacture theme, event, fundamental, or historical status labels.

## Readiness Contract

Readiness is infrastructure verification, not validation. For every proposed
U2 date, require all of the following before a dry-run:

### Date and sealed-state checks

- the date matches the preregistered manifest;
- the date is a supported trading-date/as-of convention;
- it is neither a forbidden answer-key window nor a consumed U1 window;
- no outcome-bearing validation file already exists;
- any replacement date was committed before its results were inspected.

### Historical as-of artifacts

Require:

```text
outputs/labels/stock_labels_<date>.json
outputs/labels/stock_labels_<date>.csv
outputs/daily/factors_<date>.csv
outputs/lists/high_confidence_candidates_<date>.json
outputs/lists/trend_leaders_<date>.json
outputs/lists/long_term_stable_<date>.json
outputs/lists/breakout_watch_<date>.json
outputs/lists/accumulation_watch_<date>.json
outputs/lists/rebound_watch_<date>.json
outputs/lists/high_risk_active_<date>.json
outputs/lists/multi_lists_<date>.json
```

Missing files produce `blocked_missing_as_of_outputs`. Generate them only
through the fail-closed cache-only path.

### Cache and benchmark checks

- the as-of symbol set is non-empty;
- selected stock cache covers the feature lookback through `as_of_date`;
- stock cache covers the explicit 20D future-label window;
- CSI300 benchmark aliases provide continuous verified coverage through the
  required future end;
- coverage metadata and actual CSV dates agree;
- no provider fetch is required;
- `provider_access = false`.

The target future end must come from the existing
`recommended_target_end_date()` logic. Do not replace it with a raw
calendar-day assumption.

### Point-in-time and bias checks

Require:

```text
latest_input_date <= as_of_date
leakage_guard_applied = true
no_future_leakage = true
price_point_in_time_guard_applied = true
feature_input_point_in_time_status = guarded
future_label_window_status = explicit_future_only
```

Retain the known limitations:

```text
universe_point_in_time_status = current_snapshot_limited
listing_status_point_in_time_status = current_snapshot_limited
st_status_point_in_time_status = current_snapshot_limited
suspension_status_point_in_time_status = current_snapshot_limited
```

### Current tooling limitation

The current U1 readiness checker is fixed to the four 2024 U1 dates. The
general validation readiness path still uses the legacy
`MULTI_ASOF_YEAR = 2024` policy and will defer 2025 windows.

Therefore Phase 2.25 does not authorize running a readiness command yet. A
later, small readiness-only phase must add explicit support for this frozen
U2 manifest without reading outcome fields. That implementation must preserve
provider isolation and reject both the forbidden and consumed windows.

## Frozen Metrics

Report every metric by window before any cross-window aggregate.

### Technical quality

- `status`
- `symbol_count`
- `prediction_count`
- `valid_future_count`
- valid coverage ratio
- `missing_price_count`
- `insufficient_future_window_count`
- benchmark data quality
- latest feature input date
- excluded future-row count
- leakage and bias metadata

### Existing lists

For every list:

- item count and valid count
- average and median future return
- average and median excess return
- win rate and benchmark outperform rate
- average holding-period drawdown
- best/worst-case concentration when already available
- excess-return sign by window

Additional interpretation:

- `high_confidence_candidates`: cleanliness and coverage must be shown
  together; a tiny clean cohort is not confirmation.
- `long_term_stable`: compare drawdown with `trend_leaders`,
  `breakout_watch`, and `accumulation_watch`; excess return remains secondary
  to the defensive question.
- `trend_leaders`: report coverage, excess-return sign, outperform rate, and
  drawdown. Do not attribute a result to crowding unless the frozen member-level
  crowding cohort exists.
- `breakout_watch` and `accumulation_watch`: report sign variance, outperform
  rate, drawdown, severe downside, and right-tail concentration where already
  available.
- `high_risk_active`: report non-empty windows, total member-window count,
  excess-return sign, outperform rate, drawdown, and incorrectly warned
  winners only if a preregistered winner-tail definition exists.

### Factors

For:

```text
total_score
risk_score
volatility
liquidity_score
amount
volume
momentum_score
trend_score
relative_strength_score
drawdown
```

report:

- correlation with future return;
- top-quantile average return;
- bottom-quantile average return;
- top-minus-bottom spread;
- top-quantile benchmark outperform rate;
- sign consistency across U2 windows.

### Portfolio view

Use existing simulated portfolio outputs only:

- holding and valid counts;
- average and median future/excess return;
- benchmark outperform rate;
- average holding-period drawdown;
- net average return under the existing cost assumption;
- empty or undersized portfolio notes.

Turnover remains unvalidated until multiple rebalance dates are modeled.

## Frozen Interpretation Rules

These are evaluation rules, not production thresholds.

### Cross-window classification

- `directionally_confirmed`: the expected direction appears in at least three
  of four eligible windows, sample prerequisites are met, and no pooled mean
  is used to hide a contradictory window.
- `mixed_or_regime_dependent`: the expected direction appears in two of four
  windows, or material contradictions remain.
- `weakened_or_rejected`: the opposite direction appears in at least three of
  four eligible windows.
- `insufficient_data`: fewer than three windows are evaluable, required
  cohorts are absent, or sample size is too small for the stated question.
- `not_testable_missing_external_data`: required historical external inputs
  do not exist.

No classification may be redefined after U2 results are opened.

### R0 `high_risk_active`

Directionally confirm the warning only if:

- at least three U2 windows are non-empty;
- at least 30 total member-window observations are available;
- average excess return is negative in at least three eligible windows;
- downside/drawdown remains worse than the relevant non-high-risk comparison
  when a disjoint comparison is available.

Otherwise classify it as mixed, weakened, or insufficient according to the
frozen rules. Do not judge this warning by positive candidate capture.

### B2 `long_term_stable`

Directionally confirm defensive behavior if its average holding drawdown is
shallower than `trend_leaders`, `breakout_watch`, and
`accumulation_watch` in at least three eligible windows. Excess return may
remain mixed; positive excess alone does not prove defensive quality.

### B1 `high_confidence_candidates`

Do not consider promotion unless:

- average excess return is positive in at least three eligible windows;
- benchmark outperform rate exceeds 50% in at least three eligible windows;
- valid membership does not collapse below ten in any eligible window;
- valid future coverage remains complete for the selected members.

Failure of the coverage condition cannot be offset by a favorable pooled
return.

### B3 `trend_leaders`

Treat it as a stable positive baseline only if average excess return is
positive and benchmark outperform rate exceeds 50% in at least three eligible
windows, with no severe drawdown deterioration. Otherwise retain the
regime-dependent interpretation.

### B4/B5 `breakout_watch` and `accumulation_watch`

The U1 observation-list interpretation is confirmed when excess-return signs
remain mixed or negative and weak windows retain elevated drawdown or
concentrated failures. If either list is positive in at least three windows
with controlled drawdown and adequate coverage, U2 contradicts U1; it still
does not authorize production promotion.

### F0 `total_score`

Strong opposite evidence requires:

- positive correlation with future return in at least three eligible windows;
- positive top-minus-bottom spread in at least three eligible windows;
- no severe contrary window hidden by the aggregate.

Even that result would trigger a later design review, not automatic
reweighting. Mixed or negative signs preserve the current no-change decision.

## Readiness Failure And Replacement Rules

If a proposed U2 window fails readiness:

1. record the exact infrastructure blocker;
2. do not inspect any outcome-bearing file;
3. do not replace the window based on expected or observed outcome quality;
4. attempt only a scope-approved infrastructure repair;
5. if replacement is necessary, define and commit the replacement date before
   generating or opening its results;
6. retain the failed date and reason in the U2 ledger.

A replacement date should preserve the 20D horizon and calendar spacing where
possible. Convenience, market direction, and expected model performance are
not valid selection reasons.

## Sequential Holdout Guardrails

- U2 may confirm, weaken, reject, or leave a frozen interpretation
  inconclusive.
- U2 results cannot be used for repeated threshold tuning.
- A hypothesis revised after U2 receives a new version.
- A revised post-U2 hypothesis requires a later unopened holdout.
- U1 and U2 cannot be pooled and then relabeled as unseen confirmation.
- Failed hypotheses remain visible; they are not silently renamed.
- H1-H5 cannot be retrofitted after U2 outcomes are opened.
- H6-H7 remain documented gaps until point-in-time external data exists.

## What Remains Research-Only

All Phase 2.25 interpretations remain research-only:

- list posture and stability claims;
- factor sign and spread diagnostics;
- simulated portfolio comparisons;
- high-risk warning analysis;
- any future H1-H5 cohort;
- any U2-supported hypothesis.

No U2 result directly changes production scoring, ranking, factors, candidate
selection, list membership, thresholds, or recommendation behavior.

## Requirements Before Any Production Change

At minimum, a later decision would require:

1. U2 confirmation under the frozen protocol;
2. adequate samples and multiple market regimes;
3. point-in-time-safe member-level cohort definitions where applicable;
4. unchanged results on a later holdout for any post-U2 revision;
5. explicit review of current-snapshot universe/status bias;
6. turnover, cost, drawdown, severe-failure, and right-tail trade-offs;
7. a separate implementation phase with regression tests and rollback;
8. no reuse of U1 or U2 as proof after tuning.

Passing U2 alone is not production approval.

## Future Manual Commands

The following commands are templates for later manual execution. They were not
run in Phase 2.25.

### 1. Generate cache-only as-of daily outputs

Run one date at a time only after the preregistration commit is preserved:

```powershell
$u2Dates = @(
    "2025-02-28",
    "2025-05-30",
    "2025-08-29",
    "2025-11-28"
)

foreach ($date in $u2Dates) {
    python backend\scripts\generate_cache_only_asof_daily_outputs.py `
        --date $date `
        --outputs-dir outputs `
        --cache-dir data\cache\daily-use `
        --provider baostock `
        --benchmark CSI300 `
        --limit 300 `
        --top-n 20

    if ($LASTEXITCODE -ne 0) {
        throw "Cache-only as-of generation blocked for $date"
    }
}
```

This path must remain fail-closed. If cache is missing, record the blocker; do
not substitute a provider-capable workflow.

### 2. Generate local research views

Only after each daily summary confirms:

```text
provider_access = false
cache_only = true
latest_input_date <= as_of_date
point_in_time_guard_applied = true
```

run:

```powershell
foreach ($date in $u2Dates) {
    python backend\scripts\generate_research_views.py `
        --date $date `
        --outputs-dir outputs `
        --cache-dir data\cache\daily-use `
        --top-n 30

    if ($LASTEXITCODE -ne 0) {
        throw "Research-view generation blocked for $date"
    }
}
```

### 3. Run the future U2-aware readiness check

Do not run this command until the legacy 2024-only readiness policy has been
updated and targeted tests confirm support for the frozen U2 manifest:

```powershell
foreach ($date in $u2Dates) {
    python backend\scripts\check_validation_window_readiness.py `
        --as-of-date $date `
        --horizon-days 20 `
        --outputs-dir outputs `
        --cache-dir data\cache\daily-use `
        --provider baostock `
        --benchmark CSI300 `
        --limit 300 `
        --min-valid-count 50 `
        --min-coverage-rate 0.7 `
        --write-output

    if ($LASTEXITCODE -ne 0) {
        throw "U2 readiness check failed for $date"
    }
}
```

Under the current code this command is not U2-ready because the underlying
planner defers 2025. The command is frozen here for later use after a
readiness-only compatibility patch; it was not executed.

### 4. Controlled validation dry-run

Only windows that pass the future U2-aware readiness check may proceed:

```powershell
foreach ($date in $u2Dates) {
    python backend\scripts\run_controlled_validation_batch.py `
        --as-of-date $date `
        --horizon-days 20 `
        --benchmark CSI300 `
        --outputs-dir outputs `
        --cache-dir data\cache\daily-use `
        --limit 300

    if ($LASTEXITCODE -ne 0) {
        throw "Controlled validation dry-run blocked for $date"
    }
}
```

Do not inspect performance while deciding whether another date should replace
a blocked window.

### 5. Controlled validation write-output

Run only after every intended window has passed dry-run and opening U2 has
been explicitly approved:

```powershell
foreach ($date in $u2Dates) {
    python backend\scripts\run_controlled_validation_batch.py `
        --as-of-date $date `
        --horizon-days 20 `
        --benchmark CSI300 `
        --outputs-dir outputs `
        --cache-dir data\cache\daily-use `
        --limit 300 `
        --write-output

    if ($LASTEXITCODE -ne 0) {
        throw "Controlled validation write-output failed for $date"
    }
}
```

Once an outcome is opened, that window is consumed.

## U2 Ledger

Complete this ledger without removing blocked or contradictory rows:

| Candidate | Preregistration status | Readiness status | Opened | Result classification | Blocker/revision |
|---|---|---|---|---|---|
| 2025-02-28 20D | proposed_sealed | not_run | no | sealed | none |
| 2025-05-30 20D | proposed_sealed | not_run | no | sealed | none |
| 2025-08-29 20D | proposed_sealed | not_run | no | sealed | none |
| 2025-11-28 20D | proposed_sealed | not_run | no | sealed | none |

## Phase 2.25 Decision

The four 2025 dates are preregistered candidate windows. No U2 readiness
result, validation output, list performance, factor effectiveness,
winner/loser metric, hypothesis outcome, or future return was inspected.

The next permissible work is a small U2 readiness compatibility phase. It may
extend the existing fail-closed readiness path to the frozen 2025 manifest,
but it must not generate or inspect validation outcomes.
