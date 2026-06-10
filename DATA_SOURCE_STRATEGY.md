# Data Source Strategy

## 目标

Phase 1 使用免费/开源数据源做 A 股个人研究 MVP，但架构必须按专业数据源可替换的方式设计。

## Provider 分层

数据源调用集中在：

```text
backend/src/stock_analysis/data/providers/
  base.py
  akshare_provider.py
  baostock_provider.py
  tushare_provider.py
```

上层通过 `MarketDataService` 调用，不直接调用 AKShare、BaoStock 或 Tushare。

## 统一日线 schema

所有日线 provider 输出：

```text
symbol
trade_date
open
high
low
close
volume
amount
adj_close
source
```

股票池输出：

```text
symbol
name
exchange
listing_status
listing_date
delisting_date
is_st
source
```

## 当前数据源

### BaoStock

Phase 1 最终 smoke 使用 BaoStock 完成：

- A 股股票池。
- 个股日线。
- CSI300 指数日线。
- 缓存预热。
- 每日研究 pipeline。
- walk-forward 回测。

### AKShare

保留为免费数据源之一，可用于后续补充股票池、指数、行业、ETF 或财务估值数据。

### Tushare Pro

当前保留 provider 占位，后续可接入 token 后用于更稳定的数据补充。

## 缓存策略

本地缓存位于 `data/cache/`，不提交到 GitHub。

缓存能力：

- 按 provider、dataset、symbol、adjusted 分目录存储。
- 每个行情 CSV 配套 coverage JSON。
- 读取时先检查覆盖区间。
- 覆盖则直接读缓存。
- 不覆盖则只补缺失区间。

## 预热策略

使用：

```powershell
python backend\scripts\prewarm_market_cache.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --include-lookback-days 120 --limit 50 --batch-size 10 --cache-dir data\cache\phase1-final-smoke --output-dir outputs\cache --sleep-seconds 0.5 --retry 1 --resume
```

预热输出：

- `outputs/cache/cache_prewarm_summary_YYYY-MM-DD.json`
- `outputs/cache/cache_prewarm_errors_YYYY-MM-DD.csv`

## 数据清洗和错误分类

清洗模块：`backend/src/stock_analysis/data/data_cleaning.py`

错误类型：

- `non_numeric_market_data`：关键价格字段无法转成数值。
- `empty_market_data`：provider 返回空行情。
- `missing_required_columns`：缺少关键字段。
- `invalid_price_data`：OHLC 结构异常。
- `missing_liquidity_data`：成交额或成交量缺失，作为 warning 处理。

规则：

- 可转换数字字符串会安全转为数值。
- 缺成交额/成交量可填 0 并记录 warning。
- 关键价格字段不可靠时跳过，不硬填假数据。

## 后续专业数据源扩展

后续可增加：

- Wind。
- Choice。
- iFinD。
- Tushare Pro 完整接口。
- 行业指数。
- ETF。
- 财务和估值。
- 公告、新闻、政策事件。

扩展原则：新增 provider 必须输出统一 schema，分析模块不得直接依赖 provider 原始字段。
