# Phase 3.9 Historical Sealed H1-H5 Cohort Generation And Freeze

## Purpose

Phase 3.9 generates and freezes label-free H1-H5 research cohorts for the
three historical sealed primary windows that became ready in Phase 3.8.

This phase freezes membership and risk annotations before any evaluator or
future label is opened. It is cohort generation, not validation.

## Historical Contract

```text
validation_id = h1h5-historical-sealed-v1
evidence_level = historical_sealed_not_prospective
parameter source = phase3.1-smoke-v1
parameter count = 18
parameter digest =
163b90128233383d9965c17fa2e1065c50222e4db706c93787326053ef8fca46
research_only = true
provider_access = false
labels_joined = false
production_change = false
counts_are_validation_evidence = false
```

Only the three primary windows were generated:

```text
2026-01-30
2026-03-31
2026-04-30
```

The backup windows remained inactive. Prospective U3 configs and windows were
not used or changed.

## Inputs And Configs

The builder used the Phase 3.8 feature-only snapshots:

```text
research/inputs/member_level_asof_features_2026-01-30.csv
research/inputs/member_level_asof_features_2026-03-31.csv
research/inputs/member_level_asof_features_2026-04-30.csv
```

Each snapshot contained 276 exact-date, leakage-guarded rows.

The exact date-bound configs were:

```text
research/configs/opportunity_cohorts.historical_2026-01-30.json
research/configs/opportunity_cohorts.historical_2026-03-31.json
research/configs/opportunity_cohorts.historical_2026-04-30.json
```

Historical readiness was run before generation. It returned overall
`status=ready`, with all three primary windows ready, all safety flags clean,
and the historical configs matching the frozen 18-parameter and logic
digests. The two backups remained `blocked_missing_source_snapshot`.

## Builder Dry-Runs

Each primary window was first built without writing files:

```powershell
python backend\scripts\build_research_opportunity_cohorts.py --snapshot-file research\inputs\member_level_asof_features_<DATE>.csv --as-of-date <DATE> --config research\configs\opportunity_cohorts.historical_<DATE>.json --outputs-dir outputs --dry-run
```

All three dry-runs returned:

```text
status = ok
research_only = true
provider_access = false
labels_joined = false
production_change = false
config_validation_mode = execution
holdout_id = h1h5-historical-sealed-v1
input_row_count = 276
output_record_count = 1380
cohort_count = 5
blocked_row_count = 0 for every cohort
leakage_guard_applied = true
```

The 1,380 records are 276 symbols evaluated separately against each of the
five frozen H1-H5 definitions. They are annotation records, not 1,380
distinct securities.

## Write Execution

After all dry-runs passed, each command was rerun with `--write-output`:

```powershell
python backend\scripts\build_research_opportunity_cohorts.py --snapshot-file research\inputs\member_level_asof_features_<DATE>.csv --as-of-date <DATE> --config research\configs\opportunity_cohorts.historical_<DATE>.json --outputs-dir outputs --write-output
```

Generated files:

```text
outputs/research/opportunity_cohorts_2026-01-30.csv
outputs/research/opportunity_cohorts_2026-01-30.json
outputs/research/opportunity_cohorts_2026-03-31.csv
outputs/research/opportunity_cohorts_2026-03-31.json
outputs/research/opportunity_cohorts_2026-04-30.csv
outputs/research/opportunity_cohorts_2026-04-30.json
```

## Frozen H1-H5 Member Counts

| As-of date | H1 low-position | H2 trend acceleration | H3 right-tail | H4 crowding risk | H5 false-breakout risk |
|---|---:|---:|---:|---:|---:|
| 2026-01-30 | 0 | 15 | 0 | 0 | 9 |
| 2026-03-31 | 1 | 15 | 0 | 0 | 9 |
| 2026-04-30 | 9 | 25 | 0 | 0 | 13 |

H1-H3 remain opportunity observations. H4-H5 remain non-blocking risk
annotations.

Empty cohorts are retained exactly as generated. Their zero counts do not
authorize parameter, threshold, feature-binding, role, or date changes.

These counts are execution and membership evidence only:

```text
counts_are_validation_evidence = false
```

They contain no information about future performance, winner capture, loser
contamination, benchmark excess return, drawdown outcomes, or hypothesis
support.

## Frozen SHA-256 Digests

| As-of date | File | SHA-256 |
|---|---|---|
| 2026-01-30 | CSV | `86C32E2C259E8E40E8CD638DF4BAC8A28E4ADBDA210719171D1CA76E36416198` |
| 2026-01-30 | JSON | `0BDBBFC7100D7C6ACD9F5ADC90A687BA8826C1E9700E9F9D0CF7309195CB4439` |
| 2026-03-31 | CSV | `20E79A9F469EDE9924A36077E276707BAAA4A7672DA5D629C70356CD1463A890` |
| 2026-03-31 | JSON | `097390A75552825DC5F7A0D999672D3AD03B7C5EEA93CB373C775276DC87ABAB` |
| 2026-04-30 | CSV | `201273F652BCEAC6E3E5D42B52DFD25EC50EF3B4CAFC960392F86EDAA0B39655` |
| 2026-04-30 | JSON | `387E5DF1D74BBBE8DB8078C062863845460E3067225EBC95DFD10BA9A090A5F7` |

Regenerating or overwriting these files after outcomes are opened would break
the freeze and require an explicit invalid-execution record.

## Freeze Verification

All six files were independently reopened after writing.

The verification confirmed:

- every CSV has 1,380 parseable records;
- every JSON has five cohort summaries and 1,380 records;
- actual `cohort_member=true` counts equal the JSON summaries;
- every cohort has `blocked_row_count=0`;
- no future, forward, realized, label, winner/loser, target, or outcome field
  exists in CSV headers or recursively in JSON keys;
- metadata declares `research_only=true`;
- metadata declares `provider_access=false`;
- metadata declares `labels_joined=false`;
- metadata declares `production_change=false`;
- config validation mode is `execution`;
- the parameter digest matches the frozen historical preregistration;
- the existing API safety loader returns `status=available` for each exact
  historical date with matching member counts.

## Generated File Policy

The six cohort files remain under the Git-ignored `outputs/` tree and must not
be committed. The feature-only inputs remain ignored under `research/inputs/`.

Only this Phase 3.9 execution and freeze record is intended for commit.

No validation prediction, evaluator output, future-label file, performance
report, or generated validation artifact was created or modified.

## Why This Is Not Validation

The builder applies frozen conditions to point-in-time features and records
membership. It does not open a future price, generate or join a label,
calculate a future return, compare members against CSI300 outcomes, or issue
an H1-H5 verdict.

Member counts alone cannot establish effectiveness. In particular, a larger,
smaller, or empty cohort says nothing about future returns or validation
support.

## Why Evaluation Was Not Run

The sealed execution order requires no-label memberships to be generated,
checksummed, and documented before an evaluator is designed or run.

Phase 3.9 therefore stops after freeze verification. It does not call an
evaluator and does not inspect outcome-bearing data.

## Next Phase Recommendation

The next phase is:

```text
Phase 3.10 Historical Sealed Evaluator Design
```

Phase 3.10 should define the evaluator contract, unchanged label math,
sample/coverage gates, contamination checks, per-window reporting, and
invalid/underpowered handling before any labels are generated or joined.
Evaluator execution and result interpretation should remain separately
authorized.

## Phase Decision

Phase 3.9 generated and froze label-free H1-H5 cohort outputs for all three
ready primary historical windows.

No validation, provider access, BaoStock execution, cache prewarm, feature
snapshot generation, outcome inspection, future-return calculation,
validation-label generation or join, evaluator execution, parameter/config
change, U3 change, or production logic change occurred.
