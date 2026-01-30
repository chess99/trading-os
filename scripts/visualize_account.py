#!/usr/bin/env python3
"""
账户可视化脚本

生成账户状态、持仓分布等图表
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from trading_os.account.account import load_account
from trading_os.visualization.charts import (
    plot_holdings_distribution,
    plot_portfolio_summary
)


def main():
    """主函数"""
    print("📊 生成账户可视化报告")
    print("=" * 70)

    # 加载账户
    try:
        account = load_account()
    except Exception as e:
        print(f"❌ 加载账户失败: {e}")
        return

    # 获取账户状态
    status = account.get_status()

    print(f"\n账户总值: {status.total_value:,.2f} 元")
    print(f"现金: {status.cash:,.2f} 元")
    print(f"持仓市值: {status.holdings_value:,.2f} 元")
    print(f"总收益率: {status.total_return:.2%}")

    # 准备数据
    holdings_value = {}
    holdings_detail = {}

    for position in status.positions:
        symbol = position.symbol
        value = position.market_value
        holdings_value[symbol] = value

        holdings_detail[symbol] = {
            'shares': position.shares,
            'value': value,
            'return': position.unrealized_return_pct
        }

    # 创建输出目录
    output_dir = project_root / "data" / "visualizations"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1. 持仓分布饼图
    if holdings_value:
        plot_holdings_distribution(
            holdings_value,
            output_dir / f"{timestamp}_holdings_distribution.png"
        )
    else:
        print("\n⚠️  没有持仓,跳过持仓分布图")

    # 2. 投资组合总结
    account_data = {
        'total_value': status.total_value,
        'cash': status.cash,
        'holdings': holdings_detail,
        'total_return': status.total_return
    }

    plot_portfolio_summary(
        account_data,
        output_dir / f"{timestamp}_portfolio_summary.png"
    )

    print(f"\n✅ 可视化报告已生成: {output_dir}")
    print(f"   - {timestamp}_holdings_distribution.png")
    print(f"   - {timestamp}_portfolio_summary.png")


if __name__ == "__main__":
    main()
