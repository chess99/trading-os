"""
图表可视化模块

提供权益曲线、持仓分布等图表展示功能
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    import matplotlib
    import matplotlib.pyplot as plt
    import pandas as pd

    matplotlib.use('Agg')  # 使用非交互式后端
    plt.style.use('seaborn-v0_8-darkgrid')
except ImportError:
    matplotlib = None
    plt = None
    pd = None


def _require_dependencies():
    """检查依赖"""
    if plt is None or pd is None:
        raise RuntimeError(
            "可视化功能需要matplotlib和pandas\n"
            "请安装: pip install matplotlib pandas"
        )


def plot_equity_curve(
    equity_data: pd.DataFrame,
    output_path: Path,
    title: str = "权益曲线",
    figsize: tuple = (12, 6)
):
    """
    绘制权益曲线

    Args:
        equity_data: DataFrame with columns ['date', 'total', 'return']
        output_path: 输出文件路径
        title: 图表标题
        figsize: 图表大小
    """
    _require_dependencies()

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize, height_ratios=[2, 1])

    # 权益曲线
    ax1.plot(equity_data['date'], equity_data['total'], linewidth=2, color='#2E86AB')
    ax1.set_title(title, fontsize=14, pad=15)
    ax1.set_ylabel('账户总值 (元)', fontsize=11)
    ax1.grid(True, alpha=0.3)
    ax1.tick_params(axis='x', rotation=45)

    # 添加初始资金线
    if 'total' in equity_data.columns and len(equity_data) > 0:
        initial_value = equity_data['total'].iloc[0]
        ax1.axhline(y=initial_value, color='gray', linestyle='--', alpha=0.5, label='初始资金')
        ax1.legend()

    # 收益率曲线
    if 'return' in equity_data.columns:
        returns_pct = equity_data['return'] * 100
        colors = ['green' if r >= 0 else 'red' for r in returns_pct]
        ax2.bar(equity_data['date'], returns_pct, color=colors, alpha=0.6)
        ax2.set_ylabel('收益率 (%)', fontsize=11)
        ax2.set_xlabel('日期', fontsize=11)
        ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax2.grid(True, alpha=0.3)
        ax2.tick_params(axis='x', rotation=45)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"✅ 权益曲线已保存: {output_path}")


def plot_holdings_distribution(
    holdings: Dict[str, float],
    output_path: Path,
    title: str = "持仓分布",
    figsize: tuple = (10, 6)
):
    """
    绘制持仓分布饼图

    Args:
        holdings: {symbol: value}
        output_path: 输出文件路径
        title: 图表标题
        figsize: 图表大小
    """
    _require_dependencies()

    if not holdings:
        print("⚠️  没有持仓数据")
        return

    fig, ax = plt.subplots(figsize=figsize)

    symbols = list(holdings.keys())
    values = list(holdings.values())

    # 生成颜色
    colors = plt.cm.Set3(range(len(symbols)))

    # 绘制饼图
    wedges, texts, autotexts = ax.pie(
        values,
        labels=symbols,
        colors=colors,
        autopct='%1.1f%%',
        startangle=90,
        textprops={'fontsize': 10}
    )

    # 美化百分比文字
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_weight('bold')

    ax.set_title(title, fontsize=14, pad=15)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"✅ 持仓分布图已保存: {output_path}")


def plot_trade_analysis(
    trades: pd.DataFrame,
    output_path: Path,
    title: str = "交易分析",
    figsize: tuple = (12, 8)
):
    """
    绘制交易分析图

    Args:
        trades: DataFrame with columns ['date', 'action', 'symbol', 'amount', 'fee']
        output_path: 输出文件路径
        title: 图表标题
        figsize: 图表大小
    """
    _require_dependencies()

    if trades.empty:
        print("⚠️  没有交易数据")
        return

    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=figsize)

    # 1. 交易频率
    trades['date'] = pd.to_datetime(trades['date'])
    trades_by_date = trades.groupby(trades['date'].dt.date).size()
    ax1.bar(range(len(trades_by_date)), trades_by_date.values, color='#A23B72')
    ax1.set_title('每日交易次数', fontsize=11)
    ax1.set_ylabel('交易次数', fontsize=10)
    ax1.grid(True, alpha=0.3)

    # 2. 买入卖出统计
    action_counts = trades['action'].value_counts()
    ax2.bar(action_counts.index, action_counts.values, color=['#2E86AB', '#F18F01'])
    ax2.set_title('买入/卖出统计', fontsize=11)
    ax2.set_ylabel('次数', fontsize=10)
    ax2.grid(True, alpha=0.3)

    # 3. 交易金额分布
    if 'amount' in trades.columns:
        ax3.hist(trades['amount'], bins=20, color='#06A77D', alpha=0.7, edgecolor='black')
        ax3.set_title('交易金额分布', fontsize=11)
        ax3.set_xlabel('金额 (元)', fontsize=10)
        ax3.set_ylabel('频次', fontsize=10)
        ax3.grid(True, alpha=0.3)

    # 4. 累计手续费
    if 'fee' in trades.columns:
        cumulative_fees = trades['fee'].cumsum()
        ax4.plot(range(len(cumulative_fees)), cumulative_fees, linewidth=2, color='#D00000')
        ax4.set_title('累计手续费', fontsize=11)
        ax4.set_ylabel('手续费 (元)', fontsize=10)
        ax4.grid(True, alpha=0.3)

    plt.suptitle(title, fontsize=14, y=1.00)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"✅ 交易分析图已保存: {output_path}")


def plot_drawdown(
    equity_data: pd.DataFrame,
    output_path: Path,
    title: str = "回撤分析",
    figsize: tuple = (12, 5)
):
    """
    绘制回撤曲线

    Args:
        equity_data: DataFrame with columns ['date', 'total']
        output_path: 输出文件路径
        title: 图表标题
        figsize: 图表大小
    """
    _require_dependencies()

    fig, ax = plt.subplots(figsize=figsize)

    # 计算回撤
    equity_data = equity_data.copy()
    equity_data['cum_max'] = equity_data['total'].cummax()
    equity_data['drawdown'] = (equity_data['total'] - equity_data['cum_max']) / equity_data['cum_max'] * 100

    # 绘制回撤曲线
    ax.fill_between(
        equity_data['date'],
        equity_data['drawdown'],
        0,
        where=(equity_data['drawdown'] < 0),
        color='red',
        alpha=0.3,
        label='回撤'
    )
    ax.plot(equity_data['date'], equity_data['drawdown'], linewidth=2, color='darkred')

    ax.set_title(title, fontsize=14, pad=15)
    ax.set_ylabel('回撤 (%)', fontsize=11)
    ax.set_xlabel('日期', fontsize=11)
    ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax.grid(True, alpha=0.3)
    ax.tick_params(axis='x', rotation=45)
    ax.legend()

    # 标注最大回撤
    max_dd_idx = equity_data['drawdown'].idxmin()
    max_dd_value = equity_data['drawdown'].min()
    max_dd_date = equity_data.loc[max_dd_idx, 'date']

    ax.annotate(
        f'最大回撤: {max_dd_value:.2f}%',
        xy=(max_dd_date, max_dd_value),
        xytext=(10, -20),
        textcoords='offset points',
        bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.7),
        arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0')
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"✅ 回撤分析图已保存: {output_path}")


def create_backtest_report(
    results: Dict,
    output_dir: Path,
    report_name: str = "backtest_report"
):
    """
    创建完整的回测报告(包含多个图表)

    Args:
        results: 回测结果字典
        output_dir: 输出目录
        report_name: 报告名称前缀
    """
    _require_dependencies()

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📊 生成回测报告...")

    # 1. 权益曲线
    if 'equity_curve' in results and not results['equity_curve'].empty:
        plot_equity_curve(
            results['equity_curve'],
            output_dir / f"{report_name}_equity.png",
            title=f"权益曲线 (总收益: {results.get('total_return', 0):.2%})"
        )

        # 2. 回撤分析
        plot_drawdown(
            results['equity_curve'],
            output_dir / f"{report_name}_drawdown.png"
        )

    # 3. 交易分析
    if 'trades' in results and not results['trades'].empty:
        plot_trade_analysis(
            results['trades'],
            output_dir / f"{report_name}_trades.png"
        )

    print(f"\n✅ 报告已生成: {output_dir}")


def plot_portfolio_summary(
    account_data: Dict,
    output_path: Path,
    figsize: tuple = (14, 8)
):
    """
    绘制投资组合总结图

    Args:
        account_data: 账户数据 {
            'total_value': float,
            'cash': float,
            'holdings': {symbol: {'shares': int, 'value': float, 'return': float}},
            'total_return': float
        }
        output_path: 输出文件路径
        figsize: 图表大小
    """
    _require_dependencies()

    fig = plt.figure(figsize=figsize)
    gs = fig.add_gridspec(2, 3, hspace=0.3, wspace=0.3)

    # 1. 资产分布(饼图)
    ax1 = fig.add_subplot(gs[0, 0])
    cash = account_data.get('cash', 0)
    holdings_value = sum(h['value'] for h in account_data.get('holdings', {}).values())

    if cash + holdings_value > 0:
        sizes = [cash, holdings_value]
        labels = ['现金', '持仓']
        colors = ['#A8DADC', '#457B9D']
        ax1.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        ax1.set_title('资产分布', fontsize=11, pad=10)

    # 2. 持仓占比(柱状图)
    ax2 = fig.add_subplot(gs[0, 1:])
    holdings = account_data.get('holdings', {})
    if holdings:
        symbols = list(holdings.keys())
        values = [h['value'] for h in holdings.values()]
        colors_bar = plt.cm.Set3(range(len(symbols)))

        bars = ax2.barh(symbols, values, color=colors_bar)
        ax2.set_title('持仓市值', fontsize=11, pad=10)
        ax2.set_xlabel('市值 (元)', fontsize=10)
        ax2.grid(True, alpha=0.3, axis='x')

        # 添加数值标签
        for bar in bars:
            width = bar.get_width()
            ax2.text(width, bar.get_y() + bar.get_height()/2,
                    f'{width:,.0f}',
                    ha='left', va='center', fontsize=9)

    # 3. 持仓收益(柱状图)
    ax3 = fig.add_subplot(gs[1, :])
    if holdings:
        symbols = list(holdings.keys())
        returns = [h.get('return', 0) * 100 for h in holdings.values()]
        colors_return = ['green' if r >= 0 else 'red' for r in returns]

        bars = ax3.bar(symbols, returns, color=colors_return, alpha=0.7)
        ax3.set_title('持仓收益率', fontsize=11, pad=10)
        ax3.set_ylabel('收益率 (%)', fontsize=10)
        ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax3.grid(True, alpha=0.3, axis='y')

        # 添加数值标签
        for bar in bars:
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2, height,
                    f'{height:.1f}%',
                    ha='center', va='bottom' if height >= 0 else 'top',
                    fontsize=9)

    # 总标题
    total_return = account_data.get('total_return', 0)
    total_value = account_data.get('total_value', 0)
    fig.suptitle(
        f'投资组合总结 | 总资产: {total_value:,.2f}元 | 总收益: {total_return:.2%}',
        fontsize=14,
        y=0.98
    )

    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"✅ 投资组合总结图已保存: {output_path}")
