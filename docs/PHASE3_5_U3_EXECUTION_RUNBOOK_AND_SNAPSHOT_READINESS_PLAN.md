# Phase 3.5 U3 Execution Runbook and Snapshot Readiness Plan

## Purpose

Phase 3.5 defines the future manual execution path for preparing U3
feature-only snapshots, checking readiness, generating label-free H1-H5
cohorts, and freezing those cohorts before a separate evaluator exists.

Both U3 windows are future dates as of this document. Current readiness
correctly returns `blocked_missing_feature_only_snapshot` for each window.
That state is expected and must not be bypassed.

This phase creates a runbook only. It does not run U3, fetch data, generate
future labels, inspect outcomes, create U3 cohorts, or change any config or
production logic.

## Frozen U3 Contract

| Window | Date-bound config | Horizon | Benchmark |
|---|---|---|---|
| U3 window 1 | `research/configs/opportunity_cohorts.u3_2026-09-30.json` | 20 trading days | `CSI300` |
| U3 window 2 | `research/configs/opportunity_cohorts.u3_2026-12-31.json` | 20 trading days | `CSI300` |

The frozen holdout ID is:

```text
u3-prospective-2026-h2-v1
```

Both configs copy their 18 numeric parameters from
`phase3.1-smoke-v1`. Parameter values, parameter directions, H1-H5 cohort
roles, feature bindings, missing-data behavior, and the Phase 3.3 holdout
contract are immutable during this runbook.

Phase 3.4 recorded these reference digests:

```text
parameter_digest =
163b90128233383d9965c17fa2e1065c50222e4db706c93787326053ef8fca46

frozen_logic_digest =
72d7159fb7c94c9c67fe6406e749285446b60a0c76331594ec062eb2201acdbe
```

Any digest difference is a fail-stop condition, not permission to regenerate
or tune a config.

## Important Two-Window Readiness Gate

`check_u3_opportunity_cohort_readiness.py` checks both preregistered windows
in one report. Overall `status=ready` requires both feature-only snapshots to
exist and pass.

The expected sequence is therefore:

1. after `2026-09-30`, prepare and audit the first feature-only snapshot;
2. record that window 1 may be individually ready while the overall report
   remains blocked because window 2 is still missing;
3. do not run either H1-H5 builder write-output while overall readiness is
   blocked;
4. after `2026-12-31`, prepare and audit the second feature-only snapshot;
5. require the combined readiness report to return `status=ready`;
6. then run the two date-specific builder dry-runs and, after review, their
   write-output commands.

This keeps both memberships frozen under one reviewed gate and prevents a
partial execution from being mistaken for U3 validation.

## Separation From Historical Sealed Validation

This runbook applies only to the prospective U3 windows `2026-09-30` and
`2026-12-31`.

The project may later run historical sealed H1-H5 validation on other
already-available dates, but that work requires a separate phase with:

- a separate preregistration committed before any relevant outcome inspection;
- separate exact windows, holdout ID, date-bound configs, and output namespace;
- independent proof-integrity checks, including prior use and outcome access;
- a separate evidence ledger, execution record, and interpretation;
- no mixing or reuse of U3 artifacts, evidence, or execution records.

Phase 3.5 does not select, propose, preregister, or authorize any historical
validation date. An available historical date must not substitute for either
U3 window, make U3 readiness appear ready, or be treated as prospective U3
evidence.

## Future Execution Sequence

Repeat the date-specific preparation steps for each U3 date. Commands in this
document are future templates and must not be run before their date and local
source data are available.

### A. Confirm the date and source availability

- Confirm the local calendar date is on or after the U3 as-of date.
- Confirm completed as-of source data exists through that date.
- Confirm `latest_input_date` cannot exceed the as-of date.
- Do not fetch provider data as part of this runbook.
- If a provider or new cache acquisition is required, stop and open a
  separately approved data-preparation phase.

### B. Confirm the holdout is still unopened

- Do not open a future-return, benchmark-return, winner/loser, drawdown-label,
  or validation-result file for this U3 date.
- Confirm no U3 evaluator has been run.
- Confirm no U3 label output exists from an earlier accidental execution.
- If any outcome was inspected, stop and record the window as potentially
  consumed before doing anything else.

### C. Build or locate the member-level as-of source

Locate the exact source snapshot intended for the date. Record its path and
SHA-256 before conversion.

The source may contain audited outcome columns only if the feature-only
exporter will remove them without a human inspecting their values. If the
source cannot be materialized without opening outcomes, stop and implement a
separate feature-only source path first.

### D. Run the feature-only export dry-run

Use `build_feature_only_member_snapshot.py` with the exact date, explicit
`--drop-outcome-columns`, and `--dry-run`.

Review only:

- status;
- selected row count;
- `dropped_outcome_columns` names;
- `latest_input_date_max`;
- leakage guard;
- research/provider/label/production safety flags.

Do not inspect dropped outcome values.

### E. Write the feature-only snapshot

Run the identical command with `--write-output` only after the dry-run passes.
Record both CSV and JSON paths and their SHA-256 values.

Expected paths are:

```text
research/inputs/member_level_asof_features_2026-09-30.csv
research/inputs/member_level_asof_features_2026-09-30.json
research/inputs/member_level_asof_features_2026-12-31.csv
research/inputs/member_level_asof_features_2026-12-31.json
```

### F. Run the combined U3 readiness check

Run:

```powershell
python backend\scripts\check_u3_opportunity_cohort_readiness.py
```

Review each object under `windows`, not only the top-level status. The first
window can become locally ready before the second date, but builder execution
must wait for overall `status=ready`.

### G. Run both H1-H5 builder dry-runs

After overall readiness is ready, run each date-specific builder with
`--dry-run`. Dry-run may evaluate label-free membership in memory but writes
no cohort file.

Confirm:

- execution config and as-of date match;
- config and frozen digest references match;
- `provider_access=false`;
- `labels_joined=false`;
- `production_change=false`;
- no future/outcome column is present;
- all five H1-H5 groups are reported;
- zero-member groups are retained.

Member counts are execution facts only. Do not compare them with future
outcomes or use them to revise parameters.

### H. Write the label-free H1-H5 outputs

Run `--write-output` only after both dry-runs pass and are manually reviewed.
Expected output paths are:

```text
outputs/research/opportunity_cohorts_2026-09-30.csv
outputs/research/opportunity_cohorts_2026-09-30.json
outputs/research/opportunity_cohorts_2026-12-31.csv
outputs/research/opportunity_cohorts_2026-12-31.json
```

The builder must not join labels. H4-H5 remain non-blocking annotations.

### I. Freeze the no-label cohort artifacts

For every config, feature-only snapshot, and cohort output:

- record the exact path;
- compute SHA-256;
- record the config version and as-of date;
- retain metadata and member counts;
- verify generated files remain ignored and uncommitted;
- do not overwrite or regenerate after outcome inspection.

### J. Stop before evaluation

No command in this runbook creates labels or evaluates U3. After the
label-free artifacts are frozen, stop.

A separate later phase must design and approve an evaluator that joins
unchanged labels outside the builder.

## Future Command Templates: 2026-09-30

Do not run these commands before the date and manual checks are complete.

Set the source placeholder:

```powershell
$sourceSnapshot = "<SOURCE_MEMBER_LEVEL_ASOF_SNAPSHOT_2026-09-30.csv>"
```

### Feature-only dry-run

```powershell
python backend\scripts\build_feature_only_member_snapshot.py --snapshot-file $sourceSnapshot --as-of-date 2026-09-30 --outputs-dir research\inputs --drop-outcome-columns --dry-run
```

### Feature-only write-output

```powershell
python backend\scripts\build_feature_only_member_snapshot.py --snapshot-file $sourceSnapshot --as-of-date 2026-09-30 --outputs-dir research\inputs --drop-outcome-columns --write-output
```

### Combined readiness check

```powershell
python backend\scripts\check_u3_opportunity_cohort_readiness.py
```

Until the 2026-12-31 feature-only snapshot also exists, the expected overall
result is blocked. Do not proceed to builder write-output.

### H1-H5 builder dry-run

Run only after combined readiness is ready:

```powershell
python backend\scripts\build_research_opportunity_cohorts.py --snapshot-file research\inputs\member_level_asof_features_2026-09-30.csv --as-of-date 2026-09-30 --config research\configs\opportunity_cohorts.u3_2026-09-30.json --outputs-dir outputs --dry-run
```

### H1-H5 builder write-output

Run only after both date-specific dry-runs pass:

```powershell
python backend\scripts\build_research_opportunity_cohorts.py --snapshot-file research\inputs\member_level_asof_features_2026-09-30.csv --as-of-date 2026-09-30 --config research\configs\opportunity_cohorts.u3_2026-09-30.json --outputs-dir outputs --write-output
```

## Future Command Templates: 2026-12-31

Do not run these commands before the date and manual checks are complete.

Set the source placeholder:

```powershell
$sourceSnapshot = "<SOURCE_MEMBER_LEVEL_ASOF_SNAPSHOT_2026-12-31.csv>"
```

### Feature-only dry-run

```powershell
python backend\scripts\build_feature_only_member_snapshot.py --snapshot-file $sourceSnapshot --as-of-date 2026-12-31 --outputs-dir research\inputs --drop-outcome-columns --dry-run
```

### Feature-only write-output

```powershell
python backend\scripts\build_feature_only_member_snapshot.py --snapshot-file $sourceSnapshot --as-of-date 2026-12-31 --outputs-dir research\inputs --drop-outcome-columns --write-output
```

### Combined readiness check

```powershell
python backend\scripts\check_u3_opportunity_cohort_readiness.py
```

Do not continue unless the top-level status and both window statuses are
`ready`.

### H1-H5 builder dry-run

```powershell
python backend\scripts\build_research_opportunity_cohorts.py --snapshot-file research\inputs\member_level_asof_features_2026-12-31.csv --as-of-date 2026-12-31 --config research\configs\opportunity_cohorts.u3_2026-12-31.json --outputs-dir outputs --dry-run
```

### H1-H5 builder write-output

Run only after both date-specific dry-runs pass:

```powershell
python backend\scripts\build_research_opportunity_cohorts.py --snapshot-file research\inputs\member_level_asof_features_2026-12-31.csv --as-of-date 2026-12-31 --config research\configs\opportunity_cohorts.u3_2026-12-31.json --outputs-dir outputs --write-output
```

## Manual Pre-Run Checklist

Complete this checklist separately for each execution session:

- [ ] The current Git branch is the explicitly approved U3 execution branch,
  not `main`.
- [ ] `git status --short` shows no unexpected tracked modifications.
- [ ] `AGENTS.md` and `.agents/` remain untracked unless separately approved.
- [ ] `research/inputs/` and `outputs/research/` remain ignored unless an
  artifact is intentionally documented and approved.
- [ ] The intended U3 date has arrived.
- [ ] The config path matches the exact U3 date.
- [ ] The Phase 3.4 parameter digest equals
  `163b90128233383d9965c17fa2e1065c50222e4db706c93787326053ef8fca46`.
- [ ] The Phase 3.4 frozen logic digest equals
  `72d7159fb7c94c9c67fe6406e749285446b60a0c76331594ec062eb2201acdbe`.
- [ ] The source snapshot is point-in-time and contains the requested as-of
  date.
- [ ] No `latest_input_date` exceeds the as-of date.
- [ ] No U3 validation result or future-label output already exists.
- [ ] No U3 outcome has been opened or manually inspected.
- [ ] Feature-only dry-run reports every dropped outcome-column name.
- [ ] The written feature-only snapshot contains no label, target, future,
  realized, winner/loser, outcome, or benchmark-outcome column.
- [ ] Readiness uses local files only and reports `provider_access=false`.
- [ ] Combined readiness and both per-window statuses are `ready` before any
  builder command is executed.
- [ ] Builder dry-run reports `labels_joined=false`,
  `provider_access=false`, and `production_change=false`.
- [ ] Generated artifacts will remain uncommitted unless intentional artifact
  documentation is separately approved.

## Fail-Stop Conditions

Stop immediately and do not loosen a rule when:

- the U3 date has not arrived;
- the source as-of data is unavailable;
- readiness status is not `ready`;
- a feature-only snapshot is missing;
- the source contains outcome columns and
  `--drop-outcome-columns` was not explicitly intended and audited;
- the exported feature-only snapshot still contains a future, label, target,
  realized, winner/loser, outcome, or benchmark-outcome field;
- `latest_input_date > as_of_date`;
- a config checksum or frozen logic checksum differs;
- any H1-H5 parameter, role, feature binding, or missing-data rule changed;
- provider access is required;
- labels are already joined to the builder input or output;
- production scoring, ranking, factors, candidate selection, list membership,
  thresholds, or recommendation behavior changed;
- any U3 outcome was inspected before cohort membership and checksums were
  frozen;
- a dry-run fails, reports partial unsafe metadata, or omits an H1-H5 group;
- a generated path would overwrite an existing frozen artifact.

A stopped run must record the blocker. Do not select a replacement date or
change a threshold based on expected performance.

## Future Execution Record Template

Create one record per U3 date after future execution:

```text
execution_date:
operator:
git_branch:
git_commit:
u3_as_of_date:
holdout_id: u3-prospective-2026-h2-v1

source_snapshot_path:
source_snapshot_sha256:
source_latest_input_date_max:

feature_only_csv_path:
feature_only_csv_sha256:
feature_only_json_path:
feature_only_json_sha256:
feature_only_row_count:
dropped_outcome_columns:
leakage_guard_applied:

u3_config_path:
config_version:
parameter_digest:
frozen_logic_digest:
parameter_change: false
tuning_change: false
date_binding_only_change: true

readiness_status:
readiness_window_status:
readiness_checked_at:

builder_dry_run_status:
builder_dry_run_input_row_count:
builder_dry_run_output_record_count:
builder_dry_run_blockers:

cohort_json_path:
cohort_json_sha256:
cohort_csv_path:
cohort_csv_sha256:
H1_member_count:
H2_member_count:
H3_member_count:
H4_member_count:
H5_member_count:

research_only: true
provider_access: false
labels_joined: false
production_change: false
counts_are_validation_evidence: false
outputs_committed: false

notes:
```

The record may list counts as deterministic membership facts only. It must
state that counts are not validation, return evidence, or production
authorization.

## Recommended Next Phase

After both no-label U3 cohort outputs are generated, reviewed, checksummed,
and frozen, the recommended next phase is:

```text
Phase 3.6 U3 No-Label Cohort Freeze and Validation Evaluator Design
```

If the project keeps the shorter original naming, use:

```text
Phase 3.6 U3 Validation Evaluator Design
```

The evaluator must remain a separate module and command from the H1-H5
builder. It may join frozen membership to unchanged labels only after its
design, metrics, sample gates, output paths, and failure rules are committed
and explicitly approved.

## Phase Decision

Phase 3.5 documents future execution only. On 2026-07-01 both U3 dates remain
future and both feature-only snapshots remain absent, so the correct current
state is blocked.

No command template in this document is authorization to run U3 early.
