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

## Skills (`.claude/skills/`)

基于《以交易为生》（Alexander Elder）提炼的交易决策 skills，与代码执行层互补：

| Skill | 职责 | 与代码的连接 |
|-------|------|-------------|
| `trading-system` | 编排入口，调度整个交易流程 | 调用所有子 skill |
| `elder-screen` | 三重滤网技术分析（周线+日线） | 从 `query-bars` 获取数据 |
| `signal-scanner` | 批量扫描候选标的池 | 输出供 `backtest` 验证 |
| `position-sizer` | 2%/6% 原则计算仓位 | 输出 `Signal.size` 值 |
| `trade-executor` | 生成具体交易指令 | 驱动 `paper` 命令执行 |
| `position-monitor` | 持仓监控，追踪止损 | 读取 EventLog 持仓状态 |
| `trading-journal` | 交易记录与绩效统计 | EventLog + BacktestResult |
| `backtest-review` | 系统回测健康评估 | 直接调用 `backtest` 命令 |

**使用方式**：直接说"帮我分析 600000"、"扫描今天的机会"、"算一下仓位"等，对应 skill 自动触发。

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
