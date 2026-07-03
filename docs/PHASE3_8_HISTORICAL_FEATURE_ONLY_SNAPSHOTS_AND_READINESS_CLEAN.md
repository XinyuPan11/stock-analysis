# Phase 3.8 Historical Feature-Only Snapshots And Readiness Clean

## Purpose

Phase 3.8 exports feature-only snapshots from the three label-free historical
source snapshots created by Phase 3.7.3. It then runs historical readiness to
confirm that the primary panel is ready for a separately approved,
label-free H1-H5 cohort-generation phase.

This phase is an export and readiness phase. It does not run validation,
inspect outcomes, calculate future returns, join labels, call an evaluator,
or generate H1-H5 cohort outputs.

## Historical Contract

```text
validation_id = h1h5-historical-sealed-v1
evidence_level = historical_sealed_not_prospective
benchmark = CSI300
horizon = 20 trading days
parameter source = phase3.1-smoke-v1
parameter count = 18
production_change = false
labels_joined = false
provider_access = false
```

Only the three primary windows were processed:

```text
2026-01-30
2026-03-31
2026-04-30
```

The backup windows remained inactive. Prospective U3 configs and windows were
not opened or changed.

## Source Snapshot Inputs

The following Phase 3.7.3 source snapshots existed locally before export:

| As-of date | Source snapshot | Rows | SHA-256 |
|---|---|---:|---|
| 2026-01-30 | `outputs/experiments/historical_h1h5_source_snapshot_2026-01-30.csv` | 276 | `7060827D73A0DB2F9C7788E88825997EAE825449623ACE4536C7585A88EB9A0B` |
| 2026-03-31 | `outputs/experiments/historical_h1h5_source_snapshot_2026-03-31.csv` | 276 | `3A480F15077E5AB6FDCB4149C90A9A065B5BFB06473CE16845016FE7D8D697D9` |
| 2026-04-30 | `outputs/experiments/historical_h1h5_source_snapshot_2026-04-30.csv` | 276 | `BB5937EF7596BC0EE313FCFE8D67EE7FB2739BE1833D6503CF62AC1AB84B2E69` |

These checksums match the Phase 3.7.3 execution record. No missing source was
synthesized, fetched, or replaced.

## Feature-Only Dry-Runs

Each source was first checked with the existing feature-only exporter:

```powershell
python backend\scripts\build_feature_only_member_snapshot.py --snapshot-file outputs\experiments\historical_h1h5_source_snapshot_<DATE>.csv --as-of-date <DATE> --outputs-dir research\inputs --dry-run
```

All three dry-runs returned `status=ok` with:

```text
input_row_count = 276
output_row_count = 276
dropped_outcome_columns = []
drop_outcome_columns_requested = false
latest_input_date_max = as_of_date
leakage_guard_applied = true
research_only = true
feature_only = true
labels_joined = false
provider_access = false
production_change = false
```

The export did not use `--drop-outcome-columns`. Therefore any future,
outcome, target, label, winner/loser, or realized field would have blocked
the run instead of being silently removed.

## Feature-Only Write Execution

After the dry-runs passed, each command was rerun with `--write-output`:

```powershell
python backend\scripts\build_feature_only_member_snapshot.py --snapshot-file outputs\experiments\historical_h1h5_source_snapshot_<DATE>.csv --as-of-date <DATE> --outputs-dir research\inputs --write-output
```

Generated files:

```text
research/inputs/member_level_asof_features_2026-01-30.csv
research/inputs/member_level_asof_features_2026-01-30.json
research/inputs/member_level_asof_features_2026-03-31.csv
research/inputs/member_level_asof_features_2026-03-31.json
research/inputs/member_level_asof_features_2026-04-30.csv
research/inputs/member_level_asof_features_2026-04-30.json
```

Each CSV contains 276 rows. The CSV checksums are:

```text
2026-01-30
BC30FA38F96923369431753A2D90BA04127AD600DD47A5686BD71CC46C3CF5E9

2026-03-31
3CDD69BD02BD1980B7CAD8FFFA18BD60865FCF41BC17BA8D4CCE49340BC24E50

2026-04-30
4C65E94763AF065A9E2A963B407AB25862C65BF786BA836D6B8929B82560872A
```

## Historical Readiness After Export

The default readiness command was run:

```powershell
python backend\scripts\check_historical_h1h5_readiness.py
```

It returned:

```text
status = ready
ready = true
primary_window_count = 3
ready_primary_window_count = 3
backup_window_count = 2
ready_backup_window_count = 0
```

All three primary windows returned `status=ready`, with 276 feature-only rows,
verified leakage guards, and matching 18-parameter and frozen-logic digests.
The readiness message permits only a separately approved label-free builder
dry-run.

The two inactive backups remain `blocked_missing_source_snapshot`. They were
not activated, generated, or used to replace a primary.

## Generated File Policy

`research/inputs/` is ignored by Git. The six feature-only CSV/JSON files are
local generated research artifacts and must remain uncommitted.

The Phase 3.7.3 source snapshots remain ignored under `outputs/`. No H1-H5
cohort, validation prediction, evaluator result, or performance artifact was
created.

Only this Phase 3.8 execution document is intended for commit.

## Why This Is Not Validation

The exporter selects and verifies entry-time feature rows already frozen by
the label-free historical source builder. It checks schema, exact as-of date,
point-in-time metadata, leakage guards, and forbidden columns.

It does not read a future price or outcome value, calculate a future return,
assign winner/loser status, compare a cohort with a benchmark outcome, or
produce a hypothesis verdict. Readiness validates file and config contracts,
not performance.

## Why No H1-H5 Cohort Output Was Generated

Phase 3.8 stops immediately after readiness becomes clean. The H1-H5
opportunity cohort builder was not run in dry-run or write-output mode, and no
historical cohort membership file was created.

Cohort generation changes the frozen research artifact set and therefore
belongs to its own separately approved phase.

## Next Phase Recommendation

The next phase is:

```text
Phase 3.9 Historical Sealed H1-H5 Label-Free Cohort Generation and Freeze
```

Phase 3.9 may run exact-date builder dry-runs against these three feature-only
snapshots and, after review, write and freeze label-free cohort outputs. It
must remain separate from any future-label join, evaluator execution, or
performance interpretation.

## Phase Decision

Phase 3.8 exported three clean feature-only snapshots and advanced all three
primary historical windows to readiness `status=ready`.

No validation, provider access, BaoStock execution, cache prewarm, outcome
inspection, future-return calculation, validation-label generation or join,
H1-H5 cohort generation, parameter/config change, U3 change, or production
logic change occurred.
