# Technical Architecture

## 定位

本项目是个人使用的 A 股专业研究终端。Phase 1 是本地 CLI MVP，重点是数据、过滤、因子、评分、报告、回测和可复现运行。

Phase 1 不包含前端、FastAPI、实时服务、watchlist、持仓、新闻公告或复杂机器学习模型。

## 分层结构

```text
backend/src/stock_analysis/
  data/
    providers/
    cache.py
    cache_prewarm.py
    data_cleaning.py
    schemas.py
    service.py

  research/
    ashare_filters.py
    factors.py
    scoring.py
    factor_explanation.py
    recommendation_engine.py
    pipeline.py

  reports/
    report_generator.py

  backtesting/
    metrics.py
    walk_forward.py
    backtest_report.py

backend/scripts/
  prewarm_market_cache.py
  run_daily_research.py
  generate_research_report.py
  run_backtest.py
```

## 数据流

```text
Provider
-> MarketDataService
-> LocalCsvCache
-> Data Cleaning
-> A-share Filters
-> Factor Calculation
-> Scoring and Ranking
-> Factor Explanations
-> Reports
-> Walk-forward Backtest
```

## 数据层

`MarketDataService` 是上层唯一入口：

- `get_stock_universe`
- `get_stock_daily`
- `get_index_daily`

数据源由 provider 实现：

- `BaoStockProvider`
- `AkShareProvider`
- `TushareProvider`

缓存由 `LocalCsvCache` 管理，支持 coverage 判断和增量补齐。

## 数据质量层

`data_cleaning.py` 负责：

- 数字字符串安全转换。
- 空行情识别。
- 缺关键字段识别。
- 价格结构异常识别。
- 成交额/成交量缺失 warning。

关键价格字段不可靠时直接失败，避免污染因子和回测。

## 过滤层

`ashare_filters.py` 对候选池做研究前过滤：

- ST、退市、非正常状态。
- 新股。
- 数据不足。
- 长期停牌。
- 低流动性。
- 缺失数据。
- 价格异常。

过滤层只负责排除不适合进入候选池的股票，不计算因子。

## 因子层

`factors.py` 只依赖统一日线 schema：

- momentum。
- trend。
- relative_strength。
- risk。
- liquidity。

数据不足时返回 warning，不静默产生高分。

## 评分和解释层

`scoring.py` 使用规则和横截面分位数，不使用机器学习。

权重：

- 动量 25。
- 趋势 20。
- 相对强度 20。
- 风险 20。
- 流动性 15。

`factor_explanation.py` 输出每个因子的原始值、标准化值、权重和贡献。

## 研究 pipeline

`pipeline.py` 串联：

```text
stock universe
-> daily bars
-> benchmark
-> filters
-> factors
-> scoring
-> ranking
-> factor explanations
-> files
```

支持：

- `limit`
- `offset`
- `batch_id`
- `retry`
- failed symbols CSV

## 报告层

`report_generator.py` 生成：

- 每日候选报告。
- 单股分析报告。
- Markdown。
- HTML。

报告使用真实 summary 和 factor explanations，不重新拉数据。

## 回测层

`walk_forward.py` 实现：

- monthly/weekly 调仓。
- Top N 等权组合。
- 交易成本。
- 基准对比。
- equity curve。
- rebalance log。

无未来函数规则：

- 调仓日只使用 `trade_date <= rebalance_date` 的历史数据。
- 持有期收益从调仓日之后的交易日开始。

## 输出目录

```text
outputs/cache/
outputs/daily/
outputs/reports/
outputs/backtests/
outputs/errors/
```

这些目录是运行产物，不提交 GitHub。

## Phase 2 架构方向

Phase 2 可以在不破坏 Phase 1 CLI 的基础上增加：

- FastAPI。
- 简单 dashboard。
- 推荐中心。
- 个股详情页。
- 指数对比。
- 数据更新时间展示。

Phase 2 仍应复用 Phase 1 的 data、research、reports、backtesting 模块。
