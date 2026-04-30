#!/usr/bin/env python3.11
"""Elder System 每日收盘分析 - 批量处理4个标的"""
import os, sys, logging
from datetime import datetime, timezone, timedelta
import pandas as pd

for k in list(os.environ.keys()):
    if 'proxy' in k.lower():
        del os.environ[k]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger(__name__)

CST = timezone(timedelta(hours=8))

def calc_ema(series, n):
    return series.ewm(span=n, adjust=False).mean()

def fetch_tencent_bars(ticker, start="2020-01-01", end=None):
    import requests
    if end is None:
        end = datetime.now(CST).strftime('%Y-%m-%d')
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    params = {"param": f"{ticker},day,{start},{end},2000,qfq"}
    r = requests.get(url, params=params, timeout=15,
                     headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.qq.com"})
    d = r.json()
    if d.get("code") != 0 or "data" not in d:
        return None
    ticker_data = d["data"].get(ticker, {})
    day_data = ticker_data.get("day", []) or ticker_data.get("qfqday", [])
    if not day_data:
        return None
    rows = []
    for item in day_data:
        if len(item) < 6: continue
        rows.append({"date": item[0], "open": float(item[1]), "close": float(item[2]),
                     "high": float(item[3]), "low": float(item[4]), "volume": float(item[5])})
    df = pd.DataFrame(rows)
    df['date'] = pd.to_datetime(df['date'])
    return df.sort_values('date').reset_index(drop=True)

def elder_single(df, name, ticker):
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    volume = df['volume'].values

    ema13 = calc_ema(pd.Series(close), 13).values
    ema26 = calc_ema(pd.Series(close), 26).values

    bull_power = high - ema13
    bear_power = low - ema13

    force_raw = (pd.Series(close) - pd.Series(close).shift(1)) * volume
    fi13 = calc_ema(force_raw, 13).values

    vol_ma20 = pd.Series(volume).rolling(20).mean()
    vol_ratio = (pd.Series(volume) / vol_ma20).values

    last_close = close[-1]
    trend_up = ema13[-1] > ema26[-1]
    ret20 = (last_close / close[-21] - 1) * 100 if len(close) > 21 else 0
    ret60 = (last_close / close[-61] - 1) * 100 if len(close) > 61 else 0

    # 评分
    score = 0
    if trend_up: score += 2
    if bull_power[-1] > 0: score += 1
    if fi13[-1] > 0: score += 1
    if vol_ratio[-1] > 1.2: score += 1
    if ret20 > 0: score += 1

    verdict = "强势" if score >= 5 else "中性" if score >= 3 else "弱势"
    trend_str = "上升" if trend_up else "下降"

    vol_tag = ""
    if vol_ratio[-1] > 1.2:
        vol_tag = " · 放量"
    elif vol_ratio[-1] < 0.8:
        vol_tag = " · 缩量"

    if score >= 5:
        action = "✅ 强势，持有/可加仓"
    elif score == 4:
        action = "✅ 偏强，可持有"
    elif score == 3:
        action = "➡️  中性，观望为主"
    elif score == 2:
        action = "⚠️  偏弱，轻仓或观望"
    else:
        action = "🔴 弱势，空仓不参与"

    ret20_str = f"+{ret20:.1f}%" if ret20 >= 0 else f"{ret20:.1f}%"
    ret60_str = f"+{ret60:.1f}%" if ret60 >= 0 else f"{ret60:.1f}%"

    return "\n".join([
        f"━━━ {name} · {ticker} ━━━",
        f"收盘 {last_close:.3f}   20日 {ret20_str}   60日 {ret60_str}",
        f"趋势{trend_str} · 信号{verdict} {score}/6{vol_tag}",
        action,
    ])

def main():
    symbols = [
        ("sh159740", "恒生科技ETF"),
        ("sh588000", "科创50ETF"),
        ("sh601138", "工业富联"),
        ("sh600519", "贵州茅台"),
    ]

    now_cst = datetime.now(CST)
    results = []
    for ticker, name in symbols:
        log.info(f"分析 {name}({ticker})...")
        try:
            df = fetch_tencent_bars(ticker)
            if df is None or len(df) < 60:
                log.error(f"{ticker} 数据不足: {len(df) if df else 0} 行")
                continue
            results.append(elder_single(df, name, ticker))
            log.info(f"{name} 完成")
        except Exception as e:
            log.error(f"{ticker} 分析失败: {e}")
            results.append(f"❌ {name}({ticker}) 分析失败: {e}")

    if not results:
        print("❌ 所有标的分析均失败")
    else:
        print(f"📈 Elder 日报 · {now_cst.strftime('%Y-%m-%d')}\n")
        print("\n\n".join(results))
        print(f"\n发送时间: {now_cst.strftime('%H:%M')} CST")

if __name__ == "__main__":
    main()
