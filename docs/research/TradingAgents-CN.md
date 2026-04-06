# TradingAgents-CN 深度调研报告

> 仓库：https://github.com/hsliuping/TradingAgents-CN
> 调研日期：2026-04-06

## 1. 定位与目标用户

- **核心定位**：多 Agent 股票分析框架（学习与研究平台），13,000+ Stars
- **目标用户**：学生、量化研究员、AI 应用爱好者
- **人的角色**：被动观察者 → 主动学习者；强调过程透明和可观察性，而非黑盒决策

## 2. 系统架构

**技术栈**：FastAPI + Vue 3 + MongoDB + Redis + LangGraph + LangChain

**核心目录**：
```
tradingagents/
├── agents/         # 分析师、研究员、交易员、风险经理
├── graph/          # LangGraph 编排（trading_graph.py 1397行）
├── dataflows/      # 数据获取（interface.py 77KB，data_source_manager.py 113KB）
└── llm_adapters/   # LLM 提供商适配器
app/
├── routers/        # API 路由（analysis.py 1258行，paper.py 1200行）
└── worker/         # 异步任务执行
```

**核心设计**：三层架构（数据层 → Agent 层 → 编排层）+ 状态机驱动

## 3. AI/Agent 使用方式

**框架**：LangGraph 编排多 Agent

**支持 LLM**：OpenAI、阿里百炼、百度千帆、智谱 AI、DeepSeek、Gemini、Claude、Ollama

**多 Agent 分工**（关键设计）：

```
并行分析阶段：
  市场分析师 | 基本面分析师 | 新闻分析师 | 社交媒体分析师
         ↓
辩论阶段（可配置轮次）：
  看涨研究员 vs 看跌研究员 → 研究经理仲裁
         ↓
风险评估阶段：
  激进分析师 | 保守分析师 | 中立分析师 → 风险经理
         ↓
执行阶段：
  交易员 → final_trade_decision（含置信度、目标价、止损止盈）
```

**记忆系统**：ChromaDB 向量数据库，存储历史决策，通过相似性检索改进未来决策

**混合 LLM 模式**：快速模型（预处理）+ 深度模型（复杂分析），成本优化

## 4. 数据来源与管理

**多源自动降级**：MongoDB 本地 → Tushare → AKShare → BaoStock

**支持市场**：A 股（Tushare/AKShare/BaoStock）、港股（Yahoo Finance）、美股（Yahoo Finance/Finnhub）

**三层缓存**：文件缓存 → MongoDB 缓存 → Redis 缓存

| 数据类型 | 过期时间 |
|---------|---------|
| 日线数据 | 5天 |
| 基本面数据 | 30天 |
| 新闻数据 | 1天 |

## 5. 策略层

**分析框架**（非固定策略）：技术分析 + 基本面 + 事件分析 + 情绪分析 → 综合评分

**纸币交易系统**（`app/routers/paper.py`）：
- 多账户多货币（CNY/HKD/USD）
- 自动市场检测（000001 → CN，0700 → HK，AAPL → US）
- 实时 PnL 计算

**决策输出**：
```json
{
  "recommendation": "BUY|SELL|HOLD",
  "confidence": 85,
  "target_price": 120.5,
  "stop_loss": 110,
  "take_profit": 130,
  "risk_score": 6,
  "key_drivers": [...]
}
```

## 6. 执行层

- **模式**：纸币交易（模拟），无实盘接口
- **REST API**：`POST /paper/orders`，`GET /paper/positions`，`GET /paper/performance`
- **账户**：MongoDB 存储，支持多市场多货币

## 7. 亮点与可借鉴设计

1. **分层决策制度** ⭐⭐⭐⭐⭐：分析→辩论→风险→执行，避免单一视角盲点
2. **对立观点碰撞**：看涨 vs 看跌研究员，产生更深层认知
3. **数据自动降级**：多源冗余，系统鲁棒性强
4. **工具链降级**：每个分析维度有首选/备选/离线三个工具
5. **记忆反思系统**：Agent 从历史决策中学习，持续改进
6. **可观测性**：每个节点计时，生成性能报告，便于定位瓶颈
7. **提示词动态生成**：根据市场类型（A股/港股/美股）调整货币单位和分析视角

## 8. 局限性与应避免的设计

| 问题 | 具体表现 | 建议 |
|------|---------|------|
| 单向分析流程 | 某 Agent 出错影响全链路，无反馈循环 | 加入中断点和恢复机制 |
| LLM 幻觉 | 目标价格等关键数字可能无数据支撑 | 先计算基本面估值，LLM 只做调整解释 |
| 分析延迟 | 完整分析耗时 1-2 分钟 | 异步流水线，先返回初步结果 |
| 过度参数化 | 50+ 配置参数，用户不知调什么 | 提供 `analysis_depth: normal/fast/deep` 高层抽象 |
| 黑盒决策 | 只返回 BUY/SELL，理由不透明 | 必须包含 reasoning、key_factors、confidence_breakdown |

## 9. 对本系统的启示

**最值得采用**：
- 多 Agent 分层决策架构（分析→辩论→风险→执行）
- 数据自动降级机制
- 记忆反思系统（ChromaDB）
- 可观测性设计（每步计时、决策链路日志）

**核心设计原则**：
- 让 AI 辅助人的决策，而非替代人的判断
- 完整可观测性是建立信任的基础
- 对立观点碰撞 > 单一 Agent 决策
