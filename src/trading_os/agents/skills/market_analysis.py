"""
市场分析技能模块

提供市场趋势分析、技术指标计算等功能
"""

from datetime import datetime
from typing import Dict, List, Any
import logging

from ..core.agent_interface import AgentContext, AgentOutput, Skill
from ..core.message_types import MarketSignal
from ...data.schema import Symbol


class MarketTrendAnalysis(Skill):
    """市场趋势分析技能"""

    def __init__(self):
        self.logger = logging.getLogger(f"skill.{self.__class__.__name__}")

    def execute(self, context: AgentContext) -> AgentOutput:
        """执行市场趋势分析"""
        market_data = context.market_data

        # 分析市场趋势
        trend_signals = self._analyze_market_trends(market_data)

        # 计算技术指标
        technical_indicators = self._calculate_technical_indicators(market_data)

        # 评估市场情绪
        sentiment_score = self._assess_market_sentiment(market_data)

        return AgentOutput(
            agent_id="market_trend_analysis",
            output_type="analysis",
            content={
                "trend_signals": trend_signals,
                "technical_indicators": technical_indicators,
                "sentiment_score": sentiment_score,
                "market_phase": self._determine_market_phase(trend_signals, sentiment_score)
            },
            confidence=0.8,
            timestamp=datetime.now(),
            dependencies=["market_data"]
        )

    def validate_inputs(self, context: AgentContext) -> bool:
        """验证输入数据"""
        return bool(context.market_data and 'prices' in context.market_data)

    def _analyze_market_trends(self, market_data: Dict[str, Any]) -> List[MarketSignal]:
        """分析市场趋势"""
        signals = []

        # 简化的趋势分析逻辑
        prices = market_data.get('prices', {})
        for symbol_str, price_data in prices.items():
            if self._is_uptrend(price_data):
                signals.append(MarketSignal(
                    symbol=symbol_str,
                    signal_type='buy',
                    strength=0.7,
                    reasoning='价格呈上升趋势'
                ))
            elif self._is_downtrend(price_data):
                signals.append(MarketSignal(
                    symbol=symbol_str,
                    signal_type='sell',
                    strength=0.6,
                    reasoning='价格呈下降趋势'
                ))

        return signals

    def _calculate_technical_indicators(self, market_data: Dict[str, Any]) -> Dict[str, float]:
        """计算技术指标"""
        # 简化实现
        return {
            'rsi': 65.0,
            'macd': 0.5,
            'bollinger_position': 0.7,
            'volume_trend': 1.2
        }

    def _assess_market_sentiment(self, market_data: Dict[str, Any]) -> float:
        """评估市场情绪"""
        # 简化的情绪分析
        return 0.6  # 中性偏乐观

    def _determine_market_phase(self, trend_signals: List[MarketSignal], sentiment: float) -> str:
        """确定市场阶段"""
        buy_signals = sum(1 for s in trend_signals if s.signal_type == 'buy')
        sell_signals = sum(1 for s in trend_signals if s.signal_type == 'sell')

        if buy_signals > sell_signals and sentiment > 0.6:
            return 'bull_market'
        elif sell_signals > buy_signals and sentiment < 0.4:
            return 'bear_market'
        else:
            return 'sideways'

    def _is_uptrend(self, price_data: Dict[str, Any]) -> bool:
        """判断是否为上升趋势"""
        # 简化实现
        return price_data.get('change_pct', 0) > 0.02

    def _is_downtrend(self, price_data: Dict[str, Any]) -> bool:
        """判断是否为下降趋势"""
        # 简化实现
        return price_data.get('change_pct', 0) < -0.02


class SectorAnalysis(Skill):
    """行业分析技能"""

    def __init__(self):
        self.logger = logging.getLogger(f"skill.{self.__class__.__name__}")
        self.sector_mapping = {
            'AAPL': 'technology',
            'MSFT': 'technology',
            'JPM': 'finance',
            'JNJ': 'healthcare'
        }

    def execute(self, context: AgentContext) -> AgentOutput:
        """执行行业分析"""
        sector_performance = self._analyze_sector_performance(context.market_data)
        sector_rotation = self._detect_sector_rotation(sector_performance)

        return AgentOutput(
            agent_id="sector_analysis",
            output_type="analysis",
            content={
                "sector_performance": sector_performance,
                "sector_rotation": sector_rotation,
                "leading_sectors": self._identify_leading_sectors(sector_performance),
                "lagging_sectors": self._identify_lagging_sectors(sector_performance)
            },
            confidence=0.75,
            timestamp=datetime.now(),
            dependencies=["market_data"]
        )

    def validate_inputs(self, context: AgentContext) -> bool:
        """验证输入数据"""
        return bool(context.market_data)

    def _analyze_sector_performance(self, market_data: Dict[str, Any]) -> Dict[str, float]:
        """分析行业表现"""
        sector_returns = {}
        prices = market_data.get('prices', {})

        # 按行业聚合收益率
        sector_prices = {}
        for symbol, price_data in prices.items():
            sector = self.sector_mapping.get(symbol, 'other')
            if sector not in sector_prices:
                sector_prices[sector] = []
            sector_prices[sector].append(price_data.get('change_pct', 0))

        # 计算行业平均收益率
        for sector, returns in sector_prices.items():
            sector_returns[sector] = sum(returns) / len(returns) if returns else 0

        return sector_returns

    def _detect_sector_rotation(self, sector_performance: Dict[str, float]) -> bool:
        """检测行业轮动"""
        if not sector_performance:
            return False

        max_return = max(sector_performance.values())
        min_return = min(sector_performance.values())

        # 如果行业间表现差异超过5%，认为存在轮动
        return (max_return - min_return) > 0.05

    def _identify_leading_sectors(self, sector_performance: Dict[str, float]) -> List[str]:
        """识别领先行业"""
        sorted_sectors = sorted(sector_performance.items(), key=lambda x: x[1], reverse=True)
        return [sector for sector, _ in sorted_sectors[:2]]  # 前2个

    def _identify_lagging_sectors(self, sector_performance: Dict[str, float]) -> List[str]:
        """识别落后行业"""
        sorted_sectors = sorted(sector_performance.items(), key=lambda x: x[1])
        return [sector for sector, _ in sorted_sectors[:2]]  # 后2个