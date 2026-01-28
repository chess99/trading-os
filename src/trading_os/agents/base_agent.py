"""
Agent基类定义

定义了所有基金管理Agent的基础接口和通用功能
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any
import logging
from pathlib import Path

from ..journal.event_log import EventLogger


@dataclass
class AgentMessage:
    """Agent间通信消息"""
    from_agent: str
    to_agent: str
    message_type: str  # 'report', 'request', 'alert', 'decision'
    content: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    priority: str = 'normal'  # 'low', 'normal', 'high', 'urgent'


@dataclass
class AgentReport:
    """Agent工作报告"""
    agent_name: str
    report_type: str  # 'daily', 'weekly', 'alert', 'decision'
    content: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    recommendations: List[str] = field(default_factory=list)
    alerts: List[str] = field(default_factory=list)


@dataclass
class AgentDecision:
    """Agent决策记录"""
    agent_name: str
    decision_type: str
    decision: str
    reasoning: str
    confidence: float  # 0.0 - 1.0
    data_sources: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class BaseAgent(ABC):
    """
    基金管理Agent基类

    所有具体的Agent都继承自这个基类，提供统一的接口和通用功能
    """

    def __init__(self, name: str, role: str, repo_root: Path):
        self.name = name
        self.role = role
        self.repo_root = repo_root
        self.logger = logging.getLogger(f"agent.{name}")
        self.event_logger = EventLogger(repo_root / "artifacts" / "agents" / f"{name}_events.jsonl")

        # Agent状态
        self.active = True
        self.last_update = datetime.now()
        self.message_inbox: List[AgentMessage] = []
        self.knowledge_base: Dict[str, Any] = {}

        # 确保事件日志目录存在
        self.event_logger.log_file.parent.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"Agent {name} ({role}) initialized")
        self.event_logger.log("agent_initialized", {
            "agent_name": name,
            "role": role,
            "timestamp": datetime.now().isoformat()
        })

    @abstractmethod
    def analyze(self, data: Dict[str, Any]) -> AgentReport:
        """
        分析数据并生成报告

        Args:
            data: 输入数据，格式由具体Agent定义

        Returns:
            AgentReport: 分析报告
        """
        pass

    @abstractmethod
    def make_recommendation(self, context: Dict[str, Any]) -> List[str]:
        """
        基于当前上下文提出建议

        Args:
            context: 决策上下文

        Returns:
            List[str]: 建议列表
        """
        pass

    def receive_message(self, message: AgentMessage):
        """接收来自其他Agent的消息"""
        self.message_inbox.append(message)
        self.logger.info(f"Received message from {message.from_agent}: {message.message_type}")

        self.event_logger.log("message_received", {
            "from_agent": message.from_agent,
            "message_type": message.message_type,
            "priority": message.priority,
            "timestamp": message.timestamp.isoformat()
        })

    def send_message(self, to_agent: str, message_type: str, content: Dict[str, Any], priority: str = 'normal') -> AgentMessage:
        """发送消息给其他Agent"""
        message = AgentMessage(
            from_agent=self.name,
            to_agent=to_agent,
            message_type=message_type,
            content=content,
            priority=priority
        )

        self.logger.info(f"Sending message to {to_agent}: {message_type}")
        self.event_logger.log("message_sent", {
            "to_agent": to_agent,
            "message_type": message_type,
            "priority": priority
        })

        return message

    def process_inbox(self) -> List[AgentMessage]:
        """处理收件箱中的消息"""
        messages = self.message_inbox.copy()
        self.message_inbox.clear()

        for message in messages:
            self._handle_message(message)

        return messages

    def _handle_message(self, message: AgentMessage):
        """处理单个消息 - 子类可以重写"""
        self.logger.info(f"Processing message: {message.message_type} from {message.from_agent}")

        # 默认处理逻辑 - 存储到知识库
        if message.message_type == 'report':
            self.knowledge_base[f"report_{message.from_agent}_{message.timestamp.isoformat()}"] = message.content
        elif message.message_type == 'alert':
            self.logger.warning(f"Alert from {message.from_agent}: {message.content}")

    def record_decision(self, decision_type: str, decision: str, reasoning: str,
                       confidence: float, data_sources: List[str] = None) -> AgentDecision:
        """记录决策"""
        agent_decision = AgentDecision(
            agent_name=self.name,
            decision_type=decision_type,
            decision=decision,
            reasoning=reasoning,
            confidence=confidence,
            data_sources=data_sources or []
        )

        self.event_logger.log("decision_made", {
            "decision_type": decision_type,
            "decision": decision,
            "reasoning": reasoning,
            "confidence": confidence,
            "data_sources": data_sources or []
        })

        self.logger.info(f"Decision recorded: {decision_type} - {decision}")
        return agent_decision

    def update_knowledge(self, key: str, value: Any):
        """更新知识库"""
        self.knowledge_base[key] = value
        self.event_logger.log("knowledge_updated", {
            "key": key,
            "timestamp": datetime.now().isoformat()
        })

    def get_knowledge(self, key: str, default: Any = None) -> Any:
        """从知识库获取信息"""
        return self.knowledge_base.get(key, default)

    def generate_daily_report(self) -> AgentReport:
        """生成日报 - 子类应该重写"""
        return AgentReport(
            agent_name=self.name,
            report_type='daily',
            content={
                'status': 'active' if self.active else 'inactive',
                'last_update': self.last_update.isoformat(),
                'messages_processed': len(self.message_inbox),
                'knowledge_items': len(self.knowledge_base)
            }
        )

    def check_alerts(self) -> List[str]:
        """检查是否有需要发出的警报 - 子类应该重写"""
        return []

    def get_status(self) -> Dict[str, Any]:
        """获取Agent状态"""
        return {
            'name': self.name,
            'role': self.role,
            'active': self.active,
            'last_update': self.last_update.isoformat(),
            'inbox_count': len(self.message_inbox),
            'knowledge_items': len(self.knowledge_base)
        }

    def shutdown(self):
        """关闭Agent"""
        self.active = False
        self.logger.info(f"Agent {self.name} shutting down")
        self.event_logger.log("agent_shutdown", {
            "agent_name": self.name,
            "timestamp": datetime.now().isoformat()
        })