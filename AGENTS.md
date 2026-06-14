# Trading OS Agent 指南

这个仓库主要由 Claude Code / Codex 这类 agent 操作。`AGENTS.md` 是仓库级 agent 行为的唯一事实源。

根目录 `CLAUDE.md` 应该是指向 `AGENTS.md` 的软链，方便 Claude Code 读取同一份内容。不要再维护 `.claude/CLAUDE.md` 或 `.agents/agents.md`。

Skill 的真实目录是根目录 `skills/`。兼容路径 `.claude/skills` 和 `.agents/skills` 只保留指向根目录 `skills/` 的软链；不要在多个目录维护重复 skill。

## 系统定位

Trading OS 是 agent-native 投研和量化研究平台，不是固定 daily 脚本集合。

底层基建负责确定性能力：

- `ResearchStore`：本地研究数据、缓存、证据链和 run artifacts。
- `DataHub`：唯一数据入口，负责 cache-first、refresh、offline、lazy-fill 策略。
- `research recipe`：可复用的筛选、深研、因子研究、回测、日报研究工作流。
- `RiskManager`：交易和回测的硬风控门控。
- `EventLog`：交易、回测、模拟执行的 append-only 审计日志。

Agent 负责：

- 理解用户意图。
- 选择合适的 recipe。
- 解释 manifest / trace / report。
- 在缺数据或口径受限时说明限制，不编造。

Agent 不应该每次临场拼接底层脚本，也不应该绕过 DataHub 直接读写数据源。

## 代码架构

```
src/trading_os/
  research/      ResearchStore、DataHub、research recipes、research CLI
  strategy/      策略基类 + Signal + 内置策略
  backtest/      事件驱动回测引擎，包含 A 股规则
  paper/         模拟交易引擎，带 EventLog 审计
  risk/          硬性风控门控
  data/          轻量 schema 和 ResearchStore 所需数据源 adapter
  journal/       SQLite append-only 事件日志

skills/          Agent 工作流说明
data/research/
  runs/          每次 recipe 运行的 manifest、trace、tables、charts、report
artifacts/
  research/      单标的最终深度研究报告，git 追踪
  watchlist/     自选池状态和逐标的追踪
```

关键设计约束：

- 所有正式投资分析必须使用真实数据，禁止模拟数据或假数据。
- 所有数据访问优先通过 `DataHub` 和 `ResearchStore`，不要直接读取 parquet。
- `as_of` 是研究视角日期；查询和报告不得使用 `as_of` 之后的数据。
- 风控是硬门控，AI 建议不能绕过 `RiskManager`。
- 所有交易决策必须能通过 `EventLog` 或 run manifest 追责。
- Elder、CANSLIM、Value Investing 是三套独立体系，心理模型、入场逻辑、止损逻辑不要混用。

## 常用命令

```bash
# 数据缓存和状态
python -m trading_os data status
python -m trading_os data refresh universe --as-of YYYY-MM-DD --end YYYY-MM-DD
python -m trading_os data refresh quotes --as-of YYYY-MM-DD --end YYYY-MM-DD
python -m trading_os data refresh bars --symbols SSE:600660 --start 2020-01-01 --end YYYY-MM-DD

# CANSLIM 快筛
python -m trading_os research run canslim_screen --as-of YYYY-MM-DD --top 30

# 单标的深度研究
python -m trading_os research company SSE:600660 --template quality_growth --as-of YYYY-MM-DD

# Daily CANSLIM 收口
python -m trading_os research daily-canslim --as-of YYYY-MM-DD

# 观察池盘中提醒
python -m trading_os alert monitor --mode watchlist --once
python -m trading_os alert monitor --mode watchlist --once --notify webhook --webhook-url URL --notify-attempts 3

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

最终回答用户时，优先引用 `manifest.json` 和 `report.md` 路径，并说明关键数据口径。

## ResearchStore 和 DataHub

`ResearchStore` 保存研究数据集：

- `universe_snapshot`：股票池、名称、上市状态、ST/退市状态。
- `quote_snapshot`：全市场日行情快照。
- `bars`：历史 OHLCV，按需补齐。
- `fundamentals`：财务指标和报表摘要。
- `estimates`：一致预期、估值快照、目标价等。
- `news`：新闻、公告、事件。
- `segments`：主营构成、产品/地区分部。
- `institutional`：股东和机构持仓线索。
- `peers`：同业和行业比较样本。
- `guidance`：管理层指引、订单、产能、产品周期等催化线索。
- `factors`：因子横截面和历史结果。
- `run_manifest`：每次研究运行的输入、数据版本、步骤和输出路径。

`DataHub` 支持四种数据策略：

- `cache_first`：默认，缓存足够新就不联网。
- `refresh`：强制刷新指定数据集。
- `offline`：只读本地缓存，缺数据则明确失败。
- `lazy_fill`：缺什么补什么，只补当前任务需要的标的。

CANSLIM 快筛不应触发全市场逐标的历史 K 线刷新。需要历史价格时，只对已通过前置过滤的标的懒补齐，或使用已累计的 quote/bars 缓存计算相对强度。

### Provider 路线

数据源选择以 `docs/research/canslim-daily-system-vendor-data-source-review.md`
为准。当前 DataHub 默认读取 `TRADING_OS_PROVIDER_ORDER`，未设置时按
`tushare,akshare` 解析；只有配置了 `TUSHARE_TOKEN` 才会启用 Tushare，否则回落到
AkShare：

- `TushareResearchProvider` 已作为第一阶段 A 股 provider，用于股票池、日行情、
  复权日线、财务指标、主营构成、机构持仓线索和同业样本；新闻公告和管理层指引
  仍需后续 provider 能力补齐。
- 生产级目标是 `RqdataResearchProvider`，尤其用于 point-in-time 财务、因子研究和
  回测；JQData 是付费替代选项。
- AkShare 只作为免费 fallback 和探索源，不应作为正式交易建议或回测证明的唯一事实源。
- Provider 失败、降级和缺失能力必须写入 manifest/provider health，并影响报告置信度。

## Workflow 指引

### Daily CANSLIM Closure

使用：

```bash
python -m trading_os research daily-canslim --as-of YYYY-MM-DD
```

该 workflow 会解析最近一个已完成交易日，运行全 A CANSLIM 快筛，对每一个
`strict_canslim_candidate` 执行深研，写入决策，更新
`artifacts/watchlist/state.json`，并生成
`artifacts/research/daily-canslim-YYYYMMDD.md`。

`--top` 只限制展示结果，绝不能限制下游 strict 候选处理。workflow 不能在写完
run manifest 后停止，必须完成决策、观察池更新和人类可读日报。

### Watchlist Alert Monitor

使用：

```bash
python -m trading_os alert monitor --mode watchlist --once
```

观察池盘中提醒只评估机器可读的 `artifacts/watchlist/state.json` 条目，不做全市场盘中扫描。
需要真实发送时使用 `--notify webhook|feishu|dingtalk|telegram|system`；
飞书/钉钉走 `--webhook-url` 或对应环境变量，Telegram 走
`--telegram-bot-token` / `--telegram-chat-id` 或对应环境变量。投递结果必须写入
ResearchStore alert deliveries 和 EventLog，不能只生成本地 alert 后声称已通知。

### CANSLIM 快筛

使用：

```bash
python -m trading_os research run canslim_screen --as-of YYYY-MM-DD --top 30
```

输出候选列表、评分拆解、过滤统计、manifest、trace 和 report。`--top` 只是 report
和 `tables/candidates.csv` 的展示上限；实际全量候选必须以 manifest 中的
`candidates_total`、`strict_candidates_total`、`provisional_candidates_total` 和
`tables/all_candidates.csv` 为准。

扫描结果只是研究队列，不自动形成买入结论。扫描后的默认动作是：

- 对全部 `strict_canslim_candidate` 生成 CANSLIM 深研队列，不要任意只取 top 3。
- `provisional_research_queue` 只在缺失字段补齐、或用户明确要求扩大覆盖时继续深研。
- 深研完成后必须在 `artifacts/research/` 生成一份人类可读的完整复核报告，不能只把
  `data/research/runs/...` 或 run manifest 路径甩给用户，也不能留下“后续再补”的维度后停止。
- 完整复核报告必须列出全量候选数、strict/provisional 数、全部 strict 标的、单标的报告路径、近 12 个月公告/事件、管理层指引/订单/产能/产品线索、机构持仓、主营构成、同业拥挤度、base/pivot/突破放量技术确认、数据限制和下一步队列。
- 如果某个外部数据源真实失败，报告必须列明失败接口、失败原因、已使用的替代口径和对结论置信度的影响；不得把缺口写成待办后直接结束。
- 完整复核完成后再进入 watchlist、回测或风控流程。
- 最终回答必须说明“全量候选数”和“展示候选数”的区别。

### 单标的深研

使用：

```bash
python -m trading_os research company SSE:600660 --template quality_growth --as-of YYYY-MM-DD
```

报告必须覆盖数据来源、关键财务、商业模式、风险、估值口径和限制。缺失数据要写清楚，不得用模拟值补。

### 因子研究

使用：

```bash
python -m trading_os factor run momentum_roe --as-of YYYY-MM-DD
```

因子研究应输出横截面、IC/分层收益等可复核表格。正式因子结果必须链接 run manifest。

### 回测

使用：

```bash
python -m trading_os backtest run strategy_name --start YYYY-MM-DD --end YYYY-MM-DD
```

回测必须经过 `RiskManager` 和 `EventLog`，并写入 run artifacts。

## Artifacts

产物边界：

- `data/research/runs/`：recipe 的完整运行证据链，是默认产物目录。
- `artifacts/research/`：放人类可读的研究汇总、单标的最终深度研究报告。
- `artifacts/watchlist/`：自选池状态和逐标的追踪。
- `artifacts/journal/`：事件日志和交易审计数据，通常不入库。

旧日常产物和旧批量扫描产物已经退出当前事实源；需要查看历史时使用 git history，不要把旧文件当作新的研究输入。

单标的深度研究报告命名：

- Value：`value-{EXCHANGE}{TICKER}-YYYYMMDD.md`
- CANSLIM：`canslim-{EXCHANGE}{TICKER}-YYYYMMDD.md`
- Elder：`elder-{EXCHANGE}{TICKER}-YYYYMMDD.md`
- 通用质量成长：`quality_growth-{EXCHANGE}{TICKER}-YYYYMMDD.md`

## 基本规则

- 每次 agent 完成一次实现迭代后，应自行提交自己产生的变更，不需要等待用户单独要求。
- 提交前必须确认未提交内容只包含本 agent 本轮产生的变更；不要 stage、修改或回滚用户/其他 agent 的无关变更。
- 投资分析严禁使用模拟数据或假数据。
- 测试可以使用 synthetic fixtures，但正式 recipe 必须标记真实数据来源。
- 所有交易决策必须能通过 EventLog 或 run manifest 追责。
- 不要绕过风控检查。
- 工作流语义变更时，只维护根目录 `AGENTS.md` 和相关根目录 `skills/` 文件。
