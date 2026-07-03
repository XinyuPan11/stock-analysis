# Phase 3.7.3 Historical Primary As-Of Artifacts And Source Snapshot Execution

## Purpose

Phase 3.7.3 closes the source-artifact gap identified by Phase 3.7.1 and
Phase 3.7.2. It prepares label-free factors and list-membership inputs from
local as-of research outputs, then executes the Phase 3.7.2 historical source
snapshot builder for the three primary windows.

This is an artifact-preparation phase, not validation. It does not inspect an
outcome, calculate a future return, run an evaluator, export a feature-only
snapshot, or build an H1-H5 cohort.

## Frozen Historical Contract

```text
validation_id = h1h5-historical-sealed-v1
evidence_level = historical_sealed_not_prospective
benchmark = CSI300
horizon = 20 trading days
parameter source = phase3.1-smoke-v1
parameter count = 18
production_change = false
labels_joined = false
```

The primary windows executed in this phase are:

```text
2026-01-30
2026-03-31
2026-04-30
```

The backup windows `2026-02-27` and `2026-05-29` remain inactive. The
prospective U3 windows and configs are outside this phase.

## Safe As-Of Artifact Preparation

The existing cache-only daily path successfully loaded all 300 selected
symbols from `data/cache/daily-use` for each primary date. It had no provider
object or provider fallback and applied the point-in-time cutoff before
factor calculation. Each run produced 276 factor rows after the existing
unchanged market filters.

The existing research-list JSON cannot be passed directly to the Phase 3.7.2
builder because list items include `label_reason`. Phase 3.7.3 therefore adds:

```text
backend/src/stock_analysis/research/historical_asof_artifacts.py
backend/scripts/build_historical_h1h5_asof_artifacts.py
```

The exporter:

- accepts only the three primary dates;
- consumes an explicit factors CSV and multi-list JSON;
- requires at least 100 unique, exact-date factor rows;
- copies the complete factors universe into membership;
- preserves allowlisted membership, list name, rank, score, and safe context;
- records and drops `label`, `label_reason`, `research_label`, and
  `source_label`;
- blocks any other future, outcome, target, winner/loser, realized, or label
  field;
- rejects validation, walk-forward, list-performance,
  factor-effectiveness, strategy-experiment, and future-label input paths;
- defaults to dry-run and writes only after `--write-output`;
- does not import or call provider, validation, evaluator, feature exporter,
  or H1-H5 cohort code.

For the real primary inputs, `label_reason` was the only audited unsafe field
and was removed. Thirty research-list symbols per date fell outside the exact
276-row factor universe and were ignored rather than added implicitly.

The safe outputs are:

```text
outputs/experiments/historical_h1h5_factors_<date>.csv
outputs/experiments/historical_h1h5_membership_<date>.csv
```

## Executed Workflow

For each primary date, Phase 3.7.3 ran:

1. cache-only as-of daily generation;
2. existing as-of research-view generation;
3. safe artifact dry-run for the first window and the same tested exporter
   gate for all writes;
4. safe factors/membership write-output;
5. label-free source builder dry-run;
6. source builder write-output.

The research-view command creates descriptive as-of research-label files as
part of its established output set. These are not validation labels or future
outcomes. No label field is copied into the safe artifacts or source
snapshots; `label_reason` is explicitly audited and dropped.

## Primary-Window Results

| As-of date | Cache symbols | Safe/source rows | Breakout | Accumulation | Any positive list | High risk | Future cache rows excluded |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2026-01-30 | 300 | 276 | 30 | 0 | 69 | 3 | 25,391 |
| 2026-03-31 | 300 | 276 | 30 | 0 | 77 | 3 | 15,455 |
| 2026-04-30 | 300 | 276 | 30 | 0 | 85 | 8 | 9,659 |

Zero accumulation membership is the unchanged result of the existing list
rules for these exact inputs. This phase does not tune or repair membership
by changing those rules.

For every source snapshot:

```text
provider_access = false
labels_joined = false
validation_run = false
future_labels_generated = false
future_returns_computed = false
leakage_guard_applied = true
latest_input_date_max = as_of_date
```

The source snapshot paths and SHA-256 checksums are:

```text
outputs/experiments/historical_h1h5_source_snapshot_2026-01-30.csv
7060827D73A0DB2F9C7788E88825997EAE825449623ACE4536C7585A88EB9A0B

outputs/experiments/historical_h1h5_source_snapshot_2026-03-31.csv
3A480F15077E5AB6FDCB4149C90A9A065B5BFB06473CE16845016FE7D8D697D9

outputs/experiments/historical_h1h5_source_snapshot_2026-04-30.csv
BB5937EF7596BC0EE313FCFE8D67EE7FB2739BE1833D6503CF62AC1AB84B2E69
```

Each CSV has a companion JSON at the same path stem.

## Readiness After Execution

Historical readiness was run with all three explicit primary source paths.
All primary windows advanced to:

```text
blocked_missing_feature_only_snapshot
```

This is the expected Phase 3.7.3 stopping point. Readiness confirmed matching
18-parameter and frozen-logic digests. The two inactive backups remain
`blocked_missing_source_snapshot`; no backup was activated or generated.

The readiness command returned overall `blocked` because no primary
feature-only snapshot exists. It made no file and performed no provider,
label, outcome, or validation access.

## Generated File Policy

All generated daily, label, list, search, safe-artifact, and source-snapshot
outputs remain under the ignored `outputs/` tree and must not be committed.
Only the exporter code, CLI, tests, and this execution record are commit
candidates.

No file matching a historical feature-only snapshot or H1-H5 cohort output
was generated.

## Why This Is Not Validation

The executed chain is limited to information available at or before each
as-of date. Later physical cache rows are counted and excluded. The chain
does not open validation predictions, future-label artifacts, evaluator
outputs, list performance, factor effectiveness, or strategy experiments.
It emits no performance metric, hypothesis verdict, or validation result.

## Verification

The new tests cover:

- primary-only date enforcement;
- audited removal of research-label fields;
- rejection of non-droppable outcome fields and forbidden input paths;
- preservation of membership, rank, score, and list context;
- full-universe membership projection;
- dry-run no-write behavior;
- fixed two-file exporter write scope;
- end-to-end consumption by the Phase 3.7.2 source builder;
- network/provider prohibition;
- absence of feature-only and cohort outputs;
- readiness recognition of the generated source shape.

The targeted historical source-builder, readiness, inventory, and new
exporter test suites are run before phase handoff.

## Next Phase Recommendation

The next separately approved phase should export feature-only snapshots from
these three source snapshots, verify their exact as-of and label-free
contract, and rerun historical readiness. It should still stop before any
historical validation or performance interpretation unless that execution is
explicitly authorized as a separate sealed phase.

## Phase Decision

Phase 3.7.3 successfully generated safe primary as-of artifacts and three
label-free historical source snapshots. It stops at the missing feature-only
snapshot gate.

No provider fetch, BaoStock execution, cache prewarm, validation, outcome
inspection, future return, validation-label generation or join, feature-only
export, H1-H5 cohort generation, parameter/config change, U3 change, or
production logic change occurred.
