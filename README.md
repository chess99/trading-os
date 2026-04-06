# Trading OS

A-share quantitative trading system. Event-driven architecture, unified Strategy interface across backtest / paper / live.

## Quick Start

```bash
pip install -e ".[data_lake]"

# Fetch A-share data
python -m trading_os fetch-ak --exchange SSE --ticker 600000 --start 2020-01-01 --adjustment qfq

# Run backtest
python -m trading_os backtest --symbols SSE:600000 --strategy ma --start 2022-01-01 --end 2024-12-31

# Paper trading
python -m trading_os paper --symbols SSE:600000 --strategy ma

# Agent analysis (requires ANTHROPIC_API_KEY)
python -m trading_os agent --symbols SSE:600000 --date 2024-03-15
```

## Architecture

```
strategy/     Strategy base + Signal + MA / BH / RSI / AgentStrategy
backtest/     Event-driven BacktestRunner — A-share rules (T+1, ±10% limits, 100-share lots)
paper/        PaperRunner — same execution model, with EventLog audit trail
risk/         RiskManager — position limits, sector concentration, VaR, circuit breaker
data/         DataPipeline (look-ahead bias protection) + LocalDataLake (DuckDB + Parquet)
journal/      EventLog — SQLite append-only audit log
```

## Commands

| Command | Description |
|---------|-------------|
| `fetch-ak` | Fetch A-share daily bars from AKShare |
| `fetch-yf` | Fetch bars from yfinance (US/HK) |
| `seed` | Seed synthetic bars for offline testing |
| `query-bars` | Query the local data lake |
| `backtest` | Run backtest with A-share rules |
| `paper` | Paper trading (confirm or `--bypass-confirm` auto) |
| `agent` | One-shot Claude agent analysis |
| `lake-init` | Initialize DuckDB/Parquet data lake |

## Strategies

| Flag | Class | Logic |
|------|-------|-------|
| `ma` | `MACrossStrategy` | MA5/MA20 golden/death cross |
| `bh` | `BuyAndHoldStrategy` | Buy-and-hold benchmark |
| `rsi` | `RSIStrategy` | RSI(14) mean reversion |
| `agent` | `AgentStrategy` | Claude API analysis, Pydantic-validated output |

## A-Share Rules Enforced

- **T+1 settlement**: shares bought on day T cannot be sold until T+1
- **Price limits**: ±10% daily (±5% for ST stocks, ±20% for STAR/ChiNext)
- **Lot size**: orders rounded down to nearest 100 shares
- **Fees**: 0.03% commission (min ¥5) + 0.05% stamp duty on sells

## Data

Local DuckDB + Parquet lake under `data/`. Default adjustment: QFQ (前复权).

Data source priority (A-share):
1. AKShare (free, default)
2. Tushare Pro (`TUSHARE_TOKEN` env var)
3. BaoStock (free, historical)
4. Local cache (offline)

## Vendor Reference

`vendor/` contains 7 cloned open-source repos for reference. See `docs/research/` for analysis.
To restore: `bash vendor/clone.sh`

## Docs

- `docs/plans/system-design-v2.md` — system architecture design
- `docs/research/` — competitive analysis of 7 open-source quant systems
