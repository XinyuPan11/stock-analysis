# Phase 2.36 Research-Only Opportunity Cohort Builder

## Purpose

Phase 2.36 implements a fail-closed research builder for the frozen H1-H5
cohort skeleton:

- H1 `low_position_revaluation_watch`
- H2 `trend_acceleration_with_crowding_guard`
- H3 `right_tail_opportunity_watch`
- H4 `high_position_crowding_risk`
- H5 `false_breakout_risk`

H1-H3 are opportunity observations. H4-H5 are non-blocking risk annotations.
The builder does not change existing lists, scores, ranks, thresholds, or
recommendation behavior and does not evaluate effectiveness.

## Files And Surfaces

```text
backend/src/stock_analysis/research/opportunity_cohorts.py
backend/scripts/build_research_opportunity_cohorts.py
research/configs/opportunity_cohorts.template.json
```

The module reads a feature-only member-level as-of snapshot plus an explicit
preregistered JSON config. It produces long-form research annotations: one
source row for each H1-H5 cohort.

## Critical Feature/Label Boundary

The builder rejects an input containing future or realized outcome columns,
including:

- future or forward return fields;
- benchmark outcome fields;
- winner/loser fields;
- realized-return fields;
- future high/low fields;
- holding-period drawdown labels.

The standard Phase 2.14 combined attribution snapshot contains future label
columns and therefore cannot be passed directly to this builder. A later
feature-only snapshot export must omit those columns before use.

`future_rows_excluded_count` is allowed because it is a point-in-time
diagnostic describing rows removed before feature calculation, not a future
outcome.

## Explicit Config Contract

`--config` is required. There is no runtime default.

The config must contain:

- `research_only = true`;
- a non-empty `config_version`;
- the exact `as_of_date`;
- a `parameter_source`;
- an explicit binding for the 20D volatility input;
- exactly H1-H5;
- the frozen role for every cohort;
- every named numeric parameter.

The repository template intentionally contains `null` parameter values. It
cannot run until a later phase preregisters values before opening holdout
outcomes. Tests use synthetic values only.

The builder rejects missing, non-numeric, infinite, incomplete, or silently
defaulted parameters.

## Cohort Skeleton

### H1 low-position revaluation watch

Requires low-position context, prior drawdown, positive recovery acceleration,
and activity confirmation. Low position alone is insufficient.

### H2 trend acceleration with crowding guard

Requires acceleration and medium-horizon trend support. Crowding is evaluated
as a separate warning and does not remove or promote a member.

### H3 right-tail opportunity watch

Requires explicit volatility context, positive acceleration, and activity
confirmation. The output always states that the pre-as-of right-tail proxy is
limited.

### H4 high-position crowding risk

Requires high-position, crowding, and volatility context. It is a risk
annotation and does not change eligibility.

### H5 false-breakout risk

Evaluates only same-date `breakout_watch` or `accumulation_watch` members. It
requires high-position context, activity, and as-of weakness. It does not
alter either source list.

The formulas contain no embedded numeric cutoffs. Every comparison value comes
from the explicit config.

## Point-In-Time Checks

Required checks run before membership evaluation:

```text
snapshot as_of_date == requested as_of_date
leakage_guard_applied == true for every selected row
latest_input_date <= as_of_date when latest_input_date is present
one row per symbol for the requested as_of_date
no forbidden future/outcome columns
all required feature columns present
```

Malformed dates, duplicate symbols, missing required columns, and unverified
leakage metadata block the build.

Missing required values for one symbol do not broaden the rule. That
symbol/cohort record is marked:

```text
annotation_status = excluded_missing_required_fields
cohort_member = false
```

## CLI

Dry-run is the default safe behavior. `--dry-run` may be supplied explicitly:

```powershell
python backend\scripts\build_research_opportunity_cohorts.py --snapshot-file research\inputs\member_level_asof_features_2026-03-31.csv --as-of-date 2026-03-31 --config research\configs\opportunity_cohorts_2026-03-31.json --outputs-dir outputs --dry-run
```

Write separate research outputs only after the config and feature-only
snapshot have been reviewed:

```powershell
python backend\scripts\build_research_opportunity_cohorts.py --snapshot-file research\inputs\member_level_asof_features_2026-03-31.csv --as-of-date 2026-03-31 --config research\configs\opportunity_cohorts_2026-03-31.json --outputs-dir outputs --write-output
```

The commands above are templates. Phase 2.36 does not create or run a
production-like config.

## Output Paths

With `--write-output`:

```text
outputs/research/opportunity_cohorts_<as_of_date>.json
outputs/research/opportunity_cohorts_<as_of_date>.csv
```

The JSON contains metadata, per-cohort summaries, guardrails, and records.
The CSV contains the safe source fields plus research annotation fields.

Metadata includes:

```text
research_only = true
provider_access = false
labels_joined = false
production_change = false
as_of_date
source_snapshot_path
config_path
cohort_count
input_row_count
```

## Preservation Contract

The builder copies source rows and appends research-only annotation columns.
It does not mutate the input frame.

Existing fields such as:

- symbol;
- rank;
- score/factor context;
- source-list membership;
- point-in-time diagnostics;

remain unchanged in every long-form cohort record.

## Fail-Closed Statuses

Examples include:

- `blocked_missing_snapshot`
- `blocked_missing_config`
- `blocked_invalid_config`
- `blocked_missing_frozen_parameter`
- `blocked_future_outcome_columns`
- `blocked_missing_required_feature`
- `blocked_missing_as_of_rows`
- `blocked_duplicate_symbol`
- `blocked_unverified_leakage_guard`
- `blocked_point_in_time_violation`
- `blocked_invalid_feature_value`

On failure the CLI prints research guardrail metadata and returns exit code 2.
It writes no output.

## Tests

Run:

```powershell
python -B -m pytest -p no:cacheprovider backend\tests\test_opportunity_cohorts.py -q
```

Tests cover:

- missing and incomplete config;
- future/outcome-column rejection;
- point-in-time violations;
- missing required fields;
- metadata guardrails;
- H1-H3 and H4-H5 role separation;
- source rank and list-membership preservation;
- output paths and label absence;
- CLI dry-run behavior.

## Non-Goals

Phase 2.36 does not:

- select production parameters;
- use U1/U2 or answer-key outcomes for tuning;
- join future labels;
- run validation;
- access a provider;
- change production scoring, ranking, factors, labels, lists, or thresholds;
- create a recommendation or portfolio;
- write outputs during Codex verification.

## Next Step

Before any real cohort build, preregister:

1. a feature-only snapshot export contract;
2. exact parameter values and their rationale without reading holdout outcomes;
3. a new unopened holdout;
4. minimum sample and failure rules.

Only after those are committed should the user run a dry-run. Effectiveness
evaluation belongs to a later, separate evaluator phase.
