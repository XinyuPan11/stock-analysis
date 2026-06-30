# Phase 2.32 Research-Only Defensive Positioning Report/UI Stub

## Purpose

Phase 2.32 implements the minimal presentation contract frozen in Phase 2.31.
It adds research-only defensive context to the existing
`long_term_stable` list detail API and HTML page.

This is a presentation overlay. The source list, item order, ranks, scores,
membership rules, and production behavior remain unchanged.

## Surfaces

The stub is visible on:

```text
GET /api/lists/long_term_stable
GET /lists/long_term_stable
```

The API appends a `defensive_positioning` object. The HTML list detail page
renders the same object as a separate evidence and caution section. Other
research lists receive no defensive overlay.

## Exact Presentation Wording

Title:

```text
Research-only defensive observation
```

Badge:

```text
Defensive observation
```

Evidence:

```text
U2 controlled windows showed shallower drawdown than active lists in 4/4 windows.
```

Caveat:

```text
Excess return was unstable and negative in 3/4 U2 windows.
```

Disclaimer:

```text
Research-only. Not investment advice. Not a buy recommendation. No guaranteed return.
```

Data limitation:

```text
Controlled validation remains limited and uses current-snapshot universe,
listing, ST, and suspension-status constraints.
```

The wording describes historical group-level evidence. It does not assign
lower risk or expected return to an individual member.

## Display Model

The presentation helper returns:

- `available`;
- `research_only`;
- `claim_supported`;
- `status`;
- `list_id`;
- title and badge;
- evidence note and excess-return caveat;
- disclaimer and data limitation;
- why-included and why-not-a-recommendation explanations;
- the frozen U2 window counts and comparison list identifiers.

It does not return a new defensive score, target return, position size, or
action instruction.

## Fail-Closed Behavior

The helper validates the configured list identifier, required wording, U2
window counts, and comparison-list metadata.

If the config or required evidence is absent or malformed:

```text
status = defensive_evidence_unavailable
available = false
claim_supported = false
badge = null
message = Defensive evidence unavailable.
```

The HTML page then shows the unavailable message without the defensive badge.
List membership alone is never treated as proof of defensive support.

## Data And Execution Boundary

The stub:

- reads the existing `long_term_stable` list output through `OutputLoader`;
- preserves the existing `items` array, order, and ranks;
- uses a versioned, static presentation config based on consumed U2 evidence;
- performs no provider request;
- runs no validation or label computation;
- writes no output file;
- does not inspect new outcomes.

The config is explanatory metadata, not model input.

## Tests

Targeted tests cover:

- required research-only wording and caveats;
- absence of forbidden promotional wording;
- no overlay for other lists;
- fail-closed behavior for missing or incomplete evidence;
- unchanged API list membership and rank order;
- HTML and API presentation behavior.

Run:

```powershell
python -B -m pytest -p no:cacheprovider backend\tests\test_defensive_positioning.py backend\tests\test_api.py -q
```

## Non-Goals

Phase 2.32 does not change:

- scoring or ranking;
- factor formulas or validation math;
- candidate selection or list membership;
- thresholds;
- recommendation logic;
- portfolio construction;
- provider/cache behavior;
- generated outputs.

It does not claim stable excess return, validated alpha, guaranteed return, or
individual-member safety.

## Phase Decision

The minimal report/UI stub is permitted only as a research-only presentation
layer. Any future change to membership, score, rank, threshold, or production
recommendation requires a separate phase and new evidence contract.
