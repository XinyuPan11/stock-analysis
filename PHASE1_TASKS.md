# Phase 1 Tasks: Daily A-Share Research Pipeline

## 1. Phase 1 Goal

Build a local after-close A-share research pipeline that can fetch daily data, filter the stock universe, calculate factors, rank candidates, explain results, run walk-forward backtests, and generate markdown/html research reports.

Phase 1 intentionally does not build the web dashboard, news/event system, watchlist, holdings monitor, or real-time service.

## 2. Target File Structure

```text
backend/src/stock_analysis/
  data/
    providers/
      base.py
      akshare_provider.py
      baostock_provider.py
      tushare_provider.py
    cache.py
    constants.py
    schemas.py
    service.py
    universe.py

  research/
    ashare_filters.py
    factors.py
    scoring.py
    factor_explanation.py
    signal_conflict_detector.py
    recommendation_engine.py
    peer_comparison.py

  reports/
    report_generator.py
    templates/

  backtesting/
    walk_forward.py
    metrics.py
    backtest_report.py

  cli/
    run_daily_research.py
    run_single_stock_report.py
    run_backtest.py

backend/tests/
  test_ashare_filters.py
  test_factors.py
  test_scoring.py
  test_factor_explanation.py
  test_signal_conflict_detector.py
  test_report_generator.py
  test_backtest_report.py
```

## 3. Implementation Order

### Step 1: Data Universe And Daily Bars

- Add A-share stock universe fetch.
- Normalize stock identity fields.
- Fetch daily bars for A-share stocks and benchmark indices.
- Keep provider output behind the unified schema.
- Add local cache and incremental update strategy.
- Add smoke test for one small stock set plus CSI 300.

### Step 2: A-Share Filters

Implement `ashare_filters.py`:

- Filter ST and *ST stocks.
- Filter delisting-board or delisting-risk stocks.
- Filter stocks listed fewer than 180 days.
- Filter long-suspended stocks.
- Filter low-liquidity stocks based on recent 20-day trading amount.
- Handle limit-up/limit-down, adjusted prices, missing data, and trading calendar issues.

Tests:

- Synthetic data tests for each filter.
- Smoke test on a small real-data sample.

### Step 3: Factor Calculation

Implement `factors.py`:

- Momentum factors.
- Trend factors.
- Relative strength versus CSI 300, CSI 500, and ChiNext Index.
- Volatility and drawdown risk.
- Liquidity factors.

Tests:

- Known-input factor tests.
- Missing-data behavior tests.

### Step 4: Composite Scoring

Implement `scoring.py`:

- Weighted composite score.
- Percentile rank.
- Risk penalty.
- Confidence score.
- Non-deterministic recommendation label:
  - `候选关注`
  - `重点观察`
  - `观察`
  - `风险过高`

Tests:

- Ranking test.
- Risk penalty test.
- Label threshold test.

### Step 5: Factor Explanation

Implement `factor_explanation.py`:

- Raw factor value.
- Standardized value.
- Percentile.
- Weight.
- Contribution score.
- Plain-language explanation.

Tests:

- Contribution sum test.
- Explanation table schema test.

### Step 6: Signal Conflict Detection

Implement `signal_conflict_detector.py`:

- Momentum strong but valuation/risk expensive later.
- Industry strong but stock underperforms.
- Trend strong but volatility too high.
- Fundamentals good but trend breaks later.
- Severe conflict reduces confidence and prevents strong candidate wording.

Tests:

- Conflict rule tests.
- Confidence reduction tests.

### Step 7: Recommendation Engine

Implement `recommendation_engine.py`:

- Combine filters, factors, scoring, explanations, and conflicts.
- Output Top 10 and Top 20.
- Include recommendation reason, risk warning, data source, data date, and update time.

Tests:

- End-to-end synthetic pipeline test.
- Top N output schema test.

### Step 8: Report Generator

Implement `report_generator.py`:

- Daily recommendation report.
- Single-stock report.
- Markdown output first.
- HTML output second.

Report sections:

- Recommendation conclusion.
- Core view.
- Key evidence.
- Factor contribution table.
- Risk counter-evidence.
- Signal conflicts.
- Scenario analysis.
- Invalidation conditions.
- Follow-up indicators.
- Data source and update time.

Tests:

- Markdown content test.
- No deterministic buy/sell wording test.

### Step 9: Walk-Forward Backtest

Implement `walk_forward.py`, `metrics.py`, and `backtest_report.py`:

- Top 10 and Top 20 portfolio backtests.
- Walk-forward ranking and holding periods.
- Compare against CSI 300, CSI 500, and ChiNext Index.
- Include transaction costs.
- Forbid future data usage.

Metrics:

- Cumulative return.
- Annualized return.
- Alpha.
- Sharpe.
- Max drawdown.
- Win rate.
- Turnover.
- Post-cost return.

Tests:

- No future data test.
- Metrics known-input test.
- Benchmark comparison test.

## 4. Phase 1 Completion Gate

Phase 1 is not complete unless:

- Every new module has tests or a smoke test.
- Top 10 and Top 20 candidate reports can be generated.
- Backtest report can be generated.
- Every output includes source, data date, update time, and risk warning.
- No output uses deterministic buy/sell advice wording.
