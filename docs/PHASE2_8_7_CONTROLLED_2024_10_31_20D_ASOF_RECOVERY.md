# Phase 2.8.7 Controlled 2024-10-31 20d As-of Recovery

## Branch

`phase2-8-7-controlled-2024-10-31-20d-asof-recovery`

## Exact Goal

Diagnose and recover the controlled validation path for exactly:

```text
as_of_date = 2024-10-31
horizon_days = 20
cache_dir = data/cache/daily-use
```

The diagnostic checks whether the window is blocked by missing as-of outputs,
missing cache/symbol plans, missing validation outputs, or low-quality future
labels. It is research-only and validation-only.

## Strict Non-goals

- Do not enter 2025.
- Do not run full-market workflow.
- Do not expand to 60d, 120d, or broader date ranges.
- Do not change production scoring, recommendation scoring, rankings, or factor weights.
- Do not write production recommendation outputs.
- Do not access BaoStock or any provider from the diagnostic command.
- Do not prewarm automatically.

## Local Diagnostic Command

Dry run, read-only:

```powershell
python backend\scripts\diagnose_2024_10_31_20d_asof_recovery.py --outputs-dir outputs --cache-dir data\cache\daily-use --limit 300
```

Optional diagnostic output write:

```powershell
python backend\scripts\diagnose_2024_10_31_20d_asof_recovery.py --outputs-dir outputs --cache-dir data\cache\daily-use --limit 300 --write-output
```

When `--write-output` is used, the diagnostic writes:

```text
outputs/experiments/asof_recovery_2024-10-31_20d.json
```

## Current Expected Root Cause

Current local review shows:

```text
status = blocked_missing_as_of_outputs
root_cause = missing_as_of_outputs
required_future_end_date = 2024-12-10
future_window_recoverable_with_late_2024_cache = true
as_of_result_recoverable_with_cache_through_late_2024_only = false
```

This means the future window itself stays inside late 2024, but cache alone
cannot recover the window until the 2024-10-31 as-of labels, factors, and lists
exist.

## Manual Recovery Sequence

Only the user should run long/provider-backed commands. A controlled manual
sequence is:

```powershell
python backend\scriptsun_daily_research.py --provider baostock --end-date 2024-10-31 --cache-dir data\cache\daily-use --output-dir outputs\daily --limit 300
```

```powershell
python backend\scripts\generate_research_views.py --date 2024-10-31 --outputs-dir outputs --cache-dir data\cache\daily-use
```

```powershell
python backend\scripts\generate_multi_asof_validation_plan.py --outputs-dir outputs --cache-dir data\cache\daily-use --as-of-dates 2024-10-31 --horizons 20 --recommended-limit 300
```

After as-of outputs and symbols/cache coverage are ready, run controlled
validation only for this window:

```powershell
python backend\scriptsun_controlled_validation_batch.py --as-of-date 2024-10-31 --horizon-days 20 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 300 --write-output
```

Then rerun the diagnostic:

```powershell
python backend\scripts\diagnose_2024_10_31_20d_asof_recovery.py --outputs-dir outputs --cache-dir data\cache\daily-use --limit 300 --write-output
```

## Expected Success Criteria

Check these fields:

```text
as_of_date = 2024-10-31
horizon_days = 20
required_future_end_date = 2024-12-10
future_window_recoverable_with_late_2024_cache = true
missing_as_of_outputs = {}
candidate_count > 0
valid_future_count >= 50, preferred
missing_price_count is reviewed
insufficient_future_window_count is reviewed
status = recovered_valid or recovered_low_quality / missing_validation_outputs with explicit reason
```

`recovered_low_quality` is not failure by itself; it means the diagnostic found
valid output but quality gates need review.

## Rollback And Safety Notes

- The diagnostic command is read-only unless `--write-output` is passed.
- The diagnostic never fetches provider data.
- Generated diagnostic output can be deleted safely:

```powershell
Remove-Item outputs\experimentssof_recovery_2024-10-31_20d.json
```

- Do not use this phase to tune scoring or filters.
- Do not use future return labels to generate as-of candidates.
