# Phase 2.37 Feature-Only Snapshot Export for Opportunity Cohorts

## Purpose

Phase 2.37 adds a one-way, research-only export boundary between the Phase
2.14 merged member-level snapshot and the Phase 2.36 opportunity cohort
builder.

The Phase 2.14 snapshot intentionally contains explicit future labels for
attribution. Phase 2.36 correctly rejects those labels. This exporter selects
one as-of date, verifies the point-in-time boundary, and produces an H1-H5
input containing as-of features and source membership context only.

It does not evaluate outcomes, compute labels, run validation, access a
provider, or modify production logic.

## Safety Model

The exporter fails closed by default when any future, realized, winner/loser,
label, target, or outcome column is present.

Use `--drop-outcome-columns` only when intentionally converting an existing
merged snapshot. The exporter then:

- removes every detected outcome column before selecting or writing rows;
- records the exact removed columns in `dropped_outcome_columns`;
- verifies `leakage_guard_applied=true` for every selected row;
- verifies all feature date fields are on or before `as_of_date`;
- permits `max_raw_cache_date` to be later because it records physical cache
  extent, not effective feature input;
- preserves symbol, rank, source list membership, existing scores/factors,
  as-of technical features, and point-in-time diagnostics;
- performs no provider access and joins no labels.

`future_rows_excluded_count` is an allowed point-in-time diagnostic. It records
rows excluded by the leakage guard and is not an outcome.

## CLI

Default dry run:

```powershell
python backend\scripts\build_feature_only_member_snapshot.py --snapshot-file outputs\experiments\member_level_asof_snapshot_2024.csv --as-of-date 2024-10-31 --outputs-dir research\inputs --drop-outcome-columns --dry-run
```

Write the audited feature-only files:

```powershell
python backend\scripts\build_feature_only_member_snapshot.py --snapshot-file outputs\experiments\member_level_asof_snapshot_2024.csv --as-of-date 2024-10-31 --outputs-dir research\inputs --drop-outcome-columns --write-output
```

An explicit CSV path is also supported:

```powershell
python backend\scripts\build_feature_only_member_snapshot.py --snapshot-file outputs\experiments\member_level_asof_snapshot_2024.json --as-of-date 2024-10-31 --output-path research\inputs\member_level_asof_features_2024-10-31.csv --drop-outcome-columns --write-output
```

Without `--drop-outcome-columns`, a Phase 2.14 merged snapshot must stop with
`blocked_outcome_columns_present`. This is expected fail-closed behavior.

## Outputs

The default write paths are:

```text
research/inputs/member_level_asof_features_<as_of_date>.csv
research/inputs/member_level_asof_features_<as_of_date>.json
```

The JSON contains:

- `metadata.research_only=true`
- `metadata.feature_only=true`
- `metadata.labels_joined=false`
- `metadata.provider_access=false`
- `metadata.production_change=false`
- source and output paths
- input and output row counts
- the audited `dropped_outcome_columns`
- `latest_input_date_max`
- the feature-only records

## Phase 2.36 Handoff

After reviewing the export metadata, pass the CSV to the existing cohort
builder with an explicit preregistered config:

```powershell
python backend\scripts\build_research_opportunity_cohorts.py --snapshot-file research\inputs\member_level_asof_features_2024-10-31.csv --as-of-date 2024-10-31 --config research\configs\opportunity_cohorts_2024-10-31.json --outputs-dir outputs --dry-run
```

Phase 2.37 does not supply or tune H1-H5 parameters. A complete explicit
research config remains mandatory.

## Boundaries

- Research-only and feature-only.
- No future labels, returns, outcomes, or winner/loser fields in outputs.
- No BaoStock or other provider access.
- No validation or label recomputation.
- No scoring, ranking, factor, candidate, list-membership, threshold, or
  recommendation changes.
- No U1/U2 outcome inspection or parameter tuning.
- Existing generated validation outputs are read-only source material and are
  not modified.
