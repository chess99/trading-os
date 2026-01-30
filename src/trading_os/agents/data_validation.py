"""
数据验证模块

确保Agent系统只使用真实、有效的数据
"""

from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime, timedelta


class DataValidationError(Exception):
    """数据验证错误"""
    pass


class MarketDataValidator:
    """市场数据验证器"""

    @staticmethod
    def validate_market_data(market_data: Dict[str, Any]) -> None:
        """验证市场数据的完整性和有效性"""
        if not market_data:
            raise DataValidationError("市场数据为空")

        # 检查数据源标识
        data_source = market_data.get("data_source")
        if not data_source:
            raise DataValidationError("市场数据缺少数据源标识")

        # 禁止使用模拟数据
        forbidden_sources = ["fallback_mock", "fallback_simulation", "fallback_default"]
        if data_source in forbidden_sources:
            raise DataValidationError(
                f"检测到模拟数据源: {data_source}。"
                f"系统只能使用真实数据进行分析。"
                f"请检查数据湖状态或联系技术支持。"
            )

        # 检查价格数据
        prices = market_data.get("prices", {})
        if not prices:
            raise DataValidationError("市场数据中没有价格信息")

        # 验证价格数据的时效性
        for symbol, price_data in prices.items():
            timestamp_str = price_data.get("timestamp")
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    age = datetime.now().replace(tzinfo=timestamp.tzinfo) - timestamp
                    if age > timedelta(days=7):
                        raise DataValidationError(
                            f"{symbol} 数据过期（{age.days}天前）。"
                            f"请更新市场数据。"
                        )
                except ValueError:
                    raise DataValidationError(f"{symbol} 时间戳格式无效: {timestamp_str}")

    @staticmethod
    def validate_risk_metrics(risk_metrics: Dict[str, Any]) -> None:
        """验证风险指标数据"""
        if not risk_metrics:
            raise DataValidationError("风险指标数据为空")

        data_source = risk_metrics.get("data_source")
        if not data_source:
            raise DataValidationError("风险指标缺少数据源标识")

        # 禁止使用默认风险数据
        if data_source == "fallback_default":
            raise DataValidationError(
                "检测到默认风险数据。系统需要基于真实历史数据计算风险指标。"
            )

        volatilities = risk_metrics.get("individual_volatilities", {})
        if not volatilities:
            raise DataValidationError("缺少个股波动率数据")

    @staticmethod
    def validate_portfolio_state(portfolio_state: Dict[str, Any]) -> None:
        """验证投资组合状态"""
        if not portfolio_state:
            raise DataValidationError("投资组合状态数据为空")

        total_value = portfolio_state.get("total_value")
        if total_value is None or total_value <= 0:
            raise DataValidationError("投资组合总价值无效")

        positions = portfolio_state.get("positions", {})
        if not positions:
            raise DataValidationError("投资组合没有持仓信息")


class DataIntegrityChecker:
    """数据完整性检查器"""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root

    def check_data_lake_status(self) -> Dict[str, Any]:
        """检查数据湖状态"""
        try:
            from ..data.lake import LocalDataLake
            lake = LocalDataLake(self.repo_root / "data")

            # 检查主要股票数据 - A股
            required_symbols = ["SSE:600000", "SZSE:000001", "SSE:600036"]
            status = {
                "data_lake_available": True,
                "symbols_status": {},
                "total_symbols": 0,
                "last_update": None
            }

            for symbol in required_symbols:
                try:
                    bars = lake.query_bars(symbols=[symbol])
                    if not bars.empty:
                        latest_date = bars['ts'].max()
                        status["symbols_status"][symbol] = {
                            "available": True,
                            "records": len(bars),
                            "latest_date": str(latest_date)
                        }
                        status["total_symbols"] += 1

                        # 更新最后更新时间
                        if not status["last_update"] or latest_date > status["last_update"]:
                            status["last_update"] = latest_date
                    else:
                        status["symbols_status"][symbol] = {
                            "available": False,
                            "records": 0,
                            "latest_date": None
                        }
                except Exception as e:
                    status["symbols_status"][symbol] = {
                        "available": False,
                        "error": str(e)
                    }

            return status

        except Exception as e:
            return {
                "data_lake_available": False,
                "error": str(e),
                "symbols_status": {},
                "total_symbols": 0
            }

    def generate_data_status_report(self) -> str:
        """生成数据状态报告"""
        status = self.check_data_lake_status()

        report = ["📊 数据湖状态报告", "=" * 40]

        if status["data_lake_available"]:
            report.append(f"✅ 数据湖连接: 正常")
            report.append(f"📈 可用股票数量: {status['total_symbols']}")

            if status["last_update"]:
                report.append(f"🕐 最后更新: {status['last_update']}")

            report.append("\n📋 股票数据详情:")
            for symbol, info in status["symbols_status"].items():
                if info["available"]:
                    report.append(f"  ✅ {symbol}: {info['records']} 条记录")
                else:
                    error = info.get("error", "无数据")
                    report.append(f"  ❌ {symbol}: {error}")
        else:
            report.append(f"❌ 数据湖连接: 失败")
            report.append(f"错误: {status.get('error', '未知错误')}")

        report.append("\n💡 建议操作:")
        if status["total_symbols"] == 0:
            report.append("  1. 初始化数据湖: python -m trading_os lake-init")
            report.append("  2. 添加测试数据: python -m trading_os seed --exchange NASDAQ --ticker AAPL")
            report.append("  3. 或获取真实数据: python -m trading_os fetch-yf --exchange NASDAQ --ticker AAPL")
        elif status["total_symbols"] < 3:
            report.append("  1. 添加更多股票数据以提高分析准确性")
            report.append("  2. 确保至少有3只主要股票的数据")

        return "\n".join(report)


def ensure_data_quality(context) -> None:
    """确保数据质量的主要入口函数"""
    validator = MarketDataValidator()

    # 验证市场数据
    validator.validate_market_data(context.market_data)

    # 验证风险指标
    validator.validate_risk_metrics(context.risk_metrics)

    # 验证投资组合状态
    validator.validate_portfolio_state(context.portfolio_state)

    print("✅ 数据质量验证通过")