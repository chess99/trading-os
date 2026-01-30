#!/usr/bin/env python3
"""
测试实时价格获取功能

验证实时价格接口是否正常工作
"""

import sys
from pathlib import Path

# 添加项目路径
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))

from trading_os.data.sources.realtime_price import (
    get_realtime_price,
    get_realtime_prices,
    get_stock_realtime_info
)


def main():
    """主函数"""
    print("🧪 测试实时价格获取功能")
    print("=" * 70)

    # 测试股票列表
    test_symbols = [
        "SSE:600000",  # 浦发银行
        "SSE:600519",  # 贵州茅台
    ]

    # 测试单个股票实时价格
    print("\n📊 测试1: 获取单个股票实时价格")
    print("-" * 70)

    for symbol in test_symbols:
        try:
            price = get_realtime_price(symbol)
            if price:
                print(f"✅ {symbol}: {price:.2f} 元")
            else:
                print(f"❌ {symbol}: 获取失败")
        except Exception as e:
            print(f"❌ {symbol}: {e}")

    # 测试批量获取
    print("\n📊 测试2: 批量获取实时价格")
    print("-" * 70)

    try:
        prices = get_realtime_prices(test_symbols)
        for symbol, price in prices.items():
            print(f"✅ {symbol}: {price:.2f} 元")

        if len(prices) != len(test_symbols):
            print(f"\n⚠️  警告: 预期{len(test_symbols)}只股票,实际获取{len(prices)}只")
    except Exception as e:
        print(f"❌ 批量获取失败: {e}")

    # 测试详细信息
    print("\n📊 测试3: 获取股票详细信息")
    print("-" * 70)

    for symbol in test_symbols:
        try:
            info = get_stock_realtime_info(symbol)
            if info:
                print(f"\n{symbol} ({info['name']}):")
                print(f"  最新价: {info['price']:.2f} 元")
                print(f"  涨跌额: {info['change']:+.2f} 元")
                print(f"  涨跌幅: {info['change_pct']:+.2f}%")
                print(f"  成交量: {info['volume']:.0f} 手")
                print(f"  今开: {info['open']:.2f}")
                print(f"  最高: {info['high']:.2f}")
                print(f"  最低: {info['low']:.2f}")
                print(f"  昨收: {info['prev_close']:.2f}")
            else:
                print(f"❌ {symbol}: 获取详细信息失败")
        except Exception as e:
            print(f"❌ {symbol}: {e}")

    print("\n" + "=" * 70)
    print("✅ 测试完成")

    return 0


if __name__ == '__main__':
    sys.exit(main())
