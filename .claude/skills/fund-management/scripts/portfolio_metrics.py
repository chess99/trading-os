#!/usr/bin/env python3
"""
投资组合指标计算脚本

计算详细的投资组合风险和收益指标
"""

import sys
from pathlib import Path
import json
import numpy as np
from datetime import datetime, timedelta

# 添加项目路径
repo_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(repo_root / "src"))


def calculate_portfolio_metrics(positions, market_data=None):
    """计算投资组合指标"""
    if not positions:
        return {"error": "没有持仓数据"}

    # 基础指标
    total_positions = len(positions)
    largest_position = max(positions.values()) if positions else 0
    cash_position = 1.0 - sum(positions.values())

    # 集中度指标
    sorted_weights = sorted(positions.values(), reverse=True)
    top_3_concentration = sum(sorted_weights[:3])
    top_5_concentration = sum(sorted_weights[:5])

    # 多样化指标
    herfindahl_index = sum(w**2 for w in positions.values())
    effective_positions = 1 / herfindahl_index if herfindahl_index > 0 else 0

    # 风险指标（简化计算）
    avg_volatility = 0.20  # 假设平均波动率20%
    portfolio_volatility = np.sqrt(sum(w**2 * avg_volatility**2 for w in positions.values()))

    # VaR计算（95%置信度）
    var_95 = portfolio_volatility * 1.645  # 正态分布假设

    # 风险等级评估
    risk_score = 0
    if largest_position > 0.25:
        risk_score += 2
    if top_3_concentration > 0.60:
        risk_score += 1
    if portfolio_volatility > 0.25:
        risk_score += 2
    if cash_position < 0.05:
        risk_score += 1

    risk_level = "high" if risk_score >= 4 else "medium" if risk_score >= 2 else "low"

    return {
        "基础指标": {
            "持仓数量": total_positions,
            "最大单一仓位": f"{largest_position:.1%}",
            "现金仓位": f"{cash_position:.1%}",
            "总权重": f"{sum(positions.values()):.1%}"
        },
        "集中度指标": {
            "前3大仓位集中度": f"{top_3_concentration:.1%}",
            "前5大仓位集中度": f"{top_5_concentration:.1%}",
            "赫芬达尔指数": f"{herfindahl_index:.3f}",
            "有效持仓数": f"{effective_positions:.1f}"
        },
        "风险指标": {
            "组合波动率": f"{portfolio_volatility:.1%}",
            "VaR_95%": f"{var_95:.1%}",
            "风险评分": risk_score,
            "风险等级": risk_level
        },
        "详细持仓": {symbol: f"{weight:.1%}" for symbol, weight in positions.items()}
    }


def main():
    """主函数"""
    try:
        print("📊 计算投资组合指标...")

        # 模拟当前投资组合（实际应该从数据库获取）
        mock_positions = {
            "AAPL": 0.25,
            "MSFT": 0.20,
            "GOOGL": 0.15,
            "JPM": 0.10,
            "JNJ": 0.08
        }

        # 计算指标
        metrics = calculate_portfolio_metrics(mock_positions)

        # 输出结果
        print("\n" + "="*50)
        print("📈 投资组合指标报告")
        print("="*50)

        for category, indicators in metrics.items():
            if category != "详细持仓":
                print(f"\n📋 {category}:")
                for name, value in indicators.items():
                    print(f"  {name}: {value}")

        print(f"\n💼 详细持仓:")
        for symbol, weight in metrics["详细持仓"].items():
            print(f"  {symbol}: {weight}")

        # 风险建议
        risk_level = metrics["风险指标"]["风险等级"]
        print(f"\n💡 风险建议:")

        if risk_level == "high":
            print("  ⚠️ 高风险组合，建议:")
            print("    - 减少集中仓位")
            print("    - 增加现金缓冲")
            print("    - 考虑止损措施")
        elif risk_level == "medium":
            print("  📊 中等风险组合，建议:")
            print("    - 监控仓位变化")
            print("    - 适度分散投资")
            print("    - 保持风险意识")
        else:
            print("  ✅ 低风险组合，建议:")
            print("    - 保持当前配置")
            print("    - 寻找投资机会")
            print("    - 适度增加风险敞口")

        # 保存结果
        output_file = repo_root / "artifacts" / "metrics" / f"portfolio_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "positions": mock_positions,
                "metrics": metrics
            }, f, indent=2, ensure_ascii=False)

        print(f"\n💾 指标已保存: {output_file}")
        print("\n✅ 指标计算完成")

        return 0

    except Exception as e:
        print(f"❌ 计算失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())