# Phase 2.38 Research-Only Opportunity Cohort Parameter Preregistration

## Purpose

Phase 2.38 defines the governance contract for freezing H1-H5 parameters
before any real opportunity cohort output is generated:

- H1 `low_position_revaluation_watch`
- H2 `trend_acceleration_with_crowding_guard`
- H3 `right_tail_opportunity_watch`
- H4 `high_position_crowding_risk`
- H5 `false_breakout_risk`

This phase does not select numeric values, run the builder, create cohort
members, join labels, or evaluate outcomes. It supplies an auditable process
for a later parameter-freeze decision.

H1-H3 remain research-only opportunity observations. H4-H5 remain
non-blocking risk annotations.

## Why Preregistration Is Required

Phase 2.36 intentionally has no hidden parameter defaults. Its repository
template contains `null` values and is not runnable. Phase 2.37 creates a
feature-only input boundary, but that boundary does not make parameter
selection valid.

Preregistration separates three events:

1. define the rule and numeric parameters;
2. materialize and seal membership without labels;
3. evaluate the frozen membership on a separate unopened holdout.

Without this ordering, observed outcomes can influence parameters and make a
later result in-sample evidence rather than a holdout test.

The 2024 answer key, attribution work, U1, and U2 are consumed evidence. They
may explain why H1-H5 were proposed, but they cannot select, tune, or validate
the numeric parameters.

## Preregistration Artifacts

The governance template is:

```text
research/configs/opportunity_cohorts.preregistration.template.json
```

It is deliberately non-runnable:

- every H1-H5 numeric parameter remains `null`;
- the intended holdout is unfilled;
- `template_status` states that the file is not a frozen config;
- placeholders must be replaced before the file can be preregistered.

A future frozen config should use:

```text
research/configs/opportunity_cohorts.<config_version>.json
```

Do not overwrite a frozen config. Any change creates a new file and a new
`config_version`.

## Required Config Metadata

Every future preregistered config must include:

```text
research_only = true
labels_joined = false
production_change = false
config_version
created_for_phase
as_of_date
parameter_source
feature_bindings
preregistration.status
preregistration.created_at
preregistration.rationale_document
preregistration.cohort_definition_version
preregistration.source_snapshot_schema_version
preregistration.forbidden_data_sources
preregistration.intended_future_validation_holdout
```

`config_version`, `as_of_date`, and every placeholder under
`preregistration` must be concrete before freeze. The Git commit containing
the config and rationale is the audit boundary.

Recommended lifecycle values are:

| Status | Meaning |
|---|---|
| `draft_not_preregistered` | Placeholders or null values remain; builder use is forbidden |
| `preregistered_unopened` | Values and holdout are frozen; no holdout outcome has been inspected |
| `membership_sealed` | Feature-only cohort membership is written and checksummed without labels |
| `evaluated` | A separate evaluator has opened the preregistered holdout |
| `superseded` | A later version exists; this version remains immutable |
| `failed` | Frozen success/failure rules were not met; the record is retained |

## Parameter Type Contract

Builder parameters must be explicit finite JSON numbers:

- integers or floating-point numbers are allowed;
- booleans are forbidden even though JSON booleans are numeric-like in some
  runtimes;
- `null`, strings, infinity, and NaN are forbidden in a runnable config;
- units and comparison direction must be documented;
- inclusive comparison behavior is fixed by the Phase 2.36 builder;
- no missing parameter may receive a runtime default.

The template uses `null` to remain fail-closed. It is not a source of neutral
or recommended values.

## H1-H5 Required Parameters

### H1 low-position revaluation watch

| Parameter | Builder comparison | Required rationale |
|---|---|---|
| `max_distance_to_60d_low` | feature `<=` parameter | Defines low-position proximity without using later rebound outcomes |
| `max_drawdown_60d` | feature `<=` parameter | Defines material prior drawdown from completed bars |
| `min_recent_acceleration_proxy` | feature `>=` parameter | Defines as-of recovery acceleration |
| `min_activity_change_20d` | max of amount/volume change `>=` parameter | Defines participation confirmation |

### H2 trend acceleration with crowding guard

| Parameter | Builder comparison | Required rationale |
|---|---|---|
| `min_recent_acceleration_proxy` | feature `>=` parameter | Defines improving acceleration |
| `min_pre_20d_return` | feature `>=` parameter | Defines medium-horizon trend support |
| `min_crowding_proxy` | feature `>=` parameter | Defines the separate crowding warning |
| `min_distance_to_60d_high` | feature `>=` parameter | Defines high-position warning context |

The crowding guard remains an annotation. It does not remove or promote a
member.

### H3 right-tail opportunity watch

| Parameter | Builder comparison | Required rationale |
|---|---|---|
| `min_volatility_20d` | bound volatility feature `>=` parameter | Defines elevated as-of variance context |
| `min_recent_acceleration_proxy` | feature `>=` parameter | Defines positive acceleration |
| `min_activity_change_20d` | max of amount/volume change `>=` parameter | Defines participation confirmation |

The cohort name is a hypothesis label. Parameter selection must not use known
future-tail membership.

### H4 high-position crowding risk

| Parameter | Builder comparison | Required rationale |
|---|---|---|
| `min_distance_to_60d_high` | feature `>=` parameter | Defines high-position context |
| `min_crowding_proxy` | feature `>=` parameter | Defines price-structure crowding context |
| `min_volatility_20d` | bound volatility feature `>=` parameter | Defines elevated variance context |

H4 is non-blocking. It cannot become automatic exclusion logic.

### H5 false-breakout risk

| Parameter | Builder comparison | Required rationale |
|---|---|---|
| `min_distance_to_60d_high` | feature `>=` parameter | Defines high-position context |
| `max_recent_acceleration_proxy` | feature `<=` parameter | Defines observable deceleration |
| `max_drawdown_60d` | feature `<=` parameter | Defines as-of weakness |
| `min_activity_change_20d` | max of amount/volume change `>=` parameter | Defines activity context |

H5 only annotates same-date `breakout_watch` or `accumulation_watch`
membership. It does not change either source list.

## Allowed Parameter Sources

A parameter rationale may use:

- the frozen feature definitions and units;
- domain or measurement reasoning written before the holdout is opened;
- operational data-quality constraints that contain no outcome information;
- synthetic fixtures used only to verify code behavior;
- a separately documented exploratory development source that is neither the
  future holdout nor consumed answer-key/U1/U2 evidence.

Any exploratory development source must be named, dated, and permanently
excluded from later confirmation claims.

## Forbidden Parameter Sources

The config must list, and the parameter rationale must not use:

- future returns;
- future highs or lows;
- realized labels;
- winner or loser status;
- case-study answers or manually researched outcome archetypes;
- U1 or U2 performance outcomes;
- the 2024 answer-key and attribution outcomes;
- later list membership or reconstructed future membership;
- unavailable external historical data;
- current status data backfilled into a historical as-of date;
- any new holdout outcome before the config is committed.

The builder input remains feature-only. It must not read validation summaries,
prediction labels, list-performance reports, factor-effectiveness reports, or
strategy-experiment outcomes.

## Intended Future Holdout Contract

Before a config changes to `preregistered_unopened`, it must name an unopened
future validation holdout and freeze:

- exact as-of windows and horizon;
- benchmark;
- universe definition and limit;
- feature-only snapshot schema version;
- cohort and config versions;
- minimum valid sample per window and per cohort;
- missing-data and empty-cohort behavior;
- metrics for H1-H3 opportunity observations;
- metrics for H4-H5 risk annotations;
- success, mixed, failure, and insufficient-data rules;
- replacement-window policy;
- confirmation that answer-key, U1, and U2 windows are excluded.

If a window fails technical readiness, record the blocker. Do not replace it
based on favorable or unfavorable outcome quality. Any replacement must be
preregistered before its outcomes are inspected.

## Failure And Revision Governance

Every frozen config receives an append-only result record after evaluation:

```text
config_version
cohort_id
holdout_id
evaluation_status
sample_status
decision
failure_reason
evaluated_at
evaluator_version
result_artifact_path
```

Contradictory, empty, and failed windows remain in the record. They are not
deleted from pooled summaries.

After any outcome is opened:

- the evaluated config is immutable;
- a parameter, interaction, feature binding, or missing-data change creates a
  new `config_version`;
- the reason for revision references the failed or mixed result without
  reusing that result as confirmation;
- the revised config requires a different, unopened holdout;
- repeated threshold adjustment on the same holdout is prohibited.

Passing one holdout does not authorize production changes. A separate future
proposal, independent confirmation, regression plan, rollback plan, and
manual approval would still be required.

## Future Execution Order

The later manual workflow is frozen as:

A. Export feature-only snapshots with the Phase 2.37 exporter.

B. Fill every parameter and governance placeholder in a copied config; review
and commit it before opening holdout outcomes.

C. Run the Phase 2.36 builder in dry-run mode and review PIT, config, feature,
and sample blockers only.

D. Run the builder with `--write-output` to create research-only,
label-free cohort membership.

E. Freeze the generated cohort files, metadata, config version, source
snapshot version, and checksums.

F. Confirm the next unopened holdout registration before any evaluator joins
labels.

G. Use a separate evaluator to join labels after membership is sealed. Report
all preregistered windows and failure rules.

Phase 2.38 executes none of these steps on real data.

## Future Command Templates

These are later manual commands, not Phase 2.38 execution instructions.

Feature-only export dry-run:

```powershell
python backend\scripts\build_feature_only_member_snapshot.py --snapshot-file <merged-snapshot> --as-of-date <YYYY-MM-DD> --outputs-dir research\inputs --drop-outcome-columns --dry-run
```

Cohort builder dry-run after config freeze:

```powershell
python backend\scripts\build_research_opportunity_cohorts.py --snapshot-file research\inputs\member_level_asof_features_<YYYY-MM-DD>.csv --as-of-date <YYYY-MM-DD> --config research\configs\opportunity_cohorts.<config_version>.json --outputs-dir outputs --dry-run
```

Research-only write after dry-run review:

```powershell
python backend\scripts\build_research_opportunity_cohorts.py --snapshot-file research\inputs\member_level_asof_features_<YYYY-MM-DD>.csv --as-of-date <YYYY-MM-DD> --config research\configs\opportunity_cohorts.<config_version>.json --outputs-dir outputs --write-output
```

Do not run these commands while null parameters, holdout placeholders, or
draft governance fields remain.

## Explicit Non-Goals

Phase 2.38 does not:

- select or suggest final numeric parameters;
- run validation or inspect outcomes;
- generate real H1-H5 membership or output files;
- create production recommendations or launch a portfolio;
- reweight `total_score`;
- create automatic exclusion behavior;
- use action-directed recommendation language;
- change scoring, ranking, factor, label, candidate, membership, threshold,
  or recommendation logic;
- access BaoStock or any provider;
- modify generated outputs.

## Phase Decision

The parameter process is specified, but no parameter set is preregistered by
this phase. The new template remains blocked by null values and an unfilled
holdout contract.

The next approved step, if desired, is to choose and document a genuinely
unopened holdout plus independently justified parameter values, then commit a
new immutable config before any real builder output is generated.
