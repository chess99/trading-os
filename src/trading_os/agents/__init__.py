"""
基金管理多Agent系统

这个包实现了一个完整的基金管理多agent协作系统，包括：
- 基金经理 (Fund Manager): 主决策者，负责投资策略和团队协调
- 研究分析师 (Research Analyst): 市场研究和投资建议
- 风控专员 (Risk Manager): 风险监控和合规检查
- 数据工程师 (Data Engineer): 数据采集和处理
- 交易执行专员 (Trade Executor): 交易执行和成本控制

每个Agent都具备自主决策能力，能够在预设框架内独立工作，
同时通过标准化的通信协议进行协作。
"""

from .roles.fund_manager import FundManager

__all__ = [
    'FundManager'
]