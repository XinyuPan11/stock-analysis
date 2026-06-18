# Phase 2.8.1 Controlled 2024 Forward Expansion Run Guide

This guide is for controlled manual runs. Codex should prepare scripts, tests, and documentation; the user runs long provider/cache jobs manually.

## Do Not Run Long Jobs From Codex

Do not let Codex run full-year prewarm.
Do not let Codex run full-market workflow.
Do not let Codex run full-market backtest.
Do not enter 2025 from this phase.

## Generate The Plan

This command writes only plan files. It does not access BaoStock or any provider.

```powershell
python backend\scripts\generate_forward_expansion_plan.py --outputs-dir outputs --cache-dir data\cache\daily-use --recommended-limit 50
```

Expected outputs:

```text
outputs/expansion/forward_expansion_plan_2024.json
outputs/expansion/forward_expansion_plan_2024.md
```

## Batch 1: Small Cache Preparation

Manual provider/cache command for the user:

```powershell
python backend\scripts\prewarm_market_cache.py --provider baostock --start-date 2024-02-01 --end-date 2024-05-31 --cache-dir data\cache\daily-use --output-dir outputs\cache --limit 50 --batch-size 10 --sleep-seconds 0.5 --retry 1 --resume
```

After the manual cache job, inspect local coverage:

```powershell
python backend\scripts\check_cache_coverage.py --start-date 2024-02-01 --end-date 2024-05-31 --cache-dir data\cache\daily-use --limit 50 --output-file outputs\expansion\cache_coverage_2024-02-01_2024-05-31_limit50.json
```

Success criteria:

- `symbol_count=50`
- `covered_count` is meaningfully above zero
- `missing_symbols` are reviewable
- no provider access occurs during coverage check

## Batch 1: Walk-forward Validation

Dry-run first:

```powershell
python backend\scripts\run_walk_forward_validation.py --as-of-date 2024-01-31 --horizon-days 60 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 50 --dry-run
```

Write outputs only after the dry-run looks healthy:

```powershell
python backend\scripts\run_walk_forward_validation.py --as-of-date 2024-01-31 --horizon-days 60 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 50
```

Expected output files:

```text
outputs/validation/walk_forward_summary_2024-01-31_60d.json
outputs/validation/list_performance_2024-01-31_60d.json
outputs/validation/factor_effectiveness_2024-01-31_60d.json
outputs/validation/walk_forward_predictions_2024-01-31_60d.csv
outputs/validation/walk_forward_report_2024-01-31_60d.md
```

## Batch 1: Portfolio Validation

Dry-run first:

```powershell
python backend\scripts\run_portfolio_validation.py --as-of-date 2024-01-31 --horizon-days 60 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 50 --dry-run
```

Write outputs only after the dry-run looks healthy:

```powershell
python backend\scripts\run_portfolio_validation.py --as-of-date 2024-01-31 --horizon-days 60 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 50
```

## Controlled Batch Helper

The helper chains walk-forward and portfolio validation. It defaults to dry-run and does not access a provider.

```powershell
python backend\scripts\run_controlled_validation_batch.py --as-of-date 2024-01-31 --horizon-days 60 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 50
```

Use `--write-output` only when you intentionally want to refresh validation and portfolio files:

```powershell
python backend\scripts\run_controlled_validation_batch.py --as-of-date 2024-01-31 --horizon-days 60 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 50 --write-output
```

## Batch 2 And Batch 3 Templates

Batch 2 coverage:

```powershell
python backend\scripts\check_cache_coverage.py --start-date 2024-06-01 --end-date 2024-08-31 --cache-dir data\cache\daily-use --limit 50 --output-file outputs\expansion\cache_coverage_2024-06-01_2024-08-31_limit50.json
```

Batch 3 coverage:

```powershell
python backend\scripts\check_cache_coverage.py --start-date 2024-09-01 --end-date 2024-12-31 --cache-dir data\cache\daily-use --limit 50 --output-file outputs\expansion\cache_coverage_2024-09-01_2024-12-31_limit50.json
```

For each batch, move from `limit 50` to `limit 300` to `limit 1000` only after the previous step is reviewed.

## Result Usability Checklist

- `valid_future_count > 0`
- benchmark data quality is `ok`
- missing price count is understandable
- cache coverage gaps are documented
- outputs are generated only when a write command is intentionally used
- no latest-date refresh is mixed into this phase

