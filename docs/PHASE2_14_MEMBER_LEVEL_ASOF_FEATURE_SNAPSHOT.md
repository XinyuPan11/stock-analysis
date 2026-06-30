# Phase 2.14 Member-Level As-Of Feature Snapshot

## Goal

Phase 2.14 materializes one research row per symbol and controlled validation
window. It brings existing factors, scores, list memberships, local-cache
technical features, and explicit future labels into one attribution dataset.

This is research infrastructure, not a production model change.

## Overfitting Boundary

Phase 2.13B used known 2024 outcomes as an answer-key post-mortem. Phase 2.14
does not convert those cases into thresholds or new candidate rules.

Guardrails:

- feature definitions do not use future returns
- technical inputs are sliced to `trade_date <= as_of_date`
- future labels are copied only after as-of feature materialization
- no labels are recomputed
- no production score, rank, list, or recommendation logic changes
- any later hypothesis must be frozen and tested on unseen windows

## Inputs

For each controlled window the builder reads:

```text
outputs/validation/walk_forward_predictions_<as_of_date>_<horizon>d.csv
outputs/daily/factors_<as_of_date>.csv
outputs/labels/stock_labels_<as_of_date>.csv
outputs/lists/<list_id>_<as_of_date>.json
data/cache/daily-use/baostock/stock_daily/adjusted/<symbol>.csv
```

All access is local and read-only. The builder does not instantiate a provider,
prewarm cache, run validation, or run the research workflow.

## Field Boundary

### Identity and quality

- `as_of_date`
- `horizon_days`
- `symbol`
- `data_quality`

### Point-in-time diagnostics

- `latest_input_date`
- `max_raw_cache_date`
- `future_rows_excluded_count`
- `leakage_guard_applied`
- `missing_feature_flags`

For every row with local technical features:

```text
latest_input_date <= as_of_date
```

### Existing as-of fields

The snapshot copies existing momentum, relative-strength, trend, volatility,
drawdown, amount, volume, score, rank, risk, and liquidity fields without
changing their calculations.

### List membership

The snapshot records:

- captured positive and risk-list IDs
- high-confidence membership
- trend-leader membership
- long-term-stable membership
- breakout membership
- accumulation membership
- rebound membership
- high-risk-active membership

A missing list file produces an explicit missing flag. It is not interpreted as
non-membership.

### New research-only technical fields

These fields are calculated only from local daily rows on or before the as-of
date:

- `pre_5d_return`
- `pre_20d_return`
- `pre_60d_return`
- `technical_volatility_20d`
- `drawdown_60d`
- `amount_change_20d`
- `volume_change_20d`
- `distance_to_60d_high`
- `distance_to_60d_low`
- `recent_acceleration_proxy`
- `high_position_crowding_proxy`

The amount and volume change fields compare the latest five observations with
the preceding fifteen observations. The acceleration proxy compares recent
five-session return pace with 20-session pace. The crowding proxy is a
continuous interaction of 60-session price position, positive 20-session
return, and 20-session volatility. None is a production factor or threshold.

### Explicit future labels

These fields come only from existing walk-forward prediction files:

- `future_return`
- `benchmark_return`
- `future_excess_return`
- `outperformed_benchmark`
- `future_top_quantile`
- `max_drawdown_during_holding`
- `benchmark_data_quality`

They are evaluation labels, never feature inputs.

## Unavailable Fields

Current local data cannot reliably provide:

- theme or policy catalyst identity
- restructuring or control-change events
- fundamental improvement or deterioration
- industry or sector attribution
- historical listing, ST, and suspension status where snapshots do not exist

The builder reports these limitations and does not synthesize them from price
movement.

## Commands

Dry-run the default 2024 four-window panel:

```powershell
python backend\scripts\build_member_level_asof_snapshot.py --outputs-dir outputs --cache-dir data\cache\daily-use --provider baostock
```

Write the snapshot:

```powershell
python backend\scripts\build_member_level_asof_snapshot.py --outputs-dir outputs --cache-dir data\cache\daily-use --provider baostock --write-output
```

Run one controlled window:

```powershell
python backend\scripts\build_member_level_asof_snapshot.py --outputs-dir outputs --cache-dir data\cache\daily-use --provider baostock --windows 2024-10-31:20 --write-output
```

## Outputs

```text
outputs/experiments/member_level_asof_snapshot_2024.csv
outputs/experiments/member_level_asof_snapshot_2024.json
outputs/experiments/member_level_asof_snapshot_2024.md
```

The JSON records the schema categories and guardrails as well as row records.
The Markdown report summarizes coverage and feature/label boundaries.

## Interpretation

The snapshot supports member-level attribution such as checking whether missed
cases shared low-position reversal, participation expansion, acceleration,
right-tail behavior, or crowding-risk characteristics. It does not establish
that any characteristic improves the model.

A later phase may define a frozen research hypothesis and evaluate it on unseen
windows. Production candidate construction remains unchanged.
