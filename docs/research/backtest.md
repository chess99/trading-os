# 回测口径（MVP）

## 防止“回测幻觉”的最小规则
- **信号计算**：使用第 \(t\) 根 K 线的 `close` 计算信号。
- **成交价格**：在第 \(t+1\) 根 K 线的 `open` 成交（next open），避免用未来信息。
- **费用与滑点**：
  - `fee_bps`：按成交金额收取
  - `slippage_bps`：买入在 `open*(1+slip)`，卖出在 `open*(1-slip)`

## 当前实现范围
- 单标的
- long-only
- all-in / all-out（仓位只有 0 或 1）

后续扩展方向（不影响当前接口）：多标的、多仓位、成交规则（A股涨跌停/停牌）、更细粒度时间周期等。

## CLI 示例
（需要在 Python 3.10–3.12 环境安装 `.[data_lake]`）

```bash
python -m trading_os backtest-sma --symbol NASDAQ:TEST --fast 5 --slow 20
```

