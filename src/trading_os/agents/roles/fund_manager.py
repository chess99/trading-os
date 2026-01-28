"""
基金经理角色实现

组合多个技能，实现基金经理的核心功能
"""

from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path

from ..core.agent_interface import Agent, AgentContext, AgentOutput
from ..skills.market_analysis import MarketTrendAnalysis, SectorAnalysis
from ..skills.risk_assessment import PortfolioRiskAssessment, MarketRiskMonitor
from ..core.message_types import InvestmentRecommendation, Message, MessageType, MessagePriority
from ...journal.event_log import EventLog


class FundManager(Agent):
    """
    基金经理角色

    负责投资决策和风险管理，协调各个技能模块
    """

    def __init__(self, repo_root: Path):
        # 初始化技能组合
        skills = [
            MarketTrendAnalysis(),
            SectorAnalysis(),
            PortfolioRiskAssessment(),
            MarketRiskMonitor()
        ]

        super().__init__("fund_manager", skills)

        self.repo_root = repo_root
        self.event_logger = EventLog(repo_root / "artifacts" / "agents" / "fund_manager.jsonl")

        # 决策参数
        self.max_position_weight = 0.20
        self.target_positions = 8  # 目标持仓数量
        self.rebalance_threshold = 0.05

        # 状态跟踪
        self.current_portfolio = {}
        self.pending_decisions = []

    def process(self, context: AgentContext) -> List[AgentOutput]:
        """处理输入并生成投资决策"""
        outputs = []

        # 执行所有技能分析
        skill_outputs = self._execute_skills(context)
        outputs.extend(skill_outputs)

        # 基于技能输出做出投资决策
        investment_decisions = self._make_investment_decisions(skill_outputs, context)
        outputs.extend(investment_decisions)

        # 生成风险管理建议
        risk_management = self._generate_risk_management(skill_outputs, context)
        outputs.extend(risk_management)

        # 记录决策过程
        self._log_decision_process(skill_outputs, investment_decisions, risk_management)

        return outputs

    def _execute_skills(self, context: AgentContext) -> List[AgentOutput]:
        """执行所有技能"""
        outputs = []

        for skill in self.skills:
            if skill.validate_inputs(context):
                try:
                    output = skill.execute(context)
                    outputs.append(output)
                except Exception as e:
                    self._log_error(f"Skill {skill.__class__.__name__} failed: {e}")

        return outputs

    def _make_investment_decisions(self, skill_outputs: List[AgentOutput],
                                 context: AgentContext) -> List[AgentOutput]:
        """基于技能输出做出投资决策"""
        decisions = []

        # 获取市场分析结果
        market_analysis = self._get_skill_output(skill_outputs, "market_trend_analysis")
        sector_analysis = self._get_skill_output(skill_outputs, "sector_analysis")
        risk_assessment = self._get_skill_output(skill_outputs, "portfolio_risk_assessment")

        if not all([market_analysis, sector_analysis, risk_assessment]):
            return decisions

        # 生成投资建议
        recommendations = self._generate_investment_recommendations(
            market_analysis, sector_analysis, risk_assessment, context
        )

        if recommendations:
            decisions.append(AgentOutput(
                agent_id=self.agent_id,
                output_type="decision",
                content={
                    "investment_recommendations": recommendations,
                    "reasoning": self._explain_decision_reasoning(market_analysis, sector_analysis),
                    "confidence": self._calculate_decision_confidence(market_analysis, sector_analysis)
                },
                confidence=0.8,
                timestamp=datetime.now(),
                dependencies=["market_analysis", "sector_analysis", "risk_assessment"]
            ))

        return decisions

    def _generate_risk_management(self, skill_outputs: List[AgentOutput],
                                context: AgentContext) -> List[AgentOutput]:
        """生成风险管理建议"""
        risk_outputs = []

        # 获取风险评估结果
        portfolio_risk = self._get_skill_output(skill_outputs, "portfolio_risk_assessment")
        market_risk = self._get_skill_output(skill_outputs, "market_risk_monitor")

        if portfolio_risk and market_risk:
            # 综合风险管理建议
            risk_management_actions = self._determine_risk_actions(portfolio_risk, market_risk)

            if risk_management_actions:
                risk_outputs.append(AgentOutput(
                    agent_id=self.agent_id,
                    output_type="alert",
                    content={
                        "risk_management_actions": risk_management_actions,
                        "urgency": self._assess_action_urgency(portfolio_risk, market_risk)
                    },
                    confidence=0.9,
                    timestamp=datetime.now(),
                    dependencies=["portfolio_risk", "market_risk"]
                ))

        return risk_outputs

    def _generate_investment_recommendations(self, market_analysis: AgentOutput,
                                           sector_analysis: AgentOutput,
                                           risk_assessment: AgentOutput,
                                           context: AgentContext) -> List[InvestmentRecommendation]:
        """生成具体的投资建议"""
        recommendations = []

        # 基于市场趋势信号
        trend_signals = market_analysis.content.get("trend_signals", [])
        for signal in trend_signals:
            if signal.strength > 0.7:  # 高信心信号
                recommendations.append(InvestmentRecommendation(
                    symbol=signal.symbol,
                    action=signal.signal_type,
                    target_allocation=self._calculate_target_allocation(signal, context),
                    reasoning=signal.reasoning,
                    confidence=signal.strength,
                    time_horizon="medium",
                    risk_level=self._assess_signal_risk(signal, risk_assessment)
                ))

        # 基于行业轮动
        leading_sectors = sector_analysis.content.get("leading_sectors", [])
        for sector in leading_sectors:
            sector_symbols = self._get_sector_symbols(sector)
            for symbol in sector_symbols[:2]:  # 每个行业选2只
                recommendations.append(InvestmentRecommendation(
                    symbol=symbol,
                    action="buy",
                    target_allocation=0.1,  # 10%配置
                    reasoning=f"行业{sector}表现领先",
                    confidence=0.7,
                    time_horizon="medium",
                    risk_level="medium"
                ))

        return recommendations[:5]  # 限制建议数量

    def _get_skill_output(self, skill_outputs: List[AgentOutput], agent_id: str) -> AgentOutput:
        """获取特定技能的输出"""
        for output in skill_outputs:
            if output.agent_id == agent_id:
                return output
        return None

    def _calculate_target_allocation(self, signal, context: AgentContext) -> float:
        """计算目标配置权重"""
        base_allocation = 0.15  # 基础15%配置

        # 根据信号强度调整
        allocation = base_allocation * signal.strength

        # 考虑风险限制
        return min(allocation, self.max_position_weight)

    def _assess_signal_risk(self, signal, risk_assessment: AgentOutput) -> str:
        """评估信号风险水平"""
        overall_risk = risk_assessment.content.get("overall_risk_level", "medium")

        if overall_risk == "high":
            return "high"
        elif signal.strength > 0.8:
            return "low"
        else:
            return "medium"

    def _get_sector_symbols(self, sector: str) -> List[str]:
        """获取行业内的股票代码"""
        sector_map = {
            'technology': ['AAPL', 'MSFT', 'GOOGL'],
            'finance': ['JPM', 'BAC', 'WFC'],
            'healthcare': ['JNJ', 'PFE', 'UNH']
        }
        return sector_map.get(sector, [])

    def _explain_decision_reasoning(self, market_analysis: AgentOutput,
                                  sector_analysis: AgentOutput) -> str:
        """解释决策推理"""
        market_phase = market_analysis.content.get("market_phase", "sideways")
        leading_sectors = sector_analysis.content.get("leading_sectors", [])

        reasoning = f"当前市场阶段: {market_phase}"
        if leading_sectors:
            reasoning += f", 领先行业: {', '.join(leading_sectors)}"

        return reasoning

    def _calculate_decision_confidence(self, market_analysis: AgentOutput,
                                     sector_analysis: AgentOutput) -> float:
        """计算决策信心度"""
        market_confidence = market_analysis.confidence
        sector_confidence = sector_analysis.confidence

        return (market_confidence + sector_confidence) / 2

    def _determine_risk_actions(self, portfolio_risk: AgentOutput,
                              market_risk: AgentOutput) -> List[str]:
        """确定风险管理行动"""
        actions = []

        # 从风险评估中提取建议
        risk_recommendations = portfolio_risk.content.get("risk_recommendations", [])
        actions.extend(risk_recommendations)

        # 从市场风险中提取警报
        market_alerts = market_risk.content.get("volatility_alerts", [])
        for alert in market_alerts:
            actions.extend(alert.recommended_actions)

        return list(set(actions))  # 去重

    def _assess_action_urgency(self, portfolio_risk: AgentOutput,
                             market_risk: AgentOutput) -> str:
        """评估行动紧急程度"""
        portfolio_risk_level = portfolio_risk.content.get("overall_risk_level", "low")
        market_stress = market_risk.content.get("market_stress_level", "low")

        if portfolio_risk_level == "high" or market_stress == "high":
            return "urgent"
        elif portfolio_risk_level == "medium" or market_stress == "medium":
            return "medium"
        else:
            return "low"

    def _log_decision_process(self, skill_outputs: List[AgentOutput],
                            investment_decisions: List[AgentOutput],
                            risk_management: List[AgentOutput]):
        """记录决策过程"""
        self.event_logger.write_obj("decision_process", {
            "skill_outputs_count": len(skill_outputs),
            "investment_decisions_count": len(investment_decisions),
            "risk_management_count": len(risk_management),
            "timestamp": datetime.now().isoformat()
        })

    def _log_error(self, error_message: str):
        """记录错误"""
        self.event_logger.write_obj("error", {
            "message": error_message,
            "timestamp": datetime.now().isoformat()
        })

    def create_board_report(self, context: AgentContext) -> Dict[str, Any]:
        """创建董事会报告"""
        skill_outputs = self._execute_skills(context)

        return {
            "report_date": datetime.now().isoformat(),
            "portfolio_summary": self._summarize_portfolio(context),
            "market_assessment": self._summarize_market_view(skill_outputs),
            "risk_analysis": self._summarize_risk_status(skill_outputs),
            "recent_decisions": self._summarize_recent_decisions(),
            "outlook": self._provide_outlook(skill_outputs)
        }

    def _summarize_portfolio(self, context: AgentContext) -> Dict[str, Any]:
        """总结投资组合状况"""
        portfolio_state = context.portfolio_state
        return {
            "total_positions": len(portfolio_state.get('positions', {})),
            "cash_position": portfolio_state.get('cash_position', 0),
            "largest_position": max(portfolio_state.get('positions', {}).values()) if portfolio_state.get('positions') else 0
        }

    def _summarize_market_view(self, skill_outputs: List[AgentOutput]) -> str:
        """总结市场观点"""
        market_analysis = self._get_skill_output(skill_outputs, "market_trend_analysis")
        if market_analysis:
            return market_analysis.content.get("market_phase", "中性")
        return "数据不足"

    def _summarize_risk_status(self, skill_outputs: List[AgentOutput]) -> str:
        """总结风险状况"""
        risk_assessment = self._get_skill_output(skill_outputs, "portfolio_risk_assessment")
        if risk_assessment:
            return risk_assessment.content.get("overall_risk_level", "中等")
        return "未评估"

    def _summarize_recent_decisions(self) -> List[str]:
        """总结最近决策"""
        return self.pending_decisions[-5:]  # 最近5个决策

    def _provide_outlook(self, skill_outputs: List[AgentOutput]) -> str:
        """提供展望"""
        return "基于当前分析，维持谨慎乐观态度，关注市场变化"