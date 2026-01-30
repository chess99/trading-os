#!/usr/bin/env python3
"""
ETF定投扫描工具

专门扫描ETF,因为akshare的ETF接口比较稳定
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import time

# 添加项目路径
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

# 清除代理
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('HTTP_PROXY', None)

from scripts.dca_backtest import DCABacktest
import pandas as pd


# 常见ETF列表
ETF_LIST = [
    # 宽基指数
    ('588000', '华夏科创50ETF'),
    ('588050', '华夏科创50ETF'),
    ('510050', '华夏上证50ETF'),
    ('510300', '华泰柏瑞沪深300ETF'),
    ('510500', '南方中证500ETF'),
    ('159915', '易方达创业板ETF'),
    ('159919', '嘉实沪深300ETF'),
    ('510880', '华泰柏瑞红利ETF'),

    # 行业ETF
    ('512690', '鹏华中证酒ETF'),
    ('512880', '国泰中证全指证券公司ETF'),
    ('512000', '华宝中证全指证券公司ETF'),
    ('512010', '易方达沪深300医药卫生ETF'),
    ('512760', '国泰CES半导体芯片ETF'),
    ('515050', '华夏5GETF'),
    ('515790', '华夏中证新能源汽车ETF'),
    ('515880', '国泰中证全指通信设备ETF'),
    ('516160', '华夏中证人工智能主题ETF'),

    # 主题ETF
    ('159928', '汇添富中证主要消费ETF'),
    ('159995', '华夏国证半导体芯片ETF'),
    ('515220', '国泰中证煤炭ETF'),
    ('516970', '广发中证基建工程ETF'),
    ('159845', '工银瑞信中证传媒ETF'),

    # 债券ETF
    ('511010', '国泰上证5年期国债ETF'),
    ('511260', '上证10年期国债ETF'),
]


def scan_etf_list(
    start_date: str,
    end_date: str = None,
    frequency: str = 'monthly',
    annual_investment: float = 120000
):
    """扫描ETF列表"""

    print("=" * 80)
    print("🔍 ETF定投扫描")
    print("=" * 80)
    print(f"起始日期: {start_date}")
    print(f"结束日期: {end_date or '今天'}")
    print(f"定投频率: {frequency}")
    print(f"年投入: {annual_investment:,.0f}元")
    print(f"扫描数量: {len(ETF_LIST)}只ETF")
    print("=" * 80)
    print()

    results = []
    failed = []

    for i, (code, name) in enumerate(ETF_LIST, 1):
        print(f"[{i}/{len(ETF_LIST)}] {code} {name}...", end=' ', flush=True)

        try:
            # 判断交易所
            if code.startswith('5'):
                symbol = f'SSE:{code}'
            elif code.startswith('1'):
                symbol = f'SZSE:{code}'
            else:
                symbol = code

            # 创建回测
            backtest = DCABacktest(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                frequency=frequency,
                annual_investment=annual_investment,
                data_source='online'
            )

            # 运行回测
            backtest_results = backtest.run_backtest()

            # 检查数据点
            if len(backtest_results['records']) < 50:
                print(f"⚠️  数据点不足({len(backtest_results['records'])})")
                failed.append({
                    'code': code,
                    'name': name,
                    'reason': f"数据点不足({len(backtest_results['records'])})"
                })
                continue

            results.append({
                'code': code,
                'name': name,
                'symbol': symbol,
                'total_return_pct': backtest_results['total_return_pct'],
                'annual_return': backtest_results['annual_return'],
                'max_drawdown': backtest_results['max_drawdown'],
                'investment_count': backtest_results['investment_count'],
                'total_invested': backtest_results['total_invested'],
                'final_value': backtest_results['final_value'],
            })

            print(f"✅ 收益率: {backtest_results['total_return_pct']:+.2f}%, "
                  f"年化: {backtest_results['annual_return']*100:+.2f}%, "
                  f"回撤: {backtest_results['max_drawdown']:.2f}%")

        except Exception as e:
            print(f"❌ {str(e)[:50]}")
            failed.append({
                'code': code,
                'name': name,
                'reason': str(e)[:100]
            })

        # 延迟避免请求过快
        time.sleep(1)

    print()
    print(f"✅ 扫描完成! 成功: {len(results)}, 失败: {len(failed)}")
    print()

    # 生成报告
    if results:
        generate_report(results, failed, start_date, end_date)
    else:
        print("❌ 没有成功的回测结果")


def generate_report(results, failed, start_date, end_date):
    """生成报告"""
    print("=" * 80)
    print("📊 ETF定投排行榜")
    print("=" * 80)
    print()

    # 转换为DataFrame
    df = pd.DataFrame(results)

    # 按总收益率排序
    df = df.sort_values('total_return_pct', ascending=False)

    # 显示排行榜
    print(f"{'排名':<6} {'代码':<10} {'名称':<30} {'总收益':<12} {'年化':<12} {'最大回撤':<12}")
    print("-" * 80)

    for i, row in enumerate(df.iterrows(), 1):
        _, data = row
        print(f"{i:<6} "
              f"{data['code']:<10} "
              f"{data['name']:<30} "
              f"{data['total_return_pct']:>10.2f}% "
              f"{data['annual_return']*100:>10.2f}% "
              f"{data['max_drawdown']:>10.2f}%")

    print()

    # 统计分析
    print("📈 统计分析")
    print("-" * 80)
    print(f"成功扫描: {len(results)}只")
    print(f"平均收益率: {df['total_return_pct'].mean():.2f}%")
    print(f"中位数收益率: {df['total_return_pct'].median():.2f}%")
    print(f"最高收益率: {df['total_return_pct'].max():.2f}% ({df.loc[df['total_return_pct'].idxmax(), 'name']})")
    print(f"最低收益率: {df['total_return_pct'].min():.2f}% ({df.loc[df['total_return_pct'].idxmin(), 'name']})")
    print()

    # Top 5
    print("🏆 Top 5 推荐")
    print("-" * 80)
    top5 = df.head(5)
    for i, row in enumerate(top5.iterrows(), 1):
        _, data = row
        print(f"{i}. {data['name']} ({data['code']})")
        print(f"   总收益: {data['total_return_pct']:+.2f}%, "
              f"年化: {data['annual_return']*100:+.2f}%, "
              f"回撤: {data['max_drawdown']:.2f}%")
    print()

    # 保存结果
    output_file = repo_root / 'data' / f'etf_scan_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"💾 完整结果已保存: {output_file}")
    print()

    # 失败统计
    if failed:
        print("⚠️  失败列表")
        print("-" * 80)
        for item in failed:
            print(f"  {item['code']} {item['name']}: {item['reason']}")
        print()


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='ETF定投扫描工具')
    parser.add_argument('--start', default='2020-01-01', help='起始日期')
    parser.add_argument('--end', default=None, help='结束日期')
    parser.add_argument('--frequency', choices=['daily', 'weekly', 'monthly'], default='monthly',
                        help='定投频率')
    parser.add_argument('--annual', type=float, default=120000, help='年投入总额')

    args = parser.parse_args()

    scan_etf_list(
        start_date=args.start,
        end_date=args.end,
        frequency=args.frequency,
        annual_investment=args.annual
    )

    print()
    print("=" * 80)
    print("扫描完成")
    print("=" * 80)


if __name__ == '__main__':
    main()
