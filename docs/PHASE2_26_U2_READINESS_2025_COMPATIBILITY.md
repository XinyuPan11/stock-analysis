# Phase 2.26 U2 Readiness 2025 Compatibility

## Purpose

Phase 2.26 extends the existing technical-only unseen-window readiness checker
to the four Phase 2.25 preregistered U2 windows:

```text
2025-02-28 20D
2025-05-30 20D
2025-08-29 20D
2025-11-28 20D
```

This phase checks infrastructure readiness only. It does not generate as-of
research outputs, calculate labels or returns, run validation, open U2
prediction or performance files, evaluate hypotheses, or access a provider.
U2 results remain sealed.

## Root Cause

The Phase 2.19 checker encoded its 2024 U1 scope directly in four places:

- `PROPOSED_U1_WINDOWS` was the only selectable window collection;
- candidate validation rejected every date outside that collection;
- report metadata and Markdown wording were U1-specific;
- output paths were fixed to `unseen_window_readiness_2024.*`.

The older multi-as-of planner also retains `MULTI_ASOF_YEAR = 2024`, but the
dedicated unseen-window readiness checker does not need that planner to verify
its technical contract. Phase 2.26 therefore adds a versioned explicit window
set to the dedicated checker instead of changing the historical Phase 2.8
planner's semantics.

## Window Sets

The CLI now accepts:

```text
--window-set u1-2024
--window-set u2-2025
```

`u1-2024` remains the default and preserves Phase 2.19 behavior and output
names.

`u2-2025` contains exactly the four Phase 2.25 preregistered dates. It excludes
both permanently forbidden answer-key windows and all consumed U1 windows.
An arbitrary date cannot be supplied through this interface.

## Evidence Boundary

Permanently forbidden proof windows:

```text
2024-01-31 20D
2024-04-30 20D
2024-07-31 20D
2024-10-31 20D
```

Consumed U1 windows, unavailable for sealed U2 confirmation:

```text
2024-02-29 20D
2024-05-31 20D
2024-08-30 20D
2024-11-29 20D
```

Candidate validation rejects either group for the U2 window set before any
cache or output-content inspection can affect date selection.

## Technical-Only Contract

For each selected U2 window, the checker evaluates only:

- required historical as-of file presence;
- symbols derived from as-of labels, factors, and list membership;
- local stock cache bounds through the as-of date and required future end;
- local CSI300 benchmark cache bounds using established aliases;
- validation output presence, without opening prediction rows or performance
  fields;
- member-level snapshot prerequisite presence;
- the expected point-in-time and bias metadata contract for a later run;
- whether any provider fetch would be required.

The required future end continues to use
`recommended_target_end_date(as_of_date, horizon_days)`. No raw calendar offset
or outcome-dependent date selection is introduced.

If any validation output already exists for a sealed U2 window, readiness
returns `blocked_existing_unseen_outputs`. The checker records presence only
and does not open the summary or its outcome fields.

The report always states:

```text
readiness_only = true
provider_access = false
provider_fetch_executed = false
labels_calculated = false
future_returns_recomputed = false
outcomes_inspected = false
performance_metrics_computed = false
production_logic_changed = false
```

## Readiness Statuses

- `ready_for_dry_run`: all local technical prerequisites are present.
- `blocked_missing_as_of_outputs`: required labels, factors, or lists are
  missing. The checker does not generate them.
- `blocked_missing_symbols`: no non-empty as-of symbol set is available.
- `blocked_stock_cache`: local stock cache does not cover the required dates.
- `blocked_benchmark_cache`: local benchmark cache does not cover the required
  dates.
- `blocked_existing_unseen_outputs`: the sealed state must be audited without
  opening outcome content.

A blocked status is an infrastructure finding, not a hypothesis result. Do not
replace a blocked window based on expected or observed performance.

## Future Manual Command

Run only when the user intentionally starts the U2 readiness review:

```powershell
python backend\scripts\check_unseen_window_readiness.py `
    --window-set u2-2025 `
    --outputs-dir outputs `
    --cache-dir data\cache\daily-use `
    --provider baostock `
    --benchmark CSI300 `
    --limit 300 `
    --write-output
```

The command writes:

```text
outputs/experiments/u2_window_readiness_2025.json
outputs/experiments/u2_window_readiness_2025.md
```

It does not overwrite the U1 reports:

```text
outputs/experiments/unseen_window_readiness_2024.json
outputs/experiments/unseen_window_readiness_2024.md
```

## Expected First Result

If the 2025 as-of labels, factors, and lists have not yet been generated, the
expected safe result is `blocked_missing_as_of_outputs` for those windows.
That result confirms the checker is fail-closed. It is not authorization to
run a provider-capable daily workflow.

As-of generation remains a separate, explicit future manual step through the
Phase 2.21 fail-closed cache-only path. Validation remains a later phase after
readiness passes and opening U2 is explicitly approved.

## Guardrails

- Do not run BaoStock or any provider fetch.
- Do not run validation, prewarm, or the full workflow.
- Do not generate U2 candidates, factors, labels, or lists in this phase.
- Do not open U2 future-return, list-performance, factor-effectiveness,
  portfolio, winner/loser, or hypothesis-result content.
- Do not change scoring, ranking, factors, validation math, candidate
  selection, production lists, thresholds, or recommendation behavior.
- Do not use readiness status as model-quality evidence.
- Keep U2 sealed until the separately approved execution phase.

## Tests

Targeted deterministic coverage verifies:

- the U2 set contains exactly the four preregistered 2025 windows;
- consumed U1 and forbidden answer-key windows are rejected;
- a fully cached U2 fixture is not deferred by the legacy 2024 policy;
- missing as-of outputs block without generation or provider access;
- unexpected validation summaries are presence-checked but not opened;
- readiness reports contain no performance metric fields;
- U1 default behavior and filenames remain compatible;
- U2 output paths are separate from U1 paths.

## Phase Decision

Phase 2.26 makes the frozen U2 manifest technically checkable without changing
its sealed state. It does not establish that any U2 window is ready on the
user's real cache, because the real readiness command was not run in this
phase.
