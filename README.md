# Stock Analysis

Professional stock recommendation and analysis platform.

This project is intended to become a professional decision-support terminal for stock research, recommendation tracking, risk monitoring, and event-aware analysis. It should combine real market data, financial statements, annual/quarterly report analysis, news and policy intelligence, quantitative signals, prediction models, backtesting, and transparent risk warnings.

The product scope is focused on the Chinese stock market. Version 1 should cover mainland China A-shares only, including Shanghai, Shenzhen, and Beijing exchanges.

## Current Documents

- `PRD.md`: Product requirements document for the first professional MVP.
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

The platform should not be a simple "stock tip" website. It should be built as an evidence-backed research and portfolio decision system:

- show real supporting data for every recommendation;
- use Chinese as the default website language, with Chinese/English switching planned from the beginning;
- analyze A-share individual stocks first, with CSI 300, CSI 500, ChiNext Index, STAR 50, and industry indices as background benchmarks;
- start with AKShare and BaoStock prototype data while preserving a replaceable professional data-provider architecture;
- separate facts, analyst interpretation, and model forecasts;
- explain buy, hold, reduce, and sell recommendations;
- track recommendation history and thesis changes;
- include compliance, audit logs, and risk disclosures before public use.

## Important Notice

This repository is for software product development and research tooling. It is not financial advice, and any public investment recommendation feature should be reviewed for legal and regulatory compliance before launch.
