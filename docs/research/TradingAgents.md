# TradingAgents 深度调研报告

> 仓库：https://github.com/TauricResearch/TradingAgents
> 版本：v0.2.3
> 调研日期：2026-04-06
> 论文：arXiv:2412.20138

---

## 1. 定位与目标用户

**核心定位**：模拟真实交易公司内部多部门协作流程的多 Agent LLM 金融交易框架（研究用途）。其核心贡献在于将复杂的投资决策分解为专业化角色分工——类比一家真实机构的研究部、交易部和风险部协同运作。

**目标用户**：
- 学术研究者（量化金融、LLM Agent 应用方向）
- 金融科技公司（验证 AI 辅助投资决策可行性）
- 高级量化研究员（原型验证、框架扩展）
- 对 LLM Agent 系统感兴趣的技术开发者

**人的角色**：被动观察者 + 配置者。用户只需提供 ticker 和日期，整个分析流水线由 LLM Agent 自主驱动，最终 Portfolio Manager Agent 输出决策。人介入的时机是配置（LLM 选择、辩论轮次、数据源），以及事后通过 `reflect_and_remember(returns)` 传入 P&L 触发记忆更新。系统不提供实盘接口，定位明确为研究原型。

---

## 2. 系统架构

### 技术栈

| 层次 | 技术 |
|------|------|
| Agent 编排 | LangGraph 0.4.8+（StateGraph + DAG） |
| LLM 接入 | LangChain（OpenAI / Anthropic / Google / xAI / OpenRouter / Ollama） |
| 数据获取 | yfinance（主）+ Alpha Vantage（付费备选） |
| 技术指标计算 | stockstats 0.6.5+ |
| 本地记忆检索 | rank-bm25（BM25Okapi，无向量数据库） |
| CLI 界面 | Typer + Rich（实时进度面板） |
| 回测依赖 | backtrader（引入但未实际集成） |
| 缓存 | 本地 CSV 文件缓存（按 symbol 存储） |
| 运行时 | Python 3.10+，支持 Docker + Ollama |

### 核心目录结构

```
tradingagents/
├── agents/
│   ├── analysts/
│   │   ├── market_analyst.py       # 技术指标分析（选择最优 8 个指标）
│   │   ├── fundamentals_analyst.py # 财务报表分析（PE/PB/ROE/现金流）
│   │   ├── news_analyst.py         # 宏观新闻分析（公司+全球新闻）
│   │   └── social_media_analyst.py # 情感分析（公司新闻+舆情）
│   ├── researchers/
│   │   ├── bull_researcher.py      # 多头辩护（接受记忆注入）
│   │   └── bear_researcher.py      # 空头辩护（接受记忆注入）
│   ├── managers/
│   │   ├── research_manager.py     # 辩论仲裁（生成投资计划）
│   │   └── portfolio_manager.py    # 最终决策（5 级评分）
│   ├── trader/
│   │   └── trader.py               # 交易执行（综合研究计划生成订单）
│   ├── risk_mgmt/
│   │   ├── aggressive_debator.py   # 激进风险观（高收益导向）
│   │   ├── conservative_debator.py # 保守风险观（资产保护导向）
│   │   └── neutral_debator.py      # 中立风险观（平衡两方）
│   └── utils/
│       ├── agent_states.py         # AgentState / InvestDebateState / RiskDebateState
│       ├── memory.py               # BM25 记忆系统（FinancialSituationMemory）
│       └── agent_utils.py          # 工具注册 + 语言适配 + 消息清理
├── graph/
│   ├── trading_graph.py            # 主类（TradingAgentsGraph）
│   ├── setup.py                    # StateGraph 图构建 + DAG 边定义
│   ├── conditional_logic.py        # 条件路由（辩论轮次、工具调用判断）
│   ├── reflection.py               # 反思系统（决策后写入记忆）
│   ├── propagation.py              # 状态初始化 + graph invoke
│   └── signal_processing.py        # 5 级信号提取（BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL）
├── dataflows/
│   ├── interface.py                # 供应商路由层 + 自动降级逻辑
│   ├── config.py                   # 全局配置（线程安全单例）
│   ├── y_finance.py                # yfinance 实现（OHLCV+基本面+内部人）
│   ├── yfinance_news.py            # yfinance 新闻实现
│   ├── stockstats_utils.py         # 指标计算 + CSV 缓存 + 前瞻偏差防护
│   ├── alpha_vantage.py            # Alpha Vantage 聚合入口
│   ├── alpha_vantage_stock.py      # Alpha Vantage 股价
│   ├── alpha_vantage_indicator.py  # Alpha Vantage 技术指标
│   ├── alpha_vantage_fundamentals.py
│   └── alpha_vantage_news.py
└── llm_clients/
    ├── factory.py                  # LLM 客户端工厂（provider 路由）
    ├── base_client.py              # BaseLLMClient + normalize_content
    ├── openai_client.py            # OpenAI/xAI/OpenRouter/Ollama（Responses API）
    ├── anthropic_client.py         # Claude（extended thinking 支持）
    ├── google_client.py            # Gemini（thinking level 支持）
    ├── model_catalog.py            # 统一模型目录（5 供应商全型号）
    └── validators.py               # 模型名称校验

cli/
├── main.py                         # Typer CLI + Rich 实时面板
├── models.py                       # AnalystType 枚举
├── stats_handler.py                # LLM/工具调用统计回调
└── utils.py                        # 交互式配置选项
```

### 核心设计思路

**三层决策管道 + 两轮辩论机制**：

```
[数据层]  yfinance / Alpha Vantage → stockstats
    ↓
[分析层]  4 类 Analyst（顺序执行）→ 生成 4 份专项报告
    ↓
[研究层]  Bull vs Bear 辩论（max_debate_rounds 轮）→ Research Manager 仲裁 → 投资计划
    ↓
[交易层]  Trader Agent（读取研究计划）→ 交易方案
    ↓
[风控层]  Aggressive vs Conservative vs Neutral（max_risk_discuss_rounds 轮）→ Portfolio Manager → 最终决策
    ↓
[记忆层]  reflect_and_remember(P&L) → BM25 存储 → 下次检索
```

**状态机设计**：LangGraph `StateGraph` 驱动，`AgentState`（含 `InvestDebateState` + `RiskDebateState`）贯穿全局。Analyst 节点循环通过 `tool_calls` 检测决定是否继续（`should_continue_market` 等条件函数），辩论节点通过计数器控制轮次。

---

## 3. AI/Agent 使用方式

### 集成方式

以 Python 包方式引入，核心 API 极简：

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())
_, decision = ta.propagate("NVDA", "2026-01-15")
# decision: "BUY" / "OVERWEIGHT" / "HOLD" / "UNDERWEIGHT" / "SELL"
```

### 多 LLM 分级策略

```python
config["deep_think_llm"]  = "gpt-5.4"        # 复杂推理：Research Manager、Portfolio Manager
config["quick_think_llm"] = "gpt-5.4-mini"   # 快速任务：4 类 Analyst、辩论 Agent、Trader
```

支持 6 大供应商，每个供应商均有 quick/deep 两档模型推荐：

| 供应商 | quick 示例 | deep 示例 |
|--------|-----------|----------|
| OpenAI | gpt-5.4-mini | gpt-5.4 |
| Anthropic | claude-sonnet-4-6 | claude-opus-4-6 |
| Google | gemini-3-flash-preview | gemini-3.1-pro-preview |
| xAI | grok-4-1-fast-non-reasoning | grok-4-0709 |
| OpenRouter | 动态获取 | 动态获取 |
| Ollama | qwen3:latest | glm-4.7-flash:latest |

还支持供应商级推理控制：`google_thinking_level`（"high"/"minimal"）、`openai_reasoning_effort`（"high"/"medium"/"low"）、`anthropic_effort`（"high"/"medium"/"low"）。

### 决策链路（完整流）

**第一阶段：分析师层（顺序执行，Tool Use 循环）**

每个 Analyst 都使用 `ChatPromptTemplate + MessagesPlaceholder` 构建 prompt，绑定数据工具，通过 LangGraph 条件路由实现 `Agent → Tool → Agent → ...` 循环，直到无 tool_calls 时生成报告。

以 Market Analyst 为例，prompt 指示 LLM 从预定义列表中选择最相关的 8 个技术指标（MA50/MA200/EMA10/MACD/RSI/布林带/ATR/VWMA），先调用 `get_stock_data` 获取 OHLCV，再调用 `get_indicators` 逐一计算，最后生成含 Markdown 表格的分析报告。

**第二阶段：研究员辩论（对称结构）**

多头研究员的 prompt 核心结构（完整原文）：

```
You are a Bull Analyst advocating for investing in the stock.
Key points: Growth Potential, Competitive Advantages, Positive Indicators, Bear Counterpoints
Resources: {market_report}, {sentiment_report}, {news_report}, {fundamentals_report}
Debate History: {history}
Last bear argument: {current_response}
Past lessons: {past_memory_str}
```

空头研究员结构对称，强调：风险与挑战、竞争弱点、负面指标、驳斥多头观点。

辩论控制逻辑：`count >= 2 * max_debate_rounds` 时转入 Research Manager。

**第三阶段：Research Manager 仲裁**

接收完整辩论历史，被要求做出明确的 BUY/SELL/HOLD 决定，不允许"因两方都有道理而选择 Hold"，需给出战略行动步骤。使用 `deep_think_llm`。

**第四阶段：Trader Agent**

读取 Research Manager 的投资计划，生成交易方案。必须以 `FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**` 结尾。同样接入 BM25 记忆。

**第五阶段：风险辩论（三方结构）**

激进（Aggressive）、保守（Conservative）、中立（Neutral）三方围绕 Trader 的方案展开辩论：
- 激进：捍卫高收益机会，质疑保守和中立的过度谨慎
- 保守：强调资产保护，指出激进和中立忽略的风险
- 中立：挑战两极端，倡导平衡策略

轮次控制：`count >= 3 * max_risk_discuss_rounds`（三方各说一轮算一轮）。

**第六阶段：Portfolio Manager 最终决策**

使用 5 级评分标准（Buy/Overweight/Hold/Underweight/Sell），输出必须包含：Rating、Executive Summary（含入场策略、仓位规模、关键风险、时间跨度）、Investment Thesis（基于辩论的详细论证）。使用 `deep_think_llm`。

### 关键 Prompt 设计模式

1. **角色注入**：每个 Agent 的 system prompt 明确角色定义和行为边界
2. **工具说明内嵌**：Analyst 层将工具参数说明（含使用场景和注意事项）直接写入 prompt，引导 LLM 正确选择和调用
3. **记忆注入**：BM25 检索的历史决策以 `past_memory_str` 形式追加到 prompt 末尾
4. **语言适配**：`get_language_instruction()` 动态追加输出语言指令，仅对用户可见的 Agent（Analyst + Portfolio Manager）生效，辩论层保持英文以维持推理质量
5. **消息清理机制**：每个 Analyst 完成后调用 `create_msg_delete()` 清除消息历史（含 Anthropic 兼容的 placeholder），防止上下文窗口溢出

---

## 4. 数据来源与管理

### 数据源架构

**双供应商 + 分类级路由**：

```python
# 默认配置（可按类别或工具粒度覆盖）
config["data_vendors"] = {
    "core_stock_apis":    "yfinance",  # 可选：alpha_vantage, yfinance
    "technical_indicators": "yfinance",
    "fundamental_data":   "yfinance",
    "news_data":          "yfinance",
}
# 工具级覆盖（优先于类别级）
config["tool_vendors"] = {
    "get_stock_data": "alpha_vantage",  # 单个工具级别覆盖
}
```

**降级逻辑**（`interface.py`）：仅 `AlphaVantageRateLimitError`（HTTP 429）触发供应商降级，其他异常直接抛出。这是个重要的设计决策——只对"可重试"错误降级，避免掩盖真实的数据错误。

### 支持的数据类型

| 数据类型 | yfinance 实现 | Alpha Vantage 实现 |
|---------|-------------|-----------------|
| OHLCV 日线 | `yf.Ticker.history()` | `TIME_SERIES_DAILY_ADJUSTED` |
| 技术指标 | stockstats 本地计算 | API 直接返回 |
| 公司基本面 | `yf.Ticker.info` | `OVERVIEW` endpoint |
| 资产负债表 | `yf.Ticker.balance_sheet` | `BALANCE_SHEET` endpoint |
| 现金流量表 | `yf.Ticker.cashflow` | `CASH_FLOW` endpoint |
| 利润表 | `yf.Ticker.income_stmt` | `INCOME_STATEMENT` endpoint |
| 公司新闻 | `yf.Ticker.news` | `NEWS` endpoint |
| 全球新闻 | yfinance 查询 | `NEWS` + `top news` 查询 |
| 内部人交易 | `yf.Ticker.insider_transactions` | `INSIDER_TRANSACTIONS` endpoint |

### 支持市场

**原生支持（通过 yfinance ticker 后缀）**：
- 美股：NVDA、AAPL 等（无后缀）
- 加拿大：`.TO`（多伦多交易所）
- 港股：`.HK`
- 伦敦：`.L`
- 东京：`.T`

**Ticker 上下文注入**：`build_instrument_context(ticker)` 函数向每个 Agent 注入指令，要求在所有工具调用和报告中保留 exchange suffix，防止 LLM 错误剥离后缀。

**A 股**：官方版本未集成 Tushare/AKShare，实际上不支持。

### 缓存机制

`stockstats_utils.py` 实现本地 CSV 缓存：以 `{symbol}-YFin-data-{start}-{end}.csv` 为文件名，启动时计算 5 年窗口，同一 symbol 只下载一次，后续直接读本地。`filter_financials_by_date()` 过滤财务报表中 curr_date 之后的列，防止回测前瞻偏差。

### 决策日志

所有分析结果和决策完整保存为 JSON：

```
results/{ticker}/TradingAgentsStrategy_logs/full_states_log_{trade_date}.json
```

包含：4 份分析报告、完整辩论历史（多头/空头分别存储）、Research Manager 决策、Trader 方案、风险辩论历史、最终决策。

---

## 5. 策略层

### 策略类型

TradingAgents 本质上是**策略生成框架**，不是固定策略，其核心特点是：

1. **多维度分析综合**：同时运行技术分析（趋势、动量、波动率）+ 基本面（财务健康、内在价值）+ 情感分析（市场情绪、舆论倾向）+ 宏观分析（利率、地缘、行业趋势），每维度由专项 Agent 独立分析
2. **对抗性信息合成**：通过结构化辩论而非简单加权，强迫不同视角相互碰撞，减少分析盲点
3. **风险分层决策**：交易建议经过独立的三方风险评估后才输出最终信号

### 信号生成

Portfolio Manager 输出结构化报告，`signal_processing.py` 调用 LLM 从报告中提取 5 级评分：

```
BUY / OVERWEIGHT / HOLD / UNDERWEIGHT / SELL
```

这是相对传统 3 级（买/卖/持有）的升级，允许表达"方向正确但仓位应渐进调整"的渐进立场。

### 回测框架

项目 `pyproject.toml` 中包含 `backtrader>=1.9.78.123` 依赖，但经过代码审查，**backtrader 在当前版本中未被实际使用**。数据层实现了前瞻偏差防护（`filter_financials_by_date`、`load_ohlcv` 中的日期过滤），具备回测所需的数据基础，但完整的策略回测-再平衡循环尚未实现。`reflect_and_remember(returns_losses)` API 是人工传入 P&L 的接口，不是自动回测。

### Analyst Agent 可选组合

`selected_analysts` 参数允许灵活组合（默认全选）：

```python
# 只做技术+基本面分析，跳过新闻和情感
ta = TradingAgentsGraph(
    selected_analysts=["market", "fundamentals"],
    config=config
)
```

Analyst 列表为空时系统直接报错，至少需要一个分析维度。

---

## 6. 执行层

### 交易模式

**纯模拟/研究模式**，无任何实盘交易接口。Portfolio Manager 的输出是结构化自然语言报告，用户需自行解析并连接 Broker API。

### 下单接口

无。框架的 "执行" 是指 Agent 输出 `final_trade_decision`，包含：
- 评级（5 级）
- 执行摘要（含入场策略、仓位规模建议、关键风险水平、时间跨度）
- 投资论文（详细推理）

### 风控实现

风控通过 Agent 层实现（而非量化模块）：

| 风控维度 | 实现方式 |
|---------|---------|
| 方向性风险 | Bull vs Bear 辩论，强制考虑做空理由 |
| 仓位风险 | Aggressive/Conservative/Neutral 三方辩论 |
| 历史风险 | BM25 记忆注入，防止重蹈历史错误 |
| 前瞻偏差 | 数据层 curr_date 过滤（回测数据隔离） |

**缺失**：无量化 VaR/CVaR、无相关性矩阵、无最大回撤约束、无仓位集中度限制。

### P&L 反馈循环

```python
ta.reflect_and_remember(returns_losses)  # 传入本次交易的实际盈亏
```

触发对 5 类 Agent（Bull/Bear 研究员、Trader、Research Manager、Portfolio Manager）的独立反思，生成改进建议，写入对应的 BM25 记忆库。下次相似市场环境时，`past_memory_str` 会被检索注入 prompt，形成学习闭环。

---

## 7. 亮点与可借鉴设计

### 设计亮点评分

**1. 双层对抗辩论机制** ⭐⭐⭐⭐⭐

两轮对抗辩论是该框架最核心的创新：
- 投资层：Bull vs Bear（多空对立，逼出做空理由）
- 风控层：Aggressive vs Conservative vs Neutral（三方拉锯，寻找最优风险姿态）

辩论不是"各说各话的加权"，而是强迫每方针对对方的最新论点进行回应，形成真正的对话式交锋。这种设计比单一 Agent 分析更能识别盲点和过度乐观。

**2. BM25 离线记忆系统** ⭐⭐⭐⭐⭐

将历史决策经验以（市场情况文本, 反思建议）对的形式存储，用 BM25 词法匹配检索相似情境。

技术优势：
- 无需向量数据库（ChromaDB、Pinecone 等），零额外基础设施
- 无需 Embedding API 调用，离线可运行
- 分角色独立记忆库（bull_memory / bear_memory / trader_memory / invest_judge_memory / portfolio_manager_memory），避免角色记忆污染

与 TradingAgents-CN 比较：CN 版用 ChromaDB 向量检索，原版用 BM25 词法检索。BM25 在金融文本上可能同样有效，且成本和复杂度更低。

**3. 多 LLM 供应商统一适配** ⭐⭐⭐⭐

`BaseLLMClient` → `factory.create_llm_client()` 设计支持 6 大供应商，统一接口。关键工程细节：
- OpenAI 使用 Responses API（`use_responses_api=True`），统一支持 reasoning_effort 和 tool use
- Anthropic 的 `NormalizedChatAnthropic` 将 extended thinking 输出的 content block 列表规范化为字符串
- 同样的规范化逻辑在 OpenAI 侧也有对应实现
- 供应商级推理深度控制（thinking_level / reasoning_effort / effort）

**4. 完整决策可追溯性** ⭐⭐⭐⭐

每次 `propagate()` 调用都将完整决策链路（4 份分析报告 + 完整辩论历史 + 各阶段决策）保存为 JSON。这意味着：
- 可以事后审计每个决策的完整依据
- 可以比较不同 LLM / 不同配置的决策差异
- 可以在 `reflect_and_remember()` 时拥有完整上下文

**5. 灵活的分析师可选组合** ⭐⭐⭐

`selected_analysts` 参数允许按需组合分析维度，快速模式可只选 1-2 个分析师，降低延迟和成本。图构建逻辑自动适配，不需要修改代码。

**6. 前瞻偏差防护** ⭐⭐⭐

`load_ohlcv()` 和 `filter_financials_by_date()` 通过日期截断确保回测时 Agent 不会看到 trade_date 之后的数据。这是量化研究中容易被忽视的细节。

**7. 双语输出支持** ⭐⭐⭐

内部辩论（Bull/Bear/Risk 层）保持英文（reasoning quality），用户可见报告（Analyst + Portfolio Manager）支持任意语言输出。这种设计折中了推理质量和用户体验。

**8. Rich CLI 实时监控面板** ⭐⭐⭐

Terminal 级 UI 实时展示 Agent 执行进度（进度表格 + 消息流 + Token/工具调用统计），分析过程完全透明可观察。`StatsCallbackHandler` 通过 LangChain 回调机制统计 LLM/工具调用次数和 Token 消耗。

---

## 8. 局限性与应避免的设计

| 问题 | 具体表现 | 影响程度 | 建议 |
|------|---------|---------|------|
| 回测框架未实现 | backtrader 依赖存在但无实际集成，无策略回测-再平衡闭环 | 高 | 完整实现回测循环，与 `reflect_and_remember` 对接 |
| 无实盘接口 | 纯纸面决策，需用户自行连接 Broker | 中（研究场景无影响） | 提供 Interactive Brokers / Alpaca 适配器 |
| 风险量化不足 | 无 VaR/CVaR、无相关性分析、无仓位约束 | 高（实盘使用时） | 独立量化风控模块，Agent 建议需通过量化校验 |
| Prompt 稳定性脆弱 | LLM 版本更新可能破坏信号提取，无 Pydantic/JSON Schema 输出约束 | 高 | 使用 structured output 约束关键决策输出格式 |
| 运行成本可观 | 多轮辩论（2 轮 = 4 次 LLM 调用）+ 多 Analyst + 风险辩论，每次分析 15-20+ 次 LLM 调用 | 中 | 严格控制辩论轮次，快/慢模型分级（已实现），定义成本预算上限 |
| A 股支持缺失 | yfinance 对 A 股数据不完整，无 Tushare/AKShare 集成 | 高（国内用户） | 接入 Tushare/AKShare，参考 TradingAgents-CN |
| 单股分析局限 | 每次只分析一个 ticker，无组合层面的相关性分析 | 中 | Portfolio 层面多 ticker 并发分析 + 相关性矩阵 |
| 分析顺序串行 | 4 类 Analyst 串行执行，无并行化 | 中（延迟影响） | 4 个 Analyst 可并行（互不依赖） |
| 社交媒体分析名不副实 | Social Media Analyst 实际上只调用 `get_news`（与 News Analyst 相同工具），不是真正的社交媒体分析 | 中 | 接入 Twitter/Reddit API，获取真实情感数据 |
| 记忆持久性缺失 | BM25 记忆仅在进程生命周期内有效，重启后丢失，无持久化存储 | 高 | 将 BM25 文档序列化到磁盘或数据库 |
| LLM 幻觉风险 | 目标价、止损价等关键数字直接由 LLM 生成，缺乏数据验证 | 高 | 先用量化模型计算合理估值区间，LLM 只做解释和调整 |

---

## 9. 对本系统的启示

### 最值得采用的设计

**1. 双层对抗辩论架构（分析→辩论→风险→执行）**

本系统应引入类似的多视角对抗机制。建议直接采用"多头研究员 vs 空头研究员 → 仲裁"模式，但可以将辩论上下文保存到本系统的 DuckDB 数据库中，而非 JSON 文件。

**2. BM25 历史决策记忆**

比 ChromaDB 向量库更轻量，适合本系统的本地优先原则。可以将 BM25 记忆与本系统现有的 DuckDB 存储结合：将市场情况文本和决策反思存入 DuckDB，BM25 索引在内存中重建。

**3. 多 LLM 供应商不锁定**

统一的 `BaseLLMClient` 抽象是良好实践。本系统已经有 Claude，应确保同样支持 GPT 和 Gemini 作为备选，不被单一供应商绑定。

**4. 完整决策可追溯（JSON 日志）**

本系统已有事件日志能力，应确保每次 Agent 决策包含完整的推理链路、分析报告、辩论记录，支持事后复盘和审计。

**5. 前瞻偏差防护**

本系统回测引擎应严格实施类似的日期截断机制，数据层必须接受 `curr_date` 参数，禁止返回该日期后的数据。

### 值得超越的方向

**1. 量化风控补强**

TradingAgents 的风控完全依赖 LLM Agent，存在幻觉风险。本系统应在 Agent 层之上加一层量化校验：Agent 提出方案后，量化模块计算 VaR/CVaR/最大回撤，不通过则驳回重新讨论。

**2. 真正的实盘执行层**

TradingAgents 无实盘接口，本系统应建立完整的 Broker 适配器（模拟→纸面→实盘分级），并将 Agent 决策与真实下单执行解耦。

**3. 组合层面分析**

TradingAgents 只做单股分析。本系统应支持多标的并发分析，并在 Portfolio Manager 层引入相关性矩阵和仓位优化。

**4. 持久化记忆**

TradingAgents 的 BM25 记忆在重启后丢失。本系统应将决策历史持久化到 DuckDB，重启后重建索引，确保历史经验不丢失。

**5. A 股本地化**

TradingAgents 只支持美港股。本系统应深度支持 A 股（Tushare/AKShare），适配国内市场的分析维度（北向资金、融资融券、限售解禁等）。

**6. 结构化输出约束**

TradingAgents 使用自然语言提取信号，存在格式不稳定风险。本系统应强制使用 Pydantic/JSON Schema 约束关键决策字段，确保下游处理的可靠性。

### 核心设计原则总结

| 原则 | TradingAgents 做法 | 本系统策略 |
|------|------------------|-----------|
| 对立视角 | Bull vs Bear + Aggressive vs Conservative | 采用，扩展到更多维度 |
| 记忆积累 | BM25 进程内记忆 | 采用 + 持久化到 DuckDB |
| LLM 分级 | quick_think vs deep_think | 采用，进一步优化成本控制 |
| 可追溯性 | JSON 日志全链路 | 采用 + 与现有事件日志集成 |
| 数据前瞻防护 | curr_date 截断 | 采用，作为数据层强制约束 |
| 量化风控 | 无（纯 LLM） | 超越：量化模块作为最终守门人 |
| 实盘执行 | 无 | 超越：分级 Broker 适配器 |
| A 股支持 | 无 | 超越：Tushare/AKShare 集成 |
