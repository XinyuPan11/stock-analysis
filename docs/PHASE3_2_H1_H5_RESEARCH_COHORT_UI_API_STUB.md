# Phase 3.2 H1-H5 Research Cohort UI/API Stub

## Purpose

Phase 3.2 adds a read-only presentation surface for generated H1-H5
research cohort outputs. It lets the user inspect label-free cohort
membership without treating engineering smoke counts as validation,
recommendations, or production selection logic.

## Paths

API endpoint:

```text
/api/research/opportunity-cohorts
```

Optional `as_of_date=YYYY-MM-DD` selects an exact generated output. Without
the parameter, the loader selects the latest dated JSON output.

UI page:

```text
/research/opportunity-cohorts
```

## Output Source

The authoritative source is:

```text
outputs/research/opportunity_cohorts_<as_of_date>.json
```

The JSON metadata, H1-H5 summaries, and member records are read locally.
No provider request, validation job, label join, or future-return
calculation occurs.

## Response Contract

The API exposes:

- `research_only=true`;
- `provider_access=false`;
- `labels_joined=false`;
- `production_change=false`;
- as-of date, config version, source snapshot path, and source output path;
- all H1-H5 groups in frozen order;
- member counts, evaluated counts, blocked counts, caveats, and members;
- source symbol, rank, and existing-list context copied by the builder;
- explicit empty groups when a cohort has zero members.

The UI shows the same H1-H5 groups and metadata. It uses research-only
wording and does not order cohorts as better or worse from their counts.

## Fail-Closed Behavior

Missing output returns `status=unavailable` with five explicit empty groups.
It does not fabricate membership.

The loader returns `status=blocked_unsafe_output` and exposes no members when:

- JSON is unreadable or structurally invalid;
- `research_only` is not true;
- `provider_access`, `labels_joined`, or `production_change` is not false;
- a future, forward, realized, label, target, winner/loser, or outcome field
  appears;
- records or summaries contain an unknown cohort;
- summaries do not define exactly H1-H5.

Unsafe API responses use HTTP 409. The UI presents the blocked state without
rendering member data.

## Why Smoke Counts Are Not Validation

The Phase 3.1 counts only demonstrated deterministic execution on an audited
feature-only snapshot. They were not compared with future outcomes and cannot
support return, alpha, quality, or recommendation claims. Zero and nonzero
cohort sizes are displayed as neutral generated-state facts.

## Production Boundary

Phase 3.2 changes no production score, rank, factor formula, validation
label, candidate selection, existing list membership, threshold, or
recommendation logic. H1-H3 remain opportunity observations. H4-H5 remain
non-blocking risk annotations.

## Next Phase

The next recommended phase is Phase 3.3 U3 holdout preregistration. It must
freeze the evaluator manifest, exact windows, metrics, sample gates, and
decision rules before any U3 outcome is opened.
