# Phase 2.12 Validation Quality Attribution

## Goal

Explain why controlled validation results differ across dates, lists, factors,
and risk profiles without changing or rerunning model logic.

The attribution tool is read-only. It consumes existing validation outputs,
does not access BaoStock, does not fetch cache data, and does not recompute
future-return labels.

## Supported Panel

The default panel is:

```text
2024-01-31 20D
2024-04-30 20D
2024-07-31 20D
2024-10-31 20D
```

## Inputs

For every window:

```text
outputs/validation/walk_forward_predictions_<date>_<horizon>d.csv
outputs/validation/list_performance_<date>_<horizon>d.json
outputs/validation/factor_effectiveness_<date>_<horizon>d.json
```

Existing labels are consumed as-is. The script does not recalculate returns,
benchmark excess, drawdown, rankings, factors, or labels.

## Attribution Available Now

List attribution:

- valid window and sample counts
- average future and excess returns
- win and benchmark-outperform rates
- average holding-period drawdown
- positive/negative excess-window counts
- cross-window sign consistency

Factor attribution:

- correlation mean and median
- top-minus-bottom spread mean, median, minimum, and maximum
- positive/negative spread-window counts
- correlation and spread sign consistency
- top-quantile return and outperform-rate averages

Risk and data-quality attribution:

- `high_risk_active` stability across windows
- descriptive comparison with other list summaries
- per-window prediction and valid-label counts
- data-quality status counts
- full-panel future return, excess return, and drawdown context

The other-list reference is not a disjoint non-high-risk cohort because list
memberships overlap.

## Unavailable Dimensions

- Historical point-in-time industry, sector, and market-cap fields are absent.
- Prediction CSVs do not contain member-level score/factor input columns.
- Existing factor-effectiveness top/bottom quantiles can be summarized, but
  new member-level score buckets are not reconstructed in this phase.
- A disjoint non-high-risk cohort is not defined by current list summaries.

These limitations are reported explicitly instead of inventing fields or
silently treating overlapping lists as independent samples.

## Commands

Dry-run:

```powershell
python backend\scripts\summarize_validation_quality_attribution.py --outputs-dir outputs --windows 2024-01-31:20,2024-04-30:20,2024-07-31:20,2024-10-31:20
```

Write the report:

```powershell
python backend\scripts\summarize_validation_quality_attribution.py --outputs-dir outputs --windows 2024-01-31:20,2024-04-30:20,2024-07-31:20,2024-10-31:20 --write-output
```

## Outputs

```text
outputs/experiments/validation_quality_attribution_2024.json
outputs/experiments/validation_quality_attribution_2024.md
```

## Interpretation

Use cross-window sign consistency and dispersion to distinguish stable risk
separation from regime-dependent behavior. A consistently negative
`high_risk_active` result may support the usefulness of that risk bucket, but
does not establish a production rule by itself.

Mixed factor spread or correlation signs indicate regime dependence or missing
attribution dimensions. They are not a reason to retune scoring from the same
four windows.

No production scoring, ranking, factor, validation-label, or recommendation
changes are recommended in Phase 2.12.
