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
