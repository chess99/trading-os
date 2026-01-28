"""
Agent系统消息和数据类型定义

定义Agent间通信的标准消息格式
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional
from enum import Enum


class MessagePriority(Enum):
    """消息优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class MessageType(Enum):
    """消息类型"""
    REQUEST = "request"
    RESPONSE = "response"
    ALERT = "alert"
    REPORT = "report"
    DECISION = "decision"


@dataclass
class Message:
    """Agent间通信消息"""
    id: str
    from_agent: str
    to_agent: str
    message_type: MessageType
    priority: MessagePriority
    content: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_id: Optional[str] = None  # 关联消息ID


@dataclass
class MarketSignal:
    """市场信号"""
    symbol: str
    signal_type: str  # 'buy', 'sell', 'hold'
    strength: float  # 0.0-1.0
    reasoning: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RiskAlert:
    """风险警报"""
    risk_type: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    description: str
    affected_positions: List[str]
    recommended_actions: List[str]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class InvestmentRecommendation:
    """投资建议"""
    symbol: str
    action: str  # 'buy', 'sell', 'hold', 'increase', 'decrease'
    target_allocation: float
    reasoning: str
    confidence: float
    time_horizon: str  # 'short', 'medium', 'long'
    risk_level: str  # 'low', 'medium', 'high'


@dataclass
class PortfolioSnapshot:
    """投资组合快照"""
    positions: Dict[str, float]  # symbol -> weight
    cash_position: float
    total_value: float
    unrealized_pnl: float
    timestamp: datetime = field(default_factory=datetime.now)