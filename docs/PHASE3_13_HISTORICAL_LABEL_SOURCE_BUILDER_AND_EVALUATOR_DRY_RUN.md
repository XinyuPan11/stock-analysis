# Phase 3.13 Historical Label Source Builder And Evaluator Dry-Run

## Purpose

Phase 3.13 implements the label-source path preregistered in Phase 3.12. It
builds explicit historical labels for the three frozen Phase 3.9 universes,
checks that the evaluator consumes the frozen schema, and executes evaluator
dry-runs without writing final validation results.

This is an execution-readiness phase. It does not analyze returns, judge H1-H5
effectiveness, tune parameters, or authorize any production change.

## Frozen Contract

```text
validation_id = h1h5-historical-sealed-v1
evidence_level = historical_sealed_not_prospective
benchmark = CSI300
horizon_days = 20
price_field = adj_close
label_definition_config = research/configs/historical_h1h5_label_definitions.v1.json
label_definition_sha256 = 98282FC01C3F2CE73C97A3A5F66CE62B8C927D27631852B15108A83499245BAF
```

The SHA is calculated from the committed LF bytes. The builder normalizes
Windows CRLF line endings to LF before hashing, so platform checkout behavior
cannot create a false mismatch. Any other byte change fails closed.

Only these frozen primary windows were used:

```text
2026-01-30
2026-03-31
2026-04-30
```

Answer-key, consumed U1/U2, backup, non-primary, and prospective U3 dates are
rejected.

## Builder

The implementation is:

```text
backend/src/stock_analysis/research/historical_h1h5_label_source.py
backend/scripts/build_historical_h1h5_label_source.py
```

The builder:

- verifies the frozen definition SHA and Phase 3.9 cohort JSON SHA before
  reading prices;
- derives the universe as the distinct symbol set from the frozen cohort
  records, without using cohort membership or role in label math;
- reads only `data/cache/daily-use/baostock/stock_daily/adjusted`;
- requires `adj_close` and never falls back to `close`;
- takes the first 20 CSI300 trading dates after the exact as-of date as the
  common calendar;
- computes the Phase 3.12 continuous metrics and frozen boolean labels;
- retains one row for every frozen symbol and preserves invalid rows with a
  reason;
- defaults to dry-run and writes only with `--write-output`;
- writes only the label-source CSV/JSON pair under `outputs/experiments`;
- has no provider, cache-prewarm, validation-prediction, cohort-builder, label
  join, or final validation output path.

An existing final historical evaluation output blocks the builder. Existing
label sources are not overwritten implicitly.

## Generated Label Sources

| As-of date | Rows | Valid | Missing | Future window |
|---|---:|---:|---:|---|
| `2026-01-30` | 276 | 276 | 0 | `2026-02-02` to `2026-03-09` |
| `2026-03-31` | 276 | 276 | 0 | `2026-04-01` to `2026-04-29` |
| `2026-04-30` | 276 | 276 | 0 | `2026-05-06` to `2026-06-02` |

Generated paths and SHA-256 digests:

| As-of date | File | SHA-256 |
|---|---|---|
| `2026-01-30` | `outputs/experiments/historical_h1h5_label_source_2026-01-30_20d.csv` | `A5E40FD7F6090D6201D9B92D10E784507B067CA8E299B56DC9D6BCB7FABC5E90` |
| `2026-01-30` | `outputs/experiments/historical_h1h5_label_source_2026-01-30_20d.json` | `047D50F4ABC8B1B3A4C940AB9E04CE49BECDFF6B7B6E5FE6EE21A8CDF17C0E7C` |
| `2026-03-31` | `outputs/experiments/historical_h1h5_label_source_2026-03-31_20d.csv` | `EEFA662B526E80BD1DE340F77B8BEFFBFBD024495136E034C6D092232ED49102` |
| `2026-03-31` | `outputs/experiments/historical_h1h5_label_source_2026-03-31_20d.json` | `7FAA9EDD7562C061222D8F6E0DE69000E4E5B13937288A1AEA1BFCC05A960DD6` |
| `2026-04-30` | `outputs/experiments/historical_h1h5_label_source_2026-04-30_20d.csv` | `DE8B88C33B528BE0EDF8046CB6C13BEBF0CD4DE0F23CB1A881E77A3DD8C91AEE` |
| `2026-04-30` | `outputs/experiments/historical_h1h5_label_source_2026-04-30_20d.json` | `911BD9509FE524706662EBBC8DC1F7617D45CEDE04240F985869E38328A659BB` |

These files are ignored by Git through the existing `outputs/` rule. No
label-source file contains cohort, rank, list, recommendation, provider, or
mutable builder-side fields.

## Readiness After Generation

The post-generation readiness command returned:

```text
status = ready_for_evaluator_dry_run
ready = true
primary_window_count = 3
ready_for_evaluator_count = 3
blocked_window_count = 0
labels_generated = true
labels_joined = false
evaluator_run = false
provider_access = false
final_validation_outputs_written = false
```

Each window had 276 label rows, 276 valid labels, zero missing frozen symbols,
safe schema status, matching Phase 3.9 JSON/CSV digests, and no existing final
historical evaluation output.

## Evaluator Schema Adaptation

The evaluator now requires the exact Phase 3.12 columns. Legacy aliases such
as `data_quality`, `future_return`, `benchmark_future_return`, `excess_return`,
and `max_drawdown_during_holding` are not required or duplicated.

JSON label sources remain supported. When a CSV is supplied, the evaluator
requires its same-stem JSON, verifies the CSV SHA recorded in that metadata,
then validates the exact frozen schema and formula relationships. Forbidden
membership, list, rank, recommendation, provider, or builder fields fail
closed.

All three schema-check-only executions returned `status=schema_valid`, loaded
no cohort or label source, and wrote no output.

## Evaluator Dry-Run

All three primary windows returned:

```text
status = evaluator_dry_run_complete
dry_run = true
outputs_written = false
performance_results_exposed = false
provider_access = false
labels_joined_by_evaluator = true
builder_labels_joined = false
cohort_digest_verified = true
cohort_membership_mutated = false
universe_symbol_count = 276
label_row_count = 276
```

Empty and underpowered cohort states remained visible as structural readiness
metadata. The dry-run CLI deliberately omitted cohort performance rows,
returns, winner capture, loser contamination, and investment conclusions.

No file matching `outputs/validation/historical_h1h5_*` was created.

## Test Coverage

Targeted tests cover:

- definition SHA mismatch;
- primary, consumed, and U3 date gates;
- exact `adj_close` use with no `close` fallback;
- complete common 20-day CSI300 horizon;
- synthetic continuous metric math;
- deterministic winner/loser, right-tail, and severe-drawdown labels;
- winner/loser conflict rejection;
- missing-label preservation;
- default no-write and label-pair-only writing;
- exact schema and forbidden-field rejection;
- readiness detection after generation;
- evaluator CSV/JSON frozen-schema compatibility;
- evaluator dry-run no-write behavior;
- no provider/network call.

## Evidence Boundary

Phase 3.13 generated outcome-bearing label sources, but it did not interpret
them. No H1-H5 result is classified as supported, mixed, not confirmed, or
effective in this phase. No return or cohort performance conclusion is drawn.

Production scoring, ranking, factors, candidate selection, list membership,
thresholds, recommendations, H1-H5 parameters, feature bindings, cohort roles,
U3 configs, and frozen Phase 3.9 cohort outputs remain unchanged.

## Next Phase

The recommended next phase is:

```text
Phase 3.14 Historical Sealed Validation Execution and Result Analysis
```

Phase 3.14 may run explicitly authorized evaluator write-output, retain all
empty and underpowered windows, analyze each window before any pooled summary,
and report only research-level conclusions. It must continue to keep this
historical evidence separate from prospective U3.
