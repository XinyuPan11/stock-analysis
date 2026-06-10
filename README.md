# A 股个人研究终端

这是一个个人使用的 A 股专业研究终端 MVP，不是公开投顾系统，也不提供确定性交易指令。Phase 1 已完成本地日线数据、股票池过滤、因子计算、评分排名、研究报告、walk-forward 回测、缓存预热和数据质量处理。

当前系统默认使用中文输出，面向个人每日收盘后研究。第一版优先使用免费/开源数据源，主要是 BaoStock 和 AKShare；架构上保留 Tushare Pro、Wind、Choice、iFinD 等专业数据源的替换空间。

## 项目边界

- 只关注中国 A 股市场。
- 第一版只做日线收盘后更新，不做实时 tick 或分钟线。
- 推荐表达使用研究优先级标签：`高置信候选`、`候选关注`、`重点观察`、`观察`、`风险过高`、`数据不足`。
- 输出必须包含数据来源、数据日期、更新时间、风险提示和不确定性。
- 本项目仅用于个人研究辅助，不构成投资建议。

## 如何安装依赖

建议在已有 Python 环境中运行：

```powershell
pip install pandas baostock akshare
```

如果使用当前 Windows 环境访问外网或 GitHub，请先设置本机代理：

```powershell
$env:HTTP_PROXY="http://127.0.0.1:8668"
$env:HTTPS_PROXY="http://127.0.0.1:8668"
```

## 如何运行测试

```powershell
python -m unittest discover -s backend\tests
```

Phase 1 最终验收结果：`Ran 91 tests ... OK`。

## 如何预热缓存

建议先预热缓存，再跑研究 pipeline 和回测：

```powershell
$env:HTTP_PROXY="http://127.0.0.1:8668"
$env:HTTPS_PROXY="http://127.0.0.1:8668"
python backend\scripts\prewarm_market_cache.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --include-lookback-days 120 --limit 50 --batch-size 10 --cache-dir data\cache\phase1-final-smoke --output-dir outputs\cache --sleep-seconds 0.5 --retry 1 --resume
```

预热输出：

- `outputs/cache/cache_prewarm_summary_YYYY-MM-DD.json`
- `outputs/cache/cache_prewarm_errors_YYYY-MM-DD.csv`

## 如何生成每日候选股

```powershell
python backend\scripts\run_daily_research.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --benchmark CSI300 --top-n 10 --limit 50 --cache-dir data\cache\phase1-final-smoke --output-dir outputs\daily --retry 1
```

输出：

- `outputs/daily/candidates_YYYY-MM-DD.csv`
- `outputs/daily/candidates_YYYY-MM-DD.json`
- `outputs/daily/summary_YYYY-MM-DD.json`
- `outputs/daily/factors_YYYY-MM-DD.csv`
- `outputs/daily/factors_YYYY-MM-DD.json`
- `outputs/daily/factor_explanations_YYYY-MM-DD.csv`
- `outputs/daily/factor_explanations_YYYY-MM-DD.json`

## 如何启动 Phase 2 本地 Dashboard

Phase 2 的第一版 Dashboard 只读取已经生成的 `outputs/` 文件，不重新拉取数据、不重新计算因子、不重新跑回测。

```powershell
python backend\scripts\run_api.py --outputs-dir outputs --host 127.0.0.1 --port 8000
```

启动后打开：

```text
http://127.0.0.1:8000
```

Phase 2 Dashboard 页面：

```text
/                         首页 Dashboard
/compare                  候选股横向对比
/reports                  报告中心
/health/outputs           输出健康检查
/guide                    运行指引 / 操作手册（日常运行入口）
/stocks/{symbol}          单股详情页
/reports/daily            每日报告
/reports/stocks/{symbol}  单股报告
```

Phase 2 当前是本地只读 Dashboard 阶段性版本：只读取 `outputs/`，不拉数、不重算、不回测。阶段总结见 `PHASE2_SUMMARY.md`。

## Phase 2.5 一键本地日常流程

Phase 2.5 新增本地 workflow runner，用于按顺序串联缓存预热、每日研究、报告生成、walk-forward 回测和 outputs 健康检查。它仍然只调用本地脚本，不新增数据库、不自动交易、不提供确定性交易建议。

先预览计划：

```powershell
python backend\scripts\run_daily_workflow.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --limit 50 --top-n 10 --benchmark CSI300 --cache-dir data\cache\daily-use --output-dir outputs --dry-run
```

正式运行：

```powershell
python backend\scripts\run_daily_workflow.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --limit 50 --top-n 10 --benchmark CSI300 --cache-dir data\cache\daily-use --output-dir outputs
```

Workflow 产物：

- `outputs/workflow/workflow_summary_YYYY-MM-DD.json`
- `outputs/workflow/workflow_log_YYYY-MM-DD.txt`

如果 `outputs/` 下没有每日研究产物，页面和 API 会提示：

```text
No daily research output found. Please run run_daily_research.py first.
```

## 如何生成研究报告

```powershell
python backend\scripts\generate_research_report.py --candidates outputs\daily\candidates_2024-01-31.json --summary outputs\daily\summary_2024-01-31.json --factors outputs\daily\factors_2024-01-31.json --factor-explanations outputs\daily\factor_explanations_2024-01-31.json --output-dir outputs\reports --updated-at "2024-02-01 08:00:00"
```

输出：

- `outputs/reports/daily_report_YYYY-MM-DD.md`
- `outputs/reports/daily_report_YYYY-MM-DD.html`
- `outputs/reports/stocks/{symbol}_YYYY-MM-DD.md`
- `outputs/reports/stocks/{symbol}_YYYY-MM-DD.html`

## 如何运行 walk-forward 回测

```powershell
python backend\scripts\run_backtest.py --provider baostock --start-date 2023-01-01 --end-date 2024-01-31 --lookback-days 120 --rebalance-frequency monthly --top-n 5 --benchmark CSI300 --limit 50 --cache-dir data\cache\phase1-final-smoke --output-dir outputs\backtests --transaction-cost-bps 10 --retry 1
```

输出：

- `outputs/backtests/backtest_summary_YYYY-MM-DD.json`
- `outputs/backtests/backtest_equity_curve_YYYY-MM-DD.csv`
- `outputs/backtests/backtest_rebalance_log_YYYY-MM-DD.csv`
- `outputs/backtests/backtest_report_YYYY-MM-DD.md`
- `outputs/backtests/backtest_report_YYYY-MM-DD.html`

## 什么数据不会提交到 GitHub

以下内容是本地运行产物，不应提交：

- `data/cache/`
- `outputs/`
- `__pycache__/`
- 临时 smoke test 输出

## 主要文档

- `PHASE1_FINAL_REPORT.md`：Phase 1 最终验收报告。
- `PHASE1_TASKS.md`：Phase 1 完成清单和运行顺序。
- `PROJECT_RULES.md`：项目边界、标签和输出规则。
- `DATA_SOURCE_STRATEGY.md`：数据源和缓存策略。
- `TECHNICAL_ARCHITECTURE.md`：技术架构。
- `MVP_ROADMAP.md`：个人专业研究终端路线。

## 重要声明

本项目仅为个人研究、模型验证和复盘辅助工具。任何候选标签、评分、回测结果和报告内容都不构成投资建议。
