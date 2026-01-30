#!/usr/bin/env python3
"""
重置模拟账户

清理所有错误的交易记录，重新初始化账户
"""

import json
from pathlib import Path
from datetime import datetime

print("=" * 80)
print("🔄 重置模拟账户")
print("=" * 80)
print()

# 账户参数
ACCOUNT_ID = "default_simulation"
INITIAL_CASH = 500000.0
FEE_RATE = 0.0003
MIN_FEE = 5.0

# 文件路径
data_dir = Path("data/accounts")
account_file = data_dir / f"{ACCOUNT_ID}.json"
transactions_file = data_dir / f"{ACCOUNT_ID}_transactions.jsonl"
snapshots_file = data_dir / f"{ACCOUNT_ID}_snapshots.jsonl"

# 备份旧文件
print("📦 备份旧文件...")
if account_file.exists():
    backup_file = data_dir / f"{ACCOUNT_ID}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    account_file.rename(backup_file)
    print(f"  ✅ 账户文件已备份: {backup_file.name}")

if transactions_file.exists():
    backup_file = data_dir / f"{ACCOUNT_ID}_transactions_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    transactions_file.rename(backup_file)
    print(f"  ✅ 交易记录已备份: {backup_file.name}")

if snapshots_file.exists():
    backup_file = data_dir / f"{ACCOUNT_ID}_snapshots_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    snapshots_file.rename(backup_file)
    print(f"  ✅ 快照记录已备份: {backup_file.name}")

print()

# 创建新账户
print("✨ 创建新账户...")
new_account = {
    "account_id": ACCOUNT_ID,
    "account_type": "SIMULATION",
    "initial_cash": INITIAL_CASH,
    "current_cash": INITIAL_CASH,
    "fee_rate": FEE_RATE,
    "min_fee": MIN_FEE,
    "created_at": datetime.now().isoformat(),
    "last_update": datetime.now().isoformat(),
    "positions": {}
}

with open(account_file, 'w', encoding='utf-8') as f:
    json.dump(new_account, f, indent=2, ensure_ascii=False)

print(f"  ✅ 新账户已创建")
print()

# 显示账户信息
print("💰 新账户信息")
print("-" * 80)
print(f"账户ID: {ACCOUNT_ID}")
print(f"账户类型: 模拟账户")
print(f"初始资金: {INITIAL_CASH:,.2f}元")
print(f"现金余额: {INITIAL_CASH:,.2f}元")
print(f"持仓数量: 0只")
print(f"手续费率: {FEE_RATE:.4%}")
print(f"最低手续费: {MIN_FEE:.2f}元")
print(f"创建时间: {new_account['created_at']}")
print()

# 清理决策记录中的相关记录
decisions_file = Path("data/decisions/decisions.jsonl")
if decisions_file.exists():
    print("🧹 清理决策记录...")

    # 读取所有决策
    decisions = []
    with open(decisions_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                decisions.append(json.loads(line))

    # 备份
    backup_file = decisions_file.parent / f"decisions_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    decisions_file.rename(backup_file)
    print(f"  ✅ 决策记录已备份: {backup_file.name}")

    # 过滤掉今天的错误决策(可选：保留所有，或只删除今天的)
    # 这里我们创建一个空的决策文件
    with open(decisions_file, 'w', encoding='utf-8') as f:
        pass  # 创建空文件

    print(f"  ✅ 决策记录已清空")
    print()

print("=" * 80)
print("✅ 账户重置完成！")
print("=" * 80)
print()
print("📊 账户状态:")
print(f"  初始资金: {INITIAL_CASH:,.2f}元")
print(f"  可用资金: {INITIAL_CASH:,.2f}元")
print(f"  持仓: 空仓")
print()
print("💡 下一步:")
print("  1. 运行 python scripts/quick_analysis.py 查看账户状态")
print("  2. 开始新的投资决策")
