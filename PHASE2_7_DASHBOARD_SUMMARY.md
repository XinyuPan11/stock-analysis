# Phase 2.7 Dashboard Research Views Summary

## Status

Implemented read-only Dashboard pages for Phase 2.7 research labels and multi-list
outputs. This slice only reads existing `outputs/` files through the local loader/API
layer. It does not rerun workflow, fetch market data, access BaoStock, change scoring
logic, change multi-label rules, or add a frontend framework.

## Pages Added

- `/lists`
- `/lists/{list_id}`
- `/labels`
- `/search?q=`
- enhanced `/stocks/{symbol}` to use the Phase 2.7 research detail payload

## Navigation And Search

The global Dashboard navigation now includes:

- `Lists`
- `Labels`
- `Search`

The search page accepts full symbols, numeric stock codes, and Chinese name substrings.
Results link to `/stocks/{symbol}`.

## Source APIs Used

The pages are backed by existing read-only loader/API behavior:

- `GET /api/lists`
- `GET /api/lists/{list_id}`
- `GET /api/labels`
- `GET /api/stocks/search?q=`
- `GET /api/stocks/{symbol}/research`

## Page Behavior

`/lists` shows all list cards with description, sort logic, filters, item count,
preview items, and detail links.

`/lists/{list_id}` shows every item in a list with rank, symbol, name, score, primary
type, secondary tags, research action, confidence, risk level, label reason, signals,
and a stock detail link.

`/labels` shows all labeled candidates with optional filters for `primary_type`,
`research_action`, `risk_level`, and `limit`.

`/search` shows a search form and candidate search results.

`/stocks/{symbol}` now shows a research detail view with basic information, score
breakdown, label explanation, evidence, risk fields, factor summary, related lists, and
report links.

## Empty And Missing Behavior

- Empty lists return a normal page with an empty-list message.
- Unknown list IDs return a friendly `404`.
- Empty search input returns a normal search page asking for a query.
- Unknown stock symbols return a friendly `404`.
- Missing report links show a clear fallback message.

## Disclaimer

New pages use a research-only disclaimer:

```text
本系统仅用于个人研究和学习，不构成投资建议，不提供确定性交易指令或收益承诺。
```

## Tests Run

```powershell
python -m unittest backend\tests\test_api.py
python -m unittest discover -s backend\tests
```

## Known Limitations

- No pinyin search.
- No client-side dynamic filtering.
- No new Dashboard page writes outputs or triggers workflow.
- Industry, fundamentals, valuation, news, and announcements remain unavailable.

## Next Step

Phase 2.7 can now move toward final polish, PR preparation, or a small UI pass for list
and stock-detail readability. Any future data enrichment should stay in a separate phase.
