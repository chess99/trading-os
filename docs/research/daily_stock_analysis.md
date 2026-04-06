# daily_stock_analysis 深度调研报告

> 仓库：https://github.com/aceliuchanghong/daily_stock_analysis
> 调研日期：2026-04-06

## 1. 定位与目标用户

- **核心定位**：基于 AI 大模型的股票自动分析系统，面向自选股持有人的"个人基金经理助手"
- **目标用户**：个人散户（有自选股组合）、金融爱好者、中小量化团队
- **人的角色**：被动的决策辅助使用者（阅读 AI 分析报告），主动的策略配置人（自定义分析策略）；**不做实盘交易**，仅生成"带精确点位的分析意见"

## 2. 系统架构

**技术栈**：FastAPI + React 18 + SQLite + LiteLLM（多模型路由）+ APScheduler + Jinja2

**核心目录**：
```
daily_stock_analysis/
├── src/
│   ├── core/
│   │   ├── pipeline.py          # 主流程调度器（StockAnalysisPipeline）
│   │   ├── market_strategy.py   # 市场策略蓝图（CN 三段式 / US Regime）
│   │   ├── backtest_engine.py   # 回测评估引擎
│   │   └── trading_calendar.py  # 交易日历管理
│   ├── services/
│   │   ├── fundamental_service.py  # 基本面数据聚合（fail-open）
│   │   └── social_sentiment_service.py  # 社交舆情（美股）
│   ├── analyzer.py       # AI 分析层（LiteLLM 调用 + 完整性校验）
│   ├── stock_analyzer.py # 技术分析引擎（MA/趋势/量价）
│   ├── search_service.py # 新闻搜索聚合（5 种搜索引擎）
│   ├── notification.py   # 推送层（8+ 渠道）
│   ├── storage.py        # ORM 数据层（SQLAlchemy + SQLite）
│   ├── config.py         # 配置管理（250+ 环境变量）
│   └── agent/            # Agent 对话系统（多策略 + 工具调用）
│       ├── orchestrator.py  # 多 Agent 编排器
│       └── tools/           # 工具调用集
├── data_provider/        # 数据源适配层（6 层 Fallback）
│   ├── base.py           # DataFetcherManager（策略模式）
│   ├── akshare_fetcher.py, tushare_fetcher.py, yfinance_fetcher.py
│   ├── longbridge_fetcher.py  # 长桥优先策略（美/港股）
│   └── fundamental_adapter.py # 基本面数据转换
├── api/                  # FastAPI 服务层
├── bot/                  # 机器人集成层（Telegram/Discord 等）
├── apps/
│   ├── dsa-web/          # React + TypeScript 前端
│   └── dsa-desktop/      # Electron 桌面端
└── strategies/           # 交易策略库（YAML 驱动，12 个内置策略）
```

**核心设计**：策略模式（多数据源自动切换）+ 管道模式（数据流串联）+ 工厂模式（Agent 动态加载）+ 观察者模式（多渠道推送）

## 3. AI/Agent 使用方式

**LLM 集成**：LiteLLM 统一调用，支持 Gemini/Claude/GPT/DeepSeek/通义千问/Ollama

**决策链路**：
```
行情数据 + 新闻 + 基本面 + 社交舆情
  ↓
StockAnalysisPipeline.analyze()
  ↓
GeminiAnalyzer.analyze_stock() → litellm.completion()
  ↓
完整性校验 + 占位补全（check_content_integrity + apply_placeholder_fill）
  ↓
AnalysisResult 对象 → 多渠道推送
```

**Agent 策略问股系统**（`AGENT_MODE=true`）：
```
用户问题 → Orchestrator
  ├─ Technical Agent：获取行情、K线、技术指标
  ├─ Intel Agent：新闻搜索、舆情聚合、基本面
  ├─ Risk Agent：风险评估、账户限制检查
  ├─ Specialist Agent：应用选定的策略 Skill
  └─ Decision Agent：综合生成最终建议
```

**YAML 驱动策略**（12 个内置，无需编码）：
```yaml
# bull_trend.yaml
name: bull_trend
instructions: |
  1. MA5 > MA10 > MA20 判断多头
  2. 乖离率 < 5% 时才入场
  3. 放量突破关键阻力加分
```

## 4. 数据来源与管理

**6 层 Fallback 架构**（DataFetcherManager）：

**A 股**（优先级顺序）：efinance（东方财富）→ AkShare → Tushare Pro → PyTDX → BaoStock → YFinance

**港股/美股**：Longbridge OpenAPI（若配置）→ YFinance → AkShare

**自动切换机制**：
```python
def get_price_data(stock_code):
    for fetcher in [efinance, akshare, tushare, pytdx, baostock, yfinance]:
        try:
            return fetcher.fetch_daily_data(stock_code)
        except Exception:
            logger.warning(f"{fetcher.name} failed, trying next...")
```

**基本面数据字段契约**：
- `valuation`（PE/PB/PSR）、`growth`（营收/利润增速）
- `earnings`（财报 + 分红）、`institution`（机构持仓）
- `capital_flow`（A 股主力资金）、`dragon_tiger`（龙虎榜）
- 超时 fail-open：不阻断主分析流程

**支持市场**：A 股、港股、美股、美股指数、北交所

**存储**：SQLite + SQLAlchemy ORM，增量更新，断点续传，交易日历校验

## 5. 策略层

**技术分析**（TrendAnalyzer）：
- MA5/MA10/MA20 多头排列判断
- 乖离率（BIAS）：与 MA5 偏离 > 5% 提示追高风险
- 量价分析：放量/缩量/量价配合
- 筹码分析（可选）：集中度、成本分布、获利盘/套牢盘

**市场复盘策略**：
- **CN 三段式**：趋势结构 → 资金情绪 → 主线板块 → 进攻/均衡/防守决策框架
- **US Regime 策略**：Momentum/Range/Risk-off 三种制度 + 宏观叙事

**交易纪律内置化（7 条核心规则）**：
1. 严禁追高（乖离率 > 5% 自动提示）
2. 趋势交易（MA5 > MA10 > MA20 才建议买入）
3. 精确点位（买入价/止损价/目标价）
4. 检查清单（每项条件标记满足/注意/不满足）
5. 新闻时效（利空新闻"一票否决"，默认 3 天时效）

**回测框架**（backtest_engine.py）：
- 评估窗口：1日/5日/20日可配置
- 指标：方向准确率、模拟收益率、止损触发率、目标价触发率
- Web 界面：AI 预测 vs 次日实际对比

## 6. 执行层

- **模式**：仅模拟/回测，不支持实盘交易（合规边界清晰）
- **持仓管理**：手动录入买卖，SQLite 存储，事件溯源模型（可回滚错单）
- **推送渠道**（8+ 种）：企业微信、飞书、Telegram、Discord、Slack、邮件 SMTP、Pushover、Server 酱
- **报告格式**：Simple（精简）/ Full（详细）/ Brief（3-5 句总结）

**决策输出结构**（AnalysisResult）：
```json
{
  "sentiment_score": 72,
  "operation_advice": "买入",
  "dashboard": {
    "core_conclusion": {"one_sentence": "多头排列+放量突破", "signal_type": "buy_weak"},
    "battle_plan": {
      "sniper_points": {"buy_price": 2180, "stop_loss": 2100, "target_price": 2300}
    }
  }
}
```

## 7. 亮点与可借鉴设计

1. **6 层 Fallback 数据架构** ⭐⭐⭐⭐⭐：快速源优先，自动切换，多市场差异化 API，生产级鲁棒性
2. **YAML 驱动无编码策略** ⭐⭐⭐⭐⭐：交易员/基金经理直接定义策略，Agent 自动解析执行，快速迭代
3. **完整性校验 + 占位补全** ⭐⭐⭐⭐：LLM 输出异常不导致报告失败，自动降级到合理占位符
4. **交易纪律内置化** ⭐⭐⭐⭐：核心规则强制执行，防止 AI 胡乱突破风控红线
5. **事件溯源持仓管理** ⭐⭐⭐⭐：不可篡改事件表 + 快照重放，支持错单回滚，完整审计链
6. **多 Agent 级联编排** ⭐⭐⭐：职能分离，并行处理，中间结果可缓存复用
7. **fail-open 降级策略**：可选数据（基本面/舆情）超时不阻断主流程

## 8. 局限性与应避免的设计

| 问题 | 影响 | 建议 |
|------|------|------|
| 无实盘交易能力 | 分析意见无法自动执行 | 需获得正规金融牌照后才可接入 |
| LLM 分析缺乏严格因果逻辑 | 可能循环论证 | AI 辅助决策，关键点位必须有计算逻辑支撑 |
| 国内数据源访问不稳定 | 网络阻断/限流 | 多源 Fallback + 代理 + 监控告警 |
| Agent 推理成本高 | 100 只股票/日 ≈ 500K~1M Tokens | 简单策略用规则引擎，Agent 仅用于复杂问题 |
| 配置参数过多 | 250+ 环境变量，用户容易迷失 | 合理默认值 + 极简启动配置 |
| 回测仅评估方向准确率 | 未考虑真实滑点/成本 | 精确建模交易成本 |

**应避免的设计模式**：
- 过度设计数据模型（从最小模型开始，需求驱动增量扩展）
- 主流程中串行调用过多外部 API（关键路径最小化，可选 API 异步+降级）
- 硬编码配置参数（通过环境变量 + 配置管理）
- 过度依赖单一 LLM（多供应商 + 自动 Fallback）

## 9. 对本系统的启示

**值得采用**：
- 6 层 Fallback 数据源架构（适配我们的数据层）
- YAML 驱动策略引擎（移植到定投/择时策略）
- 完整性校验 + 占位补全（报告生成的容错机制）
- 交易纪律内置化（风控限制嵌入，不可被 AI 突破）
- 事件溯源持仓管理（账户核心数据模型）
- fail-open 降级策略（可选数据不阻断主流程）

**核心教训**：
- 合规边界必须清晰（分析 vs 执行的责任隔离）
- AI 建议 + 人工确认 > 全自动执行
- 系统健壮性 = 多源 Fallback + 完整性校验 + 降级策略三位一体
