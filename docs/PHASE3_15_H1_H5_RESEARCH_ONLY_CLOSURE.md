# Phase 3.15 H1-H5 Research-Only Closure

## Closure Decision

Phase 3 is closed as the H1-H5 historical research and validation track.
The historical sealed execution was valid, completed, analyzed, and consumed.
It produced no `supported_research_only` hypothesis and no hypothesis eligible
for production design. The frozen H1-H5 boolean cohorts remain research
artifacts and authorize no change to production behavior.

The next major project line is:

```text
Phase 4.1 Production Candidate Research Foundation and Baseline Audit
```

Phase 4.1 is a new research-foundation phase, not an H1-H5 production
implementation phase. It must not change production logic.

## Historical Validation Identity And Consumption

| Field | Final value |
|---|---|
| Validation ID | `h1h5-historical-sealed-v1` |
| Evidence level | `historical_sealed_not_prospective` |
| Benchmark | `CSI300` |
| Horizon | 20 trading days |
| Primary windows | `2026-01-30`, `2026-03-31`, `2026-04-30` |
| Historical sealed validation | Complete and consumed |
| Production change | `false` |

The three historical windows are opened evidence. Their results may be
retained as historical research context, but they can never be described as
fresh, unseen, sealed, or prospective evidence again. They may not validate
a revised H1-H5 rule, threshold, feature definition, or interpretation.

Historical sealed evidence is separate from and weaker than prospective U3
evidence. Phase 3.14 did not consume U3.

## Final H1-H5 Decision Ledger

| Hypothesis | Concept | Final status | Production use | Allowed use |
|---|---|---|---|---|
| H1 | Low-position revaluation opportunity | `underpowered` | Prohibited | Historical research reference only |
| H2 | Trend acceleration with crowding guard | `mixed_research_only` | Prohibited | Research-only display; explanatory research tag; candidate feature concept for a future independent Phase 4 framework |
| H3 | Right-tail opportunity | `underpowered` | Prohibited | Historical research reference only |
| H4 | High-position crowding risk | `underpowered` | Prohibited | Research-only risk concept; future continuous risk-feature hypothesis |
| H5 | False-breakout risk | `underpowered` | Prohibited | Research-only display; explanatory risk caveat; future continuous risk-feature hypothesis |

H2 is not a validated ranking, selection, or recommendation rule. H4 must not
automatically exclude candidates. H5 must not automatically down-rank or
exclude candidates. Existing H4/H5 research annotations remain non-blocking.

Any future continuous version of an H1-H5 concept is a new candidate research
feature. It inherits no evidence, status, or eligibility from the frozen
boolean cohort bearing the same conceptual name.

## Sample Sufficiency And Interpretation

Phase 3.14 executed 15 cohort-window evaluations:

- only H2 on `2026-04-30` reached the preregistered minimum of 20 valid cohort
  labels;
- 14 of 15 cohort-window evaluations were underpowered;
- no H received `supported_research_only`;
- no H showed strong, repeated, cross-window evidence;
- no H received production-design eligibility.

The correct distinctions are:

- **Not proven useful** means the evidence did not establish reliable benefit.
  It is not permission to use the concept in production.
- **Proven harmful** would require adequately powered, repeatable adverse
  evidence. Phase 3 does not assign this conclusion to underpowered cohorts.
- **Underpowered** means sample or empty-cohort gates prevent reliable
  interpretation. It is neither proof of ineffectiveness nor a reason to
  speculate that production use may work.
- **Mixed** means usable observations or metrics disagree or point in
  different directions. H2 remains research-only.
- **Production eligible** would require separate, adequate evidence and an
  explicit production-governance decision. No H1-H5 hypothesis meets it.

The result does not prove that every underlying market concept is permanently
useless. It establishes that the frozen narrow boolean cohort implementations
did not provide sufficient evidence for production use.

## Prohibited Production Decisions

Phase 3 evidence does not authorize:

- reweighting `total_score` or adding H1-H5 terms to it;
- changing current factor weights;
- changing `high_confidence_candidates` membership;
- changing `trend_leaders` membership or ranking;
- changing `breakout_watch`, `accumulation_watch`, or `rebound_watch`
  production behavior;
- automatic `high_risk_active` exclusion;
- automatic H4/H5 exclusion, penalty, demotion, or gating;
- production candidate gating or ranking changes;
- recommendation-language changes or buy/sell classification;
- ML training based on Phase 3 result status;
- behind-flag H1-H5 production implementation;
- production API or UI behavior changes.

Phase 3 also authorizes no claim of validated alpha, guaranteed return,
inevitable price movement, stable profit, or public investment advice.

## Allowed Research-Only Uses

The following uses remain allowed:

- retain frozen H1-H5 artifacts for historical audit;
- retain existing research-only H1-H5 display and API behavior without
  changing production data or decisions;
- retain H2 as an explanatory research tag;
- retain H5 as an explanatory, non-blocking risk caveat;
- discuss H4 as a research-only risk concept;
- translate H1-H5 conceptual ingredients into new continuous candidate
  features in a future Phase 4 research framework;
- reuse Phase 3 point-in-time, sealing, identity, label/evaluator separation,
  readiness, and result-governance infrastructure;
- use empty, weak, mixed, and underpowered findings to improve research design.

Continuousized H1-H5 concepts require new definitions, identities, governance,
and validation. They are not validated rules and may not reuse the consumed
historical windows as fresh proof.

## Prospective U3 Protection

U3 remains reserved exclusively for:

```text
2026-09-30
2026-12-31
```

The U3 validation identity, configs, dates, and governance remain unchanged.
Phase 3.14 historical results do not consume U3, and Phase 3.15 neither
modifies nor reinterprets it.

U3 must remain dormant until required future point-in-time snapshots and
outcomes exist. It cannot be reassigned as a Phase 4 holdout, pooled with the
historical panel, used to repair H1-H5 sample insufficiency, or opened early.
Retiring or repurposing U3 requires a separate explicit governance phase.

## What Phase 3 Successfully Contributed

Phase 3 produced durable research infrastructure:

- feature-only snapshot separation;
- point-in-time historical source snapshots;
- label-free cohort generation and membership freeze;
- preregistered label definitions;
- local-cache-only label-source generation;
- label-builder and evaluator separation;
- artifact digest, identity, date, schema, and membership guards;
- readiness and contamination checks;
- sealed-validation execution;
- explicit result-status governance;
- research-only versus production-eligibility boundaries.

Phase 3 infrastructure was successful. The specific frozen H1-H5 production
hypothesis set was not confirmed. A valid research system must preserve weak
results and reject challengers that do not pass evidence gates.

## Methodological Lesson And Phase 4 Rationale

The narrow boolean H1-H5 structure created sparse membership, empty cohorts,
and insufficient repeated cross-sectional samples. Honest sealed evaluation
was valuable, but this is not the preferred primary structure for the next
candidate-research line.

Future work should move from:

- narrow boolean condition sets;
- sparse cohort membership;
- direct sealed evaluation of early hypotheses;

toward:

- broad point-in-time continuous feature matrices;
- sufficient and visible cross-sectional coverage;
- factor quantile and monotonicity analysis;
- transparent rule-based challengers;
- chronological walk-forward testing;
- candidate-level and portfolio-level evaluation;
- explicit comparison with the frozen production baseline;
- optional ML ranking only after schemas, labels, temporal splits, metrics,
  and governance are frozen.

This transition does not implement Phase 4 or imply that continuous features
will succeed. It defines a structure that can measure weak, nonlinear, and
interacting signals without forcing early sparse membership decisions.

## Recommended Next Line: Phase 4.1

Phase 4.1 should:

- freeze and document the current production baseline;
- define unified point-in-time feature- and label-matrix contracts;
- inventory data, temporal coverage, provenance, and missingness;
- classify development, consumed, reserved, and future windows;
- define chronological walk-forward design;
- define factor-, candidate-, and portfolio-level metrics;
- define research and production eligibility gates before results are opened;
- prepare continuous challenger development without production changes.

Mean reversion should be one candidate feature family, not the entire roadmap.
Continuousized H1-H5 concepts may enter as candidate features, not validated
rules. ML should begin only after feature/label contracts and chronological
validation are frozen. Phase 4.1 must not change production logic.

## Phase 3 Final State

- H1-H5 infrastructure: complete
- Historical sealed validation: complete and consumed
- H1 final status: `underpowered`
- H2 final status: `mixed_research_only`
- H3 final status: `underpowered`
- H4 final status: `underpowered`
- H5 final status: `underpowered`
- `supported_research_only` hypotheses: none
- Production-design-eligible hypotheses: none
- Production logic changed: `false`
- U3 changed: `false`
- Next line: Phase 4 production candidate research foundation

## Phase 3.15 Repository Safety Record

Phase 3.15 is documentation and governance only. It did not:

- run validation, the evaluator, a backtest, or ML training;
- generate, inspect, or join new future outcomes or labels;
- generate cohorts, feature matrices, feature snapshots, or other outputs;
- tune H1-H5 thresholds or parameters;
- modify frozen H1-H5 configs or Phase 3.9 cohort outputs;
- modify Phase 3.13 label sources or Phase 3.14 validation outputs;
- modify U3 identity, configs, dates, artifacts, or governance;
- access a provider or prewarm cache;
- change production scoring, ranking, factors, candidate rules, list rules,
  thresholds, recommendations, UI, API, or behind-flag behavior.

The only intended repository change is this closure document. No tests are
required when the final diff contains documentation only.
