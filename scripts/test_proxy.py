#!/usr/bin/env python3
"""
测试代理配置和数据获取

测试步骤:
1. 测试代理基本连接
2. 测试akshare数据获取
3. 测试实时价格获取
"""

import os
import sys
from pathlib import Path

# 添加项目路径
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))

# 配置代理
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7897'
os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7897'

print("=" * 60)
print("代理配置测试")
print("=" * 60)
print(f"HTTPS_PROXY: {os.environ.get('HTTPS_PROXY')}")
print(f"HTTP_PROXY: {os.environ.get('HTTP_PROXY')}")
print()

# 测试1: 基本网络连接
print("测试1: 基本网络连接")
print("-" * 60)
try:
    import requests
    response = requests.get(
        'https://82.push2.eastmoney.com',
        timeout=10,
        proxies={
            'http': os.environ['HTTP_PROXY'],
            'https': os.environ['HTTPS_PROXY']
        }
    )
    print(f"✅ 代理连接成功")
    print(f"   状态码: {response.status_code}")
except Exception as e:
    print(f"❌ 代理连接失败: {e}")
print()

# 测试2: akshare股票列表
print("测试2: akshare股票列表获取")
print("-" * 60)
try:
    import akshare as ak
    df = ak.stock_info_a_code_name()
    print(f"✅ 成功获取股票列表")
    print(f"   股票数量: {len(df)}")
    print(f"   前5只股票:")
    print(df.head())
except Exception as e:
    print(f"❌ 获取股票列表失败: {e}")
print()

# 测试3: 实时行情
print("测试3: 实时行情获取")
print("-" * 60)
try:
    import akshare as ak
    df = ak.stock_zh_a_spot_em()
    print(f"✅ 成功获取实时行情")
    print(f"   股票数量: {len(df)}")
    print(f"   前3只股票:")
    print(df[['代码', '名称', '最新价', '涨跌幅']].head(3))
except Exception as e:
    print(f"❌ 获取实时行情失败: {e}")
print()

# 测试4: 获取浦发银行实时价格
print("测试4: 浦发银行实时价格")
print("-" * 60)
try:
    from trading_os.data.sources.realtime_price import get_realtime_price
    price = get_realtime_price("SSE:600000")
    print(f"✅ 成功获取浦发银行价格")
    print(f"   价格: {price:.2f}元")
except Exception as e:
    print(f"❌ 获取价格失败: {e}")
print()

# 测试5: 获取股票基本信息
print("测试5: 股票基本信息获取")
print("-" * 60)
try:
    from trading_os.data.sources.akshare_factors import AkshareFactorSource
    source = AkshareFactorSource()
    stock_list = source.get_a_stock_list()
    print(f"✅ 成功获取股票基本信息")
    print(f"   股票数量: {len(stock_list)}")
    print(f"   前5只股票:")
    print(stock_list.head())
except Exception as e:
    print(f"❌ 获取基本信息失败: {e}")
    import traceback
    traceback.print_exc()
print()

print("=" * 60)
print("测试完成")
print("=" * 60)
