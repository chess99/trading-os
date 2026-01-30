#!/usr/bin/env python3
"""
多因子策略回测脚本

使用历史数据回测多因子选股策略的有效性
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

import duckdb
import pandas as pd
import numpy as np

from trading_os.backtest.multi_factor_strategy import (
    BacktestConfig,
    FactorWeights,
    MultiFactorBacktest,
)
from trading_os.paths import repo_root
from trading_os.visualization.charts import create_backtest_report


def load_historical_data(
    db_path: Path,
    start_date: str,
    end_date: str,
    symbols: list = None
) -> Dict[datetime, Dict[str, Dict]]:
    """
    从数据湖加载历史数据

    Returns:
        {date: {symbol: {'price': x, 'factors': {...}}}}
    """
    print(f"📊 加载历史数据: {start_date} 到 {end_date}")

    conn = duckdb.connect(str(db_path), read_only=True)

    # 加载价格数据
    price_query = f"""
    SELECT
        ts as date,
        symbol,
        close as price,
        volume
    FROM bars
    WHERE ts >= '{start_date}' AND ts <= '{end_date}'
    """

    if symbols:
        symbols_str = "','".join(symbols)
        price_query += f" AND symbol IN ('{symbols_str}')"

    price_query += " ORDER BY date, symbol"

    df_prices = conn.execute(price_query).df()

    if df_prices.empty:
        print("⚠️ 没有找到价格数据")
        return {}

    print(f"✅ 加载了 {len(df_prices)} 条价格记录")

    # 转换为所需格式
    historical_data = {}

    for _, row in df_prices.iterrows():
        date = pd.to_datetime(row['date']).to_pydatetime()
        symbol = row['symbol']
        price = float(row['price'])
        volume = float(row['volume']) if pd.notna(row['volume']) else 0

        if date not in historical_data:
            historical_data[date] = {}

        if symbol not in historical_data[date]:
            historical_data[date][symbol] = {
                'price': price,
                'factors': {}
            }

        # 添加成交量因子
        historical_data[date][symbol]['factors']['volume'] = volume

    # 计算技术因子(动量、波动率)
    print("📈 计算技术因子...")

    for symbol in df_prices['symbol'].unique():
        symbol_data = df_prices[df_prices['symbol'] == symbol].sort_values('date')

        if len(symbol_data) < 30:
            continue

        # 计算动量(20日收益率)
        symbol_data['momentum'] = symbol_data['price'].pct_change(20)

        # 计算波动率(20日标准差)
        symbol_data['volatility'] = symbol_data['price'].pct_change().rolling(20).std()

        # 更新历史数据
        for _, row in symbol_data.iterrows():
            date = pd.to_datetime(row['date']).to_pydatetime()
            if date in historical_data and symbol in historical_data[date]:
                if pd.notna(row['momentum']):
                    historical_data[date][symbol]['factors']['momentum'] = float(row['momentum'])
                if pd.notna(row['volatility']):
                    historical_data[date][symbol]['factors']['volatility'] = float(row['volatility'])

    conn.close()

    print(f"✅ 处理完成,共 {len(historical_data)} 个交易日")

    return historical_data


def add_mock_fundamental_factors(historical_data: Dict):
    """
    添加模拟的基本面因子(用于演示)

    注意: 这是临时方案,未来应该从真实数据源获取
    """
    print("⚠️  添加模拟基本面因子(演示用)")

    np.random.seed(42)

    for date, stocks in historical_data.items():
        for symbol, data in stocks.items():
            # 模拟PE、PB、ROE、ROA
            # 使用固定种子确保可重复性
            hash_val = hash(symbol) % 10000

            data['factors']['pe'] = 10 + (hash_val % 30)  # PE 10-40
            data['factors']['pb'] = 1 + (hash_val % 8)  # PB 1-9
            data['factors']['roe'] = 0.05 + (hash_val % 20) / 100  # ROE 5%-25%
            data['factors']['roa'] = 0.02 + (hash_val % 10) / 100  # ROA 2%-12%


def print_backtest_results(results: Dict):
    """打印回测结果"""
    print("\n" + "=" * 70)
    print("📊 回测结果")
    print("=" * 70)

    print(f"\n💰 收益指标:")
    print(f"  总收益率:     {results['total_return']:>10.2%}")
    print(f"  年化收益率:   {results['annual_return']:>10.2%}")
    print(f"  最终权益:     {results['final_equity']:>10,.2f} 元")

    print(f"\n📉 风险指标:")
    print(f"  最大回撤:     {results['max_drawdown']:>10.2%}")
    print(f"  夏普比率:     {results['sharpe_ratio']:>10.2f}")

    print(f"\n📈 交易统计:")
    print(f"  总交易次数:   {results['total_trades']:>10}")
    print(f"  调仓次数:     {results['rebalance_count']:>10}")
    print(f"  胜率:         {results['win_rate']:>10.2%}")

    # 显示权益曲线
    if not results['equity_curve'].empty:
        print(f"\n📊 权益曲线 (前10天和后10天):")
        df = results['equity_curve']

        print("\n前10天:")
        print(df.head(10)[['date', 'cash', 'holdings', 'total', 'return']].to_string(index=False))

        print("\n后10天:")
        print(df.tail(10)[['date', 'cash', 'holdings', 'total', 'return']].to_string(index=False))

    # 显示交易记录
    if not results['trades'].empty:
        print(f"\n📋 交易记录 (前10笔):")
        trades_df = results['trades']
        print(trades_df.head(10).to_string(index=False))

    print("\n" + "=" * 70)


def main():
    """主函数"""
    print("🔄 多因子策略回测")
    print("=" * 70)

    # 配置
    root = repo_root()
    db_path = root / "data" / "lake.duckdb"

    if not db_path.exists():
        print(f"❌ 数据库不存在: {db_path}")
        print("请先运行 `python -m trading_os lake-init` 初始化数据湖")
        return

    # 回测时间范围(使用最近6个月的数据)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)

    # 加载数据
    historical_data = load_historical_data(
        db_path,
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d")
    )

    if not historical_data:
        print("❌ 没有可用的历史数据")
        return

    # 添加模拟基本面因子
    add_mock_fundamental_factors(historical_data)

    # 创建回测配置
    config = BacktestConfig(
        initial_cash=500_000.0,
        top_n=10,
        rebalance_days=30,
        position_limit=0.20,
        total_position=0.60,
        fee_rate=0.0003
    )

    # 创建回测引擎
    print("\n🚀 开始回测...")
    backtest = MultiFactorBacktest(config)

    # 运行回测
    try:
        results = backtest.run(historical_data)

        # 打印结果
        print_backtest_results(results)

        # 保存结果
        output_dir = project_root / "data" / "backtest_results"
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 保存权益曲线
        equity_file = output_dir / f"{timestamp}_equity_curve.csv"
        results['equity_curve'].to_csv(equity_file, index=False)
        print(f"\n💾 权益曲线已保存: {equity_file}")

        # 保存交易记录
        if not results['trades'].empty:
            trades_file = output_dir / f"{timestamp}_trades.csv"
            results['trades'].to_csv(trades_file, index=False)
            print(f"💾 交易记录已保存: {trades_file}")

        # 生成可视化报告
        print(f"\n📊 生成可视化报告...")
        try:
            create_backtest_report(
                results,
                output_dir,
                report_name=timestamp
            )
        except Exception as e:
            print(f"⚠️  生成可视化报告失败: {e}")
            print("提示: 需要安装matplotlib: pip install matplotlib")

        print("\n✅ 回测完成!")

    except Exception as e:
        print(f"\n❌ 回测失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
