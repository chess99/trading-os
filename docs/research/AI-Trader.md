# AI-Trader 深度调研报告

> 仓库：https://github.com/HKUDS/AI-Trader
> 调研日期：2026-04-06

## 1. 定位与目标用户

- **核心定位**：AI Agent 驱动的交易信号市场 + 复制交易平台（SaaS）
- **目标用户**：AI Agent 开发者、信号提供者、跟单用户
- **人的角色**：
  - 信号提供者：发布买卖信号获积分
  - 信号跟随者：自动复制优秀交易者仓位
  - 分析者：参与社区讨论建立声誉

## 2. 系统架构

**技术栈**：FastAPI + SQLite/PostgreSQL + React + TypeScript

**核心目录**：
```
skills/
├── ai4trade/       # 主 SKILL 入口
├── copytrade/      # 复制交易（跟随者）
├── tradesync/      # 交易同步（提供者）
├── heartbeat/      # 消息轮询
└── market-intel/   # 市场情报
service/server/
├── routes.py       # API 路由（109KB）
├── price_fetcher.py # 行情获取
├── market_intel.py  # 市场情报聚合（53KB）
└── tasks.py        # 后台任务（PnL 计算、数据压缩）
```

**关键设计**：SKILL.md 驱动的 Agent 自动装配 + 分层 API（L1 基础 / L2 专业 / L3 管理）

## 3. AI/Agent 使用方式

**集成方式**：OpenClaw 兼容，Agent 读取 SKILL.md 自动解析并集成

**Agent 工作流**：
```python
# 注册 → 获取 token (claw_xxx)
# 发布信号
POST /api/signals/realtime {market, action, symbol, price, quantity, executed_at}
# 轮询消息（推荐 30-60 秒）
POST /api/claw/agents/heartbeat
```

**决策链路**：Agent 自主决策 → 调用 API 发布信号 → 平台广播给 followers → 自动复制仓位

**无 LLM 内置**：平台本身不做 AI 分析，Agent 自带策略逻辑

## 4. 数据来源与管理

| 市场 | 数据源 | 特点 |
|------|------|------|
| 美股 | Alpha Vantage | 按需查询，市场时间验证 |
| 加密 | Hyperliquid L2（公开，无 Key） | 实时 mid price |
| Polymarket | Gamma API + CLOB API（公开） | 预测市场 |
| A 股 | 框架支持，数据源待补充 | ❌ 未实现 |

**存储**：SQLite（开发）/ PostgreSQL（生产），支持多数据库抽象

**PnL 历史压缩**：最近 24h 保留分钟级，7天外按 15 分钟 bucket 聚合，超过 7 天删除

## 5. 策略层

**信号类型**：`position`（持仓快照）/ `trade`（已平仓）/ `strategy`（分析）/ `realtime`（实时操作）

**操作类型**：buy / sell / short / cover

**无回测框架**：只有前向纸币交易，无历史回测

## 6. 执行层

- **模式**：纸币交易（$100K 虚拟资金），无实盘接口
- **账户**：每 Agent 独立账户，积分可兑换虚拟资金（1点 = $1000）
- **复制跟单**：1:1 自动复制，仓位来源标注 `copied:{leader_id}`
- **市场时间验证**：美股强制 9:30-16:00 ET，加密/Polymarket 24/7

## 7. 亮点与可借鉴设计

1. **SKILL.md 驱动的能力组装** ⭐⭐⭐⭐⭐：Markdown 定义接口，Agent 自动发现集成，无需硬编码依赖
2. **分层 API 设计**：L1 基础 → L2 专业 → L3 管理，平缓学习曲线
3. **社交交易网络**：发布+讨论+信任+跟单，积分既是声誉也是可兑换资产
4. **多数据源透明接入**：统一 `get_price_from_market(symbol, market)` 接口
5. **PnL 历史压缩策略**：时间序列数据生命周期管理，防止数据表爆炸
6. **市场时间验证**：跨市场支持不同营业时间，防止无效下单
7. **Agent 身份管理**：token 而非密码，长期有效，便于审计撤销

## 8. 局限性与应避免的设计

| 问题 | 影响 | 建议 |
|------|------|------|
| 无回测框架 | 无法验证策略历史表现 | 必须有回测引擎 |
| 无实盘接口 | 跟单只是纸币 | 集成 Broker 适配器层 |
| 风控薄弱 | 无仓位限制、止损止盈、VaR | 企业级风控必须 |
| A 股完全缺失 | 国内用户无法使用 | 接入 Tushare/AKShare |
| 复制跟单不灵活 | 1:1 固定，无自定义比例 | 支持 copy_ratio、max_position_size |
| 消息系统不可靠 | HTTP Poll 可能丢消息 | 消息队列（Redis/RabbitMQ）替代 |

## 9. 对本系统的启示

**最值得采用**：
- SKILL.md 驱动的模块化能力设计（直接适用于 Claude Code）
- 分层 API 设计思路
- 统一数据源接口模式

**需要超越**：
- 加入完整回测引擎
- 支持 A 股市场
- 企业级风控（VaR、止损止盈、相关性分析）
- 可靠消息系统
