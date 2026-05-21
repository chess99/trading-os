from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ...paths import repo_root


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
        import baostock as bs

        lg = bs.login()
        if lg.error_code != "0":
            raise RuntimeError(f"BaoStock 登录失败: {lg.error_msg}")
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
        return pairs
    except Exception as exc:
        print(f"BaoStock 获取股票列表失败: {exc}", file=sys.stderr)
        print("Fallback：使用本地已有股票列表...", file=sys.stderr)
        try:
            import duckdb
            from ...data.schema import Exchange

            root = repo_root()
            db_path = root / "data" / "lake.duckdb"
            con = duckdb.connect(str(db_path), read_only=True)
            rows = con.execute("SELECT DISTINCT symbol FROM bars ORDER BY symbol").fetchall()
            con.close()
            pairs = []
            for (sym,) in rows:
                if ":" not in sym:
                    continue
                exch_str, ticker = sym.split(":", 1)
                try:
                    exch_upper = exch_str.upper()
                    if exch_upper == "SSE" and (
                        ticker.startswith("000") or ticker.startswith("51") or ticker.startswith("56")
                        or ticker.startswith("58") or ticker.startswith("11") or ticker.startswith("13")
                    ):
                        continue
                    if exch_upper == "SZSE" and (
                        ticker.startswith("15") or ticker.startswith("16") or ticker.startswith("12")
                    ):
                        continue
                    pairs.append((Exchange(exch_upper), ticker))
                except ValueError:
                    pass
            print(f"Fallback 成功：从本地获取到 {len(pairs)} 只股票（已过滤ETF/指数）", file=sys.stderr)
            return pairs if pairs else None
        except Exception as fallback_exc:
            print(f"Fallback 也失败: {fallback_exc}", file=sys.stderr)
            return None


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
    }
    progress_path.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")


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
            failed=len(failed_list),
            elapsed=time.time() - _start_time,
            job_id=job_id,
            effective_date=effective_date,
            source=_source_name,
            status=status,
            started_at=started_at,
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

        start = ns.start or "2022-01-01"
        end = ns.end or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        effective_date = end
        _use_baostock = False
        try:
            import baostock as bs

            lg = bs.login()
            if lg.error_code == "0":
                _use_baostock = True
                bs.logout()
            else:
                print(f"BaoStock 不可用: {lg.error_msg}，切换到 akshare", file=sys.stderr)
        except Exception as exc:
            print(f"BaoStock 不可用: {exc}，切换到 akshare", file=sys.stderr)

        print(f"开始批量拉取 {len(pairs)} 只（{'BaoStock' if _use_baostock else 'akshare'}，串行）")
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
        )
        progress_started = True

        if _use_baostock:
            def _bs_login() -> bool:
                lg = bs.login()
                if lg.error_code != "0":
                    print(f"BaoStock 登录失败: {lg.error_msg}", file=sys.stderr)
                    return False
                return True

            if not _bs_login():
                terminal_status = "failed"
                return 1

        lake = LocalDataLake(root / "data")
        batch: list[pd.DataFrame] = []
        batch_num = 0
        reconnect_interval = 500
        source_counter: dict[str, int] = {}

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
                        failed_list.append(f"{sym}: DataIntegrityError - {e2}")
                        success -= 1
            batch = []

        query_interval = 0.4
        consecutive_failures = 0
        max_consecutive_failures = 5

        if _use_baostock:
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
                        df = query_bars_with_session(
                            bs,
                            ticker,
                            exchange=exch,
                            start=start,
                            end=end,
                            adjustment=adj,
                        )
                        if df.empty:
                            failed_list.append(f"{sym_id}: 空数据（停牌或未上市）")
                            consecutive_failures += 1
                        else:
                            batch.append(df)
                            success += 1
                            consecutive_failures = 0
                        time.sleep(query_interval)
                    except Exception as exc:
                        err = str(exc)[:80]
                        failed_list.append(f"{sym_id}: {err}")
                        consecutive_failures += 1
                        reconnect_keywords = (
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
                        need_reconnect = any(k in err.lower() for k in reconnect_keywords)
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
                            consecutive_failures = 0

                    if len(batch) >= batch_size:
                        _flush_batch()
                    if i % 100 == 0 or i == len(pairs):
                        print(f"  {i}/{len(pairs)}  成功={success}  失败={len(failed_list)}")
                        _write_bulk_progress(
                            progress_log,
                            done=i,
                            total=len(pairs),
                            success=success,
                            failed=len(failed_list),
                            elapsed=time.time() - _start_time,
                            job_id=job_id,
                            effective_date=effective_date,
                            source="baostock",
                            status="running",
                            started_at=started_at,
                        )
                _flush_batch()
            finally:
                bs.logout()
        else:
            from ...data.schema import Exchange as _Exch
            from ...data.sources.akshare_source import fetch_daily_bars as ak_fetch
            from ...data.sources.akshare_source import probe_and_get_preferred_source

            preferred = probe_and_get_preferred_source(_Exch.SSE)
            print(f"  源探测完成：首选 {preferred}，后续跳过不可用源", file=sys.stderr)
            if preferred == "none":
                print("所有数据源均不可用，无法拉取数据", file=sys.stderr)
                terminal_status = "failed"
                return 1

            _fetch_lock = threading.Lock()
            _max_workers = 5

            def _fetch_one(exch_ticker):
                exch, ticker = exch_ticker
                sym_id = f"{exch.value}:{ticker}"
                try:
                    df, actual_source = ak_fetch(
                        ticker,
                        exchange=exch,
                        start=start,
                        end=end,
                        adjustment=adj,
                    )
                    return sym_id, df, actual_source, None
                except Exception as exc:
                    return sym_id, None, None, str(exc)[:80]
                finally:
                    # Per-worker throttle: 5 workers × 0.4s ≈ 12.5 req/s total,
                    # staying well below eastmoney/sina rate limits.
                    time.sleep(query_interval)

            completed = 0
            with ThreadPoolExecutor(max_workers=_max_workers) as pool:
                futures = {pool.submit(_fetch_one, pair): pair for pair in pairs}
                for future in as_completed(futures):
                    sym_id, df, actual_source, err = future.result()
                    completed += 1
                    with _fetch_lock:
                        if err is not None:
                            failed_list.append(f"{sym_id}: {err}")
                            consecutive_failures += 1
                        elif df is None or df.empty:
                            failed_list.append(f"{sym_id}: 空数据")
                            consecutive_failures += 1
                        else:
                            batch.append(df)
                            success += 1
                            source_counter[actual_source] = source_counter.get(actual_source, 0) + 1
                            consecutive_failures = 0

                        if len(batch) >= batch_size:
                            _flush_batch()

                        if completed % 100 == 0 or completed == len(pairs):
                            src_summary = ", ".join(f"{k}={v}" for k, v in source_counter.items())
                            src_info = f"  [{src_summary}]" if src_summary else ""
                            print(
                                f"  {completed}/{len(pairs)}  成功={success}  "
                                f"失败={len(failed_list)}{src_info}"
                            )
                            _write_bulk_progress(
                                progress_log,
                                done=completed,
                                total=len(pairs),
                                success=success,
                                failed=len(failed_list),
                                elapsed=time.time() - _start_time,
                                job_id=job_id,
                                effective_date=effective_date,
                                source="akshare",
                                status="running",
                                started_at=started_at,
                            )
            _flush_batch()
    finally:
        if terminal_status is not None:
            _write_terminal_progress(terminal_status)
        elif progress_started and sys.exc_info()[0] is not None:
            _write_terminal_progress("failed")
        _release_bulk_lock(lock_path)

    lake.init()
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

    print(f"\n完成: 成功={success}, 失败={len(failed_list)}")
    _write_terminal_progress("success" if not failed_list else "failed")
    if failed_list and ns.verbose:
        print("失败列表（前 20 条）:")
        for item in failed_list[:20]:
            print(f"  {item}")
        if len(failed_list) > 20:
            print(f"  ... 还有 {len(failed_list) - 20} 条")
    return 0 if not failed_list else 1


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
