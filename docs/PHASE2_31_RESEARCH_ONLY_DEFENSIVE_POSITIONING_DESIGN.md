# Phase 2.31 Research-Only Defensive Positioning Design

## Purpose

Phase 2.31 defines a report and UI presentation contract for the unchanged
`long_term_stable` list. It is a research design document, not an
implementation, validation run, portfolio construction method, or production
launch.

The permitted interpretation is narrow:

> `long_term_stable` is a research-only defensive observation list whose
> aggregate holding-period drawdown was shallower than three active comparison
> lists in all four controlled U2 windows. Its excess return was not stable.

"Defensive" describes observed group-level drawdown behavior in a specific
controlled panel. It does not mean that every member is safe, low risk, or
expected to outperform.

## Evidence Boundary

The presentation contract is based on already consumed evidence:

- U1: four controlled 2024 20D windows;
- U2: four controlled 2025 20D windows;
- approximately 300 symbols per controlled window;
- point-in-time guarded price and feature inputs;
- current-snapshot limitations for universe, listing, ST, and suspension
  status.

The central U2 result was:

- `long_term_stable` had shallower average holding drawdown than
  `trend_leaders`, `breakout_watch`, and `accumulation_watch` in 4/4 windows;
- its full-list mean drawdown was approximately -4.04%;
- its excess return was negative in 3/4 windows;
- its four-window mean excess return was approximately -1.09%;
- its top-10 view retained a shallow mean drawdown but also had negative
  excess return in 3/4 windows.

U1 provided directionally similar defensive context, but it does not turn U1
and U2 into proof of durable low risk or stable excess return. Both panels are
consumed and cannot validate a revised rule or presentation-derived
hypothesis.

## What Defensive Positioning Means

For this project, defensive positioning means:

1. a descriptive comparison of observed downside and drawdown;
2. a research view separated from return-seeking candidate promotion;
3. evidence shown at list level and by validation window;
4. explicit visibility of contradictory return evidence;
5. no change to the existing list membership, score, rank, or threshold.

It does not mean:

- capital protection;
- low absolute risk;
- stable profit or stable excess return;
- fundamental quality;
- suitability for a user, portfolio, or holding period;
- an instruction to take or avoid a position.

The word "defensive" must always be accompanied by the measured evidence,
comparison set, window scope, and excess-return caveat.

## Claim Contract

### Allowed claims

The report or UI may say:

- `research-only defensive observation list`;
- `risk-control candidate group for research`;
- `historically shallower drawdown in the four controlled U2 windows`;
- `shallower aggregate drawdown than the three named active comparison lists
  in 4/4 U2 windows`;
- `excess return was not stable`;
- `group-level evidence does not imply that each member is low risk`;
- `current membership logic is unchanged`;
- `not investment advice or a production recommendation`.

### Forbidden claims

The report or UI must not say or imply:

- `guaranteed small gain`;
- `safe stock portfolio`;
- `stable profit`;
- `must buy`;
- `high-confidence return source`;
- `production recommendation`;
- `validated alpha`;
- `risk-free`;
- `low-risk guarantee`;
- `stable excess return`;
- `fundamentally stable company` based only on the current technical data.

Synonyms, badges, colors, icons, and ordering must not communicate these
forbidden claims indirectly.

## Future Report Field Contract

A later read-only report should expose the following fields without creating
a new score or changing membership.

### Identity and provenance

| Field | Requirement |
|---|---|
| `list_id` | Exact unchanged value: `long_term_stable` |
| `display_name` | `Long-Term Stable: Defensive Research View` |
| `presentation_status` | `research_only_defensive_observation` |
| `as_of_date` | Date of the existing list snapshot |
| `membership_source` | Existing list output and version/commit where available |
| `research_only` | Always `true` |

### Evidence

| Field | Requirement |
|---|---|
| `defensive_rationale` | Plain-language description of relative drawdown evidence |
| `evidence_window_count` | Number of controlled windows represented |
| `valid_member_count_by_window` | Keep per-window samples visible |
| `average_holding_drawdown_by_window` | Show every window, not only the mean |
| `comparison_lists` | Name the active lists used in the comparison |
| `drawdown_gap_by_comparator` | Difference versus each comparator by window |
| `shallower_drawdown_window_count` | Show numerator and denominator, such as 4/4 |
| `volatility_context` | Existing observed volatility context only |
| `benchmark_symbol` | Resolved benchmark identity |
| `benchmark_quality` | Existing benchmark data-quality status |
| `benchmark_return_by_window` | Context, not a return promise |
| `average_excess_return_by_window` | Show contradictory windows explicitly |
| `positive_excess_window_count` | Show numerator and denominator |
| `mean_and_median_excess_return` | Both required; never show mean alone |

### Integrity and limitations

| Field | Requirement |
|---|---|
| `leakage_guard_applied` | Existing point-in-time guard status |
| `no_future_leakage` | Existing validation status |
| `feature_input_point_in_time_status` | Existing metadata |
| `future_label_window_status` | Existing metadata |
| `universe_point_in_time_status` | Preserve `current_snapshot_limited` when applicable |
| `listing_status_point_in_time_status` | Preserve current limitation |
| `st_status_point_in_time_status` | Preserve current limitation |
| `suspension_status_point_in_time_status` | Preserve current limitation |
| `turnover_status` | Explicitly state when turnover is unvalidated |
| `data_limitations` | Human-readable limitations list |
| `excess_return_caveat` | Required statement that excess return was unstable |
| `risk_warnings` | Required, visible, and member-specific where data exists |

A report must fail closed when required evidence is absent. It should display
`data_insufficient_for_defensive_context` rather than a defensive badge based
only on list membership.

## Recommended Report Wording

### Summary

> In the four controlled U2 windows, the unchanged `long_term_stable` group
> had shallower average holding-period drawdown than `trend_leaders`,
> `breakout_watch`, and `accumulation_watch` in 4/4 comparisons. Its excess
> return was negative in 3/4 U2 windows and was not stable. This is
> research-only defensive context, not an investment recommendation, safety
> guarantee, or expected-return claim.

### Why included

> This symbol appears because it is a member of the existing
> `long_term_stable` list for the selected as-of date. Phase 2.31 does not
> change membership, rank, score, or eligibility. The defensive label refers
> to historical group-level drawdown evidence and does not establish lower
> risk for this individual symbol.

### Why this is not a recommendation

> Controlled group-level drawdown evidence does not predict an individual
> member's return or downside. Excess return was unstable, the validation
> panel was limited, turnover was not fully evaluated, and historical
> universe/status metadata remains current-snapshot limited.

### Standard disclaimer

> Research-only. This view is for personal research and is not investment
> advice, a portfolio recommendation, a guarantee of safety, or a guarantee
> of return. Prices can decline, and defensive historical behavior may not
> persist.

## Future Dashboard And UI Contract

Phase 2.31 does not implement UI. A later stub should use the following
presentation hierarchy.

### Section header

- Page or section title: `Defensive Positioning Research`
- List title: `Long-Term Stable`
- Badge: `Research-only / Defensive observation`
- Badge style: neutral and cautionary; never use a success, approval, or
  recommendation treatment.

### Badge tooltip

> A research-only group with shallower aggregate drawdown than three active
> comparison lists in the controlled U2 panel. This does not imply stable
> excess return, guaranteed safety, or low risk for each member.

### Evidence strip

Show compact, comparable facts before the member list:

- controlled windows represented;
- valid members by window;
- shallower-drawdown comparisons;
- mean and median drawdown;
- per-window excess-return signs;
- benchmark context;
- point-in-time and data-quality status.

Do not show a single composite "defensive score." Do not sort members by a new
Phase 2.31 metric.

### Caution box

The caution box must remain visible without hover:

> Defensive describes historical group-level drawdown behavior, not safety.
> Excess return was unstable. Current-snapshot universe and status
> limitations remain. Membership and production logic are unchanged.

### Item-level evidence card

If a later UI uses item cards, each card should show only existing,
point-in-time fields:

- symbol and company name when already available;
- as-of date;
- unchanged list membership;
- existing volatility and drawdown context;
- existing risk/status labels;
- data-quality or missing-data status;
- `why included`;
- `why not a recommendation`.

An item card must not display a new return target, defensive score, confidence
upgrade, position size, or action instruction.

### Empty and incomplete states

- Missing list output: `Defensive research view unavailable for this date.`
- Missing evidence fields: `Evidence incomplete; defensive comparison not
  shown.`
- Failed quality or leakage checks: hide the badge and show the failed guard.
- Empty membership: show an empty research state, not a substitute list.

## Visual And Interaction Guardrails

- Keep the research-only badge adjacent to the list title.
- Keep the excess-return caveat visible at the same hierarchy as the drawdown
  evidence.
- Use tables or compact evidence rows for cross-window comparison.
- Do not use celebratory colors, upward arrows, trophies, or approval marks.
- Do not place the disclaimer behind a modal or tooltip only.
- Do not label an individual member as safe because the group was defensive.
- Do not default-sort the list by future return or any validation outcome.

## Future Implementation Boundaries

If Phase 2.32 implements a report or UI stub, it must:

1. be behind an explicit research-only route, mode, or feature flag;
2. read existing list and validation outputs only;
3. preserve provenance and point-in-time/bias metadata;
4. make no provider request and run no validation implicitly;
5. make no member-rule, score, rank, factor, or threshold change;
6. make no production daily recommendation change;
7. write no production recommendation or portfolio output;
8. avoid a new composite defensive score;
9. fail closed when evidence, quality, or leakage metadata is unavailable;
10. retain the exact excess-return caveat and research-only disclaimer.

Any later proposal to alter membership, ranking, scoring, thresholds, or
recommendation behavior is outside this design. It requires a separately
versioned hypothesis, a preregistered unopened holdout, and an explicit
production review. U1 and U2 cannot be reused as confirmation.

## Acceptance Checklist For A Later Stub

A later report/UI stub is acceptable only if:

- `research_only = true` is visible and machine-readable;
- drawdown evidence and unstable excess-return evidence are both visible;
- per-window samples and contradictory windows are retained;
- the comparison lists and evidence dates are named;
- current-snapshot bias limitations are shown;
- missing evidence suppresses the defensive claim;
- no action language or return promise is present;
- production outputs and logic remain byte-for-byte unaffected by the stub.

## Explicit Non-Goals

Phase 2.31 does not:

- implement a report, dashboard, or UI;
- change `long_term_stable` membership or list construction;
- create a portfolio or position-sizing method;
- change scoring, ranking, factors, labels, thresholds, or recommendations;
- claim stable excess return, validated alpha, safety, or guaranteed return;
- infer fundamental quality from technical evidence;
- run validation or inspect a new outcome;
- access a provider;
- modify generated outputs.

## Recommended Next Phase

If implementation is desired, the next phase should be:

`Phase 2.32 Research-Only Defensive Positioning Report/UI Stub`

That phase should implement only the presentation contract above behind a
research-only boundary. It should not change production behavior. If no
implementation is needed, the correct next step is to retain this document as
the frozen presentation contract and wait for a separately preregistered
holdout.

## Phase Decision

`long_term_stable` may be presented as a research-only defensive observation
list because U2 showed shallower aggregate drawdown than the three active
comparison lists in 4/4 controlled windows. It must simultaneously disclose
that excess return was unstable and negative in 3/4 U2 windows.

No production scoring, ranking, factor formulas, validation math, candidate
selection, list membership, thresholds, recommendation logic, or portfolio
