# Phase 2.7 Multi-Label And Stock Detail Plan

## Status

Design only. This document defines the Phase 2.7 implementation plan. It does not
implement multi-label classification, list generation, API routes, or Dashboard pages.

Phase 2.7 must use existing fixed historical outputs. It must not rerun the full
workflow, fetch recent data, continue BaoStock debugging, change scoring logic, or add
fundamental, valuation, news, announcement, or real-time data.

## Existing Outputs And Schema Inspection

Inspected fixed historical outputs under `outputs/` for `2024-01-31`.

Primary files:

- `outputs/daily/candidates_2024-01-31.csv`
- `outputs/daily/candidates_2024-01-31.json`
- `outputs/daily/factors_2024-01-31.csv`
- `outputs/daily/factors_2024-01-31.json`
- `outputs/daily/factor_explanations_2024-01-31.csv`
- `outputs/daily/factor_explanations_2024-01-31.json`
- `outputs/daily/summary_2024-01-31.json`
- `outputs/errors/failed_symbols_2024-01-31.csv`
- `outputs/reports/daily_report_2024-01-31.md`
- `outputs/reports/daily_report_2024-01-31.html`
- `outputs/reports/stocks/*_2024-01-31.md`
- `outputs/reports/stocks/*_2024-01-31.html`

Observed counts:

- Candidate rows: `150`
- Factor rows: `4810`
- Factor explanation rows: `81770`
- Summary universe count: `5494`
- Summary attempted count: `5494`
- Summary successful factor count: `4810`
- Summary scored count: `150`
- Summary fetch error count: `190`
- Candidate symbols without factor row: `0`

## Fields Available

Candidate fields:

- `rank`
- `symbol`
- `name`
- `as_of_date`
- `total_score`
- `label`
- `confidence`
- `momentum_score`
- `trend_score`
- `relative_strength_score`
- `risk_score`
- `liquidity_score`
- `positive_evidence`
- `negative_evidence`
- `risk_flags`
- `warnings`
- `source`

Factor fields:

- `symbol`
- `as_of_date`
- `momentum_20d`
- `momentum_60d`
- `momentum_120d`
- `ma5`
- `ma20`
- `ma60`
- `above_ma20`
- `above_ma60`
- `ma_bullish_alignment`
- `rs_20d`
- `rs_60d`
- `rs_120d`
- `volatility_20d`
- `volatility_60d`
- `max_drawdown`
- `max_drawdown_20d`
- `max_drawdown_60d`
- `avg_amount_20d`
- `avg_amount_60d`
- `avg_volume_20d`
- `avg_volume_60d`
- `data_points`
- `source`
- `warnings`

Factor explanation fields:

- `symbol`
- `as_of_date`
- `factor_group`
- `raw_value`
- `normalized_score`
- `weight`
- `contribution`
- `explanation`

Failed symbol fields:

- `symbol`
- `name`
- `stage`
- `index`
- `total`
- `error_type`
- `error_message`
- `elapsed_seconds`
- `provider`
- `start_date`
- `end_date`
- `attempt_count`
- `last_attempt_at`
- `can_retry`

## Fields Missing

These fields are not available in the current fixed historical outputs and must not be
invented:

- `industry`
- `sector`
- `theme`
- fundamentals such as revenue, profit, ROE, debt, cash flow
- valuation metrics such as PE, PB, PS, dividend yield
- news, announcement, event, sentiment, or policy fields
- intraday or tick data
- direct `report_path` in candidate rows
- pinyin search keys
- explicit latest close price in candidate rows

Workarounds:

- Report links can be derived from `outputs/reports/stocks/{symbol}_YYYY-MM-DD.md/html`.
- Risk and stability can use `risk_score`, `volatility_20d`, `volatility_60d`,
  `max_drawdown`, `max_drawdown_20d`, `max_drawdown_60d`, `risk_flags`, and `warnings`.
- Liquidity can use `liquidity_score`, `avg_amount_20d`, `avg_amount_60d`,
  `avg_volume_20d`, and `avg_volume_60d`.
- Industry hot stock logic is deferred to Phase 3. Phase 2.7 may only emit a secondary
  tag such as `行业字段待补充` when no industry field exists.

## Label System

Phase 2.7 should add `backend/src/stock_analysis/research/multi_label.py`.

Inputs:

- candidate rows
- matching factor rows by `symbol`
- matching factor explanation rows by `symbol`
- failed symbol rows for insufficient-data classification
- available stock report index

Output fields:

- `symbol`
- `name`
- `as_of_date`
- `rank`
- `total_score`
- `primary_type`
- `secondary_tags`
- `research_label`
- `research_action`
- `confidence_level`
- `risk_level`
- `confirmation_signals`
- `invalidation_signals`
- `label_reason`
- `data_quality`
- `source_label`
- `report_path_md`
- `report_path_html`

Percentile approach:

- Calculate cross-sectional percentiles within the available candidate set for score
  fields in `candidates`.
- Calculate cross-sectional percentiles within `factors` for raw factor fields when a
  label requires volatility, drawdown, amount, or volume.
- Use approximate bands:
  - `very_high`: top 10%
  - `high`: top 20%
  - `mid`: 40% to 60%
  - `low`: bottom 30%
  - `very_low`: bottom 10%
- Missing fields should lower `confidence_level`, add to `data_quality`, and appear in
  `label_reason`. Missing optional fields must not crash classification.

### Long-Term Stable

Purpose: identify lower-volatility, lower-risk, liquid candidates suitable for long-term
observation.

Logic:

- `risk_score` high or very high
- `liquidity_score` high or very high
- `trend_score` at least mid
- `volatility_20d` and `volatility_60d` not high when factor fields exist
- `max_drawdown` and recent drawdown not severe when factor fields exist
- no severe `risk_flags`

Output:

- `primary_type`: `长期稳定型`
- `research_action`: `长期稳定`
- `confidence_level`: `中` or `中高`
- `risk_level`: `低` or `中低`
- `confirmation_signals`: trend remains intact, liquidity remains stable, drawdown stays
  controlled
- `invalidation_signals`: trend breakdown, volatility expansion, liquidity deterioration

### Trend Leader

Purpose: identify the strongest current price-action candidates.

Logic:

- `trend_score` high or very high
- `momentum_score` high or very high
- `relative_strength_score` high or very high
- `total_score` high
- `risk_score` not very low
- `liquidity_score` not low

Output:

- `primary_type`: `趋势龙头型`
- `research_action`: `重点关注`
- `confidence_level`: `中高` or `高`
- `risk_level`: `中`
- `confirmation_signals`: trend continuation, relative strength maintained, turnover
  support
- `invalidation_signals`: relative strength weakens, trend breaks, failed high-volume
  extension

### Industry Hot Candidate

Purpose: reserve a future industry-relative label without inventing industry data.

Logic:

- If `industry` exists in a future output, rank candidates within each industry by
  `total_score`, `trend_score`, and `relative_strength_score`.
- In current Phase 2.7 outputs, no industry field exists.

Output for current implementation:

- Do not emit strong industry conclusions.
- Add optional `secondary_tags`: `行业字段待补充`.
- `label_reason` must state that industry enhancement is deferred to Phase 3.

### Accumulation Watch

Purpose: identify candidates with acceptable risk and improving but not dominant price
behavior.

Logic:

- `total_score` mid-high or high
- `trend_score` at least mid
- `momentum_score` mid or improving proxy from `momentum_20d` versus `momentum_60d`
- `risk_score` not low
- `liquidity_score` not low
- `relative_strength_score` does not need to be very high

Output:

- `primary_type`: `潜力蓄势型`
- `research_action`: `等待确认`
- `confidence_level`: `中`
- `risk_level`: `中`
- `confirmation_signals`: momentum continues improving, key moving averages hold,
  turnover expands moderately
- `invalidation_signals`: trend weakens again, support breaks, volume-price divergence

### Breakout Watch

Purpose: identify candidates with strong short-term momentum and trend behavior while
keeping risk visible.

Logic:

- `momentum_score` very high
- `trend_score` very high
- `relative_strength_score` high
- `liquidity_score` not low or `avg_amount_20d` high
- `risk_score` not very low
- allow medium or medium-high risk when volatility is elevated

Output:

- `primary_type`: `突破爆发型`
- `research_action`: `高置信候选` or `重点关注`
- `confidence_level`: `中高`
- `risk_level`: `中` or `中高`
- `confirmation_signals`: holds after breakout, turnover continues, relative strength
  does not roll over
- `invalidation_signals`: failed extension, high-volume reversal, falls back below the
  breakout area

### Rebound Watch

Purpose: identify weaker or recently drawdown-heavy candidates with possible recovery
signs. This is an observation label, not a stable recommendation label.

Logic:

- `risk_score` low or drawdown high
- `momentum_score` mid or improving proxy from `momentum_20d`
- `trend_score` may be low or mid
- volatility may be high
- `total_score` does not need to rank near the top

Output:

- `primary_type`: `超跌反弹型`
- `research_action`: `候选关注` or `等待确认`
- `confidence_level`: `低` or `中`
- `risk_level`: `中高`
- `confirmation_signals`: rebound continues, risk metrics improve, turnover recovers
- `invalidation_signals`: rebound fails, new low, volatility expands

### High-Risk Active

Purpose: separate active but high-risk names from stable candidates.

Logic:

- `volatility_20d` or `volatility_60d` high
- `risk_score` low or very low
- many `risk_flags`, or warnings present
- `momentum_score` may be high
- `liquidity_score` may be high
- drawdown or abnormal volatility is visible

Output:

- `primary_type`: `高风险活跃型`
- `research_action`: `风险过高`
- `confidence_level`: `低` or `中`
- `risk_level`: `高`
- `confirmation_signals`: only suitable for risk observation, not stable candidate
  classification
- `invalidation_signals`: volatility expands further, liquidity weakens, trend fails

### Insufficient Data

Purpose: identify symbols that cannot be reliably compared.

Logic:

- missing factor row
- missing required score fields
- `data_points` below minimum threshold
- failed symbol row exists
- factor calculation failed
- coverage or provider errors are present

Output:

- `primary_type`: `数据不足`
- `research_action`: `数据不足`
- `confidence_level`: `低`
- `risk_level`: `未知`
- `label_reason`: explain missing history, factors, or coverage

## Multi-List System

Phase 2.7 should add `backend/src/stock_analysis/research/multi_list.py`.

Common list output shape:

- `list_id`
- `list_name`
- `description`
- `sort_logic`
- `eligible_filters`
- `top_n`
- `items`
- `disclaimer`

Each item should include:

- `symbol`
- `name`
- `rank`
- `total_score`
- `primary_type`
- `secondary_tags`
- `research_action`
- `confidence_level`
- `risk_level`
- `score_breakdown`
- `risk_flags`
- `label_reason`
- `detail_link`
- `report_link`

### High Confidence Candidates

- `list_id`: `high_confidence_candidates`
- Sort logic: `total_score`, `confidence`, `risk_score`, `liquidity_score`
- Eligible filters: exclude `数据不足`, exclude `风险过高`, require no severe risk flags
- Default top N: `30`

### Trend Leaders

- `list_id`: `trend_leaders`
- Sort logic: `trend_score`, `momentum_score`, `relative_strength_score`, `total_score`
- Eligible filters: exclude very low `risk_score`, exclude severe risk flags
- Default top N: `30`

### Long-Term Stable

- `list_id`: `long_term_stable`
- Sort logic: `risk_score`, `liquidity_score`, `trend_score`, low volatility proxy
- Eligible filters: exclude high-risk active labels, exclude severe volatility/drawdown
- Default top N: `30`

### Breakout Watch

- `list_id`: `breakout_watch`
- Sort logic: `momentum_score`, `trend_score`, `relative_strength_score`, liquidity proxy
- Eligible filters: keep risk warnings visible; do not hide medium-high risk names
- Default top N: `30`

### Accumulation Watch

- `list_id`: `accumulation_watch`
- Sort logic: `trend_score`, `risk_score`, `liquidity_score`, `momentum_score`
- Eligible filters: require acceptable risk and liquidity; action is `等待确认`
- Default top N: `30`

### Rebound Watch

- `list_id`: `rebound_watch`
- Sort logic: momentum improvement proxy, liquidity score, recent drawdown context
- Eligible filters: include medium-high risk warning text
- Default top N: `30`

### High-Risk Active

- `list_id`: `high_risk_active`
- Sort logic: `momentum_score`, `liquidity_score`, volatility proxy
- Eligible filters: high volatility, low risk score, or risk flags
- Default top N: `30`
- Purpose: risk observation only

### Insufficient Data

- `list_id`: `insufficient_data`
- Sort logic: missing severity, source index, then symbol
- Eligible filters: failed symbol rows, missing factor rows, missing required fields
- Default top N: `100`

## Output File Design

New generated outputs for `2024-01-31`:

- `outputs/labels/candidate_labels_2024-01-31.csv`
- `outputs/labels/candidate_labels_2024-01-31.json`
- `outputs/lists/multi_lists_2024-01-31.json`
- `outputs/lists/high_confidence_candidates_2024-01-31.json`
- `outputs/lists/trend_leaders_2024-01-31.json`
- `outputs/lists/long_term_stable_2024-01-31.json`
- `outputs/lists/breakout_watch_2024-01-31.json`
- `outputs/lists/accumulation_watch_2024-01-31.json`
- `outputs/lists/rebound_watch_2024-01-31.json`
- `outputs/lists/high_risk_active_2024-01-31.json`
- `outputs/lists/insufficient_data_2024-01-31.json`

Generation should be implemented as a read-only post-processing step over existing
`outputs/daily`, `outputs/errors`, and `outputs/reports`. It must not fetch market data,
rerun factors, rerun scoring, or rerun backtest.

Suggested script:

- `backend/scripts/generate_multi_label_outputs.py`

Suggested command:

```powershell
python backend\scripts\generate_multi_label_outputs.py --outputs-dir outputs --as-of-date 2024-01-31
```

## API Design

Extend the current FastAPI read-only Dashboard API.

New endpoints:

- `GET /api/lists`
- `GET /api/lists/{list_id}`
- `GET /api/labels`
- `GET /api/stocks/search?q=`
- `GET /api/stocks/{symbol}/research`

### GET /api/lists

Returns the multi-list index:

- `latest_date`
- `lists`
- `warnings`
- `disclaimer`

### GET /api/lists/{list_id}

Returns one list:

- `list_id`
- `list_name`
- `description`
- `sort_logic`
- `eligible_filters`
- `top_n`
- `items`
- `warnings`
- `disclaimer`

### GET /api/labels

Returns all generated candidate labels:

- `latest_date`
- `count`
- `items`
- `warnings`

### GET /api/stocks/search?q=

Supported matching:

- exact full symbol: `sh.600000`
- numeric symbol suffix: `600000`
- partial numeric code
- fuzzy Chinese name substring

No pinyin search in Phase 2.7.

Return fields:

- `symbol`
- `name`
- `rank`
- `total_score`
- `primary_type`
- `research_action`
- `risk_level`
- `report_path`

### GET /api/stocks/{symbol}/research

Returns:

- `basic_info`
- `current_rank`
- `total_score`
- `score_breakdown`
- `primary_type`
- `secondary_tags`
- `research_action`
- `confidence_level`
- `risk_level`
- `confirmation_signals`
- `invalidation_signals`
- `factor_explanation`
- `risk_flags`
- `report_links`
- `related_lists`
- `data_quality`
- `disclaimer`

## Dashboard Page Design

Add pages only after backend label/list outputs are implemented and tested.

Planned pages:

- `/lists`
- `/lists/{list_id}`
- enhanced `/stocks/{symbol}`

Planned UI additions:

- Home page entry: `多榜单研究视图`
- Home page stock search form
- List summary table with list names, descriptions, counts, and risk notes
- List detail page with ranking table and visible risk column
- Stock research page showing labels, score breakdown, related lists, factor explanation,
  report links, and data quality notes

All pages must include a personal-research disclaimer and must not present deterministic
trading instructions or return guarantees.

## Test Plan

Unit tests:

- one stock can have multiple secondary tags
- high-risk names do not enter `long_term_stable`
- insufficient data enters `insufficient_data`
- `trend_leaders` ranking is sorted by trend, momentum, and relative strength
- `breakout_watch` keeps risk notes visible
- missing optional fields do not crash label generation
- failed symbols produce data-quality labels

API tests:

- `/api/lists` returns list index
- `/api/lists/{list_id}` returns one list
- `/api/labels` returns labels
- `/api/stocks/search?q=600000` returns matching stock
- `/api/stocks/search?q=中文名称片段` returns matching stock when present
- `/api/stocks/{symbol}/research` returns labels, scores, risk, factor explanation, and
  report links
- missing label/list output files do not crash API
- API/page responses do not contain deterministic investment advice phrasing

Command:

```powershell
python -m unittest discover -s backend\tests
```

## Implementation Order

1. Add `backend/src/stock_analysis/research/multi_label.py`.
2. Add `backend/src/stock_analysis/research/multi_list.py`.
3. Add focused unit tests for label and list generation.
4. Add `backend/scripts/generate_multi_label_outputs.py`.
5. Generate Phase 2.7 outputs from existing fixed historical files.
6. Extend `output_loader.py` to read `outputs/labels` and `outputs/lists`.
7. Add API schemas and routes.
8. Add minimal Dashboard pages and navigation entries.
9. Update README and Phase 2.7 docs.

## Non-Goals

Phase 2.7 will not:

- run recent data
- rerun full workflow
- continue BaoStock fetch debugging
- optimize to parquet or DuckDB
- add provider fallback
- add automated trading
- provide deterministic trading instructions
- add financial or valuation metrics
- add news or announcements
- enter Phase 3 or Phase 4

## Recommended Next Step

Implement backend-only label and list engines first, generate static outputs from the
existing `2024-01-31` files, and test them before adding API and Dashboard pages.
