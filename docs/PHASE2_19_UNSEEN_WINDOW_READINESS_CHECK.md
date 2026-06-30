# Phase 2.19 Unseen Window Readiness Check

## Purpose

Phase 2.19 checks whether the proposed Phase 2.18 U1 windows are technically
ready for a later controlled validation run. It is readiness only, not
validation.

The checker does not calculate labels, recompute returns, open prediction
rows, summarize list performance, identify winners or losers, or evaluate any
Phase 2.17 hypothesis. Provider access remains false.

## Proposed U1 Candidate Pool

The checker is deliberately fixed to:

```text
2024-02-29 20D
2024-05-31 20D
2024-08-30 20D
2024-11-29 20D
```

These dates are proposed candidates. A ready result does not select U1 or U2
and does not consume a window. Final U1/U2 assignment must be recorded and
committed before any validation output is generated.

## Permanently Forbidden Proof Windows

The original answer-key diagnostic windows remain forbidden as proof:

```text
2024-01-31 20D
2024-04-30 20D
2024-07-31 20D
2024-10-31 20D
```

The checker rejects these dates at the candidate-validation boundary.

## What Is Inspected

For each proposed U1 date, the checker reads only technical prerequisites:

- required historical as-of file presence
- symbol identifiers from as-of labels, factors, and list membership
- stock cache date bounds through the as-of date and required future end
- benchmark cache date bounds using established aliases
- validation output presence or absence without opening prediction rows
- whitelisted point-in-time/leakage metadata from an existing summary, if one
  already exists
- member-level snapshot prerequisite availability

It records the Phase 2.10 contract:

```text
feature window: trade_date <= as_of_date
label window: trade_date > as_of_date, explicit validation labels only
```

It does not inspect outcome columns or performance values.

## What Ready Means

`ready_for_dry_run` means:

- the date is in the frozen Phase 2.18 candidate pool
- all required historical as-of outputs exist
- a non-empty symbol set can be derived without prediction files
- every selected stock cache reaches the as-of date and buffered future end
- benchmark cache reaches both required dates
- no prior validation output exists for the proposed sealed window
- no provider fetch is needed

This proves technical feasibility only. It is not evidence about list,
hypothesis, or model quality.

Missing validation outputs are expected before evaluation. Per-window
point-in-time and leakage metadata become verifiable only after the future
controlled dry-run/write-output path. Their required contract is shown in the
readiness report.

## Statuses

- `ready_for_dry_run`: local prerequisites are ready.
- `blocked_missing_as_of_outputs`: labels, factors, or list files are missing.
- `blocked_missing_symbols`: no safe as-of symbol set is available.
- `blocked_stock_cache`: stock cache is missing or stale for a required date.
- `blocked_benchmark_cache`: benchmark cache does not cover required dates.
- `blocked_existing_unseen_outputs`: the sealed-window state must be audited
  because one or more validation outputs already exist.

The November window has a buffered future end in 2025. The readiness checker
may inspect local cache date bounds for that planned window, but it does not
fetch data or execute validation. Any Phase 2.18 policy deferral remains a
stop condition until explicitly resolved before U1 selection.

## Run

This command is local-only:

```powershell
python backend\scripts\check_unseen_window_readiness.py --outputs-dir outputs --cache-dir data\cache\daily-use --provider baostock --benchmark CSI300 --limit 300 --write-output
```

Expected outputs:

```text
outputs/experiments/unseen_window_readiness_2024.json
outputs/experiments/unseen_window_readiness_2024.md
```

The reports are ignored operational outputs and should not be committed.

## Later Manual Validation

Only after U1/U2 dates and hypothesis definitions are committed, a ready date
may first use the controlled dry-run command shown in its readiness report:

```powershell
python backend\scripts\run_controlled_validation_batch.py --as-of-date <frozen-U1-date> --horizon-days 20 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 300
```

Do not add `--write-output` until the dry-run passes and the operator confirms
that opening the selected U1 date is intentional.

## Stop Conditions

Stop when:

- an answer-key window is supplied
- any required historical as-of output is missing
- symbol extraction is empty
- stock or benchmark cache is incomplete
- a provider fetch would be required
- unexpected validation outputs already exist
- point-in-time or leakage metadata later fails verification
- someone proposes threshold changes after seeing U1

Blocked readiness is an infrastructure finding, not a hypothesis result.

## Guardrails

- Proposed U1 outcomes were not inspected.
- No labels or future returns were computed.
- No list performance, winner capture, loser contamination, or hypothesis
  performance was calculated.
- No BaoStock request, prewarm, full workflow, or long validation ran.
- Production scoring, ranking, factors, validation math, candidate selection,
  lists, thresholds, and recommendation behavior remain unchanged.
