#!/usr/bin/env python3.11
"""纯 parquet CANSLIM 扫描器 - 不过 DuckDB，内存友好"""
import json, logging, os, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
import requests

os.environ = {k: v for k, v in os.environ.items() if not k.lower().endswith('proxy')}

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger(__name__)

MIN_EPS_GROWTH = 0.18
MIN_ROE = 17.0  # EastMoney ROEJQ 是百分数格式，如 17.54 = 17.54%
MIN_POSITIVE_QUARTERS = 9
MIN_TURNOVER_AVG = 1e7
RS_TOP_PCT = 0.20
TOP_N = 30
MAX_WORKERS = 3
DATA_ROOT = Path('/root/.openclaw/workspace/trading-os/data/parquet/bars')
CACHE_FILE = Path('/tmp/canslim_parquet_cache.json')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://emweb.securities.eastmoney.com/",
}
EM_F10 = "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/ZYZBAjaxNew"

# ── 扫描所有 parquet，建立 liquidity + 52w 数据 ──────────────────────
def scan_parquets(scan_dt):
    """扫所有 parquet 文件，构建 symbol → (liquidity_ok, rs_return) 字典"""
    end_ts = scan_dt.isoformat()
    start_30d = (scan_dt - timedelta(days=30)).isoformat()
    start_52w = (scan_dt - timedelta(days=365)).isoformat()

    symbol_data = {}
    files = list(DATA_ROOT.glob("*.parquet"))
    log.info(f"扫描 {len(files)} 个 parquet 文件...")

    for f in files:
        try:
            pf = pq.ParquetFile(f)
            # 读取所有数据
            table = pf.read()
            df = table.to_pandas()
            if df.empty:
                continue

            df['ts'] = pd.to_datetime(df['ts'], errors='coerce')
            df = df.dropna(subset=['ts', 'close', 'volume'])
            if df.empty:
                continue

            # symbol
            sym = df['symbol'].iloc[0] if 'symbol' in df.columns else None
            if not sym:
                continue

            # Liquidity: 30日日均成交额
            df_30 = df[df['ts'] <= end_ts]
            if len(df_30) > 5:
                avg_turnover = (df_30['close'] * df_30['volume']).mean()
                liquidity_ok = avg_turnover >= MIN_TURNOVER_AVG
            else:
                liquidity_ok = False

            # 52W return
            df_52w = df[(df['ts'] >= start_52w) & (df['ts'] <= end_ts)]
            if len(df_52w) >= 60:
                start_price = df_52w.iloc[0]['close']
                end_price = df_52w.iloc[-1]['close']
                rs_return = (end_price - start_price) / start_price if start_price > 0 else None
            else:
                rs_return = None

            symbol_data[sym] = {'liquidity_ok': bool(liquidity_ok), 'rs_return': float(rs_return) if rs_return is not None else None}
        except Exception as e:
            continue

    log.info(f"Parquet 扫描完成: {len(symbol_data)} symbols")
    liquid = [s for s, d in symbol_data.items() if d['liquidity_ok']]
    log.info(f"流动性达标: {len(liquid)} 只")
    CACHE_FILE.write_text(json.dumps(symbol_data))
    return symbol_data, liquid

def _to_em_code(symbol):
    parts = symbol.split(":")
    if len(parts) != 2:
        return ""
    exchange, ticker = parts
    return ("SH" if exchange == "SSE" else "SZ") + ticker

_name_cache = {}

def get_stock_name(secucode):
    if secucode in _name_cache:
        return _name_cache[secucode]
    try:
        r = requests.get(
            "https://datacenter-web.eastmoney.com/api/data/v1/get",
            params={
                "reportName": "RPT_LICO_FN_CPD",
                "columns": "SECURITY_NAME_ABBR",
                "filter": f'(SECUCODE="{secucode}")',
                "pageSize": "1", "pageNumber": "1",
            },
            headers=HEADERS, timeout=6
        )
        name = ""
        if r.ok:
            d = r.json()
            if d.get("result") and d["result"].get("data"):
                name = d["result"]["data"][0].get("SECURITY_NAME_ABBR", "")
        _name_cache[secucode] = name
        return name
    except Exception:
        _name_cache[secucode] = ""
        return ""

def get_financial_data(symbol):
    em_code = _to_em_code(symbol)
    if not em_code:
        return None
    try:
        r = requests.get(EM_F10, params={"type": "0", "code": em_code}, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None
        result = r.json()
        pages = result.get("pages", 0)
        if not pages:
            return None

        all_data = []
        for page in range(1, min(pages, 4) + 1):
            r2 = requests.get(EM_F10, params={"type": "0", "code": em_code, "page": page}, headers=HEADERS, timeout=10)
            if r2.status_code != 200:
                break
            d = r2.json()
            all_data.extend(d.get("data", []))
            if page >= d.get("pages", 0):
                break
            time.sleep(0.05)

        if not all_data:
            return None

        roe_list = []
        yoy_eps_list = []
        for rec in all_data:
            roe = rec.get("ROEJQ")
            if roe is not None:
                roe_list.append({"period": str(rec.get("REPORT_DATE", ""))[:10], "roe": float(roe)})
            eps_tz = rec.get("EPSJBTZ")
            if eps_tz is not None:
                yoy_eps_list.append({"period": str(rec.get("REPORT_DATE", ""))[:10], "yoy_eps": float(eps_tz) / 100})

        return {"roe_list": roe_list, "yoy_eps_list": yoy_eps_list}
    except Exception:
        return None

def process_symbol(sym, symbol_data, scan_dt):
    info = symbol_data.get(sym, {})
    if not info.get('liquidity_ok'):
        return {"_type": "skip", "symbol": sym}

    rs_return = info.get('rs_return')

    fund = get_financial_data(sym)
    if not fund:
        return {"_type": "nodata", "symbol": sym}

    yoy_eps_list = fund.get("yoy_eps_list", [])
    roe_list = fund.get("roe_list", [])

    if not yoy_eps_list or not roe_list:
        return {"_type": "nodata", "symbol": sym}

    latest_yoy = yoy_eps_list[0].get("yoy_eps")
    if latest_yoy is None or latest_yoy < MIN_EPS_GROWTH:
        return {"_type": "nosignal", "symbol": sym, "reason": "eps_growth"}

    recent_12 = yoy_eps_list[:12]
    pos_count = sum(1 for g in recent_12 if (g.get("yoy_eps") or 0) > 0)
    if pos_count < MIN_POSITIVE_QUARTERS:
        return {"_type": "nosignal", "symbol": sym, "reason": "positive_quarters"}

    latest_roe = roe_list[0].get("roe", 0)
    if latest_roe < MIN_ROE:
        return {"_type": "nosignal", "symbol": sym, "reason": "roe"}

    score = 3 + 2 + 2
    if rs_return is not None and rs_return > 0:
        score += 2
    if latest_yoy >= 0.40:
        score += 1

    return {
        "_type": "candidate",
        "symbol": sym,
        "score": round(score, 1),
        "signals": {
            "eps_growth_yoy": round(latest_yoy, 4),
            "positive_quarters_12m": pos_count,
            "roe": round(latest_roe, 4),
            "rs_return_52w": round(rs_return, 4) if rs_return is not None else None,
        },
    }

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    parser.add_argument("--top", type=int, default=TOP_N)
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    scan_dt = date.fromisoformat(args.date) if args.date else (date.today() - timedelta(days=1))
    log.info(f"CANSLIM 扫描开始 date={scan_dt}")

    if args.reset or not CACHE_FILE.exists():
        symbol_data, liquid_symbols = scan_parquets(scan_dt)
    else:
        symbol_data = json.loads(CACHE_FILE.read_text())
        liquid_symbols = [s for s, d in symbol_data.items() if d['liquidity_ok']]
        log.info(f"使用缓存: {len(liquid_symbols)} 只流动性达标")

    log.info(f"待扫描: {len(liquid_symbols)} 只")

    candidates = []
    stats = {"nodata": 0, "nosignal": 0, "skip": 0}
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_symbol, sym, symbol_data, scan_dt): sym for sym in liquid_symbols}
        done = 0
        for future in as_completed(futures):
            result = future.result()
            done += 1
            if result["_type"] == "candidate":
                candidates.append(result)
            elif result["_type"] == "nodata":
                stats["nodata"] += 1
            elif result["_type"] == "nosignal":
                stats["nosignal"] += 1
            elif result["_type"] == "skip":
                stats["skip"] += 1

            if done % 50 == 0:
                elapsed = time.time() - t0
                rate = done / elapsed if elapsed > 0 else 0
                eta = (len(liquid_symbols) - done) / rate / 60 if rate > 0 else 0
                log.info(f"进度: {done}/{len(liquid_symbols)} candidates={len(candidates)} {rate:.1f}/s ETA={eta:.0f}min")

    log.info(f"扫描完成: {done} 只，candidates={len(candidates)}")

    # Ranking
    if candidates:
        rs_vals = {c["symbol"]: c["signals"].get("rs_return_52w") for c in candidates}
        valid_rs = sorted([v for v in rs_vals.values() if v is not None], reverse=True)
        if valid_rs:
            threshold_idx = min(int(len(valid_rs) * RS_TOP_PCT), max(0, len(valid_rs) - 1))
            rs_threshold = valid_rs[threshold_idx]
            for c in candidates:
                rs = c["signals"].get("rs_return_52w")
                if rs is not None and rs >= rs_threshold:
                    c["score"] = round(c["score"] + 2, 1)
                    c["signals"]["rs_top_20pct"] = True
                else:
                    c["signals"]["rs_top_20pct"] = False

    candidates.sort(key=lambda x: x["score"], reverse=True)
    top = candidates[:args.top]
    for i, c in enumerate(top, 1):
        c["rank"] = i
        c.pop("_type", None)

    output = {
        "scan_date": scan_dt.isoformat(),
        "candidates": top,
        "_stats": {"scanned": len(liquid_symbols), **stats},
    }

    out_path = Path('/root/.openclaw/workspace/trading-os/scripts/canslim_results.json')
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    log.info(f"写入: {out_path}")

    print(f"\n{'='*60}")
    print(f"CANSLIM 扫描  {scan_dt.isoformat()}")
    print(f"{'='*60}")
    for c in top:
        sym = c["symbol"]
        s = c["signals"]
        em = _to_em_code(sym); secucode = em[2:] + "." + em[:2]
        name = get_stock_name(secucode)
        rs_str = f"{s['rs_return_52w']:.1%}" if s.get('rs_return_52w') is not None else "N/A"
        print(f"#{c['rank']:2d} {sym} {name} score={c['score']:.0f} "
              f"EPS增长={s['eps_growth_yoy']:.1%} ROE={s['roe']:.2f}% "
              f"正季度={s['positive_quarters_12m']}/12 52W={rs_str}")
    print(f"\n符合: {len(top)}/30  (扫描 {stats['nodata']+stats['nosignal']} 只，无数据 {stats['nodata']} 只，不满足 {stats['nosignal']} 只)")

if __name__ == "__main__":
    main()
