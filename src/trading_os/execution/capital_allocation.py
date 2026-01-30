"""
资金分配模块

提供智能的资金分配策略,根据股价、评分、账户状态动态分配资金
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class AllocationStrategy(str, Enum):
    """资金分配策略"""
    EQUAL_WEIGHT = "equal_weight"  # 等权重
    SCORE_WEIGHTED = "score_weighted"  # 评分加权
    DYNAMIC = "dynamic"  # 动态分配(推荐)


@dataclass
class AllocationTarget:
    """分配目标"""
    symbol: str
    name: str
    score: float
    current_price: float
    expected_return: float
    risk_level: str
    allocated_amount: float = 0.0  # 分配金额
    shares: int = 0  # 可买入股数
    actual_amount: float = 0.0  # 实际金额
    weight: float = 0.0  # 权重


@dataclass
class AllocationPlan:
    """资金分配方案"""
    total_capital: float  # 总资金
    targets: List[AllocationTarget]  # 分配目标
    total_allocated: float  # 总分配金额
    remaining_cash: float  # 剩余现金
    strategy: AllocationStrategy  # 使用的策略


class CapitalAllocator:
    """
    资金分配器

    功能:
    1. 根据评分和股价动态分配资金
    2. 确保所有标的都能买入(至少100股)
    3. 优化资金使用效率
    4. 支持多种分配策略
    """

    def __init__(
        self,
        min_position_ratio: float = 0.05,  # 单只最小仓位5%
        max_position_ratio: float = 0.20,  # 单只最大仓位20%
        target_total_position: float = 0.60,  # 目标总仓位60%
        min_shares: int = 100,  # A股最小买入100股
        lot_size: int = 100,  # A股交易单位100股
    ):
        """
        初始化资金分配器

        Args:
            min_position_ratio: 单只股票最小仓位比例
            max_position_ratio: 单只股票最大仓位比例
            target_total_position: 目标总仓位比例
            min_shares: 最小买入股数
            lot_size: 交易单位(手)
        """
        self.min_position_ratio = min_position_ratio
        self.max_position_ratio = max_position_ratio
        self.target_total_position = target_total_position
        self.min_shares = min_shares
        self.lot_size = lot_size

        logger.info(
            f"资金分配器初始化: "
            f"单只仓位[{min_position_ratio:.1%}, {max_position_ratio:.1%}], "
            f"目标总仓位{target_total_position:.1%}"
        )

    def allocate(
        self,
        opportunities: List[Dict],
        total_value: float,
        current_position_value: float,
        available_cash: float,
        strategy: AllocationStrategy = AllocationStrategy.DYNAMIC
    ) -> AllocationPlan:
        """
        分配资金

        Args:
            opportunities: 投资机会列表,每个包含:
                - symbol: 股票代码
                - name: 股票名称
                - score: 评分
                - current_price: 当前价格
                - expected_return: 预期收益
                - risk_level: 风险等级
            total_value: 账户总值
            current_position_value: 当前持仓市值
            available_cash: 可用现金
            strategy: 分配策略

        Returns:
            资金分配方案
        """
        if not opportunities:
            logger.warning("没有投资机会,无需分配资金")
            return AllocationPlan(
                total_capital=0.0,
                targets=[],
                total_allocated=0.0,
                remaining_cash=available_cash,
                strategy=strategy
            )

        # 计算可用于建仓的资金
        current_position_ratio = current_position_value / total_value if total_value > 0 else 0
        target_position_value = total_value * self.target_total_position
        available_for_new = target_position_value - current_position_value

        # 限制在可用现金范围内
        available_for_new = min(available_for_new, available_cash * 0.95)  # 保留5%现金缓冲

        if available_for_new <= 0:
            logger.warning(
                f"没有可用资金建仓: "
                f"当前仓位{current_position_ratio:.1%}, "
                f"目标仓位{self.target_total_position:.1%}"
            )
            return AllocationPlan(
                total_capital=0.0,
                targets=[],
                total_allocated=0.0,
                remaining_cash=available_cash,
                strategy=strategy
            )

        logger.info(
            f"开始资金分配: "
            f"账户总值{total_value:,.2f}, "
            f"可用资金{available_for_new:,.2f}, "
            f"策略{strategy.value}"
        )

        # 根据策略分配
        if strategy == AllocationStrategy.EQUAL_WEIGHT:
            targets = self._allocate_equal_weight(
                opportunities, available_for_new, total_value
            )
        elif strategy == AllocationStrategy.SCORE_WEIGHTED:
            targets = self._allocate_score_weighted(
                opportunities, available_for_new, total_value
            )
        else:  # DYNAMIC
            targets = self._allocate_dynamic(
                opportunities, available_for_new, total_value
            )

        # 计算总分配金额
        total_allocated = sum(t.actual_amount for t in targets)
        remaining_cash = available_cash - total_allocated

        plan = AllocationPlan(
            total_capital=available_for_new,
            targets=targets,
            total_allocated=total_allocated,
            remaining_cash=remaining_cash,
            strategy=strategy
        )

        logger.info(
            f"资金分配完成: "
            f"分配{len(targets)}只股票, "
            f"总金额{total_allocated:,.2f}, "
            f"剩余现金{remaining_cash:,.2f}"
        )

        return plan

    def _allocate_equal_weight(
        self,
        opportunities: List[Dict],
        available_capital: float,
        total_value: float
    ) -> List[AllocationTarget]:
        """等权重分配"""
        targets = []
        n = len(opportunities)

        if n == 0:
            return targets

        # 每只股票分配相同金额
        amount_per_stock = available_capital / n

        for opp in opportunities:
            target = self._create_target(opp, amount_per_stock, total_value)
            if target and target.shares >= self.min_shares:
                targets.append(target)
            else:
                logger.warning(
                    f"{opp['symbol']} 资金不足: "
                    f"分配{amount_per_stock:,.2f}, "
                    f"股价{opp['current_price']:.2f}, "
                    f"仅可买{target.shares if target else 0}股"
                )

        return targets

    def _allocate_score_weighted(
        self,
        opportunities: List[Dict],
        available_capital: float,
        total_value: float
    ) -> List[AllocationTarget]:
        """评分加权分配"""
        targets = []

        # 计算总评分
        total_score = sum(opp['score'] for opp in opportunities)

        if total_score == 0:
            return self._allocate_equal_weight(opportunities, available_capital, total_value)

        for opp in opportunities:
            # 根据评分比例分配资金
            weight = opp['score'] / total_score
            allocated_amount = available_capital * weight

            target = self._create_target(opp, allocated_amount, total_value)
            if target and target.shares >= self.min_shares:
                targets.append(target)
            else:
                logger.warning(
                    f"{opp['symbol']} 资金不足: "
                    f"分配{allocated_amount:,.2f}, "
                    f"股价{opp['current_price']:.2f}"
                )

        return targets

    def _allocate_dynamic(
        self,
        opportunities: List[Dict],
        available_capital: float,
        total_value: float
    ) -> List[AllocationTarget]:
        """
        动态分配(推荐策略)

        特点:
        1. 优先确保所有标的能买入
        2. 高评分标的分配更多资金
        3. 考虑股价差异,避免高价股买不起
        4. 遵守仓位限制
        """
        targets = []

        # 按评分排序
        sorted_opps = sorted(opportunities, key=lambda x: x['score'], reverse=True)

        # 第一轮: 确保每只股票都能买入最小数量
        remaining_capital = available_capital
        min_allocations = []

        for opp in sorted_opps:
            # 计算买入100股需要的金额
            min_amount = opp['current_price'] * self.min_shares * 1.01  # 1%缓冲

            if min_amount <= remaining_capital:
                min_allocations.append((opp, min_amount))
                remaining_capital -= min_amount
            else:
                logger.warning(
                    f"{opp['symbol']} 资金不足买入最小数量: "
                    f"需要{min_amount:,.2f}, 剩余{remaining_capital:,.2f}"
                )

        if not min_allocations:
            logger.error("可用资金不足以买入任何股票")
            return targets

        # 第二轮: 根据评分分配剩余资金
        if remaining_capital > 0:
            total_score = sum(opp['score'] for opp, _ in min_allocations)

            for opp, min_amount in min_allocations:
                # 基础金额 + 评分加权的剩余资金
                weight = opp['score'] / total_score if total_score > 0 else 1.0 / len(min_allocations)
                extra_amount = remaining_capital * weight
                total_amount = min_amount + extra_amount

                # 检查单只仓位上限
                max_amount = total_value * self.max_position_ratio
                total_amount = min(total_amount, max_amount)

                target = self._create_target(opp, total_amount, total_value)
                if target:
                    targets.append(target)
        else:
            # 没有剩余资金,使用最小分配
            for opp, min_amount in min_allocations:
                target = self._create_target(opp, min_amount, total_value)
                if target:
                    targets.append(target)

        return targets

    def _create_target(
        self,
        opportunity: Dict,
        allocated_amount: float,
        total_value: float
    ) -> Optional[AllocationTarget]:
        """创建分配目标"""
        try:
            price = opportunity['current_price']

            # 计算可买入股数(100股整数倍)
            shares = int(allocated_amount / price / self.lot_size) * self.lot_size

            if shares < self.min_shares:
                return None

            # 计算实际金额
            actual_amount = shares * price

            # 计算权重
            weight = actual_amount / total_value if total_value > 0 else 0

            return AllocationTarget(
                symbol=opportunity['symbol'],
                name=opportunity['name'],
                score=opportunity['score'],
                current_price=price,
                expected_return=opportunity['expected_return'],
                risk_level=opportunity['risk_level'],
                allocated_amount=allocated_amount,
                shares=shares,
                actual_amount=actual_amount,
                weight=weight
            )

        except Exception as e:
            logger.error(f"创建分配目标失败 {opportunity['symbol']}: {e}")
            return None


def get_default_allocator() -> CapitalAllocator:
    """获取默认的资金分配器"""
    return CapitalAllocator(
        min_position_ratio=0.05,
        max_position_ratio=0.20,
        target_total_position=0.60
    )
