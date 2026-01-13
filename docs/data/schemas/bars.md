# Bars 表（K线）Schema（MVP）

这是本地数据湖里的核心表之一：`bars`（或按市场/周期拆分的视图）。

## 字段（列）
最小列集合（MVP）：
- `symbol`：string，`EXCHANGE:TICKER`
- `exchange`：string，冗余列，便于过滤
- `timeframe`：string，`1d`/`1h`/`15m`/`5m`/`1m`
- `adjustment`：string，`none`/`split_div`/`qfq`/`hfq`
- `ts`：timestamp with tz，UTC，**bar 结束时间**
- `open`：double
- `high`：double
- `low`：double
- `close`：double
- `volume`：double（兼容不同数据源；后续可用 bigint）

可选列：
- `vwap`：double
- `trades`：bigint
- `source`：string（数据源标识，比如 `yfinance`/`akshare`/`manual`）

## 主键与去重
建议逻辑主键：
- `(symbol, timeframe, adjustment, ts)`

## 质量检查（建议）
- `low <= min(open, close) <= max(open, close) <= high`
- `volume >= 0`
- `ts` 单调递增且无重复（按主键）

