# Phase 2.7 Summary

## Goal

Phase 2.7 adds read-only multi-label, multi-list, stock search, and stock research views on top of the existing local Dashboard.

The scope remains local and read-only. The views are based on fixed historical outputs for `2024-01-31` and do not trigger data fetching, workflow reruns, scoring recalculation, prewarm, or backtest execution.

## Completed Features

- Multi-label backend outputs for candidate research classification.
- Multi-list backend outputs for list-oriented browsing.
- `generate_research_views.py` for generating read-only research view artifacts from existing outputs.
- API routes for lists, labels, stock search, and stock research detail.
- Dashboard pages for multi-list browsing, label filtering, stock search, and stock research detail.
- README Phase 2.7 route documentation.
- Merge-readiness smoke checks for API and Dashboard pages.

## Generated Outputs

- `outputs/labels/candidate_labels_YYYY-MM-DD.json`
- `outputs/labels/candidate_labels_YYYY-MM-DD.csv`
- `outputs/lists/multi_lists_YYYY-MM-DD.json`
- `outputs/lists/high_confidence_candidates_YYYY-MM-DD.json`
- `outputs/lists/trend_leaders_YYYY-MM-DD.json`
- `outputs/lists/long_term_stable_YYYY-MM-DD.json`
- `outputs/lists/breakout_watch_YYYY-MM-DD.json`
- `outputs/lists/accumulation_watch_YYYY-MM-DD.json`
- `outputs/lists/high_risk_active_YYYY-MM-DD.json`
- `outputs/lists/rebound_watch_YYYY-MM-DD.json`
- `outputs/lists/insufficient_data_YYYY-MM-DD.json`

## API Routes

- `GET /api/lists`
- `GET /api/lists/{list_id}`
- `GET /api/labels`
- `GET /api/stocks/search?q=`
- `GET /api/stocks/{symbol}/research`

## Dashboard Pages

- `GET /lists`
- `GET /lists/{list_id}`
- `GET /labels`
- `GET /search`
- `GET /stocks/{symbol}`

## Tests

Phase 2.7 merge-readiness checks used:

```powershell
python -m unittest backend\tests\test_api.py
python -m unittest discover -s backend\tests
```

Latest pre-merge result:

- `backend\tests\test_api.py`: 59 tests OK
- Full backend test discovery: 183 tests OK

## Known Limitations

- Current research views are based on fixed historical outputs: `2024-01-31`.
- The Dashboard does not trigger data fetching or workflow reruns.
- No industry, sector, fundamentals, valuation, news, or announcement layer is included.
- No pinyin search is implemented.
- `rebound_watch` and `insufficient_data` may be empty depending on the current fixed historical outputs.
- The pages remain simple server-rendered HTML and do not introduce a frontend framework.

## Deferred Items

- Controlled latest-date refresh workflow.
- Better stock search normalization and pinyin support.
- Optional industry or sector grouping after stable latest-date refresh is available.
- More polished visual comparison for list membership and label distribution.

## Next Recommended Phase

Phase 2.8 should prepare controlled latest-date update / refresh workflow, with token-saving workflow:

- Codex writes code and tests.
- The user manually runs long prewarm / workflow / backtest commands.
- The user pastes results back for Codex to analyze and document.

