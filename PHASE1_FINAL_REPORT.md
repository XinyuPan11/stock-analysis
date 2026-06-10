# Phase 1 Final Report

## 1. Phase 1 完成范围

Phase 1 已形成一个本地可运行、可复现、可解释、可回测的 A 股个人研究 MVP。

已完成：

- 数据层。
- A 股候选池过滤。
- 因子计算。
- 综合评分和候选排名。
- 因子贡献解释。
- 每日研究 pipeline。
- Markdown/HTML 研究报告。
- 单股研究报告。
- walk-forward 回测。
- 缓存预热和失败股票重跑。
- 数据清洗和错误分类。

未进入 Phase 1：

- 前端。
- FastAPI。
- 财务深度分析。
- 新闻、公告、政策事件。
- watchlist。
- 持仓监控。
- 实时数据。
- 复杂机器学习模型。

## 2. 当前系统能力

### 数据层

- 获取 A 股股票池。
- 获取个股日线。
- 获取 CSI300 指数日线。
- 本地缓存和 coverage 覆盖判断。
- 增量补齐。
- 数据清洗。
- 错误分类。

### 过滤层

- ST、*ST、退市和非正常上市状态过滤。
- 新股过滤。
- 数据不足和长期停牌过滤。
- 低流动性过滤。
- 缺失数据和价格异常过滤。

### 因子层

- 动量。
- 趋势。
- 相对强度。
- 风险。
- 流动性。

### 评分排名

- 100 分综合评分。
- Top N ranking。
- confidence。
- 风险标记。
- 正面证据和负面证据。
- 因子贡献解释表。

### 报告

- 每日候选报告。
- 单股分析报告。
- Markdown 和 HTML。
- 使用真实 summary 和真实 factor explanations。

### 回测

- walk-forward。
- Top N 等权组合。
- 交易成本。
- CSI300 基准对比。
- summary、equity curve、rebalance log、Markdown/HTML 报告。

## 3. 主要 CLI 命令

### 测试

```powershell
python -m unittest discover -s backend\tests
```

### 缓存预热

```powershell
$env:HTTP_PROXY="http://127.0.0.1:8668"
$env:HTTPS_PROXY="http://127.0.0.1:8668"
python backend\scripts\prewarm_market_cache.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --include-lookback-days 120 --limit 50 --batch-size 10 --cache-dir data\cache\phase1-final-smoke --output-dir outputs\cache --sleep-seconds 0.5 --retry 1 --resume
```

### 每日研究

```powershell
python backend\scripts\run_daily_research.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --benchmark CSI300 --top-n 10 --limit 50 --cache-dir data\cache\phase1-final-smoke --output-dir outputs\daily --retry 1
```

### 研究报告

```powershell
python backend\scripts\generate_research_report.py --candidates outputs\daily\candidates_2024-01-31.json --summary outputs\daily\summary_2024-01-31.json --factors outputs\daily\factors_2024-01-31.json --factor-explanations outputs\daily\factor_explanations_2024-01-31.json --output-dir outputs\reports --updated-at "2024-02-01 08:00:00"
```

### 回测

```powershell
python backend\scripts\run_backtest.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --lookback-days 120 --rebalance-frequency monthly --top-n 5 --benchmark CSI300 --limit 50 --cache-dir data\cache\phase1-final-smoke --output-dir outputs\backtests --transaction-cost-bps 10 --retry 1
```

## 4. 主要输出文件

### 缓存预热

- `outputs/cache/cache_prewarm_summary_YYYY-MM-DD.json`
- `outputs/cache/cache_prewarm_errors_YYYY-MM-DD.csv`

### 每日研究

- `outputs/daily/candidates_YYYY-MM-DD.csv`
- `outputs/daily/candidates_YYYY-MM-DD.json`
- `outputs/daily/summary_YYYY-MM-DD.json`
- `outputs/daily/factors_YYYY-MM-DD.csv`
- `outputs/daily/factors_YYYY-MM-DD.json`
- `outputs/daily/factor_explanations_YYYY-MM-DD.csv`
- `outputs/daily/factor_explanations_YYYY-MM-DD.json`

### 研究报告

- `outputs/reports/daily_report_YYYY-MM-DD.md`
- `outputs/reports/daily_report_YYYY-MM-DD.html`
- `outputs/reports/stocks/{symbol}_YYYY-MM-DD.md`
- `outputs/reports/stocks/{symbol}_YYYY-MM-DD.html`

### 回测

- `outputs/backtests/backtest_summary_YYYY-MM-DD.json`
- `outputs/backtests/backtest_equity_curve_YYYY-MM-DD.csv`
- `outputs/backtests/backtest_rebalance_log_YYYY-MM-DD.csv`
- `outputs/backtests/backtest_report_YYYY-MM-DD.md`
- `outputs/backtests/backtest_report_YYYY-MM-DD.html`

### 错误输出

- `outputs/errors/failed_symbols_YYYY-MM-DD.csv`

## 5. 推荐标签定义

- `高置信候选`：多个信号共振，研究优先级最高。
- `候选关注`：进入正式候选池，值得进一步研究。
- `重点观察`：有明显亮点，但需要继续确认。
- `观察`：普通跟踪。
- `风险过高`：风险不适合进入当前候选池。
- `数据不足`：历史或关键字段不足，暂时无法可靠判断。

标签只代表研究优先级，不代表交易结论。

## 6. 数据质量处理规则

错误分类：

- `non_numeric_market_data`：关键价格字段无法安全转成数值。
- `empty_market_data`：provider 返回空行情。
- `missing_required_columns`：缺少关键字段。
- `invalid_price_data`：OHLC 结构异常。
- `missing_liquidity_data`：成交额或成交量缺失，作为 warning 处理。

处理原则：

- 可转换数字字符串会安全转换。
- 成交额/成交量缺失可填 0 并记录 warning。
- 关键价格字段不可靠时跳过，不硬填假数据。
- 错误写入 summary 和 CSV。

## 7. 回测方法和注意事项

回测方法：

- walk-forward。
- 每个调仓日只使用当时之前的历史数据。
- 使用现有过滤、因子、评分和排名逻辑选 Top N。
- 等权持有到下一个调仓日。
- 计算交易成本后收益。
- 与 CSI300 对比。

注意事项：

- 回测仅用于个人研究和模型验证。
- 当前样本仍偏小，不能代表全市场最终结论。
- 免费数据源可能有缺失和延迟。
- 后续需要更长区间和更多样本验证。

## 8. Phase 1 最终验收结果

最终测试：

- `python -m unittest discover -s backend\tests`
- 结果：`Ran 91 tests ... OK`

最终 smoke：

- 缓存预热 limit 50：成功，50 只全部成功，error_count 为 0。
- 每日研究 pipeline limit 50：成功，scored_count 为 10，fetch_error_count 为 0。
- 研究报告生成：成功，无 fallback warning。
- 回测 limit 50：成功，fetch_error_count 为 0。

回测样例指标：

- 成本后总收益：约 6.20%。
- 基准总收益：约 -17.30%。
- 超额收益：约 23.50%。
- 最大回撤：约 -19.07%。
- 调仓次数：13。

## 9. 已知限制

- 第一版仅支持本地 CLI。
- 数据源是免费/开源数据源，稳定性和字段质量不等同于专业终端。
- 当前财务、估值、公告、新闻、行业事件未接入。
- 当前基准 smoke 使用 CSI300。
- 未实现全市场并发优化。
- `listing_date_missing` 仍可能出现，因为免费股票池字段不完整。
- 本机 pandas 提示 numexpr 版本偏旧，不影响当前测试结果。

## 10. 不构成投资建议声明

本项目仅为个人研究辅助、模型验证和复盘工具。任何候选标签、评分、报告和回测结果都不构成投资建议。

## 11. Phase 2 建议路线

Phase 2 建议在不破坏 Phase 1 CLI 的基础上实现：

1. FastAPI。
2. 简单前端 dashboard。
3. 推荐中心。
4. 个股详情页。
5. 指数对比。
6. 数据更新时间展示。
7. 更清晰的报告浏览入口。

Phase 2 不应重写 Phase 1 的 data、research、reports、backtesting 模块，而应复用这些稳定能力。
