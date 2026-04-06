# Trading OS

A 股量化交易系统。事件驱动架构，策略代码在回测/模拟/实盘三个环境下完全一致。

## 快速开始

```bash
pip install -e ".[data_lake]"

# 获取 A 股数据
python -m trading_os fetch-ak --exchange SSE --ticker 600000 --start 2020-01-01 --adjustment qfq

# 回测
python -m trading_os backtest --symbols SSE:600000 --strategy ma --start 2022-01-01 --end 2024-12-31

# 模拟交易（确认模式）
python -m trading_os paper --symbols SSE:600000 --strategy ma

# Agent 分析（需要 ANTHROPIC_API_KEY）
python -m trading_os agent --symbols SSE:600000 --date 2024-03-15
```

## 架构

```
strategy/   策略基类 + Signal + MA / BH / RSI / AgentStrategy
backtest/   事件驱动回测引擎，A 股规则（T+1、涨跌停、最小手数）
paper/      模拟交易引擎，与回测执行模型完全一致，含 EventLog 审计
risk/       量化风控（单股上限、板块集中度、VaR、日亏损熔断）
data/       DataPipeline（前瞻偏差防护）+ LocalDataLake（DuckDB + Parquet）
journal/    EventLog（SQLite append-only 审计日志）
```

## 命令

| 命令 | 说明 |
|------|------|
| `fetch-ak` | 从 AKShare 获取 A 股日线数据 |
| `fetch-yf` | 从 yfinance 获取港美股数据 |
| `seed` | 生成合成数据（离线测试用） |
| `query-bars` | 查询本地数据湖 |
| `backtest` | 运行回测（含 A 股规则） |
| `paper` | 模拟交易（`--bypass-confirm` 全自动） |
| `agent` | Claude Agent 单次分析 |
| `lake-init` | 初始化 DuckDB/Parquet 数据湖 |

## 内置策略

| 参数 | 类 | 逻辑 |
|------|-----|------|
| `ma` | `MACrossStrategy` | MA5/MA20 金叉死叉 |
| `bh` | `BuyAndHoldStrategy` | 买入持有基准 |
| `rsi` | `RSIStrategy` | RSI(14) 均值回归 |
| `agent` | `AgentStrategy` | Claude API 分析，Pydantic 严格验证输出 |

## A 股规则

- **T+1 结算**：当日买入的股票次日才能卖出
- **涨跌停**：普通股 ±10%，ST 股 ±5%，科创板/创业板 ±20%
- **最小手数**：下单数量向下取整到 100 股整数倍
- **交易费用**：佣金 0.03%（最低 5 元）+ 卖出印花税 0.05%

## 数据

本地 DuckDB + Parquet 数据湖，存放在 `data/`，默认使用前复权（QFQ）。

A 股数据源优先级：
1. AKShare（免费，默认）
2. Tushare Pro（设置 `TUSHARE_TOKEN` 环境变量）
3. BaoStock（免费，历史数据）
4. 本地缓存（离线可用）

## 文档

- `docs/plans/system-design-v2.md` — 系统架构设计文档
- `docs/research/` — 7 个开源量化系统的竞品调研报告
- `vendor/clone.sh` — 恢复 vendor 参考库（`bash vendor/clone.sh`）
