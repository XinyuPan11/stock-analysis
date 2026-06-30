# Phase 2.16 Captured-vs-Missed Winner Deep Dive

## Goal

Phase 2.16 explains how captured winner-tail rows differ from missed
winner-tail rows, and how positive-list winners differ from positive-list
losers.

It reads existing Phase 2.14/2.15 outputs only. It does not rebuild lists,
recompute labels, or access providers.

## Answer-Key Boundary

This is an in-sample 2024 answer-key post-mortem. It is not blind validation
and is not evidence of production improvement.

The report:

- reuses the frozen Phase 2.15 tail fraction and minimum group size
- describes existing memberships
- does not select or tune thresholds
- does not alter production scoring, ranking, factors, labels, candidate
  selection, lists, or recommendations
- requires unseen-window testing for any later frozen hypothesis

## Inputs

```text
outputs/experiments/member_level_asof_snapshot_2024.csv
outputs/experiments/winner_loser_feature_attribution_2024.json
outputs/experiments/winner_loser_feature_attribution_2024.md
research/case_studies/case_study_filled_2024_with_membership.csv
```

The filled case study is optional supplemental evidence. It is not used to
construct the full-snapshot winner and loser cohorts.

## Cohorts

The report reuses Phase 2.15 within-window tails:

- captured winners: winner-union rows with existing positive-list membership
- missed winners: winner-union rows without positive-list membership
- positive-list winners: same disjoint captured-winner cohort
- positive-list losers: loser-union rows with positive-list membership

No symbol is added to a cohort based on a manually researched archetype.

## Captured-vs-Missed Features

The comparison reports valid counts, means, medians, quartiles, and
captured-minus-missed deltas for:

- existing total, momentum, trend, relative-strength, risk, and liquidity
  scores
- pre-20D and pre-60D returns
- existing and local-cache 20D volatility
- 60D drawdown
- amount and volume change
- distance to the 60D high and low
- recent acceleration
- high-position crowding proxy

Missing values remain missing and are counted by cohort.

## Positive-List Winners-vs-Losers

The report retains the same feature comparisons for positive-list winner and
loser tails. It is designed to answer descriptive questions such as:

- whether loser-tail members were more volatile
- whether they were closer to a high or more crowded
- whether their trend context was weaker
- whether drawdown and acceleration differed

These differences are diagnostics, not exclusion rules.

## List-Specific Attribution

For each existing positive list:

- total member count
- winner-tail count
- loser-tail count
- share of the full winner tail captured
- share of the full loser tail captured
- loser share among that list's winner/loser tail members
- winner-vs-loser feature medians and valid counts

Lists covered:

- `high_confidence_candidates`
- `trend_leaders`
- `long_term_stable`
- `breakout_watch`
- `accumulation_watch`
- `rebound_watch`

List combinations and membership depth are reported separately so overlapping
lists are not mistaken for independent observations.

## Missing Features And External Gaps

`missing_feature_flags` are counted separately for captured winners, missed
winners, and positive-list losers.

The full snapshot still cannot identify:

- theme or policy catalysts
- restructuring or control-change events
- fundamental changes
- industry or sector effects
- missing historical listing, ST, or suspension states

The filled case-study archetypes may illustrate these gaps for matched cases,
but cannot label unmatched rows.

## Commands

Dry-run:

```powershell
python backend\scripts\summarize_captured_missed_winner_deep_dive.py --snapshot-file outputs\experiments\member_level_asof_snapshot_2024.csv --attribution-file outputs\experiments\winner_loser_feature_attribution_2024.json --case-study-file research\case_studies\case_study_filled_2024_with_membership.csv --outputs-dir outputs
```

Write reports:

```powershell
python backend\scripts\summarize_captured_missed_winner_deep_dive.py --snapshot-file outputs\experiments\member_level_asof_snapshot_2024.csv --attribution-file outputs\experiments\winner_loser_feature_attribution_2024.json --case-study-file research\case_studies\case_study_filled_2024_with_membership.csv --outputs-dir outputs --write-output
```

## Outputs

```text
outputs/experiments/captured_vs_missed_winner_deep_dive_2024.json
outputs/experiments/captured_vs_missed_winner_deep_dive_2024.md
```

## Current 2024 Descriptive Run

The frozen Phase 2.15 tail settings produced:

- 134 winner-tail rows
- 37 captured winners
- 97 missed winners
- 29 positive-list loser-tail rows

Captured winners had substantially higher existing total score, trend score,
pre-20D return, and pre-60D return than missed winners. Current positive lists
therefore primarily capture a narrower, more established score/trend subset of
the full winner tail.

Within positive lists, loser-tail rows were more volatile, had deeper 60D
drawdowns, stronger prior 20D/60D returns, greater amount expansion, and a
higher crowding proxy than winner-tail rows. This is consistent with a
false-breakout or mature-crowding research hypothesis, but does not define an
exclusion threshold.

List-specific winner/loser tail counts were:

| List | Winner tail | Loser tail | Loser share of winner/loser tails |
|---|---:|---:|---:|
| high_confidence_candidates | 11 | 3 | 21.4% |
| trend_leaders | 15 | 6 | 28.6% |
| long_term_stable | 9 | 1 | 10.0% |
| breakout_watch | 14 | 14 | 50.0% |
| accumulation_watch | 16 | 14 | 46.7% |
| rebound_watch | 0 | 2 | 100.0% |

The rebound result has only two tail observations and must not be generalized.
The 30 filled case-study rows aligned completely; missed winner archetypes
remained concentrated in theme/policy, right-tail volatility, low-position
reversal, and event revaluation. Those causal fields remain unavailable for
the full snapshot.

## Interpretation Checklist

1. Read sample counts before feature deltas.
2. Keep list overlap and membership depth visible.
3. Compare captured and missed winners separately from winner/loser quality.
4. Treat missing features as missing, not neutral.
5. Do not infer unavailable catalysts from price behavior.
6. Do not turn same-period median differences into thresholds.
7. Freeze any future hypothesis before unseen-window validation.
