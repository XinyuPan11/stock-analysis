# Phase 3.11 Historical Label-Source Readiness And Evaluator Dry-Run

## Purpose

Phase 3.11 checks whether the frozen historical H1-H5 cohorts have enough
local, provider-free data coverage to prepare explicit 20-trading-day label
sources. It also runs the Phase 3.10 evaluator schema check.

This phase does not generate a real label source, join real labels, run the
real evaluator, write final validation outputs, or analyze H1-H5
performance.

## Why A Separate Readiness Gate Is Required

Phase 3.9 froze label-free cohort membership before outcomes were opened.
Phase 3.10 defined a digest-guarded evaluator and explicit label-source
schema.

Before opening future prices, the project must still prove:

- every frozen cohort artifact is unchanged;
- the local stock cache reaches the complete 20D horizon;
- CSI300 reaches the same horizon;
- no provider or cache prewarm is needed;
- no conflicting validation output already exists;
- a proposed label source has exact identity, schema, provenance, and
  coverage metadata;
- builder-side membership fields cannot enter the label source.

Phase 3.11 adds this read-only gate in:

```text
backend/src/stock_analysis/research/historical_h1h5_label_source_readiness.py
backend/scripts/check_historical_h1h5_label_source_readiness.py
```

It also exposes a public, no-join label-source schema validator from the
Phase 3.10 evaluator.

## Historical Contract

```text
validation_id = h1h5-historical-sealed-v1
evidence_level = historical_sealed_not_prospective
horizon_days = 20
benchmark = CSI300
provider_access = false
labels_generated = false
labels_joined = false
evaluator_run = false
final_validation_outputs_written = false
production_change = false
```

Only the three primary windows are accepted. Answer-key, U1, U2, backup,
unknown, and prospective U3 dates fail closed.

## Readiness Command

The real local check was run with:

```powershell
python backend\scripts\check_historical_h1h5_label_source_readiness.py --repo-root . --cache-dir data\cache\daily-use --outputs-dir outputs
```

The command is read-only. It reads:

- Phase 3.9 cohort JSON/CSV paths and hashes;
- frozen cohort symbol identities;
- the `trade_date` column of local stock and CSI300 cache files;
- optional explicit label-source JSON metadata and schema;
- existence, but not content, of conflicting validation outputs.

It does not read stock price values, generate a return, call a provider,
open validation predictions, or write a report file.

## Frozen Cohort Verification

All six Phase 3.9 cohort files existed and matched the committed digests.

| As-of date | Frozen symbols | JSON digest match | CSV digest match | Mutation detected |
|---|---:|---|---|---|
| 2026-01-30 | 276 | yes | yes | no |
| 2026-03-31 | 276 | yes | yes | no |
| 2026-04-30 | 276 | yes | yes | no |

No historical evaluator CSV/JSON, historical summary JSON, or matching
`walk_forward_predictions_<date>_20d.csv` existed.

The readiness checker treats any such existing validation artifact as
`blocked_existing_validation_output`. It does not offer an override in this
phase.

## Local Cache Coverage

The checker determines the required future end from the twentieth CSI300
trade date after each as-of date. It then checks each frozen symbol using
only local `trade_date` values.

| As-of date | Required future end | Frozen symbols | Cache files | Temporally covered | At least 20 rows through end | Missing/short |
|---|---|---:|---:|---:|---:|---:|
| 2026-01-30 | 2026-03-09 | 276 | 276 | 276 | 276 | 0 |
| 2026-03-31 | 2026-04-29 | 276 | 276 | 276 | 276 | 0 |
| 2026-04-30 | 2026-06-02 | 276 | 276 | 276 | 276 | 0 |

CSI300 cache was covered for all three windows. Its latest local trade date
was `2026-06-24`.

No provider fetch or cache prewarm is needed for temporal coverage.

## Label-Source Requirements

A valid label source must be an explicit metadata-bearing JSON file. A CSV
alone is insufficient because it cannot carry the required identity and
coverage contract.

Metadata must record:

```text
validation_id
evidence_level
as_of_date
horizon_days
benchmark
label_window_complete
provider_access
production_change
required_future_end
cache_coverage
```

Records must follow the Phase 3.10 evaluator schema and preserve invalid or
missing labels instead of dropping symbols.

The label source must not contain builder-side fields such as:

```text
cohort_id
cohort_role
cohort_member
annotation_status
membership_reason
rank
captured_positive_lists
captured_risk_lists
is_breakout_watch
is_accumulation_watch
```

This prevents a label file from modifying or shadowing frozen membership.

Expected future paths are:

```text
outputs/experiments/historical_h1h5_label_source_2026-01-30_20d.json
outputs/experiments/historical_h1h5_label_source_2026-03-31_20d.json
outputs/experiments/historical_h1h5_label_source_2026-04-30_20d.json
```

None of these files existed during Phase 3.11.

## Readiness Result

The overall result was:

```text
status = ready_to_build_label_sources
ready = true
primary_window_count = 3
ready_to_build_count = 3
ready_for_evaluator_count = 0
blocked_window_count = 0
provider_access = false
labels_generated = false
labels_joined = false
evaluator_run = false
final_validation_outputs_written = false
```

Each primary returned `ready_to_build_label_sources`.

This status means that frozen membership and local temporal coverage are
ready. It does not mean that a compliant label file exists or that evaluator
execution is authorized.

## Why No Label-Source Builder Was Added

The Phase 3.10 evaluator requires explicit booleans for:

```text
winner
loser
severe_drawdown
right_tail
```

The repository has not yet frozen their exact historical sealed definitions
for this validation identity. Existing validation modules contain earlier
walk-forward and attribution rules, but reusing one implicitly would choose
label math without a committed Phase 3.12 contract.

Cache availability alone is not permission to invent or select those
definitions. Phase 3.11 therefore does not implement the optional real
label-source builder and does not open future price values.

## Evaluator Schema Checks

The Phase 3.10 `--schema-check-only` command was run once for each frozen
primary cohort path and committed SHA-256:

```powershell
python backend\scripts\evaluate_historical_h1h5_cohorts.py --cohort-output outputs\research\opportunity_cohorts_<DATE>.json --as-of-date <DATE> --horizon-days 20 --benchmark CSI300 --expected-cohort-sha256 <JSON_SHA256> --schema-check-only
```

All three returned:

```text
status = schema_valid
runnable = false
snapshot_loaded = false
label_source_loaded = false
labels_generated = false
outputs_written = false
```

Schema-check-only intentionally does not open the cohort or label source.
The Phase 3.11 readiness command separately verified all real frozen cohort
digests.

## Why Evaluator Dry-Run Was Not Run

Evaluator dry-run requires a safe explicit label JSON. Readiness found none:

```text
ready_for_evaluator_count = 0
```

Running the evaluator with a synthesized, legacy, or implicit label source
would violate the digest-before-label and explicit-source contracts.
Therefore no real evaluator dry-run was attempted.

## Generated File Policy

Phase 3.11 generated no label-source file, readiness report file, evaluator
output, validation prediction, or final validation artifact.

The Phase 3.9 frozen cohort hashes remain unchanged. Existing
`research/inputs` and `outputs/research` artifacts were not rewritten.

Only the readiness code, CLI, tests, Phase 3.10 public validator addition,
and this document are intended for commit.

## Why No Performance Conclusion Is Drawn

Readiness observes file identity and temporal coverage only. It does not read
future price values or calculate labels, returns, capture, contamination,
drawdown, coverage, or result statuses.

`ready_to_build_label_sources` is an engineering readiness state, not
evidence that H1-H5 works.

## Next Phase Recommendation

The next phase is:

```text
Phase 3.12 Historical Sealed Validation Execution
```

Before execution, Phase 3.12 must first commit the exact unchanged
winner/loser/right-tail/severe-drawdown definitions and the local-only label
builder contract. It should then:

1. build explicit label sources in dry-run mode;
2. review identity, required future end, cache coverage, missing labels, and
   output checksums;
3. write and freeze label-source files only after review;
4. rerun Phase 3.11 readiness to reach
   `ready_for_evaluator_dry_run`;
5. run evaluator dry-runs without output writes;
6. separately authorize final validation output generation and analysis.

## Phase Decision

Phase 3.11 confirms that all three frozen primary cohorts and their local
20D stock/CSI300 cache coverage are ready for explicit label-source
construction.

It stops at `ready_to_build_label_sources`. No real labels, evaluator
metrics, final validation outputs, provider access, cache prewarm, parameter
or config change, U3 change, frozen cohort mutation, production logic change,
or performance conclusion occurred.
