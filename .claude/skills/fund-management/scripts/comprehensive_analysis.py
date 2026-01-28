#!/usr/bin/env python3
"""
综合分析脚本

执行完整的基金管理分析流程，输出结构化结果
"""

import sys
from pathlib import Path
import json
from datetime import datetime

# 添加项目路径
repo_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(repo_root / "src"))

from trading_os.agents.cli_integration import AgentSystemCLI


def main():
    """执行综合分析"""
    try:
        print("🤖 启动综合基金管理分析...")

        # 初始化系统
        agent_cli = AgentSystemCLI(repo_root)

        # 执行分析
        analysis_result = agent_cli.run_daily_analysis()

        # 生成投资建议
        recommendations = agent_cli.get_investment_recommendations()

        # 评估风险
        risk_assessment = agent_cli.assess_portfolio_risk()

        # 生成董事会报告
        board_report = agent_cli.generate_board_report()

        # 整合结果
        comprehensive_result = {
            "timestamp": datetime.now().isoformat(),
            "analysis": analysis_result,
            "recommendations": recommendations,
            "risk_assessment": risk_assessment,
            "board_report": board_report
        }

        # 输出结构化结果（Claude可以解析）
        print("\n" + "="*60)
        print("📊 综合分析结果")
        print("="*60)

        # 市场分析摘要
        market = analysis_result.get("market_analysis", {})
        print(f"\n🌍 市场分析:")
        print(f"  市场阶段: {market.get('market_phase', '未知')}")
        print(f"  分析信心: {market.get('confidence', 0):.1%}")

        # 投资建议摘要
        recs = recommendations.get("recommendations", [])
        print(f"\n💡 投资建议 ({len(recs)} 条):")
        for i, rec in enumerate(recs[:3], 1):  # 显示前3条
            print(f"  {i}. {rec.symbol}: {rec.action} (目标: {rec.target_allocation:.1%})")

        # 风险评估摘要
        risk = risk_assessment.get("risk_assessment", {})
        if risk:
            print(f"\n⚠️ 风险评估:")
            print(f"  整体风险: {risk.get('overall_risk_level', '未知')}")
            alerts = risk.get('risk_alerts', [])
            print(f"  风险警报: {len(alerts)} 个")

        print(f"\n📋 董事会报告已生成")
        print(f"📅 分析时间: {comprehensive_result['timestamp'][:19]}")

        # 保存详细结果到文件（供进一步分析）
        output_file = repo_root / "artifacts" / "analysis" / f"comprehensive_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(comprehensive_result, f, indent=2, ensure_ascii=False, default=str)

        print(f"\n💾 详细结果已保存: {output_file}")
        print("\n✅ 综合分析完成")

        return 0

    except Exception as e:
        print(f"❌ 分析失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())