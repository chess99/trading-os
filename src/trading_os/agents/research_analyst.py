"""
研究分析师Agent

负责：
1. 市场和行业研究
2. 个股分析和评级
3. 投资机会识别
4. 技术分析
5. 宏观经济分析
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging

from .base_agent import BaseAgent, AgentReport
from ..data.schema import Symbol
from ..data.lake import DataLake


@dataclass
class StockAnalysis:
    """个股分析结果"""
    symbol: Symbol
    recommendation: str  # 'strong_buy', 'buy', 'hold', 'sell', 'strong_sell'
    target_price: Optional[float]
    current_price: float
    target_price_return: float  # 目标价格收益率
    confidence: float  # 0.0-1.0
    reasoning: str
    risk_factors: List[str]
    catalysts: List[str]  # 催化剂
    time_horizon: str  # 'short', 'medium', 'long'
    analyst_notes: str


@dataclass
class MarketOutlook:
    """市场展望"""
    market: str  # 'US', 'China', 'Global'
    outlook: str  # 'bullish', 'neutral', 'bearish'
    confidence: float
    key_drivers: List[str]
    risks: List[str]
    time_horizon: str
    supporting_data: Dict[str, Any]


@dataclass
class SectorAnalysis:
    """行业分析"""
    sector: str
    outlook: str  # 'positive', 'neutral', 'negative'
    relative_performance: float  # vs market
    key_themes: List[str]
    top_picks: List[Symbol]
    avoid_list: List[Symbol]
    reasoning: str


class ResearchAnalyst(BaseAgent):
    """
    研究分析师Agent

    专注于深度研究和投资建议生成
    """

    def __init__(self, repo_root: Path):
        super().__init__("research_analyst", "研究分析师", repo_root)

        self.data_lake = DataLake(repo_root)

        # 研究覆盖范围
        self.coverage_universe: List[Symbol] = []
        self.sector_coverage = {
            'technology': ['NASDAQ:AAPL', 'NASDAQ:MSFT', 'NASDAQ:GOOGL'],
            'finance': ['NYSE:JPM', 'NYSE:BAC', 'NYSE:WFC'],
            'healthcare': ['NYSE:JNJ', 'NYSE:PFE', 'NASDAQ:MRNA'],
            'consumer': ['NASDAQ:AMZN', 'NASDAQ:TSLA', 'NYSE:DIS']
        }

        # 分析历史
        self.analysis_history: List[StockAnalysis] = []
        self.market_views: List[MarketOutlook] = []
        self.sector_views: List[SectorAnalysis] = []

        # 研究参数
        self.min_confidence_threshold = 0.6
        self.analysis_refresh_days = 7  # 7天更新一次分析

        self.logger.info("Research Analyst initialized with market research capabilities")

    def analyze(self, data: Dict[str, Any]) -> AgentReport:
        """
        执行综合市场分析

        Args:
            data: 包含市场数据、新闻、财务数据等
        """
        self.logger.info("Starting comprehensive market analysis")

        # 市场概览分析
        market_overview = self._analyze_market_overview(data)

        # 行业轮动分析
        sector_rotation = self._analyze_sector_rotation(data)

        # 个股筛选和分析
        stock_screening = self._screen_stocks(data)

        # 技术面分析
        technical_analysis = self._perform_technical_analysis(data)

        # 投资主题识别
        investment_themes = self._identify_investment_themes(data)

        report_content = {
            'market_overview': market_overview,
            'sector_rotation': sector_rotation,
            'stock_screening': stock_screening,
            'technical_analysis': technical_analysis,
            'investment_themes': investment_themes,
            'top_picks': self._generate_top_picks(),
            'watchlist': self._update_watchlist(),
            'risk_alerts': self._identify_risk_alerts(data)
        }

        # 生成建议和警报
        recommendations = []
        alerts = []

        # 基于分析生成建议
        for pick in report_content['top_picks']:
            if pick['confidence'] > 0.8:
                recommendations.append(
                    f"强烈推荐 {pick['symbol']}: {pick['reasoning']} (信心度: {pick['confidence']:.0%})"
                )

        # 风险警报
        for alert in report_content['risk_alerts']:
            if alert['severity'] == 'high':
                alerts.append(f"高风险警报: {alert['description']}")

        return AgentReport(
            agent_name=self.name,
            report_type='market_analysis',
            content=report_content,
            recommendations=recommendations,
            alerts=alerts
        )

    def make_recommendation(self, context: Dict[str, Any]) -> List[str]:
        """基于当前市场环境提出投资建议"""
        recommendations = []

        # 基于市场趋势
        current_market_trend = self._assess_market_trend()
        if current_market_trend == 'bullish':
            recommendations.append("市场趋势向好，建议适度增加风险敞口")
        elif current_market_trend == 'bearish':
            recommendations.append("市场风险增加，建议降低仓位或增加防御性资产")

        # 基于估值水平
        market_valuation = self._assess_market_valuation()
        if market_valuation == 'undervalued':
            recommendations.append("市场估值偏低，存在投资机会")
        elif market_valuation == 'overvalued':
            recommendations.append("市场估值偏高，建议谨慎投资")

        # 基于技术指标
        technical_signals = self._get_technical_signals()
        if technical_signals.get('momentum') == 'positive':
            recommendations.append("技术面显示积极信号，支持适度风险投资")

        return recommendations

    def analyze_stock(self, symbol: Symbol, deep_analysis: bool = True) -> StockAnalysis:
        """
        深度个股分析

        Args:
            symbol: 股票代码
            deep_analysis: 是否进行深度分析
        """
        self.logger.info(f"Analyzing stock {symbol}")

        # 获取基础数据
        stock_data = self._get_stock_data(symbol)
        if not stock_data:
            return self._create_no_data_analysis(symbol)

        # 基本面分析
        fundamental_score = self._analyze_fundamentals(symbol, stock_data)

        # 技术面分析
        technical_score = self._analyze_technicals(symbol, stock_data)

        # 估值分析
        valuation_score = self._analyze_valuation(symbol, stock_data)

        # 综合评分和建议
        overall_score = (fundamental_score + technical_score + valuation_score) / 3
        recommendation = self._score_to_recommendation(overall_score)

        # 目标价格计算
        current_price = stock_data.get('current_price', 0)
        target_price = self._calculate_target_price(symbol, stock_data, overall_score)
        target_return = (target_price - current_price) / current_price if current_price > 0 else 0

        # 风险因素识别
        risk_factors = self._identify_risk_factors(symbol, stock_data)

        # 催化剂识别
        catalysts = self._identify_catalysts(symbol, stock_data)

        # 生成分析推理
        reasoning = self._generate_analysis_reasoning(
            symbol, fundamental_score, technical_score, valuation_score, stock_data
        )

        analysis = StockAnalysis(
            symbol=symbol,
            recommendation=recommendation,
            target_price=target_price,
            current_price=current_price,
            target_price_return=target_return,
            confidence=min(overall_score, 1.0),
            reasoning=reasoning,
            risk_factors=risk_factors,
            catalysts=catalysts,
            time_horizon='medium',  # 默认中期
            analyst_notes=f"分析日期: {datetime.now().strftime('%Y-%m-%d')}"
        )

        # 记录分析
        self.analysis_history.append(analysis)
        self.record_decision(
            decision_type='stock_analysis',
            decision=f"{recommendation} {symbol}",
            reasoning=reasoning,
            confidence=analysis.confidence,
            data_sources=['market_data', 'fundamental_data', 'technical_analysis']
        )

        return analysis

    def generate_market_outlook(self, time_horizon: str = 'medium') -> MarketOutlook:
        """生成市场展望"""
        self.logger.info(f"Generating {time_horizon} term market outlook")

        # 分析宏观经济指标
        macro_indicators = self._analyze_macro_indicators()

        # 分析市场情绪
        market_sentiment = self._analyze_market_sentiment()

        # 分析技术面
        market_technicals = self._analyze_market_technicals()

        # 综合判断
        outlook_score = (
            macro_indicators['score'] * 0.4 +
            market_sentiment['score'] * 0.3 +
            market_technicals['score'] * 0.3
        )

        if outlook_score > 0.6:
            outlook = 'bullish'
        elif outlook_score < 0.4:
            outlook = 'bearish'
        else:
            outlook = 'neutral'

        key_drivers = []
        risks = []

        # 整合关键驱动因素和风险
        key_drivers.extend(macro_indicators.get('positive_factors', []))
        key_drivers.extend(market_sentiment.get('positive_factors', []))

        risks.extend(macro_indicators.get('risk_factors', []))
        risks.extend(market_sentiment.get('risk_factors', []))

        market_outlook = MarketOutlook(
            market='US',  # 默认美股
            outlook=outlook,
            confidence=abs(outlook_score - 0.5) * 2,  # 转换为0-1的信心度
            key_drivers=key_drivers,
            risks=risks,
            time_horizon=time_horizon,
            supporting_data={
                'macro_score': macro_indicators['score'],
                'sentiment_score': market_sentiment['score'],
                'technical_score': market_technicals['score']
            }
        )

        self.market_views.append(market_outlook)
        return market_outlook

    def screen_investment_opportunities(self, criteria: Dict[str, Any]) -> List[Symbol]:
        """
        筛选投资机会

        Args:
            criteria: 筛选条件
        """
        self.logger.info("Screening for investment opportunities")

        opportunities = []

        # 基于不同筛选条件
        if criteria.get('growth_stocks'):
            opportunities.extend(self._screen_growth_stocks())

        if criteria.get('value_stocks'):
            opportunities.extend(self._screen_value_stocks())

        if criteria.get('dividend_stocks'):
            opportunities.extend(self._screen_dividend_stocks())

        if criteria.get('momentum_stocks'):
            opportunities.extend(self._screen_momentum_stocks())

        # 去重并按评分排序
        unique_opportunities = list(set(opportunities))
        scored_opportunities = []

        for symbol in unique_opportunities:
            try:
                analysis = self.analyze_stock(symbol, deep_analysis=False)
                if analysis.confidence > self.min_confidence_threshold:
                    scored_opportunities.append((symbol, analysis.confidence))
            except Exception as e:
                self.logger.warning(f"Failed to analyze {symbol}: {e}")

        # 按信心度排序
        scored_opportunities.sort(key=lambda x: x[1], reverse=True)

        return [symbol for symbol, _ in scored_opportunities[:10]]  # 返回前10个

    def _analyze_market_overview(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """分析市场概览"""
        return {
            'market_trend': self._assess_market_trend(),
            'volatility_level': 'medium',
            'key_indices_performance': {
                'SPY': 0.02,
                'QQQ': 0.015,
                'IWM': -0.005
            },
            'sector_performance': self._get_sector_performance(),
            'market_breadth': 'positive'
        }

    def _analyze_sector_rotation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """分析行业轮动"""
        return {
            'leading_sectors': ['technology', 'healthcare'],
            'lagging_sectors': ['energy', 'utilities'],
            'rotation_signals': ['tech_outperformance', 'defensive_weakness'],
            'recommended_allocation': {
                'technology': 0.3,
                'healthcare': 0.2,
                'finance': 0.15,
                'consumer': 0.2,
                'others': 0.15
            }
        }

    def _screen_stocks(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """股票筛选"""
        screened_stocks = []

        # 简化的筛选逻辑
        for sector, symbols in self.sector_coverage.items():
            for symbol_str in symbols:
                symbol = Symbol.parse(symbol_str)
                try:
                    analysis = self.analyze_stock(symbol, deep_analysis=False)
                    if analysis.confidence > 0.7:
                        screened_stocks.append({
                            'symbol': str(symbol),
                            'sector': sector,
                            'recommendation': analysis.recommendation,
                            'confidence': analysis.confidence,
                            'target_return': analysis.target_price_return
                        })
                except Exception as e:
                    self.logger.warning(f"Failed to screen {symbol}: {e}")

        return screened_stocks

    def _perform_technical_analysis(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """技术分析"""
        return {
            'market_trend': 'uptrend',
            'support_levels': [4200, 4150],
            'resistance_levels': [4350, 4400],
            'momentum_indicators': {
                'RSI': 65,
                'MACD': 'bullish_crossover',
                'moving_averages': 'above_200ma'
            },
            'volume_analysis': 'healthy',
            'breadth_indicators': 'positive'
        }

    def _identify_investment_themes(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """识别投资主题"""
        return [
            {
                'theme': 'AI Revolution',
                'confidence': 0.9,
                'time_horizon': 'long',
                'key_stocks': ['NASDAQ:NVDA', 'NASDAQ:MSFT', 'NASDAQ:GOOGL'],
                'reasoning': '人工智能技术快速发展，相关公司受益明显'
            },
            {
                'theme': 'Energy Transition',
                'confidence': 0.7,
                'time_horizon': 'medium',
                'key_stocks': ['NASDAQ:TSLA', 'NYSE:NEE'],
                'reasoning': '清洁能源转型趋势明确，政策支持力度大'
            }
        ]

    def _generate_top_picks(self) -> List[Dict[str, Any]]:
        """生成精选股票"""
        top_picks = []

        # 从分析历史中选择高信心度的推荐
        recent_analyses = [a for a in self.analysis_history
                          if (datetime.now() - datetime.fromisoformat(a.analyst_notes.split(': ')[1])).days <= 30]

        for analysis in recent_analyses:
            if analysis.confidence > 0.8 and analysis.recommendation in ['buy', 'strong_buy']:
                top_picks.append({
                    'symbol': str(analysis.symbol),
                    'recommendation': analysis.recommendation,
                    'confidence': analysis.confidence,
                    'target_return': analysis.target_price_return,
                    'reasoning': analysis.reasoning[:100] + '...'  # 截断推理
                })

        # 按信心度排序
        top_picks.sort(key=lambda x: x['confidence'], reverse=True)
        return top_picks[:5]  # 返回前5个

    def _update_watchlist(self) -> List[str]:
        """更新关注列表"""
        watchlist = []

        # 添加中等信心度的股票到关注列表
        for analysis in self.analysis_history[-20:]:  # 最近20个分析
            if 0.6 <= analysis.confidence < 0.8:
                watchlist.append(str(analysis.symbol))

        return list(set(watchlist))[:10]  # 去重并限制数量

    def _identify_risk_alerts(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """识别风险警报"""
        alerts = []

        # 市场风险
        if self._assess_market_trend() == 'bearish':
            alerts.append({
                'type': 'market_risk',
                'severity': 'medium',
                'description': '市场趋势转为看空，建议谨慎投资'
            })

        # 估值风险
        market_valuation = self._assess_market_valuation()
        if market_valuation == 'overvalued':
            alerts.append({
                'type': 'valuation_risk',
                'severity': 'medium',
                'description': '市场估值偏高，存在回调风险'
            })

        return alerts

    def _get_stock_data(self, symbol: Symbol) -> Dict[str, Any]:
        """获取股票数据"""
        # 简化实现 - 实际应该从数据湖获取真实数据
        return {
            'current_price': 150.0,
            'pe_ratio': 25.0,
            'pb_ratio': 3.0,
            'roe': 0.15,
            'debt_to_equity': 0.5,
            'revenue_growth': 0.1,
            'earnings_growth': 0.12,
            'dividend_yield': 0.02,
            'beta': 1.2,
            'market_cap': 1000000000
        }

    def _create_no_data_analysis(self, symbol: Symbol) -> StockAnalysis:
        """创建无数据时的分析结果"""
        return StockAnalysis(
            symbol=symbol,
            recommendation='hold',
            target_price=None,
            current_price=0,
            target_price_return=0,
            confidence=0.0,
            reasoning='缺乏足够数据进行分析',
            risk_factors=['数据不足'],
            catalysts=[],
            time_horizon='unknown',
            analyst_notes='数据不可用'
        )

    def _analyze_fundamentals(self, symbol: Symbol, data: Dict[str, Any]) -> float:
        """基本面分析评分"""
        score = 0.5  # 基础分

        # ROE评分
        roe = data.get('roe', 0.1)
        if roe > 0.15:
            score += 0.1
        elif roe < 0.05:
            score -= 0.1

        # 增长评分
        revenue_growth = data.get('revenue_growth', 0)
        earnings_growth = data.get('earnings_growth', 0)
        if revenue_growth > 0.1 and earnings_growth > 0.1:
            score += 0.15
        elif revenue_growth < 0 or earnings_growth < 0:
            score -= 0.15

        # 财务健康度
        debt_to_equity = data.get('debt_to_equity', 0.5)
        if debt_to_equity < 0.3:
            score += 0.05
        elif debt_to_equity > 1.0:
            score -= 0.1

        return max(0.0, min(1.0, score))

    def _analyze_technicals(self, symbol: Symbol, data: Dict[str, Any]) -> float:
        """技术面分析评分"""
        # 简化的技术面评分
        return 0.6  # 默认中性偏积极

    def _analyze_valuation(self, symbol: Symbol, data: Dict[str, Any]) -> float:
        """估值分析评分"""
        score = 0.5

        pe_ratio = data.get('pe_ratio', 20)
        pb_ratio = data.get('pb_ratio', 2)

        # PE估值
        if pe_ratio < 15:
            score += 0.15
        elif pe_ratio > 30:
            score -= 0.15

        # PB估值
        if pb_ratio < 1.5:
            score += 0.1
        elif pb_ratio > 4:
            score -= 0.1

        return max(0.0, min(1.0, score))

    def _score_to_recommendation(self, score: float) -> str:
        """评分转换为投资建议"""
        if score >= 0.8:
            return 'strong_buy'
        elif score >= 0.6:
            return 'buy'
        elif score >= 0.4:
            return 'hold'
        elif score >= 0.2:
            return 'sell'
        else:
            return 'strong_sell'

    def _calculate_target_price(self, symbol: Symbol, data: Dict[str, Any], score: float) -> float:
        """计算目标价格"""
        current_price = data.get('current_price', 0)
        if current_price == 0:
            return 0

        # 基于评分调整目标价格
        adjustment = (score - 0.5) * 0.4  # -20% to +20%
        return current_price * (1 + adjustment)

    def _identify_risk_factors(self, symbol: Symbol, data: Dict[str, Any]) -> List[str]:
        """识别风险因素"""
        risks = []

        if data.get('debt_to_equity', 0) > 1.0:
            risks.append('高负债率')

        if data.get('beta', 1.0) > 1.5:
            risks.append('高波动性')

        if data.get('pe_ratio', 20) > 40:
            risks.append('估值偏高')

        return risks

    def _identify_catalysts(self, symbol: Symbol, data: Dict[str, Any]) -> List[str]:
        """识别催化剂"""
        catalysts = []

        if data.get('earnings_growth', 0) > 0.15:
            catalysts.append('强劲盈利增长')

        if data.get('revenue_growth', 0) > 0.2:
            catalysts.append('营收快速增长')

        return catalysts

    def _generate_analysis_reasoning(self, symbol: Symbol, fundamental_score: float,
                                   technical_score: float, valuation_score: float,
                                   data: Dict[str, Any]) -> str:
        """生成分析推理"""
        reasoning_parts = []

        if fundamental_score > 0.7:
            reasoning_parts.append("基本面强劲")
        elif fundamental_score < 0.3:
            reasoning_parts.append("基本面疲弱")

        if technical_score > 0.7:
            reasoning_parts.append("技术面积极")
        elif technical_score < 0.3:
            reasoning_parts.append("技术面偏弱")

        if valuation_score > 0.7:
            reasoning_parts.append("估值合理")
        elif valuation_score < 0.3:
            reasoning_parts.append("估值偏高")

        if not reasoning_parts:
            reasoning_parts.append("综合评估中性")

        return "，".join(reasoning_parts) + f"。PE: {data.get('pe_ratio', 'N/A')}，ROE: {data.get('roe', 'N/A'):.1%}"

    def _assess_market_trend(self) -> str:
        """评估市场趋势"""
        # 简化实现
        return 'neutral'

    def _assess_market_valuation(self) -> str:
        """评估市场估值"""
        # 简化实现
        return 'fair'

    def _get_technical_signals(self) -> Dict[str, str]:
        """获取技术信号"""
        return {
            'momentum': 'neutral',
            'trend': 'sideways',
            'volume': 'normal'
        }

    def _get_sector_performance(self) -> Dict[str, float]:
        """获取行业表现"""
        return {
            'technology': 0.02,
            'healthcare': 0.015,
            'finance': -0.005,
            'energy': -0.01,
            'consumer': 0.01
        }

    def _analyze_macro_indicators(self) -> Dict[str, Any]:
        """分析宏观经济指标"""
        return {
            'score': 0.6,
            'positive_factors': ['GDP增长稳定', '通胀回落'],
            'risk_factors': ['地缘政治风险', '利率不确定性']
        }

    def _analyze_market_sentiment(self) -> Dict[str, Any]:
        """分析市场情绪"""
        return {
            'score': 0.55,
            'positive_factors': ['企业盈利改善'],
            'risk_factors': ['投资者谨慎情绪']
        }

    def _analyze_market_technicals(self) -> Dict[str, Any]:
        """分析市场技术面"""
        return {
            'score': 0.65,
            'trend': 'uptrend',
            'momentum': 'positive'
        }

    def _screen_growth_stocks(self) -> List[Symbol]:
        """筛选成长股"""
        growth_candidates = [
            Symbol.parse('NASDAQ:AAPL'),
            Symbol.parse('NASDAQ:MSFT'),
            Symbol.parse('NASDAQ:GOOGL')
        ]
        return growth_candidates

    def _screen_value_stocks(self) -> List[Symbol]:
        """筛选价值股"""
        value_candidates = [
            Symbol.parse('NYSE:JPM'),
            Symbol.parse('NYSE:BAC')
        ]
        return value_candidates

    def _screen_dividend_stocks(self) -> List[Symbol]:
        """筛选分红股"""
        dividend_candidates = [
            Symbol.parse('NYSE:JNJ'),
            Symbol.parse('NYSE:PG')
        ]
        return dividend_candidates

    def _screen_momentum_stocks(self) -> List[Symbol]:
        """筛选动量股"""
        momentum_candidates = [
            Symbol.parse('NASDAQ:TSLA'),
            Symbol.parse('NASDAQ:NVDA')
        ]
        return momentum_candidates