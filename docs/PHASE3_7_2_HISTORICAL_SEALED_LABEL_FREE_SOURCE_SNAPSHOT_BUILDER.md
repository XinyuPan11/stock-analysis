# Phase 3.7.2 Historical Sealed Label-Free Source Snapshot Builder

## Purpose

Phase 3.7.2 adds a dedicated source snapshot builder for the Phase 3.6
historical sealed H1-H5 windows.

The builder creates member-level as-of source snapshots from explicit local
artifacts and local daily cache. It does not use validation predictions,
future labels, future returns, provider access, evaluator output, or H1-H5
cohort output.

## Why A New Builder Is Required

The legacy command:

```text
backend/scripts/build_member_level_asof_snapshot.py
```

is an attribution builder. It requires
`walk_forward_predictions_<date>_20d.csv` as its member universe and attaches
future label fields after feature materialization.

That behavior is valid for its original controlled attribution role but is
unsafe as the source of historical sealed H1-H5 membership. Phase 3.6
requires membership and source features to be frozen before any label source
is opened.

Phase 3.7.2 therefore adds:

```text
backend/src/stock_analysis/research/historical_source_snapshot_builder.py
backend/scripts/build_historical_h1h5_source_snapshot.py
```

The new module does not import or call the legacy validation snapshot builder,
an evaluator, a provider, or the H1-H5 opportunity cohort builder.

## Historical Contract

```text
validation_id = h1h5-historical-sealed-v1
evidence_level = historical_sealed_not_prospective
provider_access = false
labels_joined = false
production_change = false
```

Only the three primary and two backup dates preregistered by Phase 3.6 are
accepted. Answer-key, U1, U2, U3, and unknown dates fail before an input file
is opened.

## Input Artifacts

All input paths are explicit CLI arguments.

### Factors CSV

The factors file defines the frozen source universe and preserves existing
as-of factor context when present.

Required columns:

```text
symbol
as_of_date
```

Supported existing factor context includes momentum, moving averages,
relative strength, volatility, drawdown, amount/volume averages, source, and
warnings. The builder does not recalculate or change those factor formulas.

The preferred future source is:

```text
outputs/daily/factors_<as_of_date>.csv
```

produced by the existing cache-only as-of path.

### Safe membership CSV

The membership artifact must be a deliberately label-free projection.

Required columns:

```text
symbol
as_of_date
is_breakout_watch
is_accumulation_watch
```

Optional preserved context includes:

```text
rank
total_score
momentum_score
trend_score
relative_strength_score
risk_score
liquidity_score
primary_type
research_status
risk_level
captured_positive_lists
captured_risk_lists
is_high_confidence
is_trend_leader
is_long_term_stable
is_rebound_watch
is_high_risk_active
```

The membership CSV must cover every symbol in the factors universe exactly
once. The builder copies these fields; it does not generate or change list
membership rules.

Current `candidates_<date>.csv` contains a `label` column, and current
research-list JSON items contain `label_reason`. Both are rejected under the
Phase 3.7.2 input rule. They must not be passed directly or renamed to bypass
the guard.

### Local daily cache

For every source symbol, the builder reads:

```text
<cache-dir>/baostock/stock_daily/adjusted/<symbol>.csv
```

It applies the existing point-in-time slicer before calculating a feature.
Physical rows after the as-of date are excluded and counted; they are never
used as feature inputs.

No provider object or fallback exists in this path.

## Derived H1-H5 Features

The following fields are calculated only from local completed bars on or
before the as-of date:

```text
pre_5d_return
pre_20d_return
pre_60d_return
technical_volatility_20d
drawdown_60d
amount_change_20d
volume_change_20d
distance_to_60d_high
distance_to_60d_low
recent_acceleration_proxy
high_position_crowding_proxy
```

These are backward-looking entry features. They are not future returns or
validation labels.

At least 61 usable price observations and adequate amount/volume history are
required for every member. A missing cache file, malformed date, required raw
column, or non-finite feature blocks the complete snapshot.

## Output Schema

The builder writes:

```text
outputs/experiments/historical_h1h5_source_snapshot_<as_of_date>.csv
outputs/experiments/historical_h1h5_source_snapshot_<as_of_date>.json
```

Each row contains:

- exact `as_of_date` and `symbol`;
- `latest_input_date`;
- `max_raw_cache_date`;
- `future_rows_excluded_count`;
- `leakage_guard_applied=true`;
- all required H1-H5 technical fields;
- `is_breakout_watch` and `is_accumulation_watch`;
- allowed existing factor, rank, score, and list context;
- source artifact paths;
- `research_only=true`;
- `provider_access=false`;
- `labels_joined=false`;
- `production_change=false`;
- historical validation ID and evidence level.

The JSON contains the same records plus source paths, row counts, PIT summary,
and explicit safety flags.

The output contains no future, forward, realized, target, outcome, label,
winner/loser, benchmark-outcome, or holding-period field.

## Fail-Closed Behavior

The builder blocks when:

- the date is not a Phase 3.6 historical sealed window;
- the date is answer-key, U1, U2, or U3;
- an input path names validation, walk-forward predictions,
  list-performance, factor-effectiveness, strategy-experiment, or
  future-label output;
- an input header contains a future, outcome, label, winner/loser, realized,
  or holding-period field;
- factors or membership are missing, unreadable, duplicated, or date-mixed;
- membership does not cover the factors universe;
- `latest_input_date > as_of_date`;
- the factors universe contains fewer than 100 rows;
- a local daily-cache file or required raw column is missing;
- a required H1-H5 feature cannot be calculated as a finite value;
- any source row lacks a verified leakage guard.

One blocked symbol blocks the whole output. The builder never drops a weak
row silently to rescue the 100-row gate.

## CLI

The CLI requires every input and output root explicitly:

```powershell
python backend\scripts\build_historical_h1h5_source_snapshot.py --as-of-date <HISTORICAL_DATE> --factors-file <SAFE_FACTORS_CSV> --membership-file <SAFE_MEMBERSHIP_CSV> --cache-dir data\cache\daily-use --outputs-dir outputs
```

Dry-run is the default. It builds in memory and prints JSON metadata but does
not create `outputs/`.

Explicit dry-run:

```powershell
python backend\scripts\build_historical_h1h5_source_snapshot.py --as-of-date <HISTORICAL_DATE> --factors-file <SAFE_FACTORS_CSV> --membership-file <SAFE_MEMBERSHIP_CSV> --cache-dir data\cache\daily-use --outputs-dir outputs --dry-run
```

Write only after manual review:

```powershell
python backend\scripts\build_historical_h1h5_source_snapshot.py --as-of-date <HISTORICAL_DATE> --factors-file <SAFE_FACTORS_CSV> --membership-file <SAFE_MEMBERSHIP_CSV> --cache-dir data\cache\daily-use --outputs-dir outputs --write-output
```

`--write-output` creates only the source CSV and JSON under
`outputs/experiments/`.

## Current Real-Input Readiness

Phase 3.7.1 found enough local market cache for all primary as-of dates, but
the corresponding 2026 cache-only factors and safe membership CSV files do
not yet exist.

The builder is therefore implemented and tested but is not run against real
historical windows in this phase.

Phase 3.7 and Phase 3.7.1 now recognize the new source path pattern:

```text
outputs/experiments/historical_h1h5_source_snapshot_<date>.csv
```

Missing files still return `blocked_missing_source_snapshot`. No safety check
was removed.

## Manual Cache-Only Preparation

In the next approved execution phase, prepare as-of factor artifacts from the
existing local cache, starting with the three primary dates:

```powershell
python backend\scripts\generate_cache_only_asof_daily_outputs.py --date 2026-01-30 --cache-dir data\cache\daily-use --outputs-dir outputs --provider baostock --benchmark CSI300 --limit 300
python backend\scripts\generate_cache_only_asof_daily_outputs.py --date 2026-03-31 --cache-dir data\cache\daily-use --outputs-dir outputs --provider baostock --benchmark CSI300 --limit 300
python backend\scripts\generate_cache_only_asof_daily_outputs.py --date 2026-04-30 --cache-dir data\cache\daily-use --outputs-dir outputs --provider baostock --benchmark CSI300 --limit 300
```

These commands are local-cache generation commands, not validation. They were
not run by Phase 3.7.2.

A separately reviewed label-free membership projection must then be produced
from the exact as-of research-list membership. It must contain only the
allowlisted membership/rank fields and no `label` or `label_reason` field.

Backup dates remain inactive unless the frozen Phase 3.6 replacement rules
are met. `2026-05-29` additionally lacks complete local 20D future coverage,
which does not affect as-of source generation but prevents later evaluator
activation.

## Why This Is Not Validation

The builder does not read a future price, validation prediction, future
label, benchmark outcome, winner/loser status, or evaluator output. It
calculates only entry-time features from rows at or before the as-of date.

It produces no performance metric, hypothesis verdict, or evidence status.

## Why No H1-H5 Cohort Is Generated

The source snapshot contains features and unchanged list context only. The
H1-H5 opportunity builder is not imported or called.

After real source files are generated, they must pass the existing
feature-only exporter and historical readiness before a separate phase may
run an H1-H5 builder dry-run.

## Recommended Next Phase

The next phase is:

```text
Phase 3.7.3 Historical Primary As-Of Artifact Preparation and Source Snapshot Execution
```

Phase 3.7.3 should:

1. generate cache-only factors for the three primary dates;
2. create and audit safe label-free membership projections;
3. run this builder in dry-run mode;
4. after manual review, write and checksum the three source snapshots;
5. stop before feature-only export and H1-H5 cohort generation.

## Phase Decision

Phase 3.7.2 provides a deterministic, provider-free, label-free source
builder and updates readiness to recognize its output path.

No real historical source, feature-only snapshot, H1-H5 cohort, label,
validation result, provider request, cache prewarm, parameter change, U3
change, or production change is created by this phase.
