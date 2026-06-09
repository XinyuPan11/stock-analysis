# Project Rules

## 1. Product Rule

This project is a personal A-share professional research terminal. It is not a public investment advisory product.

Do not design Phase 1 around:

- public users;
- paid subscriptions;
- institutional permission systems;
- trade execution;
- public buy/sell advice;
- real-time tick data;
- high-cost institutional data sources.

## 2. Recommendation Language Rule

Allowed labels:

- `候选关注`
- `重点观察`
- `观察`
- `风险过高`

Avoid deterministic trading advice such as:

- buy now;
- strong buy;
- sell immediately;
- guaranteed upside;
- must hold;
- certain target.

Every recommendation must include uncertainty and risk language.

## 3. Evidence Rule

Every recommendation output must include:

- data source;
- data date;
- update time;
- factor evidence;
- risk counter-evidence;
- invalidation condition;
- follow-up indicators.

## 4. Phase Discipline Rule

Phase 1 only implements:

- data;
- filters;
- factors;
- scoring;
- explanations;
- reports;
- backtesting.

Move these to later phases:

- FastAPI dashboard;
- frontend UI;
- news and announcements;
- policy event intelligence;
- financial deep dive and valuation;
- watchlist;
- holdings;
- reminders and alerts;
- real-time updates;
- Wind / Choice / iFinD.

## 5. Data Rule

Phase 1 uses daily bars after market close.

Priority data sources:

1. AKShare.
2. BaoStock.
3. Tushare Pro, optional.

Do not call provider libraries from analysis code. Analysis code must consume normalized internal schemas only.

## 6. Backtest Rule

Backtests must be walk-forward.

Backtests must not use future data.

Backtest reports must compare against:

- CSI 300;
- CSI 500;
- ChiNext Index.

Backtest reports must include:

- cumulative return;
- annualized return;
- Alpha;
- Sharpe;
- max drawdown;
- win rate;
- turnover;
- post-cost return.
