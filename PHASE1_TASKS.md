# Phase 1 Tasks

Phase 1 目标已经完成：形成一个可本地运行、可复现、可解释、可回测的 A 股个人研究 MVP。

## 已完成模块

### 1. 数据层

- A 股股票池获取。
- 个股日线行情获取。
- CSI300 指数日线行情获取。
- Provider 抽象层：AKShare、BaoStock、Tushare Pro 占位。
- 统一日线 schema：`symbol, trade_date, open, high, low, close, volume, amount, adj_close, source`。
- 本地 CSV 缓存和 coverage 覆盖判断。
- 增量更新。
- 数据清洗和错误分类。
- 缓存预热、resume、retry、failed symbols 重跑。

### 2. 过滤层

- ST、*ST、退市、非正常上市状态过滤。
- 上市不足 180 天过滤。
- 长期停牌和数据不足过滤。
- 近 20 日成交额过低过滤。
- 缺失数据和价格异常过滤。
- A 股交易日覆盖检查。

### 3. 因子层

- 动量：20/60/120 日收益率。
- 趋势：MA5/MA20/MA60、均线站上和多头排列。
- 相对强度：相对 CSI300 的 20/60/120 日超额收益。
- 风险：20/60 日波动率、最大回撤、20/60 日最大回撤。
- 流动性：20/60 日平均成交额和成交量。

### 4. 评分和解释

- 综合评分 100 分制。
- 子分：动量、趋势、相对强度、风险、流动性。
- 标签：`高置信候选`、`候选关注`、`重点观察`、`观察`、`风险过高`、`数据不足`。
- Top N ranking。
- 因子贡献解释表。

### 5. 研究 pipeline

- `run_daily_research.py` 串联股票池、过滤、行情、基准、因子、评分、排名。
- 支持 `limit`、`offset`、`batch_id`、`retry`。
- 输出 candidates、summary、factors、factor_explanations。
- 失败股票输出 failed symbols CSV。

### 6. 研究报告

- `generate_research_report.py` 生成每日 Markdown/HTML 报告。
- 生成单股 Markdown/HTML 报告。
- 报告读取真实 summary 和真实 factor explanations。
- 报告包含数据来源、更新时间、风险提示和免责声明。

### 7. Walk-forward 回测

- `run_backtest.py` 支持 monthly/weekly walk-forward。
- 每个调仓日只使用当时可见历史数据。
- Top N 等权组合。
- 支持交易成本。
- 对比 CSI300。
- 输出 summary、equity curve、rebalance log、Markdown/HTML 回测报告。

### 8. 批量稳定性

- `prewarm_market_cache.py` 支持批量缓存预热。
- 支持 resume、retry、failed symbols、symbols-file、include-lookback-days。
- limit 50 可稳定预热和回测。
- limit 100 已验证可完成预热。

## Phase 1 运行顺序

1. 运行测试。
2. 预热缓存。
3. 运行每日研究 pipeline。
4. 生成研究报告。
5. 运行 walk-forward 回测。
6. 查看 `outputs/` 下的报告和 JSON/CSV。

## Phase 1 完成门槛

- 全量测试通过。
- limit 50 真实数据 smoke 通过。
- 报告不使用确定性交易指令。
- 所有输出包含数据来源、日期和更新时间。
- 回测明确禁止未来函数。
- 缓存和 outputs 不提交到 GitHub。

## 后续不在 Phase 1 范围内

- 前端 dashboard。
- FastAPI 服务。
- 财务深度分析。
- 新闻、公告、政策事件。
- watchlist 和持仓监控。
- 实时数据。
- 复杂机器学习模型。
