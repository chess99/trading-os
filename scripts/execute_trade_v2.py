#!/usr/bin/env python3
"""
智能交易执行系统 V2

使用智能资金分配策略,确保所有标的都能合理建仓
"""

import sys
from pathlib import Path

# 添加项目路径
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))

from trading_os.execution.account_manager import get_default_simulation_account
from trading_os.execution.capital_allocation import get_default_allocator, AllocationStrategy
from trading_os.decision import get_default_decision_logger, DecisionType
from trading_os.data.sources.realtime_price import get_realtime_price


def execute_allocation_plan(plan, account, decision_logger):
    """
    执行资金分配方案

    Args:
        plan: 资金分配方案
        account: 交易账户
        decision_logger: 决策记录器

    Returns:
        成功执行的交易数量
    """
    success_count = 0

    for target in plan.targets:
        print(f"\n{'='*70}")
        print(f"📈 执行买入: {target.name} ({target.symbol})")
        print(f"{'='*70}")

        print(f"\n分配方案:")
        print(f"  评分:     {target.score:.1f}")
        print(f"  当前价:   {target.current_price:.2f} 元")
        print(f"  买入数量: {target.shares} 股")
        print(f"  买入金额: {target.actual_amount:,.2f} 元")
        print(f"  预期收益: {target.expected_return:.2%}")
        print(f"  仓位:     {target.weight:.2%}")

        # 获取实时价格
        try:
            current_price = get_realtime_price(target.symbol)
            print(f"\n实时价格: {current_price:.2f} 元")

            # 检查价格变化
            price_change = abs(current_price - target.current_price) / target.current_price
            if price_change > 0.05:
                print(f"⚠️  价格变化较大: {price_change:.2%}")
                confirm = input("是否继续? (yes/no): ").strip().lower()
                if confirm != 'yes':
                    print("❌ 取消交易")
                    continue

        except Exception as e:
            print(f"❌ 获取实时价格失败: {e}")
            continue

        # 记录决策
        decision = decision_logger.log_decision(
            decision_type=DecisionType.BUY_DECISION,
            title=f"买入 {target.name}",
            description=f"基于智能资金分配策略买入 {target.name}",
            reasoning=f"""
基于智能资金分配策略:
- 评分: {target.score:.1f}/100
- 预期收益: {target.expected_return:.2%}
- 风险等级: {target.risk_level}
- 分配金额: {target.actual_amount:,.2f} 元
- 仓位占比: {target.weight:.2%}
            """,
            data_sources=[
                "市场分析报告",
                f"数据湖 - {target.symbol}历史数据",
                "智能资金分配系统"
            ],
            risk_level="medium",
            risk_factors=[
                f"市场风险等级: {target.risk_level}",
                "价格波动风险",
                "流动性风险"
            ],
            target_symbols=[target.symbol],
            target_amount=target.actual_amount,
            expected_return=target.expected_return
        )

        print(f"\n📝 决策已记录: {decision.decision_id}")

        # 确认执行
        print(f"\n⚠️  即将执行买入操作:")
        print(f"   股票: {target.name} ({target.symbol})")
        print(f"   价格: {current_price:.2f} 元")
        print(f"   数量: {target.shares} 股")
        print(f"   金额: {target.shares * current_price:,.2f} 元")

        confirm = input("\n是否确认执行? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ 取消交易")
            decision_logger.reject_decision(decision.decision_id, "用户取消")
            continue

        # 执行交易
        print("\n🔄 执行交易...")
        transaction = account.buy(
            symbol=target.symbol,
            quantity=target.shares,
            price=current_price,
            reason=f"智能资金分配,决策ID: {decision.decision_id}"
        )

        if not transaction:
            print("❌ 交易失败")
            decision_logger.reject_decision(decision.decision_id, "交易执行失败")
            continue

        # 记录执行结果
        decision_logger.record_execution(
            decision.decision_id,
            {
                "transaction_id": transaction.transaction_id,
                "symbol": target.symbol,
                "quantity": target.shares,
                "price": current_price,
                "amount": transaction.amount,
                "fee": transaction.fee
            }
        )

        # 保存账户状态
        account.save()

        print(f"\n✅ 交易成功!")
        print(f"   交易ID: {transaction.transaction_id}")
        print(f"   剩余现金: {account.get_cash():,.2f} 元")

        success_count += 1

    return success_count


def main():
    """主函数"""
    print("🎯 智能交易执行系统 V2")
    print("=" * 70)

    # 获取账户
    account = get_default_simulation_account()
    if not account:
        print("❌ 账户不存在")
        return 1

    # 获取账户状态
    positions = account.get_positions()

    # 获取实时价格
    if positions:
        from trading_os.data.sources.realtime_price import get_realtime_prices
        symbols = list(positions.keys())
        prices = get_realtime_prices(symbols)
    else:
        prices = {}

    summary = account.get_summary(prices)

    print(f"\n💼 账户状态:")
    print(f"   账户总值: {summary['total_value']:,.2f} 元")
    print(f"   持仓市值: {summary['position_value']:,.2f} 元")
    print(f"   可用现金: {summary['current_cash']:,.2f} 元")
    print(f"   当前仓位: {summary['position_value']/summary['total_value']:.2%}")

    # 模拟投资机会(实际应该从市场分析获取)
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

    print(f"\n📊 投资机会:")
    for i, opp in enumerate(opportunities, 1):
        print(f"   {i}. {opp['name']:<10} 评分:{opp['score']:>5.1f} 预期收益:{opp['expected_return']:>7.2%}")

    # 创建资金分配器
    allocator = get_default_allocator()

    # 生成分配方案
    print(f"\n🧮 生成资金分配方案...")
    plan = allocator.allocate(
        opportunities=opportunities,
        total_value=summary['total_value'],
        current_position_value=summary['position_value'],
        available_cash=summary['current_cash'],
        strategy=AllocationStrategy.DYNAMIC
    )

    # 显示分配方案
    print(f"\n{'='*70}")
    print(f"📋 资金分配方案")
    print(f"{'='*70}")
    print(f"\n策略:   {plan.strategy.value}")
    print(f"总资金: {plan.total_capital:,.2f} 元")
    print(f"目标数: {len(plan.targets)} 只")
    print(f"已分配: {plan.total_allocated:,.2f} 元")
    print(f"剩余:   {plan.remaining_cash:,.2f} 元")

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
                f"{target.weight:>7.2%}"
            )
        print("-" * 70)

        print(f"\n✅ 优势:")
        print(f"   - 所有股票都能买入(至少100股)")
        print(f"   - 高评分股票分配更多资金")
        print(f"   - 考虑股价差异,合理分配")
        print(f"   - 遵守仓位限制(单只≤20%)")

    else:
        print("\n⚠️  没有可执行的分配方案")
        print("   可能原因:")
        print("   - 可用资金不足")
        print("   - 当前仓位已达目标")
        print("   - 股价过高无法买入最小数量")
        return 0

    # 确认执行
    print(f"\n{'='*70}")
    confirm = input("\n是否执行此分配方案? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ 取消执行")
        return 0

    # 执行方案
    decision_logger = get_default_decision_logger()
    success_count = execute_allocation_plan(plan, account, decision_logger)

    # 总结
    print(f"\n{'='*70}")
    print(f"📊 执行总结")
    print(f"{'='*70}")
    print(f"计划交易: {len(plan.targets)} 笔")
    print(f"成功交易: {success_count} 笔")

    # 更新账户状态
    if positions:
        from trading_os.data.sources.realtime_price import get_realtime_prices
        symbols = list(account.get_positions().keys())
        prices = get_realtime_prices(symbols)
    else:
        prices = {}

    summary = account.get_summary(prices)

    print(f"\n💼 最新账户状态:")
    print(f"   账户总值: {summary['total_value']:,.2f} 元")
    print(f"   持仓市值: {summary['position_value']:,.2f} 元")
    print(f"   可用现金: {summary['current_cash']:,.2f} 元")
    print(f"   当前仓位: {summary['position_value']/summary['total_value']:.2%}")
    print(f"   持仓数量: {summary['position_count']} 只")

    print(f"\n{'='*70}")
    print("✅ 执行完成")
    print("=" * 70)

    return 0


if __name__ == '__main__':
    sys.exit(main())
