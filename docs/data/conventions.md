# 数据口径与约定（MVP）

这份文档定义**跨市场统一口径**，确保数据湖、回测、纸交易、实盘适配层能够复用同一套标准。

## 标的标识（Symbol ID）
- **规范**：`EXCHANGE:TICKER`
- **例子**：
  - `SSE:600000`（上交所）
  - `SZSE:000001`（深交所）
  - `NASDAQ:AAPL`
  - `HKEX:0700`
- **说明**：我们把 symbol 当成“唯一主键”。其他元数据（名称、货币、资产类型等）可在 instruments 表中补齐。

## 交易所代码（Exchange）
见代码：`src/trading_os/data/schema.py` 的 `Exchange`。

## 时间与时区
- **统一存储**：所有时间戳字段 `ts` 必须是 **UTC 且带时区**（timezone-aware）。
- **含义**：`ts` 表示 bar 的“结束时间”还是“开始时间”必须明确。MVP 先约定：**`ts` 为 bar 的结束时间（close time）**。
- **展示/分析**：需要本地时区时，在查询/展示层转换，不改存储口径。

## K线（Bars）字段
见代码：`src/trading_os/data/schema.py` 的 `BarColumns`。

最小字段：
- `symbol`, `exchange`, `timeframe`, `adjustment`, `ts`, `open`, `high`, `low`, `close`, `volume`

可选字段（后续增强真实度）：
- `vwap`, `trades`, `source`

## 复权（Adjustment）
- `none`：不复权（原始价格）
- `split_div`：拆股/分红等调整（常见 adj close 体系）
- `qfq`/`hfq`：A股前复权/后复权（保留兼容）

**原则**：回测时必须明确使用哪一种复权口径，并且订单撮合使用的价格口径要与策略输入一致或可解释。

## 交易日历（Trading Calendar）
MVP 默认用“工作日历”（周一到周五都是交易日），见 `src/trading_os/data/calendar.py` 的 `WeekdayCalendar`。\n
后续会替换为真实交易日历（节假日、半日市、停牌等），但下游接口不变。

