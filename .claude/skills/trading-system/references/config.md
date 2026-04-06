# 系统配置参考

## 账户配置

```yaml
account:
  total_capital: 500000        # 账户总资金（元/美元）
  monthly_loss_limit: 0.06     # 月度最大亏损比例（6%原则）
  per_trade_risk: 0.02         # 单笔最大风险比例（2%原则）
  currency: CNY                # 货币单位
```

## 候选标的池

建议按市场分组管理，初始建议不超过20-30个标的：

```yaml
watchlist:
  A股:
    - 600519  # 贵州茅台
    - 000858  # 五粮液
    - 300750  # 宁德时代
    - 601318  # 中国平安
    # ... 建议挑选流动性好、趋势明显的龙头股

  美股:
    - AAPL
    - NVDA
    - TSLA
    - SPY   # 标普500 ETF

  期货:
    - GC    # 黄金
    - CL    # 原油
    - ES    # 标普500期货

  外汇:
    - EURUSD
    - USDJPY
```

## 技术指标参数

```yaml
indicators:
  ema:
    slow: 26    # 慢线（周线图用26周，日线图用26日）
    fast: 13    # 快线（约为慢线的一半）

  macd:
    fast_period: 12
    slow_period: 26
    signal_period: 9

  stochastic:
    period: 5
    smooth: 3

  atr:
    period: 13

  force_index:
    short_ema: 2
    long_ema: 13
```

## 信号过滤阈值

```yaml
signal_filter:
  min_risk_reward: 2.0      # 最低风险收益比
  min_signal_strength: 中    # 最低信号强度（弱/中/强）
  require_divergence: false  # 是否只选有背离的信号
  max_signals_per_day: 5    # 每日最多深度分析的标的数
```

## 数据源配置

```yaml
data_sources:
  # 实时行情（需要配置）
  realtime:
    provider: ""    # 如：tushare、akshare、yfinance、alpha_vantage
    api_key: ""

  # 历史数据
  historical:
    provider: ""
    lookback_weeks: 52    # 周线回看52周（1年）
    lookback_days: 120    # 日线回看120天

  # 暂不可用时的替代方案
  fallback: "手动输入价格数据，或使用 web_search 获取最新行情"
```

## 交易接口配置（壳子，待接入）

```yaml
broker:
  name: ""          # 如：Interactive Brokers、富途、老虎证券
  api_endpoint: ""
  api_key: ""
  account_id: ""
  mode: paper       # paper（模拟）或 live（实盘）
  auto_execute: false   # 是否自动执行，默认关闭，需要人工确认
```
