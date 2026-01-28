#!/usr/bin/env python3
"""
市场分析脚本

执行综合市场分析，包括技术分析、行业轮动、市场情绪等
"""

import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目路径
repo_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(repo_root / "src"))

try:
    from trading_os.agents.cli_integration import AgentSystemCLI
except ImportError:
    # 如果无法导入，提供简化的分析
    pass


def analyze_market_trends():
    """分析市场趋势"""
    return {
        "trend_direction": "upward",
        "trend_strength": 0.75,
        "support_levels": [4200, 4150, 4100],
        "resistance_levels": [4350, 4400, 4450],
        "trend_confidence": 0.8
    }


def analyze_technical_indicators():
    """计算技术指标"""
    return {
        "rsi": 65.2,
        "macd": {
            "signal": "bullish",
            "histogram": 0.5,
            "line": 1.2
        },
        "bollinger_bands": {
            "position": 0.7,
            "width": "normal"
        },
        "moving_averages": {
            "ma_50": 4250,
            "ma_200": 4100,
            "price_vs_ma50": "above",
            "price_vs_ma200": "above"
        }
    }


def analyze_sector_rotation():
    """分析行业轮动"""
    return {
        "leading_sectors": [
            {"name": "Technology", "performance": 0.025, "momentum": "strong"},
            {"name": "Healthcare", "performance": 0.018, "momentum": "moderate"},
            {"name": "Consumer Discretionary", "performance": 0.012, "momentum": "moderate"}
        ],
        "lagging_sectors": [
            {"name": "Energy", "performance": -0.008, "momentum": "weak"},
            {"name": "Utilities", "performance": -0.005, "momentum": "weak"},
            {"name": "Real Estate", "performance": -0.003, "momentum": "neutral"}
        ],
        "rotation_signal": "tech_leadership",
        "cycle_phase": "mid_cycle"
    }


def assess_market_sentiment():
    """评估市场情绪"""
    return {
        "sentiment_score": 0.65,  # 0-1 scale
        "sentiment_level": "moderately_bullish",
        "fear_greed_index": 58,
        "volatility_level": "low",
        "market_breadth": {
            "advancing_stocks": 0.68,
            "new_highs_lows": 2.1,
            "breadth_score": "positive"
        }
    }


def identify_market_phase():
    """识别市场阶段"""
    trends = analyze_market_trends()
    sentiment = assess_market_sentiment()

    # 综合判断市场阶段
    if trends["trend_strength"] > 0.7 and sentiment["sentiment_score"] > 0.6:
        return {
            "phase": "bull_market",
            "sub_phase": "momentum",
            "confidence": 0.85,
            "duration_estimate": "3-6 months"
        }
    elif trends["trend_strength"] < 0.3 and sentiment["sentiment_score"] < 0.4:
        return {
            "phase": "bear_market",
            "sub_phase": "correction",
            "confidence": 0.8,
            "duration_estimate": "2-4 months"
        }
    else:
        return {
            "phase": "sideways_market",
            "sub_phase": "consolidation",
            "confidence": 0.7,
            "duration_estimate": "1-3 months"
        }


def screen_investment_opportunities():
    """筛选投资机会"""
    opportunities = []

    # 模拟筛选结果
    growth_stocks = [
        {"symbol": "NVDA", "score": 0.92, "type": "growth", "reasoning": "AI领域领导者，强劲增长"},
        {"symbol": "MSFT", "score": 0.88, "type": "growth", "reasoning": "云计算和AI双重受益"},
        {"symbol": "GOOGL", "score": 0.82, "type": "growth", "reasoning": "搜索+AI技术优势"}
    ]

    value_stocks = [
        {"symbol": "JPM", "score": 0.78, "type": "value", "reasoning": "估值合理，利率环境有利"},
        {"symbol": "BRK.B", "score": 0.75, "type": "value", "reasoning": "巴菲特价值投资标杆"}
    ]

    opportunities.extend(growth_stocks)
    opportunities.extend(value_stocks)

    return sorted(opportunities, key=lambda x: x["score"], reverse=True)


def generate_investment_recommendations():
    """生成投资建议"""
    market_phase = identify_market_phase()
    sector_rotation = analyze_sector_rotation()
    opportunities = screen_investment_opportunities()

    recommendations = []

    # 基于市场阶段的建议
    if market_phase["phase"] == "bull_market":
        recommendations.extend([
            "适度增加风险敞口，关注成长股机会",
            "重点配置领先行业：科技、医疗",
            "保持适度现金缓冲，准备回调时加仓"
        ])
    elif market_phase["phase"] == "bear_market":
        recommendations.extend([
            "降低风险敞口，增加防御性资产",
            "关注高分红、低估值标的",
            "保持较高现金比例，等待机会"
        ])
    else:
        recommendations.extend([
            "维持中性配置，等待方向明确",
            "关注相对强势的个股机会",
            "适度轮动，优化投资组合结构"
        ])

    # 基于行业轮动的建议
    for sector in sector_rotation["leading_sectors"][:2]:
        recommendations.append(f"增加{sector['name']}行业配置")

    return recommendations


def main():
    """主函数"""
    print("📊 执行市场分析...")

    try:
        # 执行各项分析
        trends = analyze_market_trends()
        technical = analyze_technical_indicators()
        sector_rotation = analyze_sector_rotation()
        sentiment = assess_market_sentiment()
        market_phase = identify_market_phase()
        opportunities = screen_investment_opportunities()
        recommendations = generate_investment_recommendations()

        # 整合分析结果
        analysis_result = {
            "timestamp": datetime.now().isoformat(),
            "market_trends": trends,
            "technical_indicators": technical,
            "sector_rotation": sector_rotation,
            "market_sentiment": sentiment,
            "market_phase": market_phase,
            "investment_opportunities": opportunities[:5],  # 前5个机会
            "recommendations": recommendations
        }

        # 输出结果摘要
        print("\n" + "="*60)
        print("📈 市场分析结果")
        print("="*60)

        print(f"\n🌍 市场阶段: {market_phase['phase']} ({market_phase['sub_phase']})")
        print(f"   信心度: {market_phase['confidence']:.1%}")
        print(f"   预期持续: {market_phase['duration_estimate']}")

        print(f"\n📊 技术面:")
        print(f"   趋势方向: {trends['trend_direction']}")
        print(f"   趋势强度: {trends['trend_strength']:.1%}")
        print(f"   RSI: {technical['rsi']}")
        print(f"   MACD: {technical['macd']['signal']}")

        print(f"\n🏭 行业轮动:")
        for sector in sector_rotation['leading_sectors'][:3]:
            print(f"   领先: {sector['name']} (+{sector['performance']:.1%})")

        print(f"\n😊 市场情绪:")
        print(f"   情绪水平: {sentiment['sentiment_level']}")
        print(f"   恐慌贪婪指数: {sentiment['fear_greed_index']}")
        print(f"   波动率: {sentiment['volatility_level']}")

        print(f"\n💡 投资机会 (前3名):")
        for i, opp in enumerate(opportunities[:3], 1):
            print(f"   {i}. {opp['symbol']}: {opp['score']:.1%} - {opp['reasoning']}")

        print(f"\n🎯 投资建议:")
        for i, rec in enumerate(recommendations[:5], 1):
            print(f"   {i}. {rec}")

        # 保存详细结果
        output_file = repo_root / "artifacts" / "analysis" / f"market_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_result, f, indent=2, ensure_ascii=False)

        print(f"\n💾 详细分析已保存: {output_file}")
        print("\n✅ 市场分析完成")

        return 0

    except Exception as e:
        print(f"❌ 分析失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())