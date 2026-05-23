# Trading OS Agent 指南

这个仓库主要由 Claude Code / Codex 这类 agent 操作。`AGENTS.md` 是仓库级 agent 行为的唯一事实源。

根目录 `CLAUDE.md` 应该是指向 `AGENTS.md` 的软链，方便 Claude Code 读取同一份内容。不要再维护 `.claude/CLAUDE.md` 或 `.agents/agents.md`。

Skill 的真实目录是根目录 `skills/`。兼容路径 `.claude/skills` 和 `.agents/skills` 只保留指向根目录 `skills/` 的软链；不要在多个目录维护重复 skill。

## 代码架构

```
src/trading_os/
  strategy/      策略基类 + Signal + 内置策略
  backtest/      事件驱动回测引擎，包含 A 股规则
  paper/         模拟交易引擎，带 EventLog 审计
  risk/          硬性风控门控
  data/          DataPipeline 前瞻偏差防护 + LocalDataLake
  scan/          Elder / CANSLIM / Value 扫描器
  scheduler.py   日常数据更新、扫描、日报门控
  journal/       SQLite append-only 事件日志

skills/          Agent 工作流说明
artifacts/
  research/      单标的最终深度研究报告，git 追踪
  scan/          扫描 JSON 快照 + 同名人工解读 Markdown，git 追踪正式快照
  watchlist/     自选池状态和逐标的追踪
```

关键设计约束：

- 策略代码要能在回测、模拟、未来实盘中复用。
- `DataPipeline` 负责前瞻偏差防护，不要绕过。
- 风控是硬门控，AI 建议不能绕过 `RiskManager`。
- Elder、CANSLIM、Value Investing 是三套独立体系，心理模型、入场逻辑、止损逻辑不要混用。

## Daily 工作流

Daily 由 scheduler 驱动，不是 agent 手工串联脚本。默认 daily 是 CANSLIM 日常流程：数据刷新、CANSLIM 全量扫描、深研队列和自选池闭环。不要为了生成日报直接拼接 `fetch-ak-bulk`、`scan-canslim`、`pool status`。

Elder 不作为 daily 默认扫描任务。Elder 扫描是宽口径技术信号，只有在明确要做技术交易机会筛选时才专项运行；不要把未深研、未入池的 Elder 扫描结果塞进 daily。

默认路径：

```bash
python -m trading_os scheduler status
python -m trading_os scheduler jobs --limit 20
python -m trading_os daily
```

如果 `daily` 生成 blocked 报告（临时路径 `artifacts/daily/tmp/YYYYMMDD-blocked.md`），停在这里。只报告阻塞原因、缺失 job、effective date、相关进度文件，不要从不完整数据推导大盘、个股、入场、退出、自选池进出结论。

完成态有两个 daily 产物：

- `artifacts/daily/YYYYMMDD-summary.md`：scheduler 本地机器回执，只证明同日数据刷新、扫描和 pool 同步完成；gitignored，不作为正式日报快照入库。
- `artifacts/daily/YYYYMMDD.md`：agent 基于完成态 summary、同日 scan、watchlist/pool 和 tracking 文件生成的人读深度日报。

如果用户要“日报”“深度日报”“今天市场怎样”，不能只交付 `*-summary.md`；在 scheduler 完成态后必须补写或更新 `YYYYMMDD.md`。

手工触发只用于诊断或修复：

```bash
python -m trading_os scheduler trigger market_data_probe
python -m trading_os scheduler trigger market_data_bulk_refresh --effective-date YYYY-MM-DD
python -m trading_os scheduler trigger full_scan_and_daily --effective-date YYYY-MM-DD
```

`python -m trading_os scheduler run` 是长驻服务入口。启动前先看 `scheduler status`，避免重复启动 scheduler。

## 日期语义

`daily` 默认使用当前应交付的 effective date：收盘前是上一交易日，收盘后是当日。如果该日依赖未完成，必须输出 blocked，而不是回退到更早的完成态日报。

扫描命令的 `--date` 是 signal date。`DataPipeline` 会排除同日 K 线以防前瞻偏差，所以 scheduler 会负责把 effective date 转成正确的 signal date。跑 daily 时不要绕过这个转换。

## 常用命令

```bash
# 单标的 A 股数据
python -m trading_os fetch-bars --exchange SSE --ticker 600000 --start 2020-01-01 --adjustment qfq

# Scheduler 状态和日报
python -m trading_os scheduler status
python -m trading_os daily

# 回测
python -m trading_os backtest --symbols SSE:600000 --strategy elder --start 2022-01-01

# 模拟交易
python -m trading_os paper --symbols SSE:600000 --strategy ma

# Agent 单次分析
python -m trading_os agent --symbols SSE:600000 --date 2024-03-15

# CANSLIM 扫描（诊断/专项分析用，不是标准 daily 入口）
python -m trading_os scan-canslim --date 2024-03-15
python -m trading_os scan-canslim --live --date 2024-03-15
```

## Skills

Agent 工作流说明放在根目录 `skills/`。Daily 的事实源是：

- `skills/daily-workflow/SKILL.md`

体系入口：

- `trading-system`：意图不明确时导航。
- `elder-system`：Elder 技术交易体系入口。
- `canslim-system`：CANSLIM 成长股体系入口。
- `value-system`：价值投资体系入口。

支撑 skill 仍然按体系隔离。不要把 Elder 的价格止损、CANSLIM 的双模式止损、Value 的逻辑止损混在一起。

## 数据访问

严禁在 agent 工作流中直接读取 parquet 文件，包括 `read_parquet`、`pd.read_parquet`、`duckdb.read_parquet`。

必须通过：

- `LocalDataLake` API，例如 `lake.query_bars()`
- `python -m trading_os` CLI

原因：直接读 parquet 会绕过 compact/dedup 层，可能读到重复行或脏数据，也可能绕过前瞻偏差防护。

如果要修改或修复数据，至少用两个独立来源交叉验证。历史上出现过直接读 parquet 误判 volume 单位、险些错误改写 SZSE compacted parquet 的事故。

## Artifacts

```
artifacts/
  research/      单标的最终深度研究报告，git 追踪
  scan/          扫描 JSON 快照 + 同名人工解读 Markdown，git 追踪正式快照
  journal/       EventLog SQLite 数据，gitignored
  agent_cache/   AgentStrategy 推理缓存，gitignored
```

产物边界：

- `artifacts/daily/`：每日状态、当日 TODO、后续处理闭环和最终研究报告链接。`YYYYMMDD-summary.md` 是 gitignored 的本地机器回执，`YYYYMMDD.md` 是入库的人读深度日报；不要额外创建 daily follow-up 中间文件。
- `artifacts/daily/tmp/`：blocked 日报等临时诊断产物，gitignored，不作为正式日报快照入库。
- `artifacts/scan/`：正式扫描快照，包含 `{system}-YYYYMMDD.json` 和可选同名 `{system}-YYYYMMDD.md` 人工解读。临时诊断扫描放 `artifacts/scan/tmp/`，不入库。
- `artifacts/research/`：只放单个标的的最终深度研究报告，不放日报拆解、扫描解读、临时笔记、批量候选清单。

单标的深度研究报告命名：

- Value：`value-{EXCHANGE}{TICKER}-YYYYMMDD.md`
- CANSLIM：`canslim-{EXCHANGE}{TICKER}-YYYYMMDD.md`
- Elder：`elder-{EXCHANGE}{TICKER}-YYYYMMDD.md`

完成一次包含结论和行动计划的单标的深度研究后，存到 `artifacts/research/`。如果研究来自 daily TODO，应在对应 `artifacts/daily/YYYYMMDD.md` 记录完成状态并链接最终研究报告。

## 基本规则

- 投资分析严禁使用模拟数据或假数据。
- 所有交易决策必须能通过 EventLog 追责。
- 不要绕过风控检查。
- 工作流语义变更时，只维护根目录 `AGENTS.md` 和相关根目录 `skills/` 文件。
