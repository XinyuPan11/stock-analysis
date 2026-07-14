# Phase 3.12 Historical Sealed Label Definition Preregistration

## Purpose

Phase 3.12 freezes the label-source contract for
`validation_id=h1h5-historical-sealed-v1` before any historical label is
generated or joined. It is a reference and governance phase only.

Phase 3.11 established that local cache coverage is temporally sufficient for
the three frozen Phase 3.9 primary windows, but correctly stopped before label
generation. The evaluator required `winner`, `loser`, `severe_drawdown`, and
`right_tail`, while no committed contract specified their exact definitions.
Cache readiness was not permission to choose label math after cohort
membership was visible.

This phase therefore creates a non-output, machine-checkable definition file:

```text
research/configs/historical_h1h5_label_definitions.v1.json
```

It contains formulas and governance only. It contains no symbols, prices,
labels, returns, cohort results, or validation results.

## Frozen Identity And Evidence Boundary

```text
schema_version = historical-h1h5-label-definitions-v1
validation_id = h1h5-historical-sealed-v1
evidence_level = historical_sealed_not_prospective
benchmark = CSI300
horizon_days = 20
primary_windows = 2026-01-30, 2026-03-31, 2026-04-30
```

Only the three Phase 3.9 frozen primary windows are eligible. Answer-key
dates, consumed U1/U2 dates, prospective U3 dates `2026-09-30` and
`2026-12-31`, backup dates, and newly discovered dates are not eligible.
Historical sealed evidence remains separate from and weaker than prospective
U3 evidence.

## Price And Trading-Calendar Convention

The only permitted price field is `adj_close`. The project generally prefers
`adj_close` and can fall back to `close` in legacy future-return utilities,
but this contract disables that fallback to remove field ambiguity. Missing
`adj_close`, conflicting price fields, non-finite prices, and prices not
strictly greater than zero fail closed.

CSI300 supplies the common trading calendar. The label horizon is the first
20 CSI300 trading dates strictly after the as-of date. A symbol and CSI300
must each have `adj_close` on the exact as-of date and all 20 common future
dates. A symbol suspension or cache gap is not replaced by a later
symbol-specific row; the row remains present with `valid_label=false`.

This common-calendar rule is intentionally stricter than the legacy helper's
"first 20 rows per instrument" behavior. It ensures every stock return and
the benchmark return use identical endpoints.

## Frozen Continuous Metrics

Let:

- \(P_0\) be the symbol's `adj_close` on the exact as-of date;
- \(P_t\), \(t=1,\ldots,20\), be its `adj_close` on the 20 frozen CSI300
  future trading dates;
- \(B_0\) and \(B_{20}\) be CSI300 `adj_close` on the same start and end
  dates;
- \(R_t=\max(P_0,P_1,\ldots,P_t)\).

The definitions are:

| Field | Frozen definition |
|---|---|
| `as_of_close` | \(P_0\) |
| `future_end_close` | \(P_{20}\) |
| `future_return_20d` | \(P_{20}/P_0-1\) |
| `benchmark_return_20d` | \(B_{20}/B_0-1\) |
| `excess_return_20d` | `future_return_20d - benchmark_return_20d` |
| `max_future_close_20d` | \(\max(P_1,\ldots,P_{20})\); entry is excluded |
| `min_future_close_20d` | \(\min(P_1,\ldots,P_{20})\); entry is excluded |
| `max_upside_20d` | `max_future_close_20d / as_of_close - 1` |
| `max_drawdown_20d` | \(\min_{t=0,\ldots,20}(P_t/R_t-1)\); entry is included in the path |
| `valid_label` | `true` only if identity, date, schema, cache, price, complete common-calendar horizon, and benchmark gates all pass |
| `missing_label_reason` | empty string for a valid row; otherwise the first frozen failure reason below |

The missing-reason priority is:

```text
price_field_ambiguity
missing_benchmark_data
missing_symbol_cache
missing_as_of_price
incomplete_20d_horizon
missing_future_path_price
missing_future_end_price
nonpositive_or_nonfinite_price
identity_or_schema_mismatch
```

Invalid rows are preserved. Their continuous metrics and boolean labels are
null; they are never silently dropped or converted to zero.

## Frozen Boolean Labels

All cross-sectional calculations use only `valid_label=true` rows from one
primary window. No cohort membership, list membership, rank, recommendation,
or H1-H5 assignment may enter a label calculation.

### `winner`

For each of `future_return_20d` and `excess_return_20d`:

1. let \(n\) be the valid-label count;
2. set tail count to
   `min(max(10, ceil(0.10*n)), max(1, floor(n/2)))`;
3. sort metric descending, then `symbol` ascending as the deterministic
   tie-break;
4. select the first tail-count rows.

`winner=true` is the union of the two selected upper tails. This reuses the
project's existing 10% winner-union attribution semantics and minimum group
size. Because one CSI300 return is shared by the entire window,
`excess_return_20d` is a constant shift of `future_return_20d`; the two
rankings should coincide. Any implementation producing a row that is both
winner and loser must fail closed.

### `loser`

The count rule is identical and symmetric to `winner`. Sort each metric
ascending, then `symbol` ascending, select the lower tails, and take their
union. This reuses the existing loser-union attribution semantics.

### `severe_drawdown`

```text
severe_drawdown = max_drawdown_20d <= -0.20
```

The threshold is inclusive. The -20% boundary is an existing project
failure-risk reporting boundary and is frozen here as a neutral risk
definition, not selected from H1-H5, U1/U2, answer-key, or Phase 3.9 results.

### `right_tail`

Compute the 80th percentile of `future_return_20d` across valid rows using
linear interpolation:

```text
right_tail = future_return_20d >= percentile_80
```

The threshold is inclusive, so ties at the threshold are retained. This
reuses the existing future-return top-20% convention. It is deliberately
different from the narrower winner tail: `right_tail` measures broad upside
retention, while `winner` preserves the established winner/loser attribution
contract.

## Future Label-Source Schema

Phase 3.13 may create one CSV and one JSON per primary window:

```text
outputs/experiments/historical_h1h5_label_source_<as_of_date>_20d.csv
outputs/experiments/historical_h1h5_label_source_<as_of_date>_20d.json
```

The row schema is exact and ordered:

```text
validation_id
evidence_level
as_of_date
horizon_days
benchmark
symbol
valid_label
missing_label_reason
as_of_close
future_end_close
future_return_20d
benchmark_return_20d
excess_return_20d
max_future_close_20d
min_future_close_20d
max_upside_20d
max_drawdown_20d
winner
loser
severe_drawdown
right_tail
label_future_rows_used_count
label_window_start_date
label_window_end_date
price_field
```

The JSON must carry the same records and identity metadata. One unique row is
required for every symbol in the frozen universe, including invalid/missing
labels. `label_future_rows_used_count` must equal 20 for valid labels,
`price_field` must equal `adj_close`, and the start/end dates must match the
common CSI300 calendar.

No extra columns are allowed. This explicitly excludes cohort IDs, roles,
membership or assignment fields, ranks, list membership, H1-H5 assignments,
recommendations, provider/source fields, builder scores or decisions, and any
other mutable builder-side field.

The Phase 3.10 evaluator currently uses legacy aliases such as
`future_return`, `benchmark_future_return`, `excess_return`,
`max_drawdown_during_holding`, and `data_quality`. Phase 3.13 must update its
explicit label adapter/schema guard to the frozen names above before any
evaluator dry-run. A builder must not emit duplicate legacy and new fields to
work around that boundary.

## Generation Guardrails

- Read local cache only; no provider import, fetch, BaoStock call, or cache
  prewarm is permitted.
- Use no validation prediction, future prediction, or cohort output as a
  label-generation input.
- Require the full common 20-trading-day horizon and complete CSI300 coverage.
- Preserve missing labels and their first-priority reason.
- Build labels independently of frozen Phase 3.9 cohort membership.
- Never mutate or rewrite the frozen cohort artifacts.
- Keep label sources under `outputs/experiments`, separate from cohort outputs
  and later evaluation outputs.
- Generate and review the label source before evaluator write-output.
- Join labels only inside the separate evaluator, by symbol, after frozen
  cohort digest verification.
- Keep `research_only=true`, `provider_access=false`,
  `labels_joined_by_builder=false`, and `production_change=false`.

## Fail-Closed Rules

Phase 3.13 must stop without label or evaluation output if any of these occurs:

- incomplete 20-date horizon or a missing future price;
- missing or incomplete CSI300 data;
- a required symbol cache is missing;
- `adj_close` is absent, ambiguous, non-finite, or nonpositive;
- formulas, thresholds, dates, schema, or guardrails differ from the committed
  definition config;
- a cohort, list, rank, recommendation, provider, or mutable builder field is
  present in a label source;
- provider access or a cache fill would be required;
- an answer-key, consumed U1/U2, prospective U3, backup, or unregistered date
  is requested;
- the Phase 3.9 frozen cohort digest differs from its ledger value;
- one row is both winner and loser;
- a final evaluation output already exists and no later phase supplies an
  explicit, audited override.

Technical missingness produces an invalid preserved row only when the
contract explicitly permits row-level missingness. Identity drift,
definition drift, provider access, prohibited dates, cohort digest mismatch,
or pre-existing final outputs block the entire execution.

## Why This Phase Generates No Labels Or Validation

Opening price outcomes while selecting definitions would collapse
preregistration into retrospective tuning. Phase 3.12 therefore does not read
future cache values, generate label CSV/JSON, join labels, run an evaluator
dry-run, write validation output, inspect real outcomes, or compute H1-H5
results. It also changes no cohort config, U3 config, frozen membership,
production score, rank, factor, candidate selection, list rule, threshold, or
recommendation.

The schema validator added here parses the definition contract and rejects
drift. It contains no price-cache loader and no provider path.

## Next Phase

The recommended next phase is:

```text
Phase 3.13 Historical Sealed Label Source Builder and Dry-Run
```

Phase 3.13 should implement a local-cache-only builder against this exact
contract, first run schema/math tests with synthetic fixtures, then generate
the three real label sources under explicit authorization. It should align
the evaluator's label adapter, verify frozen cohort digests before opening
labels, and perform only a dry-run before any separately authorized
write-output.
