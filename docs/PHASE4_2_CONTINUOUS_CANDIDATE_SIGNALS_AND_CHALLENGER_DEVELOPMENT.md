# Phase 4.2 Continuous Candidate Signals And Challenger Development

## Purpose And Scope

Phase 4.2 implements the first reusable, point-in-time-safe feature matrix and transparent challenger layer for production-candidate research. It generates candidate logic; it does not establish effectiveness.

The implementation is research-only. It does not modify the frozen production score, weights, sorting, eligibility, candidate lists, risk lists, thresholds, recommendation language, API/UI behavior, or behind-flag behavior. It does not generate or join labels, calculate future outcomes, evaluate factors, run walk-forward validation, run a portfolio backtest, train a model, or use U3.

Unlike the Phase 3 H1-H5 sparse boolean cohorts, Phase 4.2 retains continuous information. Five H1-H5-inspired features are reformulated from same-date continuous inputs and never consume H1-H5 membership. They inherit no Phase 3 effectiveness evidence.

## Phase 4.1 Integrity Anchor

The baseline and foundation were loaded and validated without modifying either file.

| Contract | Identity/version | SHA-256 |
| --- | --- | --- |
| Production baseline | `current-production-candidate-baseline` / `production-candidate-baseline-v1` | `3A1F859501758270FAE3FEC5EF4C2407B5D05439219531B22513CF701682ACEE` |
| Research foundation | `production-candidate-research-foundation` / `phase4.1-v1` | `815375A1C09A35746C545904CA63C547211669648BFBC1B1ED924B2C95FD2E0E` |
| Phase 4.2 feature registry | `production-candidate-features` / `phase4.2-v1` | `9F95EC87C40314A848822ECB69EE631C1FFA9994FFBF81CD983AF4BF7B3D2940` |
| Phase 4.2 challenger registry | `production-candidate-challengers` / `phase4.2-v1` | `D8558C3031BC567C3D6CB5F43EC358E22E842B306653C7B578F95D684BE44353` |

The Phase 4.1 audit returned `status=safe`, with `provider_access=false`, `labels_joined=false`, `production_change=false`, and `u3_changed=false`. Referenced production paths still exist. No referenced production module has changed relative to captured commit `5f692914d17169d135d1c6da87de7e6c1e93525d`.

## Tracked Contracts

```text
research/configs/production_candidate_features.v1.json
research/configs/production_candidate_challengers.v1.json
backend/src/stock_analysis/research/production_candidate_feature_matrix.py
backend/src/stock_analysis/research/production_candidate_challengers.py
backend/scripts/build_production_candidate_feature_matrix.py
backend/scripts/build_production_candidate_challengers.py
backend/tests/test_production_candidate_feature_matrix.py
backend/tests/test_production_candidate_challengers.py
docs/PHASE4_2_CONTINUOUS_CANDIDATE_SIGNALS_AND_CHALLENGER_DEVELOPMENT.md
```

## Implemented Feature Set

The output schema has 83 registered feature columns: 17 unchanged production factor references, 10 optional same-date production output/status references, and 56 new continuous or quality/status research columns. The 83-column total is not 83 new signals. The Phase 4.1 conceptual registry is not a one-to-one output-column specification; Phase 4.2 separately emits comparison aliases and optional baseline snapshot fields. The new research implementation is a coherent 56-column subset supported by the local cache.

### Formula notation

For one symbol and one as-of date, `P_t`, `V_t`, and `A_t` are adjusted close, volume, and amount; `r_t=P_t/P_(t-1)-1`; `mean_n(X)` and `std_n(X)` use the last `n` available rows with sample standard deviation; `rank_d(X)` is the deterministic average-tie percentile rank within the one as-of date, with higher values receiving higher percentiles; `inv_rank_d(X)` ranks lower values higher. Missing inputs remain null and are never imputed. The machine-readable registry is authoritative for source fields, minimum observations, missing policy, status, leakage risk, and output order.

### Existing production references (27)

The 17 factor references preserve established formulas:

- momentum: `P_t/P_(t-n)-1` for `n=20,60,120`;
- moving-average booleans: `P_t>MA20`, `P_t>MA60`, and `MA5>MA20>MA60`;
- relative strength: stock return minus CSI300 return for `n=20,60,120`, using data no later than the as-of date;
- volatility: `std_n(r)` for `n=20,60`;
- maximum drawdown: `min(P/cummax(P)-1)` over 20 or 60 rows;
- average amount and volume: `mean_n(A)` and `mean_n(V)` for `n=20,60`.

The 10 optional same-date snapshot references are `total_score`, the five component scores, `confidence`, `risk_flags`, `warnings`, and `eligibility_status`. They are comparison fields only. Their production formulas are not reimplemented or changed. A missing same-date snapshot value stays null.

### Trend quality (11)

- `return_5d`, `return_20d`, `return_60d`: `P_t/P_(t-n)-1`.
- `ma_alignment_score`: mean of `P_t>MA20`, `P_t>MA60`, and `MA5>MA20>MA60`; null if any component is null.
- `distance_to_ma20`, `distance_to_ma60`: `P_t/MA_n-1`.
- `trend_slope_20`, `trend_slope_60`: OLS slope of `log(P)` on the local row index over the last `n` rows.
- `trend_acceleration`: last-20-row return minus the preceding-20-row return.
- `trend_persistence_20`: share of the last 20 daily returns greater than zero.
- `trend_smoothness_20`: absolute net price change divided by the sum of absolute daily price changes over the last 20 return intervals; zero when the denominator is zero.

### Volume and amount confirmation (6)

- `relative_volume_5_20`: `mean_5(V)/mean_20(V)`.
- `relative_amount_5_20`: `mean_5(A)/mean_20(A)`.
- `volume_persistence_20`: share of the latest 20 volume rows exceeding the mean of the preceding 20 rows.
- `amount_expansion`: `mean(last 5 A)/mean(previous 20 A)-1`, requiring 25 rows.
- `price_volume_agreement`: mean of `sign(r_t)*sign(V_t/V_(t-1)-1)` over the last 20 return rows.
- `abnormal_volume_without_price_confirmation`: `max(relative_volume_5_20-1,0)*I(return_5d<=0)`.

Turnover-derived features are not implemented because a verified historical, point-in-time-safe denominator is not available in the current local cache.

### Position, drawdown, and recovery (9)

- `distance_from_high_n`: `P_t/max_n(P)-1`, for `n=20,60`.
- `distance_from_low_n`: `P_t/min_n(P)-1`, for `n=20,60`.
- `drawdown_n`: `P_t/max_n(P)-1`, for `n=20,60`.
- `recovery_strength_5`: `P_t/min_20(P)-1`.
- `recovery_strength_20`: `P_t/min_60(P)-1`.
- `low_position_score`: `1-clip((P_t-min_60(P))/(max_60(P)-min_60(P)),0,1)`; a flat 60-row range uses position `0.5`.

The recovery names express engineering contexts; their exact implemented windows are the formulas above and are frozen in the registry.

### Mean-reversion candidates (10)

These are research candidate features, not a standalone production strategy.

- `deviation_from_ma5/20/60`: `P_t/MA_n-1`.
- `return_zscore_20/60`: `(r_t-mean_n(r))/std_n(r)`; zero when the valid sample standard deviation is zero.
- `volatility_adjusted_deviation_20`: `deviation_from_ma20/realized_volatility_20`.
- `recent_drawdown_score`: `-drawdown_20`.
- `oversold_proxy`: `max(-return_zscore_20,0)`.
- `rebound_confirmation`: `max(return_5d,0)*clip(relative_volume_5_20,0,2)`.
- `mean_reversion_opportunity_score`: mean of same-date percentile ranks of `oversold_proxy`, `recent_drawdown_score`, `rebound_confirmation`, and `average_amount_20`; all four must be present.

### Volatility and tails (7)

- `realized_volatility_20/60`: `std_n(r)`.
- `downside_volatility_20`: sample standard deviation of negative returns among the last 20; zero if lookback is sufficient but fewer than two negative observations exist.
- `large_down_move_frequency_20`: share of last 20 returns below `-2*std_60(r)`.
- `large_up_move_frequency_20`: share of last 20 returns above `2*std_60(r)`.
- `left_tail_risk_score`: mean of `rank_d(downside_volatility_20)` and `rank_d(large_down_move_frequency_20)`.
- `right_tail_activity_score`: mean of `rank_d(large_up_move_frequency_20)` and `rank_d(return_20d)`.

### Liquidity and data quality (8)

- `average_amount_5/20`: `mean_n(A)`.
- `amount_stability`: `clip(1-std_20(A)/abs(mean_20(A)),0,1)`; zero-mean amount yields null.
- `missing_bar_rate`: `1-observed symbol dates/benchmark dates` over the last up-to-60 benchmark dates available by the as-of date.
- `non_positive_price_warning`: true if any used OHLC or adjusted close is non-positive.
- `low_liquidity_warning`: `average_amount_20<20,000,000`; this is an engineering guard, not an outcome-tuned threshold.
- `tradability_status`: price-data-only research status.
- `data_quality_status`: `ok`, insufficient history, or invalid adjusted-price status.

### H1-H5 continuousized concepts (5)

All five are new Phase 4 research features with `inherited_evidence=false`. They do not use Phase 3 cohort membership and do not claim a validated direction.

- `low_position_revaluation_score`: mean of `rank_d(low_position_score)`, `rank_d(recovery_strength_20)`, and `rank_d(relative_amount_5_20)`.
- `trend_acceleration_score`: mean of `rank_d(trend_acceleration)`, `rank_d(trend_persistence_20)`, and `rank_d(trend_smoothness_20)`.
- `crowding_risk_score`: mean of `rank_d(distance_from_high_60)`, `rank_d(relative_volume_5_20)`, and `rank_d(realized_volatility_20)`.
- `right_tail_opportunity_score`: mean of `rank_d(right_tail_activity_score)`, `rank_d(trend_acceleration_score)`, and `rank_d(amount_expansion)`.
- `false_breakout_risk_score`: mean of `rank_d(distance_from_high_60)`, `rank_d(abnormal_volume_without_price_confirmation)`, and `inv_rank_d(trend_acceleration)`.

## Deferred Or Unavailable Features

The v1 registry omits turnover features without a safe historical denominator; historical industry, fundamental, event, suspension, limit-status, and free-float fields without verified point-in-time provenance; provider-dependent fields; future outcomes and labels; validation results; cohort effectiveness; and H1-H5 membership. These may only be added in a later version after provenance is demonstrated. Unsupported fields are not synthesized.

## Point-In-Time Feature Matrix

Each row is `symbol x as_of_date`. The builder:

- reads only local adjusted daily cache files and never constructs a provider;
- uses rows whose trade date is no later than the as-of date;
- requires adjusted close and forbids close fallback;
- selects a deterministic CSI300 alias: `sz.399300`, then `sh.000300`, then raw CSI300 if present;
- preserves every selected symbol, including insufficient-history rows, with `row_status` and `missing_reason`;
- loads optional production factor/candidate snapshots only when they are already-safe same-date local outputs;
- computes percentile transforms within exactly one date and uses stable average-tie ranking plus symbol ordering;
- validates registered columns, identities, config digests, duplicates, latest-input dates, U3 dates, cache coverage, and safety flags fail-closed;
- defaults to dry-run and writes only after `--write-output`.

The builder rejects label/outcome patterns, H1-H5 membership inputs, unsafe flags, duplicate features/rows, unregistered features, invalid baseline identity, adjusted-price violations, mixed-date ranking, dates beyond cache coverage, and protected U3 dates (`2026-09-30`, `2026-12-31`).

## Transparent Challengers

For component `x`, let `R(x)=rank_d(x)` and `N(x)=1-R(x)`. A score is `100*sum(weight*transformed_component)`. Missing components or failed prerequisites preserve the row as ineligible and record reasons. Eligible rows rank by score descending and symbol ascending. All rows are retained; no sparse boolean cohort is produced.

| Challenger | Frozen formula | Prerequisites |
| --- | --- | --- |
| `trend_volume_quality_v1` | `100*(.25R(trend_acceleration_score)+.25R(trend_smoothness_20)+.25R(relative_amount_5_20)+.25R(price_volume_agreement))` | `data_quality_status=ok` |
| `low_position_recovery_v1` | `100*(R(low_position_score)+R(recovery_strength_20)+R(relative_amount_5_20))/3` | `data_quality_status=ok` |
| `mean_reversion_liquidity_v1` | `100*(.50R(mean_reversion_opportunity_score)+.25R(average_amount_20)+.25R(amount_stability))` | quality ok and `low_liquidity_warning=false` |
| `baseline_risk_adjusted_v1` | `100*(.50R(total_score)+.25R(risk_score)+.25N(left_tail_risk_score))` | `data_quality_status=ok` |
| `trend_minus_crowding_v1` | `100*(.40R(trend_acceleration_score)+.30R(trend_smoothness_20)+.30N(crowding_risk_score))` | `data_quality_status=ok` |

Equal weights are used where no engineering priority exists. Unequal formulas assign the primary construct 40%-50% and split the remainder across confirmation/guard terms. These are transparent engineering choices frozen before Phase 4.3; they were not optimized against outcomes and are not claimed optimal.

The challenger builder rejects unknown features, label columns, mixed dates, schema/digest mismatch, unsafe flags, outcome-tuned declarations, non-`not_evaluated` status, production eligibility claims, and attempts to write production candidate paths.

## ML-Ready Dataset Contract

- Dataset version: `production-candidate-feature-matrix-phase4.2-v1`.
- Feature schema: `production_candidate_feature_matrix.v1`.
- Feature columns: exactly the 83 registry columns, in registry order.
- Identity/provenance: dataset/schema/config identities, foundation/baseline IDs, symbol, as-of/latest-input dates, source snapshot, universe, benchmark, data role, safety flags, limit flag, observation count, row status, and missing reason.
- Continuous columns are numeric; moving-average/liquidity/price warnings are boolean; confidence, flags/warnings, eligibility, tradability, quality, and row status are categorical.
- Missing representation is null/CSV empty with explicit row/component status; no sentinel imputation.
- The config SHA-256 is repeated in every feature row and must match the challenger registry.

A later component may join a separately generated label matrix on `symbol+as_of_date` only after schemas and digests are frozen. It must assign chronological folds, mark consumed dates, and protect reserved U3 rows. Random splitting is prohibited because it can mix regimes and leak later information. Phase 4.2 joins no labels and creates no folds or splits.

## Engineering Smoke

Only `2024-10-31` was used, explicitly `consumed_development_smoke_only`. The command used `--limit 300`; the artifact is an engineering subset, not a market-wide research result.

Feature result:

- input/output symbols/rows: 300/300; registered columns: 83; duplicate rows: 0;
- maximum latest input date: `2024-10-31`;
- all eight computable factor/research families: 100% coverage; optional production-output coverage: 17.3%;
- all 56 new columns and all 17 local factor references: zero missing;
- `total_score`, five component scores, and `confidence`: 270 missing each;
- `risk_flags`: 291 missing; `warnings`: 300 missing; `eligibility_status`: 0 missing;
- provider false, labels false, production change false, effectiveness evidence false.

Baseline reference gaps are expected because the same-date candidate snapshot covers a subset. Nulls are preserved instead of recomputing or filling production outputs.

| Challenger | Rows | Eligible | Ineligible |
| --- | ---: | ---: | ---: |
| `baseline_risk_adjusted_v1` | 300 | 30 | 270 |
| `low_position_recovery_v1` | 300 | 300 | 0 |
| `mean_reversion_liquidity_v1` | 300 | 296 | 4 |
| `trend_minus_crowding_v1` | 300 | 300 | 0 |
| `trend_volume_quality_v1` | 300 | 300 | 0 |
| **Total** | **1,500** | **1,226** | **274** |

Duplicate challenger rows were zero and boolean truncation was false. Counts, coverage, distributions, ranks, and Top-N previews are engineering evidence only, not effectiveness evidence. No top symbol was interpreted as attractive.

Generated Git-ignored artifacts:

```text
research/inputs/production_candidate_features_2024-10-31.csv
research/inputs/production_candidate_features_2024-10-31.json
outputs/research/production_candidate_challengers_2024-10-31.csv
outputs/research/production_candidate_challengers_2024-10-31.json
```

## Explicit Non-Actions

No provider, BaoStock, or cache prewarm was used. No label was generated/joined and no future outcome was inspected. No factor effectiveness, walk-forward validation, backtest, model training, or outcome tuning occurred. No U3 artifact/date was read, changed, reassigned, or consumed. No production or validation output was generated.

No production score, weight, sorting, eligibility, candidate/list rule, threshold, recommendation, API/UI behavior, or behind-flag behavior changed.

## Recommended Phase 4.3

Phase 4.3 should separately preregister controlled multi-date feature and label matrices, freeze chronological folds and pass gates, evaluate single features and challenger rankings against the frozen baseline, compare Top-N portfolios with transaction costs, and assign research eligibility statuses. It should still make no direct production change. Phase 4.3 is not implemented here.
