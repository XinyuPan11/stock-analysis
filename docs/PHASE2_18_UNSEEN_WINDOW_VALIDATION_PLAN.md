# Phase 2.18 Unseen Window Validation Plan

## Purpose

Phase 2.18 defines how the Phase 2.17 hypotheses may be tested without reusing
their development evidence. It is a research-only pre-registration plan. It
does not execute validation or implement any candidate-list hypothesis.

No outcome from a proposed unseen window was inspected while writing this
plan.

## In-Sample Evidence Boundary

The following four 20D windows were used repeatedly for diagnosis,
answer-key learning, feature attribution, and hypothesis design:

```text
2024-01-31
2024-04-30
2024-07-31
2024-10-31
```

They are permanently forbidden as proof for Phase 2.17 hypotheses. They may
remain regression fixtures for pipeline integrity, but any result from them
must be labeled `development_only`.

The 30 filled case-study rows are also in-sample evidence. They may explain
errors but cannot validate a redesign.

## Frozen Hypothesis Registry

This registry must be committed before any unseen outcome is generated or
opened.

### Existing-list baselines

| ID | Frozen research interpretation | Expected evaluation |
|---|---|---|
| B1 | `high_confidence_candidates` is a relatively clean established-score/trend baseline with limited coverage | Cleanliness versus winner coverage |
| B2 | `long_term_stable` is a stability baseline, not a broad 20D winner catcher | Downside and excess-return stability versus limited coverage |
| B3 | `trend_leaders` is a useful established-trend baseline with crowding sensitivity | Winner retention versus crowded-loser exposure |
| B4 | `breakout_watch` is a high-variance observation list | Winner reach, loser pollution, drawdown, and failure variance |
| B5 | `accumulation_watch` is a broad staging/observation list | Winner reach versus contamination and persistence |
| B6 | `rebound_watch` remains observation-only because evidence is insufficient | Sample accumulation before interpretation |
| R0 | `high_risk_active` is a negative-risk warning baseline | Stability of negative excess return and loser concentration |

These are descriptions of unchanged lists. No production list is renamed or
rebuilt.

### Existing-data hypotheses

| ID | Frozen hypothesis | Expected direction |
|---|---|---|
| H1 | `low_position_revaluation_watch` | Capture some previously missed winners without disproportionate loser contamination |
| H2 | `trend_acceleration_with_crowding_guard` | Retain established trend winners while warning on crowded losers |
| H3 | `right_tail_opportunity_watch` | Describe asymmetric outcomes as observation-only; never qualify as high confidence |
| H4 | `high_position_crowding_risk` | Enrich for loser-prone high-position names while reporting warned winners |
| H5 | `false_breakout_risk` | Explain part of `breakout_watch` and `accumulation_watch` pollution without erasing their winner tail |

Phase 2.18 freezes direction and evaluation semantics, not numeric cutoffs.
Any future research-only feature definition, interaction, quantile, or missing
data rule must be versioned and committed before U1 outcomes are produced.

### External-data-required hypotheses

| ID | Frozen status | Testability |
|---|---|---|
| H6 | `theme_event_gap_watch` | Not testable until point-in-time theme/event data and provenance exist |
| H7 | `negative_event_or_status_risk` | Not testable until historical status/event data exist |

H6 and H7 must remain documented gaps. Price movement must not be used to
manufacture their causal labels.

## Proposed Candidate Window Pool

Dates below are proposed candidates, not final selections. Each date requires
a trading-calendar check, as-of-output check, cache check, and leakage check.
No result file should be opened during readiness review.

### Stage A: near-term 2024 pool

Candidate month-end gaps between the diagnostic anchors:

```text
2024-02-29 20D
2024-05-31 20D
2024-08-30 20D
2024-11-29 20D
```

`2024-08-30` is proposed because 2024-08-31 is not a trading day. Every date
remains subject to the repository's as-of convention and latest-trading-date
diagnostics.

The November candidate may be deferred by the legacy 2024 planner if its
buffered cache target crosses the year boundary. A deferred result is a stop
condition, not permission to bypass the planner. An earlier November trading
date may be proposed in a new plan revision before outcomes are inspected.

### Stage A split

After readiness checks, pre-register two disjoint sets without reading labels:

- **U1 evaluation set:** two ready dates selected from the pool.
- **U2 sealed confirmation set:** the remaining ready dates.

Selection should balance calendar spacing and data coverage, not expected
performance. Record the chosen dates and Git commit before running U1.

Once U1 is opened, it is no longer unseen. If a hypothesis is revised, the
revision receives a new version and may only be assessed on unopened U2 or a
later holdout.

### Stage B: later 2025 candidate pool

Only after the Stage A process is stable, consider readiness-gated quarterly
or month-end candidates such as:

```text
2025-03-31 20D
2025-06-30 20D
2025-09-30 20D
2025-12-31 20D
```

These are proposed conventions, not approved execution dates. The repository
currently lacks prepared historical as-of labels/factors/lists for many later
dates, and the older planner may report 2025 boundaries as deferred. Do not
interpret that legacy status as a model result.

A 2025 date is eligible only after:

- a hard cache-only as-of research path is confirmed
- point-in-time labels, factors, and lists exist
- the 20D future window is covered locally
- leakage and bias metadata pass
- no provider access is required

### Stage C: optional 2026

Do not select 2026 dates now. Keep 2026 as an optional later confirmation
pool only after 2025 definitions and operating procedures are stable. Any
candidate must leave enough locally cached future observations for the chosen
horizon.

## Readiness Checklist

Complete this checklist without reading future-return values, list
performance, factor effectiveness, or winner/loser outcomes.

### 1. Pre-registration

- Phase 2.17 hypothesis IDs and Phase 2.18 plan are committed.
- Any experimental annotation schema has a version and immutable definition.
- Feature direction, missing-data handling, and cohort semantics are recorded.
- U1 and U2 dates are recorded before validation output is generated.
- Forbidden development windows are excluded.
- The operator records a Git commit hash and planned commands.

### 2. As-of output presence

For each candidate `<date>`, require:

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

If these outputs are missing, mark the candidate
`blocked_missing_as_of_outputs`. Do not run the provider-capable daily
research CLI as part of Phase 2.18.

### 3. Cache and symbol plan

- The generated symbols file exists and is non-empty.
- Cache coverage checks use the actual symbols file.
- Coverage reaches the planner's buffered target end.
- Benchmark cache quality is ready.
- No prewarm or provider call is started by Codex.
- Missing cache is a stop condition for this phase.

### 4. Point-in-time integrity

Before outcome interpretation, require:

```text
latest_input_date <= as_of_date
leakage_guard_applied = true
no_future_leakage = true
price_point_in_time_guard_applied = true
feature_input_point_in_time_status = guarded
future_label_window_status = explicit_future_only
```

Also retain:

```text
universe_point_in_time_status = current_snapshot_limited
listing_status_point_in_time_status = current_snapshot_limited
st_status_point_in_time_status = current_snapshot_limited
suspension_status_point_in_time_status = current_snapshot_limited
```

A missing or contradictory field blocks interpretation.

### 5. Quality readiness

Use the existing split terminology:

- `execution_status = executable_ready`
- `comparison_eligible = true` only when the pre-registered minimum valid count
  is met
- `high_quality_ready = true` only when count and coverage gates both pass
- low-coverage but sample-sufficient windows remain explicitly exploratory
- insufficient-valid-count windows are excluded from aggregate claims

The default existing gates are:

```text
min_valid_count = 50
min_coverage_rate = 0.70
```

These are inherited readiness gates, not hypothesis-performance thresholds.

## Required Output Contract

### Before validation

- frozen hypothesis/experiment card
- selected U1/U2 date manifest
- as-of labels, factors, and list files
- non-empty symbols file
- cache-coverage report
- readiness JSON

### Core validation output

For each `<date>` and 20D horizon:

```text
outputs/validation/walk_forward_summary_<date>_20d.json
outputs/validation/walk_forward_predictions_<date>_20d.csv
outputs/validation/list_performance_<date>_20d.json
outputs/validation/factor_effectiveness_<date>_20d.json
outputs/validation/walk_forward_report_<date>_20d.md
outputs/portfolios/portfolio_summary_<date>_20d.json
```

### Research attribution output

A later implementation must use versioned names that do not overwrite the
2024 development snapshot:

```text
outputs/experiments/member_level_asof_snapshot_<panel_id>.csv
outputs/experiments/hypothesis_validation_<hypothesis_version>_<panel_id>.json
outputs/experiments/hypothesis_validation_<hypothesis_version>_<panel_id>.md
```

No current Phase 2.14/2.15 summarizer should be reused if it silently assumes
the four development windows or fixed `2024` output names.

## Common Metrics

Report every metric by window before pooling:

- source symbol count
- prediction count and valid count
- valid coverage ratio
- missing-price and insufficient-future-window counts
- winner-tail capture rate
- loser-tail contamination rate
- captured-vs-missed winner feature gaps
- average and median future return
- average and median excess return
- benchmark outperform rate
- holding-period drawdown
- severe-failure rates
- list overlap and membership depth
- high-risk overlap
- missing-feature rates

Pooled averages without window-level results are insufficient.

## Baseline List Metrics

### `high_confidence_candidates`

Measure cleanliness and coverage together:

- winner-tail capture
- loser-tail contamination
- average/median excess return
- benchmark outperform rate
- drawdown and high-risk overlap

A cleaner but nearly empty list is not automatically successful.

### `long_term_stable`

Measure:

- downside stability
- drawdown
- excess-return sign consistency
- winner coverage
- sample adequacy

Do not infer long-term fundamental quality from a 20D price label.

### `trend_leaders`

Measure:

- trend-winner retention
- crowded-loser incidence
- sensitivity to volatility, amount expansion, distance to high, and crowding
- right-tail preservation

### `breakout_watch` and `accumulation_watch`

Treat both as high-variance observation lists. Measure:

- winner reach
- loser contamination
- variance across windows
- severe downside
- payoff ratio
- right-tail preservation
- list overlap and persistence where available

### `high_risk_active`

Measure negative-bucket stability:

- mean and median excess return
- negative-excess window count
- loser-tail concentration
- severe-failure capture
- incorrectly warned winner count

Do not judge it by positive candidate capture.

## Hypothesis-Specific Checks

### H1 `low_position_revaluation_watch`

Primary question: does a frozen low-position/reversal annotation improve
missed-winner coverage without excessive loser contamination?

Required checks:

- incremental winner-tail capture beyond existing lists
- loser contamination and high-risk overlap
- drawdown and severe-failure rates
- feature availability and sample count
- per-window sign consistency

Failure includes higher capture accompanied by disproportionate downside or
results concentrated in one window.

### H2 `trend_acceleration_with_crowding_guard`

Primary question: can a frozen annotation retain established trend winners
while identifying crowded losers?

Required checks:

- retained `trend_leaders` winner count
- warned loser count
- incorrectly warned winner count
- excess return and drawdown of retained versus warned cohorts
- crowding-feature coverage
- right-tail preservation

A result that removes most trend winners is a failure even if average loss
falls.

### H3 `right_tail_opportunity_watch`

This remains observation-only and must never be promoted to high confidence
from this test.

Required checks:

- sample count
- top-tail return and payoff ratio
- failure below severe-loss boundaries
- drawdown
- right-tail preservation
- stability across windows

A few extreme winners with unstable or tiny samples are inconclusive.

### H4 `high_position_crowding_risk`

Primary question: does the frozen warning enrich for loser-prone
high-position names?

Required checks:

- loser-tail warning rate
- incorrectly warned winner rate
- excess-return gap between warned and un-warned cohorts
- drawdown and severe failures
- coverage across lists and windows

### H5 `false_breakout_risk`

Primary question: does the frozen warning explain
`breakout_watch`/`accumulation_watch` pollution?

Required checks:

- warned loser count within each source list
- warned winner count within each source list
- retained winner-tail capture
- retained right-tail return
- drawdown and failure reduction
- sample sufficiency by list

### H6 `theme_event_gap_watch`

Status: not testable without point-in-time theme/event inputs.

Do not use price behavior as a substitute label. Continue reporting the gap
until external data, taxonomy, timing, and provenance are frozen.

### H7 `negative_event_or_status_risk`

Status: not testable without historical point-in-time status/event inputs.

Do not backfill historical ST/listing/suspension state from a current snapshot.

## Interpretation Rules

Classify each hypothesis/window as:

- `directionally_supported`
- `mixed_or_regime_dependent`
- `not_supported`
- `insufficient_data`
- `not_testable_missing_external_data`

Do not define numeric success thresholds after seeing outcomes. Before U1,
each experiment card must state any minimum sample, acceptable contamination,
retention, and failure guardrails.

A hypothesis is not supported merely because:

- one pooled mean improves
- one window performs well
- a small cohort contains an extreme winner
- a warning removes losses while also destroying the winner tail
- a list becomes cleaner only by becoming nearly empty

Contradictory windows must remain in the report.

## Sequential Holdout Rules

1. U1 is opened only after definitions and dates are committed.
2. U1 outcomes may support, reject, or leave a hypothesis inconclusive.
3. Do not tune a threshold after U1 and still call U1 validation.
4. Thresholds must not be tuned after seeing unseen results.
5. A revision after U1 creates a new hypothesis version.
6. The revised version may only use unopened U2 or a later holdout.
7. Once U2 is opened, it cannot be reused for another revision.
8. 2025 dates remain reserved until the Stage A process is reviewed.
9. Failed hypotheses are reported; they are not silently renamed or removed.

Maintain a ledger:

| Hypothesis version | Definition commit | Windows opened | Result | Revision |
|---|---|---|---|---|
| pending | pending | none | not run | none |

## Future Manual Commands

The following commands are templates only. These commands were not executed in Phase 2.18.

### A. Presence-only prerequisite check

Replace the candidate dates only after recording U1/U2:

```powershell
$dates = @("2024-02-29", "2024-05-31", "2024-08-30", "2024-11-29")
foreach ($date in $dates) {
    [pscustomobject]@{
        as_of_date = $date
        stock_labels_json = Test-Path "outputs\labels\stock_labels_$date.json"
        stock_labels_csv = Test-Path "outputs\labels\stock_labels_$date.csv"
        factors = Test-Path "outputs\daily\factors_$date.csv"
        high_confidence = Test-Path "outputs\lists\high_confidence_candidates_$date.json"
        trend_leaders = Test-Path "outputs\lists\trend_leaders_$date.json"
        long_term_stable = Test-Path "outputs\lists\long_term_stable_$date.json"
        breakout_watch = Test-Path "outputs\lists\breakout_watch_$date.json"
        accumulation_watch = Test-Path "outputs\lists\accumulation_watch_$date.json"
        rebound_watch = Test-Path "outputs\lists\rebound_watch_$date.json"
        high_risk_active = Test-Path "outputs\lists\high_risk_active_$date.json"
        multi_lists = Test-Path "outputs\lists\multi_lists_$date.json"
    }
}
```

This checks presence only and does not open outcome files.

### B. Generate readiness plan

Future/manual; does not access a provider:

```powershell
python backend\scripts\generate_multi_asof_validation_plan.py --outputs-dir outputs --cache-dir data\cache\daily-use --provider baostock --benchmark CSI300 --as-of-dates 2024-02-29,2024-05-31,2024-08-30,2024-11-29 --horizons 20 --recommended-limit 300
```

The command refreshes the ignored multi-as-of plan files. Review only
readiness, missing-file, date-boundary, symbols-file, and cache-coverage
fields. Do not open experiment outcomes.

### C. Readiness checks

Future/manual and local-only:

```powershell
$dates = @("2024-02-29", "2024-05-31", "2024-08-30", "2024-11-29")
foreach ($date in $dates) {
    python backend\scripts\check_validation_window_readiness.py --as-of-date $date --horizon-days 20 --outputs-dir outputs --cache-dir data\cache\daily-use --provider baostock --limit 300 --benchmark CSI300 --min-valid-count 50 --min-coverage-rate 0.7 --write-output
}
```

Stop on missing as-of outputs, missing symbols file, missing cache, deferred
boundary, or unknown point-in-time status. Do not follow a suggested prewarm
command in this phase.

### D. Controlled validation dry-run

Run only after the experiment definition and U1 dates are committed:

```powershell
$u1Dates = @("<pre-registered-U1-date-1>", "<pre-registered-U1-date-2>")
foreach ($date in $u1Dates) {
    python backend\scripts\run_controlled_validation_batch.py --as-of-date $date --horizon-days 20 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 300
}
```

Dry-run first. If it reports a blocker, stop without changing the hypothesis.

### E. Write U1 outputs

Future/manual, after dry-run approval:

```powershell
foreach ($date in $u1Dates) {
    python backend\scripts\run_controlled_validation_batch.py --as-of-date $date --horizon-days 20 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 300 --write-output
}
```

Once written outcomes are inspected, both U1 windows are consumed.

## Stop Conditions

Stop without broadening scope when:

- a candidate is one of the four forbidden development windows
- the date was previously opened for hypothesis evaluation
- the as-of date is not supported by the trading-calendar convention
- required labels, factors, or lists are missing
- the symbols file is missing or empty
- cache coverage is incomplete
- a provider call would be required
- benchmark quality is not ready
- point-in-time or leakage metadata is missing or false
- valid count is below the pre-registered minimum
- feature coverage is insufficient
- historical status bias is hidden
- someone proposes changing a threshold after seeing U1

A blocked window is an infrastructure result, not a model failure.

## Phase 2.18 Decision

Phase 2.18 freezes the validation process, candidate pool, hypothesis
directions, metrics, and sequential holdout rules. It authorizes no validation
run and no production change.

Production scoring, ranking, factor calculations, validation math, candidate
selection, list construction, thresholds, and recommendation behavior remain
unchanged.
