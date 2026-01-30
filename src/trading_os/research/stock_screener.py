"""
股票筛选器 - 基于真实基金公司运作方式

实现多因子股票筛选，替代硬编码股票列表
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class InvestmentStyle(Enum):
    """投资风格"""
    VALUE = "value"          # 价值投资
    GROWTH = "growth"        # 成长投资
    GARP = "garp"           # 合理价格的成长投资
    MOMENTUM = "momentum"    # 动量投资
    QUALITY = "quality"     # 质量投资


class Industry(Enum):
    """行业分类（简化版）"""
    BANKING = "银行"
    INSURANCE = "保险"
    SECURITIES = "证券"
    REAL_ESTATE = "房地产"
    CONSTRUCTION = "建筑"
    STEEL = "钢铁"
    COAL = "煤炭"
    PETROCHEMICAL = "石化"
    POWER = "电力"
    TRANSPORTATION = "交通运输"
    RETAIL = "零售"
    FOOD_BEVERAGE = "食品饮料"
    TEXTILE = "纺织"
    MEDICINE = "医药"
    ELECTRONICS = "电子"
    COMPUTER = "计算机"
    COMMUNICATIONS = "通信"
    AUTO = "汽车"
    MACHINERY = "机械"
    AEROSPACE = "航空航天"
    NEW_ENERGY = "新能源"
    ENVIRONMENTAL = "环保"


@dataclass
class StockFactor:
    """股票因子数据"""
    symbol: str
    name: str
    industry: Industry

    # 估值因子
    pe_ratio: float          # 市盈率
    pb_ratio: float          # 市净率
    ps_ratio: float          # 市销率
    ev_ebitda: float        # 企业价值倍数

    # 成长因子
    revenue_growth: float    # 营收增长率
    profit_growth: float    # 利润增长率
    roe_growth: float       # ROE增长率

    # 质量因子
    roe: float              # 净资产收益率
    roa: float              # 总资产收益率
    gross_margin: float     # 毛利率
    debt_ratio: float       # 资产负债率

    # 技术因子
    momentum_1m: float      # 1月动量
    momentum_3m: float      # 3月动量
    momentum_6m: float      # 6月动量
    volatility: float       # 波动率
    turnover_rate: float   # 换手率

    # 市值因子
    market_cap: float       # 总市值
    float_market_cap: float # 流通市值

    # 流动性因子
    avg_volume: float       # 平均成交量
    avg_amount: float       # 平均成交额

    last_update: datetime


@dataclass
class ScreeningCriteria:
    """筛选条件"""
    investment_style: InvestmentStyle

    # 基本筛选条件
    min_market_cap: float = 10e8        # 最小市值（亿元）
    max_market_cap: float = None        # 最大市值
    min_avg_amount: float = 1e6         # 最小日均成交额
    max_debt_ratio: float = 0.8         # 最大负债率
    min_roe: float = 0.05               # 最小ROE

    # 行业配置
    target_industries: List[Industry] = None
    exclude_industries: List[Industry] = None
    max_industry_weight: float = 0.3    # 单行业最大权重

    # 风格因子权重
    value_weight: float = 0.3           # 价值因子权重
    growth_weight: float = 0.3          # 成长因子权重
    quality_weight: float = 0.2         # 质量因子权重
    momentum_weight: float = 0.2        # 动量因子权重

    # 组合约束
    max_position_count: int = 50        # 最大持仓数量
    min_position_count: int = 20        # 最小持仓数量
    max_single_weight: float = 0.1      # 单股最大权重


class StockScreener:
    """股票筛选器"""

    def __init__(self, data_source=None):
        self.data_source = data_source
        self.stock_universe: List[StockFactor] = []
        self.screening_results: Dict[str, Any] = {}

    def load_stock_universe(self, symbols: List[str] = None) -> None:
        """加载股票池"""
        if symbols is None:
            # 默认A股主要股票池
            symbols = self._get_default_stock_universe()

        logger.info(f"加载股票池: {len(symbols)} 只股票")

        for symbol in symbols:
            try:
                factor = self._calculate_stock_factors(symbol)
                if factor:
                    self.stock_universe.append(factor)
            except Exception as e:
                logger.warning(f"计算 {symbol} 因子失败: {e}")

        logger.info(f"成功加载 {len(self.stock_universe)} 只股票的因子数据")

    def screen_stocks(self, criteria: ScreeningCriteria) -> List[StockFactor]:
        """根据条件筛选股票"""
        logger.info(f"开始股票筛选，投资风格: {criteria.investment_style.value}")

        # 第一步：基础筛选
        filtered_stocks = self._apply_basic_filters(criteria)
        logger.info(f"基础筛选后剩余: {len(filtered_stocks)} 只")

        # 第二步：因子评分
        scored_stocks = self._calculate_factor_scores(filtered_stocks, criteria)
        logger.info(f"因子评分完成")

        # 第三步：行业平衡
        balanced_stocks = self._apply_industry_balance(scored_stocks, criteria)
        logger.info(f"行业平衡后: {len(balanced_stocks)} 只")

        # 第四步：最终排序和选择
        final_stocks = self._final_selection(balanced_stocks, criteria)
        logger.info(f"最终选择: {len(final_stocks)} 只股票")

        return final_stocks

    def _get_default_stock_universe(self) -> List[str]:
        """获取默认股票池"""
        # 模拟A股主要股票池（实际应该从数据源获取）
        default_universe = [
            # 银行
            "SSE:600000", "SSE:600036", "SSE:601398", "SSE:601939", "SSE:601288",
            "SZSE:000001", "SZSE:000002", "SZSE:002142",

            # 保险
            "SSE:601318", "SSE:601601", "SSE:601628",

            # 证券
            "SSE:600030", "SSE:600837", "SZSE:000166",

            # 白酒
            "SSE:600519", "SZSE:000858", "SSE:600809",

            # 科技
            "SZSE:000063", "SZSE:002415", "SZSE:300059",

            # 医药
            "SZSE:000661", "SSE:600276", "SZSE:300015",

            # 新能源
            "SZSE:300750", "SSE:600885", "SZSE:002594",

            # 消费
            "SZSE:000895", "SSE:600887", "SZSE:002304"
        ]

        return default_universe

    def _calculate_stock_factors(self, symbol: str) -> Optional[StockFactor]:
        """计算单只股票的因子数据"""
        try:
            # 这里应该从数据源获取真实数据
            # 目前返回模拟数据用于演示

            # 解析symbol
            exchange, ticker = symbol.split(':')

            # 模拟因子数据
            factor = StockFactor(
                symbol=symbol,
                name=self._get_stock_name(ticker),
                industry=self._get_industry(ticker),

                # 模拟估值因子
                pe_ratio=np.random.uniform(5, 50),
                pb_ratio=np.random.uniform(0.5, 5),
                ps_ratio=np.random.uniform(0.5, 10),
                ev_ebitda=np.random.uniform(3, 30),

                # 模拟成长因子
                revenue_growth=np.random.uniform(-0.2, 0.5),
                profit_growth=np.random.uniform(-0.3, 0.8),
                roe_growth=np.random.uniform(-0.5, 1.0),

                # 模拟质量因子
                roe=np.random.uniform(0.02, 0.25),
                roa=np.random.uniform(0.01, 0.15),
                gross_margin=np.random.uniform(0.1, 0.6),
                debt_ratio=np.random.uniform(0.2, 0.8),

                # 模拟技术因子
                momentum_1m=np.random.uniform(-0.2, 0.2),
                momentum_3m=np.random.uniform(-0.4, 0.4),
                momentum_6m=np.random.uniform(-0.6, 0.6),
                volatility=np.random.uniform(0.15, 0.45),
                turnover_rate=np.random.uniform(0.5, 5.0),

                # 模拟市值因子
                market_cap=np.random.uniform(50e8, 2000e8),
                float_market_cap=np.random.uniform(30e8, 1500e8),

                # 模拟流动性因子
                avg_volume=np.random.uniform(1e6, 1e8),
                avg_amount=np.random.uniform(1e7, 1e9),

                last_update=datetime.now()
            )

            return factor

        except Exception as e:
            logger.error(f"计算 {symbol} 因子失败: {e}")
            return None

    def _get_stock_name(self, ticker: str) -> str:
        """获取股票名称"""
        name_map = {
            "600000": "浦发银行",
            "600036": "招商银行",
            "601398": "工商银行",
            "000001": "平安银行",
            "600519": "贵州茅台",
            "000858": "五粮液"
        }
        return name_map.get(ticker, f"股票{ticker}")

    def _get_industry(self, ticker: str) -> Industry:
        """获取股票行业"""
        industry_map = {
            "600000": Industry.BANKING,
            "600036": Industry.BANKING,
            "601398": Industry.BANKING,
            "000001": Industry.BANKING,
            "600519": Industry.FOOD_BEVERAGE,
            "000858": Industry.FOOD_BEVERAGE
        }
        return industry_map.get(ticker, Industry.BANKING)

    def _apply_basic_filters(self, criteria: ScreeningCriteria) -> List[StockFactor]:
        """应用基础筛选条件"""
        filtered = []

        for stock in self.stock_universe:
            # 市值筛选
            if stock.market_cap < criteria.min_market_cap:
                continue
            if criteria.max_market_cap and stock.market_cap > criteria.max_market_cap:
                continue

            # 流动性筛选
            if stock.avg_amount < criteria.min_avg_amount:
                continue

            # 财务质量筛选
            if stock.debt_ratio > criteria.max_debt_ratio:
                continue
            if stock.roe < criteria.min_roe:
                continue

            # 行业筛选
            if criteria.exclude_industries and stock.industry in criteria.exclude_industries:
                continue
            if criteria.target_industries and stock.industry not in criteria.target_industries:
                continue

            filtered.append(stock)

        return filtered

    def _calculate_factor_scores(self, stocks: List[StockFactor], criteria: ScreeningCriteria) -> List[tuple]:
        """计算因子得分"""
        scored_stocks = []

        for stock in stocks:
            # 价值因子得分（越低越好）
            value_score = self._calculate_value_score(stock, stocks)

            # 成长因子得分（越高越好）
            growth_score = self._calculate_growth_score(stock, stocks)

            # 质量因子得分（越高越好）
            quality_score = self._calculate_quality_score(stock, stocks)

            # 动量因子得分（越高越好）
            momentum_score = self._calculate_momentum_score(stock, stocks)

            # 综合得分
            total_score = (
                value_score * criteria.value_weight +
                growth_score * criteria.growth_weight +
                quality_score * criteria.quality_weight +
                momentum_score * criteria.momentum_weight
            )

            scored_stocks.append((stock, total_score, {
                'value': value_score,
                'growth': growth_score,
                'quality': quality_score,
                'momentum': momentum_score
            }))

        # 按得分排序
        scored_stocks.sort(key=lambda x: x[1], reverse=True)
        return scored_stocks

    def _calculate_value_score(self, stock: StockFactor, all_stocks: List[StockFactor]) -> float:
        """计算价值因子得分"""
        pe_values = [s.pe_ratio for s in all_stocks if s.pe_ratio > 0]
        pb_values = [s.pb_ratio for s in all_stocks if s.pb_ratio > 0]

        # 计算百分位排名（越低越好，所以用1减去百分位）
        pe_rank = 1 - (stock.pe_ratio - min(pe_values)) / (max(pe_values) - min(pe_values)) if pe_values else 0.5
        pb_rank = 1 - (stock.pb_ratio - min(pb_values)) / (max(pb_values) - min(pb_values)) if pb_values else 0.5

        return (pe_rank + pb_rank) / 2

    def _calculate_growth_score(self, stock: StockFactor, all_stocks: List[StockFactor]) -> float:
        """计算成长因子得分"""
        revenue_values = [s.revenue_growth for s in all_stocks]
        profit_values = [s.profit_growth for s in all_stocks]

        # 计算百分位排名
        revenue_rank = (stock.revenue_growth - min(revenue_values)) / (max(revenue_values) - min(revenue_values)) if revenue_values else 0.5
        profit_rank = (stock.profit_growth - min(profit_values)) / (max(profit_values) - min(profit_values)) if profit_values else 0.5

        return (revenue_rank + profit_rank) / 2

    def _calculate_quality_score(self, stock: StockFactor, all_stocks: List[StockFactor]) -> float:
        """计算质量因子得分"""
        roe_values = [s.roe for s in all_stocks]
        margin_values = [s.gross_margin for s in all_stocks]
        debt_values = [s.debt_ratio for s in all_stocks]

        # 计算百分位排名
        roe_rank = (stock.roe - min(roe_values)) / (max(roe_values) - min(roe_values)) if roe_values else 0.5
        margin_rank = (stock.gross_margin - min(margin_values)) / (max(margin_values) - min(margin_values)) if margin_values else 0.5
        debt_rank = 1 - (stock.debt_ratio - min(debt_values)) / (max(debt_values) - min(debt_values)) if debt_values else 0.5

        return (roe_rank + margin_rank + debt_rank) / 3

    def _calculate_momentum_score(self, stock: StockFactor, all_stocks: List[StockFactor]) -> float:
        """计算动量因子得分"""
        momentum_3m_values = [s.momentum_3m for s in all_stocks]
        momentum_6m_values = [s.momentum_6m for s in all_stocks]

        # 计算百分位排名
        momentum_3m_rank = (stock.momentum_3m - min(momentum_3m_values)) / (max(momentum_3m_values) - min(momentum_3m_values)) if momentum_3m_values else 0.5
        momentum_6m_rank = (stock.momentum_6m - min(momentum_6m_values)) / (max(momentum_6m_values) - min(momentum_6m_values)) if momentum_6m_values else 0.5

        return (momentum_3m_rank + momentum_6m_rank) / 2

    def _apply_industry_balance(self, scored_stocks: List[tuple], criteria: ScreeningCriteria) -> List[tuple]:
        """应用行业平衡"""
        industry_counts = {}
        balanced_stocks = []
        max_per_industry = int(criteria.max_position_count * criteria.max_industry_weight)

        for stock, score, factors in scored_stocks:
            industry = stock.industry
            current_count = industry_counts.get(industry, 0)

            if current_count < max_per_industry:
                balanced_stocks.append((stock, score, factors))
                industry_counts[industry] = current_count + 1

            # 如果已经达到最大持仓数量，停止
            if len(balanced_stocks) >= criteria.max_position_count:
                break

        return balanced_stocks

    def _final_selection(self, scored_stocks: List[tuple], criteria: ScreeningCriteria) -> List[StockFactor]:
        """最终选择"""
        # 确保至少有最小持仓数量
        target_count = max(criteria.min_position_count,
                          min(len(scored_stocks), criteria.max_position_count))

        selected_stocks = [stock for stock, score, factors in scored_stocks[:target_count]]

        # 记录筛选结果
        self.screening_results = {
            'criteria': criteria,
            'total_universe': len(self.stock_universe),
            'after_basic_filter': len(scored_stocks),
            'final_selection': len(selected_stocks),
            'industry_distribution': self._get_industry_distribution(selected_stocks),
            'timestamp': datetime.now()
        }

        return selected_stocks

    def _get_industry_distribution(self, stocks: List[StockFactor]) -> Dict[str, int]:
        """获取行业分布"""
        distribution = {}
        for stock in stocks:
            industry = stock.industry.value
            distribution[industry] = distribution.get(industry, 0) + 1
        return distribution

    def get_screening_report(self) -> Dict[str, Any]:
        """获取筛选报告"""
        return self.screening_results