"""
Elder 三重滤网批量回测 — 多标的横向对比

标的：主要宽基/行业 ETF，覆盖不同风格
区间：2022-01-01 ~ 2026-04-30
"""
import sys, pathlib, tempfile
sys.path.insert(0, '/Users/zcs/code2/trading-os/src')

import pandas as pd
import numpy as np
import akshare as ak
from datetime import date, datetime, timezone

from trading_os.backtest.runner import BacktestConfig, BacktestRunner
from trading_os.data.pipeline import DataPipeline
from trading_os.data.lake import LocalDataLake
from trading_os.data.schema import Exchange, Timeframe, Adjustment
from trading_os.strategy.elder import ElderStrategy
from trading_os.strategy.builtin import BuyAndHoldStrategy

CACHE_DIR = pathlib.Path(__file__).parent / "etf_cache"
CACHE_DIR.mkdir(exist_ok=True)

# 标的列表：(akshare symbol, exchange, display_name)
TARGETS = [
    # (akshare sina symbol, exchange, display_name)
    ("sh510300", "SSE", "沪深300 ETF"),
    ("sh510500", "SSE", "中证500 ETF"),
    ("sh588000", "SSE", "科创50 ETF"),
    ("sz159915", "SZSE", "创业板 ETF"),
    ("sh512010", "SSE", "医疗 ETF"),
    ("sh512880", "SSE", "证券 ETF"),
    ("sh512690", "SSE", "酒 ETF"),
    ("sh515790", "SSE", "光伏 ETF"),
    ("sh512660", "SSE", "军工 ETF"),
    ("sz159869", "SZSE", "恒生科技 ETF"),
]

START = date(2022, 1, 1)
END   = date(2026, 4, 30)
INITIAL_CASH = 100_000.0

# ── 拉取并缓存数据 ────────────────────────────────────────────────────────────
def load_etf(symbol: str, exchange: str) -> pd.DataFrame | None:
    # symbol 形如 "sh510300"，ticker 是后6位
    ticker = symbol[2:]
    cache = CACHE_DIR / f"{ticker}.csv"
    if cache.exists():
        df = pd.read_csv(cache)
    else:
        try:
            df = ak.fund_etf_hist_sina(symbol=symbol)
            df.to_csv(cache, index=False)
        except Exception as e:
            print(f"  [{symbol}] 拉取失败: {e}")
            return None

    df = df.rename(columns={"date": "ts"})
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    sym_id = f"{exchange}:{ticker}"
    df["symbol"] = sym_id
    df["exchange"] = exchange
    df["timeframe"] = "1d"
    df["adjustment"] = "qfq"
    df["source"] = "akshare"
    df["vwap"] = df["close"]
    df["trades"] = 0
    cols = ["symbol","exchange","timeframe","adjustment","ts",
            "open","high","low","close","volume","vwap","trades","source"]
    return df[cols].sort_values("ts").reset_index(drop=True)


def run_backtest(df: pd.DataFrame, symbol_id: str) -> dict:
    tmp = pathlib.Path(tempfile.mkdtemp())
    lake = LocalDataLake(tmp); lake.init()
    exch = Exchange.SSE if symbol_id.startswith("SSE") else Exchange.SZSE
    lake.write_bars_parquet(df, exchange=exch, timeframe=Timeframe.D1,
        adjustment=Adjustment.QFQ, source="akshare",
        partition_hint=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"))
    lake.init()

    config = BacktestConfig(initial_cash=INITIAL_CASH)
    pipeline = DataPipeline(lake)

    # Elder
    runner_e = BacktestRunner(strategy=ElderStrategy(), pipeline=pipeline, config=config)
    result_e = runner_e.run(symbols=[symbol_id], start=START, end=END)

    # Buy & Hold
    runner_b = BacktestRunner(strategy=BuyAndHoldStrategy(), pipeline=pipeline, config=config)
    result_b = runner_b.run(symbols=[symbol_id], start=START, end=END)

    def nav_stats(ec):
        nav = ec.set_index("date")["nav"]
        nav.index = pd.to_datetime(nav.index)
        nav = nav.dropna()
        final = nav.iloc[-1]
        total_ret = (final - INITIAL_CASH) / INITIAL_CASH * 100
        years = (nav.index[-1] - nav.index[0]).days / 365
        ann = ((final / INITIAL_CASH) ** (1 / years) - 1) * 100 if years > 0 else 0
        roll_max = nav.cummax()
        mdd = ((nav - roll_max) / roll_max * 100).min()
        ret_d = nav.pct_change().dropna()
        rf = 0.02 / 252
        sharpe = (ret_d.mean() - rf) / ret_d.std() * np.sqrt(252) if ret_d.std() > 0 else 0
        return total_ret, ann, mdd, sharpe, len(result_e.trades) // 2

    tr_e, ann_e, mdd_e, sh_e, n_trades = nav_stats(result_e.equity_curve)
    tr_b, ann_b, mdd_b, sh_b, _ = nav_stats(result_b.equity_curve)

    return {
        "elder_ret": tr_e, "elder_ann": ann_e, "elder_mdd": mdd_e, "elder_sharpe": sh_e,
        "bh_ret": tr_b, "bh_ann": ann_b, "bh_mdd": mdd_b, "bh_sharpe": sh_b,
        "n_trades": n_trades,
        "alpha": tr_e - tr_b,
    }


# ── 主循环 ────────────────────────────────────────────────────────────────────
results = []
for symbol, exchange, name in TARGETS:
    ticker = symbol[2:]
    sym_id = f"{exchange}:{ticker}"
    print(f"处理 {name} ({sym_id})...", end=" ", flush=True)
    df = load_etf(symbol, exchange)
    if df is None:
        print("跳过")
        continue
    r = run_backtest(df, sym_id)
    r["name"] = name
    r["symbol"] = sym_id
    results.append(r)
    print(f"Elder {r['elder_ret']:+.1f}%  BH {r['bh_ret']:+.1f}%  alpha {r['alpha']:+.1f}%")

# ── 输出汇总表 ────────────────────────────────────────────────────────────────
print("\n" + "=" * 90)
print("  Elder 三重滤网批量回测结果  (2022-01-01 ~ 2026-04-30, 初始10万)")
print("=" * 90)
print(f"{'标的':<14} {'Elder收益':>9} {'Elder年化':>9} {'Elder回撤':>9} {'Elder夏普':>9} "
      f"{'BH收益':>8} {'BH回撤':>8} {'Alpha':>8} {'交易数':>6}")
print("-" * 90)

# 按 alpha 排序
results.sort(key=lambda x: x["alpha"], reverse=True)
for r in results:
    print(f"{r['name']:<14} {r['elder_ret']:>+8.1f}% {r['elder_ann']:>+8.1f}% "
          f"{r['elder_mdd']:>+8.1f}% {r['elder_sharpe']:>9.2f} "
          f"{r['bh_ret']:>+7.1f}% {r['bh_mdd']:>+7.1f}% "
          f"{r['alpha']:>+7.1f}% {r['n_trades']:>6}")

print("=" * 90)
print("Alpha = Elder总收益 - 买入持有总收益（正值=Elder跑赢）")
