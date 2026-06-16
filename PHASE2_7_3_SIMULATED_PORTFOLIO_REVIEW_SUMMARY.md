# Phase 2.7.3 Simulated Portfolio Review Summary

## Implemented

Phase 2.7.3 adds a research-only simulated portfolio validation layer using fixed historical outputs and Phase 2.7.2 future-return labels.

This is a research-only simulated portfolio validation. It is not investment advice.

## Files

- `backend/src/stock_analysis/portfolio/portfolio_rules.py`
- `backend/src/stock_analysis/portfolio/simulator.py`
- `backend/src/stock_analysis/portfolio/performance.py`
- `backend/src/stock_analysis/portfolio/review.py`
- `backend/src/stock_analysis/portfolio/experiments.py`
- `backend/scripts/run_portfolio_validation.py`
- `backend/tests/test_portfolio_simulator.py`
- `backend/tests/test_portfolio_performance.py`
- `backend/tests/test_portfolio_review.py`
- `backend/tests/test_portfolio_cli.py`

## CLI

Dry-run:

```powershell
python backend\scripts\run_portfolio_validation.py --as-of-date 2024-01-31 --horizon-days 60 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 50 --dry-run
```

Write outputs:

```powershell
python backend\scripts\run_portfolio_validation.py --as-of-date 2024-01-31 --horizon-days 60 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 50
```

The CLI does not access BaoStock, does not prewarm cache, and does not run workflow or backtest.

## Portfolio Rules

Supported portfolio IDs:

- `high_confidence_top10`
- `high_confidence_top20`
- `trend_leaders_top10`
- `accumulation_watch_top10`
- `long_term_stable_top10`
- `breakout_watch_top10`
- `mixed_baseline`
- `high_risk_active_observation`

`mixed_baseline` uses trend leaders 40%, accumulation watch 30%, and long-term stable 30%.

`high_risk_active_observation` is risk observation only.

## Review Output

The review layer creates:

- Success cases.
- Failure cases.
- Risk warning cases for positive-return holdings with large drawdown.
- Price-only reason candidates.
- List rule improvement hypotheses.
- Factor feature improvement hypotheses.
- Portfolio construction improvement hypotheses.

The review does not invent financial, industry, valuation, news, or announcement reasons.

## Outputs

Non-dry-run writes:

- `outputs/portfolios/portfolio_summary_YYYY-MM-DD_{horizon}d.json`
- `outputs/portfolios/portfolio_holdings_YYYY-MM-DD_{horizon}d.csv`
- `outputs/portfolios/portfolio_report_YYYY-MM-DD_{horizon}d.md`
- `outputs/portfolios/portfolio_cache_plan_YYYY-MM-DD_{horizon}d_limit{N}.txt`
- `outputs/reviews/portfolio_review_YYYY-MM-DD_{horizon}d.json`
- `outputs/reviews/portfolio_review_YYYY-MM-DD_{horizon}d.md`
- `outputs/experiments/strategy_experiments_YYYY-MM-DD_{horizon}d.json`

## Smoke Quality Notes

Portfolio validation now builds holdings first, then loads or computes future labels for the exact holding symbols. `--limit 50` limits the required holding symbols for the smoke run; it does not take the first 50 unrelated rows from the walk-forward predictions CSV.

Benchmark excess-return fields are preserved when present in `walk_forward_predictions`, and missing excess-return fields are recomputed from local cache only. Benchmark loading checks the aliases `CSI300`, `sh.000300`, and `000300.SH`. If the benchmark future window is unavailable, the summary and cache plan report `benchmark_data_quality`, for example `benchmark_insufficient_future_window`; excess-return metrics should not be interpreted until benchmark future-window cache is prepared.

The cache plan distinguishes missing labels from non-ok labels:

- `missing_future_label_symbols`: no label row exists for the holding.
- `non_ok_future_label_symbols`: a label row exists but its `data_quality` is not `ok`, such as `insufficient_future_window`.

JSON, CSV, and Markdown outputs are written as UTF-8. On Windows PowerShell, inspect Chinese output with:

```powershell
Get-Content -Encoding UTF8 outputs\portfolios\portfolio_summary_2024-01-31_60d.json
```

or with Python:

```powershell
python -c "import json; d=json.load(open('outputs/portfolios/portfolio_summary_2024-01-31_60d.json', encoding='utf-8')); c=next(p for p in d['portfolios'] if p['best_cases'])['best_cases'][0]; print(c.get('name')); print(c.get('primary_type')); print(c.get('secondary_tags'))"
```

## Tests

Added tests cover:

- Equal-weight portfolio construction.
- Top 10 / Top 20 counts.
- Mixed baseline allocation.
- High-risk observation-only handling.
- Transaction-cost-adjusted net return.
- Empty portfolio behavior.
- Missing future labels.
- Holding-aligned future labels.
- Benchmark alias loading and excess-return propagation.
- Benchmark future-window gap reporting.
- Success and failure review generation.
- Risk warning review generation.
- UTF-8 Chinese output regression.
- Dry-run non-writing behavior.
- Non-dry-run output writing.

## Boundaries

- No future leakage: portfolios are built from fixed as-of list outputs.
- Future returns are used only for after-the-fact validation.
- Current validation remains price-only / technical-only.
- Current limit 50 smoke does not prove model effectiveness.
- Larger-sample and multi-date validation should be run manually by the user.

## Recommended Next Manual Command

```powershell
python backend\scripts\run_portfolio_validation.py --as-of-date 2024-01-31 --horizon-days 60 --benchmark CSI300 --outputs-dir outputs --cache-dir data\cache\daily-use --limit 50 --dry-run
```

After reviewing dry-run output, run without `--dry-run` to refresh portfolio/review/experiment outputs.
