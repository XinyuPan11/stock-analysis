# Phase 3.4 U3 Execution Readiness and Config Date-Binding Fix

## Purpose

Phase 3.4 resolves the date-binding blocker identified by Phase 3.3 and adds
a fail-closed readiness check for the two preregistered U3 windows.

This phase does not run U3 validation, generate future labels, inspect
outcomes, access a provider, or generate real U3 cohort outputs.

## Date-Binding Issue

The Phase 3.1 source config is:

```text
research/configs/opportunity_cohorts.phase3_1_smoke.json
config_version = phase3.1-smoke-v1
as_of_date = 2024-10-31
```

Execution-mode schema validation requires the requested as-of date to equal
the config as-of date. The source config therefore cannot be used directly
for the U3 dates.

Phase 3.4 keeps the source immutable and creates two date-correct execution
configs:

```text
research/configs/opportunity_cohorts.u3_2026-09-30.json
research/configs/opportunity_cohorts.u3_2026-12-31.json
```

Each config declares:

```text
copied_from = phase3.1-smoke-v1
parameter_change = false
tuning_change = false
date_binding_only_change = true
research_only = true
provider_access = false
labels_joined = false
production_change = false
holdout_id = u3-prospective-2026-h2-v1
```

The nested future holdout contract is copied unchanged from the Phase 3.1
source and matches the Phase 3.3 preregistration.

## Deterministic Digest Proof

`stock_analysis.research.u3_readiness` canonicalizes the parameter block as
sorted, compact JSON and computes SHA-256. It separately computes a frozen
logic digest over:

- the exact H1-H5 cohort IDs;
- all 18 numeric parameters;
- cohort roles;
- feature bindings.

Readiness requires both U3 configs to have the same parameter digest and
frozen logic digest as `phase3.1-smoke-v1`. It also requires identical
parameter documentation and an unchanged holdout contract.

Changing one numeric value, role, or feature binding produces a different
digest and blocks readiness.

## Readiness Command

Run:

```powershell
python backend\scripts\check_u3_opportunity_cohort_readiness.py
```

The command checks local files only. It does not call BaoStock or any other
provider and does not read validation output.

For each U3 window it checks:

- source and U3 config existence;
- date-binding governance metadata;
- exact expected as-of date;
- Phase 2.39 execution-mode schema validation;
- holdout ID and full holdout-contract equality;
- parameter count and SHA-256 equality;
- role and feature-binding digest equality;
- feature-only snapshot existence and safety;
- the 100-row preregistered universe gate;
- absence of future/outcome columns and unverified leakage metadata.

The default expected snapshot paths are:

```text
research/inputs/member_level_asof_features_2026-09-30.csv
research/inputs/member_level_asof_features_2026-12-31.csv
```

If a snapshot is missing, the window returns:

```text
blocked_missing_feature_only_snapshot
```

It does not try to download data or create the snapshot.

If all checks pass, readiness reports that the window is ready only for a
separate label-free builder dry-run. It does not write cohort membership.

## Why This Is Not Validation

Readiness inspects config structure, local feature-only inputs, point-in-time
metadata, sample count, and checksums. It does not create or join future
labels, compute returns, inspect outcomes, or classify H1-H5 effectiveness.

No generated validation output is required or read.

## Why Parameters Were Not Tuned

The U3 configs copy the exact 18 numeric values, cohort roles, feature
binding, documentation, and holdout contract from the Phase 3.1 source.
Only date-specific execution metadata changes.

The configs explicitly state `parameter_change=false`,
`tuning_change=false`, and `date_binding_only_change=true`. Automated tests
alter one parameter and confirm that the checksum guard blocks readiness.

## Next Phase

The next permitted step is a controlled U3 feature-only snapshot readiness
workflow after each preregistered date has arrived and its local point-in-time
inputs are available.

Only after both snapshots pass this readiness check may a separately approved
phase run label-free H1-H5 builder dry-runs. U3 future labels and evaluation
remain separate and require explicit user authorization.
