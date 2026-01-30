#!/usr/bin/env python3
"""
每日市场分析

分析A股市场并生成投资建议
"""

import sys
from pathlib import Path

# 添加项目路径
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))

from trading_os.analysis import get_default_market_analyzer
from trading_os.decision import get_default_decision_logger, DecisionType


def main():
    """主函数"""
    print("📊 开始每日市场分析")
    print("=" * 70)

    # 获取市场分析器
    analyzer = get_default_market_analyzer()

    # 执行市场分析
    print("\n🔍 正在分析市场...")
    report = analyzer.analyze_market(days=60)

    # 生成报告文本
    report_text = analyzer.generate_report_text(report)
    print("\n" + report_text)

    # 记录决策
    print("\n📝 记录分析决策...")
    decision_logger = get_default_decision_logger()

    decision = decision_logger.log_decision(
        decision_type=DecisionType.MARKET_ANALYSIS,
        title=f"{report.timestamp.strftime('%Y-%m-%d')} 市场分析",
        description=f"市场状态: {report.market_status}, 市场情绪: {report.market_sentiment}",
        reasoning="\n".join(report.recommendations),
        data_sources=[
            "数据湖 - A股历史数据",
            "技术指标计算",
            "趋势分析"
        ],
        market_data={
            "market_status": report.market_status,
            "market_sentiment": report.market_sentiment,
            "opportunities_count": len(report.opportunities)
        },
        analysis_results={
            "top_opportunities": [
                {
                    "symbol": opp.symbol,
                    "name": opp.name,
                    "score": opp.score,
                    "expected_return": opp.expected_return
                }
                for opp in report.opportunities[:3]
            ]
        },
        risk_level="medium",
        risk_factors=report.risk_factors
    )

    print(f"✅ 决策已记录: {decision.decision_id}")

    # 保存报告到文件
    report_file = Path("data/reports") / f"market_analysis_{report.timestamp.strftime('%Y%m%d')}.txt"
    report_file.parent.mkdir(parents=True, exist_ok=True)

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_text)

    print(f"\n💾 报告已保存: {report_file}")

    # 如果有高分机会，提示
    if report.opportunities:
        top_opp = report.opportunities[0]
        if top_opp.score >= 70:
            print(f"\n🎯 发现高质量机会: {top_opp.name}")
            print(f"   评分: {top_opp.score:.1f}")
            print(f"   预期收益: {top_opp.expected_return:.1%}")
            print(f"   建议: 可以考虑建仓")

    print("\n" + "=" * 70)
    print("✅ 市场分析完成")

    return 0


if __name__ == '__main__':
    sys.exit(main())
