# Phase 4.1 Production Candidate Research Foundation And Baseline Audit

## Purpose

Phase 4.1 creates a reusable, machine-checkable foundation for future
production-candidate research. It freezes the current baseline, separates
point-in-time features from future labels, classifies historical evidence,
and defines comparative evaluation and production-eligibility governance.

This phase does not build a historical feature matrix, generate labels,
evaluate factors, train a model, run a backtest, implement a challenger, or
change production behavior.

## Why Phase 4 Starts With A Foundation

Phase 3 successfully built point-in-time snapshots, label-free cohorts,
separate label generation, digest guards, a sealed evaluator, and honest
result governance. Its frozen H1-H5 boolean cohorts did not pass production
gates: 14 of 15 cohort-window evaluations were underpowered, H2 was mixed,
and no hypothesis received `supported_research_only`.

The engineering infrastructure remains useful. The methodological lesson is
that sparse boolean cohorts are a poor primary representation for early
candidate discovery. Phase 4 therefore begins with broad continuous features,
visible coverage, baseline comparison, and chronological testing. A valid
research system must be able to reject weak challengers before prospective
proof is spent.

## Tracked Contracts

Phase 4.1 adds:

```text
research/configs/production_candidate_baseline.v1.json
research/configs/production_candidate_research_foundation.v1.json
backend/src/stock_analysis/research/production_candidate_foundation.py
backend/scripts/audit_production_candidate_foundation.py
backend/tests/test_production_candidate_foundation.py
```

The baseline was captured from:

```text
commit = 5f692914d17169d135d1c6da87de7e6c1e93525d
baseline_id = current-production-candidate-baseline
baseline_version = production-candidate-baseline-v1
benchmark = CSI300
production_change = false
```

The manifest records distributed behavior instead of pretending the baseline
is contained in one function.

## Actual Current Production Baseline

### Execution path

The current daily candidate path is:

1. `research/ashare_filters.py` filters the stock universe.
2. `research/factors.py` calculates completed-bar factors.
3. `research/scoring.py` normalizes and adds component points.
4. `research/recommendation_engine.py` sorts and takes Top-N.
5. `research/pipeline.py` writes daily candidate/factor artifacts.
6. `research/multi_label.py` creates explanatory research types and actions.
7. `research/multi_list.py` builds static research lists.
8. `backend/scripts/generate_research_views.py` writes those research views.
9. `workflow/config.py`, `workflow/steps.py`, and
   `workflow/daily_workflow.py` orchestrate the current daily flow.

No Phase 4.1 module imports or invokes those production modules. The audit
checks that the referenced paths exist.

### Universe and eligibility

The actual default universe guard:

- excludes ST/name-based ST or delisting risk;
- excludes non-normal listing status and populated out/delisting dates;
- requires at least 180 calendar days since listing when the date exists;
- inspects a 60-calendar-day price-quality window;
- requires at least 20 valid trading days;
- rejects severe missing OHLC/volume/amount/adjusted-close data above 20%;
- rejects nonpositive or inconsistent OHLC;
- requires 20 bars for the liquidity check;
- requires average 20-day amount of at least CNY 20 million;
- slices daily data to `trade_date <= as_of_date`.

Historical stock-universe membership, listing, ST, suspension, and delisting
state can still be current-snapshot-limited. This is a documented baseline
limitation, not silently treated as point-in-time history.

### total_score

`total_score` is an interpretable 100-point sum, not an ML output.

| Group | Component | Weight |
|---|---|---:|
| Momentum | `momentum_20d` | 7.50 |
| Momentum | `momentum_60d` | 10.00 |
| Momentum | `momentum_120d` | 7.50 |
| Trend | `above_ma20` | 6.00 |
| Trend | `above_ma60` | 6.00 |
| Trend | `ma_bullish_alignment` | 8.00 |
| Relative strength | `rs_20d` | 6.00 |
| Relative strength | `rs_60d` | 8.00 |
| Relative strength | `rs_120d` | 6.00 |
| Risk | `volatility_20d` | 6.00 |
| Risk | `volatility_60d` | 6.00 |
| Risk | `max_drawdown_20d` | 4.00 |
| Risk | `max_drawdown_60d` | 4.00 |
| Liquidity | `avg_amount_20d` | 5.25 |
| Liquidity | `avg_amount_60d` | 5.25 |
| Liquidity | `avg_volume_20d` | 2.25 |
| Liquidity | `avg_volume_60d` | 2.25 |

Momentum and relative strength use same-date cross-sectional percentile ranks.
Volatility and absolute drawdown use reversed ranks so lower risk receives
more current-baseline points. Amount and volume are winsorized at the 5th and
95th percentiles before ranking. The three moving-average conditions are
binary. Missing normalized values contribute zero.

The group maxima are momentum 25, trend 20, relative strength 20, risk 20,
and liquidity 15. U1 and U2 did not confirm stable ranking power for this
sum, so Phase 4.1 freezes it as a comparator and makes no weight change.

### Labels, risk, and ordering

The score-label thresholds are 88, 80, 65, and 50 for the current
high-confidence, candidate, focus, and watch bands. High-confidence also
requires confidence at least 0.75, risk score at least 10, and no risk/data
flags. Candidate requires risk score at least 8. Severe risk and insufficient
data have higher label precedence.

Risk flags include very low risk score, 60-day volatility at least 5%, absolute
60-day drawdown at least 25%, and absolute full-history drawdown at least 40%.
They affect confidence and labels but do not subtract from `total_score`.

The production candidate order is:

```text
total_score desc
confidence desc
risk_score desc
symbol asc
```

The symbol is the deterministic final tie-break. The research pipeline default
is Top-20, the daily workflow default is Top-10, and the static multi-list
generator default is 30 rows per list. Top-N uses `head(top_n)` and does not
guarantee a filled list.

### Existing list rules

| List | Actual eligibility and ordering |
|---|---|
| `high_confidence_candidates` | Exclude insufficient/high-risk-active and high, mid-high, or unknown risk; require high or mid-high confidence; order by total score, confidence, risk score |
| `trend_leaders` | Trend-leader primary/secondary tag, excluding high risk; order by trend, momentum, relative strength |
| `long_term_stable` | Stable primary/secondary tag, excluding high-risk-active; order by risk, liquidity, trend |
| `breakout_watch` | Breakout tag; retain risk note; order by momentum, trend, relative strength |
| `accumulation_watch` | Accumulation/fallback non-high-risk logic; current code excludes the top 10% total-score rank from this observation list; order by trend, momentum, relative strength, risk |
| `rebound_watch` | Rebound tag; retain risk note; order by momentum, risk, total score |
| `high_risk_active` | High-risk primary/secondary tag or high/mid-high risk; observation only; order by total score, momentum, liquidity |
| `insufficient_data` | Data-insufficient primary type; order by existing rank |

The `high_risk_active` list is not a confirmed automatic exclusion rule.
The research-language layer maps candidates to research actions such as focus,
tracking, cautious observation, risk observation, or data completion. It does
not authorize buy/sell or guaranteed-return language.

## Point-In-Time Feature Matrix Contract

The future feature schema is:

```text
production_candidate_feature_matrix.v1
row identity = symbol + as_of_date
```

Every row must include:

```text
dataset_version
symbol
as_of_date
latest_input_date
universe_id
source_snapshot_id
feature_schema_version
production_baseline_version
provider_access
labels_joined
leakage_guard_applied
```

Every feature definition records its ID, family, description, source fields,
lookback, point-in-time rule, missing policy, hypothesized direction, type,
production status, availability, leakage risk, and implementation status.

The registry contains 79 entries across:

- existing production factors and outputs;
- trend and trend quality;
- volume and price confirmation;
- position, drawdown, and recovery;
- mean-reversion candidates;
- volatility and tail-risk proxies;
- liquidity and tradability;
- continuousized H1-H5 concepts;
- cross-sectional and market context.

Mean reversion is one feature family, not the roadmap or a production
strategy. The H1-H5 continuous scores are new research features and inherit no
evidence from the frozen boolean cohorts.

True turnover, historical industry-relative features, point-in-time
fundamentals, events/policy, and reliable historical ST/suspension/delisting
state are marked as external-data requirements. They are not approximated from
later snapshots.

Allowed feature statuses are:

```text
existing_production
candidate_research_only
risk_feature_research_only
unavailable
rejected_due_to_leakage
requires_external_data
```

## Future Label Matrix Contract

The label schema is separately versioned:

```text
production_candidate_label_matrix.v1
row identity = symbol + as_of_date + horizon_days
```

It defines continuous 5D, 10D, and 20D return, benchmark return, excess return,
maximum upside, and maximum drawdown labels. It also reserves winner, loser,
right-tail, severe-drawdown, valid-label, and missing-reason fields.

Required provenance includes:

```text
label_schema_version
symbol
as_of_date
horizon_days
future_window_start
future_window_end
benchmark
valid_label
missing_label_reason
provider_access
generated_from_cache
label_definition_digest
```

Phase 3.12 math may be referenced for the 20D adjusted-close, CSI300
common-calendar, complete-horizon, return, excess, maximum-upside,
maximum-drawdown, and preserved-missingness conventions. Its identity
`h1h5-historical-sealed-v1` is not renamed or overwritten. Phase 4 uses a
new schema identity, canonical aliases only, and a new definition digest.

Features and labels remain separate tables. A name such as
`max_drawdown_20d` may legitimately represent a past-window feature in the
feature table and a future-window outcome in the label table; provenance,
table identity, and time direction distinguish them. Label entries are always
`feature_eligible=false`. Phase 4.1 generates no labels.

## Local Data Inventory

Observed local state during the audit:

- 5,416 adjusted stock/index CSV files under the BaoStock daily cache;
- aggregate stock-cache date range from 2022-09-05 through 2026-06-24, with
  per-symbol coverage varying;
- `index_daily/raw/CSI300.csv` ends at 2024-10-31;
- adjusted aliases `sh.000300.csv` and `sz.399300.csv` extend to
  2026-06-24; future builders must freeze deterministic alias selection;
- factor snapshots exist for answer-key, U1, U2, and historical H1-H5 dates;
- member-level snapshots exist for 2024-10-31 and the three historical H1-H5
  dates;
- historical labels and validation outputs exist but are already consumed
  under earlier identities.

Unavailable or unsafe capability includes reliable historical industry
membership, fundamentals, policy/event data, complete historical state
metadata, and true turnover without dated shares outstanding. The project is
daily-bar and post-market; it has no real-time tick contract.

## Chronological Data Roles

Consumed diagnostic/development-only dates:

```text
Answer-key:
2024-01-31, 2024-04-30, 2024-07-31, 2024-10-31

U1:
2024-02-29, 2024-05-31, 2024-08-30, 2024-11-29

U2:
2025-02-28, 2025-05-30, 2025-08-29, 2025-11-28

Historical H1-H5:
2026-01-30, 2026-03-31, 2026-04-30
```

They may be explicitly reclassified for development or diagnostics, but never
again described as fresh unseen final proof.

U3 remains reserved for `u3-prospective-2026-h2-v1`:

```text
2026-09-30
2026-12-31
```

U3 is not reassignable to Phase 4. It remains dormant until its own snapshots
and outcomes exist. Phase 4.1 does not select a Phase 4 prospective holdout.
Finalists must be frozen before a new holdout is preregistered.

## Walk-Forward Contract

The contract uses chronological splits only:

- expanding training window;
- minimum 252 trading days of training history;
- 20-trading-day test blocks;
- monthly rebalance on the first CSI300 trading day;
- 5D, 10D, and 20D labels;
- training labels must end before the test as-of date;
- purge overlap up to the maximum 20-day label horizon;
- 20-trading-day embargo between adjacent evaluation folds;
- complete challenger-specific feature lookback;
- technical minimum of 100 valid symbols per as-of date;
- exact feature coverage ratio remains a preregistration placeholder;
- no random train/test split;
- no silent forward filling through suspended or missing bars;
- no use of current ST/listing state as historical truth.

Exact fold dates are not invented in Phase 4.1. Phase 4.3 must select them from
verified local point-in-time coverage. Its role is comparative chronological
out-of-sample research, not final prospective proof.

## Baseline And Challenger Hierarchy

- Level 0: frozen current `total_score`, candidate rules, and research lists.
- Level 1: each continuous factor evaluated alone.
- Level 2: transparent rule challengers, including trend/volume,
  position/recovery, mean-reversion/liquidity, trend-minus-crowding, and
  production-score-plus-independent-risk-filter families.
- Level 3: training-only regularized linear or logistic models and transparent
  learned scores.
- Level 4: shallow constrained tree models or rankers only if data and
  dependencies support them.

Phase 4.1 implements none of these challengers. Future models cannot use future
returns, outcome labels, result statuses, post-window performance, answer-key
conclusions, cohort effectiveness, or later production decisions as features.

## Evaluation Framework

Factor-level evaluation covers coverage, missingness, dispersion, quantile
returns/excess, top-minus-bottom spread, rank IC and stability, monotonicity,
turnover, drift, and regime sensitivity.

Candidate-level evaluation covers count and coverage, winner capture, loser
contamination, right-tail retention, severe drawdown, mean/median excess,
Top-N precision, stability, baseline overlap, additions, and removals.

Portfolio-level evaluation covers cumulative and supported annualized return,
CSI300 excess, drawdown, volatility, Sharpe, Calmar, hit rate, payoff,
turnover, estimated costs, post-cost return, reliable industry concentration,
single-name concentration, and window/regime dependence.

Predictive, ranking, portfolio, risk-control, and operational value are
reported separately. No challenger passes on one metric alone.

## Production Eligibility Governance

Allowed statuses:

- `rejected`: materially negative, unsafe/leaky, or worse than baseline
  without offsetting risk value;
- `research_only`: interesting but mixed, under-sampled, unstable, or mainly
  explanatory;
- `shadow_test_eligible`: repeated chronological evidence, adequate
  coverage, acceptable risk, reproducibility, and no leakage; production
  output remains unchanged;
- `production_design_eligible`: clear incremental post-cost value across
  multiple windows without single-window/name domination, acceptable risk,
  reproducibility, monitoring, and rollback; later shadow/prospective evidence
  is still required;
- `invalid_execution`: leakage, identity drift, unsafe flags, or window
  governance violation;
- `insufficient_data`: coverage or history gates fail.

No justified exact Phase 4 pass thresholds currently exist. Machine contracts
therefore contain explicit null preregistration placeholders. Exact gates must
be frozen before comparative results are opened, not invented afterward.

No Phase 4.1 status authorizes score reweighting, candidate/list changes,
production risk exclusions, ML ranking, API/UI changes, or behind-flag
integration.

## Future Comparison Output

Reserved future paths:

```text
outputs/research/production_candidate_comparison_<run_id>.json
outputs/research/production_candidate_comparison_<run_id>.csv
```

The contract includes run, dataset, baseline, feature, label, challenger,
training/test window, horizon, candidate count, factor/candidate/portfolio
metrics, baseline comparison, leakage, sufficiency, status, limitations, and
`production_change=false`.

Phase 4.1 writes no comparison output.

## Audit CLI

Default dry-run:

```powershell
python backend\scripts\audit_production_candidate_foundation.py
```

The CLI validates baseline provenance and referenced paths, registry structure,
duplicate IDs, statuses, future/outcome feature leakage, post-as-of
dependencies, feature/label separation, consumed-window roles, U3 reservation,
and all safety flags.

Default execution writes nothing. Explicit write mode may write only:

```text
outputs/research/production_candidate_foundation_audit.json
```

It never writes validation or production outputs and never imports production
scoring/pipeline modules.

## Phase Decision And Next Phase

Phase 4.1 freezes the current baseline as the comparator and provides
deterministic schemas and fail-closed governance for future challengers. It
makes no effectiveness claim.

The recommended next phase is:

```text
Phase 4.2 Candidate Signal and Challenger Development
```

Phase 4.2 may implement the continuous feature-matrix builder, selected
continuous factors, the mean-reversion family, new continuousized H1-H5
features, transparent rule challengers, an ML-ready but label-separated
dataset, and frozen challenger configs. It must not treat H1-H5 as validated,
train final models before contracts are frozen, consume U3, or change
production behavior.

## Explicit Non-Changes

Phase 4.1 did not access a provider, generate labels or full feature matrices,
evaluate factors, run validation or backtests, train ML, tune parameters,
select a Phase 4 holdout, consume or modify U3, or change production scoring,
ranking, candidate rules, list rules, thresholds, recommendations, API/UI, or
behind-flag behavior. No production or validation output was generated.
