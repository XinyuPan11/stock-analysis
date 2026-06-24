# Phase 2.8.6 Validation Readiness Checker

Phase 2.8.6 adds a lightweight read-only checker for one controlled
as-of/horizon validation window.

It does not access BaoStock, prewarm cache, run daily research, run validation,
run a full workflow, enter 2025, or change production scoring.

## Command

```powershell
python backend\scripts\check_validation_window_readiness.py --as-of-date 2024-07-31 --horizon-days 60 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 300 --benchmark CSI300 --write-output
```

The checker prints JSON and, with `--write-output`, writes:

```text
outputs/experiments/window_readiness_<as_of_date>_<horizon>d.json
```

## Status Model

Phase 2.8.6.1 separates execution readiness from validation quality so summary
and checker use the same terminology.

`execution_status` values:

- `blocked_missing_as_of_outputs`: as-of labels/factors/lists are missing.
- `deferred`: the future window crosses 2025.
- `missing_symbols_file`: the required cache-plan symbols file is missing.
- `missing_cache`: symbols file exists, but cache coverage is below threshold.
- `missing_experiment_outputs`: cache is sufficient, but validation or experiment outputs are missing.
- `executable_ready`: required files exist and the window can be reviewed.

`quality_status` values:

- `high_quality`: valid prediction count and valid ratio meet thresholds.
- `low_coverage`: valid prediction count is sufficient, but valid ratio is below threshold.
- `insufficient_valid_count`: valid prediction count is below threshold.
- `missing_validation_outputs`: walk-forward prediction output is missing.
- `unknown`: execution is blocked before quality can be measured.

The checker also reports:

- `comparison_eligible`: true only when `valid_prediction_count >= min_valid_count`.
- `high_quality_ready`: true only when `comparison_eligible` is true and valid ratio is at least `min_coverage_rate`.

The legacy `status` field remains for compatibility. It maps high-quality
executable windows to `ready`, low-coverage or insufficient executable windows
to `low_quality`, and blocked/deferred windows to their execution status.

Default quality thresholds:

```text
min_valid_count = 50
min_coverage_rate = 0.7
```

Example interpretation for `2024-07-31 60d` with `55/300` valid predictions:

```text
execution_status = executable_ready
quality_status = low_coverage
comparison_eligible = true
high_quality_ready = false
```

## 2024-10-31 20d Example

```powershell
python backend\scripts\check_validation_window_readiness.py --as-of-date 2024-10-31 --horizon-days 20 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 300 --benchmark CSI300 --write-output
```

Expected current interpretation: likely `blocked_missing_as_of_outputs` until
the user manually generates the 2024-10-31 as-of labels, factors, and lists.
