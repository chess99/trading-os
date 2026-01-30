"""
投资组合管理器 - 基于真实基金公司运作方式

实现动态投资组合构建和管理
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np
from datetime import datetime
import logging

from .stock_screener import StockFactor, StockScreener, ScreeningCriteria, InvestmentStyle, Industry

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """市场状态"""
    BULL_MARKET = "bull_market"      # 牛市
    BEAR_MARKET = "bear_market"      # 熊市
    SIDEWAYS = "sideways"            # 震荡市
    RECOVERY = "recovery"            # 复苏期
    CORRECTION = "correction"        # 调整期


class RiskLevel(Enum):
    """风险等级"""
    CONSERVATIVE = "conservative"    # 保守型
    MODERATE = "moderate"           # 稳健型
    AGGRESSIVE = "aggressive"       # 积极型


@dataclass
class PortfolioPosition:
    """投资组合持仓"""
    symbol: str
    name: str
    industry: Industry
    weight: float               # 权重
    shares: int                # 股数
    cost_price: float          # 成本价
    current_price: float       # 当前价
    market_value: float        # 市值
    pnl: float                 # 盈亏
    pnl_ratio: float          # 盈亏比例

    # 风险指标
    beta: float               # 贝塔值
    volatility: float         # 波动率
    var_1d: float            # 1日VaR

    entry_date: datetime      # 建仓日期
    last_update: datetime     # 最后更新时间


@dataclass
class PortfolioMetrics:
    """投资组合指标"""
    total_value: float        # 总价值
    cash: float              # 现金
    invested_value: float    # 投资价值
    total_pnl: float         # 总盈亏
    total_return: float      # 总收益率

    # 风险指标
    portfolio_beta: float    # 组合贝塔
    portfolio_volatility: float  # 组合波动率
    sharpe_ratio: float      # 夏普比率
    max_drawdown: float      # 最大回撤
    var_1d: float           # 1日VaR

    # 配置指标
    position_count: int      # 持仓数量
    industry_concentration: Dict[str, float]  # 行业集中度
    top5_concentration: float  # 前5大持仓集中度

    last_update: datetime


class PortfolioManager:
    """投资组合管理器"""

    def __init__(self, initial_cash: float = 1000000.0):
        self.initial_cash = initial_cash
        self.current_cash = initial_cash
        self.positions: Dict[str, PortfolioPosition] = {}
        self.transaction_costs = 0.001  # 交易成本
        self.screener = StockScreener()

        # 历史记录
        self.portfolio_history: List[PortfolioMetrics] = []
        self.transaction_history: List[Dict[str, Any]] = []

    def initialize_portfolio(self, risk_level: RiskLevel = RiskLevel.MODERATE) -> None:
        """初始化投资组合"""
        logger.info(f"初始化投资组合，风险等级: {risk_level.value}")

        # 根据风险等级设置筛选条件
        criteria = self._get_screening_criteria_by_risk(risk_level)

        # 加载股票池并筛选
        self.screener.load_stock_universe()
        selected_stocks = self.screener.screen_stocks(criteria)

        if not selected_stocks:
            logger.warning("股票筛选结果为空，无法初始化投资组合")
            return

        # 构建初始投资组合
        self._build_initial_portfolio(selected_stocks, criteria)

        logger.info(f"投资组合初始化完成，持仓 {len(self.positions)} 只股票")

    def _get_screening_criteria_by_risk(self, risk_level: RiskLevel) -> ScreeningCriteria:
        """根据风险等级获取筛选条件"""

        if risk_level == RiskLevel.CONSERVATIVE:
            return ScreeningCriteria(
                investment_style=InvestmentStyle.VALUE,
                min_market_cap=100e8,
                min_avg_amount=5e6,
                max_debt_ratio=0.6,
                min_roe=0.08,
                max_industry_weight=0.25,
                max_single_weight=0.08,
                value_weight=0.5,
                growth_weight=0.1,
                quality_weight=0.3,
                momentum_weight=0.1,
                max_position_count=30,
                min_position_count=25
            )
        elif risk_level == RiskLevel.AGGRESSIVE:
            return ScreeningCriteria(
                investment_style=InvestmentStyle.GROWTH,
                min_market_cap=20e8,
                min_avg_amount=1e6,
                max_debt_ratio=0.8,
                min_roe=0.03,
                max_industry_weight=0.3,
                max_single_weight=0.1,
                value_weight=0.1,
                growth_weight=0.5,
                quality_weight=0.2,
                momentum_weight=0.2,
                max_position_count=40,
                min_position_count=30
            )
        else:  # MODERATE
            return ScreeningCriteria(
                investment_style=InvestmentStyle.GARP,
                min_market_cap=50e8,
                min_avg_amount=2e6,
                max_debt_ratio=0.7,
                min_roe=0.06,
                max_industry_weight=0.3,
                max_single_weight=0.1,
                value_weight=0.25,
                growth_weight=0.35,
                quality_weight=0.25,
                momentum_weight=0.15,
                max_position_count=35,
                min_position_count=25
            )

    def _build_initial_portfolio(self, selected_stocks: List[StockFactor], criteria: ScreeningCriteria) -> None:
        """构建初始投资组合"""
        # 计算权重分配
        weights = self._calculate_optimal_weights(selected_stocks, criteria)

        # 预留现金比例
        cash_ratio = 0.1  # 保留10%现金
        investable_cash = self.current_cash * (1 - cash_ratio)

        # 建仓
        for stock, weight in weights.items():
            if weight > 0:
                target_value = investable_cash * weight
                self._buy_stock(stock, target_value)

        # 更新现金
        self.current_cash = self.initial_cash - sum(pos.market_value for pos in self.positions.values())

    def _calculate_optimal_weights(self, stocks: List[StockFactor], criteria: ScreeningCriteria) -> Dict[str, float]:
        """计算最优权重"""
        # 简化的等权重分配（实际应该使用优化算法）
        n_stocks = len(stocks)
        if n_stocks == 0:
            return {}

        # 基础等权重
        base_weight = 1.0 / n_stocks

        weights = {}
        for stock in stocks:
            # 根据市值调整权重
            market_cap_factor = min(stock.market_cap / 500e8, 2.0)  # 市值因子，最大2倍

            # 根据质量因子调整
            quality_factor = max(stock.roe / 0.15, 0.5)  # 质量因子，最小0.5倍

            # 最终权重
            adjusted_weight = base_weight * market_cap_factor * quality_factor

            # 限制单股最大权重
            adjusted_weight = min(adjusted_weight, criteria.max_single_weight)

            weights[stock.symbol] = adjusted_weight

        # 标准化权重
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {symbol: weight / total_weight for symbol, weight in weights.items()}

        return weights

    def _buy_stock(self, symbol: str, target_value: float) -> None:
        """买入股票"""
        try:
            # 获取当前价格（模拟）
            current_price = self._get_current_price(symbol)

            # 计算股数
            shares = int(target_value / current_price)
            if shares == 0:
                return

            # 计算实际成本
            actual_cost = shares * current_price
            transaction_cost = actual_cost * self.transaction_costs
            total_cost = actual_cost + transaction_cost

            # 创建持仓
            stock_factor = self._get_stock_factor(symbol)
            position = PortfolioPosition(
                symbol=symbol,
                name=stock_factor.name if stock_factor else symbol,
                industry=stock_factor.industry if stock_factor else Industry.BANKING,
                weight=0.0,  # 稍后计算
                shares=shares,
                cost_price=current_price,
                current_price=current_price,
                market_value=actual_cost,
                pnl=0.0,
                pnl_ratio=0.0,
                beta=1.0,  # 模拟值
                volatility=0.25,  # 模拟值
                var_1d=actual_cost * 0.02,  # 模拟值
                entry_date=datetime.now(),
                last_update=datetime.now()
            )

            self.positions[symbol] = position

            # 记录交易
            self.transaction_history.append({
                'timestamp': datetime.now(),
                'symbol': symbol,
                'action': 'BUY',
                'shares': shares,
                'price': current_price,
                'value': actual_cost,
                'cost': transaction_cost
            })

            logger.info(f"买入 {symbol}: {shares}股，价格 {current_price:.2f}，价值 {actual_cost:.0f}")

        except Exception as e:
            logger.error(f"买入 {symbol} 失败: {e}")

    def _get_current_price(self, symbol: str) -> float:
        """
        获取当前价格（从数据湖）

        ⚠️ 严格禁止使用模拟数据！
        """
        from ..data.lake import LocalDataLake
        from pathlib import Path

        try:
            lake = LocalDataLake(Path("data"))
            bars = lake.query_bars(symbols=[symbol], limit=1)

            if bars.empty:
                raise ValueError(f"数据湖中没有 {symbol} 的数据")

            price = float(bars.iloc[-1]['close'])

            if price <= 0:
                raise ValueError(f"{symbol} 价格无效: {price}")

            logger.debug(f"获取 {symbol} 价格: {price:.2f}")
            return price

        except Exception as e:
            # 数据获取失败时必须抛出异常，绝不降级到模拟数据
            raise RuntimeError(
                f"无法获取 {symbol} 的真实价格: {e}。"
                f"系统不允许使用模拟数据进行投资分析。"
            ) from e

    def _get_stock_factor(self, symbol: str) -> Optional[StockFactor]:
        """获取股票因子"""
        for stock in self.screener.stock_universe:
            if stock.symbol == symbol:
                return stock
        return None

    def update_portfolio(self) -> PortfolioMetrics:
        """更新投资组合"""
        logger.info("更新投资组合数据")

        total_market_value = 0.0
        total_pnl = 0.0

        # 更新每个持仓
        for symbol, position in self.positions.items():
            # 更新价格
            new_price = self._get_current_price(symbol)
            position.current_price = new_price
            position.market_value = position.shares * new_price
            position.pnl = position.market_value - (position.shares * position.cost_price)
            position.pnl_ratio = position.pnl / (position.shares * position.cost_price) if position.cost_price > 0 else 0
            position.last_update = datetime.now()

            total_market_value += position.market_value
            total_pnl += position.pnl

        # 更新权重
        for position in self.positions.values():
            position.weight = position.market_value / total_market_value if total_market_value > 0 else 0

        # 计算组合指标
        metrics = self._calculate_portfolio_metrics(total_market_value, total_pnl)

        # 保存历史
        self.portfolio_history.append(metrics)

        return metrics

    def _calculate_portfolio_metrics(self, total_market_value: float, total_pnl: float) -> PortfolioMetrics:
        """计算投资组合指标"""
        total_value = total_market_value + self.current_cash
        invested_value = total_market_value
        total_return = total_pnl / (self.initial_cash - self.current_cash) if (self.initial_cash - self.current_cash) > 0 else 0

        # 计算行业集中度
        industry_concentration = {}
        for position in self.positions.values():
            industry = position.industry.value
            industry_concentration[industry] = industry_concentration.get(industry, 0) + position.weight

        # 计算前5大持仓集中度
        position_weights = sorted([pos.weight for pos in self.positions.values()], reverse=True)
        top5_concentration = sum(position_weights[:5])

        # 计算组合风险指标（简化）
        portfolio_beta = np.mean([pos.beta * pos.weight for pos in self.positions.values()]) if self.positions else 1.0
        portfolio_volatility = np.sqrt(sum([(pos.volatility * pos.weight) ** 2 for pos in self.positions.values()])) if self.positions else 0.0

        # 计算夏普比率（简化）
        risk_free_rate = 0.03  # 假设无风险利率3%
        sharpe_ratio = (total_return - risk_free_rate) / portfolio_volatility if portfolio_volatility > 0 else 0

        # 计算最大回撤（基于历史）
        max_drawdown = self._calculate_max_drawdown()

        # 计算VaR（简化）
        var_1d = total_value * 0.02  # 假设2%的1日VaR

        return PortfolioMetrics(
            total_value=total_value,
            cash=self.current_cash,
            invested_value=invested_value,
            total_pnl=total_pnl,
            total_return=total_return,
            portfolio_beta=portfolio_beta,
            portfolio_volatility=portfolio_volatility,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            var_1d=var_1d,
            position_count=len(self.positions),
            industry_concentration=industry_concentration,
            top5_concentration=top5_concentration,
            last_update=datetime.now()
        )

    def _calculate_max_drawdown(self) -> float:
        """计算最大回撤"""
        if len(self.portfolio_history) < 2:
            return 0.0

        values = [metrics.total_value for metrics in self.portfolio_history]
        peak = values[0]
        max_dd = 0.0

        for value in values[1:]:
            if value > peak:
                peak = value
            else:
                drawdown = (peak - value) / peak
                max_dd = max(max_dd, drawdown)

        return max_dd

    def rebalance_portfolio(self, market_regime: MarketRegime = MarketRegime.SIDEWAYS) -> None:
        """投资组合再平衡"""
        logger.info(f"投资组合再平衡，市场状态: {market_regime.value}")

        # 根据市场状态调整策略
        if market_regime == MarketRegime.BULL_MARKET:
            # 牛市：增加成长股权重
            self._adjust_for_bull_market()
        elif market_regime == MarketRegime.BEAR_MARKET:
            # 熊市：增加防御性股票权重
            self._adjust_for_bear_market()
        else:
            # 震荡市：平衡配置
            self._adjust_for_sideways_market()

    def _adjust_for_bull_market(self) -> None:
        """牛市调整"""
        # 增加成长股权重，减少现金比例
        pass

    def _adjust_for_bear_market(self) -> None:
        """熊市调整"""
        # 增加防御性股票权重，提高现金比例
        pass

    def _adjust_for_sideways_market(self) -> None:
        """震荡市调整"""
        # 平衡配置，适度调整
        pass

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """获取投资组合摘要"""
        if not self.positions:
            return {"status": "empty", "message": "投资组合为空"}

        current_metrics = self.update_portfolio()

        # 获取前5大持仓
        top_positions = sorted(self.positions.values(), key=lambda x: x.weight, reverse=True)[:5]

        return {
            "overview": {
                "total_value": current_metrics.total_value,
                "total_return": current_metrics.total_return,
                "position_count": current_metrics.position_count,
                "cash_ratio": current_metrics.cash / current_metrics.total_value
            },
            "risk_metrics": {
                "portfolio_volatility": current_metrics.portfolio_volatility,
                "sharpe_ratio": current_metrics.sharpe_ratio,
                "max_drawdown": current_metrics.max_drawdown,
                "var_1d": current_metrics.var_1d
            },
            "top_positions": [
                {
                    "symbol": pos.symbol,
                    "name": pos.name,
                    "weight": pos.weight,
                    "pnl_ratio": pos.pnl_ratio
                }
                for pos in top_positions
            ],
            "industry_distribution": current_metrics.industry_concentration,
            "last_update": current_metrics.last_update
        }