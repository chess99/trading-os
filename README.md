# Trading OS

Trading OS 是一个 agent-native 的 A 股投研与量化研究平台。它的目标不是把一组固定脚本每天跑完，而是把数据、计算、证据链和研究产物沉淀成可复用的研究内核，让 Claude Code / Codex 这类 agent 通过确定性的 recipe 完成筛选、深研、因子研究和回测。

## 核心原则

- Agent 负责理解用户意图、选择 recipe、解释结果和说明限制。
- 底层系统负责确定性数据访问、缓存、计算、回测、风控和证据链。
- 所有正式投资分析必须使用真实数据；缺数据时明确降级或失败，不使用模拟值补结论。
- 所有报告都应链接 `data/research/runs/{run_id}/manifest.json` 和 `report.md`，方便复核数据来源、计算步骤和口径限制。

## 架构

```
src/trading_os/
  research/      ResearchStore、DataHub、research recipes、research CLI
  strategy/      策略基类 + Signal + 内置策略
  backtest/      事件驱动回测引擎，包含 A 股交易规则
  paper/         模拟交易引擎，带 EventLog 审计
  risk/          硬性风控门控
  data/          历史数据 schema、兼容数据源 adapter、旧数据兼容层
  journal/       SQLite append-only 事件日志

skills/          Agent 工作流说明
data/research/
  runs/          recipe 运行证据链：manifest、trace、tables、charts、report
artifacts/
  research/      单标的最终深度研究报告
  watchlist/     自选池状态和逐标的追踪
```

## ResearchStore / DataHub

`ResearchStore` 是本地研究存储层，基于 DuckDB/Parquet 思路组织数据集：

- `universe_snapshot`：股票池、名称、上市状态、ST/退市状态。
- `quote_snapshot`：全市场日行情快照。
- `bars`：历史 OHLCV，按需补齐。
- `fundamentals`：财务指标和报表摘要。
- `estimates`：一致预期、估值快照、目标价等。
- `news`：新闻、公告、事件。
- `factors`：因子横截面和历史结果。
- `run_manifest`：每次研究运行的输入、数据版本、步骤和输出路径。

`DataHub` 是唯一数据入口，支持 `cache_first`、`refresh`、`offline`、`lazy_fill` 策略。研究 recipe 不应绕过 DataHub 直接访问数据源。

## 常用命令

```bash
# 数据缓存和状态
python -m trading_os data status
python -m trading_os data refresh universe --as-of YYYY-MM-DD --end YYYY-MM-DD
python -m trading_os data refresh quotes --as-of YYYY-MM-DD --end YYYY-MM-DD
python -m trading_os data refresh bars --symbols SSE:600660 --start 2020-01-01 --end YYYY-MM-DD

# 迁移旧基本面 JSON 到 ResearchStore
python -m trading_os data migrate legacy-fundamentals --as-of YYYY-MM-DD

# CANSLIM 快筛
python -m trading_os research run canslim_screen --as-of YYYY-MM-DD --top 30

# 单标的深度研究
python -m trading_os research company SSE:600660 --template quality_growth --as-of YYYY-MM-DD

# Daily CANSLIM 收口
python -m trading_os research daily-canslim --as-of YYYY-MM-DD

# 观察池提醒监控
python -m trading_os alert monitor --mode watchlist --once

# 因子研究和回测
python -m trading_os factor run momentum_roe --as-of YYYY-MM-DD
python -m trading_os backtest run canslim_breakout --start YYYY-MM-DD --end YYYY-MM-DD
```

每次 recipe 运行都会生成：

```
data/research/runs/{run_id}/manifest.json
data/research/runs/{run_id}/trace.md
data/research/runs/{run_id}/tables/*.csv
data/research/runs/{run_id}/charts/*.png
data/research/runs/{run_id}/report.md
```

## 研究工作流

### Daily CANSLIM Closure

使用：

```bash
python -m trading_os research daily-canslim --as-of YYYY-MM-DD
```

该 workflow 会解析最近一个已完成交易日，运行全 A CANSLIM 快筛，研究每一个 strict
candidate，写入决策，更新 `artifacts/watchlist/state.json`，并生成
`artifacts/research/daily-canslim-YYYYMMDD.md`。

`--top` 只限制展示结果，绝不能限制下游 strict 候选处理。workflow 不能在写完 run
manifest 后停止，必须完成决策、观察池更新和人类可读日报。

### Watchlist Alert Monitor

使用：

```bash
python -m trading_os alert monitor --mode watchlist --once
```

提醒监控只评估机器可读的观察池条目，不做全市场盘中扫描。

### CANSLIM 快筛

`canslim_screen` 默认只依赖全市场股票池快照、全市场行情快照、财报缓存和必要的相对强度数据。它不把全 A 逐标的历史 K 线刷新作为前置条件；需要历史价格时，只对已通过前置过滤的标的按需补齐，或使用已累计的快照/历史缓存。

输出包括候选列表、评分拆解、过滤统计、manifest、trace 和 report。筛选结果只是研究队列，不自动形成买入结论。

### 单标的深研

`research company` 用于生成结构化投研报告，覆盖财务、商业模式、风险、估值口径和限制。报告正文必须能追溯到 run manifest 中的数据和来源。

### 因子研究

`factor run` 读取同一套 ResearchStore 数据，输出横截面、IC、分层收益、稳定性等可复核表格。正式因子结论必须链接 run manifest。

### 回测

`backtest run` 使用 ResearchStore 数据，通过 `RiskManager` 和 `EventLog`，输出净值、交易、归因、风险指标和事件日志。

## 投资体系

| 体系 | 方法论来源 | 持仓周期 | 止损方式 |
|------|-----------|---------|---------|
| Elder 技术交易 | 埃尔德《以交易为生》，三重滤网 | 天到周 | 价格止损（2%/6% 原则） |
| CANSLIM 成长股 | 欧奈尔《笑傲股市》，七维度基本面 | 周到月 | 初期价格止损，盈利后逻辑止损 |
| Value Investing | 巴菲特/格雷厄姆，护城河 + DCF/SOTP | 月到年 | 纯逻辑止损（买入理由失效才卖） |

三套体系账户层面和心理模型层面保持隔离。技术入场、成长验证、价值估算和止损逻辑不要混用。

## Artifact 边界

- `data/research/runs/`：recipe 的完整运行证据链，是新的默认事实源。
- `artifacts/research/`：只放单个标的最终深度研究报告。
- `artifacts/watchlist/`：自选池状态和逐标的追踪。
- `artifacts/journal/`：事件日志和交易审计数据，通常不入库。

历史批量扫描和旧日常产物已经退出当前事实源；需要查看历史时使用 git history。

## 开源协议

MIT License。欢迎 Issue 和 PR。
