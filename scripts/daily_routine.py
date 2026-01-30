#!/usr/bin/env python3
"""
每日投资管理例行程序

整合市场分析、持仓跟踪、投资决策
"""

import sys
from pathlib import Path
from datetime import datetime

# 添加项目路径
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))

from trading_os.execution.account_manager import get_default_simulation_account
from trading_os.analysis import get_default_market_analyzer
from trading_os.decision import get_default_decision_logger, DecisionType
from trading_os.data.lake import LocalDataLake


def print_section(title):
    """打印章节标题"""
    print(f"\n{'='*70}")
    print(f"📋 {title}")
    print(f"{'='*70}\n")


def get_latest_prices(lake, symbols):
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


def main():
    """主函数"""
    print("🏦 每日投资管理例行程序")
    print("=" * 70)
    print(f"日期: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}")
    print()

    # 1. 账户状态检查
    print_section("账户状态检查")

    account = get_default_simulation_account()
    if not account:
        print("❌ 账户不存在")
        return 1

    positions = account.get_positions()
    lake = LocalDataLake(Path("data"))

    if positions:
        symbols = list(positions.keys())
        prices = get_latest_prices(lake, symbols)
        summary = account.get_summary(prices)
    else:
        prices = {}
        summary = account.get_summary(prices)

    print(f"账户总值: {summary['total_value']:>15,.2f} 元")
    print(f"持仓市值: {summary['position_value']:>15,.2f} 元")
    print(f"现金余额: {summary['current_cash']:>15,.2f} 元")
    print(f"总盈亏:   {summary['total_pnl']:>15,.2f} 元 ({summary['total_return']:>7.2%})")
    print(f"持仓数量: {summary['position_count']} 只")
    print(f"仓位:     {summary['position_value']/summary['total_value']:>14.2%}")

    # 2. 持仓分析
    if positions:
        print_section("持仓详情分析")

        for pos_summary in summary['positions']:
            symbol = pos_summary['symbol']
            print(f"\n🏷️  {symbol}")
            print("-" * 70)
            print(f"数量:     {pos_summary['quantity']:>10.0f} 股")
            print(f"成本价:   {pos_summary['avg_price']:>10.2f} 元")
            print(f"现价:     {pos_summary['current_price']:>10.2f} 元")
            print(f"市值:     {pos_summary['market_value']:>10,.2f} 元")
            print(f"盈亏:     {pos_summary['pnl']:>10,.2f} 元 ({pos_summary['pnl_ratio']:>7.2%})")
            print(f"仓位:     {pos_summary['weight']:>10.2%}")

            # 简单的持仓建议
            pnl_ratio = pos_summary['pnl_ratio']
            if pnl_ratio <= -0.05:
                print(f"\n⚠️  触及止损线，建议止损")
            elif pnl_ratio <= -0.035:
                print(f"\n⚠️  接近止损线，密切关注")
            elif pnl_ratio >= 0.15:
                print(f"\n✅ 达到止盈目标，可考虑止盈")
            elif pnl_ratio >= 0.10:
                print(f"\n✅ 盈利良好，可考虑部分止盈")
            else:
                print(f"\n✅ 状态正常，继续持有")
    else:
        print_section("持仓详情分析")
        print("当前空仓")

    # 3. 市场分析
    print_section("市场分析")

    analyzer = get_default_market_analyzer()
    print("正在分析市场...")
    report = analyzer.analyze_market(days=60)

    print(f"\n市场状态: {report.market_status}")
    print(f"市场情绪: {report.market_sentiment}")

    if report.opportunities:
        print(f"\n发现 {len(report.opportunities)} 个投资机会:")
        for i, opp in enumerate(report.opportunities[:3], 1):
            print(f"\n{i}. {opp.name} ({opp.symbol})")
            print(f"   评分: {opp.score:.1f}")
            print(f"   现价: {opp.current_price:.2f} 元")
            print(f"   目标价: {opp.target_price:.2f} 元")
            print(f"   预期收益: {opp.expected_return:.2%}")
            print(f"   风险等级: {opp.risk_level}")
    else:
        print("\n暂无符合条件的投资机会")

    # 4. 风险提示
    print_section("风险提示")

    if report.risk_factors:
        for risk in report.risk_factors:
            print(f"  ⚠️  {risk}")
    else:
        print("  ✅ 暂无特别风险")

    # 5. 投资建议
    print_section("今日投资建议")

    decision_logger = get_default_decision_logger()

    # 生成综合建议
    recommendations = []

    # 基于仓位的建议
    current_position_ratio = summary['position_value'] / summary['total_value'] if summary['total_value'] > 0 else 0
    target_position_ratio = 0.5  # 目标50%仓位

    if current_position_ratio < 0.3:
        recommendations.append("💡 当前仓位较低（{:.1%}），可考虑逐步建仓".format(current_position_ratio))
    elif current_position_ratio < target_position_ratio:
        recommendations.append("💡 当前仓位（{:.1%}）低于目标（{:.1%}），寻找机会增仓".format(
            current_position_ratio, target_position_ratio))
    elif current_position_ratio > 0.7:
        recommendations.append("💡 当前仓位较高（{:.1%}），注意风险控制".format(current_position_ratio))

    # 基于持仓的建议
    if positions:
        for pos_summary in summary['positions']:
            pnl_ratio = pos_summary['pnl_ratio']
            symbol = pos_summary['symbol']

            if pnl_ratio <= -0.05:
                recommendations.append(f"⚠️  {symbol} 触及止损线，建议止损出场")
            elif pnl_ratio >= 0.15:
                recommendations.append(f"✅ {symbol} 达到止盈目标，可考虑止盈")

    # 基于市场机会的建议
    if report.opportunities:
        high_score_opps = [opp for opp in report.opportunities if opp.score >= 65]
        if high_score_opps:
            recommendations.append(f"🎯 发现 {len(high_score_opps)} 个高分投资机会（评分≥65），可重点关注")

    # 市场建议
    recommendations.extend(report.recommendations)

    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec}")
    else:
        print("  ✅ 当前策略合理，继续执行")

    # 6. 行动计划
    print_section("今日行动计划")

    actions = []

    # 检查是否需要止损止盈
    if positions:
        for pos_summary in summary['positions']:
            pnl_ratio = pos_summary['pnl_ratio']
            symbol = pos_summary['symbol']

            if pnl_ratio <= -0.05:
                actions.append(f"🔴 立即执行: 止损 {symbol}")
            elif pnl_ratio >= 0.15:
                actions.append(f"🟢 可选执行: 止盈 {symbol}")

    # 检查是否有高分机会
    if report.opportunities:
        top_opp = report.opportunities[0]
        if top_opp.score >= 65 and current_position_ratio < target_position_ratio:
            actions.append(f"🎯 考虑建仓: {top_opp.name} (评分{top_opp.score:.1f})")

    # 常规行动
    actions.append("📊 持续跟踪: 监控持仓表现")
    actions.append("🔍 市场观察: 关注新的投资机会")

    if actions:
        for i, action in enumerate(actions, 1):
            print(f"{i}. {action}")

    # 7. 记录决策
    decision_logger.log_decision(
        decision_type=DecisionType.MARKET_ANALYSIS,
        title=f"{datetime.now().strftime('%Y-%m-%d')} 每日投资管理",
        description=f"账户总值: {summary['total_value']:.2f}元, 仓位: {current_position_ratio:.1%}",
        reasoning="\n".join(recommendations),
        data_sources=["账户状态", "市场分析", "持仓跟踪"],
        market_data={
            "total_value": summary['total_value'],
            "position_ratio": current_position_ratio,
            "opportunities_count": len(report.opportunities)
        },
        risk_level="medium"
    )

    # 8. 总结
    print_section("今日总结")

    print(f"✅ 账户状态: {'正常' if summary['total_value'] > 0 else '异常'}")
    print(f"✅ 持仓数量: {summary['position_count']} 只")
    print(f"✅ 投资机会: {len(report.opportunities)} 个")
    print(f"✅ 行动计划: {len(actions)} 项")

    print("\n" + "=" * 70)
    print("✅ 每日例行程序完成")
    print("=" * 70)

    return 0


if __name__ == '__main__':
    sys.exit(main())
