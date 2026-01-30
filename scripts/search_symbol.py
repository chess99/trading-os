#!/usr/bin/env python3
"""
股票/ETF名称搜索工具

支持通过名称、拼音、代码搜索
"""

import os
import sys
from pathlib import Path

# 清除代理
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('HTTP_PROXY', None)

import akshare as ak
import pandas as pd


def search_stock(keyword: str, limit: int = 10):
    """搜索股票"""
    print(f"🔍 搜索股票: {keyword}")
    print("-" * 70)

    try:
        # 获取A股列表
        df = ak.stock_info_a_code_name()

        # 搜索
        mask = (df['code'].str.contains(keyword, case=False, na=False) |
                df['name'].str.contains(keyword, case=False, na=False))
        results = df[mask].head(limit)

        if len(results) > 0:
            print(f"找到 {len(results)} 个结果:\n")
            for idx, row in results.iterrows():
                code = row['code']
                name = row['name']

                # 判断交易所
                if code.startswith('6'):
                    exchange = 'SSE'
                elif code.startswith(('0', '3')):
                    exchange = 'SZSE'
                else:
                    exchange = 'UNKNOWN'

                symbol = f"{exchange}:{code}"
                print(f"  {symbol:<15} {name}")

            return results
        else:
            print("未找到匹配的股票")
            return None

    except Exception as e:
        print(f"❌ 搜索失败: {e}")
        return None


def search_etf(keyword: str, limit: int = 10):
    """搜索ETF"""
    print(f"🔍 搜索ETF: {keyword}")
    print("-" * 70)

    try:
        # 获取ETF基本信息(使用历史数据接口获取代码列表)
        # 由于spot接口不稳定,我们使用已知的常见ETF列表
        common_etfs = {
            '588000': '华夏科创50ETF',
            '588050': '华夏科创50ETF',
            '510050': '华夏上证50ETF',
            '510300': '华泰柏瑞沪深300ETF',
            '510500': '南方中证500ETF',
            '512690': '鹏华中证酒ETF',
            '512880': '国泰中证全指证券公司ETF',
            '515050': '华夏5GETF',
            '515790': '华夏中证新能源汽车ETF',
            '159915': '易方达创业板ETF',
            '159919': '嘉实沪深300ETF',
            '159928': '汇添富中证主要消费ETF',
            '159995': '华夏国证半导体芯片ETF',
            '512000': '券商ETF',
            '512010': '医药ETF',
            '512760': '国泰CES半导体芯片ETF',
        }

        # 搜索
        results = []
        for code, name in common_etfs.items():
            if keyword.lower() in code.lower() or keyword in name:
                results.append({'code': code, 'name': name})

        if len(results) > 0:
            print(f"找到 {len(results)} 个结果:\n")
            for item in results[:limit]:
                code = item['code']
                name = item['name']

                # 判断交易所
                if code.startswith('5'):
                    exchange = 'SSE'
                elif code.startswith('1'):
                    exchange = 'SZSE'
                else:
                    exchange = 'UNKNOWN'

                symbol = f"{exchange}:{code}" if exchange != 'UNKNOWN' else code
                print(f"  {symbol:<15} {name}")

            return pd.DataFrame(results)
        else:
            print("未找到匹配的ETF")
            print("\n💡 提示: 可以直接使用ETF代码(如 588000, 510300)")
            return None

    except Exception as e:
        print(f"❌ 搜索失败: {e}")
        return None


def search_all(keyword: str, limit: int = 10):
    """搜索股票和ETF"""
    print("=" * 70)
    print(f"🔍 搜索: {keyword}")
    print("=" * 70)
    print()

    # 搜索股票
    stock_results = search_stock(keyword, limit)
    print()

    # 搜索ETF
    etf_results = search_etf(keyword, limit)
    print()

    if stock_results is None and etf_results is None:
        print("💡 提示:")
        print("  - 输入股票名称: 如 '浦发', '茅台', '平安'")
        print("  - 输入ETF名称: 如 '科创', '半导体', '医药'")
        print("  - 输入代码: 如 '600000', '588000'")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='股票/ETF搜索工具')
    parser.add_argument('keyword', help='搜索关键词(名称/代码)')
    parser.add_argument('--type', choices=['stock', 'etf', 'all'], default='all',
                        help='搜索类型')
    parser.add_argument('--limit', type=int, default=10, help='最多显示结果数')

    args = parser.parse_args()

    if args.type == 'stock':
        search_stock(args.keyword, args.limit)
    elif args.type == 'etf':
        search_etf(args.keyword, args.limit)
    else:
        search_all(args.keyword, args.limit)


if __name__ == '__main__':
    main()
