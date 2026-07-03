# Phase 3.10 Historical Sealed Evaluator Design And Label-Join Guard

## Purpose

Phase 3.10 adds a separate evaluator framework for the frozen historical
H1-H5 cohorts. It defines how a later phase may verify a frozen cohort,
open an explicit label source, join labels without changing membership, and
produce guarded research metrics.

This phase uses synthetic fixtures only. It does not run the evaluator
against real historical labels, calculate real future returns, or create
historical validation outputs.

## Why The Evaluator Is Separate

The evaluator is implemented in:

```text
backend/src/stock_analysis/research/historical_h1h5_evaluator.py
backend/scripts/evaluate_historical_h1h5_cohorts.py
```

It is separate from:

- the opportunity cohort builder;
- the feature-only exporter;
- the historical source snapshot builder;
- the research API/UI loader;
- the existing walk-forward and future-return generators.

The module does not import any of those execution paths. The builder remains
label-free and cannot call the evaluator. The evaluator consumes an already
frozen cohort artifact and never writes back into it.

## Historical Identity

```text
validation_id = h1h5-historical-sealed-v1
evidence_level = historical_sealed_not_prospective
benchmark = CSI300
horizon = 20 trading days
minimum valid labels per cohort = 20
production_change = false
builder_labels_joined = false
```

Only these primary dates are accepted:

```text
2026-01-30
2026-03-31
2026-04-30
```

Answer-key, U1, U2, U3, unknown, and backup dates fail before evaluation.

## Schema-Check-Only

The file-free schema command is:

```powershell
python backend\scripts\evaluate_historical_h1h5_cohorts.py --schema-check-only
```

It prints:

- accepted dates, horizon, benchmark, and identity;
- the exact H1-H5 cohort IDs;
- required label fields;
- required output fields;
- result statuses;
- future output path patterns;
- the digest-before-label-load rule.

It does not load a cohort, label source, provider, builder, or output path.

## Explicit Evaluator Inputs

Normal execution requires every input to be named:

```text
--cohort-output
--as-of-date
--horizon-days
--benchmark
--label-source
--expected-cohort-sha256
--outputs-dir
```

The cohort input must be the metadata-bearing JSON frozen in Phase 3.9.
The expected SHA-256 must come from the committed Phase 3.9 freeze record.

The label source must be a separate metadata-bearing JSON. There is no
implicit path lookup, provider fallback, cache lookup, or walk-forward
prediction fallback.

Future dry-run pattern:

```powershell
python backend\scripts\evaluate_historical_h1h5_cohorts.py --cohort-output <FROZEN_COHORT_JSON> --as-of-date <PRIMARY_DATE> --horizon-days 20 --benchmark CSI300 --label-source <EXPLICIT_LABEL_JSON> --expected-cohort-sha256 <FROZEN_SHA256> --outputs-dir outputs --dry-run
```

Phase 3.10 does not execute this command with real Phase 3.9 labels.

## Frozen Cohort Safety Validation

Before a label source is loaded, the evaluator:

1. accepts only a primary historical date;
2. requires a valid explicit SHA-256;
3. hashes the frozen JSON and requires an exact match;
4. parses the JSON only after the digest matches;
5. verifies `research_only=true`;
6. verifies `provider_access=false`;
7. verifies `labels_joined=false`;
8. verifies `production_change=false`;
9. requires `validation_id` or the Phase 3.9 `holdout_id` to equal
   `h1h5-historical-sealed-v1`;
10. requires exactly the frozen H1-H5 IDs and roles;
11. requires one row per symbol and cohort;
12. requires every cohort to evaluate the same frozen universe;
13. rejects prejoined label or outcome fields recursively.

The digest is checked again immediately before the label join. A cohort file
changed after initial verification is blocked.

Forbidden prejoin fields include:

```text
future_return
benchmark_future_return
future_excess_return
excess_return
label
target
outcome
winner
loser
realized_return
holding_period
max_drawdown_during_holding
max_future*
min_future*
```

The existing physical-cache diagnostic
`future_rows_excluded_count` remains allowed because it records excluded
rows, not a future outcome.

## Explicit Label Source Schema

Label-source metadata must contain:

```text
validation_id = h1h5-historical-sealed-v1
evidence_level = historical_sealed_not_prospective
as_of_date = exact primary date
horizon_days = 20
benchmark = CSI300
label_window_complete = true
provider_access = false
production_change = false
```

Each label record defines:

```text
symbol
as_of_date
horizon_days
benchmark
data_quality
future_return
benchmark_future_return
excess_return
winner
loser
severe_drawdown
right_tail
max_drawdown_during_holding
label_future_rows_used_count
```

A valid label has `data_quality=ok`, finite numeric outcomes, valid booleans,
and `label_future_rows_used_count=20`. A row cannot be both winner and loser.

Symbols missing from the label source are retained by the left join and
counted as missing. Invalid or incomplete label rows are also counted as
missing rather than silently removed. Label symbols outside the frozen
universe are rejected.

Phase 3.10 defines this contract but does not generate a real label source.

## Label-Join Guardrails

- The cohort digest must pass before the CLI opens the label file.
- The label source path is always explicit.
- The source metadata and every valid row must match the 20D/CSI300 contract.
- Labels join by symbol only after membership is frozen.
- The evaluator compares symbol, cohort ID, role, and membership before and
  after the join.
- Any membership change returns `invalid_execution`.
- Missing labels remain in counts.
- Empty cohorts remain in output.
- Cohorts below 20 valid labels remain visible as `underpowered`.
- The evaluator never overwrites cohort or feature artifacts.
- No provider, builder, recommendation, or production authorization path
  exists.

## Evaluator Output Schema

Each output row represents one H1-H5 cohort for one primary window:

```text
validation_id
evidence_level
as_of_date
horizon
benchmark
cohort_name
cohort_role
member_count
valid_label_count
missing_label_count
winner_count
loser_count
winner_capture
loser_contamination
severe_drawdown_incidence
benchmark_excess_return
benchmark_excess_return_median
right_tail_retention
false_warning_rate
coverage
empty_cohort_rate
underpowered
result_status
caveats
labels_joined_by_evaluator
builder_labels_joined
production_change
```

Future output paths are:

```text
outputs/validation/historical_h1h5_evaluation_<as_of_date>_20d.json
outputs/validation/historical_h1h5_evaluation_<as_of_date>_20d.csv
outputs/validation/historical_h1h5_summary_h1h5-historical-sealed-v1.json
```

The module implements the per-window CSV/JSON writer for later explicit use.
The cross-window summary path is reserved by the schema contract; Phase 3.10
does not write any of these files.

## Metric Definitions

| Metric | Definition |
|---|---|
| Member count | Frozen `cohort_member=true` symbols |
| Valid label count | Members with complete, valid 20D labels |
| Missing label count | Member count minus valid label count |
| Winner count | Valid cohort labels with `winner=true` |
| Loser count | Valid cohort labels with `loser=true` |
| Winner capture | Cohort winners divided by all valid-universe winners |
| Loser contamination | Cohort losers divided by valid cohort labels |
| Severe drawdown incidence | Severe-drawdown members divided by valid cohort labels |
| Benchmark excess return | Mean explicit `excess_return` among valid cohort labels |
| Benchmark excess return median | Median explicit `excess_return` |
| Right-tail retention | Cohort right-tail members divided by valid-universe right-tail members |
| False warning rate | For H4/H5, warned valid members that are winner or right-tail divided by warned valid members |
| Coverage | Valid labels divided by frozen members |
| Empty cohort rate | Empty H1-H5 cohorts divided by five for the window |
| Underpowered | Valid label count below 20 |

Metric calculations consume explicit labels. They do not redefine winner,
loser, severe-drawdown, or right-tail label math.

## Result Statuses

The allowed statuses are:

```text
supported_research_only
mixed_research_only
not_confirmed
underpowered
invalid_execution
```

The framework automatically marks cohorts below the frozen 20-label gate as
`underpowered`. Until a later phase freezes interpretation rules, an
adequately powered synthetic result uses the conservative
`mixed_research_only` default rather than claiming support.

No status authorizes a production or recommendation change.

## Synthetic Verification

Synthetic tests cover:

- safe label-free cohort acceptance;
- required output schema and metrics;
- digest mismatch and post-verification mutation;
- prejoined future/label/outcome rejection;
- unsafe metadata rejection;
- unknown cohort and identity rejection;
- consumed and U3 date rejection;
- complete 20D label-window enforcement;
- missing-label accounting;
- empty and underpowered cohort retention;
- membership immutability;
- provider and builder non-invocation;
- dry-run no-write behavior;
- schema-check-only without real files;
- future per-window output filenames.

The three real Phase 3.9 cohort JSON files were checked only through the
digest and label-free cohort-input gate. No real label source was loaded and
no metric was calculated from those real artifacts.

## Why Phase 3.10 Does Not Run Validation

This phase creates code, schemas, and synthetic tests. It does not open a
real future outcome, generate a label, join a real label, calculate a real
historical metric, or write into `outputs/validation`.

The frozen Phase 3.9 cohort files remain unchanged.

## Next Phase Recommendation

The next phase is:

```text
Phase 3.11 Historical Sealed Evaluator Dry-Run and Label Source Readiness
```

Phase 3.11 should audit the proposed label source, its provenance, exact
20-trading-day coverage, unchanged label definitions, frozen cohort
checksums, and contamination status. It may run a real evaluator dry-run only
after those gates pass and only under separate authorization.

## Phase Decision

Phase 3.10 provides a separate fail-closed evaluator and label-join boundary
without running historical sealed validation.

No provider access, BaoStock execution, cache prewarm, real future-label
generation or join, real outcome inspection, cohort regeneration, parameter
or config change, U3 change, frozen artifact mutation, production logic
change, or validation output generation occurred.
