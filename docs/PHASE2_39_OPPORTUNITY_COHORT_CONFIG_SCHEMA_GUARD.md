# Phase 2.39 Opportunity Cohort Config Schema Guard

## Purpose

Phase 2.39 adds a fail-closed schema boundary before the Phase 2.36 H1-H5
research-only cohort builder can load a real snapshot or generate membership.

It separates two questions:

1. Is a preregistration template structurally complete?
2. Is a frozen config safe and complete enough for execution?

A structurally valid template is not runnable. This phase selects no numeric
parameters, runs no real cohort, joins no labels, and evaluates no outcomes.

## Validation Modes

### Template schema mode

Use `--schema-check-only` for the Phase 2.38 template:

```powershell
python backend\scripts\build_research_opportunity_cohorts.py --config research\configs\opportunity_cohorts.preregistration.template.json --schema-check-only
```

This mode:

- reads only the config;
- does not require `--snapshot-file` or `--as-of-date`;
- does not load a snapshot;
- does not evaluate cohort membership;
- permits required H1-H5 parameter values to remain `null`;
- verifies parameter names, roles, safety flags, forbidden-source governance,
  feature binding, and the holdout-contract structure;
- returns `runnable=false`, `provider_access=false`,
  `labels_joined=false`, and `production_change=false`;
- writes no output.

Expected template status:

```text
status = schema_valid_template
schema_validation_mode = template
runnable = false
parameter_count = 18
null_parameter_count = 18
snapshot_loaded = false
outputs_written = false
```

Template mode does not certify parameter values or validation readiness.

### Execution mode

Normal dry-run and write-output use execution validation. They require:

- `config_version`;
- `created_for_phase`;
- a concrete `as_of_date` and `parameter_source`;
- `research_only=true`;
- `labels_joined=false`;
- `production_change=false`;
- an allowed explicit volatility feature binding;
- exactly H1-H5 and their frozen roles;
- all 18 exact parameter keys;
- a finite JSON number for every parameter;
- preregistration status `preregistered_unopened`;
- every required forbidden data-source category;
- a concrete unopened future holdout contract;
- explicit exclusion of the 2024 answer key, U1, and U2;
- no forbidden outcome-tuning flags.

`null`, strings, booleans, non-finite values, missing keys, extra parameter
keys, placeholders, and hidden defaults are blocked.

## Why Null Parameters Remain Blocked

The preregistration template intentionally uses `null`. Allowing those values
in normal dry-run would create pressure for runtime defaults or accidental
execution before a parameter freeze.

Therefore:

- `--schema-check-only` may verify the null template structure;
- normal dry-run rejects the same template;
- `--write-output` uses the same strict execution validator as dry-run;
- no code path fills a missing value or substitutes a default.

## Holdout Contract

Before a config can run, its
`preregistration.intended_future_validation_holdout` must contain:

- a concrete holdout ID;
- one or more unopened window IDs;
- a positive horizon;
- benchmark and universe definitions;
- positive minimum valid-sample gates;
- success/failure rules;
- a replacement policy fixed before outcome inspection;
- exclusions for consumed answer-key, U1, and U2 evidence.

A config also must use `preregistration.status=preregistered_unopened`.
Template placeholders may pass schema mode, but never execution mode.

## Forbidden Tuning Flags

The validator recursively rejects keys that state or imply tuning from:

- U1;
- U2;
- the answer key.

Examples include `tuned_from_u1`, `tuned_from_u2`, and
`tuned_from_answer_key`, regardless of whether their value is true or false.
The presence of the flag is itself invalid governance.

Required `forbidden_data_sources` include:

- future returns;
- future highs or lows;
- realized labels;
- winner or loser status;
- case-study answers;
- U1 or U2 performance outcomes;
- unavailable external historical data.

## Normal Dry-Run Template

Only after copying the template, replacing every placeholder, filling all
parameters, preregistering a genuinely unopened holdout, and committing the
config may a later user run:

```powershell
python backend\scripts\build_research_opportunity_cohorts.py --snapshot-file research\inputs\member_level_asof_features_<YYYY-MM-DD>.csv --as-of-date <YYYY-MM-DD> --config research\configs\opportunity_cohorts.<config_version>.json --outputs-dir outputs --dry-run
```

A dry-run validates both the config and feature-only snapshot but writes no
cohort files. It does not establish performance.

## Fail-Closed Statuses

Relevant statuses include:

- `blocked_missing_config`
- `blocked_invalid_config`
- `blocked_template_config_execution`
- `blocked_missing_preregistration`
- `blocked_invalid_preregistration`
- `blocked_unfrozen_preregistration`
- `blocked_missing_holdout_contract`
- `blocked_missing_frozen_parameter`
- `blocked_forbidden_tuning_source`
- `blocked_hidden_defaults`
- `blocked_missing_execution_argument`

Failures return exit code 2 and retain the research-only safety metadata.

## Future Freeze Sequence

1. Copy the non-runnable preregistration template to a versioned config.
2. Document independently justified values without using consumed outcomes.
3. Fill and preregister a genuinely unopened holdout.
4. Commit the config and rationale.
5. Run `--schema-check-only` for structure review.
6. Export a feature-only snapshot through Phase 2.37.
7. Run normal builder dry-run.
8. Only after review, generate and seal label-free research cohort membership.
9. Join labels later through a separate evaluator on the frozen holdout.

Any post-result parameter revision requires a new version and a different
unopened holdout.

## Non-Goals

Phase 2.39 does not:

- fill or suggest final H1-H5 values;
- generate real cohort membership or outputs;
- run validation or inspect outcomes;
- access BaoStock or another provider;
- join labels or compute future returns;
- tune from U1, U2, answer-key, or case-study outcomes;
- modify generated outputs;
- change production scoring, ranking, factors, validation math, candidate
  selection, list membership, thresholds, or recommendation logic.
