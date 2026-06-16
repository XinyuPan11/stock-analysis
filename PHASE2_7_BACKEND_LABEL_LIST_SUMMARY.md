# Phase 2.7 Backend Label/List Summary

## Status

Implemented the backend-only multi-label and multi-list static output step. This round
does not add API routes, Dashboard pages, workflow reruns, provider fallback, new data
sources, fundamentals, valuation, news, announcements, or real-time data.

## Candidate Source

The generator reads the fixed historical Phase 2.6 outputs for `2024-01-31`:

- `outputs/daily/candidates_2024-01-31.json`
- `outputs/daily/factors_2024-01-31.json`
- `outputs/errors/failed_symbols_2024-01-31.csv`
- stock report links derived from `outputs/reports/stocks/{symbol}_2024-01-31.md/html`

## Available Fields

The backend label engine uses existing candidate score fields, evidence text, risk flags,
warnings, factor rows, and failed-symbol records. It does not invent missing fields.

Available candidate fields include `rank`, `symbol`, `name`, `total_score`, `label`,
`confidence`, `momentum_score`, `trend_score`, `relative_strength_score`, `risk_score`,
`liquidity_score`, `positive_evidence`, `negative_evidence`, `risk_flags`, and `warnings`.

## Missing Fields

Current outputs still do not include industry, sector, theme, fundamentals, valuation,
news, announcements, pinyin, or real-time market data. The label engine therefore uses
`行业字段待补充` as a placeholder tag and does not make industry-hot judgments.

## Labels

Implemented labels:

- `长期稳定型`
- `趋势龙头型`
- `行业热股型` is reserved but not assigned without industry data
- `潜力蓄势型`
- `突破爆发型`
- `超跌反弹型`
- `高风险活跃型`
- `数据不足`

Each stock can have one `primary_type` and multiple `secondary_tags`.

## Lists

Generated list IDs:

- `high_confidence_candidates`
- `trend_leaders`
- `long_term_stable`
- `breakout_watch`
- `accumulation_watch`
- `rebound_watch`
- `high_risk_active`
- `insufficient_data`

## Output Paths

The static generator writes:

- `outputs/labels/candidate_labels_2024-01-31.csv`
- `outputs/labels/candidate_labels_2024-01-31.json`
- `outputs/lists/multi_lists_2024-01-31.json`
- `outputs/lists/{list_id}_2024-01-31.json`

## Command

```powershell
python backend\scripts\generate_research_views.py --date 2024-01-31 --outputs-dir outputs
```

## Tests

Executed test commands:

```powershell
python -m unittest backend\tests\test_multi_label.py backend\tests\test_multi_list.py
python -m unittest discover -s backend\tests
```

Results:

- `test_multi_label.py` + `test_multi_list.py`: `10 tests OK`
- Full backend suite: `166 tests OK`

## Generated Output Snapshot

The fixed historical generation command produced `150` labeled candidate rows.

Primary type counts:

- `趋势龙头型`: `36`
- `长期稳定型`: `27`
- `突破爆发型`: `7`
- `潜力蓄势型`: `43`
- `高风险活跃型`: `37`

List item counts:

- `high_confidence_candidates`: `30`
- `trend_leaders`: `30`
- `long_term_stable`: `27`
- `breakout_watch`: `30`
- `accumulation_watch`: `30`
- `rebound_watch`: `0`
- `high_risk_active`: `30`
- `insufficient_data`: `0`

The empty `rebound_watch` and `insufficient_data` lists reflect the current top-150
candidate set and available fixed historical fields. They are still emitted with stable
JSON structure for downstream API and Dashboard integration.

## Next Step

The next Phase 2.7 step can wire these static outputs into API routes and Dashboard pages,
including a stock detail/search surface. That should remain read-only over `outputs/`.
