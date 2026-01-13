# 纸交易（Paper Trading）（MVP）

## 目标
把策略研究与未来实盘之间的“执行链路”先跑通：
- 信号生成
- 订单生成
- 风控拦截
- 模拟成交
- 持仓与净值更新
- 全量事件日志（可追溯、可复盘）

## 当前执行模型（MVP）
- 数据：日线 bars（`open/high/low/close/volume`）
- **信号**：用第 \(t\) 根 bar 的 `close` 计算
- **成交**：在第 \(t+1\) 根 bar 的 `open` 成交（next open）
- **滑点**：买入 `open*(1+slip)`，卖出 `open*(1-slip)`
- **费用**：按成交金额收取 `fee_bps`
- **仓位**：all-in/all-out（0 或 100%）

## 风控（最小集）
见 `src/trading_os/risk/manager.py`：
- 最大总敞口 `max_gross_exposure_pct`
  - 用于限制整体杠杆/满仓程度
- 单标的最大仓位 `max_position_pct`
- 冷却期 `cooldown_bars`
- 止损 `stop_loss_pct`（基于开盘价的简化版）
- 单日最大亏损 `max_daily_loss_pct`
- 回撤熔断 `circuit_breaker_drawdown_pct`（从权益峰值回撤触发停交易）

## 事件日志
- 位置：默认写到 `artifacts/paper/`（gitignored）
- 格式：JSONL（每行一个 event）
  - `order_rejected`
  - `order_filled`
  - `portfolio`

## CLI 示例
（需要在 Python 3.10–3.12 环境安装 `.[data_lake]`）

```bash
python -m trading_os paper-run-sma --symbol NASDAQ:TEST --fast 5 --slow 20 --stop-loss 0.1 --max-daily-loss 0.03 --circuit-breaker 0.1
```

