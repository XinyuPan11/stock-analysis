# Phase 2.7.2 Walk-forward Validation Summary

## Status

Framework implemented; full validation not run by Codex.

## Implemented Files

- `backend/src/stock_analysis/validation/future_returns.py`
- `backend/src/stock_analysis/validation/list_performance.py`
- `backend/src/stock_analysis/validation/factor_effectiveness.py`
- `backend/src/stock_analysis/validation/walk_forward.py`
- `backend/scripts/run_walk_forward_validation.py`

## CLI Parameters

The new CLI is read-only by default:

```powershell
python backend\scripts\run_walk_forward_validation.py --as-of-date 2024-01-31 --horizon-days 20 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 50 --dry-run
```

Supported parameters:

- `--start-date`
- `--end-date`
- `--as-of-date`
- `--horizon-days`
- `--benchmark`
- `--outputs-dir`
- `--cache-dir`
- `--list-ids`
- `--limit`
- `--dry-run`
- `--write-output`

Dry-run is the default behavior. Output files are written only when `--write-output` is passed.

## Tests

New tests:

- `backend/tests/test_future_returns.py`
- `backend/tests/test_list_performance.py`
- `backend/tests/test_factor_effectiveness.py`
- `backend/tests/test_walk_forward_validation.py`

Covered behavior:

- Future return calculation.
- Benchmark excess return calculation.
- Insufficient future window.
- Missing single-stock price data.
- List average return and outperform rate.
- Empty list handling.
- Missing factor handling.
- Dry-run behavior.
- CLI short smoke without provider access.

## Short Smoke

The framework supports a small dry-run smoke on existing fixed historical outputs. It reads local outputs/cache only and does not trigger provider access, prewarm, daily workflow, or backtest.

Executed smoke:

```powershell
python backend\scripts\run_walk_forward_validation.py --as-of-date 2024-01-31 --horizon-days 20 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 50 --dry-run
```

Result:

- `status`: `dry_run`
- `symbol_count`: `50`
- `valid_future_count`: `0`
- `data_quality_counts`: `insufficient_future_window = 50`
- `list_count`: `7`
- `factor_count`: `10`

This is expected for the current fixed historical cache because it ends at the as-of date and does not contain post-2024-01-31 future windows.

## Remaining Limitations

- This is a single as-of-date framework in the first pass.
- Full validation across many as-of dates has not been run by Codex.
- Signal metrics are descriptive; they are not portfolio simulation results.
- No financial, valuation, industry, news, or announcement data is used.
- No complex ML training is included.

## Next Step

Run controlled Phase 2.7.2 smoke validation on fixed historical outputs, then decide whether Phase 2.7.3 should add simulated portfolio validation for selected lists.

## Controlled Real Validation Guide

Added a run guide for preparing future-window cache data and running controlled 20D / 60D validation:

- `PHASE2_7_2_REAL_VALIDATION_RUN_GUIDE.md`

Key boundaries:

- `2024-01-31` signals, rankings, labels, and lists remain fixed.
- Future price data is used only for validation labels and list/factor evaluation.
- 20D validation should prepare cache through at least `2024-03-15`.
- 60D validation should prepare cache through preferably `2024-05-31`.
- Validation remains dry-run/read-only by default.
