# Implementation Plan: Professional Stock Recommendation & Analysis Platform

## Objective
Build a professional-grade stock recommendation and analysis website for advanced investors, analysts, and portfolio managers. The platform should combine real-time market data, historical financial data, fundamental analysis, event/news intelligence, quantitative signals, predictive models, risk controls, and explainable investment recommendations.

## Context
- Triggered by: User request to build a detailed, professional stock recommendation website with real-time updates, true supporting data, predictive modeling, annual/financial report analysis, industry and policy catalysts, geopolitical context, buy/sell/watchlist recommendations, and risk warnings.
- Related work: None yet.
- Important boundary: The product can provide decision-support analysis and model-generated recommendations, but any public-facing investment advice may require legal/compliance review, licensed investment adviser qualifications, risk disclosures, audit logs, and jurisdiction-specific controls.

## Open Questions
- Target markets: A-shares, Hong Kong stocks, US stocks, global equities, or a phased rollout?
- Target users: Internal professional desk, paid professional subscribers, retail investors, or institutional clients?
- Recommendation style: Pure research support, model scoring, explicit buy/sell calls, or portfolio allocation advice?
- Data budget: Free/public data, mid-tier APIs, or professional terminals/data vendors such as Wind, Choice, Bloomberg, Refinitiv/LSEG, FactSet, S&P Capital IQ, Nasdaq Data Link, Polygon, IEX Cloud, Tiingo, SEC EDGAR, HKEX, exchange feeds, and local filings sources?
- Real-time requirement: Tick-level, second-level, minute-level, or delayed quotes?
- Compliance scope: China mainland, Hong Kong, US, EU, or multi-jurisdiction?
- Asset coverage: Equities only, or also ETFs, indices, sectors, futures, FX, rates, commodities, and macro indicators?
- Output format: Web dashboard only, or also alerts, PDF research notes, API access, and portfolio monitoring?

## Product Vision
This should be designed as a professional stock decision terminal with four jobs:

1. Find opportunities.
2. Explain why the opportunity exists.
3. Quantify upside, downside, timing, and confidence.
4. Monitor whether the thesis is becoming stronger or broken.

The platform should never simply say "buy this stock." It should show the evidence chain: valuation, earnings quality, growth drivers, market regime, sector momentum, capital flow, news/policy catalysts, technical condition, risk events, and the assumptions behind the model.

## Core User Workflows

### 1. Market Overview
- Real-time indices, sectors, themes, market breadth, turnover, volatility, rates, FX, commodities, and global risk indicators.
- "Today focus" panel: sectors gaining momentum, stocks with abnormal volume, earnings surprises, policy/news catalysts, negative risk events.
- Heatmaps by sector, theme, valuation percentile, earnings revision, fund flow, and technical strength.

### 2. Stock Recommendation Center
- Lists by strategy bucket:
  - Short-term buy candidates.
  - Medium/long-term compounder candidates.
  - Value reversal candidates.
  - Event-driven opportunities.
  - High-risk high-reward watchlist.
  - Hold/observe.
  - Reduce/sell/avoid.
- Every recommendation must include:
  - Rating or score.
  - Suggested horizon.
  - Entry zone.
  - Stop-loss or invalidation condition.
  - Target price or scenario range.
  - Confidence level.
  - Key evidence.
  - Key risks.
  - Last update time.

### 3. Individual Stock Analysis Page
- Price, volume, intraday trend, K-line chart, moving averages, volatility, beta, relative strength.
- Financial summary: revenue, profit, margin, ROE/ROIC, debt, cash flow, free cash flow, inventory, receivables, capex, shareholder returns.
- Annual/quarterly report analysis:
  - Key financial statement changes.
  - Management discussion extraction.
  - Segment performance.
  - Risk disclosures.
  - Auditor notes.
  - Guidance and earnings call summary when available.
- Valuation:
  - P/E, forward P/E, P/B, P/S, EV/EBITDA, FCF yield, dividend yield.
  - Historical valuation percentile.
  - Peer comparison.
  - Scenario valuation.
  - DCF or residual income model for suitable companies.
- Catalysts:
  - Earnings date.
  - Product cycle.
  - Regulatory/policy events.
  - Industry demand/supply changes.
  - M&A, buybacks, dividends, insider transactions.
- Risk dashboard:
  - Liquidity risk.
  - Leverage risk.
  - Earnings quality risk.
  - Valuation risk.
  - Policy/regulatory risk.
  - Geopolitical risk.
  - Concentration and correlation risk.
  - News sentiment deterioration.
- Final professional summary:
  - Bull case.
  - Base case.
  - Bear case.
  - Thesis.
  - What would change the recommendation.

### 4. Industry & Theme Analysis
- Sector ranking by valuation, growth, earnings revision, capital flow, momentum, policy support, and event intensity.
- Theme pages such as AI, semiconductors, new energy, defense, consumer, banks, biotech, cloud, robotics, gold, oil, shipping, and rate-sensitive sectors.
- Industry chain mapping:
  - Upstream, midstream, downstream.
  - Key companies.
  - Price drivers.
  - Supply/demand indicators.
  - Policy sensitivity.
- "Recommended sectors to watch" should explain:
  - Why now.
  - What data confirms the trend.
  - Which stocks are leaders vs laggards.
  - What event would invalidate the view.

### 5. News, Policy, and Event Intelligence
- Ingest market news, filings, policy releases, earnings calendars, macro releases, central bank announcements, geopolitical events, and company announcements.
- Classify events by:
  - Asset impacted.
  - Sector impacted.
  - Direction: positive, negative, mixed, uncertain.
  - Time horizon: intraday, short-term, medium-term, structural.
  - Confidence.
- Event-to-stock mapping:
  - Example: export controls, rate cuts, AI capex, oil price shock, local consumption policy, real estate policy, drug approval, tariff changes.
- Real-time alerts when a material event changes a stock's thesis or model score.

### 6. Portfolio & Watchlist Tools
- User portfolios with positions, cost basis, risk exposure, drawdown, factor exposure, and sector concentration.
- Alerts:
  - Price breaks.
  - Valuation reaches target.
  - Financial report changes thesis.
  - Negative news cluster.
  - Technical breakdown.
  - Stop-loss/invalidation condition triggered.
- Professional notes:
  - Analyst can write thesis notes.
  - Version history of recommendations.
  - "Why did the model change?" explanation log.

## Recommendation Framework

Each stock should receive multiple sub-scores instead of one opaque score:

| Score Area | Description |
| --- | --- |
| Fundamental Quality | Profitability, cash flow quality, balance sheet, ROE/ROIC, earnings stability |
| Growth Momentum | Revenue/profit growth, analyst revisions, order/backlog signals, industry demand |
| Valuation | Absolute valuation, peer valuation, historical percentile, scenario upside/downside |
| Market Momentum | Price trend, relative strength, volume, volatility, breakout/breakdown signals |
| Capital Flow | Institutional flow, northbound/southbound flow where available, block trades, buybacks |
| Event Catalyst | Earnings, policy, industry news, product cycle, regulation, M&A, macro catalysts |
| Risk Score | Leverage, liquidity, governance, policy, geopolitical, earnings quality, crowding |
| Confidence Score | Data freshness, source reliability, model agreement, signal consistency |

Recommendation labels should be explainable:
- Strong Buy: high score, clear catalyst, acceptable risk, strong evidence alignment.
- Buy: positive risk/reward, but with some uncertainty.
- Watch: thesis forming but confirmation missing.
- Hold: no decisive edge or already fairly valued.
- Reduce: upside limited, risk rising, thesis weakening.
- Sell/Avoid: broken thesis, severe risk, valuation pressure, or negative event cluster.

## Prediction Model Plan

### Phase 1: Baseline Models
- Factor model using valuation, quality, momentum, growth, volatility, liquidity, and event features.
- Time-series models for price/volatility forecasting.
- Earnings surprise probability model.
- Risk model for drawdown and stop-loss probability.
- Sector rotation model.

### Phase 2: Event-Aware Models
- NLP model for news, filings, earnings calls, and policy documents.
- Event classification and stock impact mapping.
- Sentiment and materiality scoring.
- "Thesis change detector" comparing latest events against previous recommendation assumptions.

### Phase 3: Professional Forecasting Layer
- Scenario model:
  - Bull/base/bear cases.
  - Probability-weighted target price.
  - Expected return distribution.
  - Downside risk and max drawdown estimate.
- Portfolio-aware recommendation:
  - Avoid recommending too many correlated names.
  - Factor exposure control.
  - Sector and country risk control.

### Phase 4: Backtesting & Live Evaluation
- Backtest every strategy by market, sector, cap bucket, liquidity bucket, and regime.
- Measure:
  - Total return.
  - Alpha.
  - Sharpe/Sortino.
  - Max drawdown.
  - Hit rate.
  - Turnover.
  - Slippage.
  - Transaction costs.
  - Capacity.
  - Performance during stress periods.
- Live paper-trading evaluation before any production recommendation is trusted.

## Data Architecture

### Data Sources
- Market data: quotes, OHLCV, tick/minute bars, indices, sectors, ETF proxies.
- Fundamentals: annual reports, quarterly reports, financial statements, consensus estimates, dividends, buybacks, corporate actions.
- Filings and announcements: exchange filings, company announcements, SEC EDGAR for US-listed companies, local disclosure platforms for target markets.
- News and events: licensed news APIs, exchange announcements, government policy websites, central banks, regulators, industry associations.
- Macro: rates, FX, inflation, PMI, employment, credit, commodities, yield curves.
- Alternative/professional data if budget allows: fund flows, supply chain, web traffic, app ranking, shipping, satellite, options, short interest.

### Pipeline
- Ingestion layer:
  - Scheduled historical pulls.
  - Streaming or polling for real-time data.
  - Vendor failover and freshness checks.
- Normalization layer:
  - Symbol mapping.
  - Corporate action adjustment.
  - Currency conversion.
  - Calendar alignment.
  - Timezone handling.
- Storage layer:
  - Time-series database for quotes and factors.
  - Relational database for fundamentals, users, recommendations, portfolios.
  - Object storage for filings, parsed documents, model artifacts.
  - Vector database/search index for filings/news semantic retrieval.
- Quality layer:
  - Missing data detection.
  - Outlier checks.
  - Source reconciliation.
  - Data freshness SLA.
  - Audit logs.

## Suggested Technical Stack

| Layer | Recommendation |
| --- | --- |
| Frontend | React + TypeScript, professional dashboard UI, charts, heatmaps, tables, watchlists |
| Backend API | Python FastAPI for market data, research, recommendations, portfolios, alerts |
| Data Jobs | Python workers with scheduled jobs and streaming consumers |
| Database | PostgreSQL for core data, TimescaleDB or ClickHouse for time-series/analytics |
| Cache | Redis for real-time quotes, sessions, hot recommendations, alerts |
| Search/NLP | OpenSearch/Elasticsearch plus vector search for filings/news retrieval |
| ML | Python, scikit-learn, XGBoost/LightGBM, PyTorch when needed, MLflow for experiments |
| Charts | TradingView Lightweight Charts, ECharts, or Highcharts Stock depending on license |
| Observability | Prometheus/Grafana or equivalent, structured logs, data freshness monitoring |
| Deployment | Docker, CI/CD, cloud deployment with secrets management |

## Affected Modules

| Layer | Module | Change Type | Impact |
| --- | --- | --- | --- |
| Backend | auth/users | New module | User accounts, roles, professional access |
| Backend | market-data service | New module | Real-time and historical quotes |
| Backend | fundamentals service | New module | Financial statements and annual report metrics |
| Backend | filings/news ingestion | New module | Documents, news, policy events |
| Backend | recommendation engine | New module | Scores, labels, thesis generation |
| Backend | model service | New module | Forecasts, backtests, live scoring |
| Backend | risk service | New module | Risk metrics, alerts, invalidation rules |
| Backend | portfolio service | New module | Holdings, exposure, performance |
| Backend | alert service | New module | Real-time notifications |
| Backend | audit/compliance | New module | Disclosures, recommendation logs, source traceability |
| Backend | schemas/API contracts | New module | Strongly typed API responses |
| Backend | database models | New module | Users, stocks, prices, statements, events, scores, portfolios |
| Frontend | dashboard pages | New module | Market overview, sector views, recommendation center |
| Frontend | stock detail page | New module | Full single-stock research workflow |
| Frontend | portfolio/watchlist pages | New module | Professional monitoring tools |
| Frontend | chart components | New module | K-line, valuation bands, heatmaps, scenario charts |
| Frontend | evidence panels | New module | Source-backed thesis, financial report excerpts, news links |
| Frontend | risk panels | New module | Risk warnings, stress tests, invalidation alerts |
| Frontend | admin/data quality pages | New module | Data freshness and source health |
| Infrastructure | data vendors/secrets | New config | API keys, rate limits, contracts |
| Infrastructure | worker queues | New module | Ingestion, scoring, alerts |
| Infrastructure | monitoring | New module | Latency, failures, data freshness, model drift |
| Tests | backend/frontend/model tests | New tests | Reliability and regression coverage |

## Step-by-Step Delivery Roadmap

### Phase 0: Scope, Market, and Compliance
- Decide first market and user type.
- Decide whether the platform gives explicit recommendations or internal decision-support only.
- Define compliance disclaimers, user suitability, audit logs, and recommendation approval workflow.
- Select initial data vendors and confirm licensing.

### Phase 1: MVP Research Terminal
- Build authentication, watchlist, stock search, stock detail page, market overview.
- Add delayed or near-real-time quote data.
- Add basic financial statements and valuation metrics.
- Add manual analyst notes and simple rule-based recommendation labels.
- Add source links for every displayed fact.

### Phase 2: Professional Data Layer
- Add robust ingestion pipelines for prices, fundamentals, announcements, news, and macro data.
- Add data freshness dashboard and anomaly detection.
- Add corporate action handling and adjusted price series.
- Add sector/theme mapping and peer groups.

### Phase 3: Recommendation Engine V1
- Implement multi-factor scoring.
- Add short-term, long-term, watch, reduce, and sell buckets.
- Add evidence-backed recommendation pages.
- Add risk score and invalidation conditions.
- Add recommendation version history.

### Phase 4: Backtesting & Model Validation
- Build backtesting engine with transaction costs and slippage.
- Test strategies by regime, sector, market cap, liquidity, and stress period.
- Add model performance dashboard.
- Prevent production deployment of models without live/paper-trading validation.

### Phase 5: Event Intelligence
- Ingest filings, earnings reports, news, policy releases, macro events, and geopolitical updates.
- Add NLP extraction and event classification.
- Map events to sectors and stocks.
- Add real-time thesis-change alerts.

### Phase 6: Forecasting & Scenario Analysis
- Add scenario-based expected return and target price ranges.
- Add model ensemble forecasts.
- Add bull/base/bear case valuation.
- Add confidence and uncertainty explanations.

### Phase 7: Portfolio-Level Professional Tools
- Add portfolio import/manual entry.
- Add exposure, factor, sector, country, currency, and correlation risk.
- Add portfolio-aware recommendations.
- Add rebalance suggestions and risk limits.

### Phase 8: Institutional Hardening
- Add role-based permissions.
- Add analyst approval workflow.
- Add compliance review queue.
- Add audit logs for every recommendation and model change.
- Add high availability, vendor failover, disaster recovery, and security review.

## Verification

### Integration Verification
- User can search a stock and see current quote, historical chart, financial statements, valuation, risks, news/events, and recommendation.
- Every displayed recommendation includes source-backed evidence and an update timestamp.
- Data freshness dashboard correctly flags stale market data, stale fundamentals, and failed ingestion jobs.
- A financial report update changes derived metrics and triggers a recommendation recalculation.
- A material negative event appears on the affected stock page and updates risk score or alert state.
- A model recommendation can be traced back to factor values, source data, and model version.
- A watchlist alert fires when price, risk, or thesis conditions are met.

### Regression Checks
- Backend unit and integration tests for data ingestion, scoring, risks, and API contracts.
- Frontend tests for dashboard, stock detail page, recommendation center, and alert states.
- Model tests for leakage prevention, backtest correctness, and reproducibility.
- Data quality tests for missing values, outliers, symbol mapping, and corporate action handling.
- Security checks for secrets, auth, role permissions, and audit logging.

## Risks & Unknowns

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Real-time data licensing is expensive or restrictive | High | High | Start with delayed data for MVP; design vendor abstraction; confirm contracts before launch |
| Public investment recommendations may require regulatory licensing | High | High | Add legal review, disclaimers, suitability controls, approval workflow, and jurisdiction-specific rules |
| Model overfitting or data leakage creates misleading recommendations | High | High | Enforce walk-forward validation, leakage tests, out-of-sample evaluation, and live paper trading |
| News/policy NLP may misclassify materiality | Medium | High | Keep human review path for major events; show confidence and original source |
| Data quality issues create false conclusions | High | High | Build source reconciliation, freshness SLA, anomaly detection, and audit trails |
| Recommendation labels become too opaque | Medium | High | Use explainable sub-scores, evidence panels, and model version logs |
| Real-time system latency or vendor failure | Medium | High | Use caching, queues, vendor fallback, and degraded-mode UI |
| Users overtrust model output | Medium | High | Show risk, uncertainty, scenario ranges, and invalidation conditions prominently |
| Global macro/geopolitical interpretation is subjective | Medium | Medium | Separate facts from interpretation; provide source links and confidence levels |
| Professional users need export/API integrations | Medium | Medium | Design API-first and add PDF/CSV exports after core workflows stabilize |

## Acceptance Criteria
- The platform supports at least one target market with reliable quote, historical price, and financial statement data.
- Each recommendation has explicit horizon, rating, evidence, risk, confidence, update time, and source links.
- Stock pages include fundamentals, valuation, technicals, news/events, financial report analysis, and risk dashboard.
- Industry pages rank sectors/themes using multiple transparent factors.
- Predictive models are backtested with leakage controls and transaction-cost assumptions.
- Real-time or near-real-time data freshness is visible and monitored.
- Users can create watchlists/portfolios and receive relevant alerts.
- Model outputs are explainable and versioned.
- Compliance disclaimers and audit logs exist before public launch.
- The app can distinguish data-backed facts from analyst interpretation and model-generated forecasts.

## Estimation Summary

| Metric | Value |
| --- | --- |
| Total backend modules affected | 12+ |
| Total frontend modules affected | 8+ |
| Migration required | Yes |
| API changes | Yes, many new endpoints/contracts |
| Overall complexity | large |

## Recommended Skills For Next Steps
- `project-planner`: Continue refining scope, modules, risks, and acceptance criteria.
- `documentation-writer`: Turn this plan into a formal PRD, technical spec, investor-facing product brief, or compliance-oriented documentation.
- `spreadsheets`: Build stock-scoring templates, factor ranking sheets, backtest result summaries, and financial statement models.
- `pdf`: Parse and verify annual reports, research notes, and source documents when PDF layout matters.
- `playwright` or `browser:control-in-app-browser`: Test the frontend dashboard and verify charts, tables, and responsive layouts.
- `debugging` / `Verification Before Completion`: Validate data freshness, model outputs, and ingestion bugs before claiming the system works.
- `test-generator`: Generate focused tests for scoring logic, API contracts, model leakage prevention, and UI state behavior.

## Professional Improvements To Add
- Add a "thesis lifecycle" system: new, confirmed, weakening, broken, closed.
- Add "what would make us wrong" for every recommendation.
- Add scenario probability instead of one target price.
- Add a position-sizing suggestion based on risk, volatility, liquidity, and confidence.
- Add correlation and crowding warnings so the system does not recommend many stocks with the same hidden exposure.
- Add regime detection: bull, bear, range-bound, liquidity tightening, liquidity easing, inflation shock, recession scare.
- Add model disagreement indicators when fundamentals, momentum, and news signals conflict.
- Add analyst override with mandatory reason and audit trail.
- Add "source confidence" because not all data/news sources deserve equal weight.
- Add post-trade/recommendation review: after 7/30/90/180 days, evaluate whether the thesis worked and why.
