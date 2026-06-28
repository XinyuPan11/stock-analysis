# Phase 2.9 Raw Daily Cache Catch-up to Recent

## Goal

Build helper tooling and documentation for raw daily stock cache catch-up from late 2024 to the current controlled date.

```text
provider = baostock
start_date = 2024-12-11
end_date = 2026-06-24
cache_dir = data/cache/daily-use
cache_layout = data/cache/daily-use/baostock/stock_daily/adjusted
logs_dir = outputs/cache
```

This phase is raw data cache catch-up only. It does not run validation, recommendations, backtests, scoring changes, ranking changes, factor changes, or model-quality conclusions.

## Confirmed Manual Smoke

User-run smoke results already confirmed:

```text
offset 0 / limit 50: success
offset 50 / limit 200: completed with 11 symbol_timeout failures
retry-only for offset50 failed symbols: success
confirmed catch-up coverage from smoke: first 250 symbols successful
current failed count after retry: 0
```

Files were written under:

```text
data/cache/daily-use/baostock/stock_daily/adjusted
```

Progress logs and failed-symbol files are written under:

```text
outputs/cache
```

## Codex / User Contract

- Codex writes tools, tests, command plans, and docs.
- User manually runs long BaoStock prewarm/catch-up commands.
- User pastes summary JSON and short log tails back to Codex.
- Codex should not spend tokens watching long-running downloads.
- Do not run full workflow.
- Do not run walk-forward validation.
- Do not generate recommendations.
- Do not change production scoring, ranking, factor formulas, or validation math.

## Coverage Report

Read-only local cache coverage report:

```powershell
python backend
eg scripts? nope
```

Use this command:

```powershell
python backend\scripts\report_raw_cache_catchup.py --cache-dir data\cache\daily-use --provider baostock --target-end-date 2026-06-24 --output-file outputs\cache\raw_cache_catchup_coverage_2026-06-24.json
```

Optional expected-universe symbols file:

```powershell
python backend\scripts\report_raw_cache_catchup.py --cache-dir data\cache\daily-use --provider baostock --target-end-date 2026-06-24 --symbols-file outputs\cache_plans\some_symbol_universe.txt --output-file outputs\cache\raw_cache_catchup_coverage_2026-06-24.json
```

Important fields:

```text
total_stock_csv_files
complete_symbol_count
stale_incomplete_symbol_count
missing_symbol_count
symbols[].earliest_cached_date
symbols[].latest_cached_date
symbols[].reaches_target_end_date
```

## Chunk Plan Generation

Generate the next manual chunks after the confirmed first 250 symbols:

```powershell
python backend\scripts\generate_raw_cache_catchup_plan.py --provider baostock --start-date 2024-12-11 --end-date 2026-06-24 --cache-dir data\cache\daily-use --output-dir outputs\cache --chunk-size 500 --start-offset 250 --chunk-count 1 --write-output
```

Generate several planned commands without running them:

```powershell
python backend\scripts\generate_raw_cache_catchup_plan.py --provider baostock --start-date 2024-12-11 --end-date 2026-06-24 --cache-dir data\cache\daily-use --output-dir outputs\cache --chunk-size 500 --start-offset 250 --chunk-count 3 --write-output
```

Each generated chunk command includes:

```text
--resume
--retry
--max-errors
--symbol-timeout-seconds
--max-consecutive-symbol-timeouts
--failed-symbols-output
--progress-log
```

## Retry Plan

Generate a retry-only command from one failed-symbols CSV:

```powershell
python backend\scripts\generate_raw_cache_catchup_plan.py --provider baostock --start-date 2024-12-11 --end-date 2026-06-24 --cache-dir data\cache\daily-use --output-dir outputs\cache --failed-symbols-file outputs\cache\raw_catchup_2024-12-11_2026-06-24_offset250_limit500_failed.csv
```

Retry command defaults follow the successful manual retry pattern:

```text
--retry-only
--batch-size 1
--sleep-seconds 2.0
--retry 2
--symbol-timeout-seconds 40
--max-consecutive-symbol-timeouts 2
```

## Next Manual Command

Recommended next manual chunk after confirmed first 250 symbols:

```powershell
python backend\scripts\prewarm_market_cache.py --provider baostock --start-date 2024-12-11 --end-date 2026-06-24 --cache-dir data\cache\daily-use --output-dir outputs\cache --limit 500 --offset 250 --batch-size 5 --sleep-seconds 1.0 --retry 1 --resume --max-errors 50 --symbol-timeout-seconds 20 --max-consecutive-symbol-timeouts 3 --failed-symbols-output outputs\cache\raw_catchup_2024-12-11_2026-06-24_offset250_limit500_failed.csv --progress-log outputs\cache\raw_catchup_2024-12-11_2026-06-24_offset250_limit500_progress.jsonl
```

If failures remain, generate or run the retry-only command for that chunk before moving to the next large chunk.


## Coverage Metadata Consistency Repair

Confirmed root cause:

```text
coverage metadata covered_end = 2026-06-24
actual CSV latest trade_date = 2026-06-23
prewarm --resume previously trusted metadata only and skipped the symbol
```

The consistency check now compares the daily CSV latest date with
`.coverage.json`. If `metadata_covered_end` is later than `csv_latest_date`, the
symbol is marked `coverage_metadata_mismatch`, `coverage_ok` is false, and the
prewarm path clamps metadata to the CSV latest date before fetching the missing
tail. Successful cache files already written are preserved.

The coverage report now includes:

```text
symbol
csv_latest_date
metadata_covered_end
coverage_metadata_mismatch
repair_recommendation
coverage_metadata_mismatch_count
coverage_metadata_mismatch_symbols
```

Known state before repair:

```text
total_stock_csv_files = 5416
complete_symbol_count = 5199
stale_incomplete_symbol_count = 217
missing_symbol_count = 0
metadata/CSV mismatches ending at 2026-06-23 = 216
other stale symbol latest date = 2026-06-09
```

Generate the full diagnostic report and a repair-only symbols CSV without
accessing BaoStock:

```powershell
python backend\scripts\report_raw_cache_catchup.py --cache-dir data\cache\daily-use --provider baostock --target-end-date 2026-06-24 --output-file outputs\cache\raw_cache_catchup_coverage_2026-06-24.json --mismatched-symbols-output outputs\cache\raw_cache_mismatched_2026-06-24.csv
```

The command prints a `mismatch_repair_command`. The equivalent protected manual
repair command is:

```powershell
python backend\scripts\prewarm_market_cache.py --provider baostock --start-date 2024-12-11 --end-date 2026-06-24 --cache-dir data\cache\daily-use --output-dir outputs\cache --symbols-file outputs\cache\raw_cache_mismatched_2026-06-24.csv --retry-only --batch-size 1 --sleep-seconds 2.0 --retry 2 --resume --max-errors 20 --symbol-timeout-seconds 40 --max-consecutive-symbol-timeouts 2 --failed-symbols-output outputs\cache\raw_cache_mismatched_2026-06-24_repair_failed.csv --progress-log outputs\cache\raw_cache_mismatched_2026-06-24_repair_progress.jsonl
```

The user runs this long repair manually. Codex only prepares and verifies the
tooling.

## Interpretation

This phase only improves raw local cache freshness. It does not imply model effectiveness and does not justify scoring/ranking changes.
