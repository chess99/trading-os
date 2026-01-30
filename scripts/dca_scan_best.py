#!/usr/bin/env python3
"""
定投最佳标的扫描工具

功能:
1. 全量扫描A股市场
2. 对每只股票/ETF进行定投回测
3. 按收益率排序,找出最佳标的
4. 生成详细报告
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import time

# 添加项目路径
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

# 清除代理
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('HTTP_PROXY', None)

from scripts.dca_backtest import DCABacktest
import pandas as pd


class DCAScanner:
    """定投扫描器"""

    def __init__(
        self,
        start_date: str,
        end_date: str = None,
        frequency: str = 'monthly',
        annual_investment: float = 120000,
        min_data_points: int = 100,  # 最少数据点
        max_symbols: int = None,  # 最多扫描数量(测试用)
    ):
        """
        初始化扫描器

        Args:
            start_date: 起始日期
            end_date: 结束日期
            frequency: 定投频率
            annual_investment: 年投入
            min_data_points: 最少数据点(过滤上市时间短的)
            max_symbols: 最多扫描数量(None=全部)
        """
        self.start_date = start_date
        self.end_date = end_date or datetime.now().strftime('%Y-%m-%d')
        self.frequency = frequency
        self.annual_investment = annual_investment
        self.min_data_points = min_data_points
        self.max_symbols = max_symbols

        self.results = []
        self.failed = []

        print("=" * 80)
        print("🔍 定投最佳标的扫描")
        print("=" * 80)
        print(f"起始日期: {self.start_date}")
        print(f"结束日期: {self.end_date}")
        print(f"定投频率: {self.frequency}")
        print(f"年投入: {self.annual_investment:,.0f}元")
        print(f"最少数据点: {self.min_data_points}")
        if self.max_symbols:
            print(f"最多扫描: {self.max_symbols}只")
        print("=" * 80)
        print()

    def get_stock_universe(self) -> List[Dict]:
        """获取股票池"""
        import akshare as ak

        print("📋 获取股票池...")

        try:
            # 获取A股列表
            df = ak.stock_info_a_code_name()
            print(f"  ✅ 获取到 {len(df)} 只A股")

            stocks = []
            for idx, row in df.iterrows():
                code = row['code']
                name = row['name']

                # 判断交易所
                if code.startswith('6'):
                    exchange = 'SSE'
                elif code.startswith(('0', '3')):
                    exchange = 'SZSE'
                else:
                    continue

                symbol = f"{exchange}:{code}"
                stocks.append({
                    'symbol': symbol,
                    'code': code,
                    'name': name,
                    'type': 'stock'
                })

            # 添加常见ETF
            common_etfs = [
                ('SSE:588000', '588000', '华夏科创50ETF'),
                ('SSE:588050', '588050', '华夏科创50ETF'),
                ('SSE:510050', '510050', '华夏上证50ETF'),
                ('SSE:510300', '510300', '华泰柏瑞沪深300ETF'),
                ('SSE:510500', '510500', '南方中证500ETF'),
                ('SSE:512690', '512690', '鹏华中证酒ETF'),
                ('SSE:515050', '515050', '华夏5GETF'),
                ('SZSE:159915', '159915', '易方达创业板ETF'),
                ('SZSE:159919', '159919', '嘉实沪深300ETF'),
            ]

            for symbol, code, name in common_etfs:
                stocks.append({
                    'symbol': symbol,
                    'code': code,
                    'name': name,
                    'type': 'etf'
                })

            print(f"  ✅ 总计 {len(stocks)} 只标的 ({len(stocks)-len(common_etfs)}股票 + {len(common_etfs)}ETF)")

            # 限制数量(测试用)
            if self.max_symbols:
                stocks = stocks[:self.max_symbols]
                print(f"  ⚠️  限制扫描数量: {len(stocks)}只")

            return stocks

        except Exception as e:
            print(f"  ❌ 获取股票池失败: {e}")
            return []

    def scan_symbol(self, symbol_info: Dict) -> Dict:
        """扫描单个标的"""
        symbol = symbol_info['symbol']
        name = symbol_info['name']
        code = symbol_info['code']

        try:
            # 创建回测
            backtest = DCABacktest(
                symbol=symbol,
                start_date=self.start_date,
                end_date=self.end_date,
                frequency=self.frequency,
                annual_investment=self.annual_investment,
                data_source='online'
            )

            # 运行回测
            results = backtest.run_backtest()

            # 检查数据点数量
            if len(results['records']) < self.min_data_points:
                return {
                    'success': False,
                    'reason': f"数据点不足({len(results['records'])})"
                }

            return {
                'success': True,
                'symbol': symbol,
                'code': code,
                'name': name,
                'type': symbol_info['type'],
                'total_return_pct': results['total_return_pct'],
                'annual_return': results['annual_return'],
                'max_drawdown': results['max_drawdown'],
                'sharpe_ratio': results['sharpe_ratio'],
                'investment_count': results['investment_count'],
                'total_invested': results['total_invested'],
                'final_value': results['final_value'],
                'avg_cost': results['avg_cost'],
                'final_price': results['final_price'],
            }

        except Exception as e:
            return {
                'success': False,
                'reason': str(e)
            }

    def scan_all(self):
        """扫描所有标的"""
        # 获取股票池
        universe = self.get_stock_universe()
        if not universe:
            print("❌ 无法获取股票池")
            return

        total = len(universe)
        print()
        print(f"🔄 开始扫描 {total} 只标的...")
        print()

        for i, symbol_info in enumerate(universe, 1):
            symbol = symbol_info['symbol']
            name = symbol_info['name']

            print(f"[{i}/{total}] {symbol} {name}...", end=' ', flush=True)

            result = self.scan_symbol(symbol_info)

            if result['success']:
                self.results.append(result)
                print(f"✅ 收益率: {result['total_return_pct']:+.2f}%")
            else:
                self.failed.append({
                    'symbol': symbol,
                    'name': name,
                    'reason': result['reason']
                })
                print(f"❌ {result['reason']}")

            # 添加延迟,避免请求过快
            time.sleep(0.5)

        print()
        print(f"✅ 扫描完成! 成功: {len(self.results)}, 失败: {len(self.failed)}")

    def generate_report(self, top_n: int = 20):
        """生成报告"""
        if not self.results:
            print("❌ 没有成功的回测结果")
            return

        print()
        print("=" * 80)
        print("📊 扫描结果报告")
        print("=" * 80)
        print()

        # 转换为DataFrame
        df = pd.DataFrame(self.results)

        # 按总收益率排序
        df = df.sort_values('total_return_pct', ascending=False)

        # Top N
        top_df = df.head(top_n)

        print(f"🏆 定投收益率 Top {top_n}")
        print("-" * 80)
        print(f"{'排名':<6} {'代码':<10} {'名称':<20} {'类型':<8} {'总收益':<12} {'年化':<12} {'最大回撤':<12}")
        print("-" * 80)

        for i, row in enumerate(top_df.iterrows(), 1):
            _, data = row
            print(f"{i:<6} "
                  f"{data['code']:<10} "
                  f"{data['name']:<20} "
                  f"{data['type']:<8} "
                  f"{data['total_return_pct']:>10.2f}% "
                  f"{data['annual_return']*100:>10.2f}% "
                  f"{data['max_drawdown']:>10.2f}%")

        print()

        # 统计分析
        print("📈 统计分析")
        print("-" * 80)
        print(f"总扫描数: {len(self.results)}只")
        print(f"平均收益率: {df['total_return_pct'].mean():.2f}%")
        print(f"中位数收益率: {df['total_return_pct'].median():.2f}%")
        print(f"最高收益率: {df['total_return_pct'].max():.2f}% ({df.loc[df['total_return_pct'].idxmax(), 'name']})")
        print(f"最低收益率: {df['total_return_pct'].min():.2f}% ({df.loc[df['total_return_pct'].idxmin(), 'name']})")
        print()

        # 按类型统计
        print("📊 按类型统计")
        print("-" * 80)
        for type_name in df['type'].unique():
            type_df = df[df['type'] == type_name]
            print(f"{type_name}:")
            print(f"  数量: {len(type_df)}只")
            print(f"  平均收益率: {type_df['total_return_pct'].mean():.2f}%")
            print(f"  最高收益率: {type_df['total_return_pct'].max():.2f}%")
        print()

        # 保存结果
        output_file = repo_root / 'data' / f'dca_scan_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"💾 完整结果已保存: {output_file}")
        print()

        # 失败统计
        if self.failed:
            print("⚠️  失败统计")
            print("-" * 80)
            failure_reasons = {}
            for item in self.failed:
                reason = item['reason']
                if reason not in failure_reasons:
                    failure_reasons[reason] = 0
                failure_reasons[reason] += 1

            for reason, count in sorted(failure_reasons.items(), key=lambda x: x[1], reverse=True):
                print(f"  {reason}: {count}只")
            print()


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='定投最佳标的扫描工具')
    parser.add_argument('--start', default='2020-01-01', help='起始日期')
    parser.add_argument('--end', default=None, help='结束日期')
    parser.add_argument('--frequency', choices=['daily', 'weekly', 'monthly'], default='monthly',
                        help='定投频率')
    parser.add_argument('--annual', type=float, default=120000, help='年投入总额')
    parser.add_argument('--top', type=int, default=20, help='显示Top N')
    parser.add_argument('--max-symbols', type=int, default=None, help='最多扫描数量(测试用)')
    parser.add_argument('--min-data-points', type=int, default=100, help='最少数据点')

    args = parser.parse_args()

    # 创建扫描器
    scanner = DCAScanner(
        start_date=args.start,
        end_date=args.end,
        frequency=args.frequency,
        annual_investment=args.annual,
        min_data_points=args.min_data_points,
        max_symbols=args.max_symbols
    )

    # 执行扫描
    scanner.scan_all()

    # 生成报告
    scanner.generate_report(top_n=args.top)

    print()
    print("=" * 80)
    print("扫描完成")
    print("=" * 80)


if __name__ == '__main__':
    main()
