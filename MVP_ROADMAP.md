# MVP Roadmap: Personal A-Share Research Terminal

## 1. Product Positioning

This project is a personal A-share professional research terminal. It is built for one user's daily research workflow, not for public investment advisory service, paid subscription, institutional permissioning, or public buy/sell recommendations.

The MVP should help the user answer:

1. Which A-share stocks deserve attention after today's close?
2. Why did they rank highly?
3. What evidence supports the candidate status?
4. What risks or counter-evidence could invalidate the idea?
5. How did the logic perform historically?
6. What should be tracked over the next 7, 30, 60, and 90 days?

## 2. Core Product Boundary

### Current MVP Boundary

- Personal-use A-share research terminal.
- A-share individual stocks are the main research object.
- CSI 300, CSI 500, ChiNext Index, STAR 50, and industry indices are benchmark context.
- First version updates after market close using daily bars.
- Recommendation language must be non-deterministic:
  - `候选关注`
  - `重点观察`
  - `观察`
  - `风险过高`
- Every output must show data source, data date, update time, risk warning, and uncertainty.
- Every recommendation should become a professional research report, not only a Top N list.

### Explicitly Not In Current MVP

- Public investment advisory service.
- Paid subscriptions.
- Institutional permission systems.
- Complex user/account system.
- Public buy/sell advice.
- Real-time tick data.
- Wind, Choice, iFinD, or other high-cost institutional data vendors.
- News, announcements, policy event intelligence.
- Deep financial statement and valuation analysis.
- Watchlist, holdings, and personal alerts.
- Full web dashboard.

These are not deleted from the long-term vision; they are moved to later phases.

## 3. Long-Term Vision Kept

The long-term product can still include:

- A-share all-market candidate recommendation.
- Individual stock research pages.
- Industry and index benchmark comparison.
- Financial, valuation, risk, and event analysis.
- Personal watchlist and holdings monitoring.
- Backtesting and model validation.
- Data source, update time, recommendation history, and risk warnings.
- Professional markdown/html research reports for every recommendation.
- Later professional data sources and more advanced models.
- Later FastAPI and frontend dashboard.
- Later thesis lifecycle tracking, news, announcements, and policy events.

## 4. Phase Roadmap

### Phase 1: Daily A-Share Research Pipeline

Goal: build a local daily research pipeline that runs after market close and outputs candidate stocks with professional explanations and backtest support.

Scope:

- A-share stock universe.
- Daily bars.
- Local cache and incremental update plan.
- A-share filters.
- Momentum, trend, relative strength, risk, and liquidity factors.
- Composite scoring.
- Top 10 and Top 20 candidate lists.
- Factor explanations.
- Signal conflict detection.
- Daily recommendation report.
- Single-stock markdown/html report.
- Walk-forward backtest against CSI 300, CSI 500, and ChiNext Index.

Phase 1 does not include frontend, FastAPI, news, announcements, watchlist, holdings, or real-time updates.

### Phase 2: FastAPI + Simple Dashboard

Goal: expose Phase 1 results through a simple personal dashboard.

Scope:

- FastAPI service.
- Simple Chinese-first frontend dashboard.
- Recommendation center.
- Individual stock detail page.
- Index comparison.
- Data source and update-time display.
- Daily report viewing.

### Phase 3: Fundamentals, Valuation, Industry, And History

Goal: make the recommendation more research-grade by adding fundamental and valuation context.

Scope:

- Financial metrics.
- Valuation metrics.
- Industry comparison.
- Recommendation history.
- More complete single-stock report.
- Peer comparison and relative ranking.

### Phase 4: Events And Thesis Lifecycle

Goal: add qualitative event tracking and thesis monitoring.

Scope:

- Announcements.
- News.
- Policy events.
- Thesis lifecycle:
  - New
  - Confirming
  - Strengthening
  - Weakening
  - Broken
  - Closed
- 7 / 30 / 60 / 90 day review.

### Phase 5: Personal Watchlist, Holdings, Risk, And Alerts

Goal: connect research output to the user's personal monitoring workflow.

Scope:

- Watchlist.
- Personal holdings.
- Position-level risk.
- Exposure and concentration warnings.
- Follow-up reminders.
- Thesis invalidation alerts.

### Phase 6: Advanced Data, Models, Real-Time, And Deployment

Goal: professionalize the system after the personal MVP has proved useful.

Scope:

- Higher-quality paid data sources.
- Wind / Choice / iFinD adapters if needed.
- More advanced models.
- Real-time or near-real-time updates.
- More robust deployment.
- More complete report automation.

## 5. Recommendation Output Standard

The system should not output only a ranked table. Each candidate must be explainable as:

```text
推荐结论
证据链
风险反证
回测支持
后续跟踪
```

Every report should include:

- Recommendation label.
- Core view.
- Key evidence.
- Factor contribution table.
- Signal conflict analysis.
- Risk counter-evidence.
- Scenario analysis.
- Invalidation conditions.
- Follow-up tracking indicators.
- Data source.
- Data date.
- Update time.

## 6. Phase 1 Acceptance Criteria

Phase 1 is complete when the system can:

- Fetch the A-share stock list.
- Fetch all-market daily bars.
- Cache data and support an incremental update plan.
- Filter ST, delisting, suspended, newly listed, low-liquidity, missing-data, limit-up/limit-down edge cases.
- Calculate momentum, trend, relative strength, risk, and liquidity factors.
- Output Top 10 and Top 20 candidate stocks.
- Provide composite score, factor breakdown, recommendation reason, and risk warning for every candidate.
- Generate daily markdown/html recommendation reports.
- Generate single-stock analysis reports.
- Run walk-forward backtests against CSI 300, CSI 500, and ChiNext Index.
- Show data date, source, and update time in all outputs.
- Avoid deterministic buy/sell wording.
