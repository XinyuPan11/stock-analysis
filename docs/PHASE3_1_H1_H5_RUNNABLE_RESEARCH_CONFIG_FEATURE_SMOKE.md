# Phase 3.1 H1-H5 Runnable Research Config and Feature-Only Smoke

## Purpose

Phase 3.1 proves that the existing H1-H5 research builder can execute from an
audited feature-only snapshot with an explicit finite config. It does not test
returns, validate effectiveness, or authorize production behavior.

H1-H3 remain opportunity observations. H4-H5 remain non-blocking risk
annotations.

## Runnable Config

The runnable research config is:

```text
research/configs/opportunity_cohorts.phase3_1_smoke.json
```

It uses `config_version=phase3.1-smoke-v1`,
`created_for_phase=Phase 3.1`, and
`parameter_source=engineering_smoke_not_u1_u2_tuned`.

All 18 values are finite engineering smoke boundaries chosen from feature
meaning and synthetic execution needs only. They were not selected from U1,
U2, the 2024 answer key, case-study outcomes, winners, losers, future returns,
or performance metrics. They are not validated parameters, production
thresholds, or effectiveness estimates.

The config keeps:

- `research_only=true`;
- `labels_joined=false`;
- `production_change=false`;
- `effectiveness_claim=false`;
- `production_eligible=false`.

It also names a prospective unopened U3 contract. Phase 3.3 must freeze the
exact evaluator manifest and decision thresholds before any holdout outcome is
opened. No Phase 3.1 command evaluates that holdout.

## Feature-Only Snapshot

The source is the existing ignored Phase 2.14 merged snapshot:

```text
outputs/experiments/member_level_asof_snapshot_2024.csv
```

Only `as_of_date=2024-10-31` is exported for the engineering smoke. The
exporter explicitly removes and audits all detected outcome columns before it
selects or writes rows. It performs no provider access.

Dry-run:

```powershell
python backend\scripts\build_feature_only_member_snapshot.py --snapshot-file outputs\experiments\member_level_asof_snapshot_2024.csv --as-of-date 2024-10-31 --outputs-dir research\inputs --drop-outcome-columns --dry-run
```

Write the ignored feature-only snapshot:

```powershell
python backend\scripts\build_feature_only_member_snapshot.py --snapshot-file outputs\experiments\member_level_asof_snapshot_2024.csv --as-of-date 2024-10-31 --outputs-dir research\inputs --drop-outcome-columns --write-output
```

Expected local paths:

```text
research/inputs/member_level_asof_features_2024-10-31.csv
research/inputs/member_level_asof_features_2024-10-31.json
```

`research/inputs/` is ignored because these are generated smoke artifacts.

## H1-H5 Builder Smoke

Dry-run:

```powershell
python backend\scripts\build_research_opportunity_cohorts.py --snapshot-file research\inputs\member_level_asof_features_2024-10-31.csv --as-of-date 2024-10-31 --config research\configs\opportunity_cohorts.phase3_1_smoke.json --outputs-dir outputs --dry-run
```

Write the ignored research-only output after the dry-run passes:

```powershell
python backend\scripts\build_research_opportunity_cohorts.py --snapshot-file research\inputs\member_level_asof_features_2024-10-31.csv --as-of-date 2024-10-31 --config research\configs\opportunity_cohorts.phase3_1_smoke.json --outputs-dir outputs --write-output
```

Expected local paths:

```text
outputs/research/opportunity_cohorts_2024-10-31.csv
outputs/research/opportunity_cohorts_2024-10-31.json
```

The output contains source rows plus research annotations. It contains no
future labels or returns, does not join validation data, and reports
`provider_access=false`, `labels_joined=false`, and
`production_change=false`.

## Why This Is Not Validation

The smoke date comes from consumed historical infrastructure and is used only
to verify execution, point-in-time checks, label removal, schema compatibility,
and output safety. Cohort membership counts from this smoke are engineering
diagnostics, not evidence of effectiveness.

No future return, benchmark outcome, winner/loser status, U1/U2 result, or
answer-key result is inspected or used. The Phase 3.1 artifacts cannot support
alpha, performance, or recommendation claims.

## Production Boundary

Phase 3.1 changes no production score, rank, factor, validation label,
candidate selection, existing list membership, threshold, or recommendation
logic. H4-H5 remain annotations and cannot exclude a symbol. No generated
smoke file is a production list.

## Next Phase

Phase 3.2 may seal the label-free H1-H5 membership, config version, snapshot
version, and checksums, then add a research-only UI/API stub. Outcome
evaluation remains prohibited until the separate Phase 3.3 U3 preregistration
is complete.
