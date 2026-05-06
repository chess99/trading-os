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

def fetch_realtime_bar(ticker):
    """用腾讯实时行情 API 获取今日 bar（收盘后可用），返回单行 dict 或 None"""
    import requests
    r = requests.get(f"https://qt.gtimg.cn/q={ticker}", timeout=10,
                     headers={"User-Agent": "Mozilla/5.0"})
    fields = r.text.split("~")
    if len(fields) < 37:
        return None
    dt_str = fields[30]  # 例如 "20260506161450"
    if len(dt_str) < 8:
        return None
    date_str = f"{dt_str[:4]}-{dt_str[4:6]}-{dt_str[6:8]}"
    try:
        return {
            "date": date_str,
            "open": float(fields[5]),
            "close": float(fields[3]),
            "high": float(fields[33]),
            "low": float(fields[34]),
            "volume": float(fields[36]) * 100,  # 手 → 股
        }
    except (ValueError, IndexError):
        return None

def fetch_tencent_bars(ticker, start="2020-01-01", end=None):
    import requests
    today = datetime.now(CST).strftime('%Y-%m-%d')
    if end is None:
        end = today
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
    df = df.sort_values('date').reset_index(drop=True)

    # 历史K线 API 有延迟，若最新一条不是今天，用实时行情补齐
    last_date = df['date'].iloc[-1].strftime('%Y-%m-%d')
    if last_date < today:
        rt = fetch_realtime_bar(ticker)
        if rt and rt["date"] == today:
            new_row = pd.DataFrame([{**rt, "date": pd.Timestamp(rt["date"])}])
            df = pd.concat([df, new_row], ignore_index=True)
            log.info(f"{ticker} 实时行情补齐今日数据 ({today})")

    return df

def elder_single(df, name, ticker):
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    volume = df['volume'].values

    ema13 = calc_ema(pd.Series(close), 13).values
    ema26 = calc_ema(pd.Series(close), 26).values
    ema50 = calc_ema(pd.Series(close), 50).values

    bull_power = high - ema13
    bear_power = low - ema13

    force_raw = (pd.Series(close) - pd.Series(close).shift(1)) * volume
    fi13 = calc_ema(force_raw, 13).values

    vol_ma20 = pd.Series(volume).rolling(20).mean()
    vol_ratio = (pd.Series(volume) / vol_ma20).values

    last_close = close[-1]
    last_date = df['date'].iloc[-1].date()
    trend = "↑ 上升" if ema13[-1] > ema26[-1] else "↓ 下降"
    fi_state = "🟢" if fi13[-1] > 0 else "🔴"
    bp_state = "✅" if bull_power[-1] > 0 else "⚠️"
    vol_state = "放量" if vol_ratio[-1] > 1.2 else "缩量" if vol_ratio[-1] < 0.8 else "正常"

    ret20 = (last_close / close[-21] - 1) * 100 if len(close) > 21 else 0
    ret60 = (last_close / close[-61] - 1) * 100 if len(close) > 61 else 0

    # 评分
    score = 0
    if ema13[-1] > ema26[-1]: score += 2
    if bull_power[-1] > 0: score += 1
    if fi13[-1] > 0: score += 1
    if vol_ratio[-1] > 1.2: score += 1
    if ret20 > 0: score += 1

    verdict = "强势" if score >= 5 else "中性" if score >= 3 else "弱势"

    verdict_icon = "🔥" if score >= 5 else "⚡" if score >= 3 else "❄️"
    lines = [
        f"┌─ 📊 {name}({ticker}) ─── {last_date} ───────────────",
        f"│  收盘 {last_close:.3f}  {trend}",
        f"│  EMA13={ema13[-1]:.3f}  EMA26={ema26[-1]:.3f}  EMA50={ema50[-1]:.3f}",
        f"│  多头力量 {bull_power[-1]:+.4f} {bp_state}   空头力量 {bear_power[-1]:+.4f}",
        f"│  Force Index(13)={fi13[-1]:+.0f} {fi_state}   成交量/MA20={vol_ratio[-1]:.1f}×({vol_state})",
        f"│  20日收益={ret20:+.1f}%   60日收益={ret60:+.1f}%",
        f"└─ {verdict_icon} Elder信号: {score}/6 [{verdict}]",
    ]
    return "\n".join(lines)

def main():
    symbols = [
        ("sh510300", "沪深300ETF"),
        ("sh159740", "恒生科技ETF"),
        ("sh588000", "科创50ETF"),
        ("sh601138", "工业富联"),
        ("sh600519", "贵州茅台"),
    ]

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
        msg = "📈 Elder 每日收盘分析\n" + "\n".join(results)
        msg += f"\n🕐 {datetime.now(CST).strftime('%Y-%m-%d %H:%M')} (CST)"
        print(msg)

if __name__ == "__main__":
    main()
