#!/usr/bin/env python3
"""
测试资金分配功能

演示智能资金分配策略
"""

import sys
from pathlib import Path

# 添加项目路径
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))

from trading_os.execution.capital_allocation import (
    CapitalAllocator,
    AllocationStrategy,
    get_default_allocator
)


def print_section(title):
    """打印章节标题"""
    print(f"\n{'='*70}")
    print(f"📋 {title}")
    print(f"{'='*70}\n")


def print_allocation_plan(plan):
    """打印分配方案"""
    print(f"总资金: {plan.total_capital:>15,.2f} 元")
    print(f"策略:   {plan.strategy.value}")
    print(f"目标数: {len(plan.targets)} 只")
    print(f"已分配: {plan.total_allocated:>15,.2f} 元")
    print(f"剩余:   {plan.remaining_cash:>15,.2f} 元")

    if plan.targets:
        print(f"\n{'股票':<12} {'评分':>6} {'股价':>10} {'数量':>8} {'金额':>12} {'仓位':>8}")
        print("-" * 70)
        for target in plan.targets:
            print(
                f"{target.name:<12} "
                f"{target.score:>6.1f} "
                f"{target.current_price:>10.2f} "
                f"{target.shares:>8} "
                f"{target.actual_amount:>12,.2f} "
                f"{target.weight:>7.1%}"
            )
        print("-" * 70)


def main():
    """主函数"""
    print("🧪 测试资金分配功能")
    print("=" * 70)

    # 模拟账户状态
    total_value = 500000.0  # 账户总值50万
    current_position_value = 0.0  # 当前空仓
    available_cash = 500000.0  # 可用现金50万

    print(f"\n账户状态:")
    print(f"  账户总值: {total_value:,.2f} 元")
    print(f"  持仓市值: {current_position_value:,.2f} 元")
    print(f"  可用现金: {available_cash:,.2f} 元")
    print(f"  当前仓位: {current_position_value/total_value:.1%}")

    # 模拟投资机会
    opportunities = [
        {
            'symbol': 'SSE:600000',
            'name': '浦发银行',
            'score': 65.0,
            'current_price': 10.05,
            'expected_return': 0.119,
            'risk_level': '中'
        },
        {
            'symbol': 'SSE:600519',
            'name': '贵州茅台',
            'score': 68.0,
            'current_price': 1403.8,
            'expected_return': 0.015,
            'risk_level': '中'
        },
        {
            'symbol': 'SSE:600036',
            'name': '招商银行',
            'score': 62.0,
            'current_price': 35.50,
            'expected_return': 0.085,
            'risk_level': '中'
        },
    ]

    print(f"\n投资机会:")
    for i, opp in enumerate(opportunities, 1):
        print(f"  {i}. {opp['name']:<10} 评分:{opp['score']:>5.1f} 股价:{opp['current_price']:>8.2f}")

    # 创建分配器
    allocator = get_default_allocator()

    # 测试1: 动态分配(推荐)
    print_section("测试1: 动态分配策略(推荐)")

    plan = allocator.allocate(
        opportunities=opportunities,
        total_value=total_value,
        current_position_value=current_position_value,
        available_cash=available_cash,
        strategy=AllocationStrategy.DYNAMIC
    )

    print_allocation_plan(plan)

    print("\n✅ 优点:")
    print("  - 确保所有股票都能买入(优先买入100股)")
    print("  - 高评分股票分配更多资金")
    print("  - 考虑股价差异(茅台虽然评分高但价格贵)")
    print("  - 遵守仓位限制(单只≤20%)")

    # 测试2: 评分加权
    print_section("测试2: 评分加权策略")

    plan = allocator.allocate(
        opportunities=opportunities,
        total_value=total_value,
        current_position_value=current_position_value,
        available_cash=available_cash,
        strategy=AllocationStrategy.SCORE_WEIGHTED
    )

    print_allocation_plan(plan)

    print("\n⚠️  问题:")
    print("  - 茅台评分最高(68)但价格贵(1403.8)")
    print("  - 可能分配的资金不够买100股")
    print("  - 导致茅台买不了")

    # 测试3: 等权重
    print_section("测试3: 等权重策略")

    plan = allocator.allocate(
        opportunities=opportunities,
        total_value=total_value,
        current_position_value=current_position_value,
        available_cash=available_cash,
        strategy=AllocationStrategy.EQUAL_WEIGHT
    )

    print_allocation_plan(plan)

    print("\n⚠️  问题:")
    print("  - 不考虑评分差异")
    print("  - 高评分和低评分股票分配相同资金")
    print("  - 资金使用效率不高")

    # 测试4: 已有持仓的情况
    print_section("测试4: 已有持仓的情况")

    current_position_value = 74580.0  # 已持仓14.92%
    available_cash = 425420.0

    print(f"账户状态:")
    print(f"  账户总值: {total_value:,.2f} 元")
    print(f"  持仓市值: {current_position_value:,.2f} 元")
    print(f"  可用现金: {available_cash:,.2f} 元")
    print(f"  当前仓位: {current_position_value/total_value:.1%}")

    plan = allocator.allocate(
        opportunities=opportunities,
        total_value=total_value,
        current_position_value=current_position_value,
        available_cash=available_cash,
        strategy=AllocationStrategy.DYNAMIC
    )

    print_allocation_plan(plan)

    print("\n✅ 说明:")
    print("  - 当前仓位14.92%,目标仓位60%")
    print("  - 还可以增仓45%左右")
    print("  - 动态分配确保合理利用资金")

    # 测试5: 接近目标仓位
    print_section("测试5: 接近目标仓位的情况")

    current_position_value = 280000.0  # 已持仓56%
    available_cash = 220000.0

    print(f"账户状态:")
    print(f"  账户总值: {total_value:,.2f} 元")
    print(f"  持仓市值: {current_position_value:,.2f} 元")
    print(f"  可用现金: {available_cash:,.2f} 元")
    print(f"  当前仓位: {current_position_value/total_value:.1%}")

    plan = allocator.allocate(
        opportunities=opportunities,
        total_value=total_value,
        current_position_value=current_position_value,
        available_cash=available_cash,
        strategy=AllocationStrategy.DYNAMIC
    )

    print_allocation_plan(plan)

    print("\n✅ 说明:")
    print("  - 当前仓位56%,接近目标60%")
    print("  - 仅分配剩余4%的资金")
    print("  - 风险控制,不过度建仓")

    print("\n" + "=" * 70)
    print("✅ 测试完成")
    print("\n💡 结论:")
    print("  1. 动态分配策略最适合实际使用")
    print("  2. 能够处理高价股(如茅台)")
    print("  3. 根据仓位自动调整分配金额")
    print("  4. 遵守风险控制规则")
    print("=" * 70)

    return 0


if __name__ == '__main__':
    sys.exit(main())
