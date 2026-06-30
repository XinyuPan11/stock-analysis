# Phase 2.13C Existing-Data Candidate Feature Gap Design

## Status And Boundary

Phase 2.13C is a read-only answer-key post-mortem design phase. It uses the
Phase 2.13B findings to identify general feature gaps, but it does not use the
known 2024 outcomes to select thresholds or claim model improvement.

This phase does not change:

- production scoring or ranking
- candidate-list or recommendation logic
- factor or validation-label calculations
- thresholds
- external data sources

The proposed fields are research hypotheses. They must be frozen before being
evaluated, then must be tested on unseen windows. The 2024 answer-key cases
cannot validate them.

## Evidence Inspected

The design is grounded in existing local artifacts:

- `outputs/daily/factors_<as_of_date>.csv`
- `outputs/validation/walk_forward_predictions_<as_of_date>_20d.csv`
- `outputs/lists/<list_id>_<as_of_date>.json`
- `outputs/experiments/positive_list_weakness_attribution_2024.json`
- `outputs/experiments/answer_key_case_study_learning_2024.json`
- `research/case_studies/case_study_filled_2024.csv`
- the existing point-in-time factor and list builders

The current factor snapshots already expose 20/60/120-day momentum and
relative strength, moving-average state, 20/60-day volatility and drawdown,
and 20/60-day average amount and volume. Raw daily cache also contains
point-in-time OHLCV and amount history.

## What Existing Data Can Explain

| Missed-winner behavior | Existing-data approximation | Confidence | Boundary |
|---|---|---|---|
| Low-position reversal | Rolling price position, drawdown from prior high, short/medium momentum turn, moving-average reclaim | Medium | Detects price behavior after reversal starts; does not identify why it reverses |
| Theme/event acceleration | Amount/volume expansion, volatility expansion, return acceleration, relative-strength inflection | Low to medium | Detects market response, not the catalyst or theme |
| High-volatility right tail | Upside-return concentration, volatility expansion, range expansion, strong close and amount expansion | Medium | High false-positive risk from speculative surges and false breakouts |
| Trend continuation/acceleration | Multi-horizon momentum slope, moving-average spread, relative-strength acceleration | Medium | Can be late and vulnerable to crowding reversal |
| Accumulation/watch persistence | Repeated membership across saved list snapshots plus sustained amount/relative-strength improvement | Partial | Historical list snapshots are sparse and not yet a durable daily state history |
| False breakout/crowding reversal | High rolling price position, stretched moving-average distance, volatility/amount spike followed by weak close or momentum decay | Medium | Price-only crowding proxy; cannot observe holders or theme persistence |

These are behavioral approximations, not causal classifications.

## What Existing Data Cannot Reliably Explain

The following case-study labels cannot be inferred reliably from price,
volume, factors, or list membership:

- policy or concept-theme identity
- restructuring, control-change, transaction, or other event causality
- fundamental turnaround or deterioration
- industry-cycle or sector repricing attribution
- theme fade versus an ordinary technical reversal
- historical announcement, ST, listing, or suspension state when no
  point-in-time snapshot exists

A price/volume response may flag that something changed. It cannot establish
what changed. Phase 2.13C therefore does not create synthetic event, theme,
industry, or fundamental labels.

## Member-Level As-Of Snapshot

A future read-only prototype should produce one row per `symbol + as_of_date`.
The snapshot must be created before labels are joined and must contain no
future-return or future-drawdown columns.

### Identity And Provenance

- `symbol`
- `as_of_date`
- `snapshot_schema_version`
- `source`
- `data_points`
- `latest_input_date`
- `max_raw_cache_date`
- `future_rows_excluded_count`
- `leakage_guard_applied`
- `data_quality_status`
- `warnings`

Required invariant:

```text
latest_input_date <= as_of_date
```

### Existing Factor Values

Retain the current values without changing their formulas:

- `momentum_20d`, `momentum_60d`, `momentum_120d`
- `rs_20d`, `rs_60d`, `rs_120d`
- `ma5`, `ma20`, `ma60`
- `above_ma20`, `above_ma60`, `ma_bullish_alignment`
- `volatility_20d`, `volatility_60d`
- `max_drawdown`, `max_drawdown_20d`, `max_drawdown_60d`
- `avg_amount_20d`, `avg_amount_60d`
- `avg_volume_20d`, `avg_volume_60d`

Existing scores may be copied for attribution, but they must not be
recalculated or reweighted in this phase.

### Membership Context

- one boolean per existing list
- `positive_list_membership_count`
- `risk_list_membership_count`
- membership source-file date
- optional prior-snapshot membership count when earlier snapshots exist
- explicit `membership_history_available` flag

Missing historical snapshots must remain missing. They must not be interpreted
as non-membership.

### Prototype Feature Values

Prototype features should be continuous raw values and cross-sectional ranks,
not fitted binary thresholds. Every field should include a definition version
and minimum-history requirement.

The output may later use a path such as:

```text
outputs/experiments/candidate_feature_snapshot_<as_of_date>.csv
```

No snapshot writer is implemented in Phase 2.13C.

## Candidate Feature Families

### 1. Low-Position Reversal Proxy

**Intuition:** distinguish an early recovery from mature trend leadership.

**Existing inputs:** adjusted close/high/low, momentum 20/60/120D, drawdown,
moving averages, relative strength.

**Candidate continuous fields:**

- close position within trailing 120/250-session range
- drawdown from trailing 120/250-session high
- short-versus-medium momentum change
- relative-strength inflection
- moving-average reclaim state and distance

**Point-in-time safety:** safe when every rolling window ends at
`as_of_date`.

**Leakage risks:** using the eventual rebound low/high, a full-year range, or a
threshold selected from the known 2024 winners.

**Expected coverage:** low-position reversal, oversold rebound, distressed or
turnaround repricing after price confirmation begins.

**Expected pollution:** value traps, weak fundamentals, delisting/status
risk, and temporary rebounds.

**Posture:** read-only prototype only; it cannot identify the underlying
revaluation cause.

### 2. Volume And Amount Expansion Proxy

**Intuition:** identify new participation rather than absolute liquidity
alone.

**Existing inputs:** daily amount and volume plus current 20/60-day averages.

**Candidate continuous fields:**

- recent amount relative to its 20/60-session baseline
- recent volume relative to its 20/60-session baseline
- count and concentration of expansion days
- price response per unit of amount expansion
- amount expansion accompanied by relative-strength improvement

**Point-in-time safety:** safe with trailing windows ending at the as-of date.

**Leakage risks:** normalizing with future observations or defining an
"abnormal" event from the known subsequent move.

**Expected coverage:** theme acceleration, event response, accumulation, and
early breakout behavior after participation appears.

**Expected pollution:** one-day news spikes, false breakouts, theme fade, and
illiquid price manipulation.

**Posture:** read-only prototype only.

### 3. Accumulation And Watchlist Persistence Proxy

**Intuition:** separate repeated, strengthening observation from a one-date
list appearance.

**Existing inputs:** saved list membership, factor snapshots, amount,
relative strength, trend state.

**Candidate continuous fields:**

- appearances across available prior snapshots
- time since first available appearance
- changes in momentum, relative strength, amount, and risk state while present
- overlap transitions among accumulation, trend, breakout, and risk lists

**Point-in-time safety:** safe only when each referenced snapshot was generated
on or before the current as-of date.

**Leakage risks:** reconstructing prior membership with current formulas or
treating absent snapshot files as negative membership.

**Expected coverage:** gradual accumulation and persistent trend formation.

**Expected pollution:** stale watchlist members and slowly weakening trends.

**Posture:** partially available. A durable point-in-time list-history store is
needed before persistence is reliable.

### 4. Right-Tail Volatility Proxy

**Intuition:** distinguish asymmetric upside expansion from uniformly noisy
volatility.

**Existing inputs:** OHLCV, amount, volatility 20/60D, momentum, drawdown,
relative strength.

**Candidate continuous fields:**

- volatility 20D relative to volatility 60D
- upside versus downside return concentration
- largest positive return contribution within a trailing window
- intraday range expansion and close location
- right-tail behavior confirmed by amount and relative strength

**Point-in-time safety:** safe when calculated only from completed bars through
the as-of date.

**Leakage risks:** labeling a move as right-tail because its future return is
known, or selecting cutoffs from the 2024 winner cases.

**Expected coverage:** high-volatility right-tail and rapid repricing patterns.

**Expected pollution:** speculative spikes, unstable small samples, false
breakouts, and severe drawdowns.

**Posture:** read-only observation bucket only, never a quality substitute.

### 5. Trend Acceleration Proxy

**Intuition:** measure change in trend strength rather than only its current
level.

**Existing inputs:** momentum and relative strength at 20/60/120D, moving
averages, amount and volatility.

**Candidate continuous fields:**

- short-horizon momentum relative to medium/long-horizon pace
- relative-strength acceleration
- moving-average spread and spread change
- return acceleration confirmed by amount
- trend acceleration adjusted for volatility expansion

**Point-in-time safety:** safe when current and lagged values are both
point-in-time snapshots.

**Leakage risks:** using a later snapshot as the lag, survivorship-biased
membership, or tuning the acceleration boundary to known winners.

**Expected coverage:** trend continuation, semiconductor/industry repricing
after price confirmation, and theme acceleration.

**Expected pollution:** late-cycle leaders, crowded momentum, and exhaustion.

**Posture:** read-only prototype only.

### 6. False-Breakout And Crowding-Reversal Risk Proxy

**Intuition:** retain potential right-tail observations while separately
measuring reversal risk.

**Existing inputs:** rolling highs, moving-average distance, momentum,
volatility, drawdown, amount/volume and close location.

**Candidate continuous fields:**

- price position near a trailing high
- distance above medium-term moving averages
- long-horizon momentum with short-horizon deceleration
- amount/volume spike without sustained close strength
- volatility expansion plus recent drawdown or failed high

**Point-in-time safety:** safe when failed-high logic uses only highs already
observed by the as-of date.

**Leakage risks:** calling a breakout false only because the future decline is
known, or using future maximum drawdown.

**Expected coverage:** high-position crowding reversal, technical theme fade,
and false breakout risk.

**Expected pollution:** legitimate consolidations and strong trends pausing
before continuation.

**Posture:** read-only risk diagnostic only.

## Evaluation Contract For A Later Phase

1. Freeze feature names, formulas, lookback conventions, and missing-data
   behavior before opening unseen outcomes.
2. Materialize feature snapshots independently from validation labels.
3. Verify point-in-time diagnostics for every row.
4. Join labels only inside an explicit evaluator.
5. Compare continuous distributions and broad predeclared cohorts first.
6. Report sample size, overlap, coverage, downside, and regime stability.
7. Do not select production thresholds from the 2024 answer-key cases.
8. Require separate unseen-window evidence before considering any production
   candidate-list experiment.

## Recommended Next Step

The next minimal phase should define a versioned, read-only member-level
snapshot schema and generate a small dry-run for one as-of date. It should
verify column availability and point-in-time boundaries only. It should not
rank candidates, create a new production list, or evaluate thresholds.

## Known Limitations

- Existing saved list history is sparse.
- Historical universe, listing, ST, and suspension metadata remain
  current-snapshot limited.
- Price/volume behavior cannot identify event, policy, theme, industry, or
  fundamental causality.
- The 30 researched cases are deliberately selected answer-key cases, not a
  representative blind sample.
- No production-quality claim follows from this design.
