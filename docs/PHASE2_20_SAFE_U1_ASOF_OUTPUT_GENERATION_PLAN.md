# Phase 2.20 Safe U1 As-Of Output Generation Plan

## Purpose

Phase 2.20 defines a safe, documentation-first procedure for creating the
historical as-of artifacts required by the Phase 2.18 proposed U1 windows.
It does not generate those artifacts and does not run validation.

The proposed U1 candidate pool is:

```text
2024-02-29 20D
2024-05-31 20D
2024-08-30 20D
2024-11-29 20D
```

Phase 2.19 classified all four windows as
`blocked_missing_as_of_outputs`. This is an infrastructure blocker, not a
hypothesis result.

## Evidence Boundary

Generating point-in-time research inputs is allowed before evaluation because
the generation step does not answer whether a list, factor, or hypothesis
performed well. It only reconstructs what the research system could have
known at each as-of date.

Outcome evaluation is a separate irreversible step. Opening predictions,
future-return labels, list performance, factor effectiveness, winner/loser
tails, or hypothesis reports consumes the unseen status of a window.

Phase 2.20 therefore permits planning for:

- cache-only candidate and factor generation through the as-of date
- as-of research labels and list artifacts derived from those inputs
- presence checks, provenance checks, and readiness checks

Phase 2.20 does not permit:

- walk-forward or controlled validation
- future-return label calculation
- prediction output generation
- list-performance or factor-effectiveness generation
- strategy-family or aggressive-filter experiments
- member-level snapshot generation from prediction files
- any outcome or hypothesis interpretation

## Permanently Forbidden Proof Windows

The following answer-key diagnostic windows remain permanently forbidden as
proof:

```text
2024-01-31 20D
2024-04-30 20D
2024-07-31 20D
2024-10-31 20D
```

They must never appear in a Phase 2.20 generation loop.

## Current Command Audit

### `run_daily_research.py`

This script is relevant because it can write:

```text
outputs/daily/candidates_<date>.csv
outputs/daily/candidates_<date>.json
outputs/daily/factors_<date>.csv
outputs/daily/factors_<date>.json
outputs/daily/factor_explanations_<date>.csv
outputs/daily/factor_explanations_<date>.json
outputs/daily/summary_<date>.json
```

It is not approved for U1 generation in its current form.

The script constructs a real `BaoStockProvider`, `AkShareProvider`, or
`TushareProvider`. `MarketDataService` uses cache first but calls the provider
when stock-universe or date-range coverage is missing. The CLI has no hard
`--cache-only` or `--no-provider-fallback` switch.

Even when current cache coverage appears complete, the command cannot prove
that provider access is impossible. Do not run it for U1 until a separate
phase adds and tests a fail-closed cache-only path.

### `generate_research_views.py`

This script is approved as a local-only second-stage command after safe daily
inputs already exist. It reads:

```text
outputs/daily/candidates_<date>.json
outputs/daily/factors_<date>.json
outputs/errors/failed_symbols_<date>.csv  # optional
data/cache/daily-use/**/stock_universe.csv
```

It then writes as-of research labels and lists. It does not calculate
future-return labels and does not access a provider.

### Validation and attribution scripts

The following are deliberately excluded from Phase 2.20:

```text
run_walk_forward_validation.py
run_controlled_validation_batch.py
run_strategy_family_experiments.py
run_aggressive_filter_experiments.py
build_member_level_asof_snapshot.py
```

They either generate or consume outcome-bearing validation files. They must
not be run until U1/U2 assignment, hypothesis versions, and the evaluation
protocol are frozen in a later phase.

## Missing Output Contract

For each U1 `<date>`, Phase 2.19 requires:

```text
outputs/labels/stock_labels_<date>.json
outputs/labels/stock_labels_<date>.csv
outputs/daily/factors_<date>.csv
outputs/lists/high_confidence_candidates_<date>.json
outputs/lists/trend_leaders_<date>.json
outputs/lists/long_term_stable_<date>.json
outputs/lists/breakout_watch_<date>.json
outputs/lists/accumulation_watch_<date>.json
outputs/lists/rebound_watch_<date>.json
outputs/lists/high_risk_active_<date>.json
outputs/lists/multi_lists_<date>.json
```

Before `generate_research_views.py` can create the label/list portion, these
daily source artifacts must exist:

```text
outputs/daily/candidates_<date>.json
outputs/daily/factors_<date>.json
outputs/daily/factors_<date>.csv
outputs/daily/summary_<date>.json
```

The daily summary must preserve:

```text
as_of_date = <date>
latest_input_date <= as_of_date
leakage_guard_applied = true
feature inputs use trade_date <= as_of_date
provider_access = false
```

`max_raw_cache_date` may be later than the as-of date. That is acceptable only
when the point-in-time guard confirms that later rows were excluded from
features.

## Outputs Not Required Before U1 Evaluation

Do not generate these merely to clear
`blocked_missing_as_of_outputs`:

```text
outputs/validation/walk_forward_summary_<date>_20d.json
outputs/validation/walk_forward_predictions_<date>_20d.csv
outputs/validation/list_performance_<date>_20d.json
outputs/validation/factor_effectiveness_<date>_20d.json
outputs/portfolios/portfolio_summary_<date>_20d.json
outputs/experiments/member_level_asof_snapshot_*.csv
```

Missing validation outputs are expected while U1 remains sealed. A
member-level snapshot depends on prediction membership and evaluation labels,
so it belongs after the protocol is frozen and the selected U1 window is
intentionally opened.

## Staged Workflow

## A. Preflight

### A1. Confirm branch and clean scope

Future manual command:

```powershell
git branch --show-current
git status --short
git log --oneline -5
```

The generation work must occur on a dedicated branch. Existing unrelated
untracked files must not be added.

### A2. Freeze and verify the date set

Future manual command:

```powershell
$u1Dates = @(
    "2024-02-29",
    "2024-05-31",
    "2024-08-30",
    "2024-11-29"
)
$forbiddenDates = @(
    "2024-01-31",
    "2024-04-30",
    "2024-07-31",
    "2024-10-31"
)
$overlap = @($u1Dates | Where-Object { $forbiddenDates -contains $_ })
if ($overlap.Count -gt 0) {
    throw "Forbidden answer-key date in U1 generation plan: $($overlap -join ', ')"
}
$u1Dates
```

Do not replace the explicit array with directory discovery or a broad date
range.

### A3. Presence-only cache preflight

Future manual command:

```powershell
$cacheRoot = "data\cache\daily-use\baostock"
[pscustomobject]@{
    stock_cache_root = Test-Path "$cacheRoot\stock_daily\adjusted"
    benchmark_cache = (
        (Test-Path "$cacheRoot\index_daily\raw\sh.000300.csv") -or
        (Test-Path "$cacheRoot\stock_daily\adjusted\sh.000300.csv")
    )
    stock_universe_cache = [bool](
        Get-ChildItem "data\cache\daily-use" -Recurse -Filter stock_universe.csv |
        Select-Object -First 1
    )
}
```

This check is provisional. Full per-symbol cache readiness cannot be proven
until a non-empty as-of symbol set exists. It must not trigger prewarm or
provider access.

### A4. Confirm that U1 outputs remain absent

Future manual command:

```powershell
foreach ($date in $u1Dates) {
    [pscustomobject]@{
        as_of_date = $date
        daily_candidates = Test-Path "outputs\daily\candidates_$date.json"
        daily_factors_json = Test-Path "outputs\daily\factors_$date.json"
        daily_factors_csv = Test-Path "outputs\daily\factors_$date.csv"
        stock_labels = Test-Path "outputs\labels\stock_labels_$date.json"
        multi_lists = Test-Path "outputs\lists\multi_lists_$date.json"
        predictions = Test-Path "outputs\validation\walk_forward_predictions_${date}_20d.csv"
    }
}
```

Do not open a prediction file if it unexpectedly exists. Stop and audit
whether the proposed unseen window has already been consumed.

## B. Generate Missing As-Of Outputs

### B1. Safe daily candidates and factors

There is no approved executable command for this step yet.

The next minimal implementation must provide a fail-closed cache-only
historical research path with these properties:

- accepts one explicit `--as-of-date`
- reads the existing local stock universe and daily cache only
- raises an error on missing cache instead of calling a provider
- writes only `candidates`, `factors`, factor explanations, and a provenance
  summary for that date
- applies `trade_date <= as_of_date` before filters, factors, scoring, and
  ranking
- reports `provider_access = false`
- reports `latest_input_date`, `max_raw_cache_date`,
  `future_rows_excluded_count`, and `leakage_guard_applied`
- accepts a controlled limit such as 300
- does not calculate future labels or validation metrics

Do not substitute the current `run_daily_research.py` command. Cache-first is
not equivalent to provider-disabled.

Once that fail-closed path exists and has targeted tests, freeze its exact
command and commit before generating any U1 daily files.

### B2. Generate local research labels and list artifacts

After the approved cache-only daily command has produced and verified the
three required daily source files, run this local-only command manually:

```powershell
$u1Dates = @(
    "2024-02-29",
    "2024-05-31",
    "2024-08-30",
    "2024-11-29"
)
foreach ($date in $u1Dates) {
    $required = @(
        "outputs\daily\candidates_$date.json",
        "outputs\daily\factors_$date.json",
        "outputs\daily\factors_$date.csv"
    )
    $missing = @($required | Where-Object { -not (Test-Path $_) })
    if ($missing.Count -gt 0) {
        throw "Missing cache-only daily inputs for ${date}: $($missing -join ', ')"
    }
    python backend\scripts\generate_research_views.py `
        --date $date `
        --outputs-dir outputs `
        --cache-dir data\cache\daily-use `
        --top-n 30
    if ($LASTEXITCODE -ne 0) {
        throw "generate_research_views failed for $date"
    }
}
```

These labels are as-of research classifications, not future-return labels.
Do not open or summarize validation outputs after this command.

### B3. Verify output presence and point-in-time provenance

Future manual presence-only command:

```powershell
$requiredTemplates = @(
    "outputs\labels\stock_labels_{date}.json",
    "outputs\labels\stock_labels_{date}.csv",
    "outputs\daily\factors_{date}.csv",
    "outputs\lists\high_confidence_candidates_{date}.json",
    "outputs\lists\trend_leaders_{date}.json",
    "outputs\lists\long_term_stable_{date}.json",
    "outputs\lists\breakout_watch_{date}.json",
    "outputs\lists\accumulation_watch_{date}.json",
    "outputs\lists\rebound_watch_{date}.json",
    "outputs\lists\high_risk_active_{date}.json",
    "outputs\lists\multi_lists_{date}.json"
)
foreach ($date in $u1Dates) {
    foreach ($template in $requiredTemplates) {
        $path = $template.Replace("{date}", $date)
        [pscustomobject]@{
            as_of_date = $date
            path = $path
            exists = Test-Path $path
        }
    }
}
```

Review only presence and the whitelisted provenance fields in
`outputs/daily/summary_<date>.json`. Do not inspect ranking outcomes or compare
lists between dates in this phase.

## C. Re-Run Phase 2.19 Readiness

After all as-of artifacts exist, run:

```powershell
python backend\scripts\check_unseen_window_readiness.py `
    --outputs-dir outputs `
    --cache-dir data\cache\daily-use `
    --provider baostock `
    --benchmark CSI300 `
    --limit 300 `
    --write-output
```

Expected reports:

```text
outputs/experiments/unseen_window_readiness_2024.json
outputs/experiments/unseen_window_readiness_2024.md
```

Safe status-only review:

```powershell
$readiness = Get-Content `
    "outputs\experiments\unseen_window_readiness_2024.json" `
    -Raw | ConvertFrom-Json
$readiness.windows |
    Select-Object `
        as_of_date,
        horizon_days,
        required_future_end_date,
        readiness_status,
        provider_fetch_required,
        symbol_count,
        missing_prerequisites
```

The expected transition is from `blocked_missing_as_of_outputs` to either:

- `ready_for_dry_run`; or
- a more specific infrastructure blocker such as missing symbols, stock
  cache, benchmark cache, an existing unseen output, or the unresolved
  November boundary policy.

If a window remains blocked, record the blocker. Do not alter hypotheses,
lists, or thresholds to make it pass.

## D. Do Not Inspect or Execute

Even after readiness improves, Phase 2.20 stops before validation. Do not:

- run controlled validation or walk-forward validation
- add `--write-output` to a validation command
- open prediction rows
- inspect list-performance or factor-effectiveness files
- compute winner or loser tails
- compare list returns or excess returns
- run experiment or attribution summaries
- evaluate any Phase 2.17 hypothesis
- generate member-level snapshots from U1 predictions

The future evaluation command is intentionally omitted from this phase.

## Guardrails Before Generation

- Commit the Phase 2.17 hypothesis registry and Phase 2.18 protocol.
- Keep the four answer-key dates outside every command.
- Use explicit U1 dates; never discover dates from existing outputs.
- Require a fail-closed cache-only daily source path.
- Confirm provider access cannot occur.
- Confirm the physical cache may contain later rows but every feature input is
  sliced to `trade_date <= as_of_date`.
- Record the generation code commit and exact command before creating files.
- Preserve the current-snapshot universe/listing/ST/suspension limitations.

## Guardrails After Generation

- U1 results remain sealed until U1/U2 assignment and evaluation rules are
  committed.
- If a script computes returns for labels in a later phase, it must not
  summarize performance conclusions during output-generation review.
- Do not tune thresholds after seeing any U1 result.
- Do not repeatedly reuse the same U1 outcomes for revisions.
- A failed readiness check is recorded as an infrastructure blocker.
- An unexpected validation output is treated as possible window consumption,
  not silently overwritten.
- Failed or mixed hypotheses must remain visible after evaluation.

## Stop Conditions

Stop immediately when:

- any command includes a forbidden answer-key date
- a command contains a broad or discovered date range
- the daily source path can call a provider
- cache-only mode is absent or not fail-closed
- as-of provenance metadata is missing or contradictory
- `latest_input_date > as_of_date`
- `leakage_guard_applied` is not true
- symbol or benchmark cache coverage is incomplete
- validation or prediction output unexpectedly exists
- someone requests outcome inspection before protocol freeze
- someone proposes changing thresholds or hypotheses in response to U1

## Phase 2.20 Decision

The local research-view generator is safe after its daily source inputs exist.
The repository does not yet expose a hard provider-disabled historical daily
candidate/factor generator. Therefore Phase 2.20 is a plan, not authorization
to run `run_daily_research.py`.

The next minimal implementation should add and test a fail-closed cache-only
as-of generation path. Only then may the user generate the four explicit U1
daily source sets, build research views, and rerun Phase 2.19 readiness.

No U1 outcome, list performance, winner/loser metric, hypothesis result,
scoring formula, ranking formula, factor formula, validation math, candidate
selection, production list, threshold, or recommendation behavior is
inspected or changed by this plan.
