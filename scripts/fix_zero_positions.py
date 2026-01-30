#!/usr/bin/env python3
"""
修复0股持仓问题

清理账户中数量为0的持仓记录
"""

import sys
from pathlib import Path

# 添加项目路径
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))

from trading_os.execution.account_manager import get_default_simulation_account


def main():
    """主函数"""
    print("🔧 修复0股持仓问题")
    print("=" * 70)

    # 获取账户
    account = get_default_simulation_account()
    if not account:
        print("❌ 账户不存在")
        return 1

    # 检查持仓
    positions = account.get_positions()
    print(f"\n当前持仓数量: {len(positions)}")

    # 找出0股持仓
    zero_positions = []
    for symbol, pos in positions.items():
        if pos.qty == 0:
            zero_positions.append(symbol)
            print(f"  ⚠️  发现0股持仓: {symbol}")

    if not zero_positions:
        print("\n✅ 没有0股持仓，无需修复")
        return 0

    # 清理0股持仓
    print(f"\n🔄 清理 {len(zero_positions)} 个0股持仓...")
    for symbol in zero_positions:
        account.portfolio.positions.pop(symbol, None)
        print(f"  ✓ 已清理: {symbol}")

    # 保存账户
    account.save()
    print("\n💾 账户已保存")

    # 验证
    positions_after = account.get_positions()
    print(f"\n✅ 修复完成")
    print(f"修复前持仓数: {len(positions)}")
    print(f"修复后持仓数: {len(positions_after)}")
    print(f"清理数量: {len(zero_positions)}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
