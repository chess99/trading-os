#!/usr/bin/env python3
"""
持仓跟踪

每日监控持仓表现、盈亏情况、止损止盈条件
"""

import sys
from pathlib import Path
from datetime import datetime

# 添加项目路径
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))

from trading_os.execution.account_manager import get_default_simulation_account
from trading_os.data.lake import LocalDataLake
from trading_os.decision import get_default_decision_logger


def get_latest_prices(lake: LocalDataLake, symbols: list) -> dict:
    """获取最新价格"""
    prices = {}
    for symbol in symbols:
        try:
            bars = lake.query_bars(symbols=[symbol], limit=1)
            if not bars.empty:
                prices[symbol] = float(bars.iloc[-1]['close'])
        except Exception as e:
            print(f"警告: 无法获取 {symbol} 的价格: {e}")
            prices[symbol] = 0.0
    return prices


def check_stop_loss_profit(position, current_price, stop_loss_pct=0.05, take_profit_pct=0.15):
    """检查止损止盈条件"""
    if position.qty == 0:
        return None, None

    cost_price = position.avg_price
    pnl_ratio = (current_price - cost_price) / cost_price if cost_price > 0 else 0

    alerts = []

    # 检查止损
    if pnl_ratio <= -stop_loss_pct:
        alerts.append({
            'type': 'STOP_LOSS',
            'level': 'HIGH',
            'message': f'⚠️ 触及止损线 {-stop_loss_pct:.1%}，当前跌幅 {pnl_ratio:.1%}',
            'action': '建议止损出场'
        })

    # 检查止盈
    if pnl_ratio >= take_profit_pct:
        alerts.append({
            'type': 'TAKE_PROFIT',
            'level': 'MEDIUM',
            'message': f'✅ 达到止盈目标 {take_profit_pct:.1%}，当前涨幅 {pnl_ratio:.1%}',
            'action': '可考虑止盈或减仓'
        })

    # 接近止损
    if -stop_loss_pct < pnl_ratio <= -stop_loss_pct * 0.7:
        alerts.append({
            'type': 'WARNING',
            'level': 'MEDIUM',
            'message': f'⚠️ 接近止损线，当前跌幅 {pnl_ratio:.1%}',
            'action': '密切关注，准备止损'
        })

    return alerts, pnl_ratio


def main():
    """主函数"""
    print("📊 持仓跟踪监控")
    print("=" * 70)
    print(f"监控时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 获取账户
    account = get_default_simulation_account()
    if not account:
        print("❌ 账户不存在")
        return 1

    # 获取持仓
    positions = account.get_positions()
    if not positions:
        print("📋 当前空仓，无需跟踪")
        return 0

    print(f"持仓数量: {len(positions)}")
    print()

    # 获取最新价格
    lake = LocalDataLake(Path("data"))
    symbols = list(positions.keys())
    prices = get_latest_prices(lake, symbols)

    # 获取账户摘要
    summary = account.get_summary(prices)

    # 显示整体情况
    print("💼 账户概览")
    print("-" * 70)
    print(f"账户总值: {summary['total_value']:>15,.2f} 元")
    print(f"持仓市值: {summary['position_value']:>15,.2f} 元")
    print(f"现金余额: {summary['current_cash']:>15,.2f} 元")
    print(f"总盈亏:   {summary['total_pnl']:>15,.2f} 元 ({summary['total_return']:>7.2%})")
    print()

    # 逐个分析持仓
    print("📋 持仓详情")
    print("=" * 70)

    decision_logger = get_default_decision_logger()
    has_alerts = False

    for pos_summary in summary['positions']:
        symbol = pos_summary['symbol']
        position = positions[symbol]
        current_price = pos_summary['current_price']

        print(f"\n🏷️  {symbol}")
        print("-" * 70)
        print(f"数量:     {pos_summary['quantity']:>10.0f} 股")
        print(f"成本价:   {pos_summary['avg_price']:>10.2f} 元")
        print(f"现价:     {current_price:>10.2f} 元")
        print(f"市值:     {pos_summary['market_value']:>10,.2f} 元")
        print(f"盈亏:     {pos_summary['pnl']:>10,.2f} 元 ({pos_summary['pnl_ratio']:>7.2%})")
        print(f"仓位:     {pos_summary['weight']:>10.2%}")

        # 检查止损止盈
        alerts, pnl_ratio = check_stop_loss_profit(position, current_price)

        if alerts:
            has_alerts = True
            print(f"\n⚠️  风险提示:")
            for alert in alerts:
                print(f"   {alert['message']}")
                print(f"   建议: {alert['action']}")

                # 记录到决策日志
                if alert['level'] == 'HIGH':
                    decision_logger.log_decision(
                        decision_type="risk_assessment",
                        title=f"{symbol} 触发{alert['type']}警报",
                        description=alert['message'],
                        reasoning=f"当前价格{current_price:.2f}元，盈亏比{pnl_ratio:.2%}",
                        data_sources=["持仓跟踪系统"],
                        risk_level="high",
                        risk_factors=[alert['message']],
                        target_symbols=[symbol]
                    )
        else:
            print(f"\n✅ 状态正常，继续持有")

    print("\n" + "=" * 70)

    # 总结
    if has_alerts:
        print("\n⚠️  发现风险提示，请及时处理！")
    else:
        print("\n✅ 所有持仓状态正常")

    # 生成跟踪报告
    report_dir = Path("data/tracking")
    report_dir.mkdir(parents=True, exist_ok=True)

    report_file = report_dir / f"tracking_{datetime.now().strftime('%Y%m%d')}.txt"

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(f"持仓跟踪报告\n")
        f.write(f"{'='*70}\n")
        f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"账户总值: {summary['total_value']:,.2f} 元\n")
        f.write(f"总盈亏: {summary['total_pnl']:,.2f} 元 ({summary['total_return']:.2%})\n\n")

        for pos_summary in summary['positions']:
            f.write(f"{pos_summary['symbol']}:\n")
            f.write(f"  数量: {pos_summary['quantity']:.0f} 股\n")
            f.write(f"  成本: {pos_summary['avg_price']:.2f} 元\n")
            f.write(f"  现价: {pos_summary['current_price']:.2f} 元\n")
            f.write(f"  盈亏: {pos_summary['pnl']:.2f} 元 ({pos_summary['pnl_ratio']:.2%})\n\n")

    print(f"\n💾 跟踪报告已保存: {report_file}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
