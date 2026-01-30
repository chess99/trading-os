"""
Agent系统CLI集成

将Agent系统集成到现有的CLI中
"""

from datetime import datetime
from typing import Dict, Any
from pathlib import Path
import numpy as np

from .core.agent_interface import AgentContext
from .core.message_types import PortfolioSnapshot
from .roles.fund_manager import FundManager
from .data_validation import ensure_data_quality, DataIntegrityChecker


class AgentSystemCLI:
    """Agent系统CLI接口"""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.fund_manager = FundManager(repo_root)

    def run_daily_analysis(self) -> Dict[str, Any]:
        """运行日常分析"""
        print("🤖 启动基金经理AI分析...")

        # 构建分析上下文
        context = self._build_analysis_context()

        # 执行分析
        outputs = self.fund_manager.process(context)

        # 格式化输出
        analysis_result = self._format_analysis_results(outputs)

        print("✅ 分析完成")
        return analysis_result

    def generate_board_report(self) -> Dict[str, Any]:
        """生成董事会报告"""
        print("📊 生成董事会报告...")

        context = self._build_analysis_context()
        report = self.fund_manager.create_board_report(context)

        print("✅ 报告生成完成")
        return report

    def get_investment_recommendations(self) -> Dict[str, Any]:
        """获取投资建议"""
        print("💡 生成投资建议...")

        context = self._build_analysis_context()
        outputs = self.fund_manager.process(context)

        # 提取投资建议
        recommendations = []
        for output in outputs:
            if output.output_type == "decision":
                content = output.content
                if "investment_recommendations" in content:
                    recommendations.extend(content["investment_recommendations"])

        print(f"✅ 生成了 {len(recommendations)} 条投资建议")
        return {"recommendations": recommendations}

    def assess_portfolio_risk(self) -> Dict[str, Any]:
        """评估投资组合风险"""
        print("⚠️  评估投资组合风险...")

        context = self._build_analysis_context()
        outputs = self.fund_manager.process(context)

        # 提取风险评估
        risk_assessment = None
        for output in outputs:
            if output.agent_id == "portfolio_risk_assessment":
                risk_assessment = output.content
                break

        if risk_assessment:
            print(f"✅ 风险评估完成，整体风险水平: {risk_assessment.get('overall_risk_level', '未知')}")
        else:
            print("❌ 风险评估失败")

        return {"risk_assessment": risk_assessment}

    def _build_analysis_context(self) -> AgentContext:
        """构建分析上下文"""
        try:
            # 从数据湖获取真实市场数据
            from ..data.lake import LocalDataLake
            lake = LocalDataLake(self.repo_root / "data")

            # 获取主要股票的最新价格 - 切换到A股
            symbols = ["SSE:600000", "SZSE:000001", "SSE:600036"]  # 浦发银行、平安银行、招商银行
            market_data = {"prices": {}}

            for symbol in symbols:
                try:
                    bars = lake.query_bars(symbols=[symbol])
                    if not bars.empty:
                        latest = bars.iloc[-1]
                        prev_close = bars.iloc[-2]['close'] if len(bars) > 1 else latest['close']
                        change_pct = (latest['close'] - prev_close) / prev_close

                        ticker = symbol.split(':')[1]
                        market_data["prices"][ticker] = {
                            "current_price": float(latest['close']),
                            "change_pct": float(change_pct),
                            "volume": float(latest['volume']),
                            "timestamp": str(latest['ts'])
                        }
                except Exception as e:
                    print(f"警告: 无法获取 {symbol} 数据: {e}")

            # 计算市场指标
            if market_data["prices"]:
                prices = [data["current_price"] for data in market_data["prices"].values()]
                changes = [data["change_pct"] for data in market_data["prices"].values()]

                market_data.update({
                    "market_volatility": float(np.std(changes)) if len(changes) > 1 else 0.02,
                    "market_liquidity_score": 0.8,  # 可以基于成交量计算
                    "average_correlation": 0.6,  # 可以基于历史数据计算
                    "market_trend": "bullish" if np.mean(changes) > 0 else "bearish",
                    "data_source": "real_data_lake"
                })
            else:
                # 如果没有数据，明确失败
                print("❌ 错误: 数据湖中没有找到任何市场数据")
                print("请先添加数据：")
                print("  python -m trading_os seed --exchange NASDAQ --ticker AAPL")
                print("  python -m trading_os seed --exchange NASDAQ --ticker MSFT")
                print("  python -m trading_os seed --exchange NASDAQ --ticker GOOGL")
                raise RuntimeError("数据湖为空，无法进行市场分析")

        except Exception as e:
            print(f"❌ 错误: 无法从数据湖获取市场数据")
            print(f"详细错误: {e}")
            print("请检查：")
            print("1. 数据湖是否已初始化：python -m trading_os lake-init")
            print("2. 是否有数据：python -m trading_os query-bars --symbols NASDAQ:AAPL")
            print("3. 如需添加数据：python -m trading_os seed --exchange NASDAQ --ticker AAPL")
            raise RuntimeError(f"市场数据获取失败，无法进行分析: {e}") from e

        # 模拟投资组合状态（实际应该从投资组合管理系统获取）
        mock_portfolio = {
            "positions": {
                "600000": 0.25,  # 浦发银行
                "000001": 0.20,  # 平安银行
                "600036": 0.15   # 招商银行
            },
            "cash_position": 0.40,
            "total_value": 1000000
        }

        # 计算真实的风险指标
        try:
            # 基于真实数据计算波动率
            risk_metrics = {"individual_volatilities": {}}

            for symbol in ["SSE:600000", "SZSE:000001", "SSE:600036"]:
                try:
                    bars = lake.query_bars(symbols=[symbol])
                    if len(bars) > 10:  # 需要足够的数据点
                        returns = bars['close'].pct_change().dropna()
                        volatility = float(returns.std() * np.sqrt(252))  # 年化波动率
                        ticker = symbol.split(':')[1]
                        risk_metrics["individual_volatilities"][ticker] = volatility
                except:
                    pass

            # 如果没有计算出波动率，明确失败
            if not risk_metrics["individual_volatilities"]:
                print("❌ 错误: 无法计算任何股票的波动率")
                print("请确保数据湖中有足够的历史数据（至少10个交易日）")
                raise RuntimeError("风险指标计算失败：数据不足")

            risk_metrics["data_source"] = "calculated_from_real_data"

        except Exception as e:
            print(f"❌ 错误: 无法计算风险指标: {e}")
            print("风险计算需要足够的历史数据")
            raise RuntimeError(f"风险指标计算失败: {e}") from e

        context = AgentContext(
            timestamp=datetime.now(),
            market_data=market_data,
            portfolio_state=mock_portfolio,
            risk_metrics=risk_metrics,
            metadata={"data_integration_status": "enhanced_with_real_data"}
        )

        # 验证数据质量
        try:
            ensure_data_quality(context)
        except Exception as e:
            # 提供详细的诊断信息
            checker = DataIntegrityChecker(self.repo_root)
            report = checker.generate_data_status_report()
            print(report)
            raise RuntimeError(f"数据质量验证失败: {e}") from e

        return context

    def _format_analysis_results(self, outputs: list) -> Dict[str, Any]:
        """格式化分析结果"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "total_outputs": len(outputs),
            "market_analysis": None,
            "risk_assessment": None,
            "investment_decisions": None
        }

        for output in outputs:
            if output.agent_id == "market_trend_analysis":
                result["market_analysis"] = {
                    "market_phase": output.content.get("market_phase"),
                    "sentiment_score": output.content.get("sentiment_score"),
                    "confidence": output.confidence
                }
            elif output.agent_id == "portfolio_risk_assessment":
                result["risk_assessment"] = {
                    "overall_risk_level": output.content.get("overall_risk_level"),
                    "risk_alerts": len(output.content.get("risk_alerts", [])),
                    "confidence": output.confidence
                }
            elif output.output_type == "decision":
                result["investment_decisions"] = {
                    "recommendations_count": len(output.content.get("investment_recommendations", [])),
                    "reasoning": output.content.get("reasoning"),
                    "confidence": output.confidence
                }

        return result

    def print_analysis_summary(self, analysis_result: Dict[str, Any]):
        """打印分析摘要"""
        print("\n" + "="*50)
        print("📈 基金经理AI分析报告")
        print("="*50)

        # 市场分析
        market = analysis_result.get("market_analysis")
        if market:
            print(f"\n🌍 市场分析:")
            print(f"  市场阶段: {market.get('market_phase', '未知')}")
            print(f"  情绪指数: {market.get('sentiment_score', 0):.2f}")
            print(f"  分析信心: {market.get('confidence', 0):.1%}")

        # 风险评估
        risk = analysis_result.get("risk_assessment")
        if risk:
            print(f"\n⚠️  风险评估:")
            print(f"  风险水平: {risk.get('overall_risk_level', '未知')}")
            print(f"  风险警报: {risk.get('risk_alerts', 0)} 个")
            print(f"  评估信心: {risk.get('confidence', 0):.1%}")

        # 投资决策
        decisions = analysis_result.get("investment_decisions")
        if decisions:
            print(f"\n💡 投资决策:")
            print(f"  投资建议: {decisions.get('recommendations_count', 0)} 条")
            print(f"  决策推理: {decisions.get('reasoning', '无')}")
            print(f"  决策信心: {decisions.get('confidence', 0):.1%}")

        print("\n" + "="*50)


def add_agent_commands(cli_parser):
    """向现有CLI添加Agent相关命令"""

    # 添加agent子命令组
    agent_parser = cli_parser.add_parser('agent', help='基金经理AI系统')
    agent_subparsers = agent_parser.add_subparsers(dest='agent_action', help='Agent操作')

    # 日常分析命令
    daily_parser = agent_subparsers.add_parser('daily', help='运行日常分析')

    # 董事会报告命令
    board_parser = agent_subparsers.add_parser('board-report', help='生成董事会报告')

    # 投资建议命令
    recommend_parser = agent_subparsers.add_parser('recommend', help='获取投资建议')

    # 风险评估命令
    risk_parser = agent_subparsers.add_parser('risk', help='评估投资组合风险')

    # 数据状态检查命令
    status_parser = agent_subparsers.add_parser('status', help='检查数据湖状态')

    return agent_parser


def handle_agent_command(args, repo_root: Path):
    """处理Agent相关命令"""
    agent_cli = AgentSystemCLI(repo_root)

    if args.agent_action == 'daily':
        result = agent_cli.run_daily_analysis()
        agent_cli.print_analysis_summary(result)

    elif args.agent_action == 'board-report':
        report = agent_cli.generate_board_report()
        print("\n📊 董事会报告:")
        print(f"报告日期: {report['report_date']}")
        print(f"投资组合: {report['portfolio_summary']}")
        print(f"市场观点: {report['market_assessment']}")
        print(f"风险状况: {report['risk_analysis']}")
        print(f"展望: {report['outlook']}")

    elif args.agent_action == 'recommend':
        recommendations = agent_cli.get_investment_recommendations()
        print(f"\n💡 投资建议 ({len(recommendations['recommendations'])} 条):")
        for i, rec in enumerate(recommendations['recommendations'], 1):
            print(f"{i}. {rec.symbol}: {rec.action} (目标: {rec.target_allocation:.1%})")
            print(f"   推理: {rec.reasoning}")
            print(f"   信心: {rec.confidence:.1%}, 风险: {rec.risk_level}")

    elif args.agent_action == 'risk':
        risk_result = agent_cli.assess_portfolio_risk()
        if risk_result['risk_assessment']:
            risk = risk_result['risk_assessment']
            print(f"\n⚠️  风险评估结果:")
            print(f"整体风险: {risk.get('overall_risk_level', '未知')}")
            print(f"风险指标: {risk.get('risk_metrics', {})}")
            alerts = risk.get('risk_alerts', [])
            if alerts:
                print(f"风险警报 ({len(alerts)} 个):")
                for alert in alerts:
                    print(f"  - {alert.description} (严重性: {alert.severity})")

    elif args.agent_action == 'status':
        checker = DataIntegrityChecker(repo_root)
        report = checker.generate_data_status_report()
        print(report)

    else:
        print("请指定有效的agent操作: daily, board-report, recommend, risk, status")