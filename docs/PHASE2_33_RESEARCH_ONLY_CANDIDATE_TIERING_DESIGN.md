# Phase 2.33 Research-Only Candidate Tiering Design

## Purpose

Phase 2.33 defines a presentation and interpretation layer over the existing
research lists. It does not replace, merge, rename, reorder, or recalculate
any list.

The design gives the operator one stable reading order:

1. defensive observation;
2. core research candidates;
3. trend observation;
4. active opportunity observation;
5. risk warning.

The tier number is a navigation order, not a quality rank, confidence score,
expected-return rank, or position priority. Tier 1 is not "better" than Tier
2, and Tier 5 is not an automatic exclusion.

## Evidence And Governance Boundary

This design follows the post-U2 decision ledger:

- `long_term_stable` is `defensive_positioning_only`;
- `high_confidence_candidates` is `research_only`;
- `breakout_watch`, `accumulation_watch`, and `rebound_watch` are
  `observation_only`;
- `trend_leaders` and `high_risk_active` are `not_confirmed`;
- no item currently permits a production change.

U2 supported the defensive drawdown interpretation of `long_term_stable`, but
its excess return was negative in 3/4 windows. U2 did not establish
`trend_leaders` as a stable positive baseline or `high_risk_active` as a
stable negative bucket. Active lists retained high-variance, mixed, or
sample-limited evidence.

These results define wording boundaries only. They do not authorize new
membership rules, scores, rankings, thresholds, or production behavior.

## Stable Tier Mapping

| Tier | Tier ID | Display name | Existing list IDs | Permitted posture |
|---|---|---|---|---|
| 1 | `defensive_observation` | Defensive Observation | `long_term_stable` | Research-only defensive and lower-drawdown context |
| 2 | `core_research_candidates` | Core Research Candidates | `high_confidence_candidates` | Selective research candidates with unstable cross-window evidence |
| 3 | `trend_observation` | Trend Observation | `trend_leaders` | Trend and momentum context; not a stable positive baseline |
| 4 | `active_opportunity_observation` | Active Opportunity Observation | `breakout_watch`, `accumulation_watch`, `rebound_watch` | Higher-variance opportunity discovery with explicit failure caveats |
| 5 | `risk_warning` | Risk Warning | `high_risk_active` | Caution and risk review only; not a confirmed stable negative bucket |

The mapping is one-to-one from each existing list into a presentation tier,
except Tier 4, which groups three unchanged observation lists. Grouping does
not combine their members, deduplicate overlaps, create a union list, or
change their internal ordering.

`insufficient_data` remains outside the five candidate tiers. It is a
data-quality state, not an opportunity or risk tier. A future UI should show
it separately as `Data insufficient`.

## Tier 1: Defensive Observation

### Existing list

`long_term_stable`

### Interpretation

This tier provides defensive context. In U2, the unchanged list had shallower
average holding-period drawdown than `trend_leaders`, `breakout_watch`, and
`accumulation_watch` in 4/4 controlled windows.

The excess-return evidence must appear beside that result: excess return was
negative in 3/4 U2 windows and was not stable.

### Allowed wording

- `Research-only defensive observation`
- `Historically shallower drawdown in the controlled U2 comparison`
- `Risk-control context`
- `Excess return was not stable`
- `Group-level evidence; individual risk may differ`

### Required caveat

Defensive describes historical group-level drawdown behavior. It is not a
safety claim, return forecast, or statement of fundamental quality.

## Tier 2: Core Research Candidates

### Existing list

`high_confidence_candidates`

### Interpretation

This tier preserves the project's most selective existing candidate list as a
research baseline. U1 and U2 did not establish stable cleanliness, coverage,
or excess return together.

The word "core" means central to the research workflow. It does not mean
production-approved, validated, or suitable for action.

### Allowed wording

- `Core research candidates`
- `Selective research baseline`
- `Evidence and counter-evidence required`
- `Coverage and cross-window stability remain under review`
- `Research-only`

### Required caveat

The list is not a production action list and has not established stable alpha.
Favorable windows must not hide unstable coverage or contradictory windows.

## Tier 3: Trend Observation

### Existing list

`trend_leaders`

### Interpretation

This tier presents existing trend, momentum, and relative-strength context.
U2 did not support the unchanged list as a stable positive baseline.

### Allowed wording

- `Trend observation`
- `Momentum and trend context`
- `Regime-dependent evidence`
- `Crowding sensitivity remains a research question`
- `Not confirmed as a stable positive baseline`

### Required caveat

Trend strength is descriptive context. It does not establish future
outperformance, and the current outputs do not directly prove crowding as the
cause of weak windows.

## Tier 4: Active Opportunity Observation

### Existing lists

- `breakout_watch`
- `accumulation_watch`
- `rebound_watch`

### Interpretation

This tier keeps active opportunity discovery visible without promoting it to
high confidence. The three lists remain separate:

- `breakout_watch` observes breakout and acceleration behavior;
- `accumulation_watch` observes staging and participation behavior;
- `rebound_watch` observes recovery behavior with limited samples.

Their evidence is mixed or high variance. A favorable right tail or one strong
window must not override drawdown, weak outperform consistency, contamination,
or sample limitations.

### Allowed wording

- `Active opportunity observation`
- `Higher-variance research view`
- `Opportunity discovery with explicit risk review`
- `Waiting for confirmation`
- `Observation only`

### Required caveat

This tier is not a high-confidence recommendation. Each source list must show
its own sample size, contradictory windows, downside evidence, and
list-specific failure risks.

## Tier 5: Risk Warning

### Existing list

`high_risk_active`

### Interpretation

This tier is a caution layer. U1 showed a negative direction with small
samples, while U2 was directionally mixed and below its preregistered sample
gate. The stable-negative interpretation was not confirmed.

### Allowed wording

- `Risk warning`
- `Caution layer`
- `Requires additional risk review`
- `U2 did not confirm a stable negative bucket`
- `Not an automatic exclusion`

### Required caveat

Membership is not an instruction to avoid, remove, or take an opposing
position. It is not a confirmed short signal. Any automatic exclusion rule
would require a separately frozen hypothesis and a new holdout.

## Original Lists Remain Authoritative

The source list contract remains unchanged:

- original list IDs and display names remain visible;
- each tier links to the existing list output;
- member arrays are read as-is;
- source-list order and rank are preserved;
- overlaps between lists remain visible;
- no cross-tier rank is calculated;
- no tier-level union or portfolio is created.

If one symbol appears in several lists, the UI may show each source membership.
It must not choose a "winning" tier or synthesize a new eligibility decision.

## Allowed Wording Contract

Every tier must use research language:

- `research-only`;
- `observation`;
- `candidate research`;
- `waiting for confirmation`;
- `evidence`;
- `counter-evidence`;
- `risk warning`;
- `data insufficient`;
- `not confirmed`;
- `current-snapshot limited`.

Evidence wording must name its scope. For example, a U2 statement must identify
the controlled panel and must not be generalized to all periods or all
members.

## Forbidden Wording And Implications

The report or UI must not say or imply:

- `guaranteed gain`;
- `stable profit`;
- `must buy`;
- `safe stock`;
- `validated alpha`;
- `production recommendation`;
- `risk-free`;
- `automatic exclusion`;
- `confirmed short signal`;
- `confirmed avoid signal`;
- `stable excess return` where the evidence does not support it;
- that a higher tier number or lower tier number is an action priority.

Colors, icons, badges, default sorting, and section placement must not imply
these forbidden meanings indirectly.

## Future Report Field Contract

A future read-only tiering report may expose:

### Tier fields

- `tier_id`;
- `tier_order`;
- `tier_name`;
- `tier_badge`;
- `research_only = true`;
- `interpretation`;
- `allowed_claim`;
- `required_caveat`;
- `source_list_ids`;
- `metadata_version`.

### List-level fields

- existing `list_id` and `list_name`;
- `as_of_date`;
- existing `item_count`;
- existing eligibility and sort descriptions;
- decision-ledger status;
- evidence summary;
- counter-evidence summary;
- sample and coverage context;
- drawdown and excess-return caveats where already available;
- point-in-time and current-snapshot limitations;
- link to the unchanged source list.

### Item-level fields

- symbol and name from the source list;
- source list memberships;
- original rank and existing score fields;
- `why included`: the existing list membership reason only;
- existing confirmation and invalidation signals;
- item-level risk flags already present;
- tier-specific risk caveat;
- data-quality status;
- research-only label.

No field may contain a new tier score, combined rank, action instruction,
position size, target return, or inferred membership.

## Future UI Layout

### Global header

- Title: `Research Candidate Tiers`
- Badge: `Research-only`
- Introductory caution: tiers organize existing lists for reading; they do not
  change selection or establish action priority.

### Section order and badge text

1. `Defensive Observation`
2. `Core Research`
3. `Trend Observation`
4. `Active Opportunity Observation`
5. `Risk Warning`

`Data insufficient` appears in a separate status section after the five tiers.

### Tooltip text

| Tier | Tooltip |
|---|---|
| Defensive Observation | Historical group-level drawdown context; excess return was not stable |
| Core Research | Selective existing research list; not production-approved |
| Trend Observation | Trend and momentum context; stable positive behavior was not confirmed |
| Active Opportunity Observation | Higher-variance discovery lists requiring explicit failure and downside review |
| Risk Warning | Caution context only; not an automatic exclusion or confirmed negative signal |

### Caution boxes

Each tier section must keep its required caveat visible without hover. Tier 1
must show the unstable-excess caveat beside the drawdown evidence. Tier 4 must
show high-variance and failure-risk language. Tier 5 must state that U2 did not
confirm a stable negative bucket.

### List and item presentation

- Keep each original list as a distinct subsection.
- Show the existing list name more prominently than the tier metadata.
- Use compact evidence rows rather than a new promotional score.
- Preserve source rank and membership.
- Show `why included` as an explanation of existing membership.
- Show item risk caveats at the same visual level as positive evidence.
- Do not use celebratory styling, action colors, or icons that imply approval.

## Fail-Closed Behavior

A future implementation must use a versioned tier metadata map.

If tier metadata is missing or invalid:

- do not infer a tier from a list name, score, rank, or member attributes;
- show the unchanged source list without a tier badge, or omit it from the
  tiered view;
- display `Tier metadata unavailable`;
- preserve the source list and its link;
- write no generated or production output.

If evidence metadata is missing:

- retain the neutral tier name only when its mapping is valid;
- suppress the evidence claim;
- display `Tier evidence unavailable`;
- never substitute a generalized positive or negative claim.

An unknown future list remains unclassified until its tier metadata is
explicitly reviewed. `insufficient_data` must never be promoted into a
candidate tier.

## Future Implementation Boundaries

If Phase 2.34 implements a UI/API stub, it must:

1. remain behind explicit research-only framing;
2. use a static, versioned mapping from existing list IDs to tiers;
3. read list membership and rank without modifying them;
4. add no tier score or cross-list ranking;
5. change no scoring, factor, threshold, or validation formula;
6. change no daily production recommendation output;
7. launch no portfolio recommendation;
8. perform no provider request or validation job;
9. fail closed when mapping or evidence metadata is absent;
10. test that source list items, order, rank, and counts remain unchanged.

Any later change to list construction, tier membership semantics, eligibility,
or production behavior requires a separate phase, a versioned hypothesis, and
new preregistered evidence.

## Explicit Non-Goals

Phase 2.33 does not:

- implement API or UI code;
- rename or replace existing lists;
- create a new candidate list;
- combine list members;
- change list membership or ordering;
- change scoring, ranking, factors, thresholds, or validation math;
- create a portfolio or production recommendation;
- run validation or inspect a new outcome;
- access a provider;
- modify generated outputs.

## Recommended Next Phase

If implementation is desired, the next phase should be:

`Phase 2.34 Research-Only Candidate Tiering UI/API Stub`

That phase should implement only the static presentation mapping and
fail-closed behavior defined here. If implementation is not needed, this
document remains the frozen interpretation contract.

## Phase Decision

The five-tier design organizes the existing research lists without changing
their meaning or mechanics. It keeps defensive context, selective research,
trend context, active opportunity discovery, and risk warning visible at the
same time while preserving contradictory evidence.

No production scoring, ranking, factor formulas, validation math, candidate
selection, list membership, thresholds, recommendation logic, or portfolio
behavior is authorized or changed by Phase 2.33.
