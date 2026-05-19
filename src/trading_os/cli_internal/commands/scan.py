from __future__ import annotations

import argparse
import sys
from datetime import date as date_type
from pathlib import Path

from ...paths import repo_root


def _run_scan(
    ns: argparse.Namespace,
    *,
    scanner_fn,
    system_name: str,
    lookback_days: int = 504,
    scanner_kwargs: dict | None = None,
) -> int:
    from datetime import timedelta
    import pandas as pd
    from ...data.lake import LocalDataLake
    from ...data.pipeline import DataPipeline
    from ...data.sources.akshare_factors import AkshareFactorSource
    from ...scan.common import filter_by_turnover, get_scan_symbols, get_stock_names, load_bars_batch, write_scan_output

    root = repo_root()
    scan_date = date_type.fromisoformat(ns.date) if ns.date else date_type.today() - timedelta(days=1)
    output_path = root / ns.output if ns.output else root / "artifacts" / "scan" / f"{system_name}-{scan_date.isoformat().replace('-', '')}.json"

    lake = LocalDataLake(root / "data")
    lake.init()
    pipeline = DataPipeline(lake)
    akshare = AkshareFactorSource()
    print(f"Scanning {system_name} signals for {scan_date}...")
    try:
        symbols, no_data = get_scan_symbols(pipeline, akshare, exchange=ns.exchange)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"  Local symbols: {len(symbols)} ({no_data} without local data)")

    batch_size = 500
    all_bars_parts = []
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        bars = load_bars_batch(pipeline, batch, scan_date=scan_date, lookback_days=lookback_days)
        if not bars.empty:
            all_bars_parts.append(bars)
    all_bars = pd.concat(all_bars_parts) if all_bars_parts else pd.DataFrame()
    if not all_bars.empty:
        symbols, low_turnover = filter_by_turnover(symbols, all_bars, min_amount=ns.min_turnover)
    else:
        low_turnover = len(symbols)
        symbols = []

    kwargs: dict = {"scan_date": scan_date, "top_n": ns.top}
    if scanner_kwargs:
        kwargs.update(scanner_kwargs)
    try:
        result = scanner_fn(symbols, all_bars, **kwargs)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("  获取股票名称...")
    name_cache = root / "data" / "stock_names.json"
    name_map = get_stock_names(cache_path=name_cache)
    missing = [c["symbol"] for c in result["candidates"] if c["symbol"] not in name_map]
    if missing:
        print(f"  发现 {len(missing)} 只未知股票，刷新名称缓存...")
        name_map = get_stock_names(cache_path=name_cache, max_age_days=0)
    for c in result["candidates"]:
        c["name"] = name_map.get(c["symbol"], "")

    output = {
        "effective_date": getattr(ns, "effective_date", None),
        "signal_date": scan_date.isoformat(),
        "scan_date": scan_date.isoformat(),
        "system": system_name,
        "total_scanned": len(symbols) + result["_stats"]["insufficient_data"] + result["_stats"]["no_signal"],
        "candidates": result["candidates"],
        "filtered_out": {
            "no_data": no_data,
            "low_turnover": low_turnover,
            "insufficient_data": result["_stats"]["insufficient_data"],
            "no_signal": result["_stats"]["no_signal"],
        },
    }
    if "metadata" in result:
        output["metadata"] = result["metadata"]
    write_scan_output(output, output_path)
    print(f"  Found {len(result['candidates'])} candidates → {output_path}")
    return 0


def _cmd_scan_elder(ns: argparse.Namespace) -> int:
    from ...scan.elder_scanner import scan_elder
    return _run_scan(ns, scanner_fn=scan_elder, system_name="elder", lookback_days=504)


def _cmd_fundamental_store(ns: argparse.Namespace) -> int:
    import json
    from ...data.sources.fundamental_source import get_financial_summary
    from ...scan.common import fundamental_path

    root = repo_root()
    (root / "data" / "fundamental").mkdir(parents=True, exist_ok=True)
    if ns.symbols:
        symbols = [s.strip() for s in ns.symbols.split(",")]
    else:
        try:
            from ...data.sources.akshare_factors import AkshareFactorSource
            from ...scan.common import to_canonical

            akshare = AkshareFactorSource()
            df = akshare.get_a_stock_list()
            symbols = [to_canonical(row["exchange"], row["symbol"]) for _, row in df.iterrows()]
        except Exception as exc:
            print(f"AKShare 不可用，请检查网络连接。错误：{exc}", file=sys.stderr)
            return 1

    success = failed = skipped = 0
    print(f"fundamental-store: processing {len(symbols)} symbols...")
    for i, sym in enumerate(symbols, 1):
        path = fundamental_path(root / "data", sym)
        if ns.skip_existing and path.exists():
            skipped += 1
            continue
        try:
            data = get_financial_summary(sym, years=ns.years)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            success += 1
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Failed %s: %s", sym, exc)
            failed += 1
        if i % 100 == 0:
            print(f"  Progress: {i}/{len(symbols)} (success={success}, failed={failed}, skipped={skipped})")
    print(f"\nDone: success={success}, failed={failed}, skipped={skipped}")
    return 0


def _cmd_scan_canslim(ns: argparse.Namespace) -> int:
    root = repo_root()
    if getattr(ns, "live", False):
        from ...scan.canslim_scanner import scan_canslim_live
        return _run_scan(ns, scanner_fn=scan_canslim_live, system_name="canslim", lookback_days=504, scanner_kwargs={"max_workers": getattr(ns, "workers", 3)})
    from ...scan.canslim_scanner import scan_canslim
    return _run_scan(ns, scanner_fn=scan_canslim, system_name="canslim", lookback_days=504, scanner_kwargs={"data_root": root / "data"})


def _cmd_scan_value(ns: argparse.Namespace) -> int:
    from ...scan.value_scanner import scan_value

    root = repo_root()
    return _run_scan(ns, scanner_fn=scan_value, system_name="value", lookback_days=756, scanner_kwargs={"data_root": root / "data", "mode": ns.mode})
