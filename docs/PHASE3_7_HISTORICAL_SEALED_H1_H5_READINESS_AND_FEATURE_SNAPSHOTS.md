# Phase 3.7 Historical Sealed H1-H5 Readiness and Feature Snapshots

## Purpose

Phase 3.7 makes the Phase 3.6 historical sealed plan technically checkable.
It adds exact-date execution configs and a fail-closed readiness path, then
prepares feature-only snapshots only when an already-existing local source is
available.

This phase does not run validation, inspect outcomes, generate or join future
labels, compute future returns, access a provider, tune parameters, or
generate H1-H5 cohort outputs.

## Frozen Historical Identity

```text
validation_id = h1h5-historical-sealed-v1
evidence_level = historical_sealed_not_prospective
benchmark = CSI300
horizon = 20 trading days
parameter_source = phase3.1-smoke-v1
parameter_change = false
tuning_change = false
production_change = false
labels_joined = false
```

Historical sealed evidence remains weaker than prospective U3 evidence. The
historical readiness code does not import, modify, or require either U3
config file.

## Historical Windows

Primary windows:

| Priority | As-of date | Horizon |
|---|---|---|
| P1 | `2026-01-30` | 20 trading days |
| P2 | `2026-03-31` | 20 trading days |
| P3 | `2026-04-30` | 20 trading days |

Backup windows:

| Priority | As-of date | Horizon | Activation rule |
|---|---|---|---|
| B1 | `2026-02-27` | 20 trading days | First eligible replacement for a primary blocked by missing local data or contamination |
| B2 | `2026-05-29` | 20 trading days | Use only if complete 20D future coverage exists locally without provider fetch |

Backups are reported separately and do not block an otherwise ready
three-window primary panel. They cannot be activated from performance
expectations or after outcome inspection.

## Excluded Or Reserved Windows

The readiness checker rejects:

- answer-key windows: `2024-01-31`, `2024-04-30`, `2024-07-31`,
  `2024-10-31`;
- consumed U1 windows: `2024-02-29`, `2024-05-31`, `2024-08-30`,
  `2024-11-29`;
- consumed U2 windows: `2025-02-28`, `2025-05-30`, `2025-08-29`,
  `2025-11-28`;
- prospective U3 windows: `2026-09-30`, `2026-12-31`.

These dates return `blocked_excluded_window` before any config or snapshot is
opened.

## Date-Bound Historical Configs

Phase 3.7 adds:

```text
research/configs/opportunity_cohorts.historical_2026-01-30.json
research/configs/opportunity_cohorts.historical_2026-03-31.json
research/configs/opportunity_cohorts.historical_2026-04-30.json
research/configs/opportunity_cohorts.historical_2026-02-27.json
research/configs/opportunity_cohorts.historical_2026-05-29.json
```

Each config binds one exact date while copying the Phase 3.1 parameter
documentation, feature bindings, cohort roles, and all 18 numeric values.
Each declares:

```text
copied_from = phase3.1-smoke-v1
validation_id = h1h5-historical-sealed-v1
evidence_level = historical_sealed_not_prospective
parameter_change = false
tuning_change = false
date_binding_only_change = true
research_only = true
provider_access = false
labels_joined = false
production_change = false
```

The nested execution contract lists the three primary and two backup windows,
the unchanged 20-day horizon, CSI300 benchmark, 100-row universe gate, and
20-valid-labeled-member cohort gate. It remains historical and is not the U3
holdout contract.

## Checksum Proof

The checker uses the Phase 3.4 canonical SHA-256 method.

```text
parameter_digest =
163b90128233383d9965c17fa2e1065c50222e4db706c93787326053ef8fca46

frozen_logic_digest =
72d7159fb7c94c9c67fe6406e749285446b60a0c76331594ec062eb2201acdbe
```

The parameter digest covers the exact 18-value H1-H5 block. The frozen logic
digest additionally covers cohort IDs, roles, and feature bindings. Any
single parameter, role, or binding change blocks readiness. Parameter
documentation must also equal `phase3.1-smoke-v1`.

## Readiness Command

Run the local-only checker:

```powershell
python backend\scripts\check_historical_h1h5_readiness.py
```

An explicit existing source can be supplied without changing the
preregistration:

```powershell
python backend\scripts\check_historical_h1h5_readiness.py --source-snapshot 2026-01-30=<LOCAL_SOURCE_CSV> --source-snapshot 2026-03-31=<LOCAL_SOURCE_CSV> --source-snapshot 2026-04-30=<LOCAL_SOURCE_CSV>
```

The checker:

- accepts only the five Phase 3.6 historical dates;
- rejects all answer-key, U1, U2, and U3 dates;
- validates exact config/date/identity/evidence metadata;
- validates execution schema and checksum equality;
- requires an existing local source path;
- requires a separately exported feature-only snapshot;
- rejects outcome-bearing or point-in-time-unsafe feature snapshots;
- requires at least 100 valid feature-only rows;
- reports primary and backup readiness separately;
- reads no validation output and makes no provider request.

Missing files return:

```text
blocked_missing_source_snapshot
blocked_missing_feature_only_snapshot
```

The checker never downloads, synthesizes, exports, or repairs a missing file.

## Current Local Readiness

The local file-name audit found only:

```text
outputs/experiments/member_level_asof_snapshot_2024.csv
outputs/experiments/member_level_asof_snapshot_2024.json
outputs/experiments/member_level_asof_snapshot_2024.md
```

No local source member-level snapshot was found for any Phase 3.6 historical
date. The default required paths are:

```text
outputs/experiments/member_level_asof_snapshot_2026-01-30.csv
outputs/experiments/member_level_asof_snapshot_2026-03-31.csv
outputs/experiments/member_level_asof_snapshot_2026-04-30.csv
outputs/experiments/member_level_asof_snapshot_2026-02-27.csv
outputs/experiments/member_level_asof_snapshot_2026-05-29.csv
```

Therefore all three primary windows and both backup windows currently return
`blocked_missing_source_snapshot`. No provider fallback is permitted.

## Feature-Only Snapshot Export

When an exact local source exists, first run an explicit dry-run:

```powershell
python backend\scripts\build_feature_only_member_snapshot.py --snapshot-file <LOCAL_SOURCE_CSV> --as-of-date <HISTORICAL_DATE> --outputs-dir research\inputs --drop-outcome-columns --dry-run
```

Review only:

- output row count;
- dropped outcome-column names;
- `latest_input_date_max`;
- leakage guard;
- `research_only=true`;
- `provider_access=false`;
- `labels_joined=false`;
- `production_change=false`.

Only after the dry-run passes may a separately reviewed command replace
`--dry-run` with `--write-output`. Expected generated paths are:

```text
research/inputs/member_level_asof_features_<date>.csv
research/inputs/member_level_asof_features_<date>.json
```

The feature exporter may remove audited outcome columns only through the
explicit `--drop-outcome-columns` flag and records every removed column name.
The written feature snapshot must contain no future, forward, realized,
target, outcome, label, winner/loser, benchmark-outcome, or holding-period
field.

Because no matching source exists in the current workspace, Phase 3.7 runs no
export command and writes no feature-only snapshot.

## Generated File Policy

`research/inputs/` remains ignored by Git. Feature-only CSV and JSON files are
local generated research artifacts and must remain uncommitted unless a later
phase explicitly approves artifact capture.

Readiness does not read or modify:

```text
outputs/research/opportunity_cohorts_<date>.csv
outputs/research/opportunity_cohorts_<date>.json
```

No generated validation output is required, read, or changed.

## Why This Is Not Validation

Readiness verifies identities, local file existence, schema safety,
point-in-time metadata, checksums, forbidden columns, and sample size. It
does not create labels, calculate returns, compare cohorts with outcomes, or
classify H1-H5 effectiveness.

Member counts do not exist yet and no performance conclusion can be drawn.

## Why No Cohort Output Is Generated

Phase 3.7 stops before the H1-H5 builder. It does not run builder
`--write-output` and does not create a real historical H1-H5 membership file.

Cohort generation requires clean feature-only readiness and a separately
approved next phase. Missing source files are blockers, not permission to
fetch data, synthesize rows, loosen a gate, or use another date.

## Recommended Next Phase

After the selected historical windows have clean local source snapshots and
feature-only readiness, the recommended next phase is:

```text
Phase 3.8 Historical Sealed H1-H5 Label-Free Cohort Generation and Freeze
```

Phase 3.8 may run builder dry-runs and, after review, freeze no-label cohort
outputs. It must still stop before any evaluator joins future labels.

## Phase Decision

Phase 3.7 establishes deterministic historical readiness infrastructure and
date-bound configs. Current execution remains blocked because all five local
source snapshots are absent.

No validation, provider access, label join, future-return calculation,
outcome inspection, H1-H5 cohort output, U3 change, parameter tuning, or
production change occurs in this phase.
