# Phase 3.7.1 Historical Source Snapshot Inventory and Generation Plan

## Purpose

Phase 3.7.1 explains why Phase 3.7 remains blocked, inventories the local
files needed to create historical sealed H1-H5 source snapshots, and defines
a provider-free generation plan for a later phase.

This phase is read-only. It does not run validation, inspect outcomes,
generate labels, calculate returns, prewarm cache, create feature-only
snapshots, or generate H1-H5 cohort outputs.

## Current Phase 3.7 Blocker

Phase 3.7 expects one source file per historical date:

```text
outputs/experiments/member_level_asof_snapshot_<date>.csv
```

None of the five files exists. Phase 3.7 therefore correctly returns
`blocked_missing_source_snapshot` for every primary and backup window.

The missing source files do not imply that all underlying local market data
is absent. This phase separates cache availability from source-builder
availability.

## Read-Only Inventory Command

Phase 3.7.1 adds:

```text
backend/src/stock_analysis/research/historical_snapshot_inventory.py
backend/scripts/inventory_historical_h1h5_source_snapshots.py
```

Run:

```powershell
python backend\scripts\inventory_historical_h1h5_source_snapshots.py
```

The command prints JSON only. It creates no report file and performs no
provider call, prewarm, validation, evaluator call, return calculation, or
output generation.

It reads only:

- cached universe symbols;
- cache coverage JSON;
- the `trade_date` column from local CSI300 cache candidates;
- source snapshot headers and row counts, if a source exists;
- existence of expected local output filenames.

It does not read price, return, label, winner/loser, or validation-result
values.

## Expected Source Snapshot Format

### Path

```text
outputs/experiments/member_level_asof_snapshot_<date>.csv
```

The source filename must contain the exact preregistered date.

### Required identity and PIT columns

```text
as_of_date
symbol
leakage_guard_applied
```

`as_of_date` must equal the requested historical window for every row.
`leakage_guard_applied` must be true for every row.

`latest_input_date` is conditional metadata under the current exporter. When
present, every value must be on or before `as_of_date`.

`max_raw_cache_date` may be later than the as-of date because it describes
physical cache extent rather than feature usage.
`future_rows_excluded_count` is an allowed diagnostic count, not an outcome.

### Required H1-H5 as-of features

```text
pre_5d_return
pre_20d_return
pre_60d_return
drawdown_60d
amount_change_20d
volume_change_20d
distance_to_60d_high
distance_to_60d_low
recent_acceleration_proxy
high_position_crowding_proxy
is_breakout_watch
is_accumulation_watch
```

One volatility field is required:

```text
technical_volatility_20d
```

or:

```text
volatility_20d
```

All features must be materialized only from rows available on or before the
as-of date. Existing rank, score, factor, and list-context columns may be
preserved, but they are not permission to change production behavior.

### Forbidden columns

The source passed into Phase 3.7 must not expose future, forward, realized,
target, outcome, label, winner/loser, benchmark-outcome, or holding-period
columns.

The minimum valid universe is 100 rows per window. Phase 3.7 rechecks the
feature-only output and fails closed below this gate.

## Local Inventory Summary

The inventory was run against:

```text
data/cache/daily-use/baostock
```

Observed local state:

| Item | Inventory result |
|---|---:|
| Cached universe symbols | 5,494 |
| Symbols with usable stock coverage metadata | 5,415 |
| Minimum source universe gate | 100 |
| Latest local benchmark trade date | `2026-06-24` |
| Historical source snapshots present | 0 of 5 |
| Cache-only factors present for historical dates | 0 of 5 |
| Cache-only candidates present for historical dates | 0 of 5 |
| Historical list files present | 0 |
| Historical validation-prediction filenames present | 0 |

CSI300 cache candidates include:

```text
data/cache/daily-use/baostock/index_daily/raw/CSI300.csv
data/cache/daily-use/baostock/stock_daily/adjusted/sh.000300.csv
data/cache/daily-use/baostock/stock_daily/adjusted/sz.399300.csv
```

The dedicated index file ends at `2024-10-31`, but the two local stock-style
CSI300 aliases extend through `2026-06-24` and cover all five as-of dates.

## Per-Window Inventory

| Window | Kind | Source exists | Stock cache through as-of | CSI300 through as-of | Local 20D future dates | Provider needed for source | Provider needed for later 20D | Current blocker |
|---|---|---:|---:|---:|---|---:|---:|---|
| `2026-01-30` | Primary | No | 5,415 symbols | Yes | Complete; 20th date `2026-03-09` | No | No | `blocked_safe_source_snapshot_builder_required` |
| `2026-03-31` | Primary | No | 5,415 symbols | Yes | Complete; 20th date `2026-04-29` | No | No | `blocked_safe_source_snapshot_builder_required` |
| `2026-04-30` | Primary | No | 5,415 symbols | Yes | Complete; 20th date `2026-06-02` | No | No | `blocked_safe_source_snapshot_builder_required` |
| `2026-02-27` | Backup | No | 5,415 symbols | Yes | Complete; 20th date `2026-03-27` | No | No | `blocked_safe_source_snapshot_builder_required` |
| `2026-05-29` | Backup | No | 5,415 symbols | Yes | Incomplete; 17 dates through `2026-06-24` | No | Yes under current cache | Source builder missing; later evaluator cache also incomplete |

The first four windows have enough local metadata coverage for both as-of
source preparation and later 20D evaluation. No return or label was computed
to reach this conclusion; the inventory counted benchmark trade dates and
checked coverage intervals only.

The `2026-05-29` backup has sufficient as-of cache for source generation, but
it does not satisfy its separate Phase 3.6 activation rule for complete local
20D future coverage.

## Existing Builder Limitation

The current command:

```text
backend/scripts/build_member_level_asof_snapshot.py
```

is not approved for these historical sealed windows. Its implementation:

1. requires
   `outputs/validation/walk_forward_predictions_<date>_20d.csv` as the
   member universe;
2. copies future label fields from those prediction files;
3. writes the fixed 2024 summary filenames.

Using it would mix source preparation with validation artifacts and violate
the Phase 3.6 membership-before-label boundary.

Do not create historical prediction files merely to satisfy this builder.
Do not run this builder for Phase 3.7.1.

## Safe Generation Plan

The local cache appears sufficient to build as-of inputs for all three
primary windows and both backups without provider access. The missing
component is a source-only assembler.

The next implementation should:

1. use the exact cached universe or an explicitly frozen local 300-symbol
   universe;
2. read only local daily cache through the requested as-of date;
3. generate cache-only factor and candidate context;
4. derive H1-H5 source features before any label source is opened;
5. set and verify `latest_input_date <= as_of_date`;
6. retain `max_raw_cache_date` and `future_rows_excluded_count` as
   diagnostics;
7. write one exact-date source CSV/JSON pair;
8. reject every future/outcome/label field before writing;
9. never import validation predictions, evaluator code, or provider objects.

The source-only implementation should use a new command, rather than changing
the legacy 2024 attribution builder silently:

```text
backend/scripts/build_historical_h1h5_source_snapshot.py
```

Its proposed future invocation is:

```powershell
python backend\scripts\build_historical_h1h5_source_snapshot.py --as-of-date <HISTORICAL_DATE> --cache-dir data\cache\daily-use --outputs-dir outputs --limit 300 --dry-run
```

Only after dry-run review should a later approved phase allow:

```powershell
python backend\scripts\build_historical_h1h5_source_snapshot.py --as-of-date <HISTORICAL_DATE> --cache-dir data\cache\daily-use --outputs-dir outputs --limit 300 --write-output
```

This command does not exist in Phase 3.7.1; the next phase must implement and
test it before either template is used.

## Future Cache-Only Preparation Commands

The existing cache-only daily generator can prepare factor and candidate
context without provider fallback. These commands are for a later approved
generation phase and were not executed here:

```powershell
python backend\scripts\generate_cache_only_asof_daily_outputs.py --date 2026-01-30 --cache-dir data\cache\daily-use --outputs-dir outputs --provider baostock --benchmark CSI300 --limit 300
python backend\scripts\generate_cache_only_asof_daily_outputs.py --date 2026-03-31 --cache-dir data\cache\daily-use --outputs-dir outputs --provider baostock --benchmark CSI300 --limit 300
python backend\scripts\generate_cache_only_asof_daily_outputs.py --date 2026-04-30 --cache-dir data\cache\daily-use --outputs-dir outputs --provider baostock --benchmark CSI300 --limit 300
```

Run backup commands only after a primary is formally blocked and the frozen
backup order is applied.

## Optional Manual Cache Extension For The Second Backup

No cache prewarm is needed to prepare an as-of source for `2026-05-29`.
However, that backup cannot later be activated for evaluation until at least
three more CSI300 trading dates and corresponding stock coverage are
available after `2026-06-24`.

If the backup is formally activated and the user separately authorizes
provider access, a manual resumable command may use:

```powershell
python backend\scripts\prewarm_full_market_batches.py --provider baostock --start-date 2026-06-25 --end-date <DATE_CONTAINING_AT_LEAST_THREE_MORE_CSI300_SESSIONS> --include-lookback-days 365 --cache-dir data\cache\daily-use --output-dir outputs\cache --resume
```

This is a user-run provider command. Codex did not execute it. The end date
must be confirmed from a trading calendar before use; it must not be chosen
from H1-H5 outcomes.

## Can Feature-Only Generation Proceed?

Not yet.

The underlying as-of market cache appears sufficient, but the required safe
source snapshots do not exist and the current member-level builder is
label-coupled. Running the feature-only exporter now would correctly return
`blocked_missing_source_snapshot`.

Phase 3.7.1 creates no file under `research/inputs/`.

## Recommended Next Phase

The next phase is:

```text
Phase 3.7.2 Historical Sealed Label-Free Source Snapshot Builder
```

Phase 3.7.2 should implement the new source-only dry-run and writer, cover all
PIT and forbidden-column guards with tests, and generate only the three
primary source snapshots after manual review.

Feature-only export should remain a separate following step. H1-H5 cohort
generation and evaluation remain later phases.

## Phase Decision

Phase 3.7.1 finds no need for provider access to prepare the primary as-of
source data. It does find a missing safe source-builder path and incomplete
future coverage for the second backup.

This phase changes inventory code and documentation only. It does not run
validation, inspect outcomes, prewarm cache, create source or feature
snapshots, generate labels, calculate returns, create H1-H5 cohorts, modify
configs, or change production behavior.
