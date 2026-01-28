"""
基金经理Agent

作为主决策者，负责：
1. 投资策略制定
2. 资产配置决策
3. 团队协调管理
4. 向董事长汇报
5. 风险控制决策
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, List, Any, Optional
import pandas as pd
from pathlib import Path

from .base_agent import BaseAgent, AgentReport, AgentDecision
from ..data.schema import Symbol
from ..data.lake import DataLake
from ..risk.manager import RiskManager, RiskConfig
from ..backtest.strategies import sma_crossover_signals


@dataclass
class InvestmentDecision:
    """投资决策"""
    symbol: Symbol
    action: str  # 'buy', 'sell', 'hold', 'reduce', 'increase'
    target_weight: float  # 目标仓位权重 0.0-1.0
    reasoning: str
    confidence: float  # 0.0-1.0
    risk_assessment: str
    expected_return: Optional[float] = None
    time_horizon: Optional[str] = None  # 'short', 'medium', 'long'


@dataclass
class PortfolioAllocation:
    """投资组合配置"""
    allocations: Dict[Symbol, float]  # symbol -> weight
    cash_weight: float
    total_weight: float
    rebalance_needed: bool
    reasoning: str


class FundManager(BaseAgent):
    """
    基金经理Agent - 主决策者

    负责整个基金的投资决策和团队协调
    """

    def __init__(self, repo_root: Path):
        super().__init__("fund_manager", "基金经理", repo_root)

        # 初始化数据湖和风控
        self.data_lake = DataLake(repo_root)
        self.risk_manager = RiskManager(RiskConfig())

        # 投资组合状态
        self.current_portfolio: Dict[Symbol, float] = {}  # symbol -> weight
        self.cash_position = 1.0  # 初始100%现金
        self.target_portfolio: Dict[Symbol, float] = {}

        # 投资策略参数
        self.max_single_position = 0.2  # 单一标的最大仓位20%
        self.max_sector_exposure = 0.4  # 单一行业最大敞口40%
        self.rebalance_threshold = 0.05  # 5%偏差触发再平衡

        # 决策历史
        self.decision_history: List[InvestmentDecision] = []

        self.logger.info("Fund Manager initialized with portfolio management capabilities")

    def analyze(self, data: Dict[str, Any]) -> AgentReport:
        """
        分析市场数据和团队报告，生成投资分析报告

        Args:
            data: 包含市场数据、团队报告等信息
        """
        self.logger.info("Starting portfolio analysis")

        # 分析当前投资组合
        portfolio_analysis = self._analyze_current_portfolio()

        # 分析市场机会
        market_opportunities = self._analyze_market_opportunities(data)

        # 风险评估
        risk_assessment = self._assess_portfolio_risk()

        # 生成投资建议
        investment_recommendations = self._generate_investment_recommendations(
            portfolio_analysis, market_opportunities, risk_assessment
        )

        report_content = {
            'portfolio_analysis': portfolio_analysis,
            'market_opportunities': market_opportunities,
            'risk_assessment': risk_assessment,
            'investment_recommendations': investment_recommendations,
            'portfolio_performance': self._calculate_portfolio_performance(),
            'next_actions': self._plan_next_actions()
        }

        recommendations = []
        alerts = []

        # 生成建议和警报
        if risk_assessment.get('high_risk_positions'):
            alerts.append(f"高风险仓位需要关注: {risk_assessment['high_risk_positions']}")

        if portfolio_analysis.get('rebalance_needed'):
            recommendations.append("建议进行投资组合再平衡")

        for opportunity in market_opportunities:
            if opportunity.get('confidence', 0) > 0.7:
                recommendations.append(f"高信心投资机会: {opportunity['symbol']} - {opportunity['reasoning']}")

        return AgentReport(
            agent_name=self.name,
            report_type='analysis',
            content=report_content,
            recommendations=recommendations,
            alerts=alerts
        )

    def make_recommendation(self, context: Dict[str, Any]) -> List[str]:
        """基于当前上下文提出投资建议"""
        recommendations = []

        # 基于风险水平调整
        current_risk = self._calculate_portfolio_risk()
        if current_risk > 0.15:  # 15%以上风险
            recommendations.append("当前投资组合风险偏高，建议降低仓位或增加防御性资产")

        # 基于现金仓位
        if self.cash_position > 0.3:  # 现金仓位超过30%
            recommendations.append("现金仓位较高，建议寻找投资机会")
        elif self.cash_position < 0.05:  # 现金仓位低于5%
            recommendations.append("现金仓位过低，建议适当减仓保持流动性")

        # 基于仓位集中度
        if self.current_portfolio:
            max_position = max(self.current_portfolio.values())
            if max_position > self.max_single_position:
                recommendations.append(f"单一仓位过于集中({max_position:.1%})，建议分散风险")

        return recommendations

    def make_investment_decision(self, symbol: Symbol, analysis: Dict[str, Any]) -> InvestmentDecision:
        """
        做出具体的投资决策

        Args:
            symbol: 投资标的
            analysis: 分析数据（来自研究分析师）
        """
        self.logger.info(f"Making investment decision for {symbol}")

        # 获取当前仓位
        current_weight = self.current_portfolio.get(symbol, 0.0)

        # 基于分析确定行动
        action, target_weight, reasoning, confidence = self._determine_action(symbol, analysis, current_weight)

        # 风险评估
        risk_assessment = self._assess_investment_risk(symbol, target_weight, analysis)

        decision = InvestmentDecision(
            symbol=symbol,
            action=action,
            target_weight=target_weight,
            reasoning=reasoning,
            confidence=confidence,
            risk_assessment=risk_assessment,
            expected_return=analysis.get('expected_return'),
            time_horizon=analysis.get('time_horizon', 'medium')
        )

        # 记录决策
        self.record_decision(
            decision_type='investment',
            decision=f"{action} {symbol} to {target_weight:.1%}",
            reasoning=reasoning,
            confidence=confidence,
            data_sources=['research_analyst', 'market_data']
        )

        self.decision_history.append(decision)
        return decision

    def execute_portfolio_rebalance(self) -> PortfolioAllocation:
        """执行投资组合再平衡"""
        self.logger.info("Executing portfolio rebalance")

        # 计算目标配置
        target_allocation = self._calculate_target_allocation()

        # 检查是否需要再平衡
        rebalance_needed = self._check_rebalance_needed(target_allocation)

        allocation = PortfolioAllocation(
            allocations=target_allocation,
            cash_weight=1.0 - sum(target_allocation.values()),
            total_weight=sum(target_allocation.values()) + (1.0 - sum(target_allocation.values())),
            rebalance_needed=rebalance_needed,
            reasoning="基于当前市场分析和风险评估的组合优化"
        )

        if rebalance_needed:
            self.target_portfolio = target_allocation.copy()
            self.logger.info(f"Portfolio rebalance planned: {allocation.allocations}")

            self.event_logger.log("portfolio_rebalance", {
                "target_allocations": {str(k): v for k, v in allocation.allocations.items()},
                "cash_weight": allocation.cash_weight,
                "reasoning": allocation.reasoning
            })

        return allocation

    def coordinate_team(self) -> Dict[str, Any]:
        """协调团队工作"""
        self.logger.info("Coordinating team activities")

        # 处理收件箱消息
        messages = self.process_inbox()

        # 分析团队报告
        team_insights = self._analyze_team_reports(messages)

        # 分配新任务
        new_tasks = self._assign_team_tasks(team_insights)

        coordination_result = {
            'messages_processed': len(messages),
            'team_insights': team_insights,
            'new_tasks': new_tasks,
            'team_status': self._get_team_status()
        }

        self.event_logger.log("team_coordination", coordination_result)
        return coordination_result

    def generate_board_report(self) -> Dict[str, Any]:
        """生成董事会报告"""
        self.logger.info("Generating board report")

        performance = self._calculate_portfolio_performance()
        risk_metrics = self._calculate_risk_metrics()
        recent_decisions = self.decision_history[-10:]  # 最近10个决策

        board_report = {
            'period': {
                'start_date': (datetime.now() - pd.Timedelta(days=30)).strftime('%Y-%m-%d'),
                'end_date': datetime.now().strftime('%Y-%m-%d')
            },
            'performance': performance,
            'risk_metrics': risk_metrics,
            'current_allocation': self.current_portfolio.copy(),
            'cash_position': self.cash_position,
            'recent_decisions': [
                {
                    'symbol': str(d.symbol),
                    'action': d.action,
                    'target_weight': d.target_weight,
                    'reasoning': d.reasoning,
                    'confidence': d.confidence
                } for d in recent_decisions
            ],
            'key_achievements': self._summarize_achievements(),
            'challenges_and_risks': self._identify_challenges(),
            'outlook_and_strategy': self._provide_outlook()
        }

        self.event_logger.log("board_report_generated", {
            'report_period': board_report['period'],
            'performance_summary': performance,
            'risk_summary': risk_metrics
        })

        return board_report

    def _analyze_current_portfolio(self) -> Dict[str, Any]:
        """分析当前投资组合"""
        if not self.current_portfolio:
            return {
                'status': 'empty',
                'cash_position': self.cash_position,
                'rebalance_needed': False
            }

        total_weight = sum(self.current_portfolio.values())
        largest_position = max(self.current_portfolio.values()) if self.current_portfolio else 0
        position_count = len(self.current_portfolio)

        return {
            'total_weight': total_weight,
            'cash_position': self.cash_position,
            'position_count': position_count,
            'largest_position': largest_position,
            'diversification_score': self._calculate_diversification_score(),
            'rebalance_needed': self._check_rebalance_needed(self.current_portfolio)
        }

    def _analyze_market_opportunities(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """分析市场机会"""
        opportunities = []

        # 从研究分析师的报告中提取机会
        research_reports = data.get('research_reports', [])
        for report in research_reports:
            if report.get('recommendation') in ['buy', 'strong_buy']:
                opportunities.append({
                    'symbol': report.get('symbol'),
                    'type': 'research_recommendation',
                    'confidence': report.get('confidence', 0.5),
                    'reasoning': report.get('reasoning', ''),
                    'expected_return': report.get('target_price_return')
                })

        # 技术面机会
        technical_signals = data.get('technical_signals', [])
        for signal in technical_signals:
            if signal.get('signal') == 'buy':
                opportunities.append({
                    'symbol': signal.get('symbol'),
                    'type': 'technical_signal',
                    'confidence': signal.get('strength', 0.5),
                    'reasoning': f"技术信号: {signal.get('indicator', '')}"
                })

        return opportunities

    def _assess_portfolio_risk(self) -> Dict[str, Any]:
        """评估投资组合风险"""
        if not self.current_portfolio:
            return {'overall_risk': 0.0, 'high_risk_positions': []}

        # 计算各种风险指标
        concentration_risk = max(self.current_portfolio.values()) if self.current_portfolio else 0
        position_count_risk = 1.0 / max(len(self.current_portfolio), 1)

        high_risk_positions = [
            str(symbol) for symbol, weight in self.current_portfolio.items()
            if weight > self.max_single_position
        ]

        return {
            'overall_risk': self._calculate_portfolio_risk(),
            'concentration_risk': concentration_risk,
            'position_count_risk': position_count_risk,
            'high_risk_positions': high_risk_positions,
            'cash_buffer': self.cash_position
        }

    def _generate_investment_recommendations(self, portfolio_analysis: Dict, market_opportunities: List,
                                           risk_assessment: Dict) -> List[Dict[str, Any]]:
        """生成投资建议"""
        recommendations = []

        # 基于风险调整建议
        if risk_assessment['overall_risk'] > 0.2:
            recommendations.append({
                'type': 'risk_reduction',
                'action': 'reduce_risk',
                'reasoning': '当前组合风险偏高，建议降低风险敞口',
                'priority': 'high'
            })

        # 基于机会生成建议
        for opportunity in market_opportunities:
            if opportunity['confidence'] > 0.6:
                recommendations.append({
                    'type': 'investment_opportunity',
                    'symbol': opportunity['symbol'],
                    'action': 'consider_buy',
                    'reasoning': opportunity['reasoning'],
                    'confidence': opportunity['confidence'],
                    'priority': 'medium' if opportunity['confidence'] > 0.8 else 'low'
                })

        return recommendations

    def _determine_action(self, symbol: Symbol, analysis: Dict[str, Any], current_weight: float) -> tuple:
        """确定对特定标的的行动"""
        recommendation = analysis.get('recommendation', 'hold')
        confidence = analysis.get('confidence', 0.5)
        target_price_return = analysis.get('target_price_return', 0.0)

        if recommendation == 'strong_buy' and confidence > 0.8:
            target_weight = min(self.max_single_position, current_weight + 0.1)
            action = 'buy' if current_weight == 0 else 'increase'
            reasoning = f"强烈买入建议，预期收益{target_price_return:.1%}，信心度{confidence:.1%}"

        elif recommendation == 'buy' and confidence > 0.6:
            target_weight = min(self.max_single_position * 0.7, current_weight + 0.05)
            action = 'buy' if current_weight == 0 else 'increase'
            reasoning = f"买入建议，预期收益{target_price_return:.1%}，信心度{confidence:.1%}"

        elif recommendation == 'sell' or confidence < 0.3:
            target_weight = max(0, current_weight - 0.1)
            action = 'reduce' if target_weight > 0 else 'sell'
            reasoning = f"卖出建议，信心度不足或负面预期"

        else:
            target_weight = current_weight
            action = 'hold'
            reasoning = f"维持现有仓位，等待更明确信号"

        return action, target_weight, reasoning, confidence

    def _assess_investment_risk(self, symbol: Symbol, target_weight: float, analysis: Dict[str, Any]) -> str:
        """评估投资风险"""
        risk_factors = []

        if target_weight > self.max_single_position:
            risk_factors.append("仓位过于集中")

        volatility = analysis.get('volatility', 0.2)
        if volatility > 0.3:
            risk_factors.append("高波动性")

        beta = analysis.get('beta', 1.0)
        if beta > 1.5:
            risk_factors.append("高市场敏感性")

        if not risk_factors:
            return "风险可控"
        else:
            return f"风险因素: {', '.join(risk_factors)}"

    def _calculate_target_allocation(self) -> Dict[Symbol, float]:
        """计算目标资产配置"""
        # 简化的等权重配置策略
        # 实际实现中应该基于更复杂的优化算法
        target_symbols = list(self.current_portfolio.keys())

        if not target_symbols:
            return {}

        # 为每个标的分配权重
        base_weight = min(0.8 / len(target_symbols), self.max_single_position)
        return {symbol: base_weight for symbol in target_symbols}

    def _check_rebalance_needed(self, target_allocation: Dict[Symbol, float]) -> bool:
        """检查是否需要再平衡"""
        for symbol, target_weight in target_allocation.items():
            current_weight = self.current_portfolio.get(symbol, 0.0)
            if abs(current_weight - target_weight) > self.rebalance_threshold:
                return True
        return False

    def _calculate_portfolio_performance(self) -> Dict[str, float]:
        """计算投资组合表现"""
        # 简化实现 - 实际应该基于历史数据计算
        return {
            'total_return': 0.05,  # 5%
            'ytd_return': 0.03,    # 3%
            'volatility': 0.15,    # 15%
            'sharpe_ratio': 0.33,  # 0.33
            'max_drawdown': -0.08  # -8%
        }

    def _calculate_portfolio_risk(self) -> float:
        """计算投资组合整体风险"""
        if not self.current_portfolio:
            return 0.0

        # 简化的风险计算 - 基于仓位集中度
        concentration_risk = max(self.current_portfolio.values()) if self.current_portfolio else 0
        diversification_penalty = 1.0 / max(len(self.current_portfolio), 1)

        return min(concentration_risk + diversification_penalty * 0.1, 1.0)

    def _calculate_diversification_score(self) -> float:
        """计算多元化分数"""
        if not self.current_portfolio:
            return 0.0

        position_count = len(self.current_portfolio)
        weight_variance = pd.Series(list(self.current_portfolio.values())).var()

        # 分数基于持仓数量和权重分布
        return min(position_count / 10.0, 1.0) * (1.0 - weight_variance)

    def _calculate_risk_metrics(self) -> Dict[str, float]:
        """计算风险指标"""
        return {
            'portfolio_risk': self._calculate_portfolio_risk(),
            'concentration_risk': max(self.current_portfolio.values()) if self.current_portfolio else 0,
            'cash_buffer': self.cash_position,
            'position_count': len(self.current_portfolio),
            'diversification_score': self._calculate_diversification_score()
        }

    def _analyze_team_reports(self, messages: List) -> Dict[str, Any]:
        """分析团队报告"""
        insights = {
            'research_insights': [],
            'risk_alerts': [],
            'data_quality_issues': [],
            'execution_feedback': []
        }

        for message in messages:
            if message.from_agent == 'research_analyst':
                insights['research_insights'].append(message.content)
            elif message.from_agent == 'risk_manager':
                insights['risk_alerts'].append(message.content)
            elif message.from_agent == 'data_engineer':
                insights['data_quality_issues'].append(message.content)
            elif message.from_agent == 'trade_executor':
                insights['execution_feedback'].append(message.content)

        return insights

    def _assign_team_tasks(self, team_insights: Dict[str, Any]) -> List[Dict[str, Any]]:
        """分配团队任务"""
        tasks = []

        # 基于当前需求分配任务
        if len(self.current_portfolio) < 5:
            tasks.append({
                'assignee': 'research_analyst',
                'task': 'identify_investment_opportunities',
                'priority': 'high',
                'details': '寻找新的投资机会，目标增加组合多样性'
            })

        if self.cash_position > 0.3:
            tasks.append({
                'assignee': 'research_analyst',
                'task': 'analyze_cash_deployment',
                'priority': 'medium',
                'details': '分析现金部署机会，降低现金仓位'
            })

        return tasks

    def _get_team_status(self) -> Dict[str, str]:
        """获取团队状态"""
        return {
            'research_analyst': 'active',
            'risk_manager': 'active',
            'data_engineer': 'active',
            'trade_executor': 'active'
        }

    def _plan_next_actions(self) -> List[str]:
        """规划下一步行动"""
        actions = []

        if self.cash_position > 0.2:
            actions.append("寻找投资机会部署现金")

        if len(self.current_portfolio) > 10:
            actions.append("考虑精简投资组合，集中优质标的")

        if not self.decision_history:
            actions.append("开始建立投资组合")

        return actions

    def _summarize_achievements(self) -> List[str]:
        """总结关键成就"""
        achievements = []

        if self.decision_history:
            achievements.append(f"完成{len(self.decision_history)}项投资决策")

        if self.current_portfolio:
            achievements.append(f"构建了包含{len(self.current_portfolio)}只股票的投资组合")

        return achievements

    def _identify_challenges(self) -> List[str]:
        """识别挑战和风险"""
        challenges = []

        if self.cash_position > 0.5:
            challenges.append("现金仓位过高，存在机会成本")

        if self._calculate_portfolio_risk() > 0.2:
            challenges.append("投资组合风险偏高")

        return challenges

    def _provide_outlook(self) -> str:
        """提供前景展望"""
        return "继续专注于价值投资，保持风险控制，寻找长期增长机会"