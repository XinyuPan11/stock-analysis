# Phase 2.7 Label/List API Summary

## Status

Implemented read-only API routes for Phase 2.7 label/list outputs, stock search, and
stock research detail. This slice does not add Dashboard pages and does not rerun
workflow, fetch market data, access BaoStock, or change scoring and label-generation
logic.

## API Routes Added

- `GET /api/lists`
- `GET /api/lists/{list_id}`
- `GET /api/labels`
- `GET /api/stocks/search?q=`
- `GET /api/stocks/{symbol}/research`

## Source Files Read

The routes read local `outputs/` files only:

- `outputs/lists/multi_lists_YYYY-MM-DD.json`
- `outputs/lists/{list_id}_YYYY-MM-DD.json`
- `outputs/labels/candidate_labels_YYYY-MM-DD.json`
- `outputs/daily/candidates_YYYY-MM-DD.json`
- `outputs/daily/factors_YYYY-MM-DD.json`
- `outputs/daily/factor_explanations_YYYY-MM-DD.json`
- `outputs/errors/failed_symbols_YYYY-MM-DD.csv`
- `outputs/reports/stocks/{symbol}_YYYY-MM-DD.md/html`

## Example Responses

`/api/lists` returns list metadata, `item_count`, and `items_preview`.

`/api/lists/{list_id}` returns the full list payload with `items`. Empty lists return
`200` with `items: []`.

`/api/labels` returns labeled candidate rows plus `label_counts`,
`primary_type_counts`, `risk_level_counts`, and `research_action_counts`. Optional
filters are `primary_type`, `research_action`, `risk_level`, and `limit`.

`/api/stocks/search?q=` returns matching labeled candidates with report link metadata.

`/api/stocks/{symbol}/research` combines label output, candidate score fields, factor
summary, evidence, risk fields, report links, related list memberships, and data quality.

## Empty And Missing Behavior

- Empty lists return `200` and an empty `items` array.
- Unknown `list_id` returns `404` with `available_list_ids`.
- Empty search query returns `400` without crashing.
- Unknown stock research symbol returns `404` with a clear message and failed-symbol
  detail when available.
- Missing label/list files return graceful empty payloads and messages.

## Symbol Normalization

Search and detail lookup support:

- full symbols such as `sh.600000` and `sz.000001`
- numeric codes such as `600000` and `000001`
- Chinese name substring matching

Numeric `6xxxxx` codes normalize toward Shanghai, `0xxxxx` and `3xxxxx` toward Shenzhen,
and direct prefix matches are preserved.

## Disclaimer

New API responses include a research-only disclaimer that avoids deterministic trading
wording:

```text
本系统仅用于个人研究和学习，不构成投资建议，不提供确定性交易指令或收益承诺。
```

## Tests Run

```powershell
python -m unittest backend\tests\test_api.py
python -m unittest discover -s backend\tests
```

## Known Limitations

- No API route generates labels or lists on demand; callers must run
  `generate_research_views.py` first.
- No Dashboard pages are added in this slice.
- No pinyin matching is implemented.
- Industry, fundamentals, valuation, news, and announcement fields remain unavailable.

## Next Step

The next Phase 2.7 slice can add Dashboard pages for list browsing, label filtering, stock
search, and stock research detail, still read-only over `outputs/`.
