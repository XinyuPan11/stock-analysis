# Phase 2.13B Answer-Key Case Study Learning

## Framing

This phase is answer-key post-mortem learning using already revealed 2024
outcomes. It is in-sample diagnosis, not blind validation, and it is not
evidence of production improvement.

No production scoring, ranking, factor, validation-label, candidate-selection,
or recommendation logic is changed.

## Overfitting Guardrails

- The 2024 answer key may only support diagnosis, mistake review, and research
  hypothesis generation.
- It can explain observed errors, but it cannot validate an improvement.
- Candidate-bucket ideas must be stated as general hypotheses and must be
  tested on unseen windows after they are frozen.
- The same 2024 answer-key cases must not be used to claim improved
  performance.
- Do not hard-code the 2024 winners or tune thresholds to reproduce them.
- The next phase may design generalizable feature-gap or candidate-bucket
  hypotheses; it must not directly add known winners to candidate lists.

## Filled Input

The primary input is:

```text
research/case_studies/case_study_filled_2024.csv
```

It contains 30 researched cases:

- 20 winners
- 10 losers
- four controlled 2024 as-of dates
- company, catalyst, archetype, risk, confidence, and research-note fields

Archetype values are semicolon-separated and are summarized as individual
pattern tokens.

## Membership Alignment

The helper matches each case by `symbol + as_of_date + horizon_days` to:

```text
outputs/validation/walk_forward_predictions_<date>_20d.csv
outputs/lists/<list_id>_<date>.json
```

The first complete alignment found:

```text
prediction matches: 30/30
winners captured by positive lists: 6/20
winners missed: 14/20
losers incorrectly captured by positive lists: 1/10
losers captured by high_risk_active: 1/10
winners captured by high_risk_active: 0/20
```

The report and enriched CSV include:

- `captured_by_system`
- `captured_lists`
- `captured_positive_lists`
- `captured_risk_lists`
- `missed_winner`
- `polluted_positive_list_loser`
- `winner_in_high_risk_active`
- `membership_notes`
- prediction return cross-check fields

The filled source file is read-only.

## Answer-Key Diagnosis

The first diagnosis emphasizes under-capture:

- Fourteen of twenty winners were absent from positive lists.
- Only one loser entered a positive list, so broad loser pollution is not the
  main explanation.
- `high_risk_active` captured no winners, so the risk bucket does not explain
  the missed winner population in this sample.
- Missed winners must be studied by their theme, event, low-position reversal,
  right-tail, recovery, and repricing archetypes.

The generated report includes:

- winner and loser archetype-token distributions
- winner catalyst-flag counts
- loser risk-pattern counts
- captured-winner archetypes
- missed-winner archetypes
- the share of missed winners carrying theme, event, reversal, or right-tail
  flags

These are same-period answer-key findings and require separate unseen-window
testing.

The following bucket names are diagnostic research hypotheses only. They are
not new production lists and are not validated model improvements.

## Candidate-Bucket Research Hypotheses

### `stable_trend_candidates`

- Motivation: separate repeatable trend structure from event-driven cases.
- Current support: momentum, trend, relative strength, volatility, drawdown.
- Risks: exhaustion, crowding, volatility expansion.
- Posture: high-confidence only after unseen-window validation.

### `low_position_revaluation_candidates`

- Motivation: study low-position repricing outside mature trend leadership.
- Current support: long-horizon drawdown, moving-average position, relative-strength inflection.
- Missing: historical valuation context.
- Posture: watch-only.

### `turnaround_watch`

- Motivation: isolate turnaround, industry recovery, and cyclical repricing.
- Current support: price reversal, volume, relative strength.
- Missing: financial, industry-cycle, and announcement confirmation.
- Posture: watch-only.

### `theme_acceleration_watch`

- Motivation: represent catalyst acceleration without calling it stable trend.
- Current support: momentum, volume, volatility.
- Missing: news, announcements, policy and theme classification.
- Posture: watch-only.

### `right_tail_opportunity_watch`

- Motivation: preserve asymmetric high-volatility cases in a separate bucket.
- Current support: volatility, momentum, drawdown, right-tail validation metrics.
- Missing: catalyst confirmation.
- Posture: watch-only.

### `high_position_crowding_risk`

- Motivation: distinguish high-position reversal risk from generic volatility.
- Current support: long-horizon momentum, moving-average distance, volatility, drawdown.
- Missing: crowding and theme-persistence data.
- Posture: risk-warning only.

### `negative_event_or_delisting_risk`

- Motivation: isolate event and status hazards from positive candidate logic.
- Current support: current risk labels, price and drawdown deterioration.
- Missing: historical ST/listing status, announcements, transaction lifecycle, fundamentals.
- Posture: risk-warning only.

## Hypothesis Evaluation Plan

### A. Existing price, factor, and list outputs

- Prototype research-only stable-trend, low-position, volatility, drawdown, and crowding diagnostics.
- Keep stable, turnaround, and right-tail observations separate.
- Preserve `high_risk_active` as a risk-warning bucket.

### B. Durable member-level factor snapshots

- Persist point-in-time bucket features, thresholds, membership reasons, and exclusions.
- Track moving-average position, distance from highs, factor exposure, and overlap.

### C. News, announcement, theme, and fundamental data

- Event revaluation, restructuring, policy catalysts, transaction outcomes, and delisting evidence.
- Industry-cycle confirmation, theme fade, and fundamental deterioration.

### D. Unseen-window validation

- Freeze hypotheses before selecting thresholds.
- Test each general hypothesis against unchanged baseline logic on separate,
  unseen dates.
- Defer every production-ranking or candidate-promotion change.
- Never reuse these 2024 answer-key cases as proof of improvement.

## Commands

Dry-run:

```powershell
python backend\scripts\summarize_answer_key_case_study_learning.py --case-study-file research\case_studies\case_study_filled_2024.csv --outputs-dir outputs
```

Write reports and the enriched membership CSV:

```powershell
python backend\scripts\summarize_answer_key_case_study_learning.py --case-study-file research\case_studies\case_study_filled_2024.csv --outputs-dir outputs --write-output
```

## Outputs

```text
outputs/experiments/answer_key_case_study_learning_2024.json
outputs/experiments/answer_key_case_study_learning_2024.md
research/case_studies/case_study_filled_2024_with_membership.csv
```

## Interpretation Boundary

Membership matching can identify captured winners, missed winners, and losers
present in positive lists. Manual case research supplies diagnostic catalyst
and archetype explanations, but the resulting ideas remain research
hypotheses. They must be tested on unseen windows and cannot be used to claim
production improvement from the same 2024 answer key.
