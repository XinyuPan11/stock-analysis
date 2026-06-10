# Phase 2 Summary

## 完成页面

- `/` 首页 Dashboard
- `/compare` 候选股横向对比
- `/reports` 报告中心
- `/health/outputs` 输出健康检查
- `/guide` 运行指引 / 操作手册
- `/stocks/{symbol}` 单股详情页
- `/reports/daily` 每日报告
- `/reports/stocks/{symbol}` 单股报告

## 完成 API

- `GET /health`
- `GET /api/latest`
- `GET /api/candidates`
- `GET /api/candidates/{symbol}`
- `GET /api/summary`
- `GET /api/backtest`
- `GET /api/reports`
- `GET /api/reports/daily`
- `GET /api/reports/stocks/{symbol}`
- `GET /api/factor-explanations`
- `GET /api/factor-explanations/{symbol}`
- `GET /api/factor-summary/{symbol}`
- `GET /api/compare`
- `GET /api/factor-groups`
- `GET /api/factor-groups/{factor_group}`
- `GET /api/output-health`
- `GET /api/report-index`
- `GET /api/failed-symbols`
- `GET /api/data-quality`
- `GET /api/guide`

## 当前 Dashboard 能做什么

- 读取 Phase 1 `outputs/` 文件并展示最新候选股、summary、回测核心指标和报告链接。
- 支持候选股筛选、排序、详情页和横向对比。
- 展示因子解释、因子组贡献摘要和报告内容。
- 汇总报告中心、输出健康检查、failed symbols 和数据质量 warning。
- 提供 `/guide` 作为日常运行入口，集中展示命令、输出文件和排错提示。

## 日常运行入口

启动本地 Dashboard：

```powershell
python backend\scripts\run_api.py --outputs-dir outputs --host 127.0.0.1 --port 8000
```

打开：

```text
http://127.0.0.1:8000/guide
```

## 测试命令

```powershell
python -m unittest discover -s backend\tests
```

## 已知限制

- Phase 2 Dashboard 只读本地 `outputs/`，不重新拉取数据、不重新计算因子、不重新跑回测。
- 前端为 FastAPI 返回的轻量 HTML，不使用 React/Vue 或模板引擎。
- 报告中心与健康检查基于文件命名约定和现有 JSON/CSV 字段。
- 不包含登录、数据库、实时行情、watchlist、持仓、新闻公告或机器学习模型。

## 下一阶段建议

- 准备 PR 描述、截图和验收清单，将 `phase2-dashboard` 合并回 `main`。
- 后续 Phase 3 可考虑更稳定的配置文件、运行批处理脚本或更完整的日常自动化，但仍需保持“不构成投资建议”的表达边界。
