#!/usr/bin/env python3
"""
定投回测工具 (Dollar Cost Averaging Backtest)

功能:
1. 支持多种定投频率: 每日/每周/每月
2. 支持任意标的: 股票/ETF/指数
3. 完整的回测指标: 收益率/年化/最大回撤/夏普比率
4. 自动获取数据(本地优先,不足则在线获取)
5. 可视化结果
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import argparse

# 添加项目路径
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))

# 配置代理
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7897'
os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7897'

import pandas as pd
import numpy as np


class DCABacktest:
    """定投回测引擎"""

    def __init__(
        self,
        symbol: str,
        start_date: str,
        end_date: Optional[str] = None,
        frequency: str = 'monthly',  # daily/weekly/monthly
        annual_investment: float = 120000,  # 年投入总额
        data_source: str = 'auto'  # auto/local/online
    ):
        """
        初始化定投回测

        Args:
            symbol: 标的代码 (如 'SSE:600000', '588000.SH', '科创50')
            start_date: 起始日期 'YYYY-MM-DD'
            end_date: 结束日期 (默认今天)
            frequency: 定投频率 daily/weekly/monthly
            annual_investment: 年投入总额
            data_source: 数据源 auto/local/online
        """
        self.symbol = self._normalize_symbol(symbol)
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date) if end_date else pd.Timestamp.now()
        self.frequency = frequency
        self.annual_investment = annual_investment
        self.data_source = data_source

        # 计算每次定投金额
        if frequency == 'daily':
            # 假设一年250个交易日
            self.investment_per_period = annual_investment / 250
        elif frequency == 'weekly':
            # 一年52周
            self.investment_per_period = annual_investment / 52
        else:  # monthly
            # 一年12个月
            self.investment_per_period = annual_investment / 12

        print(f"📊 定投回测配置:")
        print(f"  标的: {self.symbol}")
        print(f"  周期: {self.start_date.date()} 至 {self.end_date.date()}")
        print(f"  频率: {frequency}")
        print(f"  年投入: {annual_investment:,.0f}元")
        print(f"  每次投入: {self.investment_per_period:,.2f}元")
        print()

    def _normalize_symbol(self, symbol: str) -> str:
        """标准化股票代码"""
        # 如果是中文名称或缩写,需要转换
        # TODO: 实现名称到代码的映射
        if ':' in symbol:
            return symbol

        # 处理常见格式
        if symbol.endswith('.SH'):
            code = symbol.replace('.SH', '')
            return f'SSE:{code}'
        elif symbol.endswith('.SZ'):
            code = symbol.replace('.SZ', '')
            return f'SZSE:{code}'
        elif len(symbol) == 6 and symbol.isdigit():
            # 6位数字,判断交易所
            if symbol.startswith('6'):
                return f'SSE:{symbol}'
            else:
                return f'SZSE:{symbol}'

        return symbol

    def get_price_data(self) -> pd.DataFrame:
        """获取价格数据"""
        print("📈 获取价格数据...")

        # 先尝试从本地数据湖获取
        if self.data_source in ['auto', 'local']:
            try:
                df = self._get_local_data()
                if df is not None and len(df) > 0:
                    print(f"  ✅ 从本地获取 {len(df)} 条数据")
                    return df
            except Exception as e:
                print(f"  ⚠️  本地数据获取失败: {e}")

        # 在线获取
        if self.data_source in ['auto', 'online']:
            try:
                df = self._get_online_data()
                if df is not None and len(df) > 0:
                    print(f"  ✅ 从在线获取 {len(df)} 条数据")
                    return df
            except Exception as e:
                print(f"  ❌ 在线数据获取失败: {e}")
                raise

        raise RuntimeError(f"无法获取 {self.symbol} 的价格数据")

    def _get_local_data(self) -> Optional[pd.DataFrame]:
        """从本地数据湖获取数据"""
        import duckdb

        db_path = repo_root / 'data' / 'lake.duckdb'
        if not db_path.exists():
            return None

        conn = duckdb.connect(str(db_path), read_only=True)

        query = f"""
        SELECT ts as date, close as price
        FROM bars
        WHERE symbol = '{self.symbol}'
          AND ts >= '{self.start_date}'
          AND ts <= '{self.end_date}'
        ORDER BY ts
        """

        df = conn.execute(query).df()
        conn.close()

        if len(df) == 0:
            return None

        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        return df

    def _get_online_data(self) -> pd.DataFrame:
        """从在线获取数据"""
        import akshare as ak

        # 清除代理(akshare某些接口不支持代理)
        import os
        os.environ.pop('HTTPS_PROXY', None)
        os.environ.pop('HTTP_PROXY', None)

        # 提取代码
        if ':' in self.symbol:
            _, code = self.symbol.split(':')
        else:
            code = self.symbol

        print(f"  正在获取 {code} 的历史数据...")

        # 判断是ETF还是股票
        is_etf = len(code) == 6 and (code.startswith('5') or code.startswith('1'))

        try:
            if is_etf:
                # ETF使用专用接口
                print(f"  检测到ETF,使用fund_etf_hist_em接口...")
                df = ak.fund_etf_hist_em(
                    symbol=code,
                    period='daily',
                    start_date=self.start_date.strftime('%Y%m%d'),
                    end_date=self.end_date.strftime('%Y%m%d'),
                    adjust='qfq'  # 前复权
                )
            else:
                # 股票使用标准接口
                print(f"  检测到股票,使用stock_zh_a_hist接口...")
                df = ak.stock_zh_a_hist(
                    symbol=code,
                    period='daily',
                    start_date=self.start_date.strftime('%Y%m%d'),
                    end_date=self.end_date.strftime('%Y%m%d'),
                    adjust='qfq'  # 前复权
                )

            if df is None or len(df) == 0:
                raise RuntimeError(f"未获取到数据")

            # 标准化列名
            df = df.rename(columns={'日期': 'date', '收盘': 'price'})
            df['date'] = pd.to_datetime(df['date'])
            df = df[['date', 'price']]
            df = df.set_index('date')

            return df

        except Exception as e:
            raise RuntimeError(f"在线获取失败: {e}")

    def run_backtest(self) -> Dict:
        """运行回测"""
        print("🔄 运行回测...")

        # 获取价格数据
        price_data = self.get_price_data()

        # 生成定投日期
        dca_dates = self._generate_dca_dates(price_data.index)
        print(f"  定投次数: {len(dca_dates)}")

        # 执行定投
        records = []
        total_shares = 0
        total_invested = 0

        for date in dca_dates:
            # 找到最近的交易日价格
            price = self._get_price_on_date(price_data, date)
            if price is None:
                continue

            # 计算买入份额
            shares = self.investment_per_period / price
            total_shares += shares
            total_invested += self.investment_per_period

            records.append({
                'date': date,
                'price': price,
                'investment': self.investment_per_period,
                'shares': shares,
                'total_shares': total_shares,
                'total_invested': total_invested,
                'market_value': total_shares * price
            })

        # 转换为DataFrame
        df = pd.DataFrame(records)
        df = df.set_index('date')

        # 计算最终市值
        final_price = price_data.iloc[-1]['price']
        final_value = total_shares * final_price
        total_return = final_value - total_invested
        total_return_pct = (final_value / total_invested - 1) * 100

        # 计算年化收益率
        years = (self.end_date - self.start_date).days / 365.25
        annual_return = (final_value / total_invested) ** (1 / years) - 1

        # 计算最大回撤
        df['return_pct'] = ((df['market_value'] / df['total_invested']) - 1) * 100

        # 使用numpy计算累计最大值
        return_values = df['return_pct'].to_numpy()
        cummax_values = np.maximum.accumulate(return_values)
        df['cummax_return'] = cummax_values
        df['drawdown'] = df['return_pct'] - df['cummax_return']
        max_drawdown = float(df['drawdown'].min())

        # 计算夏普比率 (简化版,假设无风险利率3%)
        returns = df['return_pct'].pct_change().dropna()
        if len(returns) > 0:
            sharpe_ratio = (returns.mean() - 0.03/12) / returns.std() * np.sqrt(12)
        else:
            sharpe_ratio = 0

        results = {
            'records': df,
            'total_invested': total_invested,
            'final_value': final_value,
            'total_return': total_return,
            'total_return_pct': total_return_pct,
            'annual_return': annual_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'investment_count': len(dca_dates),
            'total_shares': total_shares,
            'avg_cost': total_invested / total_shares if total_shares > 0 else 0,
            'final_price': final_price,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'years': years
        }

        return results

    def _generate_dca_dates(self, available_dates: pd.DatetimeIndex) -> List[pd.Timestamp]:
        """生成定投日期"""
        dates = []
        current = self.start_date

        while current <= self.end_date:
            dates.append(current)

            # 计算下一个定投日期
            if self.frequency == 'daily':
                current += timedelta(days=1)
            elif self.frequency == 'weekly':
                current += timedelta(days=7)
            else:  # monthly
                # 下个月同一天
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)

        return dates

    def _get_price_on_date(self, price_data: pd.DataFrame, date: pd.Timestamp) -> Optional[float]:
        """获取指定日期的价格(如果不是交易日,找最近的交易日)"""
        # 确保时区一致
        if price_data.index.tz is not None and date.tz is None:
            date = date.tz_localize(price_data.index.tz)
        elif price_data.index.tz is None and date.tz is not None:
            date = date.tz_localize(None)

        # 找到最近的交易日
        future_dates = price_data.index[price_data.index >= date]
        if len(future_dates) == 0:
            return None

        nearest_date = future_dates[0]
        price = price_data.loc[nearest_date, 'price']

        # 确保返回float而不是Series
        if isinstance(price, pd.Series):
            price = price.iloc[0]

        return float(price)

    def print_results(self, results: Dict):
        """打印回测结果"""
        print()
        print("=" * 80)
        print("📊 定投回测结果")
        print("=" * 80)
        print()

        print("📈 基本信息")
        print("-" * 80)
        print(f"标的: {self.symbol}")
        print(f"回测周期: {results['start_date'].date()} 至 {results['end_date'].date()}")
        print(f"时长: {results['years']:.2f}年")
        print(f"定投频率: {self.frequency}")
        print(f"定投次数: {results['investment_count']}次")
        print()

        print("💰 投资情况")
        print("-" * 80)
        print(f"总投入: {results['total_invested']:,.2f}元")
        print(f"累计份额: {results['total_shares']:,.2f}份")
        print(f"平均成本: {results['avg_cost']:.4f}元/份")
        print(f"最终价格: {results['final_price']:.4f}元/份")
        print()

        print("📊 收益分析")
        print("-" * 80)
        print(f"最终市值: {results['final_value']:,.2f}元")
        print(f"总收益: {results['total_return']:+,.2f}元")
        print(f"总收益率: {results['total_return_pct']:+.2f}%")
        print(f"年化收益率: {results['annual_return']*100:+.2f}%")
        print()

        print("⚠️  风险指标")
        print("-" * 80)
        print(f"最大回撤: {results['max_drawdown']:.2f}%")
        print(f"夏普比率: {results['sharpe_ratio']:.2f}")
        print()

        # 显示关键时间点
        records = results['records']
        if len(records) > 0:
            print("📅 关键时间点")
            print("-" * 80)
            print(f"首次定投: {records.index[0].date()}, 价格: {records.iloc[0]['price']:.4f}元")
            print(f"最后定投: {records.index[-1].date()}, 价格: {records.iloc[-1]['price']:.4f}元")

            # 找到最高和最低回报时刻
            max_return_idx = records['return_pct'].idxmax()
            min_return_idx = records['return_pct'].idxmin()
            print(f"最高收益时刻: {max_return_idx.date()}, 收益率: {records.loc[max_return_idx, 'return_pct']:.2f}%")
            print(f"最低收益时刻: {min_return_idx.date()}, 收益率: {records.loc[min_return_idx, 'return_pct']:.2f}%")
            print()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='定投回测工具')
    parser.add_argument('symbol', help='标的代码 (如 600000, SSE:600000, 588000.SH)')
    parser.add_argument('--start', default='2020-01-01', help='起始日期 (YYYY-MM-DD)')
    parser.add_argument('--end', default=None, help='结束日期 (默认今天)')
    parser.add_argument('--frequency', choices=['daily', 'weekly', 'monthly'], default='monthly',
                        help='定投频率')
    parser.add_argument('--annual', type=float, default=120000, help='年投入总额(元)')
    parser.add_argument('--data-source', choices=['auto', 'local', 'online'], default='auto',
                        help='数据源')

    args = parser.parse_args()

    # 创建回测引擎
    backtest = DCABacktest(
        symbol=args.symbol,
        start_date=args.start,
        end_date=args.end,
        frequency=args.frequency,
        annual_investment=args.annual,
        data_source=args.data_source
    )

    # 运行回测
    results = backtest.run_backtest()

    # 打印结果
    backtest.print_results(results)

    print()
    print("=" * 80)
    print("回测完成")
    print("=" * 80)


if __name__ == '__main__':
    main()
