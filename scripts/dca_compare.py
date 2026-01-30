#!/usr/bin/env python3
"""
定投频率对比工具

对比不同定投频率(每日/每周/每月)的回测效果
"""

import sys
from pathlib import Path

# 添加项目路径
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

from scripts.dca_backtest import DCABacktest


def compare_frequencies(symbol: str, start_date: str, end_date: str = None, annual_investment: float = 120000):
    """对比不同定投频率"""

    frequencies = ['daily', 'weekly', 'monthly']
    results_dict = {}

    print("=" * 80)
    print(f"📊 定投频率对比分析")
    print(f"标的: {symbol}")
    print(f"年投入: {annual_investment:,.0f}元")
    print("=" * 80)
    print()

    for freq in frequencies:
        print(f"🔄 测试频率: {freq}")
        print("-" * 80)

        try:
            backtest = DCABacktest(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                frequency=freq,
                annual_investment=annual_investment,
                data_source='auto'
            )

            results = backtest.run_backtest()
            results_dict[freq] = results

            print(f"  ✅ 完成")
            print(f"  总投入: {results['total_invested']:,.2f}元")
            print(f"  最终市值: {results['final_value']:,.2f}元")
            print(f"  总收益率: {results['total_return_pct']:+.2f}%")
            print(f"  年化收益率: {results['annual_return']*100:+.2f}%")
            print(f"  最大回撤: {results['max_drawdown']:.2f}%")
            print()

        except Exception as e:
            print(f"  ❌ 失败: {e}")
            print()

    # 对比总结
    if len(results_dict) > 0:
        print()
        print("=" * 80)
        print("📊 对比总结")
        print("=" * 80)
        print()

        print(f"{'频率':<12} {'投入次数':<10} {'总收益率':<12} {'年化收益':<12} {'最大回撤':<12}")
        print("-" * 80)

        for freq, results in results_dict.items():
            print(f"{freq:<12} "
                  f"{results['investment_count']:<10} "
                  f"{results['total_return_pct']:>10.2f}% "
                  f"{results['annual_return']*100:>10.2f}% "
                  f"{results['max_drawdown']:>10.2f}%")

        print()

        # 找出最佳频率
        best_freq = max(results_dict.keys(), key=lambda k: results_dict[k]['total_return_pct'])
        best_results = results_dict[best_freq]

        print(f"🏆 最佳频率: {best_freq}")
        print(f"  总收益率: {best_results['total_return_pct']:+.2f}%")
        print(f"  年化收益率: {best_results['annual_return']*100:+.2f}%")
        print()

        # 分析差异
        returns = [r['total_return_pct'] for r in results_dict.values()]
        max_diff = max(returns) - min(returns)
        print(f"📈 频率间最大差异: {max_diff:.2f}%")

        if max_diff < 2:
            print("  💡 结论: 不同频率收益差异很小,选择月度定投即可(省时省力)")
        elif max_diff < 5:
            print("  💡 结论: 不同频率有一定差异,但不显著")
        else:
            print("  💡 结论: 不同频率差异较大,建议选择收益最高的频率")

    print()
    print("=" * 80)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='定投频率对比工具')
    parser.add_argument('symbol', help='标的代码')
    parser.add_argument('--start', default='2020-01-01', help='起始日期')
    parser.add_argument('--end', default=None, help='结束日期')
    parser.add_argument('--annual', type=float, default=120000, help='年投入总额')

    args = parser.parse_args()

    compare_frequencies(args.symbol, args.start, args.end, args.annual)
