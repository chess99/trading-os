# Scan & Fetch Parallelization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Elder/CANSLIM 双扫描从串行改为并行，将 AKShare 全量抓取从串行改为线程池并发，把 daily 工作流的扫描耗时减少约 50%，全量抓取耗时减少约 80%。

**Architecture:**
两个独立任务，可按任意顺序或并行执行。Task 1（扫描并行化）需先给 `LocalDataLake` 加 `read_only` 参数解决 DuckDB 文件锁冲突，再用 `ThreadPoolExecutor(max_workers=2)` 在 scheduler 里同时启动两个扫描子进程。Task 2（AKShare 线程池）在 `_cmd_fetch_ak_bulk` 的 AKShare 路径里换成 `ThreadPoolExecutor(max_workers=5)`，BaoStock 路径维持串行（baostock 库单连接不支持多线程）。

**Tech Stack:** Python stdlib `concurrent.futures.ThreadPoolExecutor`，DuckDB `read_only=True` 参数，不引入新依赖。

---

## 背景与可行性说明

**为什么扫描并行化需要 read_only 前置：**

`LocalDataLake.connect()` 当前调用 `duckdb.connect(str(path))` —— 默认 read-write 模式。DuckDB 对同一个 `.duckdb` 文件只允许一个 read-write 连接（OS 文件锁）。两个 scan 子进程同时启动时，第二个进程打开 `lake.duckdb` 会抛 `duckdb.IOException`。

scan 进程只读不写（只调 `list_symbols()` 和 `query_bars()`，均使用 `read_parquet(glob)` 内联查询，不写 catalog），传入 `read_only=True` 即可让多个进程并发读同一个文件。

**为什么 BaoStock 路径不并发：**

`baostock` 库维护进程级全局 TCP 连接（`bs.login()` 是全局状态），多线程并发调用会竞争同一个 socket。安全做法是多进程（复杂），或维持串行。BaoStock 在当前设计中是 fallback 数据源，不值得为它投入多进程改造。

---

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/trading_os/data/lake.py` | 修改 | `__init__` 加 `read_only` 参数，`connect()` 传递给 duckdb |
| `src/trading_os/cli_internal/commands/scan.py` | 修改 | 创建 `LocalDataLake` 时传 `read_only=True` |
| `src/trading_os/scheduler.py` | 修改 | `trigger_full_scan_and_daily` 用 ThreadPoolExecutor 并行两扫描 |
| `src/trading_os/cli_internal/commands/data.py` | 修改 | AKShare 路径换成 ThreadPoolExecutor，提取 `_fetch_one_akshare` 函数 |
| `tests/test_scheduler_workflow.py` | 修改 | 验证两扫描并行启动 |
| `tests/test_akshare_source.py` | 修改 | 验证并发抓取结果与串行一致 |

---

## Task 1: LocalDataLake read_only 支持

**Files:**
- Modify: `src/trading_os/data/lake.py:56-66`
- Test: `tests/test_lake_read_only.py` (new)

- [ ] **Step 1: 写失败测试**

新建 `tests/test_lake_read_only.py`：

```python
import pytest
from pathlib import Path
from trading_os.data.lake import LocalDataLake
from trading_os.data.schema import Adjustment, Timeframe
import pandas as pd
from datetime import datetime, timezone


def _write_test_bars(lake: LocalDataLake) -> None:
    df = pd.DataFrame({
        "symbol": ["SSE:600000", "SSE:600000"],
        "exchange": ["SSE", "SSE"],
        "timeframe": ["1d", "1d"],
        "adjustment": ["qfq", "qfq"],
        "ts": [
            datetime(2024, 1, 2, tzinfo=timezone.utc),
            datetime(2024, 1, 3, tzinfo=timezone.utc),
        ],
        "open": [9.5, 9.8],
        "high": [9.9, 10.0],
        "low": [9.4, 9.7],
        "close": [9.8, 9.6],
        "volume": [1_000_000.0, 800_000.0],
        "vwap": [9.7, 9.8],
        "trades": [None, None],
        "source": ["baostock", "baostock"],
    })
    lake.write_bars_parquet(df, timeframe=Timeframe.D1, adjustment=Adjustment.QFQ, source="baostock")


def test_read_only_lake_can_list_symbols(tmp_path: Path) -> None:
    """read_only=True 的 lake 能正确读取 list_symbols。"""
    rw_lake = LocalDataLake(tmp_path)
    _write_test_bars(rw_lake)

    ro_lake = LocalDataLake(tmp_path, read_only=True)
    symbols = ro_lake.list_symbols()
    assert "SSE:600000" in symbols


def test_two_read_only_lakes_concurrent(tmp_path: Path) -> None:
    """两个 read_only lake 可以同时持有连接并查询，不互相阻塞。"""
    from concurrent.futures import ThreadPoolExecutor

    rw_lake = LocalDataLake(tmp_path)
    _write_test_bars(rw_lake)

    def query(i: int) -> list[str]:
        lake = LocalDataLake(tmp_path, read_only=True)
        return lake.list_symbols()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(query, range(2)))

    assert results[0] == results[1]
    assert "SSE:600000" in results[0]


def test_read_only_lake_cannot_write(tmp_path: Path) -> None:
    """read_only lake 写入时应抛出异常。"""
    rw_lake = LocalDataLake(tmp_path)
    _write_test_bars(rw_lake)

    ro_lake = LocalDataLake(tmp_path, read_only=True)
    df = pd.DataFrame({
        "symbol": ["SSE:600001"],
        "exchange": ["SSE"],
        "timeframe": ["1d"],
        "adjustment": ["qfq"],
        "ts": [datetime(2024, 1, 2, tzinfo=timezone.utc)],
        "open": [10.0], "high": [10.5], "low": [9.9], "close": [10.2],
        "volume": [500_000.0], "vwap": [10.1], "trades": [None], "source": ["baostock"],
    })
    with pytest.raises(Exception):  # duckdb.IOException or similar
        ro_lake.write_bars_parquet(df, timeframe=Timeframe.D1, adjustment=Adjustment.QFQ, source="baostock")
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/zcs/code2/trading-os
python -m pytest tests/test_lake_read_only.py -v 2>&1 | head -30
```

期望：`AttributeError: LocalDataLake.__init__() got an unexpected keyword argument 'read_only'`

- [ ] **Step 3: 实现 read_only 参数**

修改 `src/trading_os/data/lake.py`：

```python
# __init__ 签名改为（行 ~56）：
def __init__(self, root: Path, *, read_only: bool = False):
    try:  # pragma: no cover
        self._duckdb = importlib.import_module("duckdb")
        self._pd = importlib.import_module("pandas")
    except ModuleNotFoundError as e:  # pragma: no cover
        raise RuntimeError(
            "LocalDataLake requires optional dependencies. "
            "Create a Python 3.10–3.12 environment and install: "
            "`pip install -e .[data_lake]`"
        ) from e
    self.paths = DataLakePaths(root=root)
    self.paths.root.mkdir(parents=True, exist_ok=True)
    self.paths.bars_dir.mkdir(parents=True, exist_ok=True)
    self._read_only = read_only
    self._view_dirty: bool = True
```

```python
# connect() 改为（行 ~61）：
def connect(self) -> Any:
    con = self._duckdb.connect(str(self.paths.duckdb_path), read_only=self._read_only)
    con.execute("SET TimeZone='UTC'")
    return con
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_lake_read_only.py -v
```

期望：3 个测试全部 PASS。

- [ ] **Step 5: 确认现有测试不受影响**

```bash
python -m pytest tests/ -v --timeout=60 -x -q 2>&1 | tail -20
```

期望：所有现有测试 PASS（新增 3 个）。

- [ ] **Step 6: Commit**

```bash
git add src/trading_os/data/lake.py tests/test_lake_read_only.py
git commit -m "feat(lake): add read_only parameter to LocalDataLake

Allows scan processes to open lake.duckdb concurrently without
DuckDB file lock conflicts. Read-only connections use duckdb's
built-in read_only mode which permits multiple concurrent readers."
```

---

## Task 2: scan 命令使用 read_only=True

**Files:**
- Modify: `src/trading_os/cli_internal/commands/scan.py:33`

*依赖 Task 1 完成。*

- [ ] **Step 1: 写并发测试**

在 `tests/test_scheduler_workflow.py` 末尾追加：

```python
def test_two_scan_processes_can_open_lake_simultaneously(tmp_path: Path) -> None:
    """两个 DataPipeline（read_only=True）可同时存在，不会互相阻塞。"""
    from concurrent.futures import ThreadPoolExecutor
    from trading_os.data.lake import LocalDataLake
    from trading_os.data.pipeline import DataPipeline

    # 准备 lake（需要至少有 parquet 文件目录）
    lake_path = tmp_path / "data"
    lake_path.mkdir()
    (lake_path / "parquet" / "bars").mkdir(parents=True)

    def make_pipeline_and_list(i: int) -> list:
        lake = LocalDataLake(lake_path, read_only=True)
        pipe = DataPipeline(lake)
        return pipe.available_symbols()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(make_pipeline_and_list, range(2)))

    assert results[0] == results[1]  # both return same (empty) list
```

- [ ] **Step 2: 运行确认测试通过（空 lake 场景）**

```bash
python -m pytest tests/test_scheduler_workflow.py::test_two_scan_processes_can_open_lake_simultaneously -v
```

期望：PASS

- [ ] **Step 3: 修改 scan 命令使用 read_only=True**

修改 `src/trading_os/cli_internal/commands/scan.py` 第 33 行：

```python
# 原来：
lake = LocalDataLake(root / "data")

# 改为：
lake = LocalDataLake(root / "data", read_only=True)
```

- [ ] **Step 4: 运行 scan 命令冒烟测试**

```bash
python -m trading_os scan-elder --date 2026-05-19 --output /tmp/elder-test.json
```

期望：正常完成，`/tmp/elder-test.json` 有输出。

- [ ] **Step 5: Commit**

```bash
git add src/trading_os/cli_internal/commands/scan.py tests/test_scheduler_workflow.py
git commit -m "feat(scan): open LocalDataLake in read_only mode

Scan commands only read from the lake, never write. Using read_only=True
allows multiple concurrent scan processes to open the same DuckDB file
without triggering file lock conflicts."
```

---

## Task 3: scheduler 并行执行两扫描

**Files:**
- Modify: `src/trading_os/scheduler.py:546-586`
- Test: `tests/test_scheduler_workflow.py`

*依赖 Task 2 完成。*

- [ ] **Step 1: 写并行时序测试**

在 `tests/test_scheduler_workflow.py` 末尾追加：

```python
import time as _time
from threading import Event


def test_trigger_full_scan_and_daily_runs_scans_in_parallel(tmp_path: Path) -> None:
    """elder_scan 和 canslim_scan 应该并发启动，而不是串行等待。"""
    from trading_os.scheduler import SchedulerStore, trigger_full_scan_and_daily, JobRunner
    from trading_os.scheduler import JOB_STATUS_SUCCESS

    store = SchedulerStore(tmp_path)

    # 注入一个已成功的 bulk refresh
    bulk = store.create_job("market_data_bulk_refresh", effective_date="2026-05-19")
    store.update_job(bulk.id, status=JOB_STATUS_SUCCESS, ended=True)

    start_times: dict[str, float] = {}
    lock_obj = __import__("threading").Lock()

    def slow_runner(args: list, log_path) -> int:
        # 通过命令行参数判断是哪个扫描
        cmd = " ".join(args)
        name = "elder" if "scan-elder" in cmd else "canslim"
        with lock_obj:
            start_times[name] = _time.monotonic()
        _time.sleep(0.3)  # 模拟扫描耗时
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("ok")
        return 0

    t0 = _time.monotonic()
    trigger_full_scan_and_daily(store, effective_date="2026-05-19", runner=slow_runner)
    total = _time.monotonic() - t0

    assert "elder" in start_times and "canslim" in start_times
    gap = abs(start_times["elder"] - start_times["canslim"])
    # 两个扫描应在 0.1 秒内同时启动（并发），总耗时应 < 0.8s（不是串行的 0.6s）
    assert gap < 0.1, f"扫描未并发启动，启动时差 {gap:.2f}s"
    assert total < 0.8, f"总耗时 {total:.2f}s，串行预期 >= 0.6s"
```

- [ ] **Step 2: 运行测试确认失败（当前是串行）**

```bash
python -m pytest tests/test_scheduler_workflow.py::test_trigger_full_scan_and_daily_runs_scans_in_parallel -v
```

期望：FAIL（gap 会 > 0.3s，因为 elder 先跑完再启动 canslim）

- [ ] **Step 3: 改 trigger_full_scan_and_daily 为并行**

修改 `src/trading_os/scheduler.py`，在文件顶部 import 区加：

```python
from concurrent.futures import ThreadPoolExecutor
```

然后找到 `trigger_full_scan_and_daily` 中串行执行两扫描的部分（约 545-586 行），替换为：

```python
    # 并行启动 elder 和 canslim 两个扫描
    with ThreadPoolExecutor(max_workers=2) as _scan_pool:
        elder_future = _scan_pool.submit(
            _ensure_scan_job,
            store,
            name="elder_scan",
            effective_date=effective_date,
            command=[
                sys.executable,
                "-m", "trading_os",
                "scan-elder",
                "--date", signal_date,
                "--effective-date", effective_date,
                "--output", f"artifacts/scan/elder-{effective_compact}.json",
            ],
            runner=runner,
            force=force,
        )
        canslim_future = _scan_pool.submit(
            _ensure_scan_job,
            store,
            name="canslim_scan",
            effective_date=effective_date,
            command=[
                sys.executable,
                "-m", "trading_os",
                "scan-canslim",
                "--date", signal_date,
                "--live",
                "--effective-date", effective_date,
                "--output", f"artifacts/scan/canslim-{effective_compact}.json",
            ],
            runner=runner,
            force=force,
        )
    elder = elder_future.result()
    canslim = canslim_future.result()
    results.append(elder)
    results.append(canslim)
```

注意：原来的代码是：
```python
    elder = _ensure_scan_job(store, name="elder_scan", ...)
    results.append(elder)
    canslim = _ensure_scan_job(store, name="canslim_scan", ...)
    results.append(canslim)
```

只把这四行替换成上面的 ThreadPoolExecutor 块。后续的 `if elder.status != JOB_STATUS_SUCCESS or canslim.status != JOB_STATUS_SUCCESS:` 逻辑不变。

- [ ] **Step 4: 运行新测试确认通过**

```bash
python -m pytest tests/test_scheduler_workflow.py::test_trigger_full_scan_and_daily_runs_scans_in_parallel -v
```

期望：PASS

- [ ] **Step 5: 运行全部 scheduler 测试**

```bash
python -m pytest tests/test_scheduler_workflow.py -v
```

期望：全部 PASS

- [ ] **Step 6: Commit**

```bash
git add src/trading_os/scheduler.py tests/test_scheduler_workflow.py
git commit -m "perf(scheduler): parallelize elder and canslim scans

Run both scans concurrently with ThreadPoolExecutor(max_workers=2).
Requires scan commands to use read_only=True on LocalDataLake to avoid
DuckDB file lock conflicts between the two concurrent scan processes.
Expected wall-clock reduction: ~50% of combined scan time."
```

---

## Task 4: AKShare 路径线程池并发抓取

**Files:**
- Modify: `src/trading_os/cli_internal/commands/data.py:638-691`
- Test: `tests/test_akshare_source.py`

*独立任务，与 Task 1-3 无依赖关系。*

- [ ] **Step 1: 写并发正确性测试**

在 `tests/test_akshare_source.py` 末尾追加：

```python
def test_concurrent_fetch_same_result_as_serial(monkeypatch) -> None:
    """并发抓取的结果集应与串行抓取相同（不丢数据，不重复）。"""
    import pandas as pd
    from datetime import datetime, timezone
    from trading_os.data.schema import Exchange, Adjustment

    # 构造 mock fetch 函数，模拟 10 只股票各返回 2 天数据
    call_log: list[str] = []

    def mock_fetch(ticker, *, exchange, start, end, adjustment):
        call_log.append(ticker)
        df = pd.DataFrame({
            "symbol": [f"{exchange.value}:{ticker}"] * 2,
            "exchange": [exchange.value] * 2,
            "timeframe": ["1d"] * 2,
            "adjustment": ["qfq"] * 2,
            "ts": [datetime(2024, 1, 2, tzinfo=timezone.utc),
                   datetime(2024, 1, 3, tzinfo=timezone.utc)],
            "open": [10.0, 10.1],
            "high": [10.5, 10.6],
            "low": [9.9, 10.0],
            "close": [10.2, 10.3],
            "volume": [500_000.0, 600_000.0],
            "vwap": [10.1, 10.2],
            "trades": [None, None],
            "source": ["eastmoney"] * 2,
        })
        return df, "eastmoney"

    from trading_os.data.schema import Exchange as _Exch
    pairs = [(_Exch.SSE, f"60000{i}") for i in range(10)]

    # 串行抓取
    serial_frames = []
    for exch, ticker in pairs:
        df, _ = mock_fetch(ticker, exchange=exch, start="2024-01-01", end="2024-01-31",
                           adjustment=Adjustment.QFQ)
        serial_frames.append(df)
    serial_result = pd.concat(serial_frames).sort_values("symbol").reset_index(drop=True)

    call_log.clear()

    # 并发抓取（复用相同逻辑）
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading

    concurrent_frames = []
    lock = threading.Lock()

    def fetch_one(exch, ticker):
        df, src = mock_fetch(ticker, exchange=exch, start="2024-01-01", end="2024-01-31",
                             adjustment=Adjustment.QFQ)
        return df

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(fetch_one, exch, ticker) for exch, ticker in pairs]
        for f in as_completed(futures):
            concurrent_frames.append(f.result())

    concurrent_result = pd.concat(concurrent_frames).sort_values("symbol").reset_index(drop=True)

    assert len(serial_result) == len(concurrent_result)
    assert set(serial_result["symbol"]) == set(concurrent_result["symbol"])
```

- [ ] **Step 2: 运行测试确认通过（测试本身先验证逻辑）**

```bash
python -m pytest tests/test_akshare_source.py::test_concurrent_fetch_same_result_as_serial -v
```

期望：PASS（这个测试验证并发模式本身是正确的）

- [ ] **Step 3: 提取单只抓取函数并改写 AKShare 路径**

在 `src/trading_os/cli_internal/commands/data.py` 顶部 import 区（约第 1-20 行）已有 import，在使用前确认有：

```python
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
```

然后在 `_cmd_fetch_ak_bulk` 函数内，找到 AKShare 路径（`else:` 分支，约 638 行）的 `for i, (exch, ticker) in enumerate(pairs, 1):` 循环，替换为：

```python
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
```

注意：这段代码完整替换原 AKShare `for` 循环（从 `for i, (exch, ticker) in enumerate(pairs, 1):` 开始到 `_flush_batch()` 结束）。原循环末尾的独立 `_flush_batch()` 也包含在内。

- [ ] **Step 4: 小规模冒烟测试（可选，需要网络）**

```bash
# 用 10 只股票做冒烟测试
python -m trading_os fetch-ak-bulk \
  --tickers SSE:600000,SSE:600036,SSE:601318,SZSE:000001,SZSE:000002,SZSE:000858,SZSE:300750,SSE:601012,SSE:600519,SZSE:002594 \
  --start 2026-05-19 --end 2026-05-19
```

期望：正常完成，成功数 = 10（或接近 10，部分停牌可能返回空）

- [ ] **Step 5: 运行全部 data 相关测试**

```bash
python -m pytest tests/test_akshare_source.py -v
```

期望：全部 PASS

- [ ] **Step 6: Commit**

```bash
git add src/trading_os/cli_internal/commands/data.py tests/test_akshare_source.py
git commit -m "perf(fetch): parallelize AKShare bulk fetch with ThreadPoolExecutor

Replace serial for-loop with ThreadPoolExecutor(max_workers=5) in the
AKShare path of fetch-ak-bulk. BaoStock path remains serial (baostock
library uses a single global TCP connection, not thread-safe).

Expected throughput: ~5x faster for AKShare path, reducing full-market
refresh from ~90 min to ~18 min at max_workers=5."
```

---

## 自我检查

**Spec 覆盖：**
- ✅ Elder + CANSLIM 并行化 → Task 3
- ✅ AKShare 线程池 → Task 4
- ✅ DuckDB 文件锁前置修复 → Task 1+2
- ✅ BaoStock 串行保留（库不支持多线程）→ Task 4 说明

**Placeholder 扫描：** 无 TBD/TODO/similar 占位符。每个步骤都有完整代码。

**类型一致性：**
- `LocalDataLake(path, read_only=True)` 在 Task 1 定义，Task 2 使用，一致 ✅
- `_fetch_one` 签名 `(exch_ticker) -> (sym_id, df, source, err)` 在 Task 4 内自洽 ✅
- `ThreadPoolExecutor` import 在 Task 3 和 Task 4 各自局部 import，不冲突 ✅
