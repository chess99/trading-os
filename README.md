# Trading OS - 基金管理AI系统

这是一套基于**Claude Code**构建的专业基金管理AI系统，将trading-os转变为一个完整的基金公司，其中Claude扮演专业基金经理角色，具备自主分析、决策和执行能力。

> 📋 **重要**: 请先阅读 [TRADING_OS_CHARTER.md](./TRADING_OS_CHARTER.md) 了解系统核心理念和工作方式

## 🎯 系统概述

### 核心特性
- ✅ **Claude Code标准架构**: 基于Skills和Sub-agents的专业设计
- ✅ **自主基金管理**: AI具备独立投资决策和风险管理能力
- ✅ **多Agent协作**: 专业化分工的Sub-agent系统
- ✅ **完整交易闭环**: 数据→研究→回测→执行→风控→复盘→迭代

### 角色定义
- **您(用户)**: 董事长/大股东，负责战略方向和重大决策拍板
- **Claude AI**: 专业基金经理团队，负责日常投资决策和风险管理

## 🚀 快速开始

### 1. 环境设置
```bash
cd /Users/zcs/code2/trading-os
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[data_lake]"
```

### 2. 启动Claude Code
```bash
# 在trading-os目录下启动Claude Code
claude

# 系统会自动加载基金管理AI身份和技能
```

### 3. 基础验证
```bash
# 验证基础系统
python -m trading_os --help
python -m trading_os paths

# 测试AI系统
python tests/test_agent_system.py

# 运行市场分析
python .claude/skills/market-analysis/scripts/market_analysis.py
```

## 🏗️ 系统架构

### Claude Code标准架构
```
.claude/
├── CLAUDE.md                 # 系统身份和上下文
├── settings.json            # 权限配置和环境设置
├── ROLE_DEFINITION.md       # 角色识别和切换指南
├── skills/                  # Skills技能包
│   ├── fund-management/     # 综合基金管理技能
│   └── market-analysis/     # 市场分析技能
└── agents/                  # Sub-agents专业AI
    ├── system-architect.md  # 首席技术官/系统架构师
    ├── fund-manager.md      # 基金经理
    ├── research-analyst.md  # 研究分析师
    └── risk-manager.md      # 风控专员
```

### Trading OS基础架构
```
src/trading_os/
├── data/                    # 数据层
│   ├── schema.py           # 统一数据结构
│   ├── lake.py             # DuckDB数据湖
│   └── sources/            # 数据源适配
├── backtest/               # 回测引擎
├── execution/              # 交易执行
├── risk/                   # 风险管理
├── journal/                # 事件日志和复盘
└── cli.py                  # CLI主入口
```

## 🎭 AI角色系统

Claude会根据您的需求自动选择合适的专业角色：

### 🏗️ 系统架构师/CTO
**适用场景**: 技术开发、系统优化、Bug修复
```bash
"优化系统性能"
"添加新功能"
"修复这个bug"
"重构代码架构"
```

### 💼 基金经理
**适用场景**: 投资决策、市场分析、风险管理
```bash
"分析今日市场"
"推荐投资标的"
"评估投资组合风险"
"制定投资策略"
```

### 📊 专业Sub-agents
```bash
# 调用专业分析师
"请research-analyst深度分析科技股机会"
"让risk-manager评估当前风险"
"用system-architect优化架构"
```

## 💡 使用示例

### 市场分析
```
📊 执行市场分析...

🌍 市场阶段: bull_market (momentum)
   信心度: 85.0%

💡 投资机会:
   1. NVDA: 92.0% - AI领域领导者
   2. MSFT: 88.0% - 云计算和AI受益
   3. GOOGL: 82.0% - 搜索+AI优势

🎯 投资建议:
   1. 适度增加风险敞口，关注成长股
   2. 重点配置科技、医疗行业
   3. 保持现金缓冲，准备回调加仓
```

## 🛠️ 系统功能

### Skills技能包
- **fund-management**: 投资组合管理、决策记录、董事会报告
- **market-analysis**: 技术分析、行业轮动、投资机会筛选

### 核心命令
```bash
# 数据可靠性检查 (开发前必须运行)
python scripts/data_reliability_check.py

# 数据状态检查
python -m trading_os agent status

# 市场分析
python .claude/skills/market-analysis/scripts/market_analysis.py

# 投资组合分析
python .claude/skills/fund-management/scripts/portfolio_metrics.py

# 传统CLI命令
python -m trading_os agent daily
python -m trading_os backtest-sma --symbol NASDAQ:AAPL
```

### 数据管理
```bash
# 初始化数据湖
python -m trading_os lake-init

# 获取数据
python -m trading_os fetch-yf --exchange NASDAQ --ticker AAPL

# 查询数据
python -m trading_os query-bars --symbols NASDAQ:AAPL
```

## 📈 投资功能

### 回测系统
```bash
# SMA策略回测
python -m trading_os backtest-sma --symbol NASDAQ:AAPL --fast 10 --slow 30

# 买入持有基准
python -m trading_os backtest-bh --symbol NASDAQ:AAPL
```

### 纸交易
```bash
# SMA策略纸交易
python -m trading_os paper-run-sma --symbol NASDAQ:AAPL --stop-loss 0.1
```

### 复盘分析
```bash
# 生成复盘报告
python -m trading_os draft-review --events artifacts/paper/events_NASDAQ_AAPL.jsonl
```

## ⚙️ 配置和扩展

### 环境配置
- `.claude/settings.json`: 权限、环境变量、hooks配置
- `pyproject.toml`: 项目依赖和配置
- `.env`: 环境变量(需要自行创建)

### 扩展指南
1. **新增Skills**: 在`.claude/skills/`下创建新技能包
2. **新增Agents**: 在`.claude/agents/`下定义新的专业AI
3. **自定义配置**: 修改`.claude/settings.json`中的权限和环境

## 🔒 重要声明

- **不构成投资建议**: 本系统仅用于研究与工程实践
- **风险自担**: 实盘前必须在纸交易中验证稳定性
- **严格风控**: 设置适当的风险限制和止损机制
- **数据可靠性**: 系统严格禁止使用模拟数据进行投资分析，详见 [数据可靠性标准](docs/DATA_RELIABILITY_STANDARDS.md)

## 📚 文档结构

- `FUND_MANAGEMENT_AI_README.md`: 详细的AI系统说明
- `docs/`: 系统文档和设计说明
- `.claude/ROLE_DEFINITION.md`: AI角色定义和切换指南
- `tests/`: 测试文件和验证脚本

## 🎯 下一步发展

### 已实现
- ✅ Claude Code标准架构
- ✅ 多Agent协作系统
- ✅ 完整的投资决策流程
- ✅ 风险管理和监控

### 计划中
- [ ] 实时数据源集成
- [ ] 机器学习模型集成
- [ ] Web界面开发
- [ ] 更多专业Sub-agents

这个系统将您的trading-os从工具集升级为具备自主决策能力的智能基金管理平台！