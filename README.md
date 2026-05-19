# Trading OS

A 股 AI 辅助研究工具集。事件驱动回测引擎 + Claude Code Skills 驱动的三套独立分析体系。

---

## 这是什么

Trading OS 是一个以 **AI Agent 为主要操作界面** 的 A 股研究工具集。不同于传统量化框架靠人手动跑脚本，这里的分析流程由 Claude Code 中的 Skill 驱动——你对 AI 说"用 Elder 分析 600000"，它会按照完整的三重滤网流程执行分析、调用底层数据命令、生成结构化结论。

**当前状态**：研究和分析工具已基本完善，回测引擎可用，实盘接口尚未接入券商 API。更准确的描述是"AI 驱动的 A 股研究工作台"，而非完整的自动交易系统。

---

## 核心设计决策

**策略与回测是一个闭环，不是两个独立系统。** AI 的分析建议必须能在回测引擎里经历史数据验证，验证通过才有资格进入模拟/实盘执行。这是与其他"AI 分析 + 独立回测"项目最根本的架构差异。

**前瞻偏差防护是内置的，无法绕过。** `DataPipeline.get_bars(as_of=T)` 在接口层面强制只返回 T 之前的数据，策略代码无需自己做日期过滤，也无法意外引入未来数据。

**风控是硬性门控，AI 无法绕过。** 回测与模拟交易都会在下单前通过 `RiskManager`（单股上限、板块集中度、VaR、日亏损熔断）。AI 说"买"，但 VaR 超限，就不买。

**三套投资体系账户层面完全隔离。** Elder 技术交易、CANSLIM 成长股、价值投资三套体系使用互相矛盾的心理模型和止损逻辑，混用会互相干扰。每套体系有自己完整的 Skill 链，不共享止损决策。

---

## 三套投资体系

| 体系 | 方法论来源 | 持仓周期 | 止损方式 |
|------|-----------|---------|---------|
| Elder 技术交易 | 埃尔德《以交易为生》，三重滤网 | 天到周 | 价格止损（2%/6% 原则） |
| CANSLIM 成长股 | 欧奈尔《笑傲股市》，七维度基本面 | 周到月 | 初期价格止损，盈利后逻辑止损 |
| Value Investing | 巴菲特/格雷厄姆，护城河 + DCF/SOTP | 月到年 | 纯逻辑止损（买入理由失效才卖） |

每套体系都有完整的 Skill 链：从全 A 股批量扫描（Python CLI）到候选池管理，再到 AI 深度分析、仓位计算和交易指令生成。

---

## 代码架构

```
src/trading_os/
  strategy/   策略基类 + Signal + 内置策略（MA、BH、RSI、AgentStrategy）
  backtest/   事件驱动回测引擎（T+1、涨跌停 ±10%/±20%、最小手数 100 股）
  paper/      模拟交易引擎，与回测执行模型完全一致，含 EventLog 审计
  risk/       量化风控守门人（单股上限、板块集中度、VaR、日亏损熔断）
  data/       DataPipeline（前瞻偏差防护）+ LocalDataLake（DuckDB + Parquet）
  scan/       三套体系的全 A 股批量筛选（Elder/CANSLIM/Value）
  journal/    EventLog（SQLite append-only 审计日志）

.claude/skills/   AI Agent 决策层，三套体系完全独立
artifacts/
  research/   分析报告存档（git 追踪）
  scan/       批量扫描输出 JSON（gitignored）
  watchlist/  自选池状态（pool.json + 逐标的追踪日志）
```

技术选型：DuckDB + Parquet 存行情，SQLite 存账户/日志，直接调用 Claude API（不走 LangChain），Pydantic v2 严格验证 AI 输出，AKShare/BaoStock 数据源。

---

## AI Agent 集成方式

`AgentStrategy` 是一个标准 `Strategy` 子类，`generate_signals()` 内部调用 Claude API 分析市场上下文，输出经 Pydantic 严格验证的结构化信号。连续验证失败时自动退化为 HOLD，不会因 LLM 输出格式错误而下错单。

支持两种模式：
- **确认模式（默认）**：显示 AI 分析结果，等待人工确认后执行
- **全自动模式**（`--bypass-confirm`）：无人值守运行，类似 Claude Code 的 bypassPermissions

日常研究工作流不通过 `AgentStrategy` 运行，而是通过 `.claude/skills/` 里的 Skill——由 Claude Code 调用 `python -m trading_os` 子命令获取数据，AI 在此基础上做判断。两者有明确的分工边界：确定性计算归 Python，模糊判断归 AI。

---

## 快速开始

```bash
git clone https://github.com/chess99/trading-os
cd trading-os
pip install -e ".[data_ashare,agent]"

# 拉取 A 股历史数据
python -m trading_os fetch-ak-bulk --start 2022-01-01

# 回测 Elder 策略
python -m trading_os backtest --symbols SSE:600000 --strategy elder --start 2022-01-01

# CANSLIM 全 A 股扫描
python -m trading_os scan-canslim --date 2024-03-15

# Value 扫描：默认实时估值快照（不可严格回放）
python -m trading_os scan-value --date 2024-03-15 --mode live

# Value 扫描：历史快照模式（需提前准备 data/valuation_snapshots/YYYY-MM-DD.json）
python -m trading_os scan-value --date 2024-03-15 --mode historical

# 在 Claude Code 中触发日常工作流
# 说："跑日常工作流"
```

需要 `ANTHROPIC_API_KEY`。

---

## 与同类项目的区别

大多数"AI + 量化"项目把 AI 分析和回测引擎建成两套独立系统，AI 的建议无法在历史数据上验证。Trading OS 的设计目标是让两者成为一个闭环：AI 生成策略参数 → 回测引擎历史验证 → 通过验证才进入模拟/实盘。

操作界面是 AI Agent，不是 UI 或命令行。这意味着分析流程可以根据上下文动态调整，而不是固定在几个预设按钮里。

---

## 开源协议

MIT License。欢迎 Issue 和 PR。
