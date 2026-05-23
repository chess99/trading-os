# 系统配置参考

三套体系各自独立配置。选择使用哪套体系时，对应的配置节生效。

---

## Elder 技术交易体系配置

```yaml
elder:
  account:
    total_capital: 500000        # 技术交易账户资金（元）
    monthly_loss_limit: 0.06     # 月度最大亏损比例（6% 原则）
    per_trade_risk: 0.02         # 单笔最大风险比例（2% 原则）
    currency: CNY

  watchlist:
    A股:
      - 600519  # 贵州茅台
      - 000858  # 五粮液
      - 300750  # 宁德时代
      - 601318  # 中国平安
      # 建议挑选流动性好、趋势明显的龙头股

    美股:
      - AAPL
      - NVDA
      - TSLA
      - SPY   # 标普500 ETF

    期货:
      - GC    # 黄金
      - CL    # 原油
      - ES    # 标普500期货

  indicators:
    ema:
      slow: 26
      fast: 13
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

  signal_filter:
    min_risk_reward: 2.0
    min_signal_strength: 中
    require_divergence: false
    max_signals_per_day: 5
```

---

## CANSLIM 成长股体系配置

```yaml
canslim:
  account:
    total_capital: 500000        # 成长股账户资金（元）
    initial_stop_loss: 0.08      # 欧奈尔规则：初始止损 7-8%
    currency: CNY

  watchlist:
    A股成长股候选:
      - 300750  # 宁德时代
      - 688981  # 中芯国际
      # 建议选择 EPS 高增长、行业龙头、近期创新高的标的

  screening_thresholds:
    eps_growth_quarterly: 0.25   # 当季 EPS 增长 > 25%（C 维度）
    eps_growth_annual_years: 3   # 年度 EPS 连续增长年数（A 维度）
    roe_min: 0.17                # ROE > 17%
    relative_strength_rank: 90  # 相对强度排名前 10%（L 维度）
```

---

## Value Investing 价值投资体系配置

```yaml
value_investing:
  account:
    total_capital: 500000        # 价值投资账户资金（元）
    stop_loss_type: logic        # 纯逻辑止损，无价格止损
    currency: CNY

  watchlist:
    A股价值候选:
      - 600519  # 贵州茅台
      - 601318  # 中国平安
      # 建议选择护城河清晰、ROE 稳定、管理层优秀的公司

  valuation_methods:
    - DCF          # 现金流折现
    - PE_relative  # 相对市盈率
    - SOTP         # 分部估值（适合多业务公司）
```

---

## 数据源配置（三套体系共用）

```yaml
data_sources:
  realtime:
    provider: ""    # tushare、akshare、yfinance、alpha_vantage
    api_key: ""

  historical:
    provider: akshare
    lookback_weeks: 52
    lookback_days: 120

  fallback: "手动输入价格数据，或使用 web_search 获取最新行情"

broker:
  name: ""
  api_endpoint: ""
  api_key: ""
  account_id: ""
  mode: paper
  auto_execute: false
```
