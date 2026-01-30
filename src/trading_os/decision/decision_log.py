"""
决策记录系统

记录所有投资分析、决策和操作，提供完整的审计追溯
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class DecisionType(str, Enum):
    """决策类型"""
    MARKET_ANALYSIS = "market_analysis"      # 市场分析
    STOCK_SCREENING = "stock_screening"      # 股票筛选
    BUY_DECISION = "buy_decision"            # 买入决策
    SELL_DECISION = "sell_decision"          # 卖出决策
    HOLD_DECISION = "hold_decision"          # 持有决策
    RISK_ASSESSMENT = "risk_assessment"      # 风险评估
    PORTFOLIO_REBALANCE = "portfolio_rebalance"  # 组合再平衡


class DecisionStatus(str, Enum):
    """决策状态"""
    PROPOSED = "proposed"      # 提议
    APPROVED = "approved"      # 批准
    REJECTED = "rejected"      # 拒绝
    EXECUTED = "executed"      # 已执行
    CANCELLED = "cancelled"    # 已取消


@dataclass
class DecisionRecord:
    """决策记录"""
    decision_id: str
    timestamp: datetime
    decision_type: DecisionType
    status: DecisionStatus

    # 决策内容
    title: str
    description: str
    reasoning: str  # 决策理由和推理过程

    # 数据依据
    data_sources: List[str] = field(default_factory=list)
    market_data: Dict[str, Any] = field(default_factory=dict)
    analysis_results: Dict[str, Any] = field(default_factory=dict)

    # 风险评估
    risk_level: str = "medium"  # low, medium, high
    risk_factors: List[str] = field(default_factory=list)
    expected_return: Optional[float] = None
    expected_risk: Optional[float] = None

    # 执行信息
    target_symbols: List[str] = field(default_factory=list)
    target_amount: Optional[float] = None
    execution_time: Optional[datetime] = None
    execution_result: Optional[Dict[str, Any]] = None

    # 审批信息
    approved_by: Optional[str] = None
    approval_time: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    # 后续跟踪
    follow_up_notes: List[str] = field(default_factory=list)
    actual_return: Optional[float] = None
    review_time: Optional[datetime] = None

    def to_dict(self) -> dict:
        """转换为字典"""
        d = asdict(self)
        d['timestamp'] = self.timestamp.isoformat()
        d['decision_type'] = self.decision_type.value
        d['status'] = self.status.value
        if self.execution_time:
            d['execution_time'] = self.execution_time.isoformat()
        if self.approval_time:
            d['approval_time'] = self.approval_time.isoformat()
        if self.review_time:
            d['review_time'] = self.review_time.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> DecisionRecord:
        """从字典创建"""
        data = data.copy()
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        data['decision_type'] = DecisionType(data['decision_type'])
        data['status'] = DecisionStatus(data['status'])
        if data.get('execution_time'):
            data['execution_time'] = datetime.fromisoformat(data['execution_time'])
        if data.get('approval_time'):
            data['approval_time'] = datetime.fromisoformat(data['approval_time'])
        if data.get('review_time'):
            data['review_time'] = datetime.fromisoformat(data['review_time'])
        return cls(**data)


class DecisionLogger:
    """
    决策记录器

    功能:
    1. 记录所有投资决策
    2. 记录分析依据和推理过程
    3. 记录风险评估
    4. 记录执行结果
    5. 提供查询和复盘功能
    """

    def __init__(self, data_dir: Path):
        """
        初始化决策记录器

        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = data_dir / "decisions"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.decisions_file = self.data_dir / "decisions.jsonl"
        self.decisions: List[DecisionRecord] = []

        # 加载历史决策
        self._load_decisions()

        logger.info(f"决策记录器初始化完成，数据目录: {self.data_dir}")

    def log_decision(
        self,
        decision_type: DecisionType,
        title: str,
        description: str,
        reasoning: str,
        data_sources: List[str],
        market_data: Dict[str, Any] = None,
        analysis_results: Dict[str, Any] = None,
        risk_level: str = "medium",
        risk_factors: List[str] = None,
        target_symbols: List[str] = None,
        target_amount: Optional[float] = None,
        expected_return: Optional[float] = None,
        expected_risk: Optional[float] = None,
    ) -> DecisionRecord:
        """
        记录决策

        Args:
            decision_type: 决策类型
            title: 标题
            description: 描述
            reasoning: 决策理由
            data_sources: 数据来源
            market_data: 市场数据
            analysis_results: 分析结果
            risk_level: 风险等级
            risk_factors: 风险因素
            target_symbols: 目标股票
            target_amount: 目标金额
            expected_return: 预期收益
            expected_risk: 预期风险

        Returns:
            决策记录
        """
        decision_id = f"DEC_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        decision = DecisionRecord(
            decision_id=decision_id,
            timestamp=datetime.now(),
            decision_type=decision_type,
            status=DecisionStatus.PROPOSED,
            title=title,
            description=description,
            reasoning=reasoning,
            data_sources=data_sources or [],
            market_data=market_data or {},
            analysis_results=analysis_results or {},
            risk_level=risk_level,
            risk_factors=risk_factors or [],
            target_symbols=target_symbols or [],
            target_amount=target_amount,
            expected_return=expected_return,
            expected_risk=expected_risk,
        )

        self.decisions.append(decision)
        self._save_decision(decision)

        logger.info(f"记录决策: {decision_id} - {title}")
        return decision

    def approve_decision(
        self,
        decision_id: str,
        approved_by: str = "董事长"
    ) -> Optional[DecisionRecord]:
        """
        批准决策

        Args:
            decision_id: 决策ID
            approved_by: 批准人

        Returns:
            更新后的决策记录
        """
        decision = self.get_decision(decision_id)
        if not decision:
            logger.warning(f"决策不存在: {decision_id}")
            return None

        decision.status = DecisionStatus.APPROVED
        decision.approved_by = approved_by
        decision.approval_time = datetime.now()

        self._update_decision(decision)
        logger.info(f"决策已批准: {decision_id}")
        return decision

    def reject_decision(
        self,
        decision_id: str,
        reason: str
    ) -> Optional[DecisionRecord]:
        """
        拒绝决策

        Args:
            decision_id: 决策ID
            reason: 拒绝理由

        Returns:
            更新后的决策记录
        """
        decision = self.get_decision(decision_id)
        if not decision:
            logger.warning(f"决策不存在: {decision_id}")
            return None

        decision.status = DecisionStatus.REJECTED
        decision.rejection_reason = reason

        self._update_decision(decision)
        logger.info(f"决策已拒绝: {decision_id} - {reason}")
        return decision

    def record_execution(
        self,
        decision_id: str,
        execution_result: Dict[str, Any]
    ) -> Optional[DecisionRecord]:
        """
        记录执行结果

        Args:
            decision_id: 决策ID
            execution_result: 执行结果

        Returns:
            更新后的决策记录
        """
        decision = self.get_decision(decision_id)
        if not decision:
            logger.warning(f"决策不存在: {decision_id}")
            return None

        decision.status = DecisionStatus.EXECUTED
        decision.execution_time = datetime.now()
        decision.execution_result = execution_result

        self._update_decision(decision)
        logger.info(f"记录执行结果: {decision_id}")
        return decision

    def add_follow_up(
        self,
        decision_id: str,
        note: str
    ) -> Optional[DecisionRecord]:
        """
        添加跟踪记录

        Args:
            decision_id: 决策ID
            note: 跟踪记录

        Returns:
            更新后的决策记录
        """
        decision = self.get_decision(decision_id)
        if not decision:
            logger.warning(f"决策不存在: {decision_id}")
            return None

        decision.follow_up_notes.append(f"[{datetime.now().isoformat()}] {note}")
        self._update_decision(decision)
        logger.info(f"添加跟踪记录: {decision_id}")
        return decision

    def get_decision(self, decision_id: str) -> Optional[DecisionRecord]:
        """获取决策记录"""
        for decision in self.decisions:
            if decision.decision_id == decision_id:
                return decision
        return None

    def query_decisions(
        self,
        decision_type: Optional[DecisionType] = None,
        status: Optional[DecisionStatus] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[DecisionRecord]:
        """
        查询决策记录

        Args:
            decision_type: 决策类型
            status: 决策状态
            start_date: 开始日期
            end_date: 结束日期
            limit: 返回数量限制

        Returns:
            决策记录列表
        """
        results = self.decisions.copy()

        # 过滤
        if decision_type:
            results = [d for d in results if d.decision_type == decision_type]
        if status:
            results = [d for d in results if d.status == status]
        if start_date:
            results = [d for d in results if d.timestamp >= start_date]
        if end_date:
            results = [d for d in results if d.timestamp <= end_date]

        # 按时间倒序排序
        results.sort(key=lambda x: x.timestamp, reverse=True)

        # 限制数量
        if limit:
            results = results[:limit]

        return results

    def generate_decision_report(
        self,
        decision_id: str
    ) -> Optional[str]:
        """
        生成决策报告

        Args:
            decision_id: 决策ID

        Returns:
            决策报告文本
        """
        decision = self.get_decision(decision_id)
        if not decision:
            return None

        lines = [
            "=" * 70,
            f"决策报告: {decision.title}",
            "=" * 70,
            f"决策ID: {decision.decision_id}",
            f"决策类型: {decision.decision_type.value}",
            f"决策状态: {decision.status.value}",
            f"记录时间: {decision.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "📝 决策描述:",
            decision.description,
            "",
            "🤔 决策理由:",
            decision.reasoning,
            "",
            "📊 数据来源:",
        ]

        for source in decision.data_sources:
            lines.append(f"  - {source}")

        lines.extend([
            "",
            f"⚠️ 风险等级: {decision.risk_level}",
            "风险因素:",
        ])

        for factor in decision.risk_factors:
            lines.append(f"  - {factor}")

        if decision.target_symbols:
            lines.extend([
                "",
                "🎯 目标股票:",
            ])
            for symbol in decision.target_symbols:
                lines.append(f"  - {symbol}")

        if decision.target_amount:
            lines.append(f"\n💰 目标金额: {decision.target_amount:,.2f} 元")

        if decision.expected_return is not None:
            lines.append(f"📈 预期收益: {decision.expected_return:.2%}")

        if decision.expected_risk is not None:
            lines.append(f"📉 预期风险: {decision.expected_risk:.2%}")

        if decision.status == DecisionStatus.APPROVED:
            lines.extend([
                "",
                f"✅ 批准人: {decision.approved_by}",
                f"批准时间: {decision.approval_time.strftime('%Y-%m-%d %H:%M:%S')}",
            ])

        if decision.status == DecisionStatus.REJECTED:
            lines.extend([
                "",
                f"❌ 拒绝理由: {decision.rejection_reason}",
            ])

        if decision.execution_result:
            lines.extend([
                "",
                "🔧 执行结果:",
                json.dumps(decision.execution_result, indent=2, ensure_ascii=False),
            ])

        if decision.follow_up_notes:
            lines.extend([
                "",
                "📌 跟踪记录:",
            ])
            for note in decision.follow_up_notes:
                lines.append(f"  {note}")

        lines.append("=" * 70)

        return "\n".join(lines)

    def _save_decision(self, decision: DecisionRecord) -> None:
        """保存决策记录"""
        try:
            with open(self.decisions_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(decision.to_dict(), ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"保存决策记录失败: {e}")

    def _update_decision(self, decision: DecisionRecord) -> None:
        """更新决策记录"""
        # 重写整个文件
        try:
            with open(self.decisions_file, 'w', encoding='utf-8') as f:
                for d in self.decisions:
                    f.write(json.dumps(d.to_dict(), ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"更新决策记录失败: {e}")

    def _load_decisions(self) -> None:
        """加载历史决策"""
        if not self.decisions_file.exists():
            return

        try:
            with open(self.decisions_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        decision = DecisionRecord.from_dict(data)
                        self.decisions.append(decision)

            logger.info(f"加载了 {len(self.decisions)} 条决策记录")
        except Exception as e:
            logger.error(f"加载决策记录失败: {e}")


def get_default_decision_logger() -> DecisionLogger:
    """
    获取默认决策记录器

    Returns:
        决策记录器实例
    """
    from pathlib import Path
    data_dir = Path.cwd() / "data"
    return DecisionLogger(data_dir)
