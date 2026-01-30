"""
市场分析器

提供A股市场的综合分析能力
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

from ..data.lake import LocalDataLake
from ..data.schema import parse_symbol

logger = logging.getLogger(__name__)


@dataclass
class MarketTrend:
    """市场趋势分析结果"""
    symbol: str
    trend: str  # "上涨", "下跌", "震荡"
    strength: float  # 趋势强度 0-1
    support_level: float  # 支撑位
    resistance_level: float  # 阻力位
    current_price: float
    change_pct_1d: float
    change_pct_5d: float
    change_pct_20d: float
    volume_ratio: float  # 量比


@dataclass
class StockOpportunity:
    """投资机会"""
    symbol: str
    name: str
    score: float  # 综合评分 0-100
    current_price: float
    target_price: float  # 目标价
    expected_return: float  # 预期收益率
    risk_level: str  # "低", "中", "高"
    reasons: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    technical_signals: Dict[str, str] = field(default_factory=dict)


@dataclass
class MarketAnalysisReport:
    """市场分析报告"""
    timestamp: datetime
    market_status: str  # "牛市", "熊市", "震荡"
    market_sentiment: str  # "乐观", "谨慎", "悲观"
    index_analysis: Dict[str, MarketTrend]
    opportunities: List[StockOpportunity]
    risk_factors: List[str]
    recommendations: List[str]


class MarketAnalyzer:
    """
    市场分析器

    功能:
    1. 市场整体趋势分析
    2. 技术指标计算
    3. 投资机会筛选
    4. 风险因素识别
    """

    def __init__(self, data_dir: Path):
        """初始化市场分析器"""
        self.data_dir = data_dir
        self.lake = LocalDataLake(data_dir)
        logger.info("市场分析器初始化完成")

    def analyze_market(self, days: int = 60) -> MarketAnalysisReport:
        """
        综合市场分析

        Args:
            days: 分析的历史天数

        Returns:
            市场分析报告
        """
        logger.info(f"开始市场分析，分析周期: {days}天")

        # 分析市场指数
        index_analysis = self._analyze_indices(days)

        # 判断市场状态
        market_status, market_sentiment = self._determine_market_status(index_analysis)

        # 筛选投资机会
        opportunities = self._screen_opportunities(days)

        # 识别风险因素
        risk_factors = self._identify_risks(index_analysis)

        # 生成投资建议
        recommendations = self._generate_recommendations(
            market_status, opportunities, risk_factors
        )

        report = MarketAnalysisReport(
            timestamp=datetime.now(),
            market_status=market_status,
            market_sentiment=market_sentiment,
            index_analysis=index_analysis,
            opportunities=opportunities,
            risk_factors=risk_factors,
            recommendations=recommendations
        )

        logger.info("市场分析完成")
        return report

    def _analyze_indices(self, days: int) -> Dict[str, MarketTrend]:
        """分析市场指数"""
        # 暂时返回空字典，后续可以添加指数分析
        return {}

    def _analyze_stock(self, symbol: str, days: int = 60) -> Optional[MarketTrend]:
        """
        分析个股趋势

        Args:
            symbol: 股票代码
            days: 分析天数

        Returns:
            趋势分析结果
        """
        try:
            # 获取历史数据
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            bars = self.lake.query_bars(
                symbols=[symbol],
                start=start_date,
                end=end_date
            )

            if bars.empty or len(bars) < 20:
                logger.warning(f"{symbol} 数据不足")
                return None

            # 按时间排序
            bars = bars.sort_values('ts')

            # 计算技术指标
            close_prices = bars['close'].values
            volumes = bars['volume'].values

            current_price = float(close_prices[-1])

            # 计算涨跌幅
            change_1d = (close_prices[-1] / close_prices[-2] - 1) if len(close_prices) > 1 else 0
            change_5d = (close_prices[-1] / close_prices[-5] - 1) if len(close_prices) > 5 else 0
            change_20d = (close_prices[-1] / close_prices[-20] - 1) if len(close_prices) > 20 else 0

            # 计算均线
            ma5 = np.mean(close_prices[-5:]) if len(close_prices) >= 5 else current_price
            ma20 = np.mean(close_prices[-20:]) if len(close_prices) >= 20 else current_price
            ma60 = np.mean(close_prices[-60:]) if len(close_prices) >= 60 else current_price

            # 判断趋势
            if current_price > ma5 > ma20 > ma60:
                trend = "上涨"
                strength = 0.8
            elif current_price < ma5 < ma20 < ma60:
                trend = "下跌"
                strength = 0.8
            else:
                trend = "震荡"
                strength = 0.5

            # 计算支撑位和阻力位（简化版）
            recent_prices = close_prices[-20:]
            support_level = float(np.min(recent_prices))
            resistance_level = float(np.max(recent_prices))

            # 计算量比
            avg_volume = np.mean(volumes[-5:]) if len(volumes) >= 5 else volumes[-1]
            prev_avg_volume = np.mean(volumes[-10:-5]) if len(volumes) >= 10 else avg_volume
            volume_ratio = avg_volume / prev_avg_volume if prev_avg_volume > 0 else 1.0

            return MarketTrend(
                symbol=symbol,
                trend=trend,
                strength=strength,
                support_level=support_level,
                resistance_level=resistance_level,
                current_price=current_price,
                change_pct_1d=change_1d,
                change_pct_5d=change_5d,
                change_pct_20d=change_20d,
                volume_ratio=volume_ratio
            )

        except Exception as e:
            logger.error(f"分析 {symbol} 失败: {e}")
            return None

    def _determine_market_status(
        self,
        index_analysis: Dict[str, MarketTrend]
    ) -> Tuple[str, str]:
        """判断市场状态和情绪"""
        # 简化版本，后续可以基于指数分析
        return "震荡", "谨慎"

    def _screen_opportunities(self, days: int = 60) -> List[StockOpportunity]:
        """
        筛选投资机会

        Args:
            days: 分析天数

        Returns:
            投资机会列表
        """
        opportunities = []

        # 获取所有可用股票
        symbols = self._get_available_stocks()

        logger.info(f"开始筛选投资机会，候选股票: {len(symbols)}只")

        for symbol in symbols:
            try:
                opportunity = self._evaluate_stock(symbol, days)
                if opportunity and opportunity.score >= 60:
                    opportunities.append(opportunity)
            except Exception as e:
                logger.error(f"评估 {symbol} 失败: {e}")
                continue

        # 按评分排序
        opportunities.sort(key=lambda x: x.score, reverse=True)

        logger.info(f"筛选到 {len(opportunities)} 个投资机会")
        return opportunities

    def _evaluate_stock(self, symbol: str, days: int = 60) -> Optional[StockOpportunity]:
        """
        评估个股投资价值

        Args:
            symbol: 股票代码
            days: 分析天数

        Returns:
            投资机会，如果不符合条件返回None
        """
        # 分析趋势
        trend = self._analyze_stock(symbol, days)
        if not trend:
            return None

        # 计算综合评分
        score = 0.0
        reasons = []
        risks = []
        technical_signals = {}

        # 趋势评分（40分）
        if trend.trend == "上涨":
            score += 40 * trend.strength
            reasons.append(f"处于上涨趋势，强度{trend.strength:.1%}")
            technical_signals["趋势"] = "上涨"
        elif trend.trend == "震荡":
            score += 20
            reasons.append("处于震荡整理阶段")
            technical_signals["趋势"] = "震荡"
        else:
            risks.append("处于下跌趋势")
            technical_signals["趋势"] = "下跌"

        # 涨跌幅评分（30分）
        if -0.05 < trend.change_pct_20d < 0.05:
            # 20日涨跌幅在±5%以内，相对平稳
            score += 20
            reasons.append("近期价格相对稳定")
        elif trend.change_pct_20d > 0.15:
            # 涨幅过大，警惕回调
            score += 5
            risks.append(f"近20日涨幅{trend.change_pct_20d:.1%}，注意回调风险")
        elif trend.change_pct_20d < -0.15:
            # 跌幅较大，可能超跌
            score += 15
            reasons.append(f"近20日跌幅{trend.change_pct_20d:.1%}，可能存在超跌反弹机会")

        # 量价配合评分（20分）
        if trend.volume_ratio > 1.2:
            score += 15
            reasons.append(f"成交量放大，量比{trend.volume_ratio:.2f}")
            technical_signals["量能"] = "放大"
        elif trend.volume_ratio < 0.8:
            score += 5
            risks.append("成交量萎缩")
            technical_signals["量能"] = "萎缩"
        else:
            score += 10
            technical_signals["量能"] = "正常"

        # 位置评分（10分）
        price_position = (trend.current_price - trend.support_level) / \
                        (trend.resistance_level - trend.support_level) \
                        if trend.resistance_level > trend.support_level else 0.5

        if price_position < 0.3:
            score += 10
            reasons.append("价格接近支撑位，安全边际较高")
        elif price_position > 0.7:
            score += 3
            risks.append("价格接近阻力位")
        else:
            score += 6

        # 计算目标价和预期收益
        if trend.trend == "上涨":
            target_price = trend.resistance_level
        else:
            target_price = (trend.support_level + trend.resistance_level) / 2

        expected_return = (target_price / trend.current_price - 1) if trend.current_price > 0 else 0

        # 评估风险等级
        if score >= 80:
            risk_level = "低"
        elif score >= 60:
            risk_level = "中"
        else:
            risk_level = "高"

        # 获取股票名称
        name = self._get_stock_name(symbol)

        return StockOpportunity(
            symbol=symbol,
            name=name,
            score=score,
            current_price=trend.current_price,
            target_price=target_price,
            expected_return=expected_return,
            risk_level=risk_level,
            reasons=reasons,
            risks=risks,
            technical_signals=technical_signals
        )

    def _get_available_stocks(self) -> List[str]:
        """获取所有可用的A股股票"""
        try:
            # 从数据湖获取所有股票
            bars = self.lake.query_bars()
            if bars.empty:
                return []

            # 筛选A股（SSE和SZSE）
            symbols = bars['symbol'].unique()
            a_stocks = [s for s in symbols if s.startswith('SSE:') or s.startswith('SZSE:')]

            return a_stocks
        except Exception as e:
            logger.error(f"获取可用股票失败: {e}")
            return []

    def _get_stock_name(self, symbol: str) -> str:
        """获取股票名称"""
        # 简化版本，返回代码
        # 后续可以从数据源获取真实名称
        stock_names = {
            'SSE:600000': '浦发银行',
            'SSE:600036': '招商银行',
            'SZSE:000001': '平安银行',
            'SSE:600519': '贵州茅台'
        }
        return stock_names.get(symbol, symbol)

    def _identify_risks(self, index_analysis: Dict[str, MarketTrend]) -> List[str]:
        """识别市场风险因素"""
        risks = [
            "市场整体处于震荡期，方向不明确",
            "需要关注政策变化和外部环境",
            "个股分化明显，需要精选标的"
        ]
        return risks

    def _generate_recommendations(
        self,
        market_status: str,
        opportunities: List[StockOpportunity],
        risk_factors: List[str]
    ) -> List[str]:
        """生成投资建议"""
        recommendations = []

        if market_status == "震荡":
            recommendations.append("建议采用稳健策略，控制仓位在50-60%")
            recommendations.append("优先配置低风险、高确定性的标的")

        if opportunities:
            top3 = opportunities[:3]
            recommendations.append(
                f"重点关注: {', '.join([o.name for o in top3])}"
            )

        recommendations.append("建议分批建仓，避免一次性满仓")
        recommendations.append("设置止损位，控制单只股票损失在5%以内")

        return recommendations

    def generate_report_text(self, report: MarketAnalysisReport) -> str:
        """生成文本格式的分析报告"""
        lines = [
            "=" * 70,
            "📊 市场分析报告",
            "=" * 70,
            f"分析时间: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"市场状态: {report.market_status}",
            f"市场情绪: {report.market_sentiment}",
            "",
            "🎯 投资机会 (Top 5):",
            "-" * 70,
        ]

        if report.opportunities:
            lines.append(
                f"{'股票':<15} {'评分':>6} {'现价':>10} {'目标价':>10} {'预期收益':>10} {'风险':>6}"
            )
            lines.append("-" * 70)

            for opp in report.opportunities[:5]:
                lines.append(
                    f"{opp.name:<15} "
                    f"{opp.score:>6.1f} "
                    f"{opp.current_price:>10.2f} "
                    f"{opp.target_price:>10.2f} "
                    f"{opp.expected_return:>9.1%} "
                    f"{opp.risk_level:>6}"
                )

                if opp.reasons:
                    for reason in opp.reasons:
                        lines.append(f"  ✓ {reason}")
                if opp.risks:
                    for risk in opp.risks:
                        lines.append(f"  ⚠ {risk}")
                lines.append("")
        else:
            lines.append("暂无符合条件的投资机会")

        lines.extend([
            "",
            "⚠️ 风险提示:",
            "-" * 70,
        ])

        for risk in report.risk_factors:
            lines.append(f"  • {risk}")

        lines.extend([
            "",
            "💡 投资建议:",
            "-" * 70,
        ])

        for rec in report.recommendations:
            lines.append(f"  • {rec}")

        lines.append("=" * 70)

        return "\n".join(lines)


def get_default_market_analyzer() -> MarketAnalyzer:
    """获取默认市场分析器"""
    from pathlib import Path
    data_dir = Path.cwd() / "data"
    return MarketAnalyzer(data_dir)
