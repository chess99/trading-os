"""
科创50 ETF (588000) Elder 三重滤网策略回测（探索脚本）

数据直接从 akshare 拉取，不走 lake，避免代理问题。
用 trading_os 的 ElderStrategy + BacktestRunner 跑。
"""
import sys
import os
# 禁用系统代理（macOS SCF proxy 对东方财富接口不稳定）
os.environ["no_proxy"] = "*"
os.environ["NO_PROXY"] = "*"
import urllib.request
urllib.request._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
sys.path.insert(0, '/Users/zcs/code2/trading-os/src')

import requests
requests.Session.__init__.__func__ if False else None
# monkey-patch: 让 requests 也不走代理
import requests.utils
_orig_get_environ_proxies = requests.utils.get_environ_proxies
requests.utils.get_environ_proxies = lambda *a, **kw: {}

import akshare as ak
import pandas as pd
from datetime import datetime, timezone

# ── 1. 拉取数据（带本地缓存）─────────────────────────────────────────────────
import pathlib
CACHE_CSV = pathlib.Path(__file__).parent / "588000_cache.csv"

if CACHE_CSV.exists():
    print(f"从缓存加载数据: {CACHE_CSV}")
    df = pd.read_csv(CACHE_CSV)
else:
    print("拉取科创50 ETF (588000) 数据...")
    df = ak.fund_etf_hist_em(
        symbol="588000", period="daily",
        start_date="20200701", end_date="20260507", adjust="qfq"
    )
    df.to_csv(CACHE_CSV, index=False)
    print(f"数据已缓存至 {CACHE_CSV}")

# 统一列名（兼容中文原始列名和已重命名列名）
df = df.rename(columns={
    "日期": "ts", "开盘": "open", "最高": "high",
    "最低": "low", "收盘": "close", "成交量": "volume"
})
df["ts"] = pd.to_datetime(df["ts"], utc=True)
df["symbol"] = "SSE:588000"
df["exchange"] = "SSE"
df["timeframe"] = "1d"
df["adjustment"] = "qfq"
df["source"] = "akshare"
df["vwap"] = df["close"]
df["trades"] = 0
df = df.sort_values("ts").reset_index(drop=True)
print(f"数据: {df['ts'].iloc[0].date()} ~ {df['ts'].iloc[-1].date()}  {len(df)} 条\n")

# ── 2. 写入临时 lake ──────────────────────────────────────────────────────────
import tempfile, pathlib
from trading_os.data.lake import LocalDataLake
from trading_os.data.schema import Exchange, Timeframe, Adjustment

tmp_dir = pathlib.Path(tempfile.mkdtemp())
lake = LocalDataLake(tmp_dir)
lake.init()

cols = ["symbol","exchange","timeframe","adjustment","ts",
        "open","high","low","close","volume","vwap","trades","source"]
lake.write_bars_parquet(
    df[cols],
    exchange=Exchange.SSE, timeframe=Timeframe.D1, adjustment=Adjustment.QFQ,
    source="akshare",
    partition_hint=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
)
lake.init()

# ── 3. 运行 Elder 回测 ────────────────────────────────────────────────────────
from trading_os.backtest.runner import BacktestConfig, BacktestRunner
from trading_os.data.pipeline import DataPipeline
from trading_os.strategy.elder import ElderStrategy
from datetime import date

pipeline = DataPipeline(lake)
config = BacktestConfig(initial_cash=100_000.0)
strategy = ElderStrategy()
runner = BacktestRunner(strategy=strategy, pipeline=pipeline, config=config)

print("运行 Elder 三重滤网回测...")
result = runner.run(
    symbols=["SSE:588000"],
    start=date(2022, 1, 1),
    end=date(2026, 4, 30),
)

# ── 4. 输出结果 ───────────────────────────────────────────────────────────────
import numpy as np

ec = result.equity_curve  # columns: date, nav, cash, equity
nav = ec.set_index("date")["nav"]
nav.index = pd.to_datetime(nav.index)

# 买入持有基准
start_date = pd.Timestamp("2022-01-04")
bh_bars = df[df["ts"] >= pd.Timestamp("2022-01-04", tz="UTC")].copy()
bh_start_price = float(bh_bars["close"].iloc[0])
bh_nav = pd.Series(
    config.initial_cash / bh_start_price * bh_bars["close"].values,
    index=pd.to_datetime(bh_bars["ts"].dt.tz_localize(None).values),
)

def stats(nav_s, initial):
    nav_s = nav_s.dropna()
    final = nav_s.iloc[-1]
    total_ret = (final - initial) / initial * 100
    years = (nav_s.index[-1] - nav_s.index[0]).days / 365
    ann = ((final / initial) ** (1 / years) - 1) * 100 if years > 0 else 0
    roll_max = nav_s.cummax()
    mdd = ((nav_s - roll_max) / roll_max * 100).min()
    ret_d = nav_s.pct_change().dropna()
    rf = 0.02 / 252
    sharpe = (ret_d.mean() - rf) / ret_d.std() * np.sqrt(252) if ret_d.std() > 0 else 0
    return total_ret, ann, mdd, sharpe, final

tr_e, ann_e, mdd_e, sh_e, final_e = stats(nav, config.initial_cash)
tr_b, ann_b, mdd_b, sh_b, final_b = stats(bh_nav, config.initial_cash)

print("\n" + "=" * 60)
print("  科创50 ETF (588000) Elder 三重滤网 vs 买入持有")
print("  区间: 2022-01-01 ~ 2026-04-30")
print("=" * 60)
print(f"\n{'指标':<20} {'Elder三重滤网':>15} {'买入持有':>12}")
print("-" * 50)
print(f"{'总收益率':<20} {tr_e:>14.1f}% {tr_b:>11.1f}%")
print(f"{'年化收益率':<20} {ann_e:>14.1f}% {ann_b:>11.1f}%")
print(f"{'最大回撤':<20} {mdd_e:>14.1f}% {mdd_b:>11.1f}%")
print(f"{'夏普比率':<20} {sh_e:>15.2f} {sh_b:>12.2f}")
print(f"{'期末净值(万)':<20} {final_e/10000:>15.2f} {final_b/10000:>12.2f}")

# 交易记录
trades_df = result.trades
if not trades_df.empty:
    sells = trades_df[trades_df["side"] == "SELL"]
    buys  = trades_df[trades_df["side"] == "BUY"]
    # 配对
    pairs = []
    buy_stack = list(buys["price"])
    for _, row in sells.iterrows():
        if buy_stack:
            bp = buy_stack.pop(0)
            pnl_pct = (row["price"] - bp) / bp * 100
            pairs.append(pnl_pct)
    wins = [p for p in pairs if p > 0]
    n = len(pairs)
    wr = len(wins) / n * 100 if n > 0 else 0
    avg = np.mean(pairs) if pairs else 0
    print(f"\n完成交易: {n} 笔  胜率: {wr:.1f}%  平均盈亏: {avg:.1f}%")
    print("\n逐笔记录:")
    print(trades_df[["date","side","price","shares"]].to_string(index=False))
else:
    print("\n无交易记录（历史数据不足触发三重滤网条件）")

print("=" * 60)
