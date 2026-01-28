"""
Agent系统核心接口定义

定义所有Agent必须实现的基础接口
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Protocol
from dataclasses import dataclass
from datetime import datetime


@dataclass
class AgentContext:
    """Agent执行上下文"""
    timestamp: datetime
    market_data: Dict[str, Any]
    portfolio_state: Dict[str, Any]
    risk_metrics: Dict[str, Any]
    metadata: Dict[str, Any]


@dataclass
class AgentOutput:
    """Agent输出标准格式"""
    agent_id: str
    output_type: str  # 'analysis', 'recommendation', 'alert', 'decision'
    content: Dict[str, Any]
    confidence: float  # 0.0-1.0
    timestamp: datetime
    dependencies: List[str]  # 依赖的输入数据源


class Skill(Protocol):
    """技能接口协议"""

    def execute(self, context: AgentContext) -> AgentOutput:
        """执行技能"""
        ...

    def validate_inputs(self, context: AgentContext) -> bool:
        """验证输入是否满足技能要求"""
        ...


class Agent(ABC):
    """Agent基础接口"""

    def __init__(self, agent_id: str, skills: List[Skill]):
        self.agent_id = agent_id
        self.skills = skills
        self.active = True

    @abstractmethod
    def process(self, context: AgentContext) -> List[AgentOutput]:
        """处理输入并生成输出"""
        pass

    def get_capabilities(self) -> List[str]:
        """返回Agent能力列表"""
        return [skill.__class__.__name__ for skill in self.skills]

    def is_ready(self, context: AgentContext) -> bool:
        """检查Agent是否准备好处理请求"""
        return self.active and all(skill.validate_inputs(context) for skill in self.skills)