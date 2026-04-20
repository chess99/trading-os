# Trading OS

A 股量化交易系统。事件驱动架构，策略代码在回测/模拟/实盘三个环境下完全一致。

## 代码架构

```
strategy/   策略基类 + Signal + 内置策略（MA、BH、RSI、AgentStrategy）
backtest/   事件驱动回测引擎，A 股规则（T+1、涨跌停、最小手数）
paper/      模拟交易引擎，与回测执行模型完全一致，含 EventLog 审计
risk/       量化风控守门人（单股上限、板块集中度、VaR、日亏损熔断）
data/       DataPipeline（前瞻偏差防护）+ LocalDataLake（DuckDB + Parquet）
journal/    EventLog（SQLite append-only 审计日志）
```

## 关键设计决策

- **策略一次写，三环境跑**：同一个 Strategy 子类在回测/模拟/实盘中不改代码
- **前瞻偏差防护**：`DataPipeline.get_bars(trading_date=T)` 严格只返回 T 之前的数据
- **A 股规则强制执行**：T+1 结算、涨跌停 ±10%、最小手数 100 股
- **风控是硬性门控**：每笔信号都必须通过 RiskManager，AI 不能绕过
- **AgentStrategy**：直接调用 Claude API，Pydantic 严格验证输出，支持磁盘缓存和确认/全自动两种模式

## 常用命令

```bash
# 获取 A 股数据
python -m trading_os fetch-bars --exchange SSE --ticker 600000 --start 2020-01-01 --adjustment qfq

# 回测
python -m trading_os backtest --symbols SSE:600000 --strategy ma --start 2022-01-01 --end 2024-12-31

# 模拟交易（确认模式）
python -m trading_os paper --symbols SSE:600000 --strategy ma

# 模拟交易（全自动）
python -m trading_os paper --symbols SSE:600000 --strategy agent --bypass-confirm

# Agent 单次分析
python -m trading_os agent --symbols SSE:600000 --date 2024-03-15
```

## 投资策略定位

**三套独立体系，账户层面隔离，各自独立迭代。**

| 体系 | 方法 | 持仓周期 | 止损方式 |
|------|------|---------|---------|
| Elder 技术交易 | 三重滤网（Elder） | 天到周 | 价格止损（2%/6%） |
| CANSLIM 成长股 | 基本面七维度（欧奈尔）+ 技术面确认 | 周到月 | 初期价格止损，盈利后逻辑止损 |
| Value Investing | 护城河 + DCF/SOTP 估值（巴菲特/格雷厄姆） | 月到年 | 纯逻辑止损 |

## Skills（`.claude/skills/`）

三套体系完全独立，各有子目录。意图不明确时先用 `trading-system` 导航。

**导航层**
| Skill | 触发词 |
|-------|-------|
| `trading-system` | "分析一下这只股票"、"帮我看看600000"、意图不明确时 |

**Elder 技术交易体系**（`.claude/skills/elder/`）
| Skill | 职责 |
|-------|------|
| `elder/elder-system` | 体系入口，三套流程（单标的/批量扫描/持仓管理） |
| `elder/elder-screen` | 三重滤网技术分析 |
| `elder/signal-scanner` | 技术面批量扫描 |
| `elder/position-sizer` | 2%/6% 原则仓位计算 |
| `elder/trade-executor` | 技术交易指令生成 |
| `elder/position-monitor` | 价格止损持仓监控（不处理逻辑止损） |
| `elder/trading-journal` | 技术交易记录 |
| `elder/backtest-review` | Elder 系统回测评估 |

**CANSLIM 成长股体系**（`.claude/skills/canslim/`）
| Skill | 职责 |
|-------|------|
| `canslim/canslim-system` | 体系入口，两套流程（单标的分析/持仓管理） |
| `canslim/canslim-screen` | CANSLIM 七维度基本面评分 |
| `canslim/fundamental-research` | 深度基本面研究（CANSLIM 视角） |
| `canslim/elder-confirm` | 技术面确认（elder-screen 裁剪版，只用第二三滤网） |
| `canslim/position-sizer` | 欧奈尔 7-8% 止损规则仓位计算 |
| `canslim/position-monitor` | 双模式止损（初期价格止损，盈利后逻辑止损） |
| `canslim/trade-executor` | 枢纽点买入指令生成 |
| `canslim/trading-journal` | 成长股交易记录（含 CANSLIM 评分准确性追踪） |

**Value Investing 体系**（`.claude/skills/value-investing/`）
| Skill | 职责 |
|-------|------|
| `value-investing/value-system` | 体系入口，两套流程（新标的研究/持仓监控） |
| `value-investing/fundamental-research` | 深度基本面研究（价值投资视角） |
| `value-investing/valuation` | 程序化估值（封装 `trading_os valuation` CLI） |
| `value-investing/position-monitor` | 纯逻辑止损（不检查价格，卖出唯一理由是逻辑失效） |

说"用 Elder 分析 600000"触发 Elder 体系，"CANSLIM 分析"触发 CANSLIM 体系，"估值分析"触发 Value Investing 体系。

## 参考资料

`vendor/` 存放 7 个参考开源项目（gitignored，用 `bash vendor/clone.sh` 恢复）。
`docs/research/` 存放对应的深度调研报告，关键结论：
- `TradingAgents`：BM25 离线记忆 + 多 Agent 辩论，Phase 4 候选
- `daily_stock_analysis`：6 层 Fallback 数据架构 + YAML 策略系统，值得借鉴
- `ai_quant_trade`：**警告**——RL 策略存在未来数据泄露，不可复制

## 规则

- 严禁使用模拟/假数据进行投资分析
- 所有交易决策必须写入 EventLog
- 风控检查不可绕过
- 回测数据层严格执行前瞻偏差防护
