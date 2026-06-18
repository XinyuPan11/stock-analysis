# Phase 2.8.1 Controlled 2024 Forward Expansion Plan

## Goal

Phase 2.8.1 prepares a controlled forward-data expansion from the fixed historical research baseline:

```text
as-of date: 2024-01-31
forward window: 2024-02-01 to 2024-12-31
```

This phase does not generate a latest-date research view. It prepares scripts, checks, and manual command templates so later validation can test whether the existing 2024-01-31 research lists remain useful over later 2024 windows.

## Boundary

No future leakage.

- Signals, labels, lists, rankings, and portfolios remain fixed as of `2024-01-31`.
- Forward price data is used only for validation labels and review metrics.
- The project remains price-only / technical-only in this phase.
- This phase does not rerun scoring, factors, list generation, full workflow, or full-market backtest.
- Codex should not run long provider jobs in this phase.

## Why 2024 First

2024 is the next controlled step after the fixed historical benchmark. It is close enough to the existing cached baseline to validate the mechanics, but still far enough forward to expose stability issues in list membership, factor scores, and simulated portfolio reviews.

Running directly against the latest available dates would mix two concerns: forward-validation mechanics and current-date refresh operations. Phase 2.8.1 keeps those concerns separate.

## Batch Plan

The expansion is split into three manual batches:

```text
Batch 1: 2024-02-01 to 2024-05-31
Batch 2: 2024-06-01 to 2024-08-31
Batch 3: 2024-09-01 to 2024-12-31
```

Each batch should be expanded by limit ladder:

```text
limit 50 -> limit 300 -> limit 1000 -> full market later
```

Do not start with full market.

## Scripts Added

```text
backend/scripts/generate_forward_expansion_plan.py
backend/scripts/check_cache_coverage.py
backend/scripts/run_controlled_validation_batch.py
```

The scripts are designed to be safe by default:

- `generate_forward_expansion_plan.py` writes plan files only.
- `check_cache_coverage.py` reads local cache files only.
- `run_controlled_validation_batch.py` defaults to dry-run and does not refresh validation outputs unless `--write-output` is passed.

## Outputs

Plan generation writes:

```text
outputs/expansion/forward_expansion_plan_2024.json
outputs/expansion/forward_expansion_plan_2024.md
```

These files are planning artifacts only. They do not mean 2024 data has been fully prepared.

## Success Criteria

For each batch and limit step:

- cache coverage check completes locally;
- missing symbols are explainable;
- controlled validation default dry-run reports usable walk-forward future labels;
- controlled validation default dry-run reports usable portfolio benchmark and future labels;
- formal outputs are refreshed only when the user intentionally passes `--write-output`;
- no full-market workflow runs during this preparation phase.

## When to Enter 2025

Move to 2025 only after:

- Batch 1/2/3 are reviewed at small scale;
- larger 2024 validation runs are manually completed and documented;
- missing cache and data-quality issues are understood;
- the 2024 review does not reveal blocking design issues.
