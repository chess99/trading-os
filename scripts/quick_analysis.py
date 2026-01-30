#!/usr/bin/env python3
"""
快速市场分析 - 不依赖实时因子数据

基于现有账户数据和实时价格进行分析
"""

import json
import os
from pathlib import Path
from datetime import datetime

# 配置代理
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7897'
os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7897'

print("=" * 80)
print("📊 Trading OS - 快速市场分析")
print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)
print()

# 1. 读取账户数据
print("💰 账户状态")
print("-" * 80)

account_file = Path("data/accounts/default_simulation.json")
with open(account_file) as f:
    account_data = json.load(f)

initial_cash = account_data['initial_cash']
current_cash = account_data['current_cash']
positions = account_data['positions']

print(f"账户ID: {account_data['account_id']}")
print(f"初始资金: {initial_cash:,.2f}元")
print(f"现金余额: {current_cash:,.2f}元")
print(f"持仓数量: {len(positions)}只")
print()

# 2. 持仓分析
print("📈 持仓分析")
print("-" * 80)

import sys
sys.path.insert(0, 'src')

total_position_value = 0
total_cost = 0
total_pnl = 0

if positions:
    from trading_os.data.sources.realtime_price import get_realtime_price

    print("正在获取实时价格...")
    print()

    for symbol, pos in positions.items():
        qty = pos['qty']
        avg_price = pos['avg_price']
        cost_value = qty * avg_price

        try:
            # 获取实时价格
            current_price = get_realtime_price(symbol)

            # 计算盈亏
            current_value = qty * current_price
            pnl = current_value - cost_value
            pnl_pct = (current_price / avg_price - 1) * 100

            total_position_value += current_value
            total_cost += cost_value
            total_pnl += pnl

            # 显示持仓详情
            print(f"🔹 {symbol}")
            print(f"   持仓: {qty:,.0f}股")
            print(f"   成本价: {avg_price:.2f}元")
            print(f"   现价: {current_price:.2f}元")
            print(f"   成本市值: {cost_value:,.2f}元")
            print(f"   当前市值: {current_value:,.2f}元")
            print(f"   盈亏: {pnl:+,.2f}元 ({pnl_pct:+.2f}%)")
            print()

        except Exception as e:
            print(f"   ⚠️  获取价格失败: {e}")
            print()
else:
    print("当前无持仓")
    print()

# 3. 账户汇总
print("💼 账户汇总")
print("-" * 80)

total_value = current_cash + total_position_value
total_return = total_value - initial_cash
total_return_pct = (total_value / initial_cash - 1) * 100

position_ratio = (total_position_value / total_value * 100) if total_value > 0 else 0
cash_ratio = (current_cash / total_value * 100) if total_value > 0 else 100

print(f"账户总值: {total_value:,.2f}元")
print(f"总盈亏: {total_return:+,.2f}元 ({total_return_pct:+.2f}%)")
print()
print(f"现金: {current_cash:,.2f}元 ({cash_ratio:.1f}%)")
print(f"持仓市值: {total_position_value:,.2f}元 ({position_ratio:.1f}%)")
print()

# 4. 投资建议
print("💡 投资建议")
print("-" * 80)

if position_ratio < 30:
    print("🟡 仓位状态: 偏低")
    print()
    print("建议:")
    print("  1. 当前仓位仅{:.1f}%，有较大建仓空间".format(position_ratio))
    print("  2. 可用资金: {:.2f}万元".format(current_cash/10000))
    print("  3. 建议逐步建仓至40-50%")
    print("  4. 分散配置2-3只优质标的")
    print()

elif position_ratio < 50:
    print("🟢 仓位状态: 适中")
    print()
    print("建议:")
    print("  1. 当前仓位{:.1f}%，处于合理区间".format(position_ratio))
    print("  2. 保持当前配置，关注市场变化")
    print("  3. 根据市场情况适度调整")
    print()

elif position_ratio < 70:
    print("🟠 仓位状态: 偏高")
    print()
    print("建议:")
    print("  1. 当前仓位{:.1f}%，相对较高".format(position_ratio))
    print("  2. 注意风险控制")
    print("  3. 考虑分批获利了结")
    print()

else:
    print("🔴 仓位状态: 过高")
    print()
    print("建议:")
    print("  1. 当前仓位{:.1f}%，风险较大".format(position_ratio))
    print("  2. 建议及时减仓")
    print("  3. 保持适当现金储备")
    print()

# 持仓集中度分析
if len(positions) == 0:
    print("📌 持仓建议:")
    print("  - 当前空仓，建议开始建仓")
    print("  - 建议配置2-3只优质股票")
    print("  - 分散行业配置，降低风险")
    print()

elif len(positions) == 1:
    print("📌 持仓建议:")
    print("  - 当前仅持有1只股票，集中度过高")
    print("  - 建议增加1-2只，实现分散配置")
    print("  - 注意行业分散，避免系统性风险")
    print()

elif len(positions) <= 3:
    print("📌 持仓建议:")
    print("  - 持仓数量合理")
    print("  - 继续关注个股表现")
    print("  - 定期评估调仓")
    print()

else:
    print("📌 持仓建议:")
    print("  - 持仓数量较多")
    print("  - 考虑优化持仓结构")
    print("  - 集中配置优质标的")
    print()

# 5. 下一步行动
print("🎯 下一步行动")
print("-" * 80)
print("""
基于当前状态，建议采取以下行动:

方案A: 技术分析选股 (无需实时因子数据)
  1. 使用数据湖中的历史价格数据
  2. 计算技术指标(动量、波动率、趋势)
  3. 筛选技术面强势股票
  4. 结合行业研究确定标的

方案B: 集成Tushare Pro (获取基本面数据)
  1. 注册Tushare Pro账号 (免费)
  2. 获取基本面因子(PE/PB/ROE等)
  3. 进行多因子选股
  4. 更全面的投资决策

方案C: 手动筛选 + 系统执行
  1. 基于您的研究和判断筛选标的
  2. 告诉我标的代码
  3. 系统进行风控和资金分配
  4. 执行交易并跟踪

推荐: 方案A或C，可以立即开始
""")

print()
print("=" * 80)
print("分析完成")
print("=" * 80)
print()
print("💬 董事长，请告诉我下一步想做什么:")
print("   1. 基于技术分析筛选标的")
print("   2. 您提供标的，我来分析和执行")
print("   3. 集成Tushare获取更多数据")
print("   4. 其他需求")
