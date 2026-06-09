# Stock Analysis

Personal A-share professional research terminal.

This project is intended to become a personal professional research terminal for daily A-share analysis. The current MVP focuses on after-close daily data, factor scoring, candidate ranking, explanations, reports, and backtesting.

The product scope is focused on the Chinese stock market. Version 1 should cover mainland China A-shares only, including Shanghai, Shenzhen, and Beijing exchanges.

## Current Documents

- `PRD.md`: Product requirements document for the first professional MVP.
- `MVP_ROADMAP.md`: Personal A-share research terminal roadmap and phase boundaries.
- `PHASE1_TASKS.md`: Phase 1 file structure, implementation order, and completion gate.
- `PROJECT_RULES.md`: Product, recommendation language, data, and backtest rules.
- `TECHNICAL_ARCHITECTURE.md`: Technical architecture for frontend, backend, data, recommendations, models, alerts, and bilingual output.
- `DATA_SOURCE_STRATEGY.md`: Prototype data-source strategy for China A-share data with professional provider abstraction.
- `SMOKE_TESTS.md`: Recorded verification results for the real-data provider smoke tests.
- `plan.md`: Full implementation plan for the professional stock recommendation platform.
- `PRODUCTION_WORKFLOW.md`: Step-by-step production workflow for building the platform from planning to launch.

## First Data Smoke Test

```powershell
$env:HTTP_PROXY="http://127.0.0.1:8668"
$env:HTTPS_PROXY="http://127.0.0.1:8668"
python backend/scripts/smoke_market_data.py --provider akshare --symbol 000001 --index-code CSI300 --start-date 2024-01-01 --end-date 2024-01-31
```

## Initial Direction

The terminal should not be a simple "stock tip" tool. It should be built as an evidence-backed personal research system:

- show real supporting data for every recommendation;
- use Chinese as the default website language, with Chinese/English switching planned from the beginning;
- analyze A-share individual stocks first, with CSI 300, CSI 500, ChiNext Index, STAR 50, and industry indices as background benchmarks;
- start with AKShare and BaoStock prototype data while preserving a replaceable professional data-provider architecture;
- separate facts, analyst interpretation, and model forecasts;
- use non-deterministic labels: `候选关注`, `重点观察`, `观察`, `风险过高`;
- explain each candidate through conclusion, evidence chain, risk counter-evidence, backtest support, and follow-up tracking;
- track recommendation history and thesis changes;
- include data source, data date, update time, risk warnings, and uncertainty in every output.

## Important Notice

This repository is for personal software product development and research tooling. It is not financial advice and should not present deterministic public buy/sell recommendations.
