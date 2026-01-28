"""
风险评估技能模块

提供投资组合风险评估、风险监控等功能
"""

from datetime import datetime
from typing import Dict, List, Any
import logging

from ..core.agent_interface import AgentContext, AgentOutput, Skill
from ..core.message_types import RiskAlert


class PortfolioRiskAssessment(Skill):
    """投资组合风险评估技能"""

    def __init__(self, risk_thresholds: Dict[str, float] = None):
        self.logger = logging.getLogger(f"skill.{self.__class__.__name__}")
        self.risk_thresholds = risk_thresholds or {
            'max_position_weight': 0.20,  # 单一仓位最大权重
            'max_sector_weight': 0.40,    # 单一行业最大权重
            'max_drawdown': 0.15,         # 最大回撤
            'min_cash_buffer': 0.05,      # 最小现金缓冲
            'concentration_limit': 0.60   # 集中度限制
        }

    def execute(self, context: AgentContext) -> AgentOutput:
        """执行风险评估"""
        portfolio_state = context.portfolio_state
        risk_metrics = context.risk_metrics

        # 计算风险指标
        risk_analysis = self._calculate_risk_metrics(portfolio_state, risk_metrics)

        # 识别风险警报
        risk_alerts = self._identify_risk_alerts(risk_analysis)

        # 生成风险建议
        risk_recommendations = self._generate_risk_recommendations(risk_analysis)

        return AgentOutput(
            agent_id="portfolio_risk_assessment",
            output_type="analysis",
            content={
                "risk_metrics": risk_analysis,
                "risk_alerts": risk_alerts,
                "risk_recommendations": risk_recommendations,
                "overall_risk_level": self._assess_overall_risk(risk_analysis)
            },
            confidence=0.85,
            timestamp=datetime.now(),
            dependencies=["portfolio_state", "risk_metrics"]
        )

    def validate_inputs(self, context: AgentContext) -> bool:
        """验证输入数据"""
        return bool(context.portfolio_state and context.risk_metrics)

    def _calculate_risk_metrics(self, portfolio_state: Dict[str, Any],
                               risk_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """计算风险指标"""
        positions = portfolio_state.get('positions', {})

        # 计算仓位集中度
        position_weights = list(positions.values())
        max_position = max(position_weights) if position_weights else 0

        # 计算行业集中度
        sector_weights = self._calculate_sector_weights(positions)
        max_sector = max(sector_weights.values()) if sector_weights else 0

        # 计算组合波动率
        portfolio_volatility = self._calculate_portfolio_volatility(positions, risk_metrics)

        # 计算VaR
        var_95 = self._calculate_var(positions, risk_metrics, confidence=0.95)

        return {
            'max_position_weight': max_position,
            'max_sector_weight': max_sector,
            'portfolio_volatility': portfolio_volatility,
            'var_95': var_95,
            'cash_buffer': portfolio_state.get('cash_position', 0),
            'position_count': len(positions),
            'concentration_ratio': sum(sorted(position_weights, reverse=True)[:5])  # 前5大仓位
        }

    def _identify_risk_alerts(self, risk_analysis: Dict[str, Any]) -> List[RiskAlert]:
        """识别风险警报"""
        alerts = []

        # 检查仓位集中度
        if risk_analysis['max_position_weight'] > self.risk_thresholds['max_position_weight']:
            alerts.append(RiskAlert(
                risk_type="position_concentration",
                severity="high",
                description=f"单一仓位权重过高: {risk_analysis['max_position_weight']:.1%}",
                affected_positions=[],
                recommended_actions=["减少集中仓位", "增加分散投资"]
            ))

        # 检查行业集中度
        if risk_analysis['max_sector_weight'] > self.risk_thresholds['max_sector_weight']:
            alerts.append(RiskAlert(
                risk_type="sector_concentration",
                severity="medium",
                description=f"行业集中度过高: {risk_analysis['max_sector_weight']:.1%}",
                affected_positions=[],
                recommended_actions=["分散行业配置", "减少单一行业敞口"]
            ))

        # 检查现金缓冲
        if risk_analysis['cash_buffer'] < self.risk_thresholds['min_cash_buffer']:
            alerts.append(RiskAlert(
                risk_type="liquidity_risk",
                severity="medium",
                description=f"现金缓冲不足: {risk_analysis['cash_buffer']:.1%}",
                affected_positions=[],
                recommended_actions=["增加现金仓位", "提高流动性"]
            ))

        return alerts

    def _generate_risk_recommendations(self, risk_analysis: Dict[str, Any]) -> List[str]:
        """生成风险建议"""
        recommendations = []

        # 基于风险水平的建议
        if risk_analysis['portfolio_volatility'] > 0.20:
            recommendations.append("投资组合波动率偏高，建议增加低风险资产")

        if risk_analysis['concentration_ratio'] > 0.60:
            recommendations.append("投资组合过于集中，建议增加分散化")

        if risk_analysis['position_count'] < 5:
            recommendations.append("持仓数量较少，建议增加投资标的以分散风险")

        return recommendations

    def _assess_overall_risk(self, risk_analysis: Dict[str, Any]) -> str:
        """评估整体风险水平"""
        risk_score = 0

        # 集中度风险
        if risk_analysis['max_position_weight'] > 0.25:
            risk_score += 2
        elif risk_analysis['max_position_weight'] > 0.20:
            risk_score += 1

        # 波动率风险
        if risk_analysis['portfolio_volatility'] > 0.25:
            risk_score += 2
        elif risk_analysis['portfolio_volatility'] > 0.20:
            risk_score += 1

        # 流动性风险
        if risk_analysis['cash_buffer'] < 0.05:
            risk_score += 1

        if risk_score >= 4:
            return "high"
        elif risk_score >= 2:
            return "medium"
        else:
            return "low"

    def _calculate_sector_weights(self, positions: Dict[str, float]) -> Dict[str, float]:
        """计算行业权重"""
        # 简化的行业映射
        sector_mapping = {
            'AAPL': 'technology',
            'MSFT': 'technology',
            'GOOGL': 'technology',
            'JPM': 'finance',
            'BAC': 'finance',
            'JNJ': 'healthcare'
        }

        sector_weights = {}
        for symbol, weight in positions.items():
            sector = sector_mapping.get(symbol.split(':')[-1], 'other')
            sector_weights[sector] = sector_weights.get(sector, 0) + weight

        return sector_weights

    def _calculate_portfolio_volatility(self, positions: Dict[str, float],
                                      risk_metrics: Dict[str, Any]) -> float:
        """计算投资组合波动率"""
        # 简化实现 - 实际应该基于协方差矩阵
        individual_vols = risk_metrics.get('individual_volatilities', {})

        weighted_vol = 0
        for symbol, weight in positions.items():
            vol = individual_vols.get(symbol, 0.20)  # 默认20%波动率
            weighted_vol += weight * vol

        return weighted_vol

    def _calculate_var(self, positions: Dict[str, float],
                      risk_metrics: Dict[str, Any], confidence: float = 0.95) -> float:
        """计算风险价值(VaR)"""
        # 简化的VaR计算
        portfolio_vol = self._calculate_portfolio_volatility(positions, risk_metrics)

        # 假设正态分布，95%置信度对应1.645个标准差
        z_score = 1.645 if confidence == 0.95 else 2.33  # 99%置信度

        return portfolio_vol * z_score


class MarketRiskMonitor(Skill):
    """市场风险监控技能"""

    def __init__(self):
        self.logger = logging.getLogger(f"skill.{self.__class__.__name__}")

    def execute(self, context: AgentContext) -> AgentOutput:
        """执行市场风险监控"""
        market_data = context.market_data

        # 监控市场波动率
        volatility_alerts = self._monitor_volatility(market_data)

        # 监控相关性变化
        correlation_alerts = self._monitor_correlations(market_data)

        # 监控流动性风险
        liquidity_alerts = self._monitor_liquidity(market_data)

        return AgentOutput(
            agent_id="market_risk_monitor",
            output_type="alert",
            content={
                "volatility_alerts": volatility_alerts,
                "correlation_alerts": correlation_alerts,
                "liquidity_alerts": liquidity_alerts,
                "market_stress_level": self._assess_market_stress(market_data)
            },
            confidence=0.80,
            timestamp=datetime.now(),
            dependencies=["market_data"]
        )

    def validate_inputs(self, context: AgentContext) -> bool:
        """验证输入数据"""
        return bool(context.market_data)

    def _monitor_volatility(self, market_data: Dict[str, Any]) -> List[RiskAlert]:
        """监控波动率风险"""
        alerts = []

        market_vol = market_data.get('market_volatility', 0.15)
        if market_vol > 0.30:
            alerts.append(RiskAlert(
                risk_type="high_volatility",
                severity="high",
                description=f"市场波动率异常高: {market_vol:.1%}",
                affected_positions=[],
                recommended_actions=["降低仓位", "增加对冲"]
            ))

        return alerts

    def _monitor_correlations(self, market_data: Dict[str, Any]) -> List[RiskAlert]:
        """监控相关性风险"""
        alerts = []

        # 简化实现 - 实际应该计算资产间相关性
        avg_correlation = market_data.get('average_correlation', 0.5)
        if avg_correlation > 0.8:
            alerts.append(RiskAlert(
                risk_type="high_correlation",
                severity="medium",
                description=f"资产间相关性过高: {avg_correlation:.2f}",
                affected_positions=[],
                recommended_actions=["增加非相关资产", "调整资产配置"]
            ))

        return alerts

    def _monitor_liquidity(self, market_data: Dict[str, Any]) -> List[RiskAlert]:
        """监控流动性风险"""
        alerts = []

        market_liquidity = market_data.get('market_liquidity_score', 0.7)
        if market_liquidity < 0.3:
            alerts.append(RiskAlert(
                risk_type="liquidity_risk",
                severity="high",
                description=f"市场流动性不足: {market_liquidity:.2f}",
                affected_positions=[],
                recommended_actions=["提高现金比例", "避免大额交易"]
            ))

        return alerts

    def _assess_market_stress(self, market_data: Dict[str, Any]) -> str:
        """评估市场压力水平"""
        volatility = market_data.get('market_volatility', 0.15)
        liquidity = market_data.get('market_liquidity_score', 0.7)

        if volatility > 0.30 or liquidity < 0.3:
            return "high"
        elif volatility > 0.20 or liquidity < 0.5:
            return "medium"
        else:
            return "low"