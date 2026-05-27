from __future__ import annotations

import argparse
import contextlib
import json
import os
import signal
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ...paths import repo_root


MIN_STOCK_UNIVERSE_SIZE = 5000


@contextlib.contextmanager
def _operation_timeout(seconds: int, message: str):
    def _handle_timeout(signum, frame):  # noqa: ARG001
        raise TimeoutError(message)

    if threading.current_thread() is not threading.main_thread():
        yield
        return
    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _handle_timeout)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)


def _cmd_paths(_: argparse.Namespace) -> int:
    root = repo_root()
    print(f"repo_root: {root}")
    print(f"docs:      {root / 'docs'}")
    print(f"data:      {root / 'data'}")
    print(f"artifacts: {root / 'artifacts'}")
    return 0


def _cmd_lake_init(_: argparse.Namespace) -> int:
    from ...data.lake import LocalDataLake

    root = repo_root()
    lake = LocalDataLake(root / "data")
    lake.init()
    print(f"Initialized lake at: {lake.paths.duckdb_path}")
    return 0


def _cmd_lake_compact(_: argparse.Namespace) -> int:
    from ...data.lake import LocalDataLake

    root = repo_root()
    lake = LocalDataLake(root / "data")
    n = lake.compact(threshold=0)
    if n == 0:
        print("没有数据需要 compact")
    else:
        print(f"Compact 完成，当前 {n} 个 Parquet 文件")
    return 0


def _cmd_fetch_bars(ns: argparse.Namespace) -> int:
    from ...data.lake import LocalDataLake
    from ...data.schema import Adjustment, AssetType, Exchange, Timeframe
    from ...data.sources.akshare_source import fetch_daily_bars

    root = repo_root()
    lake = LocalDataLake(root / "data")
    exch = Exchange(ns.exchange)
    adj = {"qfq": Adjustment.QFQ, "hfq": Adjustment.HFQ}.get(ns.adjustment, Adjustment.NONE)
    asset_type_map = {"equity": AssetType.EQUITY, "index": AssetType.INDEX, "etf": AssetType.ETF}
    asset_type = asset_type_map.get(getattr(ns, "asset_type", "equity"), AssetType.EQUITY)
    if asset_type == AssetType.INDEX:
        adj = Adjustment.NONE

    try:
        print(f"获取A股数据: {exch.value}:{ns.ticker} (复权: {adj.value}, 类型: {asset_type.value})")
        df, actual_source = fetch_daily_bars(
            ns.ticker,
            exchange=exch,
            start=ns.start,
            end=ns.end,
            adjustment=adj,
            asset_type=asset_type,
        )
        if df.empty:
            print("未获取到数据")
            return 1
        lake.write_bars_parquet(
            df,
            timeframe=Timeframe.D1,
            adjustment=adj,
            source=actual_source,
            partition_hint=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        )
        lake.init()
        source_note = f" (via {actual_source})" if actual_source not in ("none",) else ""
        print(f"写入 {len(df)} 条: {exch.value}:{ns.ticker}{source_note}")
        print(f"数据范围: {df['ts'].min().date()} 至 {df['ts'].max().date()}")
        return 0
    except Exception as e:
        print(f"获取A股数据失败: {e}", file=sys.stderr)
        return 1


def _cmd_lake_fix_index(ns: argparse.Namespace) -> int:
    from ...data.lake import LocalDataLake
    from ...data.schema import Adjustment, AssetType, Exchange, Timeframe
    from ...data.sources.akshare_source import fetch_daily_bars

    root = repo_root()
    lake = LocalDataLake(root / "data")
    symbol = ns.symbol
    exch_str, ticker = symbol.split(":", 1)
    exch = Exchange(exch_str)
    bars_glob = lake.paths.bars_dir.as_posix() + "/*.parquet"
    files = list(lake.paths.bars_dir.glob("*.parquet"))

    if not files:
        print(f"No parquet files found in {lake.paths.bars_dir}. Nothing to fix.")
        return 0

    with lake.connect() as con:
        try:
            audit = con.execute(
                f"""
                SELECT source, adjustment, COUNT(*) AS n,
                       MIN(ts::DATE) AS first, MAX(ts::DATE) AS last
                FROM read_parquet('{bars_glob}', union_by_name=true)
                WHERE symbol = ?
                GROUP BY source, adjustment
                ORDER BY source
                """,
                [symbol],
            ).df()
        except Exception:
            audit = None

    if audit is not None and not audit.empty:
        print(f"[lake-fix-index] Current state of {symbol}:")
        for _, row in audit.iterrows():
            print(f"  source={row['source']} adjustment={row['adjustment']} n={row['n']} {row['first']}~{row['last']}")
    else:
        print(f"[lake-fix-index] {symbol}: no existing data found.")

    if audit is not None and not audit.empty:
        non_clean = audit[~((audit["source"] == "akshare_index") & (audit["adjustment"] == "none"))]
        if non_clean.empty:
            print("[lake-fix-index] Already fully clean (only akshare_index/none). Nothing to do.")
            return 0

    print(f"[lake-fix-index] Removing ALL existing rows for {symbol}...")
    try:
        with lake.connect() as con:
            remaining_df = con.execute(
                f"""
                SELECT * FROM read_parquet('{bars_glob}', union_by_name=true)
                WHERE symbol != ?
                ORDER BY symbol, ts
                """,
                [symbol],
            ).df()
        clean_path = lake.paths.bars_dir / "bars_all_except_fixed_index.parquet"
        remaining_df.to_parquet(clean_path, index=False)
        for f in lake.paths.bars_dir.glob("*.parquet"):
            if f != clean_path:
                f.unlink()
        print(f"[lake-fix-index] Done. {len(remaining_df)} rows from other symbols retained.")
    except Exception as e:
        print(f"[lake-fix-index] ERROR during cleanup: {e}", file=sys.stderr)
        return 1

    print(f"[lake-fix-index] Re-fetching {symbol} full history via IndexHandler...")
    try:
        df, source = fetch_daily_bars(
            ticker,
            exchange=exch,
            start=None,
            end=None,
            adjustment=Adjustment.NONE,
            asset_type=AssetType.INDEX,
        )
        if df.empty:
            print(f"[lake-fix-index] WARNING: no data returned for {symbol}. Check network connectivity.")
            return 1

        lake.write_bars_parquet(
            df,
            timeframe=Timeframe.D1,
            adjustment=Adjustment.NONE,
            source=source,
            partition_hint=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        )
        lake.init()
        print(f"[lake-fix-index] Written {len(df)} records for {symbol} (source={source}, adjustment=none)")
        print(f"[lake-fix-index] Data range: {df['ts'].min().date()} to {df['ts'].max().date()}")
        print(f"[lake-fix-index] DONE. {symbol} now has a single clean series.")
        return 0
    except Exception as e:
        print(f"[lake-fix-index] ERROR during re-fetch: {e}", file=sys.stderr)
        return 1


def _stock_universe_cache_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / "artifacts" / "jobs" / "stock_universe_cache.json"


def _pair_to_cache_row(pair) -> dict[str, str]:
    exch, ticker = pair
    return {"exchange": exch.value, "ticker": ticker}


def _pairs_from_cache_rows(rows: list[dict]) -> list | None:
    from ...data.schema import Exchange

    pairs = []
    for row in rows:
        try:
            pairs.append((Exchange(str(row["exchange"]).upper()), str(row["ticker"])))
        except Exception:
            continue
    return pairs if len(pairs) >= MIN_STOCK_UNIVERSE_SIZE else None


def _load_stock_universe_cache(root: Path | None = None) -> list | None:
    path = _stock_universe_cache_path(root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    pairs = _pairs_from_cache_rows(data.get("pairs", []))
    if pairs is None:
        print(
            f"股票池 cache 无效：{path} 少于 {MIN_STOCK_UNIVERSE_SIZE} 只",
            file=sys.stderr,
        )
    return pairs


def _save_stock_universe_cache(pairs: list, root: Path | None = None) -> None:
    if len(pairs) < MIN_STOCK_UNIVERSE_SIZE:
        return
    path = _stock_universe_cache_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(pairs),
        "pairs": [_pair_to_cache_row(pair) for pair in pairs],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _fetch_baostock_universe(max_retries: int = 3) -> list:
    from ...data.schema import Exchange

    last_error: Exception | None = None
    for attempt in range(1, max(1, int(max_retries)) + 1):
        try:
            import time
            import baostock as bs

            with _operation_timeout(30, "BaoStock 获取股票列表超时"):
                lg = bs.login()
                if lg.error_code != "0":
                    raise RuntimeError(f"BaoStock 登录失败: {lg.error_msg}")
                _set_baostock_socket_timeout(30)
                rs = bs.query_stock_basic(code="", code_name="")
            pairs = []
            while rs.next():
                row = rs.get_row_data()
                code = row[0]
                stock_type = row[4]
                status = row[5]
                if stock_type != "1" or status != "1":
                    continue
                prefix, ticker = code.split(".")
                exch = Exchange.SSE if prefix == "sh" else Exchange.SZSE
                pairs.append((exch, ticker))
            bs.logout()
            if len(pairs) < MIN_STOCK_UNIVERSE_SIZE:
                raise RuntimeError(
                    f"BaoStock 股票列表过小: {len(pairs)} < {MIN_STOCK_UNIVERSE_SIZE}"
                )
            return pairs
        except Exception as exc:
            last_error = exc
            try:
                bs.logout()  # type: ignore[name-defined]
            except Exception:
                pass
            if attempt < max(1, int(max_retries)):
                time.sleep(min(2 ** (attempt - 1), 8))
    assert last_error is not None
    raise last_error


def _resolve_bulk_pairs(ns) -> list | None:
    from ...data.schema import Exchange

    if ns.tickers:
        pairs = []
        for sym in ns.tickers.split(","):
            sym = sym.strip()
            if ":" in sym:
                exch_str, ticker = sym.split(":", 1)
                pairs.append((Exchange(exch_str.upper()), ticker))
            else:
                print(f"跳过格式不正确的代码: {sym}（需要 SSE:600000 格式）", file=sys.stderr)
        return pairs

    try:
        pairs = _fetch_baostock_universe(max_retries=getattr(ns, "max_retries", 3))
        _save_stock_universe_cache(pairs)
        return pairs
    except Exception as exc:
        print(f"BaoStock 获取股票列表失败: {exc}", file=sys.stderr)
        cached = _load_stock_universe_cache()
        if cached is not None:
            print(f"Fallback：使用有效股票池 cache，共 {len(cached)} 只", file=sys.stderr)
            return cached
        print("股票池 cache 缺失或无效，无法安全执行 bulk refresh", file=sys.stderr)
        return None


def _set_baostock_socket_timeout(timeout: int) -> None:
    """Set BaoStock's module-level socket timeout when the session exists."""
    try:
        import baostock.common.context as _bs_ctx

        sock = getattr(_bs_ctx, "default_socket", None)
        if sock is not None:
            sock.settimeout(timeout)
    except Exception:
        pass


def _bulk_lock_path() -> Path:
    return repo_root() / "artifacts" / "fetch_bulk.pid"


def _bulk_progress_log_path() -> Path:
    return repo_root() / "artifacts" / "fetch_bulk_progress.log"


def _parse_bulk_lock(raw: str) -> dict:
    raw = raw.strip()
    if not raw:
        raise ValueError("empty lock")
    if raw.startswith("{"):
        data = json.loads(raw)
        data["pid"] = int(data["pid"])
        return data
    return {"pid": int(raw)}


def _acquire_bulk_lock(
    lock_path: Path,
    *,
    job_id: str | None = None,
    command: str | None = None,
    effective_date: str | None = None,
) -> None:
    if lock_path.exists():
        try:
            lock_data = _parse_bulk_lock(lock_path.read_text(encoding="utf-8"))
            pid = int(lock_data["pid"])
            os.kill(pid, 0)
            running_job = lock_data.get("job_id", "unknown")
            print(
                f"[fetch-ak-bulk] 已有实例在运行（job {running_job}, PID {pid}），拒绝启动。\n"
                f"  进度日志：{lock_path.parent / 'fetch_bulk_progress.log'}\n"
                f"  进度快照：{lock_path.parent / 'jobs' / 'current_fetch_bulk.json'}\n"
                f"  若确认进程已死，手动删除 {lock_path} 后重试。",
                file=sys.stderr,
            )
            sys.exit(1)
        except ProcessLookupError:
            lock_path.unlink(missing_ok=True)
        except PermissionError:
            pid_text = lock_path.read_text().strip()
            print(
                f"[fetch-ak-bulk] lock 文件存在（PID {pid_text}），进程属于其他用户，无法判断是否活跃。\n"
                f"  若确认可以继续，手动删除 {lock_path} 后重试。",
                file=sys.stderr,
            )
            sys.exit(1)
        except ValueError:
            lock_path.unlink(missing_ok=True)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_data = {
        "job_id": job_id or f"fetch-ak-bulk-{uuid4().hex[:12]}",
        "pid": os.getpid(),
        "command": command or "fetch-ak-bulk",
        "effective_date": effective_date,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    lock_path.write_text(json.dumps(lock_data, ensure_ascii=False, indent=2), encoding="utf-8")


def _release_bulk_lock(lock_path: Path) -> None:
    lock_path.unlink(missing_ok=True)


def _current_fetch_bulk_json_path(log_path: Path) -> Path:
    return log_path.parent / "jobs" / "current_fetch_bulk.json"


def _write_bulk_progress(
    log_path: Path,
    *,
    done: int,
    total: int,
    success: int,
    failed: int,
    elapsed: float,
    job_id: str | None = None,
    effective_date: str | None = None,
    source: str | None = None,
    status: str = "running",
    started_at: str | None = None,
    source_counts: dict[str, int] | None = None,
    retry_round: int | None = None,
    coverage_path: str | None = None,
) -> None:
    remaining = int((elapsed / done) * (total - done)) if done > 0 else None
    line = (
        f"[{datetime.now().strftime('%H:%M:%S')}] "
        f"{done}/{total}  success={success}  failed={failed}  "
        f"elapsed={int(elapsed)}s  eta={remaining if remaining is not None else 'unknown'}s\n"
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as f:
        f.write(line)
    progress_path = _current_fetch_bulk_json_path(log_path)
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    previous = {}
    if progress_path.exists():
        try:
            previous = json.loads(progress_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = {}
    progress = {
        "job_id": job_id or previous.get("job_id"),
        "effective_date": effective_date or previous.get("effective_date"),
        "total": total,
        "done": done,
        "success": success,
        "failed": failed,
        "started_at": started_at or previous.get("started_at"),
        "updated_at": now,
        "elapsed_sec": int(elapsed),
        "eta_sec": remaining,
        "source": source or previous.get("source"),
        "status": status,
        "source_counts": source_counts if source_counts is not None else previous.get("source_counts", {}),
        "retry_round": retry_round if retry_round is not None else previous.get("retry_round", 0),
        "coverage_path": coverage_path if coverage_path is not None else previous.get("coverage_path"),
    }
    progress_path.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")


def _bulk_coverage_path(effective_date: str, root: Path | None = None) -> Path:
    compact = effective_date.replace("-", "")
    return (root or repo_root()) / "artifacts" / "jobs" / f"bulk_coverage_{compact}.json"


def _is_network_error(message: str) -> bool:
    err = message.lower()
    return any(
        keyword in err
        for keyword in (
            "connection",
            "login",
            "socket",
            "timeout",
            "timed out",
            "reset",
            "broken pipe",
            "网络",
            "接收错误",
            "连接失败",
            "10002",
        )
    )


def _load_baostock_exceptions(symbols: list[str], effective_date: str) -> dict[str, dict]:
    if not symbols:
        return {}
    exceptions: dict[str, dict] = {}
    try:
        import baostock as bs

        lg = bs.login()
        if lg.error_code != "0":
            return {}
        _set_baostock_socket_timeout(30)
        for symbol in symbols:
            try:
                exch, ticker = symbol.split(":", 1)
                code = f"{'sh' if exch == 'SSE' else 'sz'}.{ticker}"
                rs = bs.query_stock_basic(code=code)
                rows = []
                while rs.error_code == "0" and rs.next():
                    rows.append(rs.get_row_data())
                if rows:
                    row = rows[0]
                    out_date = row[3]
                    status = row[5]
                    if status != "1" and out_date and out_date <= effective_date:
                        exceptions[symbol] = {
                            "status": "inactive",
                            "name": row[1],
                            "out_date": out_date,
                            "basic_status": status,
                        }
                        continue
                day = bs.query_history_k_data_plus(
                    code,
                    "date,tradestatus",
                    start_date=effective_date,
                    end_date=effective_date,
                    frequency="d",
                    adjustflag="3",
                )
                day_rows = []
                while day.error_code == "0" and day.next():
                    day_rows.append(day.get_row_data())
                if day_rows and len(day_rows[0]) >= 2 and day_rows[0][1] == "0":
                    exceptions[symbol] = {
                        "status": "suspended",
                        "trade_date": effective_date,
                        "tradestatus": "0",
                    }
            except Exception:
                continue
        bs.logout()
    except Exception:
        try:
            bs.logout()  # type: ignore[name-defined]
        except Exception:
            pass
    return exceptions


def _write_bulk_coverage_manifest(
    *,
    root: Path,
    effective_date: str,
    pairs: list,
    adjustment,
    source_counts: dict[str, int],
    failure_reasons: dict[str, str],
) -> Path:
    from ...data.lake import LocalDataLake
    from ...data.schema import Timeframe

    symbols = [f"{exch.value}:{ticker}" for exch, ticker in pairs]
    lake = LocalDataLake(root / "data")
    latest_by_symbol = lake.latest_bar_dates(
        symbols=symbols,
        timeframe=Timeframe.D1,
        adjustment=adjustment,
    )
    lagging = [
        symbol
        for symbol in symbols
        if latest_by_symbol.get(symbol) is None or latest_by_symbol[symbol] < effective_date
    ]
    exceptions = _load_baostock_exceptions(lagging, effective_date)
    rows = []
    status_counts = {"covered": 0, "inactive": 0, "suspended": 0, "failed": 0}
    for symbol in symbols:
        latest = latest_by_symbol.get(symbol)
        if latest is not None and latest >= effective_date:
            row = {"symbol": symbol, "status": "covered", "latest": latest}
        elif symbol in exceptions:
            row = {"symbol": symbol, "latest": latest, **exceptions[symbol]}
        else:
            row = {
                "symbol": symbol,
                "status": "failed",
                "latest": latest,
                "reason": failure_reasons.get(symbol, "missing effective_date coverage"),
            }
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
        rows.append(row)
    path = _bulk_coverage_path(effective_date, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "effective_date": effective_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(symbols),
        "status_counts": status_counts,
        "source_counts": source_counts,
        "symbols": rows,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _cmd_fetch_ak_bulk(ns: argparse.Namespace) -> int:
    import time
    import pandas as pd

    from ...data.lake import LocalDataLake
    from ...data.schema import Adjustment, Timeframe
    from ...data.sources.baostock_source import query_bars_with_session

    root = repo_root()
    lock_path = _bulk_lock_path()
    progress_log = _bulk_progress_log_path()
    job_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    job_id = f"fetch-ak-bulk-{job_stamp}-{uuid4().hex[:8]}"
    effective_date = ns.end or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    started_at = datetime.now(timezone.utc).isoformat()
    command = " ".join(
        [
            "fetch-ak-bulk",
            "--start",
            str(ns.start),
            "--end",
            str(ns.end),
            "--adjustment",
            str(ns.adjustment),
            "--source",
            str(getattr(ns, "source", "auto")),
        ]
    )
    _acquire_bulk_lock(lock_path, job_id=job_id, command=command, effective_date=effective_date)
    progress_log.unlink(missing_ok=True)
    _current_fetch_bulk_json_path(progress_log).unlink(missing_ok=True)
    _start_time = time.time()
    progress_started = False
    terminal_status: str | None = None
    terminal_written = False
    pairs: list = []
    success = 0
    failed_list: list[str] = []
    failure_reasons: dict[str, str] = {}
    successful_symbols: set[str] = set()
    source_counter: dict[str, int] = {}
    failed_pairs_for_retry: dict[str, tuple] = {}
    pairs_by_symbol: dict[str, tuple] = {}
    coverage_path_str: str | None = None
    retry_round = 0
    _source_name = "unknown"

    def _write_terminal_progress(status: str) -> None:
        nonlocal terminal_written
        if terminal_written:
            return
        pair_count = len(pairs) if pairs is not None else 0
        _write_bulk_progress(
            progress_log,
            done=pair_count,
            total=pair_count,
            success=success,
            failed=len(failed_pairs_for_retry),
            elapsed=time.time() - _start_time,
            job_id=job_id,
            effective_date=effective_date,
            source=_source_name,
            status=status,
            started_at=started_at,
            source_counts=source_counter,
            retry_round=retry_round,
            coverage_path=coverage_path_str,
        )
        terminal_written = True

    try:
        adj = {"qfq": Adjustment.QFQ, "hfq": Adjustment.HFQ}.get(ns.adjustment, Adjustment.NONE)
        batch_size = 200
        pairs = _resolve_bulk_pairs(ns)
        if pairs is None:
            terminal_status = "failed"
            return 1
        if not pairs:
            print("没有需要拉取的股票")
            terminal_status = "skipped"
            return 0

        if ns.skip_existing:
            lake_check = LocalDataLake(root / "data")
            lake_check.init()
            from ...data.pipeline import DataPipeline

            existing = set(DataPipeline(lake_check).available_symbols())
            before = len(pairs)
            pairs = [(e, t) for e, t in pairs if f"{e.value}:{t}" not in existing]
            print(f"--skip-existing: 跳过 {before - len(pairs)} 只已有数据，剩余 {len(pairs)} 只")

        if not pairs:
            print("没有需要拉取的股票")
            terminal_status = "skipped"
            return 0
        pairs_by_symbol = {f"{exch.value}:{ticker}": (exch, ticker) for exch, ticker in pairs}

        start = ns.start or "2022-01-01"
        end = ns.end or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        effective_date = end
        _use_baostock = False
        source_policy = getattr(ns, "source", "auto")
        max_retries = max(1, int(getattr(ns, "max_retries", 3)))
        retry_failed_rounds = max(0, int(getattr(ns, "retry_failed_rounds", 2)))
        max_workers = max(1, int(getattr(ns, "workers", 5)))
        if source_policy == "baostock":
            _use_baostock = True
        elif source_policy == "akshare":
            _use_baostock = False
        else:
            from ...data.schema import Exchange as _Exch
            from ...data.sources.akshare_source import probe_and_get_preferred_source

            preferred = probe_and_get_preferred_source(_Exch.SSE)
            print(f"  源探测完成：首选 {preferred}", file=sys.stderr)
            if preferred == "none":
                print("所有数据源均不可用，无法拉取数据", file=sys.stderr)
                terminal_status = "failed"
                return 1
            _use_baostock = preferred == "baostock"

        mode_label = "BaoStock，串行" if _use_baostock else "akshare，并发"
        print(f"开始批量拉取 {len(pairs)} 只（{mode_label}）")
        print(f"  日期范围: {start} ~ {end}，ETA 将按实际进度滚动计算")
        _source_name = "baostock" if _use_baostock else "akshare"
        _write_bulk_progress(
            progress_log,
            done=0,
            total=len(pairs),
            success=0,
            failed=0,
            elapsed=0,
            job_id=job_id,
            effective_date=effective_date,
            source="baostock" if _use_baostock else "akshare",
            status="running",
            started_at=started_at,
            source_counts={},
            retry_round=retry_round,
        )
        progress_started = True

        if _use_baostock:
            import baostock as bs

            def _bs_login() -> bool:
                try:
                    with _operation_timeout(30, "BaoStock 登录超时"):
                        lg = bs.login()
                        if lg.error_code != "0":
                            print(f"BaoStock 登录失败: {lg.error_msg}", file=sys.stderr)
                            return False
                        _set_baostock_socket_timeout(30)
                        return True
                except TimeoutError as exc:
                    print(str(exc), file=sys.stderr)
                    return False

            if not _bs_login():
                terminal_status = "failed"
                return 1

        lake = LocalDataLake(root / "data")
        batch: list[pd.DataFrame] = []
        batch_num = 0
        reconnect_interval = 500

        def _flush_batch() -> None:
            nonlocal batch, batch_num, success
            if not batch:
                return
            from ...data.exceptions import DataIntegrityError

            combined = pd.concat(batch, ignore_index=True)
            batch_num += 1
            actual_src = (
                combined["source"].iloc[0] if "source" in combined.columns else _source_name
            )
            try:
                lake.write_bars_parquet(
                    combined,
                    timeframe=Timeframe.D1,
                    adjustment=adj,
                    source=actual_src,
                    partition_hint=f"bulk_{batch_num:05d}",
                )
            except DataIntegrityError:
                for sym, sym_df in combined.groupby("symbol"):
                    sym_src = (
                        sym_df["source"].iloc[0] if "source" in sym_df.columns else _source_name
                    )
                    try:
                        lake.write_bars_parquet(
                            sym_df,
                            timeframe=Timeframe.D1,
                            adjustment=adj,
                            source=sym_src,
                            partition_hint=f"bulk_{batch_num:05d}_{sym.replace(':', '_')}",
                        )
                    except DataIntegrityError as e2:
                        if sym in successful_symbols:
                            successful_symbols.discard(sym)
                            success = max(0, success - 1)
                        failure_reasons[sym] = f"DataIntegrityError - {e2}"
                        if sym in pairs_by_symbol:
                            failed_pairs_for_retry[sym] = pairs_by_symbol[sym]
                        failed_list.append(f"{sym}: DataIntegrityError - {e2}")
            batch = []

        def _record_success(df: pd.DataFrame, actual_source: str | None) -> None:
            nonlocal success
            sym_id = str(df["symbol"].iloc[0]) if "symbol" in df.columns and not df.empty else ""
            batch.append(df)
            if sym_id and sym_id not in successful_symbols:
                successful_symbols.add(sym_id)
                success += 1
            if sym_id:
                failure_reasons.pop(sym_id, None)
                failed_pairs_for_retry.pop(sym_id, None)
            src = actual_source or (df["source"].iloc[0] if "source" in df.columns else _source_name)
            source_counter[str(src)] = source_counter.get(str(src), 0) + 1

        def _record_failure(pair, reason: str) -> None:
            sym_id = f"{pair[0].value}:{pair[1]}"
            if sym_id in successful_symbols:
                return
            failure_reasons[sym_id] = reason
            failed_pairs_for_retry[sym_id] = pair
            failed_list.append(f"{sym_id}: {reason}")

        def _progress_done() -> int:
            return min(len(pairs), len(successful_symbols) + len(failed_pairs_for_retry))

        def _write_running_progress(source: str) -> None:
            _write_bulk_progress(
                progress_log,
                done=_progress_done(),
                total=len(pairs),
                success=success,
                failed=len(failed_pairs_for_retry),
                elapsed=time.time() - _start_time,
                job_id=job_id,
                effective_date=effective_date,
                source=source,
                status="running",
                started_at=started_at,
                source_counts=source_counter,
                retry_round=retry_round,
            )

        def _run_akshare_round(target_pairs: list, round_no: int) -> None:
            from ...data.sources.akshare_source import fetch_daily_bars as ak_fetch

            if not target_pairs:
                return
            print(f"  akshare 补拉轮次 {round_no}: {len(target_pairs)} 只")
            _fetch_lock = threading.Lock()

            def _fetch_one(exch_ticker):
                exch, ticker = exch_ticker
                sym_id = f"{exch.value}:{ticker}"
                last_error = ""
                for attempt in range(1, max_retries + 1):
                    try:
                        df, actual_source = ak_fetch(
                            ticker,
                            exchange=exch,
                            start=start,
                            end=end,
                            adjustment=adj,
                        )
                        return exch_ticker, sym_id, df, actual_source, None
                    except Exception as exc:
                        last_error = str(exc)[:120]
                        if attempt < max_retries and _is_network_error(last_error):
                            time.sleep(min(2 ** (attempt - 1), 8))
                            continue
                        return exch_ticker, sym_id, None, None, last_error
                    finally:
                        time.sleep(query_interval)
                return exch_ticker, sym_id, None, None, last_error or "unknown error"

            completed = 0
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {pool.submit(_fetch_one, pair): pair for pair in target_pairs}
                for future in as_completed(futures):
                    pair, sym_id, df, actual_source, err = future.result()
                    completed += 1
                    with _fetch_lock:
                        if err is not None:
                            _record_failure(pair, err)
                        elif df is None or df.empty:
                            _record_failure(pair, "空数据")
                        else:
                            _record_success(df, actual_source)
                        if len(batch) >= batch_size:
                            _flush_batch()
                        if completed % 100 == 0 or completed == len(target_pairs):
                            src_summary = ", ".join(f"{k}={v}" for k, v in source_counter.items())
                            src_info = f"  [{src_summary}]" if src_summary else ""
                            print(
                                f"  {completed}/{len(target_pairs)}  成功={success}  "
                                f"待补={len(failed_pairs_for_retry)}{src_info}"
                            )
                            _write_running_progress("akshare")
            _flush_batch()

        query_interval = 0.4
        if _use_baostock:
            consecutive_failures = 0
            max_consecutive_failures = 5
            try:
                for i, (exch, ticker) in enumerate(pairs, 1):
                    if i > 1 and (i - 1) % reconnect_interval == 0:
                        bs.logout()
                        time.sleep(2)
                        if not _bs_login():
                            print(f"重连失败，已处理 {i-1} 只，中止", file=sys.stderr)
                            break

                    sym_id = f"{exch.value}:{ticker}"
                    try:
                        df = pd.DataFrame()
                        last_error = ""
                        for attempt in range(1, max_retries + 1):
                            try:
                                with _operation_timeout(30, f"BaoStock 查询超时 {sym_id}"):
                                    df = query_bars_with_session(
                                        bs,
                                        ticker,
                                        exchange=exch,
                                        start=start,
                                        end=end,
                                        adjustment=adj,
                                    )
                                break
                            except Exception as exc:
                                last_error = str(exc)[:120]
                                if attempt < max_retries and _is_network_error(last_error):
                                    time.sleep(min(2 ** (attempt - 1), 8))
                                    continue
                                raise
                        if df.empty:
                            _record_failure((exch, ticker), "空数据（停牌或未上市）")
                            consecutive_failures += 1
                        else:
                            _record_success(df, "baostock")
                            consecutive_failures = 0
                        time.sleep(query_interval)
                    except Exception as exc:
                        err = str(exc)[:120]
                        _record_failure((exch, ticker), err)
                        consecutive_failures += 1
                        need_reconnect = _is_network_error(err)
                        if not need_reconnect and consecutive_failures >= max_consecutive_failures:
                            need_reconnect = True
                            print(f"  连续失败 {consecutive_failures} 次，强制重连")
                        if need_reconnect:
                            print(f"  连接异常，重连 BaoStock ({sym_id}): {err}")
                            try:
                                bs.logout()
                            except Exception:
                                pass
                            time.sleep(3)
                            _bs_login()
                            if source_policy == "auto" and consecutive_failures >= max_consecutive_failures:
                                remaining = pairs[i:]
                                for pair in remaining:
                                    failed_pairs_for_retry[f"{pair[0].value}:{pair[1]}"] = pair
                                print(
                                    f"  BaoStock 连续网络异常，剩余 {len(remaining)} 只切换 akshare 补拉",
                                    file=sys.stderr,
                                )
                                break
                            consecutive_failures = 0

                    if len(batch) >= batch_size:
                        _flush_batch()
                    if i % 100 == 0 or i == len(pairs):
                        print(f"  {i}/{len(pairs)}  成功={success}  待补={len(failed_pairs_for_retry)}")
                        _write_running_progress("baostock")
                _flush_batch()
            finally:
                bs.logout()
        else:
            if source_policy == "akshare":
                preferred = "akshare"
            else:
                from ...data.sources.akshare_source import probe_and_get_preferred_source

                preferred = probe_and_get_preferred_source(pairs[0][0])
                print(f"  源探测完成：首选 {preferred}，后续跳过不可用源", file=sys.stderr)
                if preferred == "none":
                    print("所有数据源均不可用，无法拉取数据", file=sys.stderr)
                    terminal_status = "failed"
                    return 1
            _run_akshare_round(pairs, 0)

        for extra_round in range(1, retry_failed_rounds + 1):
            retry_targets = list(failed_pairs_for_retry.values())
            if not retry_targets:
                break
            retry_round = extra_round
            _run_akshare_round(retry_targets, extra_round)
    finally:
        if terminal_status is not None:
            _write_terminal_progress(terminal_status)
        elif progress_started and sys.exc_info()[0] is not None:
            _write_terminal_progress("failed")
        _release_bulk_lock(lock_path)

    lake.init()
    coverage_failed_count: int | None = None
    try:
        from datetime import date as _date
        from datetime import timedelta as _timedelta
        from ...data.calendar import WeekdayCalendar as _Cal

        _con = lake.connect()
        _row = _con.execute("SELECT MAX(ts)::DATE as latest FROM bars WHERE timeframe='1d' AND adjustment=?", [adj.value]).fetchone()
        _con.close()
        if _row and _row[0]:
            _latest = _row[0]
            _today = _date.today()
            _cal = _Cal()
            _trading_lag = sum(1 for _i in range(1, (_today - _latest).days + 1) if _cal.is_trading_day(_latest + _timedelta(days=_i)))
            _status = "✓ 今日数据已就绪" if _trading_lag == 0 else f"⚠️  落后 {_trading_lag} 个交易日（最新 {_latest}，今日 {_today}）"
            print(f"数据截止: {_latest}  [{_status}]")
    except Exception:
        pass

    try:
        coverage_path = _write_bulk_coverage_manifest(
            root=root,
            effective_date=effective_date,
            pairs=pairs,
            adjustment=adj,
            source_counts=source_counter,
            failure_reasons=failure_reasons,
        )
        coverage_path_str = str(coverage_path)
        coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
        coverage_failed_count = int(coverage.get("status_counts", {}).get("failed", 0))
    except Exception as exc:
        coverage_failed_count = len(failed_pairs_for_retry) or 1
        print(f"coverage manifest 写入失败: {exc}", file=sys.stderr)

    final_failed = coverage_failed_count if coverage_failed_count is not None else len(failed_pairs_for_retry)
    print(f"\n完成: 成功={success}, 失败={final_failed}")
    _write_terminal_progress("success" if final_failed == 0 else "failed")
    if final_failed and ns.verbose:
        print("失败列表（前 20 条）:")
        for sym_id, reason in list(failure_reasons.items())[:20]:
            print(f"  {sym_id}: {reason}")
        if len(failure_reasons) > 20:
            print(f"  ... 还有 {len(failure_reasons) - 20} 条")
    return 0 if final_failed == 0 else 1


def _cmd_fetch_yf(ns: argparse.Namespace) -> int:
    from ...data.lake import LocalDataLake
    from ...data.schema import Adjustment, Exchange, Timeframe
    from ...data.sources.yfinance_source import fetch_daily_bars

    root = repo_root()
    lake = LocalDataLake(root / "data")
    exch = Exchange(ns.exchange)
    df = fetch_daily_bars(ns.ticker, exchange=exch, start=ns.start, end=ns.end)
    if df.empty:
        print("No data fetched.")
        return 1
    lake.write_bars_parquet(
        df,
        timeframe=Timeframe.D1,
        adjustment=Adjustment.NONE,
        source="yfinance",
        partition_hint=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
    )
    lake.init()
    print(f"Wrote {len(df)} rows for {exch.value}:{ns.ticker}")
    return 0


def _cmd_seed(ns: argparse.Namespace) -> int:
    from ...data.lake import LocalDataLake
    from ...data.schema import Adjustment, Exchange, Timeframe
    from ...data.sources.synthetic_source import make_daily_bars

    root = repo_root()
    lake = LocalDataLake(root / "data")
    exch = Exchange(ns.exchange)
    df = make_daily_bars(ns.ticker, exchange=exch).head(int(ns.days))
    lake.write_bars_parquet(
        df,
        timeframe=Timeframe.D1,
        adjustment=Adjustment.NONE,
        source="synthetic",
        partition_hint=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
    )
    lake.init()
    print(f"Seeded {len(df)} rows for {exch.value}:{ns.ticker}")
    return 0


def _cmd_query_bars(ns: argparse.Namespace) -> int:
    from ...data.lake import LocalDataLake
    from ...data.schema import Adjustment, Exchange, Timeframe

    root = repo_root()
    lake = LocalDataLake(root / "data")
    exch = Exchange(ns.exchange) if ns.exchange else None
    symbols = [s.strip() for s in ns.symbols.split(",")] if ns.symbols else None
    df = lake.query_bars(
        symbols=symbols,
        exchange=exch,
        timeframe=Timeframe(ns.timeframe),
        adjustment=Adjustment(ns.adjustment),
        start=ns.start,
        end=ns.end,
        limit=ns.limit,
    )
    print(df)
    return 0
