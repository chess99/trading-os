#!/usr/bin/env python3
"""
执行交易

基于市场分析执行交易决策
"""

import sys
from pathlib import Path

# 添加项目路径
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))

from trading_os.execution.account_manager import get_default_simulation_account
from trading_os.decision import get_default_decision_logger, DecisionType, DecisionStatus
from trading_os.data.sources.realtime_price import get_realtime_price


def get_latest_price(symbol: str) -> float:
    """
    获取最新价格

    使用实时行情接口获取最新价格,确保交易价格准确
    """
    price = get_realtime_price(symbol)
    if price is None:
        raise ValueError(f"无法获取 {symbol} 的实时价格")
    return price


def execute_buy_decision(
    symbol: str,
    name: str,
    amount: float,
    reasoning: str,
    risk_factors: list,
    expected_return: float
):
    """执行买入决策"""
    print(f"\n{'='*70}")
    print(f"📈 执行买入决策: {name} ({symbol})")
    print(f"{'='*70}")

    # 获取账户
    account = get_default_simulation_account()
    if not account:
        print("❌ 账户不存在")
        return False

    # 获取最新价格
    try:
        price = get_latest_price(symbol)
        print(f"\n当前价格: {price:.2f} 元")
    except Exception as e:
        print(f"❌ 获取价格失败: {e}")
        return False

    # 计算买入数量
    shares = int(amount / price / 100) * 100  # A股100股整数倍
    actual_amount = shares * price

    print(f"计划金额: {amount:,.2f} 元")
    print(f"买入数量: {shares} 股")
    print(f"实际金额: {actual_amount:,.2f} 元")

    # 检查资金
    if actual_amount > account.get_cash():
        print(f"❌ 资金不足: 需要 {actual_amount:,.2f}, 可用 {account.get_cash():,.2f}")
        return False

    # 记录决策
    decision_logger = get_default_decision_logger()
    decision = decision_logger.log_decision(
        decision_type=DecisionType.BUY_DECISION,
        title=f"买入 {name}",
        description=f"基于市场分析，买入 {name}",
        reasoning=reasoning,
        data_sources=[
            "市场分析报告",
            f"数据湖 - {symbol}历史数据",
            "技术指标分析"
        ],
        risk_level="medium",
        risk_factors=risk_factors,
        target_symbols=[symbol],
        target_amount=actual_amount,
        expected_return=expected_return
    )

    print(f"\n📝 决策已记录: {decision.decision_id}")

    # 确认执行
    print(f"\n⚠️  即将执行买入操作，请确认:")
    print(f"   股票: {name} ({symbol})")
    print(f"   价格: {price:.2f} 元")
    print(f"   数量: {shares} 股")
    print(f"   金额: {actual_amount:,.2f} 元")

    confirm = input("\n是否确认执行? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ 取消交易")
        decision_logger.reject_decision(decision.decision_id, "用户取消")
        return False

    # 执行交易
    print("\n🔄 执行交易...")
    transaction = account.buy(
        symbol=symbol,
        quantity=shares,
        price=price,
        reason=f"基于市场分析买入，决策ID: {decision.decision_id}"
    )

    if not transaction:
        print("❌ 交易失败")
        decision_logger.reject_decision(decision.decision_id, "交易执行失败")
        return False

    # 记录执行结果
    decision_logger.record_execution(
        decision.decision_id,
        {
            "transaction_id": transaction.transaction_id,
            "symbol": symbol,
            "quantity": shares,
            "price": price,
            "amount": actual_amount,
            "fee": transaction.fee
        }
    )

    # 保存账户状态
    account.save()

    print(f"\n✅ 交易成功!")
    print(f"   交易ID: {transaction.transaction_id}")
    print(f"   剩余现金: {account.get_cash():,.2f} 元")

    return True


def main():
    """主函数"""
    print("🎯 交易执行系统")
    print("=" * 70)

    # 基于市场分析，制定交易计划
    print("\n📋 交易计划:")
    print("-" * 70)
    print("基于今日市场分析，发现两个投资机会:")
    print("1. 浦发银行 - 超跌反弹机会，安全边际高")
    print("2. 贵州茅台 - 震荡整理，成交量放大")
    print()
    print("采用稳健策略，分批建仓:")
    print("- 首次建仓仓位: 30%")
    print("- 单只股票仓位: 15%")
    print("- 总仓位: 30% (150,000元)")

    # 交易计划
    trades = [
        {
            "symbol": "SSE:600000",
            "name": "浦发银行",
            "amount": 75000,
            "reasoning": """
买入理由:
1. 近20日跌幅18.9%，存在超跌反弹机会
2. 价格接近支撑位(9.36元)，安全边际较高
3. 成交量放大(量比1.53)，资金关注度提升
4. 银行股估值较低，防御性较好
5. 震荡市场中，低估值蓝筹具有配置价值

技术面:
- 当前价格: 10.05元
- 支撑位: 9.36元
- 阻力位: 11.25元
- 目标价: 11.25元
- 预期收益: 11.9%
            """,
            "risk_factors": [
                "银行业整体承压，需关注不良率变化",
                "市场震荡，短期可能继续调整",
                "成交量虽放大但趋势尚未明确"
            ],
            "expected_return": 0.119
        },
        {
            "symbol": "SSE:600519",
            "name": "贵州茅台",
            "amount": 75000,
            "reasoning": """
买入理由:
1. 处于震荡整理阶段，价格相对稳定
2. 成交量放大(量比1.21)，市场关注度提升
3. 白酒龙头，品牌价值和护城河深厚
4. 长期配置价值显著
5. 防御性资产，适合震荡市配置

技术面:
- 当前价格: 1355.02元
- 支撑位: 1320.00元
- 阻力位: 1375.85元
- 目标价: 1375.85元
- 预期收益: 1.5%
            """,
            "risk_factors": [
                "白酒行业增速放缓",
                "高端消费需求波动",
                "价格处于相对高位"
            ],
            "expected_return": 0.015
        }
    ]

    # 执行交易
    success_count = 0
    for trade in trades:
        success = execute_buy_decision(
            symbol=trade["symbol"],
            name=trade["name"],
            amount=trade["amount"],
            reasoning=trade["reasoning"],
            risk_factors=trade["risk_factors"],
            expected_return=trade["expected_return"]
        )
        if success:
            success_count += 1

    # 总结
    print(f"\n{'='*70}")
    print(f"📊 交易总结")
    print(f"{'='*70}")
    print(f"计划交易: {len(trades)} 笔")
    print(f"成功交易: {success_count} 笔")

    # 显示账户状态
    account = get_default_simulation_account()
    if account:
        print(f"\n💼 账户状态:")
        print(f"   剩余现金: {account.get_cash():,.2f} 元")
        print(f"   持仓数量: {len(account.get_positions())}")

    print(f"\n{'='*70}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
