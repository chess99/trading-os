"""
基金管理多Agent系统

这个包实现了基于Claude Code标准架构的基金管理系统：
- Skills: 可复用的专业能力包 (fund-management, market-analysis)
- Sub-agents: 专业化的AI代理 (system-architect, fund-manager, research-analyst, risk-manager)
- CLI Integration: 与trading-os的完整集成

系统采用Claude Code的标准架构，支持Skills和Sub-agents的协作。
"""

# 导入CLI集成模块
from .cli_integration import AgentSystemCLI

__all__ = [
    'AgentSystemCLI'
]