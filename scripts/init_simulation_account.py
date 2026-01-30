#!/usr/bin/env python3
"""
初始化模拟账户

创建默认的50万模拟账户用于AI交易决策
"""

import sys
from pathlib import Path

# 添加项目路径
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))

from trading_os.execution.account_manager import (
    initialize_default_simulation_account,
    get_default_simulation_account
)


def main():
    """主函数"""
    print("🏦 初始化模拟交易账户")
    print("=" * 50)

    # 检查是否已存在
    existing_account = get_default_simulation_account()

    if existing_account:
        print(f"\n✅ 模拟账户已存在")
        print(f"账户ID: {existing_account.account_id}")
        print(f"初始资金: {existing_account.initial_cash:,.2f} 元")
        print(f"当前现金: {existing_account.get_cash():,.2f} 元")
        print(f"创建时间: {existing_account.created_at}")
        print(f"最后更新: {existing_account.last_update}")

        # 询问是否覆盖
        response = input("\n是否重新初始化账户? (yes/no): ").strip().lower()
        if response != 'yes':
            print("取消操作")
            return 0

    # 初始化账户
    print("\n🔧 创建新的模拟账户...")
    account = initialize_default_simulation_account(
        initial_cash=500000.0,
        overwrite=True
    )

    print(f"\n✅ 模拟账户初始化成功!")
    print(f"账户ID: {account.account_id}")
    print(f"账户类型: {account.account_type.value}")
    print(f"初始资金: {account.initial_cash:,.2f} 元")
    print(f"手续费率: {account.fee_rate:.4%}")
    print(f"最低手续费: {account.min_fee:.2f} 元")
    print(f"数据目录: {account.data_dir}")

    print("\n📋 账户说明:")
    print("- 这是一个模拟交易账户，与真实账户完全隔离")
    print("- 初始资金为50万人民币")
    print("- 可以用于AI自主交易决策和策略测试")
    print("- 所有交易都会被记录，便于审计和复盘")
    print("- 未来可以无缝切换到真实账户")

    print("\n🚀 下一步:")
    print("1. 运行市场分析: python -m trading_os agent daily")
    print("2. 获取投资建议: python -m trading_os agent recommend")
    print("3. 查看账户状态: python scripts/check_account_status.py")

    return 0


if __name__ == '__main__':
    sys.exit(main())
