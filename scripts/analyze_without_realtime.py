#!/usr/bin/env python3
"""
基于现有数据的市场分析

不依赖实时因子数据,使用:
1. 数据湖中的历史价格数据
2. 技术指标分析
3. 现有持仓分析
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目路径
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))

print("=" * 70)
print("📊 Trading OS - 市场分析报告")
print(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)
print()

# 1. 账户状态
print("💰 账户状态")
print("-" * 70)
try:
    from trading_os.execution.simulation_account import SimulationAccount
    from trading_os.paths import repo_root

    db_path = repo_root() / "data" / "simulation_account.db"
    account = SimulationAccount("default_simulation", db_path)

    cash = account.get_cash()
    positions = account.get_positions()
    total_value = account.get_total_value()

    print(f"账户ID: {account.account_id}")
    print(f"现金余额: {cash:,.2f}元")
    print(f"持仓数量: {len(positions)}只")
    print(f"账户总值: {total_value:,.2f}元")
    print()

    if positions:
        print("持仓明细:")
        for symbol, pos in positions.items():
            print(f"  {symbol}:")
            print(f"    数量: {pos.quantity:,}股")
            print(f"    成本: {pos.avg_cost:.2f}元")
            print(f"    市值: {pos.quantity * pos.avg_cost:,.2f}元")
        print()

    # 计算仓位
    if total_value > 0:
        position_value = sum(p.quantity * p.avg_cost for p in positions.values())
        position_ratio = position_value / total_value * 100
        print(f"总仓位: {position_ratio:.2f}%")
        print(f"现金比例: {100-position_ratio:.2f}%")

except Exception as e:
    print(f"❌ 获取账户信息失败: {e}")
    import traceback
    traceback.print_exc()

print()
print()

# 2. 持仓分析
print("📈 持仓分析")
print("-" * 70)
try:
    if positions:
        # 配置代理
        os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7897'
        os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7897'

        from trading_os.data.sources.realtime_price import get_realtime_price

        print("获取实时价格...")
        for symbol in positions.keys():
            try:
                current_price = get_realtime_price(symbol)
                pos = positions[symbol]
                cost = pos.avg_cost
                pnl = (current_price - cost) * pos.quantity
                pnl_pct = (current_price / cost - 1) * 100

                print(f"\n{symbol}:")
                print(f"  持仓: {pos.quantity:,}股")
                print(f"  成本价: {cost:.2f}元")
                print(f"  现价: {current_price:.2f}元")
                print(f"  盈亏: {pnl:+,.2f}元 ({pnl_pct:+.2f}%)")
                print(f"  市值: {current_price * pos.quantity:,.2f}元")

            except Exception as e:
                print(f"  ⚠️ 获取{symbol}价格失败: {e}")
    else:
        print("当前无持仓")

except Exception as e:
    print(f"❌ 持仓分析失败: {e}")

print()
print()

# 3. 投资建议
print("💡 投资建议")
print("-" * 70)

try:
    # 基于当前账户状态给出建议
    if total_value > 0:
        position_value = sum(p.quantity * p.avg_cost for p in positions.values())
        position_ratio = position_value / total_value * 100

        print(f"当前仓位: {position_ratio:.2f}%")
        print()

        if position_ratio < 30:
            print("🟡 仓位较低")
            print("   建议: 考虑增加配置,提升至40-50%")
            print("   可用资金: {:.2f}万元".format(cash/10000))
            print()

        elif position_ratio < 50:
            print("🟢 仓位适中")
            print("   建议: 保持当前配置,关注市场变化")
            print()

        else:
            print("🔴 仓位较高")
            print("   建议: 注意风险控制,考虑分散配置")
            print()

        # 持仓数量建议
        if len(positions) == 0:
            print("📌 持仓建议:")
            print("   - 建议建仓2-3只优质股票")
            print("   - 分散行业配置")
            print("   - 控制单只仓位≤20%")

        elif len(positions) == 1:
            print("📌 持仓建议:")
            print("   - 当前持仓过于集中")
            print("   - 建议增加1-2只,分散风险")
            print("   - 注意行业分散")

        else:
            print("📌 持仓建议:")
            print("   - 持仓数量合理")
            print("   - 继续关注个股表现")
            print("   - 定期调仓优化")

except Exception as e:
    print(f"❌ 生成建议失败: {e}")

print()
print()

# 4. 下一步行动
print("🎯 下一步行动建议")
print("-" * 70)
print("""
由于网络限制无法获取实时因子数据,建议:

方案1: 基于技术分析(推荐)
  - 使用数据湖中的历史数据
  - 计算技术指标(动量、波动率)
  - 筛选技术面强势股票

方案2: 集成Tushare数据源
  - 注册Tushare Pro账号
  - 获取基本面因子数据
  - 进行全面的多因子分析

方案3: 手动筛选
  - 基于行业研究和市场判断
  - 人工筛选优质标的
  - 系统执行交易和风控
""")

print()
print("=" * 70)
print("报告完成")
print("=" * 70)
