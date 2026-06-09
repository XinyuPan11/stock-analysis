# Professional Production Workflow: Stock Recommendation & Analysis Platform

## Goal

Build a professional-grade stock analysis website for serious investors, analysts, and portfolio managers. The product must support real data, transparent evidence, stock recommendations, industry monitoring, financial report analysis, event intelligence, risk warnings, prediction models, and eventually real-time updates.

The core principle is simple: every recommendation must answer five questions:

1. What is the opportunity?
2. Why does it exist now?
3. What data supports it?
4. What can go wrong?
5. What condition changes or invalidates the recommendation?

## Phase 0: Product Boundary And Compliance

### Purpose

Before writing application code, define what the system is legally and professionally allowed to do.

### Decisions

- Initial product type: professional decision-support platform, not an unqualified public financial adviser.
- Recommendation wording: use evidence-backed ratings and risk scenarios instead of unsupported promises.
- User target: advanced investors, analysts, and professional users.
- Initial market: mainland China A-shares only, covering Shanghai Stock Exchange, Shenzhen Stock Exchange, and Beijing Stock Exchange.
- Excluded markets: US stocks, Hong Kong stocks, China ADRs, and global equities.
- Compliance baseline: show risk disclosure, recommendation timestamp, source trail, and model limitation notice.

### Deliverables

- Product requirements document.
- Compliance and disclaimer draft.
- User roles: admin, analyst, professional user, read-only viewer.
- Definition of recommendation labels: strong buy, buy, watch, hold, reduce, sell/avoid.

### Acceptance Criteria

- The team can explain what the platform does and does not claim to do.
- Every future feature can be judged against this boundary.

## Phase 1: Data Source Strategy

### Purpose

A stock platform is only as good as its data. Real-time, financial, news, and filing data should be planned before UI and model work.

### Data Categories

- Market data: price, volume, OHLCV, intraday bars, indices, sectors, ETFs.
- Fundamentals: income statement, balance sheet, cash flow, margins, ROE, ROIC, debt, free cash flow.
- Filings: annual reports, quarterly reports, announcements, earnings call transcripts where available.
- News and policy: company news, industry policy, central bank events, regulation, geopolitics.
- Macro: rates, FX, commodities, inflation, PMI, employment, yield curves.
- Optional professional data: analyst estimates, institutional flow, short interest, options, supply chain signals.

### Recommended Approach

- Start with one or two data vendors only.
- Store original source timestamps.
- Keep raw data and normalized data separately.
- Build data freshness checks from day one.
- Never show a recommendation without the latest successful data update time.

### Deliverables

- Data vendor comparison.
- Data dictionary.
- Symbol mapping rules.
- Market calendar and timezone rules.
- Data freshness service requirements.

### Acceptance Criteria

- Each data point has a source, timestamp, and refresh policy.
- The system can flag stale or missing data.

## Phase 2: Technical Architecture

### Purpose

Design the system so real-time data, historical analysis, model scoring, and frontend dashboards do not become tangled together.

### Recommended Stack

- Frontend: React, TypeScript, professional dashboard UI, charting library.
- Backend API: Python FastAPI.
- Database: PostgreSQL for core data.
- Time-series analytics: TimescaleDB or ClickHouse when scale requires it.
- Cache and real-time layer: Redis.
- Background jobs: Python workers with scheduled ingestion and scoring.
- Search/NLP: OpenSearch or vector search for filings, reports, and news.
- ML: scikit-learn, LightGBM/XGBoost first; deep learning only when needed.
- Experiment tracking: MLflow or equivalent.

### Core Services

- Market data service.
- Fundamentals service.
- Filing and news ingestion service.
- Recommendation engine.
- Risk engine.
- Forecasting/model service.
- Backtesting service.
- Portfolio/watchlist service.
- Alert service.
- Compliance and audit service.

### Acceptance Criteria

- Services have clear responsibility boundaries.
- Data ingestion, model scoring, and UI rendering can be tested independently.

## Phase 3: MVP Research Terminal

### Purpose

Build the first usable version before advanced AI or prediction work.

### Features

- Stock search.
- Market overview.
- Stock detail page.
- Basic quote and historical chart.
- Financial statement summary.
- Valuation metrics.
- Watchlist.
- Manual analyst notes.
- Basic recommendation label with timestamp and explanation.

### Stock Detail Page Must Include

- Current price and price change.
- K-line or historical price chart.
- Key financial metrics.
- Valuation percentile and peer comparison.
- Recent news and filings.
- Risk summary.
- Recommendation thesis.
- Source links and update time.

### Acceptance Criteria

- A user can open one stock and understand its price trend, fundamentals, valuation, news, risks, and current recommendation.
- The page clearly separates facts, interpretation, and model output.

## Phase 4: Recommendation Engine V1

### Purpose

Create a transparent scoring framework before complex prediction models.

### Scoring Dimensions

- Fundamental quality.
- Growth momentum.
- Valuation attractiveness.
- Market momentum.
- Capital flow where available.
- Event catalyst strength.
- Risk score.
- Confidence score.

### Recommendation Output

Each recommendation should include:

- Rating.
- Time horizon.
- Entry zone or observation condition.
- Target scenario range.
- Stop-loss or invalidation condition.
- Evidence summary.
- Risk summary.
- Confidence level.
- Last update time.

### Acceptance Criteria

- Two analysts can inspect the same recommendation and understand why the system produced it.
- A changed factor can explain a changed recommendation.

## Phase 5: Financial Report And Filing Analysis

### Purpose

Professional users need proof from annual reports, quarterly reports, and disclosures, not only price charts.

### Features

- Parse financial statements.
- Extract year-over-year and quarter-over-quarter changes.
- Highlight revenue, margin, cash flow, debt, inventory, receivables, and capex changes.
- Extract management discussion themes.
- Identify risk disclosure changes.
- Link each extracted point back to the original source.

### Acceptance Criteria

- The platform can explain how the latest report changed the investment thesis.
- Important report-derived signals appear in stock analysis and recommendation pages.

## Phase 6: News, Policy, And Event Intelligence

### Purpose

Stocks move because fundamentals, liquidity, expectations, and events change. The system must connect events to affected stocks and sectors.

### Features

- Ingest news, policy releases, earnings calendars, macro events, and company announcements.
- Classify events as positive, negative, mixed, or uncertain.
- Map events to stocks, sectors, and themes.
- Score event materiality and time horizon.
- Trigger thesis-change alerts.

### Acceptance Criteria

- A material news or policy event can update affected stock pages and risk scores.
- Users can see the original source and why the event matters.

## Phase 7: Backtesting And Model Validation

### Purpose

No prediction or recommendation model should be trusted without historical and live validation.

### Required Tests

- Walk-forward backtesting.
- Out-of-sample validation.
- Transaction cost and slippage modeling.
- Liquidity constraints.
- Sector, market cap, and market regime breakdown.
- Stress-period testing.
- Leakage checks.

### Metrics

- Total return.
- Alpha.
- Sharpe and Sortino.
- Max drawdown.
- Hit rate.
- Turnover.
- Average holding period.
- Capacity.
- Performance by regime.

### Acceptance Criteria

- A model cannot be promoted to production unless validation results are documented.
- Backtest assumptions are visible to the user or analyst.

## Phase 8: Forecasting Model

### Purpose

Use real historical data and current data to forecast future risk and return, while showing uncertainty.

### Model Path

- Start with factor scoring and interpretable models.
- Add sector rotation models.
- Add earnings surprise probability models.
- Add expected return and drawdown models.
- Add event-aware models after event data is reliable.
- Use ensemble outputs only after individual models are validated.

### Forecast Output

- Bull/base/bear scenarios.
- Probability-weighted target range.
- Expected return distribution.
- Downside risk.
- Confidence and uncertainty.
- Key drivers behind the forecast.

### Acceptance Criteria

- Forecasts are not shown as certainties.
- Users can inspect the factors that drive each forecast.

## Phase 9: Portfolio And Risk Layer

### Purpose

Professional recommendations must consider portfolio exposure, not just individual stock attractiveness.

### Features

- Portfolio import or manual holdings.
- Position-level profit/loss.
- Sector and theme exposure.
- Factor exposure.
- Correlation and concentration risk.
- Stop-loss and thesis invalidation alerts.
- Position sizing suggestion based on volatility, liquidity, confidence, and risk.

### Acceptance Criteria

- The system can warn when many recommendations share the same hidden risk.
- Users can see whether a stock improves or worsens portfolio risk.

## Phase 10: Real-Time Update And Alerts

### Purpose

Once the core analysis is reliable, add real-time behavior carefully.

### Real-Time Priorities

- Quote updates.
- Abnormal volume.
- Price breakout or breakdown.
- Risk threshold trigger.
- Material news or filing update.
- Recommendation score change.
- Watchlist and portfolio alerts.

### Acceptance Criteria

- The UI shows data freshness.
- Alerts are traceable to source data and rules.
- Delayed, stale, or failed data is visibly marked.

## Phase 11: Professional UI And Workflow Design

### Purpose

The interface should feel like a professional research terminal, not a marketing website.

### UI Principles

- Dense but readable information.
- Tables, charts, heatmaps, filters, tabs, watchlists, and alerts.
- No decorative landing page as the main experience.
- Fast navigation between market, sector, stock, portfolio, and alerts.
- Every important number should have source, timestamp, and context.

### First Screens

- Market overview.
- Recommendation center.
- Stock detail page.
- Industry/theme analysis.
- Watchlist and portfolio risk.
- Data freshness/admin page.

### Acceptance Criteria

- A professional user can scan opportunities quickly.
- A user can drill from recommendation to evidence in one or two clicks.

## Phase 12: Security, Compliance, And Audit

### Purpose

Investment-related software needs strong accountability.

### Requirements

- Authentication.
- Role-based permissions.
- Recommendation version history.
- Analyst override logs.
- Source traceability.
- Model version traceability.
- Risk disclosures.
- Secure secrets management.
- Data vendor license controls.

### Acceptance Criteria

- Every recommendation can be reconstructed after the fact.
- The system can prove which data, model, and analyst action produced a recommendation.

## Phase 13: Launch And Iteration

### Launch Path

1. Internal prototype with delayed data.
2. Analyst-reviewed recommendations only.
3. Paper-trading validation.
4. Limited beta with professional users.
5. Real-time data and alerts.
6. Public or paid launch only after legal review.

### Operating Rhythm

- Daily data quality check.
- Weekly model performance review.
- Monthly recommendation post-mortem.
- Quarterly product and compliance review.

## Immediate Next Steps

1. Put `plan.md` and this workflow into GitHub.
2. Create a formal PRD from the plan.
3. Define the A-share universe, including supported exchanges, stock boards, industry classifications, and index context.
4. Choose MVP data source.
5. Scaffold the frontend/backend project.
6. Build the first stock detail page with mocked or delayed data.
7. Add real data ingestion.
8. Add rule-based recommendation scoring.
9. Add backtesting before any serious prediction claim.
10. Add event and filing intelligence.

## Recommended Skills For Future Work

- `project-planner`: refine project phases, module impact, and acceptance criteria.
- `documentation-writer`: turn the plan into PRD, technical spec, and user-facing docs.
- `spreadsheets`: build factor scoring templates, valuation sheets, and backtest summaries.
- `pdf`: parse and verify annual reports and research PDFs.
- `playwright` or `browser`: test the web dashboard and verify UI behavior.
- `debugging` and `Verification Before Completion`: validate data freshness, model correctness, and ingestion bugs.
- `test-generator`: create tests for scoring, data pipelines, API contracts, and UI states.
