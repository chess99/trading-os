#!/usr/bin/env python3
"""
查看账户状态

显示模拟账户的当前状态、持仓和盈亏情况
"""

import sys
from pathlib import Path

# 添加项目路径
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))

from trading_os.execution.account_manager import get_default_simulation_account
from trading_os.data.sources.realtime_price import get_realtime_prices


def get_latest_prices(symbols: list) -> dict:
    """
    获取最新价格

    优先使用实时价格,确保显示的盈亏准确
    """
    try:
        prices = get_realtime_prices(symbols)
        if prices:
            return prices
    except Exception as e:
        print(f"警告: 获取实时价格失败: {e}")

    # 降级方案: 返回空字典
    return {symbol: 0.0 for symbol in symbols}


def main():
    """主函数"""
    print("💼 模拟账户状态")
    print("=" * 70)

    # 获取账户
    account = get_default_simulation_account()

    if account is None:
        print("❌ 模拟账户不存在")
        print("请先运行: python scripts/init_simulation_account.py")
        return 1

    # 获取持仓
    positions = account.get_positions()

    # 获取最新价格
    if positions:
        symbols = list(positions.keys())
        prices = get_latest_prices(symbols)
    else:
        prices = {}

    # 获取账户摘要
    summary = account.get_summary(prices)

    # 显示基本信息
    print(f"\n📊 账户概览")
    print(f"{'账户ID:':<20} {summary['account_id']}")
    print(f"{'账户类型:':<20} {summary['account_type']}")
    print(f"{'创建时间:':<20} {summary['created_at']}")
    print(f"{'最后更新:':<20} {summary['last_update']}")

    # 显示资金情况
    print(f"\n💰 资金情况")
    print(f"{'初始资金:':<20} {summary['initial_cash']:>15,.2f} 元")
    print(f"{'当前现金:':<20} {summary['current_cash']:>15,.2f} 元")
    print(f"{'持仓市值:':<20} {summary['position_value']:>15,.2f} 元")
    print(f"{'账户总值:':<20} {summary['total_value']:>15,.2f} 元")

    # 显示收益情况
    print(f"\n📈 收益情况")
    pnl_sign = "+" if summary['total_pnl'] >= 0 else ""
    return_sign = "+" if summary['total_return'] >= 0 else ""
    print(f"{'总盈亏:':<20} {pnl_sign}{summary['total_pnl']:>15,.2f} 元")
    print(f"{'总收益率:':<20} {return_sign}{summary['total_return']:>14.2%}")

    # 显示持仓情况
    print(f"\n📦 持仓情况")
    print(f"{'持仓数量:':<20} {summary['position_count']}")
    print(f"{'交易次数:':<20} {summary['transaction_count']}")

    # 显示持仓详情
    if summary['positions']:
        print(f"\n📋 持仓详情")
        print("-" * 70)
        header = f"{'股票代码':<15} {'数量':>10} {'成本价':>10} {'现价':>10} {'盈亏':>12} {'收益率':>10}"
        print(header)
        print("-" * 70)

        for pos in summary['positions']:
            pnl_str = f"{pos['pnl']:+,.2f}"
            return_str = f"{pos['pnl_ratio']:+.2%}"

            print(
                f"{pos['symbol']:<15} "
                f"{pos['quantity']:>10.0f} "
                f"{pos['avg_price']:>10.2f} "
                f"{pos['current_price']:>10.2f} "
                f"{pnl_str:>12} "
                f"{return_str:>10}"
            )

        print("-" * 70)
    else:
        print("\n📋 持仓详情: 空仓")

    # 显示最近交易
    if account.transactions:
        print(f"\n📜 最近交易 (最多显示5条)")
        print("-" * 70)

        recent_txns = account.transactions[-5:]
        for txn in reversed(recent_txns):
            side_emoji = "🟢" if txn.side.value == "BUY" else "🔴"
            print(
                f"{side_emoji} {txn.timestamp.strftime('%Y-%m-%d %H:%M')} "
                f"{txn.symbol:<12} {txn.side.value:<4} "
                f"{txn.quantity:>8.0f}股 @ {txn.price:>8.2f} "
                f"金额: {txn.amount:>12,.2f}"
            )
            if txn.reason:
                print(f"   理由: {txn.reason}")

    print("\n" + "=" * 70)

    return 0


if __name__ == '__main__':
    sys.exit(main())
