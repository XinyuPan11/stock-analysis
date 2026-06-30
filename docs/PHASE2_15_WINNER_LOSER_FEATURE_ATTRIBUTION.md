# Phase 2.15 Winner / Loser Feature Attribution

## Goal

Phase 2.15 describes how existing as-of features differ across winner, loser,
captured, missed, and high-risk cohorts. It reads the Phase 2.14 snapshot only.

This is an in-sample 2024 answer-key post-mortem. It is not blind validation
and is not evidence of production improvement.

## Boundaries

The attribution:

- does not access BaoStock or raw cache
- does not recompute labels or factors
- does not run workflow or validation
- does not alter scoring, ranking, candidate selection, or recommendations
- does not create production lists
- does not fit thresholds to 2024 outcomes

Any later hypothesis must be specified before testing and evaluated on unseen
windows.

## Input

```text
outputs/experiments/member_level_asof_snapshot_2024.csv
```

The script requires non-empty `as_of_date` and `horizon_days` values. If the
window identity is missing, regenerate the Phase 2.14 snapshot before running
attribution.

## Group Construction

The default tail fraction is 10%, with a minimum of 10 rows per label and
window. Tails are selected independently inside every as-of/horizon window.
These are predeclared descriptive cohorts, not production thresholds.

Groups:

- top `future_return` winners
- top `future_excess_return` winners
- union of the two winner tails
- winner union captured by existing positive lists
- winner union missed by existing positive lists
- bottom `future_return` losers
- bottom `future_excess_return` losers
- union of the two loser tails
- loser union captured by existing positive lists
- existing `high_risk_active` members
- the disjoint non-high-risk complement

Positive-list capture is determined only from
`captured_positive_lists`. No list is rebuilt.

## Feature Summaries

Each group reports:

- valid and missing counts
- mean and median
- 25th and 75th percentiles
- minimum and maximum
- average and median future outcomes for descriptive context

The report compares:

- winner union versus loser union
- captured versus missed winners
- positive-list losers versus all losers
- high-risk versus non-high-risk rows

Features include the Phase 2.14 technical fields and existing score/factor
columns where available.

## Pattern Views

### Low-position reversal

Described using pre-60D return, 60D drawdown, distances to the 60D high/low,
and recent acceleration.

### Trend acceleration

Described using pre-5D and pre-20D returns, recent acceleration, momentum
score, and trend score.

### Volume and amount expansion

Described using amount/volume change and existing average amount/volume.

### Right-tail volatility

Described using existing and cache-derived 20D volatility, pre-5D return, and
recent acceleration.

### High-position crowding / false breakout

Described using the crowding proxy, distance to the 60D high, pre-20D return,
volatility, and 60D drawdown.

All pattern outputs are median differences and sample counts. They do not
establish causality or a candidate rule.

## External-Data Gaps

The snapshot cannot attribute:

- theme or policy catalysts
- restructuring or control-change events
- fundamental changes
- industry or sector effects
- historical listing, ST, or suspension status where snapshots are missing

Price/volume behavior may describe a response but cannot identify its cause.

## Commands

Dry-run:

```powershell
python backend\scripts\summarize_winner_loser_feature_attribution.py --snapshot-file outputs\experiments\member_level_asof_snapshot_2024.csv --outputs-dir outputs
```

Write reports:

```powershell
python backend\scripts\summarize_winner_loser_feature_attribution.py --snapshot-file outputs\experiments\member_level_asof_snapshot_2024.csv --outputs-dir outputs --tail-fraction 0.10 --min-group-size 10 --write-output
```

The tail options support sensitivity review. Changing them does not create a
production threshold and must not be optimized against the same 2024 labels.

## Outputs

```text
outputs/experiments/winner_loser_feature_attribution_2024.json
outputs/experiments/winner_loser_feature_attribution_2024.md
```

## Current 2024 Descriptive Run

Using the predeclared 10% within-window tails:

- winner union: 134 rows
- winner rows captured by positive lists: 37
- winner rows missed by positive lists: 97
- loser union: 134 rows
- loser rows captured by positive lists: 29
- `high_risk_active`: 84 rows

Captured winners had stronger median existing total-score and pre-60D trend
context than missed winners. The broad winner tail did not show stronger
pre-5D return, amount expansion, volume expansion, or volatility than the
loser tail. This supports the descriptive hypothesis that current lists favor
established score/trend profiles while many right-tail outcomes have weaker
observable pre-move signatures.

`high_risk_active` retained negative mean future excess return relative to the
disjoint non-high-risk cohort. This remains a risk-warning diagnostic, not a
production rule.

These are in-sample observations and cannot validate a model change.

## Interpretation Checklist

Before describing a feature difference:

1. Check valid counts and missing rates.
2. Compare medians as well as means.
3. Check whether the sign is consistent across relevant cohorts.
4. Keep list-membership overlap visible.
5. Do not infer a catalyst from a price/volume proxy.
6. Treat the 2024 findings as hypothesis generation only.
7. Freeze any proposed hypothesis before unseen-window validation.

## Phase 2.14 Identifier Repair

During implementation, the generated Phase 2.14 CSV was found to have blank
`as_of_date` values because point-in-time diagnostics introduced a duplicate
date column during merge. The snapshot builder now keeps the identity
`as_of_date` and excludes the duplicate diagnostic field. A regression test
asserts the as-of date and horizon on generated rows.

This repair changes snapshot identity metadata only. It does not change any
feature, factor, score, label, or validation calculation.
