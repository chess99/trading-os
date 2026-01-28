# 基金管理Agent系统

## 🎯 系统概述

这是一个基于trading-os构建的**自主基金管理Agent系统**。该系统将您的仓库转变为一个完整的基金公司，其中AI Agent扮演基金经理角色，具备自主分析、决策和执行能力。

## 🏗️ 架构设计

### 设计原则
- **模块化**: 每个文件专注单一职责，便于维护和扩展
- **组合优于继承**: 通过技能组合构建复杂功能
- **接口驱动**: 标准化的数据和通信接口
- **融合现有**: 基于trading-os现有架构，保持兼容性

### 目录结构
```
src/trading_os/agents/
├── core/                     # 核心抽象层
│   ├── agent_interface.py    # Agent基础接口
│   └── message_types.py      # 消息和数据类型定义
├── skills/                   # 可复用技能模块
│   ├── market_analysis.py    # 市场分析技能
│   └── risk_assessment.py    # 风险评估技能
├── roles/                    # 角色实现层
│   └── fund_manager.py       # 基金经理角色
└── cli_integration.py        # CLI集成
```

## 🤖 Agent角色

### 基金经理 (Fund Manager)
**职责**: 主决策者，负责投资策略制定和风险管理

**核心技能**:
- 市场趋势分析 (MarketTrendAnalysis)
- 行业分析 (SectorAnalysis)
- 投资组合风险评估 (PortfolioRiskAssessment)
- 市场风险监控 (MarketRiskMonitor)

**输出**:
- 投资决策和建议
- 风险管理措施
- 董事会报告
- 日常分析报告

## 🛠️ 使用方法

### CLI命令
```bash
# 运行日常分析
python -m trading_os agent daily

# 生成董事会报告
python -m trading_os agent board-report

# 获取投资建议
python -m trading_os agent recommend

# 评估投资组合风险
python -m trading_os agent risk
```

### 编程接口
```python
from trading_os.agents.cli_integration import AgentSystemCLI
from trading_os.paths import repo_root

# 初始化系统
agent_cli = AgentSystemCLI(repo_root())

# 运行分析
result = agent_cli.run_daily_analysis()
agent_cli.print_analysis_summary(result)
```

## 📊 示例输出

### 日常分析报告
```
==================================================
📈 基金经理AI分析报告
==================================================

🌍 市场分析:
  市场阶段: sideways
  情绪指数: 0.60
  分析信心: 80.0%

⚠️  风险评估:
  风险水平: low
  风险警报: 0 个
  评估信心: 85.0%

💡 投资决策:
  投资建议: 4 条
  决策推理: 当前市场阶段: sideways, 领先行业: technology, finance
  决策信心: 77.5%
```

### 投资建议示例
```
💡 投资建议 (4 条):
1. AAPL: buy (目标: 15.0%)
   推理: 价格呈上升趋势
   信心: 70.0%, 风险: medium

2. MSFT: buy (目标: 10.0%)
   推理: 行业technology表现领先
   信心: 70.0%, 风险: medium
```

## 🔧 技术特性

### 核心技能模块

#### 市场分析技能
- **MarketTrendAnalysis**: 趋势识别、技术指标、市场情绪
- **SectorAnalysis**: 行业轮动、相对表现、领先/落后行业

#### 风险管理技能
- **PortfolioRiskAssessment**: 仓位集中度、VaR计算、风险建议
- **MarketRiskMonitor**: 波动率监控、相关性分析、流动性风险

### 数据流
1. **输入**: 市场数据、投资组合状态、风险指标
2. **处理**: 各技能模块并行分析
3. **整合**: 基金经理综合各技能输出
4. **输出**: 投资决策、风险建议、分析报告

## 🚀 扩展指南

### 添加新技能
1. 在`agents/skills/`创建新技能模块
2. 继承`Skill`接口，实现`execute()`和`validate_inputs()`
3. 在基金经理中组合使用

```python
class NewSkill(Skill):
    def execute(self, context: AgentContext) -> AgentOutput:
        # 实现技能逻辑
        pass

    def validate_inputs(self, context: AgentContext) -> bool:
        # 验证输入数据
        pass
```

### 添加新角色
1. 在`agents/roles/`创建新角色
2. 继承`Agent`基类，组合所需技能
3. 实现角色特定的决策逻辑

### 自定义决策参数
在`FundManager`中调整:
- `max_position_weight`: 单一仓位最大权重
- `target_positions`: 目标持仓数量
- `rebalance_threshold`: 再平衡触发阈值

## 📈 测试验证

运行测试脚本验证系统功能:
```bash
python test_agent_system.py
```

预期输出:
- ✅ 基金经理初始化成功
- ✅ 分析完成，生成多个输出
- ✅ 董事会报告生成完成
- 🎉 所有测试通过！

## 🎯 下一步发展

### 已实现功能
- ✅ 模块化Agent架构
- ✅ 市场分析和风险评估技能
- ✅ 基金经理角色实现
- ✅ CLI集成和测试验证

### 待扩展功能
- [ ] 更多专业角色(研究分析师、数据工程师等)
- [ ] 实时数据源集成
- [ ] 机器学习模型集成
- [ ] 更复杂的投资策略
- [ ] 回测验证框架
- [ ] Web界面

## 💡 使用建议

1. **日常使用**: 每日运行`agent daily`获取市场分析
2. **重要决策**: 使用`agent recommend`获取投资建议
3. **风险监控**: 定期运行`agent risk`评估投资组合风险
4. **汇报沟通**: 使用`agent board-report`生成正式报告

这个系统将您的trading-os从工具集升级为具备自主决策能力的智能基金管理平台！