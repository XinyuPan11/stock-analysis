# Product Requirements Document: Personal A-Share Research Terminal

## 1. Product Summary

Stock Analysis is a personal A-share professional research terminal for daily after-close research. It helps the user find candidate A-share stocks, inspect evidence, understand risk, validate signals with backtests, and generate professional research reports.

The product is not a public investment advisory platform and does not provide public buy/sell advice. Every candidate result must be supported by data source, data date, update time, evidence chain, risk counter-evidence, uncertainty, and follow-up conditions.

## 2. Product Decisions For Version 1

| Area | Decision |
| --- | --- |
| First market | Mainland China A-shares: Shanghai Stock Exchange, Shenzhen Stock Exchange, and Beijing Stock Exchange |
| Reason | The product will focus only on the Chinese stock market; A-shares provide the core universe for China-focused equity research, policy analysis, sector rotation, and domestic capital-market monitoring |
| First user type | Personal professional research user |
| Product type | Personal A-share research terminal |
| Recommendation style | Evidence-backed candidate labels, not deterministic buy/sell advice |
| Update target | Daily after market close |
| Product language | Chinese-first UI with optional Chinese/English switching |
| Analysis target | A-share individual stocks |
| Benchmark context | CSI 300, CSI 500, ChiNext Index, STAR 50, and industry indices |
| ETF scope | Optional extension, not a primary version 1 recommendation target |
| Prototype data strategy | Use AKShare and BaoStock first, with Tushare Pro optional; keep provider abstraction ready for Wind, Choice, and iFinD |
| Phase 1 boundary | Data, filters, factors, scoring, explanations, reports, and walk-forward backtesting only |
| Public advice boundary | Personal research only; no public investment advisory service, paid subscription, or public buy/sell recommendations |

The recommendation universe is limited to mainland China A-share individual stocks. Hong Kong stocks, US stocks, China ADRs, and global equities are excluded unless the product scope is explicitly changed later. CSI 300, CSI 500, ChiNext Index, STAR 50, and industry indices are required benchmark context. China ETFs are optional future extensions, not Phase 1 recommendation targets.

## 3. Target Users

### 3.1 Primary User

The primary user is the owner of this repository, using the terminal for personal daily A-share research.

Needs:

- after-close A-share candidate discovery;
- professional explanation for why a stock ranks highly;
- risk counter-evidence, not only positive signals;
- walk-forward backtest support;
- markdown/html reports that can be reviewed later;
- data source, data date, update time, and uncertainty shown everywhere.

### 3.2 Future User Modes

Future phases may add watchlist, personal holdings, alerts, dashboard views, and more advanced report review. Complex roles, subscriptions, and institutional access are out of scope.

## 4. MVP Scope

### 4.1 Phase 1 In Scope

- A-share stock universe.
- Daily close data after market close.
- Local cache and incremental update plan.
- A-share filters.
- Momentum, trend, relative strength, risk, and liquidity factors.
- Composite scoring.
- Top 10 and Top 20 candidate lists.
- Recommendation labels:
  - `候选关注`
  - `重点观察`
  - `观察`
  - `风险过高`
- Factor explanation.
- Signal conflict detection.
- Daily recommendation report.
- Single-stock report.
- Walk-forward backtest against CSI 300, CSI 500, and ChiNext Index.
- Data source, data date, update time, risk warning, and uncertainty in all outputs.

### 4.2 Later Phase Scope

- FastAPI and simple frontend dashboard.
- Stock detail page.
- Index and industry comparison pages.
- Financial metrics.
- Valuation metrics.
- Recommendation history.
- Announcements, news, policy events.
- Thesis lifecycle.
- Watchlist.
- Personal holdings.
- Risk monitoring and reminders.
- More professional data sources.
- More advanced models.

### 4.3 Out Of Scope For Phase 1

- Public investment advisory service.
- Paid subscription.
- Complex user or permission system.
- Public buy/sell recommendations.
- Real-time tick data.
- Wind / Choice / iFinD integration.
- News and announcement ingestion.
- Deep financial statement analysis.
- Watchlist and holdings monitor.
- FastAPI and web dashboard.
- ETF recommendation workflows.
- Trade execution.
- Brokerage integration.
- Fully automated high-frequency trading.
- Multi-market global coverage.
- Hard-coded single-language UI strings.

<!-- Historical platform scope below remains as long-term reference, but Phase 1 is governed by MVP_ROADMAP.md and PROJECT_RULES.md. -->

### 4.4 Long-Term Reference Scope

- Evidence-backed recommendation labels.
- Data freshness indicators.
- Recommendation history.
- Manual analyst notes.
- Initial rule-based scoring engine.
- Chinese-first user interface.
- Internationalization foundation for Chinese/English switching.
- Benchmark views for CSI 300, CSI 500, ChiNext Index, STAR 50, and industry indices.

## 5. Phase 1 Core User Journeys

### 5.1 Run Daily Research

1. User runs the after-close daily research command.
2. System updates A-share daily data and benchmark index data.
3. System filters unsuitable stocks.
4. System calculates factors, scores, conflicts, and candidate labels.
5. System outputs Top 10 and Top 20 candidate lists.
6. System generates a daily markdown/html report.

### 5.2 Review A Candidate

1. User opens the daily report.
2. User reviews candidate label, composite score, and factor breakdown.
3. User checks why the stock ranked highly.
4. User reviews risk counter-evidence and signal conflicts.
5. User checks invalidation conditions and follow-up indicators.
6. User decides whether to manually track the stock.

### 5.3 Validate The Logic

1. User runs a walk-forward backtest.
2. System forms historical Top 10 and Top 20 portfolios without future data.
3. System compares results against CSI 300, CSI 500, and ChiNext Index.
4. System outputs return, Alpha, Sharpe, max drawdown, win rate, turnover, and post-cost return.
5. User uses the backtest report to judge whether the recommendation logic deserves trust.

## 5A. Future User Journeys

### 5A.1 Find A Stock Opportunity In Dashboard

1. User opens the market overview.
2. User sees sectors, themes, unusual movers, and recommendation buckets.
3. User filters by rating, sector, valuation, momentum, and risk.
4. User opens a stock detail page.
5. User reviews price action, fundamentals, valuation, events, and risks.
6. User adds the stock to a watchlist or portfolio.

### 5A.2 Validate A Recommendation In Dashboard

1. User opens a recommended stock.
2. User sees rating, horizon, target range, confidence, and invalidation condition.
3. User expands the evidence panel.
4. User reviews the financial, valuation, technical, event, and risk factors behind the rating.
5. User checks source links and update times.
6. User accepts, watches, overrides, or rejects the thesis.

### 5A.3 Monitor Thesis Change

1. A filing, news item, price event, or financial update arrives.
2. The system maps the event to affected stocks and sectors.
3. The risk or recommendation score changes if the event is material.
4. User receives an alert.
5. User can see exactly which data changed and why the thesis changed.

### 5A.4 Review Portfolio Risk

1. User creates or imports holdings.
2. System calculates position, sector, theme, and factor exposure.
3. User sees concentration, volatility, drawdown, and correlation risk.
4. Recommendations are adjusted or flagged if they increase hidden exposure.

## 6. Future Product Screens

Product screens are Phase 2+ work. Phase 1 outputs markdown/html reports and data artifacts.

### 6.1 Market Overview

Must show:

- Major indices.
- Sector and theme heatmaps.
- Market breadth.
- Top gainers and losers.
- Abnormal volume.
- Volatility and risk indicators.
- Today focus: earnings, policy, macro, and major events.
- Data freshness status.

### 6.2 Recommendation Center

Must show:

- Candidate关注 list.
- 重点观察 list.
- 观察 list.
- 风险过高 list.
- Filters for sector, risk, valuation, momentum, confidence, and horizon.
- Clear recommendation timestamp and model version.

### 6.3 Stock Detail Page

Must show:

- Quote and chart.
- Key price and volume metrics.
- Financial statement summary.
- Valuation and peer comparison.
- Annual/quarterly report insights.
- News, filings, and event timeline.
- Recommendation thesis.
- Bull/base/bear scenario.
- Risk dashboard.
- Source links and update time.

### 6.4 Industry And Theme Page

Must show:

- Sector ranking.
- Theme ranking.
- Industry chain map.
- Leading and lagging stocks.
- Policy and macro sensitivity.
- Sector valuation and earnings trend.

### 6.5 Watchlist And Portfolio

Must show:

- User selected stocks.
- Alerts.
- Position size.
- Cost basis.
- Profit/loss.
- Sector and factor exposure.
- Risk warnings.
- Thesis status for each holding.

### 6.6 Data Quality And Admin

Must show:

- Data source health.
- Last successful update time.
- Missing data warnings.
- Failed ingestion jobs.
- Model version status.
- Recommendation audit log.

## 7. Recommendation System Requirements

### 7.1 Recommendation Labels

| Label | Meaning |
| --- | --- |
| 候选关注 | Data-backed candidate worth reviewing after market close |
| 重点观察 | Stronger candidate, but still not deterministic buy advice |
| 观察 | Interesting but confirmation is missing or signal quality is mixed |
| 风险过高 | Risk, data quality, liquidity, or signal conflict is too high |

### 7.2 Required Recommendation Fields

Every recommendation must include:

- Ticker and company name.
- Candidate label.
- Time horizon.
- Confidence score.
- Scenario range when available.
- Entry or observation condition.
- Stop-loss or invalidation condition.
- Key positive evidence.
- Key negative evidence.
- Risk summary.
- Source data timestamps.
- Recommendation update time.
- Model or rule version.
- Data source, data date, update time, and uncertainty.

### 7.3 Scoring Dimensions

- Fundamental quality.
- Growth momentum.
- Valuation.
- Market momentum.
- Capital flow if available.
- Event catalyst.
- Risk.
- Confidence.

### 7.4 Thesis Lifecycle

Each thesis must have one status:

- New.
- Confirming.
- Strengthening.
- Weakening.
- Broken.
- Closed.

## 8. Data Requirements

### 8.1 Required Data Types

- Prices and volume.
- Corporate actions.
- Financial statements.
- Company metadata.
- Sector and industry classification.
- Filings and reports.
- News and events.
- Earnings calendar.
- Macro data.
- Recommendation and score history.

### 8.2 Source Requirements

- Every displayed data point must have a source or vendor.
- Every source must have a timestamp.
- Data freshness must be visible in the UI.
- Stale data must be marked.
- Failed updates must be visible to admins.
- Raw source data should be retained separately from normalized data.

### 8.3 MVP Data Strategy

For the first version:

- Use one market data vendor or a clearly labeled delayed data source.
- Use China-focused disclosure sources such as exchange announcements, company reports, official disclosure platforms, and licensed market-data vendors where access permits.
- Use a configurable provider interface so vendors can be replaced later.
- Do not depend on a single fragile scraping source for production.

## 9. Model And Backtesting Requirements

### 9.1 Model V1

The first production model should be interpretable:

- Rule-based factor scoring.
- Simple factor-weighted recommendation score.
- Scenario-based target range.
- Risk-adjusted confidence score.

### 9.2 Later Models

Later models may include:

- Factor models.
- Sector rotation models.
- Earnings surprise models.
- Expected return models.
- Drawdown risk models.
- News and filing event models.
- Ensemble models.

### 9.3 Validation Requirements

No model should be promoted without:

- Walk-forward backtesting.
- Out-of-sample validation.
- Leakage checks.
- Slippage and transaction cost assumptions.
- Stress-period performance.
- Model version record.
- Clear explanation of input features.

## 10. Non-Functional Requirements

### 10.1 Reliability

- Core pages should load even if one data vendor is degraded.
- Stale data must be marked rather than silently shown as current.
- Recommendation calculation failures must be logged.

### 10.2 Performance

- Dashboard initial load target: under 3 seconds with cached data.
- Stock detail load target: under 3 seconds for summary data.
- Heavy report analysis can run asynchronously.

### 10.3 Security

- Authentication required for saved watchlists and portfolios.
- Role-based access for admin and analyst functions.
- API keys and vendor credentials must not be stored in frontend code.
- Audit logs required for recommendation changes.

### 10.4 Personal-Use Boundary

- Show risk disclosure.
- Show recommendation timestamp.
- Show source trail.
- Distinguish facts, interpretation, and forecasts.
- Store recommendation history.
- Avoid deterministic public buy/sell language.
- Keep output for personal research unless the product scope changes later.

### 10.5 Language And Localization

- The default website output language should be Chinese.
- The system should support a Chinese/English language switch.
- User-facing UI strings must not be hard-coded inside components.
- Recommendation explanations, risk warnings, alert text, empty states, and data quality messages should support `zh-CN` and `en-US`.
- Financial metric IDs, ticker symbols, exchange codes, source names, and model feature names should remain language-neutral internally.
- Chinese professional terminology should be clear and consistent, especially for rating labels, valuation, risk, financial statements, and model confidence.

## 11. Phase 1 Acceptance Criteria

Phase 1 is acceptable when:

- The system can fetch the A-share stock list.
- The system can fetch all-market daily bars.
- Data can be cached and has an incremental update plan.
- ST, delisting, suspended, newly listed, low-liquidity, and missing-data stocks can be filtered.
- Momentum, trend, relative strength, risk, and liquidity factors can be calculated.
- Top 10 and Top 20 candidate lists can be generated.
- Each candidate has composite score, factor breakdown, reason, risk warning, source, data date, and update time.
- Daily markdown/html recommendation reports can be generated.
- Single-stock analysis reports can be generated.
- Walk-forward backtests can compare against CSI 300, CSI 500, and ChiNext Index.
- Output language avoids deterministic buy/sell advice.

## 12. Milestones

### Milestone 1: Phase 1 Research Pipeline

- A-share universe and daily bars.
- Filters.
- Factors.
- Scoring.
- Explanations.
- Reports.
- Walk-forward backtests.

### Milestone 2: Simple Dashboard

- FastAPI.
- Simple Chinese-first dashboard.
- Recommendation center.
- Stock detail page.
- Index comparison.
- Data update-time display.

### Milestone 3: Fundamentals And History

- Financial metrics.
- Valuation metrics.
- Industry comparison.
- Recommendation history.

### Milestone 4: Events And Thesis Lifecycle

- Announcements.
- News.
- Policy events.
- Thesis lifecycle.
- 7 / 30 / 60 / 90 day review.

### Milestone 5: Personal Monitoring

- Watchlist.
- Personal holdings.
- Risk monitoring.
- Reminders and alerts.

### Milestone 6: Advanced Data And Models

- Paid/professional data sources.
- Advanced models.
- Real-time or near-real-time updates.
- Deployment hardening.

## 13. Resolved MVP Defaults

- Phase 1 output language: simplified Chinese first.
- English switching remains a future-friendly design constraint, not a Phase 1 implementation blocker.
- MVP data budget: free/open-source first, AKShare and BaoStock priority, Tushare Pro optional.
- Phase 1 recommendation targets: A-share individual stocks only.
- Phase 1 benchmark context: CSI 300, CSI 500, ChiNext Index, STAR 50, and later industry indices.
- ETFs are optional later extensions, not Phase 1 recommendation targets.
- No analyst approval workflow is needed for personal use.
- Phase 1 uses daily after-close data, not real-time tick data.

## 14. Implementation Rule

Do not build prediction models before data quality, backtesting, and source traceability exist. A professional stock platform must first be trustworthy, then intelligent.
