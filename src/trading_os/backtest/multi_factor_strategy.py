"""
多因子选股策略回测

基于真实因子数据的选股策略,用于验证策略有效性。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional

try:
    import numpy as np
    import pandas as pd
except ImportError:
    np = None
    pd = None

if TYPE_CHECKING:
    import pandas as pd_types  # noqa: F401


@dataclass
class FactorWeights:
    """因子权重配置"""

    # 估值因子
    pe_weight: float = 0.15  # 市盈率(越低越好)
    pb_weight: float = 0.15  # 市净率(越低越好)

    # 财务因子
    roe_weight: float = 0.20  # 净资产收益率(越高越好)
    roa_weight: float = 0.10  # 总资产收益率(越高越好)

    # 技术因子
    momentum_weight: float = 0.20  # 动量(越高越好)
    volatility_weight: float = 0.10  # 波动率(越低越好)

    # 其他因子
    volume_weight: float = 0.10  # 成交量(越高越好)


@dataclass
class BacktestConfig:
    """回测配置"""

    initial_cash: float = 500_000.0  # 初始资金
    top_n: int = 10  # 选择前N只股票
    rebalance_days: int = 30  # 调仓周期(天)
    position_limit: float = 0.20  # 单只股票最大仓位
    total_position: float = 0.60  # 总仓位
    fee_rate: float = 0.0003  # 手续费率
    min_shares: int = 100  # 最小交易单位


class MultiFactorBacktest:
    """多因子策略回测引擎"""

    def __init__(self, config: BacktestConfig, factor_weights: Optional[FactorWeights] = None):
        if pd is None or np is None:
            raise RuntimeError("需要安装pandas和numpy")

        self.config = config
        self.weights = factor_weights or FactorWeights()

        # 回测状态
        self.cash = config.initial_cash
        self.positions: Dict[str, int] = {}  # {symbol: shares}
        self.equity_curve: List[Dict] = []
        self.trades: List[Dict] = []
        self.rebalance_dates: List[datetime] = []

    def calculate_factor_score(self, factors: Dict[str, float]) -> float:
        """
        计算因子综合得分

        Args:
            factors: 因子值字典

        Returns:
            综合得分(0-100)
        """
        score = 0.0

        # 估值因子(越低越好,需要反转)
        if 'pe' in factors and factors['pe'] > 0:
            pe_score = 100 / (1 + factors['pe'] / 20)  # 归一化到0-100
            score += pe_score * self.weights.pe_weight

        if 'pb' in factors and factors['pb'] > 0:
            pb_score = 100 / (1 + factors['pb'] / 5)
            score += pb_score * self.weights.pb_weight

        # 财务因子(越高越好)
        if 'roe' in factors:
            roe_score = min(100, factors['roe'] * 5)  # ROE 20%得100分
            score += roe_score * self.weights.roe_weight

        if 'roa' in factors:
            roa_score = min(100, factors['roa'] * 10)  # ROA 10%得100分
            score += roa_score * self.weights.roa_weight

        # 技术因子
        if 'momentum' in factors:
            # 动量通常是收益率,转换为0-100分数
            momentum_score = min(100, max(0, 50 + factors['momentum'] * 2))
            score += momentum_score * self.weights.momentum_weight

        if 'volatility' in factors and factors['volatility'] > 0:
            # 波动率越低越好
            vol_score = 100 / (1 + factors['volatility'] * 10)
            score += vol_score * self.weights.volatility_weight

        if 'volume' in factors and factors['volume'] > 0:
            # 成交量越大越好(流动性)
            volume_score = min(100, np.log10(factors['volume']) * 10)
            score += volume_score * self.weights.volume_weight

        return score

    def select_stocks(
        self,
        stock_data: Dict[str, Dict[str, float]],
        date: datetime
    ) -> List[tuple[str, float]]:
        """
        根据因子选择股票

        Args:
            stock_data: {symbol: {factor: value}}
            date: 当前日期

        Returns:
            [(symbol, score), ...] 按得分排序
        """
        scores = []

        for symbol, factors in stock_data.items():
            score = self.calculate_factor_score(factors)
            scores.append((symbol, score))

        # 按得分排序,选择前N只
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:self.config.top_n]

    def rebalance(
        self,
        selected_stocks: List[tuple[str, float]],
        prices: Dict[str, float],
        date: datetime
    ):
        """
        调仓

        Args:
            selected_stocks: [(symbol, score), ...]
            prices: {symbol: price}
            date: 当前日期
        """
        if not selected_stocks:
            return

        # 计算当前持仓市值
        current_value = self.cash
        for symbol, shares in self.positions.items():
            if symbol in prices:
                current_value += shares * prices[symbol]

        # 计算目标仓位
        total_capital = current_value * self.config.total_position

        # 使用智能资金分配算法
        from ..execution.capital_allocation import CapitalAllocator, AllocationStrategy

        allocator = CapitalAllocator(
            max_position_ratio=self.config.position_limit,
            target_total_position=self.config.total_position
        )

        # 准备候选列表
        opportunities = [
            {
                'symbol': symbol,
                'name': symbol,
                'score': score,
                'current_price': prices.get(symbol, 0),
                'expected_return': score / 100,  # 简化:用评分估算收益
                'risk_level': 'medium'
            }
            for symbol, score in selected_stocks
            if symbol in prices and prices[symbol] > 0
        ]

        # 分配资金
        allocation_plan = allocator.allocate(
            opportunities=opportunities,
            total_value=current_value,
            current_position_value=current_value - self.cash,
            available_cash=self.cash,
            strategy=AllocationStrategy.DYNAMIC
        )

        # 执行调仓
        target_positions = {}
        for target in allocation_plan.targets:
            if target.shares >= self.config.min_shares:
                target_positions[target.symbol] = target.shares

        # 卖出不在目标持仓中的股票
        for symbol in list(self.positions.keys()):
            if symbol not in target_positions:
                shares = self.positions[symbol]
                if symbol in prices:
                    price = prices[symbol]
                    proceeds = shares * price
                    fee = proceeds * self.config.fee_rate
                    self.cash += proceeds - fee

                    self.trades.append({
                        'date': date,
                        'symbol': symbol,
                        'action': 'SELL',
                        'shares': shares,
                        'price': price,
                        'amount': proceeds,
                        'fee': fee
                    })

                del self.positions[symbol]

        # 买入或调整目标持仓
        for symbol, target_shares in target_positions.items():
            current_shares = self.positions.get(symbol, 0)
            delta = target_shares - current_shares

            if delta > 0:  # 买入
                price = prices[symbol]
                cost = delta * price
                fee = cost * self.config.fee_rate
                total_cost = cost + fee

                if total_cost <= self.cash:
                    self.cash -= total_cost
                    self.positions[symbol] = target_shares

                    self.trades.append({
                        'date': date,
                        'symbol': symbol,
                        'action': 'BUY',
                        'shares': delta,
                        'price': price,
                        'amount': cost,
                        'fee': fee
                    })

            elif delta < 0:  # 卖出部分
                price = prices[symbol]
                proceeds = abs(delta) * price
                fee = proceeds * self.config.fee_rate
                self.cash += proceeds - fee
                self.positions[symbol] = target_shares

                self.trades.append({
                    'date': date,
                    'symbol': symbol,
                    'action': 'SELL',
                    'shares': abs(delta),
                    'price': price,
                    'amount': proceeds,
                    'fee': fee
                })

        self.rebalance_dates.append(date)

    def update_equity_curve(self, date: datetime, prices: Dict[str, float]):
        """更新权益曲线"""
        holdings_value = sum(
            shares * prices.get(symbol, 0)
            for symbol, shares in self.positions.items()
        )

        total_equity = self.cash + holdings_value

        self.equity_curve.append({
            'date': date,
            'cash': self.cash,
            'holdings': holdings_value,
            'total': total_equity,
            'return': (total_equity - self.config.initial_cash) / self.config.initial_cash
        })

    def run(
        self,
        historical_data: Dict[datetime, Dict[str, Dict]],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """
        运行回测

        Args:
            historical_data: {date: {symbol: {'price': x, 'factors': {...}}}}
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            回测结果
        """
        dates = sorted(historical_data.keys())

        if start_date:
            dates = [d for d in dates if d >= start_date]
        if end_date:
            dates = [d for d in dates if d <= end_date]

        if not dates:
            raise ValueError("没有可用的历史数据")

        last_rebalance = None

        for date in dates:
            data = historical_data[date]

            # 提取价格和因子
            prices = {
                symbol: info['price']
                for symbol, info in data.items()
                if 'price' in info
            }

            stock_data = {
                symbol: info.get('factors', {})
                for symbol, info in data.items()
                if 'factors' in info
            }

            # 检查是否需要调仓
            should_rebalance = (
                last_rebalance is None or
                (date - last_rebalance).days >= self.config.rebalance_days
            )

            if should_rebalance and stock_data:
                selected = self.select_stocks(stock_data, date)
                self.rebalance(selected, prices, date)
                last_rebalance = date

            # 更新权益曲线
            self.update_equity_curve(date, prices)

        # 计算回测指标
        return self.calculate_metrics()

    def calculate_metrics(self) -> Dict:
        """计算回测指标"""
        if not self.equity_curve:
            return {}

        df = pd.DataFrame(self.equity_curve)

        # 总收益率
        total_return = df['return'].iloc[-1]

        # 年化收益率
        days = (df['date'].iloc[-1] - df['date'].iloc[0]).days
        years = days / 365.25
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

        # 最大回撤
        df['cum_max'] = df['total'].cummax()
        df['drawdown'] = (df['total'] - df['cum_max']) / df['cum_max']
        max_drawdown = df['drawdown'].min()

        # 夏普比率(简化计算,假设无风险利率为3%)
        returns = df['return'].pct_change().dropna()
        if len(returns) > 0:
            sharpe = (annual_return - 0.03) / (returns.std() * np.sqrt(252))
        else:
            sharpe = 0

        # 胜率
        winning_trades = sum(1 for t in self.trades if t['action'] == 'SELL' and t['amount'] > 0)
        total_trades = len([t for t in self.trades if t['action'] == 'SELL'])
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        return {
            'total_return': total_return,
            'annual_return': annual_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe,
            'win_rate': win_rate,
            'total_trades': len(self.trades),
            'rebalance_count': len(self.rebalance_dates),
            'final_equity': df['total'].iloc[-1],
            'equity_curve': df,
            'trades': pd.DataFrame(self.trades) if self.trades else pd.DataFrame()
        }
