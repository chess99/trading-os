"""
科创50 ETF (588000) MACD 金叉/死叉策略回测

策略规则：
  - MACD 金叉（MACD 线从下方穿越信号线）→ 买入（全仓）
  - MACD 死叉（MACD 线从上方穿越信号线）→ 卖出（清仓）

对比基准：买入并持有（Buy & Hold）

MACD 参数：EMA(12), EMA(26), Signal EMA(9)
"""

import sys
import pathlib
import pandas as pd
import numpy as np

# ── 1. 拉取数据（带缓存）─────────────────────────────────────────────────────
CACHE = pathlib.Path(__file__).parent / "588000_cache.csv"

if CACHE.exists():
    print(f"从缓存加载数据: {CACHE}")
    df_raw = pd.read_csv(CACHE)
    df_raw.columns = [c.lower() for c in df_raw.columns]
    # 统一列名
    col_map = {"日期": "date", "收盘": "close", "开盘": "open",
               "最高": "high", "最低": "low", "成交量": "volume", "成交额": "amount"}
    df_raw = df_raw.rename(columns=col_map)
    df = df_raw
else:
    print("正在拉取科创50 ETF (588000) 数据...")
    try:
        import akshare as ak
        df_raw = ak.fund_etf_hist_em(
            symbol="588000", period="daily",
            start_date="20200701", end_date="20260507", adjust="qfq",
        )
    except Exception as e:
        print(f"数据拉取失败: {e}", file=sys.stderr)
        sys.exit(1)
    df_raw.to_csv(CACHE, index=False)
    print(f"数据已缓存至 {CACHE}")
    df_raw = df_raw.rename(columns={"日期": "date", "收盘": "close", "开盘": "open", "成交额": "amount"})
    df = df_raw

if "date" not in df.columns and "日期" in df.columns:
    df = df.rename(columns={"日期": "date", "收盘": "close", "开盘": "open"})
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date").reset_index(drop=True)

# 只取指定区间
df = df[(df["date"] >= "2022-01-01") & (df["date"] <= "2026-04-30")].reset_index(drop=True)
print(f"数据范围: {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}  共 {len(df)} 个交易日\n")

# ── 2. 计算 MACD ─────────────────────────────────────────────────────────────
close = df["close"].astype(float)
ema12 = close.ewm(span=12, adjust=False).mean()
ema26 = close.ewm(span=26, adjust=False).mean()
macd_line = ema12 - ema26          # DIF
signal_line = macd_line.ewm(span=9, adjust=False).mean()  # DEA
hist = macd_line - signal_line     # MACD 柱

df["macd"] = macd_line
df["signal"] = signal_line
df["hist"] = hist

# 金叉/死叉检测
df["golden_cross"] = (df["macd"] > df["signal"]) & (df["macd"].shift(1) <= df["signal"].shift(1))
df["death_cross"]  = (df["macd"] < df["signal"]) & (df["macd"].shift(1) >= df["signal"].shift(1))

# ── 3. 回测 ──────────────────────────────────────────────────────────────────
INITIAL_CASH = 100_000.0
cash = INITIAL_CASH
shares = 0.0
trades = []
nav_series = []

# A 股 T+1：买入信号当日以收盘价成交（简化），次日才能卖
# 此处使用信号触发日收盘价成交（简化实现），注意会有轻微前瞻偏差
# 生产级实现应改为次日开盘价成交；这里用来做策略方向验证

in_position = False
entry_price = 0.0
entry_date = None

for i, row in df.iterrows():
    price = row["close"]
    nav = cash + shares * price
    nav_series.append(nav)

    if row["golden_cross"] and not in_position and cash > 0:
        # 买入：全仓
        shares = cash / price
        cash = 0.0
        in_position = True
        entry_price = price
        entry_date = row["date"]
        trades.append({
            "type": "BUY",
            "date": row["date"].date(),
            "price": price,
            "shares": shares,
            "nav": nav,
        })

    elif row["death_cross"] and in_position:
        # 卖出：清仓
        pnl = (price - entry_price) * shares
        pnl_pct = (price - entry_price) / entry_price * 100
        cash = shares * price
        shares = 0.0
        in_position = False
        hold_days = (row["date"] - entry_date).days
        trades.append({
            "type": "SELL",
            "date": row["date"].date(),
            "price": price,
            "shares": 0,
            "nav": cash,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "hold_days": hold_days,
        })

df["nav_macd"] = nav_series

# ── 4. 买入持有基准 ───────────────────────────────────────────────────────────
df["nav_bh"] = INITIAL_CASH / df["close"].iloc[0] * df["close"]

# ── 5. 统计结果 ───────────────────────────────────────────────────────────────
final_nav_macd = df["nav_macd"].iloc[-1]
final_nav_bh   = df["nav_bh"].iloc[-1]

# 总收益率
total_return_macd = (final_nav_macd - INITIAL_CASH) / INITIAL_CASH * 100
total_return_bh   = (final_nav_bh   - INITIAL_CASH) / INITIAL_CASH * 100

# 年化收益率
years = (df["date"].iloc[-1] - df["date"].iloc[0]).days / 365.0
ann_macd = ((final_nav_macd / INITIAL_CASH) ** (1 / years) - 1) * 100
ann_bh   = ((final_nav_bh   / INITIAL_CASH) ** (1 / years) - 1) * 100

# 最大回撤
def max_drawdown(nav):
    rolling_max = nav.cummax()
    dd = (nav - rolling_max) / rolling_max * 100
    return dd.min()

mdd_macd = max_drawdown(df["nav_macd"])
mdd_bh   = max_drawdown(df["nav_bh"])

# 夏普比率（日收益，无风险利率 2%/年）
rf_daily = 0.02 / 252
ret_macd = df["nav_macd"].pct_change().dropna()
ret_bh   = df["nav_bh"].pct_change().dropna()
sharpe_macd = (ret_macd.mean() - rf_daily) / ret_macd.std() * np.sqrt(252) if ret_macd.std() > 0 else 0
sharpe_bh   = (ret_bh.mean()   - rf_daily) / ret_bh.std()   * np.sqrt(252) if ret_bh.std()   > 0 else 0

# 交易统计
sell_trades = [t for t in trades if t["type"] == "SELL"]
n_trades = len(sell_trades)
win_trades = [t for t in sell_trades if t["pnl"] > 0]
win_rate = len(win_trades) / n_trades * 100 if n_trades > 0 else 0
avg_pnl = np.mean([t["pnl_pct"] for t in sell_trades]) if sell_trades else 0
avg_hold = np.mean([t["hold_days"] for t in sell_trades]) if sell_trades else 0

# ── 6. 输出报告 ───────────────────────────────────────────────────────────────
print("=" * 60)
print("  科创50 ETF (588000) MACD 金叉死叉策略 vs 买入持有")
print("=" * 60)

print(f"\n{'指标':<20} {'MACD策略':>15} {'买入持有':>15}")
print("-" * 52)
print(f"{'总收益率':<20} {total_return_macd:>14.1f}% {total_return_bh:>14.1f}%")
print(f"{'年化收益率':<20} {ann_macd:>14.1f}% {ann_bh:>14.1f}%")
print(f"{'最大回撤':<20} {mdd_macd:>14.1f}% {mdd_bh:>14.1f}%")
print(f"{'夏普比率':<20} {sharpe_macd:>15.2f} {sharpe_bh:>15.2f}")
print(f"{'期末净值(万)':<20} {final_nav_macd/10000:>15.2f} {final_nav_bh/10000:>15.2f}")

print(f"\n{'── 交易明细 ──':}")
print(f"  完成交易次数：{n_trades} 笔")
print(f"  胜率：{win_rate:.1f}%")
print(f"  平均单笔盈亏：{avg_pnl:.1f}%")
print(f"  平均持仓天数：{avg_hold:.0f} 天")

# 当前持仓状态
if in_position:
    last_price = df["close"].iloc[-1]
    unrealized = (last_price - entry_price) / entry_price * 100
    print(f"\n  当前持仓中（买入价 {entry_price:.3f}，未实现 {unrealized:+.1f}%）")
else:
    print(f"\n  当前空仓")

print(f"\n── 逐笔交易记录 ──")
print(f"{'序号':<4} {'方向':<5} {'日期':<12} {'价格':>8} {'盈亏%':>8} {'持仓天':>6}")
print("-" * 48)

buy_idx = 0
for i, t in enumerate(trades):
    if t["type"] == "BUY":
        buy_idx = i
        print(f"{buy_idx//2+1:<4} 买入   {str(t['date']):<12} {t['price']:>8.3f}")
    else:
        print(f"{'':4} 卖出   {str(t['date']):<12} {t['price']:>8.3f} {t['pnl_pct']:>7.1f}% {t['hold_days']:>5}天")

print("\n注：价格使用信号触发日收盘价（简化，实际应用应使用次日开盘价）")
print("=" * 60)
