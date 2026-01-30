#!/usr/bin/env python3
"""
测试决策记录系统
"""

import sys
from pathlib import Path

# 添加项目路径
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))

from trading_os.decision import (
    get_default_decision_logger,
    DecisionType
)


def main():
    """主函数"""
    print("📝 测试决策记录系统")
    print("=" * 70)

    # 获取决策记录器
    logger = get_default_decision_logger()

    # 记录一个市场分析决策
    print("\n1. 记录市场分析决策...")
    decision = logger.log_decision(
        decision_type=DecisionType.MARKET_ANALYSIS,
        title="2026-01-30 A股市场分析",
        description="分析当前A股市场趋势和投资机会",
        reasoning="""
        基于以下分析:
        1. 上证指数近期呈现震荡上行趋势
        2. 成交量稳步放大，市场活跃度提升
        3. 科技板块表现强劲，有持续性
        4. 资金面宽松，政策环境友好

        结论: 当前市场处于震荡上行阶段，适合逢低布局优质成长股
        """,
        data_sources=[
            "数据湖 - A股日线数据",
            "akshare - 市场指数数据",
            "技术指标计算结果"
        ],
        market_data={
            "sh_index": 3200,
            "volume": "5000亿",
            "sector_leaders": ["科技", "新能源", "医药"]
        },
        risk_level="medium",
        risk_factors=[
            "国际市场波动风险",
            "政策变化风险",
            "估值偏高风险"
        ]
    )

    print(f"✅ 决策已记录: {decision.decision_id}")

    # 记录一个买入决策
    print("\n2. 记录买入决策...")
    buy_decision = logger.log_decision(
        decision_type=DecisionType.BUY_DECISION,
        title="买入贵州茅台(600519)",
        description="基于价值投资逻辑买入贵州茅台",
        reasoning="""
        买入理由:
        1. 公司基本面优秀，ROE持续保持高位
        2. 品牌价值强大，护城河深厚
        3. 当前价格处于合理估值区间
        4. 白酒行业景气度回升
        5. 长期配置价值显著
        """,
        data_sources=[
            "数据湖 - SSE:600519历史数据",
            "基本面分析 - 财务指标",
            "估值分析 - PE/PB"
        ],
        target_symbols=["SSE:600519"],
        target_amount=50000.0,
        expected_return=0.15,
        expected_risk=0.20,
        risk_level="low",
        risk_factors=[
            "白酒行业政策风险",
            "消费需求波动风险"
        ]
    )

    print(f"✅ 买入决策已记录: {buy_decision.decision_id}")

    # 生成决策报告
    print("\n3. 生成决策报告...")
    report = logger.generate_decision_report(buy_decision.decision_id)
    print(report)

    # 查询决策
    print("\n4. 查询最近决策...")
    recent_decisions = logger.query_decisions(limit=5)
    print(f"共有 {len(recent_decisions)} 条决策记录")

    for dec in recent_decisions:
        print(f"  - [{dec.timestamp.strftime('%Y-%m-%d %H:%M')}] "
              f"{dec.decision_type.value}: {dec.title} ({dec.status.value})")

    print("\n" + "=" * 70)
    print("✅ 决策记录系统测试完成")

    return 0


if __name__ == '__main__':
    sys.exit(main())
