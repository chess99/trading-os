# TradingAgents 深度调研报告

> 仓库：https://github.com/TauricResearch/TradingAgents
> 调研日期：2026-04-06

## 1. 定位与目标用户

- **核心定位**：模拟真实交易公司内部多部门协作流程的多 Agent 股票分析框架
- **目标用户**：量化研究机构、金融科技公司、研究团队、有技术背景的投资者
- **人的角色**：最终审批权——Portfolio Manager 是最后把关者，LLM Agent 负责专业分析与评估，不直接触及真实资金

## 2. 系统架构

**技术栈**：LangGraph 0.4.8+ + backtrader + LiteLLM（OpenAI/Claude/Gemini/Grok/Ollama）+ yfinance + Alpha Vantage + stockstats

**核心目录**：
```
tradingagents/
├── agents/
│   ├── analysts/        # 4 类分析 Agent（市场、情感、新闻、基本面）
│   ├── researchers/     # 2 类研究 Agent（多头、空头）
│   ├── managers/        # 2 类经理 Agent（研究经理、投资组合经理）
│   ├── trader/          # 交易 Agent
│   ├── risk_mgmt/       # 3 类风控 Agent（激进、保守、中立）
│   └── utils/           # 状态定义（AgentState、InvestDebateState、RiskDebateState）
├── graph/
│   ├── trading_graph.py  # 主入口（LangGraph）
│   ├── setup.py          # 图构建逻辑（StateGraph + DAG）
│   ├── conditional_logic.py  # 条件路由（辩论轮次控制）
│   ├── reflection.py     # 反思和记忆更新
│   └── signal_processing.py  # 信号提取（5 级评分）
├── dataflows/
│   ├── interface.py      # 供应商路由 + 降级链
│   ├── y_finance.py      # yfinance 实现
│   └── alpha_vantage.py  # Alpha Vantage 实现
└── llm_clients/
    ├── factory.py        # LLM 客户端工厂
    ├── openai_client.py  # GPT/Grok 支持
    ├── anthropic_client.py  # Claude 支持
    └── google_client.py  # Gemini 支持
```

**核心设计**：三层决策管道（分析→辩论→风险→执行）+ LangGraph DAG 状态机 + BM25 离线记忆

## 3. AI/Agent 使用方式

**框架**：LangGraph 编排多 Agent

**支持 LLM**：OpenAI（GPT-5.x）、Anthropic（Claude 4.x）、Google（Gemini）、xAI（Grok）、OpenRouter、Ollama 本地模型

**混合 LLM 模式**：
```python
"deep_think_llm": "gpt-5.4",       # 复杂推理（研究经理、投资组合经理）
"quick_think_llm": "gpt-5.4-mini", # 快速任务（分析、辩论）
```

**多 Agent 分工**：
```
并行分析阶段：
  市场分析师 | 情感分析师 | 新闻分析师 | 基本面分析师
         ↓
辩论阶段（max_debate_rounds 可配置）：
  多头研究员 vs 空头研究员 → 研究经理仲裁
         ↓
风险评估阶段：
  激进分析师 | 保守分析师 | 中立分析师 → 风险经理
         ↓
执行阶段：
  投资组合经理 → final_trade_decision（5 级评分）
```

**记忆系统**：BM25 离线记忆（无需向量数据库），本地计算，检索历史相似决策

**关键 Prompt 结构**（多头研究员示例）：
```python
prompt = f"""You are a Bull Analyst advocating for investing...
Focus on: Growth Potential, Competitive Advantages, Positive Indicators, Counter Bear Arguments
Resources: {market_report}\n{sentiment_report}\n{news_report}\n{fundamentals_report}
Last bear argument: {current_response}
Past lessons: {past_memory_str}
"""
```

## 4. 数据来源与管理

**双层供应商架构**：yfinance（免费）+ Alpha Vantage（付费），支持自动降级

**降级机制**（interface.py）：
```python
# 仅速率限制触发降级，其他异常不触发
for vendor in fallback_vendors:
    try:
        return impl_func(*args, **kwargs)
    except AlphaVantageRateLimitError:
        continue
```

**支持数据类型**：
| 类型 | 来源 | 说明 |
|------|------|------|
| OHLCV 日线 | yfinance / Alpha Vantage | 主要数据源 |
| 技术指标 | stockstats（窗口计算） | MA、MACD、RSI、布林带、ATR |
| 基本面 | yfinance | 财务报表、PE/PB/ROE |
| 新闻 | yfinance / Alpha Vantage | 情感评分 |
| 内部人交易 | yfinance | insider transactions |

**支持市场**：美股（原生）、加拿大（.TO）、港股（.HK）、伦敦（.L）；A 股未完全支持

**决策日志**：完整决策轨迹保存为 JSON（`results/{ticker}/TradingAgentsStrategy_logs/`）

## 5. 策略层

**策略类型**：非固定策略，而是**策略生成框架**
- 基本面驱动（Financial Analyst 评估内在价值）
- 技术面驱动（Market Analyst 选择最相关的 8 个指标）
- 情感驱动（Social Media Analyst 监测情绪反转）
- 宏观驱动（News Analyst 评估宏观环境）
- 多因子综合（Research Manager 综合各方）

**信号生成**（5 级评分）：
```python
# signal_processing.py
# BUY / OVERWEIGHT / HOLD / UNDERWEIGHT / SELL
def process_signal(full_signal: str) -> str:
    return llm.invoke([
        ("system", "Extract rating as exactly one of: BUY, OVERWEIGHT, HOLD, UNDERWEIGHT, SELL."),
        ("human", full_signal)
    ]).content
```

**辩论轮次控制**（conditional_logic.py）：
```python
def should_continue_debate(state) -> str:
    if state["investment_debate_state"]["count"] >= 2 * self.max_debate_rounds:
        return "Research Manager"  # 辩论结束
    if state["..."]["current_response"].startswith("Bull"):
        return "Bear Researcher"
    return "Bull Researcher"
```

## 6. 执行层

- **模式**：模拟交易（纸面决策），无实盘接口
- **下单**：Portfolio Manager 输出 5 级评分 + 执行摘要 + 投资论文，用户自行实现下单
- **头寸追踪**：通过 `reflect_and_remember(returns_losses)` 传递模拟 P&L
- **风控**：Risk Management 层评估决策风险，但无量化 VaR/CVaR

## 7. 亮点与可借鉴设计

1. **多 Agent 对抗辩论框架** ⭐⭐⭐⭐⭐：Bull vs Bear + Aggressive vs Conservative vs Neutral，动态轮次，避免单一视角盲点
2. **BM25 离线记忆系统** ⭐⭐⭐⭐⭐：无需向量数据库，本地 BM25 词法匹配，积累历史决策教训
3. **多 LLM 供应商适配** ⭐⭐⭐⭐：统一 BaseLLMClient 接口，支持 extended thinking / reasoning effort
4. **完整决策可追溯** ⭐⭐⭐⭐：全决策链路保存为 JSON，便于复盘和审计
5. **灵活的数据源路由** ⭐⭐⭐：类别级 + 工具级双层配置，支持按需升级数据源
6. **文化适配**：内部辩论用英文（推理质量），报告输出支持本地语言

## 8. 局限性与应避免的设计

| 问题 | 影响 | 建议 |
|------|------|------|
| 回测框架未完成 | backtrader 依赖存在但未实际使用 | 完整集成回测反馈循环 |
| 无实盘接口 | 仅纸面决策 | 集成 Broker 适配器 |
| 风险量化不足 | 无 VaR/CVaR/相关性分析 | 完整量化风控框架 |
| 提示词稳定性 | LLM 版本更新可能破坏输出格式 | 严格 Pydantic 输出验证 |
| 成本高 | 多轮辩论 × 深度模型，成本可观 | 严格控制轮次 + 快/慢模型分级 |
| A 股支持有限 | 国内用户无法完整使用 | 接入 Tushare/AKShare |
| 单股分析 | 无跨资产组合优化 | Portfolio 层面相关性分析 |

## 9. 对本系统的启示

**最值得采用**：
- 多 Agent 对抗辩论框架（分析→辩论→风险→执行）
- BM25 离线记忆（低成本历史决策积累）
- 多 LLM 供应商适配（不被单一模型锁定）
- 完整决策可追溯（JSON 日志 + 复盘能力）

**核心设计原则**：
- 对立观点碰撞 > 单一 Agent 决策
- 记忆驱动的持续改进 > 每次从零开始
- 快慢模型分级 > 全部使用最贵模型
