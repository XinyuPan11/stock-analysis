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

## Status Values

- `ready`: cache coverage and validation quality gates pass, and required
  validation/experiment outputs exist.
- `blocked_missing_as_of_outputs`: as-of labels/factors/lists are missing.
- `deferred`: the future window crosses 2025.
- `missing_cache`: symbols file is missing or cache coverage is below the
  configured threshold.
- `missing_experiment_outputs`: cache is sufficient, but validation or
  experiment outputs are missing.
- `low_quality`: validation outputs exist but valid prediction count or valid
  prediction ratio is below configured thresholds.

## 2024-10-31 20d Example

```powershell
python backend\scripts\check_validation_window_readiness.py --as-of-date 2024-10-31 --horizon-days 20 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 300 --benchmark CSI300 --write-output
```

Expected current interpretation: likely `blocked_missing_as_of_outputs` until
the user manually generates the 2024-10-31 as-of labels, factors, and lists.
