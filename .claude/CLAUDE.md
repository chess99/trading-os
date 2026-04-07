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
python -m trading_os fetch-ak --exchange SSE --ticker 600000 --start 2020-01-01 --adjustment qfq

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

**量化因子选股 + AI 增强研究 + 技术面择时**

不做纯量化（alpha 衰减快，同质化严重），不做纯主观（缺乏行业深度积累）。
比较优势在于用 LLM 大规模处理非结构化信息（研报、财报、电话会议纪要），结合技术面择时，形成差异化的分析链。

三层分析链：
```
研究层  fundamental-research（内在价值估算）+ canslim-screen（成长特征快速筛选）
择时层  elder-screen（三重滤网，确认买卖点）
执行层  position-sizer（仓位）+ trade-executor（指令）
```

止损的两种模式：
- 技术面持仓（短中线）：价格止损，Elder 2%/6% 原则
- 基本面持仓（中长线）：逻辑止损，买入理由不再成立时卖出，与价格无关

## Skills（`.claude/skills/`）

交易决策 skills，与代码执行层互补，按用途分四层：

**编排层**
| Skill | 职责 |
|-------|------|
| `trading-system` | 入口，识别意图，调度基本面/技术面/综合三条流程 |

**选股层**（什么值得关注）
| Skill | 职责 | 知识来源 |
|-------|------|---------|
| `fundamental-research` | 深度基本面研究，估算内在价值，建立逻辑止损条件 | 巴菲特/芒格/格雷厄姆 |
| `canslim-screen` | CANSLIM 七维度快速基本面评分（10 分钟） | 欧奈尔《笑傲股市》 |
| `signal-scanner` | 技术面批量扫描候选标的池 | Elder《以交易为生》 |

**分析层**（深度分析单标的）
| Skill | 职责 | 知识来源 |
|-------|------|---------|
| `elder-screen` | 三重滤网技术分析（周线趋势 + 日线时机） | Elder《以交易为生》 |

**执行层**（怎么买卖）
| Skill | 职责 |
|-------|------|
| `position-sizer` | 2%/6% 原则计算仓位，输出 `Signal.size` |
| `trade-executor` | 生成具体交易指令，驱动 `paper` 命令执行 |
| `position-monitor` | 持仓监控，支持价格止损和逻辑止损两种模式 |

**复盘层**（回顾改进）
| Skill | 职责 |
|-------|------|
| `trading-journal` | 交易记录与绩效统计 |
| `backtest-review` | 系统回测健康评估，直接调用 `backtest` 命令 |

说"帮我分析 600000"、"这家公司值多少钱"、"扫描今天的机会"等，对应 skill 自动触发。

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
