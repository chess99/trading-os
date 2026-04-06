# daily_stock_analysis 项目深度调研报告

> 仓库：https://github.com/ZhuLinsen/daily_stock_analysis
> 调研日期：2026-04-06
> 代码版本：本地 vendor 快照（review.md 导出日期 2026-03-19）

---

## 1. 定位与目标用户

**核心定位**：面向个人投资者的 A股/港股/美股自选股 AI 智能分析系统，每日自动分析并通过多渠道推送"决策仪表盘"。

**目标用户群体**：
- 主力用户：持有自选股、每日关注行情的个人散户投资者
- 次要用户：需要多股监控并快速筛选机会的小型私募/量化爱好者
- 技术用户：希望以零成本（GitHub Actions）或低成本方式运行 AI 选股的开发者

**人的角色**：
- 系统扮演"AI 分析师助手"角色，输出结构化的买卖建议，但最终决策权留给用户。
- 无法直接下单，所有建议都附有"仅供参考，不构成投资建议"免责声明。
- 系统对用户的最低门槛非常低——配置 STOCK_LIST 和一个 API Key 即可在 GitHub Actions 上零成本运行，不需要服务器。

## 2. 系统架构

### 技术栈

| 层次 | 技术选型 |
|------|---------|
| 语言/运行时 | Python 3.10+，asyncio + ThreadPoolExecutor 混合并发 |
| Web 框架 | FastAPI + Uvicorn |
| 前端 | Vue 3 + Vite（apps/dsa-web），Electron 桌面端（apps/dsa-desktop） |
| 存储 | SQLite（SQLAlchemy ORM，WAL 模式） |
| LLM 接入 | LiteLLM Router（统一调用 Gemini/OpenAI/Anthropic/Ollama） |
| 新闻搜索 | Tavily/SerpAPI/Bocha/Brave/MiniMax/SearXNG（多源冗余） |
| 数据推送 | 企微/飞书/Telegram/Discord/Slack/钉钉/Email/Pushover/PushPlus 等 |
| 自动化 | GitHub Actions（无服务器定时执行） |
| 容器 | Docker（docker/ 目录提供完整 compose 配置） |
| 桌面端 | Electron 打包（apps/dsa-desktop） |

### 核心目录结构

```
daily_stock_analysis/
├── main.py                  # CLI 主入口（分析/定时/服务模式统一调度）
├── server.py                # FastAPI 服务独立入口
├── src/
│   ├── analyzer.py          # GeminiAnalyzer：LiteLLM 调用 + 结果解析（2194行核心）
│   ├── core/
│   │   ├── pipeline.py      # StockAnalysisPipeline：主流程编排（断点续传/并发）
│   │   ├── market_review.py # 大盘复盘流程
│   │   ├── market_strategy.py # A股三段式/美股Regime策略蓝图
│   │   ├── trading_calendar.py # 交易日历（A/H/US三市场）
│   │   └── backtest_engine.py  # 历史分析准确率回测引擎
│   ├── agent/
│   │   ├── executor.py      # 单 Agent ReAct 执行器
│   │   ├── orchestrator.py  # 多 Agent 流水线编排（1575行）
│   │   ├── agents/          # 专业化子 Agent（technical/intel/risk/decision）
│   │   ├── tools/           # Agent 工具集（data/search/analysis/backtest/market）
│   │   └── skills/          # Skill 管理器（YAML策略加载/路由）
│   ├── services/            # 业务服务层（portfolio/backtest/history/task/image提取）
│   ├── repositories/        # 数据访问层（SQLAlchemy Repository模式）
│   ├── schemas/             # Pydantic/数据契约（report_schema等）
│   ├── notification.py      # 多渠道通知聚合
│   ├── storage.py           # SQLite ORM模型（StockDaily/AnalysisRecord等）
│   └── search_service.py    # 多源新闻搜索服务
├── data_provider/
│   ├── base.py              # BaseFetcher抽象基类 + DataFetcherManager（策略模式，2494行）
│   ├── akshare_fetcher.py   # AkShare适配器（A股主力）
│   ├── efinance_fetcher.py  # Efinance适配器
│   ├── tushare_fetcher.py   # Tushare适配器
│   ├── yfinance_fetcher.py  # YFinance适配器（美股）
│   ├── longbridge_fetcher.py # 长桥适配器（港美股优先）
│   ├── baostock_fetcher.py  # Baostock适配器
│   ├── pytdx_fetcher.py     # Pytdx适配器
│   └── tickflow_fetcher.py  # TickFlow适配器（A股大盘增强）
├── strategies/              # YAML格式策略技能（11种内置策略）
├── api/                     # FastAPI路由（v1 RESTful API）
├── bot/                     # 机器人接入（Telegram/Discord/飞书/钉钉 Stream）
├── apps/
│   ├── dsa-web/             # Vue 3 前端
│   └── dsa-desktop/         # Electron 桌面端
├── templates/               # Jinja2报告模板
└── docker/                  # Docker Compose配置
```

### 设计思路

- **面向可用性优先**：所有关键模块都有 fail-open 降级逻辑，单数据源/单 LLM/单通知渠道失败不中断主流程。
- **多运行模式统一**：一个 `main.py` 覆盖 CLI 单次/定时/Web 服务/仅大盘复盘/回测五种模式。
- **断点续传**：以"最新可复用交易日"为粒度缓存数据到 SQLite，避免重复拉取。
- **配置驱动**：所有能力（数据源、LLM 模型、推送渠道、策略）均可通过 `.env` 或 Web 设置页热更新，无需改代码。

## 3. AI/Agent 使用方式

### 集成方式

系统提供两条 AI 路径，通过 `AGENT_MODE` 和 `AGENT_ARCH` 配置切换：

**路径 A：传统 Prompt 路径（默认）**

```
数据获取 → 技术分析 → 新闻搜索 → 组装 Context → 单次 LiteLLM 调用 → JSON 解析
```

入口在 `src/analyzer.py` 的 `GeminiAnalyzer`，通过精心设计的 System Prompt 直接要求 LLM 输出完整的决策仪表盘 JSON，不使用工具调用。

**路径 B：Agent ReAct 路径（AGENT_MODE=true）**

分为单 Agent 和多 Agent 两种架构：

- **单 Agent**（`AGENT_ARCH=single`）：`AgentExecutor` 的 ReAct 循环，LLM 自主决定调用哪些工具（最多 `AGENT_MAX_STEPS` 步）。
- **多 Agent**（`AGENT_ARCH=multi`）：`AgentOrchestrator` 编排 Technical → Intel → Risk → Specialist → Decision 五阶段流水线，每个专业化 Agent 只获得与其职责匹配的工具子集，最终由 `DecisionAgent` 综合各阶段意见生成仪表盘。

### 决策链路

**多 Agent 流水线（完整模式）**：

```
用户请求（股票代码）
  ↓
AgentOrchestrator.run()
  ↓ [TechnicalAgent] max_steps=6
  工具: get_realtime_quote / get_daily_history / analyze_trend /
        calculate_ma / get_volume_analysis / analyze_pattern /
        get_chip_distribution / get_analysis_context
  → 输出: { signal, confidence, key_levels, trend_score, ma_alignment }
  ↓ [IntelAgent] max_steps=4
  工具: search_stock_news / search_comprehensive_intel /
        get_stock_info / get_capital_flow
  → 输出: { risk_alerts, positive_catalysts, sentiment_label, capital_flow_signal }
  ↓ [RiskAgent] max_steps=3  (full/specialist模式)
  ↓ [SpecialistAgent / SkillAgent] max_steps=4  (specialist模式)
  ↓ [DecisionAgent] max_steps=3，无工具访问
  综合上述各阶段 opinion → 输出完整决策仪表盘 JSON
  ↓
OrchestratorResult → AnalysisResult → 通知推送
```

**降级机制**：任一中间阶段超时或 JSON 解析失败时，Orchestrator 保留已完成阶段结果，通过 `_mark_partial_dashboard()` 标注降级信息，而非返回空报告。

### 关键 Prompt 结构

系统 Prompt 由多层拼接构成，按以下顺序组装：

1. **市场角色声明**：通过 `get_market_role()` 和 `get_market_guidelines()` 区分 A股/港股/美股投资视角
2. **工作流阶段约束**：强制要求按"行情/K线 → 技术/筹码 → 情报搜索 → 生成报告"四阶段顺序执行，禁止跨阶段合并调用
3. **默认技能基线**（`CORE_TRADING_SKILL_POLICY_ZH`）：严进策略（乖离率 <5% 才可入场）、多头排列、筹码效率、买点偏好等五条硬性规则
4. **激活的策略 Skills**：从 YAML 文件动态加载的策略指令注入（如缠论要求"判断一买/二买/三买买卖点"）
5. **输出格式 JSON Schema**：完整的决策仪表盘结构定义，包含字段说明和取值范围
6. **评分标准**：强烈买入/买入/观望/卖出的数值区间和条件矩阵

## 4. 数据来源与管理

### 数据源与路由策略

系统采用策略模式（`DataFetcherManager`），所有 Fetcher 注册统一优先级，失败自动切换：

| 市场 | 主数据源 | 备用数据源（fallback顺序） |
|------|---------|--------------------------|
| A股 K线 | Efinance | AkShare → Tushare → Pytdx → Baostock |
| A股实时行情 | Efinance | AkShare → Pytdx |
| A股大盘指数 | TickFlow（有Key时） | AkShare(EM→Sina) → Tushare |
| 港股 K线/实时 | Longbridge（有Key时） | AkShare |
| 美股 K线/实时 | Longbridge（有Key时） | YFinance |
| 美股指数 | YFinance（始终优先） | — |
| A股筹码分布 | AkShare | — |
| 新闻/舆情 | Tavily | SerpAPI → Bocha → Brave → MiniMax → SearXNG |
| 美股社交舆情 | Stock Sentiment API（Reddit/X/Polymarket） | — |

### 存储方式

- **SQLite + SQLAlchemy**：本地文件数据库，WAL 模式，所有分析历史持久化
- 核心 ORM 模型：
  - `StockDaily`：日线行情数据（date/open/high/low/close/volume/amount/pct_chg）
  - `AnalysisRecord`：每次分析结果（含完整 JSON dashboard 和 raw_response）
  - `BacktestResult`：AI 预测 vs 实际涨跌的回测评估记录
  - `BacktestSummary`：跨股票的准确率汇总
  - Portfolio 系列表：账户/交易流水/快照（FIFO/均值成本法）
- **断点续传**：以"最新可复用交易日"为锚，已有当日数据则跳过网络请求
- **LLM Token 用量追踪**：每次 LLM 调用记录 token 消耗，可按 call_type/model 汇总查询

### 支持市场

A 股（全面覆盖，含科创板/创业板/北交所）、港股（HK 前缀格式）、美股（NYSE/NASDAQ Ticker）及主要美股指数（SPX/DJI/IXIC 等）。

## 5. 策略层

### 支持策略类型

系统采用 YAML 文件定义策略，存放在 `strategies/` 目录，当前内置 11 种：

| 策略名 | 类型 | 核心逻辑 |
|--------|------|---------|
| bull_trend（默认） | trend | MA5>MA10>MA20 多头排列，回踩低吸 |
| ma_golden_cross | trend | 均线金叉信号 |
| chan_theory | framework | 缠论分型→笔→线段→中枢→背驰判断 |
| wave_theory | framework | 艾略特波浪五波三浪结构 |
| volume_breakout | momentum | 放量突破关键阻力 |
| shrink_pullback | pullback | 缩量回踩均线支撑 |
| dragon_head | momentum | 龙头股领涨跟随 |
| emotion_cycle | sentiment | 情绪周期识别（贪婪/恐慌） |
| one_yang_three_yin | pattern | 一阳吞三阴形态 |
| box_oscillation | range | 箱体震荡区间交易 |
| bottom_volume | reversal | 底部放量反转信号 |

每个 YAML 策略定义了：`name/display_name/description/category/required_tools/aliases/instructions`，以及 `sentiment_score` 调整建议（如"底背驰 + 一买信号：+15 分"）。

用户可在 `AGENT_SKILL_DIR` 下新建自定义 YAML 策略，无需修改代码。

### 回测框架

系统实现了"预测 vs 次日实际"的简单回测验证（1 日窗口）：

- `BacktestEngine`：从 `AnalysisRecord` 中取历史分析记录，与当时 AI 的 `decision_type`（buy/hold/sell）对照次日实际涨跌幅
- 评价指标：按 `neutral_band_pct`（默认 2%）划分中性区间，计算方向准确率
- 可按股票代码或日期范围筛选，Web 回测页有可视化展示
- 限制：这是"分析准确率验证"，不是真实策略回测（无仓位管理/手续费/滑点）

### 信号生成

- 传统路径：`StockTrendAnalyzer` 计算 MA5/MA10/MA20/MACD/RSI 后，将结构化结果注入 LLM Context，由 LLM 生成综合信号
- Agent 路径：TechnicalAgent 自主调用 `analyze_trend` 工具，以结构化 JSON opinion（`{ signal, confidence, trend_score }`）传递给 DecisionAgent 加权合成
- DecisionAgent 的信号权重：技术 40% + 情报情绪 30% + 风险标志 30%，存在 Skill 时各减 10% 换给 Skill 评估

## 6. 执行层

### 交易模式

系统为纯分析建议系统，**不具备实盘下单能力**。Portfolio 模块是纯本地账本记录（手工录入交易流水），用于持仓盈亏追踪，不与任何券商 API 对接下单。

### 通知推送（"软执行"机制）

系统以推送通知作为"提醒用户手动下单"的间接执行机制：

- 推送渠道：企微/飞书/Telegram/Discord/Slack/钉钉/Email/Pushover/PushPlus/Server酱/自定义 Webhook
- 推送格式：Markdown 决策仪表盘（可配置 `REPORT_TYPE: simple/full/brief`）
- 支持 Markdown→图片转换（wkhtmltoimage 或 markdown-to-file 引擎），改善移动端可读性
- 单股推送模式（`SINGLE_STOCK_NOTIFY=true`）：每分析完一只立即推送，而非汇总后统一推送

### 风控机制（分析层面）

系统在分析层面内置以下风控规则，作为 Prompt 硬性约束而非系统级熔断：

| 规则 | 实现方式 |
|------|---------|
| 严禁追高 | 乖离率 > BIAS_THRESHOLD（默认 5%）自动标注"观望"；强势趋势股自动放宽 |
| 趋势交易 | 系统 Prompt 硬性要求 MA5 > MA10 > MA20 才可建议买入 |
| 精确止损 | 要求输出买入价/止损价/目标价三要素 |
| 风险排查 | IntelAgent 专门检测减持/业绩预亏/监管处罚/大额解禁 |
| 超售保护 | Portfolio 卖出录入时校验可用持仓，超售直接拒绝（`PortfolioOversellError`） |

## 7. 亮点与可借鉴设计

### 极值得借鉴（五星）

1. **多 Agent 流水线编排（Technical → Intel → Risk → Decision）**：职责分离极为清晰，每个 Agent 只访问与职责匹配的工具子集，避免 Token 浪费和角色混乱。阶段性 JSON opinion 的传递协议（`AgentOpinion` dataclass）让下游 Agent 可以对上游意见进行加权，而不是混入全量对话历史。

2. **YAML 策略即代码（Strategy-as-Code）**：策略以 YAML 声明（含 `required_tools/aliases/instructions/scoring_delta`），完全解耦于 Python 代码，支持用户无代码扩展。这是一个极为实用的可扩展性设计。

3. **双路径降级（Prompt 路径 + Agent 路径）**：系统保留传统单次 LLM 调用路径，当 Agent 路径超时或出错时可自动降级，确保每只股票都能产出分析结果，可用性优先于完整性。

4. **LiteLLM Router 多模型负载均衡**：通过 `LLM_CHANNELS` 配置多个渠道，支持 Key 级别的 fallback，一处配置覆盖所有 LLM 提供商，对接任何 OpenAI 兼容 API。

5. **多数据源策略模式（DataFetcherManager）**：统一的 `BaseFetcher` 抽象，所有 Fetcher 注册优先级，任意数据源失败自动切换，数据层完全透明于上层逻辑。

### 值得借鉴（四星）

6. **报告完整性校验与自动补全**：`check_content_integrity()` 验证必填字段，缺失时可重试 LLM 或用占位符填充，而不是直接返回不可用报告，提升了用户体验。

7. **Vision LLM 智能导入（从截图识别股票代码）**：支持上传持仓截图，通过 Vision 模型提取代码+名称，降低自选股配置门槛，是一个对非技术用户极友好的 UX 设计。

8. **交易日历多市场感知**：同时感知 A/H/US 三个市场的交易日，非交易日自动跳过，精确到市场级别的股票过滤（而非全局 ON/OFF）。

9. **Orchestrator 预算控制**：Orchestrator 级别的 wall-clock timeout + stage 级别剩余预算传递，避免某个 Agent 阶段无限占用资源。超时后保留已完成阶段结果，而不是丢弃整个分析。

10. **飞书云文档集成**：分析完成后可自动创建飞书文档（`FeishuDocManager`），将仪表盘归档到团队知识库，比 IM 消息更易检索。

### 有参考价值（三星）

11. **A股三段式复盘策略蓝图**（`CN_BLUEPRINT`）：将市场复盘结构化为"趋势结构/资金情绪/主线板块"三个维度，每个维度有明确的检查点，比开放式 Prompt 更一致。

12. **多轮对话持久化 + 会话管理**：Agent 问股支持多轮追问，会话历史保存到 SQLite，支持导出为 `.md` 文件或发送到通知渠道。

## 8. 局限性与应避免的设计

| 缺陷 | 具体问题 | 对本系统的建议 |
|------|---------|--------------|
| 无真实回测引擎 | 所谓"回测"仅是"AI 预测 vs 次日涨跌"的方向准确率，无法验证策略在完整仓位管理下的 P&L 曲线，没有手续费/滑点/仓位模型 | 必须区分"AI 准确率监控"和"策略回测"，不可混淆 |
| 无实盘接口 | 系统无法自动下单，所有"执行"依赖用户手动操作 | 若需自动化，需接入长桥/富途 OpenAPI 等券商 API |
| SQLite 单点限制 | 多进程/多 worker 部署下认证状态不一致（README 已坦诚），SQLite WAL 在高并发写入下仍有竞争 | 分布式或高并发场景需迁移到 PostgreSQL |
| 筹码分布接口不稳定 | GitHub Actions 默认关闭筹码分布（`ENABLE_CHIP_DISTRIBUTION=false`），说明该接口可靠性欠佳 | 数据源稳定性不足时应有降级而非开关 |
| Prompt 漂移风险 | Prompt 在 `analyzer.py`/`executor.py`/多个 Agent 文件中分散维护，规则一致性依赖手工对齐；`review.md` 中已提及"能力漂移"问题 | 应有 Prompt 版本管理和一致性测试 |
| AI 决策黑盒 | Agent 的 `tool_calls_log` 虽然保存，但 Web UI 上没有清晰展示推理链路，用户难以理解 AI 为何给出该建议 | 在报告中展示决策依据分解（各维度评分贡献） |
| 定时任务无持久化 | Scheduler 依赖进程内 schedule 库，进程重启任务丢失；`review.md` 中标记为待修复问题 | 使用 APScheduler + 持久化 jobstore 或 Celery |
| 深度研究/事件监控不完整 | `review.md` 明确指出 Deep Research / EventMonitor 实现状态对齐不足，部分功能"看起来支持"但底层不完整 | 功能状态应在 UI 和文档中诚实呈现，避免功能幻觉 |
| 技术分析深度有限 | 内置 `StockTrendAnalyzer` 只做 MA/MACD/RSI，缺少布林带/KDJ/OBV 等更丰富指标；YAML 策略中的"缠论/波浪"分析实质是让 LLM 基于文字描述进行，缺乏算法级计算 | 需要真正的技术指标计算引擎（如 TA-Lib） |
| 长会话 Token 膨胀 | 多轮对话历史全量传入 LLM，未实现长会话裁剪；`review.md` 列为中长期治理项 | 应实现摘要压缩或滑动窗口策略 |
| 纯 LLM 判断可靠性 | 所有信号最终依赖 LLM 生成，LLM 可能"幻觉"技术位（README 中对"决策仪表盘"的精确点位有明显展示意味），但 LLM 实际不擅长精确数值推断 | 关键价格水平应由算法计算，LLM 只做叙事解释 |

## 9. 对本系统的启示

### 值得采用

**架构层面**：
- **多 Agent 流水线范式**（Technical → Intel → Risk → Decision）是目前最清晰的股票分析 Agent 拆解，可直接引入本系统，对应 `market-analysis` 和 `fund-management` skill 的分层。
- **YAML 策略即代码**：将交易策略描述从 Python 代码中解耦，用 YAML 声明 `required_tools/instructions/scoring_delta`，是策略管理的可持续设计，远优于硬编码 Prompt。
- **DataFetcherManager 策略模式**：统一 `BaseFetcher` 抽象 + 优先级 fallback，本系统的 `data_provider` 层可参考此设计实现多数据源透明切换。
- **报告完整性校验**：对 AI 输出做字段级完整性校验并触发重试，是生产级 AI 系统的标配。

**工程层面**：
- **LiteLLM Router + 多渠道 fallback**：本系统已在用，但 LLM Key 级别的负载均衡和 fallback 策略可以参考 DSA 的 `LLM_CHANNELS` 配置体系进一步完善。
- **断点续传机制**：以"最新可复用交易日"为粒度缓存，对定时任务的幂等性设计有很好的参考价值。
- **多运行模式统一入口**：CLI/定时/服务模式在一个 `main.py` 中统一，本系统可参考此组织方式。

**用户体验层面**：
- **A股三段式复盘策略蓝图**：结构化市场复盘的维度（趋势结构/资金情绪/主线板块）值得直接借鉴，与本系统的每日市场分析工作流高度匹配。
- **决策仪表盘 JSON Schema**：核心结论 + 数据透视 + 舆情情报 + 作战计划的四模块结构，是目前见到的最清晰的个股分析报告结构，值得作为本系统报告格式的参考。

### 需要超越

**能力层面**：
- **真实回测引擎**：DSA 的"回测"是 AI 预测准确率监控，本系统已有基于 DuckDB 的完整回测引擎，是实质性的超越。
- **实盘执行接口**：DSA 无下单能力，本系统若接入券商 API 则是量级差异的超越。
- **算法级技术分析**：DSA 的技术分析高度依赖 LLM 叙述（尤其是缠论/波浪），本系统应坚持算法计算（TA-Lib/pandas_ta），LLM 只做解释而不做计算。
- **投资组合级风控**：DSA 无 VaR/压力测试/相关性分析等组合级风控，本系统的 `portfolio_risk_service` 已是超越方向。

**数据层面**：
- **数据可靠性标准**：DSA 在 Actions 默认关闭筹码分布，说明对数据质量的容忍度较高。本系统要求严格的数据可靠性（禁止使用模拟数据），是正确的方向。
- **结构化基本面数据**：DSA 的基本面分析以新闻搜索 + LLM 总结为主，本系统若能接入财报数据库（Tushare Pro 的财务数据）则远超其基本面分析深度。

**架构层面**：
- **分布式数据存储**：DSA 使用 SQLite，本系统的 DuckDB + Parquet 数据湖架构在数据容量和分析性能上是数量级的超越。
- **确定性调度**：DSA 的 Scheduler 基于进程内 schedule 库，本系统应使用持久化调度（APScheduler + DB jobstore），确保重启不丢任务。
