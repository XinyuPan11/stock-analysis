# Phase 2.13A Risk Bucket Stabilization and Disjoint Cohort Attribution

## Goal

Evaluate whether the existing `high_risk_active` bucket is useful as a stable
risk warning by comparing it with a genuinely disjoint reference cohort.

This phase is read-only. It does not access BaoStock, fetch cache data,
recompute validation labels, or modify scoring, ranking, factors, validation
math, or production recommendations.

## Data Availability

Disjoint attribution is available now.

For each 2024 controlled window, the project has:

```text
outputs/validation/walk_forward_predictions_<date>_20d.csv
outputs/lists/high_risk_active_<date>.json
```

The membership files contain explicit symbols. The tool constructs:

- `high_risk_active`: valid prediction symbols present in the list.
- `non_high_risk_disjoint`: every other valid evaluated symbol.

It verifies that overlap is zero and that the two cohorts partition all valid
prediction symbols.

## Metrics

For each cohort and window:

- sample count
- average future and excess return
- win and benchmark-outperform rates
- average holding-period drawdown
- failure rates below -10% and -20%
- bottom-five average return
- bottom-decile loss concentration

Across windows:

- minimum and median sample count
- average metrics
- negative and positive excess-window counts
- sign consistency
- classification

Classification is `stable_negative_risk_bucket` only when the high-risk cohort
has sufficient samples, is negative in at least 75% of windows, has negative
mean excess return, and underperforms the disjoint reference cohort.

## Overlap Awareness

Other research lists may overlap with `high_risk_active`. The report includes
their overlap counts when individual list membership files are available.
These lists remain descriptive and are not treated as independent cohorts.

## Commands

Dry-run:

```powershell
python backend\scripts\summarize_risk_bucket_attribution.py --outputs-dir outputs --windows 2024-01-31:20,2024-04-30:20,2024-07-31:20,2024-10-31:20 --min-bucket-sample 5 --negative-window-ratio 0.75
```

Write reports:

```powershell
python backend\scripts\summarize_risk_bucket_attribution.py --outputs-dir outputs --windows 2024-01-31:20,2024-04-30:20,2024-07-31:20,2024-10-31:20 --min-bucket-sample 5 --negative-window-ratio 0.75 --write-output
```

## Outputs

```text
outputs/experiments/risk_bucket_disjoint_attribution_2024.json
outputs/experiments/risk_bucket_disjoint_attribution_2024.md
```

## Interpretation Boundary

A stable negative result supports further use of `high_risk_active` in risk
warning and candidate-downgrade analysis. It does not establish a production
action rule and does not justify changing scoring weights from this four-window
panel.

Remaining limitations:

- Only four controlled 2024 windows are included.
- Historical universe and status metadata remain current-snapshot limited.
- The high-risk cohort is small in some windows.
- Broader out-of-sample dates are still required before production changes.
