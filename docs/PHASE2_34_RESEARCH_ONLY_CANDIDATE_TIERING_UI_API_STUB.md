# Phase 2.34 Research-Only Candidate Tiering UI/API Stub

## Purpose

Phase 2.34 implements the static presentation mapping frozen in Phase 2.33.
It groups existing research-list outputs for reading without changing their
names, members, rank, order, scores, or eligibility.

## Surfaces

```text
GET /api/lists/tiers
GET /lists/tiers
```

The API returns five research-only tiers. The HTML page renders the same
metadata, caveats, and unchanged source-list contents.

## Implemented Mapping

| Order | Tier | Existing lists |
|---|---|---|
| 1 | Defensive Observation | `long_term_stable` |
| 2 | Core Research Candidates | `high_confidence_candidates` |
| 3 | Trend Observation | `trend_leaders` |
| 4 | Active Opportunity Observation | `breakout_watch`, `accumulation_watch`, `rebound_watch` |
| 5 | Risk Warning | `high_risk_active` |

`insufficient_data` is returned separately as a data-quality state and is not
treated as a tier.

Tier order is a reading order only. It is not a quality, return, confidence,
or action rank.

## Required Presentation Wording

The API and page include:

```text
Research-only tiering
Not investment advice
Not a buy recommendation
No guaranteed return
Tier numbers indicate reading order only
Existing list logic is unchanged
```

Each tier also carries:

- `tier_id`;
- `tier_name`;
- `tier_badge`;
- `tier_description`;
- `evidence_note`;
- `caveat`;
- `forbidden_action_note`;
- `research_only = true`;
- its explicit source list IDs and unchanged list payloads.

## Preservation Contract

The loader reads each source list through the existing `OutputLoader` path.
The tier builder deep-copies the payload for presentation and does not mutate
the source object.

Tests compare source and tiered:

- list IDs and names;
- member arrays;
- item order;
- rank order;
- item counts.

Tier 4 does not union or deduplicate its three source lists. Tier 5 only
prompts manual risk review and does not change eligibility or produce an
action signal.

## Fail-Closed Behavior

The versioned metadata must exactly match the five Phase 2.33 tiers, their
order, and their source list IDs.

If metadata is absent, incomplete, duplicated, reordered, or maps
`insufficient_data` into a tier:

```text
status = tier_metadata_unavailable
available = false
message = Tier metadata unavailable
tiers = []
```

The UI displays the unavailable message and makes no tier claim. It does not
infer a tier from a list name, score, member, or rank.

Missing source-list outputs are recorded in `missing_source_list_ids`; they
are not replaced or inferred.

## Execution Boundary

The stub:

- reads existing list JSON only;
- performs no provider request;
- runs no validation or label calculation;
- writes no generated output;
- inspects no new outcome;
- creates no score, ranking, combined list, or portfolio.

## Tests

Run the targeted suite:

```powershell
python -B -m pytest -p no:cacheprovider backend\tests\test_candidate_tiering.py backend\tests\test_defensive_positioning.py backend\tests\test_api.py -q
```

Tests cover exact mapping, wording, fail-closed behavior, source preservation,
the separate data-quality state, API fields, and HTML presentation.

## Non-Goals

Phase 2.34 does not change:

- scoring or ranking formulas;
- factor formulas or validation math;
- candidate selection or list membership;
- list order or ranks;
- thresholds;
- recommendation logic;
- portfolio construction;
- provider or cache behavior;
- generated outputs.

## Phase Decision

The tiering stub is a research-only reading layer over unchanged source lists.
Any future change to source membership, ordering, eligibility, scoring, or
production behavior requires a separate phase and evidence contract.
