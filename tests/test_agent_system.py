#!/usr/bin/env python3
"""
测试基金经理Agent系统

简单的测试脚本，验证Agent系统的基本功能
"""

import sys
from pathlib import Path

# 添加src路径以便导入
sys.path.insert(0, str(Path(__file__).parent / "src"))

from datetime import datetime
from trading_os.agents.core.agent_interface import AgentContext
from trading_os.agents.roles.fund_manager import FundManager
from trading_os.paths import repo_root


def test_fund_manager():
    """测试基金经理功能"""
    print("🤖 测试基金经理Agent系统...")

    try:
        # 初始化基金经理
        fund_manager = FundManager(repo_root())
        print("✅ 基金经理初始化成功")

        # 构建测试上下文
        context = AgentContext(
            timestamp=datetime.now(),
            market_data={
                "prices": {
                    "AAPL": {"current_price": 150.0, "change_pct": 0.02},
                    "MSFT": {"current_price": 300.0, "change_pct": 0.015},
                    "JPM": {"current_price": 140.0, "change_pct": -0.005}
                },
                "market_volatility": 0.18,
                "market_liquidity_score": 0.75,
                "average_correlation": 0.6
            },
            portfolio_state={
                "positions": {
                    "AAPL": 0.25,
                    "MSFT": 0.20,
                    "JPM": 0.15
                },
                "cash_position": 0.40,
                "total_value": 1000000
            },
            risk_metrics={
                "individual_volatilities": {
                    "AAPL": 0.25,
                    "MSFT": 0.22,
                    "JPM": 0.20
                }
            },
            metadata={}
        )

        # 执行分析
        print("📊 执行市场分析...")
        outputs = fund_manager.process(context)
        print(f"✅ 分析完成，生成了 {len(outputs)} 个输出")

        # 显示结果
        for i, output in enumerate(outputs, 1):
            print(f"\n{i}. {output.agent_id} ({output.output_type})")
            print(f"   信心度: {output.confidence:.1%}")
            print(f"   时间: {output.timestamp.strftime('%H:%M:%S')}")

            # 显示关键内容
            if output.output_type == "analysis":
                if "market_phase" in output.content:
                    print(f"   市场阶段: {output.content['market_phase']}")
                if "overall_risk_level" in output.content:
                    print(f"   风险水平: {output.content['overall_risk_level']}")

            elif output.output_type == "decision":
                recommendations = output.content.get("investment_recommendations", [])
                print(f"   投资建议: {len(recommendations)} 条")
                for rec in recommendations[:3]:  # 显示前3条
                    print(f"     - {rec.symbol}: {rec.action} (信心: {rec.confidence:.1%})")

        # 生成董事会报告
        print("\n📋 生成董事会报告...")
        board_report = fund_manager.create_board_report(context)
        print("✅ 董事会报告生成完成")
        print(f"   报告日期: {board_report['report_date'][:10]}")
        print(f"   投资组合: {board_report['portfolio_summary']}")
        print(f"   市场观点: {board_report['market_assessment']}")

        print("\n🎉 所有测试通过！基金经理Agent系统运行正常。")
        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_fund_manager()
    sys.exit(0 if success else 1)