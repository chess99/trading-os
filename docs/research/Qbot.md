# Qbot 深度调研报告

> 仓库：https://github.com/UFund-Me/Qbot
> 调研日期：2026-04-06

## 1. 定位与目标用户

- **核心定位**：面向散户与量化研究者的开源自动化量化投研平台（~71,796 行 Python）
- **目标用户**：量化研究者、散户投资者、AI 体验者、基金定投者
- **人的角色**：辅助决策为主，平台生成信号，人工核验后执行实盘

## 2. 系统架构

**技术栈**：wxPython + backtrader + easytrader + vnpy + Tushare/AKShare + quantstats

**核心目录**：
```
qbot/
├── gui/          # wxPython GUI 客户端
├── engine/       # 交易执行引擎（真实/模拟）
├── strategies/   # 策略库（25+ 策略）
├── data/         # 数据管理
├── easyuncle/    # 多账户管理（MongoDB）
└── vnpy/         # VNpy 量化框架
pytrader/         # 传统量化模块（easytrader/easyquant）
pyfunds/          # 基金特化模块（xalpha 回测、DCA 策略）
pyfutures/        # 期货模块（CTP API）
```

**核心设计**：分层解耦（数据层→策略层→交易层→展示层）+ 事件驱动引擎 + 多品种统一框架

## 3. AI/Agent 使用方式

**重要发现**：AI 主要是 UI 集成，非核心引擎集成。

**ChatGPT 集成**（`gui/mainframe.py` 第 128 行）：
```python
web1.show_url("https://wo2qwg.aitianhu.com/")  # 外链第三方 ChatGPT
```

**AI 选股**（第 131 行）：
```python
web2.show_url("http://111.229.117.200:4868")  # 远程 IP 服务
```

**深度学习策略**（有实现）：
- LSTM 时序预测（`lstm_strategy_bt.py`）：Keras LSTM(50) + Dense(1)，预测价格 > 当前价 → 买入
- 强化学习（`rl_strategy_bt.py`）：RLkit + BacktraderEnv，agent.predict(obs) → 0/1/2
- SSA 麻雀搜索优化算法（`ssa_strategy_bt.py`）

**决策链路**：`用户输入 → 数据获取 → 策略计算 → 信号生成 → 持仓更新 → GUI 展示`（LLM 只用于代码生成辅助）

## 4. 数据来源与管理

**数据源**：Tushare、AKShare（巨潮）、BaoStock、YFinance、eFunds、Binance/OKEx

**数据存储**（`engine/config.py`）：
```
DATA_DIR/
├── hdf5/         # 核心数据（快速读写）
├── stocks/       # CSV 备份
├── futures/      # 期货数据
├── funds/        # 基金数据
├── btc/          # 虚拟货币
├── multi-facts/  # 多因子缓存
└── qlib_data/    # QLib 预处理数据
```

**支持市场**：A 股 + 港股 + 美股 + 基金/ETF + 期货（CTP）+ 虚拟货币（Binance/OKEx/Bybit）

## 5. 策略层

**策略类型**（25+ 个）：
- 单因子：RSI、MACD、布林带、KDJ、RSRS 择时、情绪指标 ARBR、低估值策略
- 机器学习：SSA、SVM、LSTM、LGBM、随机森林、线性回归
- 强化学习：Policy Gradient、Q-Learning
- 传统组合：海龟策略、网格策略、配对交易
- 基金特化：4433 法则、DCA 定投

**回测框架**：backtrader（股票/期货）+ easyquant（事件驱动）+ xalpha（基金定投）

**信号生成**：继承 `bt.Strategy`，`next()` 方法每根 K 线调用一次

## 6. 执行层

**交易模式**：
- 模拟盘：SimTradeEngine（100% 本地虚拟，滑点/延迟可配置）
- 实盘：RealTradeEngine（需真实账户登录）

**下单接口**：
| 平台 | 接口类型 |
|------|---------|
| 掘金 Gmsdk | 原生 API |
| 东方财富 | HTTP 爬虫 |
| CTP 期货 | Socket |
| 华泰证券 | 行情柜台 |
| 虚拟货币 | REST API |

**多账户管理**（easyuncle）：MongoDB 中心存储 + 持仓实时同步 + 多线程并行执行

**性能分析**：quantstats 一键生成完整报告（夏普比、最大回撤、月度收益等）

## 7. 亮点与可借鉴设计

1. **回测→模拟→实盘完整闭环** ⭐⭐⭐⭐：三个环节模型一致，策略迁移最小改动
2. **多品种统一框架** ⭐⭐⭐⭐：股票/基金/期货/加密同一套策略框架
3. **数据本地化存储** ⭐⭐⭐⭐：HDF5/Parquet 本地数据湖，离线开发，查询 <100ms
4. **事件驱动多账户引擎**：账户隔离 + 事件队列 + 下单路由
5. **低代码基金选择界面**：pyfunds 提供高层抽象，适合非技术用户
6. **quantstats 插件化**：高质量性能评估报告，建立信任基础
7. **模块化分层架构**：BaseQuotation 抽象，数据源无缝切换

## 8. 局限性与应避免的设计

| 问题 | 影响 | 建议 |
|------|------|------|
| AI 集成肤浅 | 只是 UI 外链，无后端集成 | 原生 LLM API 集成，而非网页嵌入 |
| 无实时行情推送 | 最小粒度分钟 K 线，不支持高频 | 支持 tick 级别推送 |
| 无参数优化工具 | 需手动调参 | 集成 optuna 参数搜索 |
| 风控模块不完整 | 无头寸管理、止损止盈、VaR | 完整风控框架 |
| 数据质量无验证 | 脏数据导致回测失真 | 数据质量监控告警 |
| 学习曲线陡峭 | 非技术用户难以上手 | 提供低代码界面 |
| 无审计日志 | 无法追溯操作记录 | 完整操作审计 |

## 9. 对本系统的启示

**值得采用**：
- 回测→模拟→实盘三阶段一致性设计
- 多品种统一策略框架思路
- 本地数据湖（HDF5/Parquet）
- quantstats 性能分析集成

**需要超越**：
- AI 集成：外链网页 → 原生 Claude Agent 决策链
- 数据可靠性：依赖第三方 → 严格验证 + 双源确认
- 风险管理：基础配置 → 完整 Kelly + VaR + 头寸管理
- 用户友好度：高门槛 → 低代码优先
