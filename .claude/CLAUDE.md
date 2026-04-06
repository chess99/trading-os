# Trading OS

A-share quantitative trading system. Event-driven architecture with unified Strategy interface across backtest / paper / live.

## Architecture

```
strategy/       — Strategy base class + Signal + built-in strategies (MA, BH, RSI, Agent)
backtest/       — Event-driven BacktestRunner (A-share rules: T+1, price limits, lot size)
paper/          — PaperRunner (same execution model as backtest, with EventLog)
risk/           — RiskManager (position limits, sector limits, VaR, circuit breaker)
data/           — DataPipeline (look-ahead bias protection) + LocalDataLake (DuckDB+Parquet)
journal/        — EventLog (SQLite append-only audit log)
```

## Key Design Decisions

- **Strategy once, three environments**: same Strategy subclass runs in backtest/paper/live
- **as_of protection**: `DataPipeline.get_bars(trading_date=T)` strictly returns data < T
- **A-share rules enforced**: T+1 settlement, ±10% price limits, 100-share lot size
- **Risk is a hard gate**: RiskManager runs before every order, AI cannot bypass it
- **AgentStrategy**: Claude API native, Pydantic output validation, disk cache, confirm/auto mode

## CLI

```bash
# Fetch A-share data
python -m trading_os fetch-ak --exchange SSE --ticker 600000 --start 2020-01-01 --adjustment qfq

# Backtest
python -m trading_os backtest --symbols SSE:600000 --strategy ma --start 2022-01-01 --end 2024-12-31

# Paper trading (confirm mode)
python -m trading_os paper --symbols SSE:600000 --strategy ma

# Paper trading (full auto)
python -m trading_os paper --symbols SSE:600000 --strategy agent --bypass-confirm

# Agent one-shot analysis
python -m trading_os agent --symbols SSE:600000 --date 2024-03-15
```

## Strategies

| Name | Class | Description |
|------|-------|-------------|
| `ma` | `MACrossStrategy` | MA5/MA20 golden/death cross |
| `bh` | `BuyAndHoldStrategy` | Buy and hold benchmark |
| `rsi` | `RSIStrategy` | RSI mean reversion |
| `agent` | `AgentStrategy` | Claude API analysis |

## Data Sources (A-share priority)

1. AKShare (free, East Money) — default
2. Tushare Pro (paid, most stable) — set TUSHARE_TOKEN env var
3. BaoStock (free, historical)
4. Local cache (DuckDB, offline)

## Investment Strategy

**定位：量化因子选股 + AI 增强研究 + 技术面择时**

不做纯量化（alpha 衰减快，同质化严重），不做纯主观（缺乏行业深度积累）。
比较优势在于：用 LLM 大规模处理非结构化信息（研报、财报、电话会议），
结合技术面择时，形成差异化的分析链。

**分析链（三层）：**
```
1. 研究层：fundamental-research（内在价值估算，AI 研究员模式）
           canslim-screen（快速基本面筛选，成长特征）
2. 择时层：elder-screen（三重滤网，确认买卖点）
3. 执行层：position-sizer + trade-executor（仓位 + 指令）
```

**止损逻辑的两种模式：**
- 技术面持仓（短中线）：价格止损，Elder 的 2%/6% 原则
- 基本面持仓（中长线）：逻辑止损，买入理由不再成立时卖出，与价格无关

## Skills (`.claude/skills/`)

交易决策 skills，与代码执行层互补。按用途分层：

**编排层**
| Skill | 职责 |
|-------|------|
| `trading-system` | 入口，识别意图，调度三条分析流程（基本面优先/技术面优先/综合） |

**选股层**（什么值得关注）
| Skill | 职责 | 来源 |
|-------|------|------|
| `fundamental-research` | 深度基本面研究，估算内在价值，逻辑止损框架 | 巴菲特/芒格/格雷厄姆 |
| `canslim-screen` | CANSLIM 七维度快速基本面评分 | 欧奈尔《笑傲股市》 |
| `signal-scanner` | 技术面批量扫描 | Elder《以交易为生》 |

**分析层**（深度分析单标的）
| Skill | 职责 | 来源 |
|-------|------|------|
| `elder-screen` | 三重滤网技术分析（周线+日线） | Elder《以交易为生》 |

**执行层**（怎么买卖）
| Skill | 职责 |
|-------|------|
| `position-sizer` | 2%/6% 原则计算仓位，输出 `Signal.size` |
| `trade-executor` | 生成具体交易指令，驱动 `paper` 命令 |
| `position-monitor` | 持仓监控，追踪止损（价格止损/逻辑止损两种模式） |

**复盘层**（回顾改进）
| Skill | 职责 |
|-------|------|
| `trading-journal` | 交易记录与绩效统计 |
| `backtest-review` | 系统回测健康评估，调用 `backtest` 命令 |

**使用方式**：直接说"帮我分析 600000"、"这家公司值多少钱"、"扫描今天的机会"等，对应 skill 自动触发。

## Vendor Research

`vendor/` contains cloned repos for reference. Key findings in `docs/research/`:
- `TradingAgents` — BM25 memory + multi-agent debate (Phase 4 candidate)
- `daily_stock_analysis` — 6-layer data fallback + YAML strategy system
- `ai_quant_trade` — WARNING: RL uses future data leakage, do not copy RL code

## Rules

- No simulated/fake data in production analysis
- All trading decisions must be logged to EventLog
- Risk checks cannot be bypassed
- Backtest data strictly enforces look-ahead bias protection
- `vendor/` is gitignored, use it freely for reference
