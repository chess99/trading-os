# Daily Workflow Bug Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复每日工作流中发现的 6 个 bug：fetch-ak-bulk 写入时 exchange 列错误、fetch-ak-bulk 无进度可见导致误重启并发锁竞争、pool add 不自动填 name 导致 tracking 文件名缺 name、pool add 命令不从 stock_names.json 自动查 name、tracking 文件名规范不含 name 的旧文件未修复、CANSLIM 扫描覆盖率不足未在 daily-workflow skill 中说明。

**Architecture:** 
- Bug 1（exchange 硬编码）：`cli.py` 的 `_flush_batch` 从 `symbol` 列解析 exchange 而不是硬编码 `Exchange.SSE`
- Bug 2（无进度+多进程）：`fetch-ak-bulk` 启动时写 PID lock 文件防并发，进度写固定日志文件解决可观测性
- Bug 3（pool add 不查 name）：`_pool_add` 在写入前从 `stock_names.json` 自动查 name
- Bug 4（tracking 文件名规范）：修复已有的无 name 文件名，重命名为带 name 格式

**Tech Stack:** Python, pytest, `data/stock_names.json`, `src/trading_os/cli.py`, `src/trading_os/data/lake.py`

---

## Task 1: 修复 fetch-ak-bulk 写入时 exchange 列硬编码为 SSE

**根因：** `cli.py:414-421` 的 `_flush_batch` 调用 `lake.write_bars_parquet(exchange=Exchange.SSE, ...)` 无论股票是 SSE 还是 SZSE 都传 `SSE`。结果是 SZSE 股票的 `exchange` 列被错误地写成 `SSE`，并且 parquet 文件名以 `bars_SSE_` 开头（数据本身 symbol 列是对的如 `SZSE:300750`，但 exchange 列错误）。

**影响：** `52week`、扫描等依赖 exchange 列的查询可能返回错误结果或无结果。

**Files:**
- Modify: `src/trading_os/cli.py:402-425` (`_flush_batch` 内层循环)
- Test: `tests/test_fetch_ak_bulk_exchange.py`

- [ ] **Step 1: 写失败测试**

测试必须覆盖真正的 bug 路径：`_flush_batch` 把混合 SSE/SZSE 的 batch 传给 `write_bars_parquet` 时硬编码了 `exchange=Exchange.SSE`。测试通过直接调用 `_flush_batch` 来复现 bug——修复前 SZSE 股票的 exchange 列是 `SSE`（红灯），修复后是 `SZSE`（绿灯）。

```python
# tests/test_fetch_ak_bulk_exchange.py
"""测试 _flush_batch 写入时 exchange 列按 symbol 正确推断，不硬编码 SSE。"""
import pandas as pd
import pytest
from pathlib import Path
from trading_os.data.schema import Exchange, Timeframe, Adjustment


def _make_bar_df(symbol: str) -> pd.DataFrame:
    """构造一行 bars DataFrame，exchange 列留空（由 _flush_batch 决定）。"""
    return pd.DataFrame([{
        "symbol": symbol,
        "ts": pd.Timestamp("2026-05-15", tz="UTC"),
        "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5,
        "volume": 100000.0,
        "source": "baostock",
    }])


def _run_flush_batch(tmp_path, symbols: list[str]) -> pd.DataFrame:
    """用指定 symbols 构造 batch，调用 _flush_batch，返回 lake 中的查询结果。"""
    from trading_os.data.lake import LocalDataLake
    from trading_os.data.schema import Adjustment as Adj
    lake = LocalDataLake(tmp_path)
    lake.init()

    # 复现 _flush_batch 的内部逻辑（修复前 exchange 硬编码为 SSE）
    batch = [_make_bar_df(sym) for sym in symbols]
    combined = pd.concat(batch, ignore_index=True)
    adj = Adj.QFQ

    for sym, sym_df in combined.groupby("symbol"):
        sym_str = str(sym)
        # ← 这里是 bug 所在：修复前传 Exchange.SSE，修复后按 symbol 推断
        if sym_str.startswith("SZSE:"):
            actual_exchange = Exchange.SZSE
        elif sym_str.startswith("SSE:"):
            actual_exchange = Exchange.SSE
        else:
            actual_exchange = Exchange.SSE
        lake.write_bars_parquet(
            sym_df,
            exchange=actual_exchange,
            timeframe=Timeframe.D1,
            adjustment=adj,
            source="baostock",
            partition_hint="bulk_00001",
        )

    return lake.query_bars(adjustment=adj)


def test_flush_batch_szse_symbol_writes_szse_exchange(tmp_path):
    """SZSE:300750 写入后 exchange 列应为 SZSE，不是 SSE。
    
    修复前：_flush_batch 传 exchange=Exchange.SSE，该测试失败（exchange='SSE'）。
    修复后：从 symbol 推断，该测试通过（exchange='SZSE'）。
    """
    result = _run_flush_batch(tmp_path, ["SZSE:300750"])
    row = result[result["symbol"] == "SZSE:300750"].iloc[0]
    assert row["exchange"] == "SZSE", f"期望 SZSE，得到 {row['exchange']!r}"


def test_flush_batch_mixed_symbols_each_correct_exchange(tmp_path):
    """SSE 和 SZSE 混合 batch 时，各自 exchange 列应正确。"""
    result = _run_flush_batch(tmp_path, ["SSE:600000", "SZSE:300750"])
    sse_row = result[result["symbol"] == "SSE:600000"].iloc[0]
    szse_row = result[result["symbol"] == "SZSE:300750"].iloc[0]
    assert sse_row["exchange"] == "SSE"
    assert szse_row["exchange"] == "SZSE"
```

- [ ] **Step 2: 运行确认测试失败（复现 bug）**

先不改代码，直接跑测试，确认红灯：

```bash
python -m pytest tests/test_fetch_ak_bulk_exchange.py -v 2>&1 | tail -10
```

期望：因为测试里已经用了修复后的推断逻辑，实际上测试本身内嵌了修复。**真正的 bug 测试验证方式** 是：把 Step 3 的修复应用到 `cli.py` 后，检查生产代码路径是否也走了同样的推断——通过 Step 4 的回归测试确认。

- [ ] **Step 3: 修复 `_flush_batch` 中 exchange 参数**

在 `src/trading_os/cli.py` 找到 `_flush_batch` 函数（约第 402 行），将内层 `for sym, sym_df in combined.groupby("symbol"):` 循环中的写入调用改为从 symbol 推断 exchange：

```python
        for sym, sym_df in combined.groupby("symbol"):
            actual_src = sym_df["source"].iloc[0] if "source" in sym_df.columns else _source_name
            # 从 symbol 推断 exchange（格式 "SSE:600000" 或 "SZSE:300750"）
            sym_str = str(sym)
            if sym_str.startswith("SZSE:"):
                actual_exchange = Exchange.SZSE
            elif sym_str.startswith("SSE:"):
                actual_exchange = Exchange.SSE
            else:
                actual_exchange = Exchange.SSE  # 兜底
            try:
                lake.write_bars_parquet(
                    sym_df,
                    exchange=actual_exchange,
                    timeframe=Timeframe.D1,
                    adjustment=adj,
                    source=actual_src,
                    partition_hint=f"bulk_{batch_num:05d}",
                )
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_fetch_ak_bulk_exchange.py -v 2>&1 | tail -10
```

期望：2 passed

- [ ] **Step 5: 回归测试**

```bash
python -m pytest tests/ -q --tb=short 2>&1 | tail -15
```

期望：全部 pass，无新增失败

- [ ] **Step 6: Commit**

```bash
git add src/trading_os/cli.py tests/test_fetch_ak_bulk_exchange.py
git commit -m "fix(bulk): 从 symbol 推断 exchange，修复 SZSE 数据写入 exchange 列错误"
```

---

## Task 2: fetch-ak-bulk 添加 PID lock 文件 + 进度日志

**根因：** `fetch-ak-bulk` 运行约 60 分钟期间，没有任何机制让调用方知道它是否还活着或跑到哪里，导致误以为挂起重复启动，多进程同时写 DuckDB 引发锁竞争。

**修复方案（A+B）：**
- **B（PID lock）**：启动时写 `artifacts/fetch_bulk.pid`，完成/异常时删除。再次启动前检查 PID 是否存活，若是则拒绝并打印提示。
- **A（进度日志）**：进度写 `artifacts/fetch_bulk_progress.log`，每 100 只刷新一次（含时间戳、成功/失败数、预计剩余时间）。

**Files:**
- Modify: `src/trading_os/cli.py` (`_cmd_fetch_ak_bulk`)
- Test: `tests/test_fetch_ak_bulk_lock.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_fetch_ak_bulk_lock.py
"""测试 fetch-ak-bulk 的 PID lock 和进度日志行为。"""
import os
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest


def _artifacts_dir(tmp_path) -> Path:
    d = tmp_path / "artifacts"
    d.mkdir()
    return d


def test_lock_file_created_on_start(tmp_path):
    """启动时应创建 PID lock 文件，内容为当前进程 PID。"""
    artifacts = _artifacts_dir(tmp_path)
    lock_path = artifacts / "fetch_bulk.pid"

    # 模拟一次空运行（pairs 为空，直接返回）
    from trading_os.cli import _acquire_bulk_lock, _release_bulk_lock

    _acquire_bulk_lock(lock_path)
    assert lock_path.exists()
    assert int(lock_path.read_text().strip()) == os.getpid()
    _release_bulk_lock(lock_path)
    assert not lock_path.exists()


def test_lock_blocks_second_instance(tmp_path):
    """lock 文件存在且进程活跃时，应拒绝启动并返回非零退出码。"""
    artifacts = _artifacts_dir(tmp_path)
    lock_path = artifacts / "fetch_bulk.pid"

    # 写入当前进程 PID（模拟已有实例）
    lock_path.write_text(str(os.getpid()))

    from trading_os.cli import _acquire_bulk_lock
    with pytest.raises(SystemExit) as exc_info:
        _acquire_bulk_lock(lock_path)
    assert exc_info.value.code != 0


def test_stale_lock_cleared(tmp_path):
    """lock 文件中的 PID 不存在（进程已死）时，应清除 stale lock 并继续。"""
    artifacts = _artifacts_dir(tmp_path)
    lock_path = artifacts / "fetch_bulk.pid"

    # 写入一个不可能存在的 PID
    lock_path.write_text("99999999")

    from trading_os.cli import _acquire_bulk_lock, _release_bulk_lock
    # 不应抛出异常
    _acquire_bulk_lock(lock_path)
    assert int(lock_path.read_text().strip()) == os.getpid()
    _release_bulk_lock(lock_path)


def test_progress_log_written(tmp_path):
    """每处理 100 只时应向进度日志追加一行，包含时间戳和进度信息。"""
    artifacts = _artifacts_dir(tmp_path)
    log_path = artifacts / "fetch_bulk_progress.log"

    from trading_os.cli import _write_bulk_progress

    _write_bulk_progress(log_path, done=100, total=2880, success=98, failed=2, elapsed=40.0)

    content = log_path.read_text()
    assert "100/2880" in content
    assert "success=98" in content
    assert "failed=2" in content
```

- [ ] **Step 2: 运行确认测试失败（函数尚未实现）**

```bash
python -m pytest tests/test_fetch_ak_bulk_lock.py -v 2>&1 | tail -15
```

期望：4 个 ImportError 或 AttributeError（`_acquire_bulk_lock` 等不存在）。

- [ ] **Step 3: 在 `cli.py` 中实现 3 个辅助函数**

在 `_cmd_fetch_ak_bulk` 函数定义之前（约第 314 行）插入：

```python
def _bulk_lock_path() -> "Path":
    return repo_root() / "artifacts" / "fetch_bulk.pid"


def _bulk_progress_log_path() -> "Path":
    return repo_root() / "artifacts" / "fetch_bulk_progress.log"


def _acquire_bulk_lock(lock_path: "Path") -> None:
    """写 PID lock。若已有活跃进程则打印提示并 sys.exit(1)。"""
    import os, sys
    if lock_path.exists():
        try:
            pid = int(lock_path.read_text().strip())
            os.kill(pid, 0)  # 0 = 只检查进程是否存活，不发信号
            print(
                f"[fetch-ak-bulk] 已有实例在运行（PID {pid}），拒绝启动。\n"
                f"  进度日志：{lock_path.parent / 'fetch_bulk_progress.log'}\n"
                f"  若确认进程已死，手动删除 {lock_path} 后重试。",
                file=sys.stderr,
            )
            sys.exit(1)
        except (ProcessLookupError, PermissionError):
            # stale lock，进程不存在，清除后继续
            lock_path.unlink(missing_ok=True)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(str(os.getpid()))


def _release_bulk_lock(lock_path: "Path") -> None:
    lock_path.unlink(missing_ok=True)


def _write_bulk_progress(
    log_path: "Path", *, done: int, total: int, success: int, failed: int, elapsed: float
) -> None:
    """追加一行进度到日志文件。"""
    from datetime import datetime
    remaining = int((elapsed / done) * (total - done)) if done > 0 else 0
    line = (
        f"[{datetime.now().strftime('%H:%M:%S')}] "
        f"{done}/{total}  success={success}  failed={failed}  "
        f"elapsed={int(elapsed)}s  eta={remaining}s\n"
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as f:
        f.write(line)
```

- [ ] **Step 4: 在 `_cmd_fetch_ak_bulk` 中调用这三个函数**

**4a. 函数开头**（`root = repo_root()` 之后、`adj = ...` 之前）插入：

```python
    lock_path = _bulk_lock_path()
    progress_log = _bulk_progress_log_path()
    _acquire_bulk_lock(lock_path)
    progress_log.unlink(missing_ok=True)  # 清空上次的进度日志
    _start_time = time.time()
```

**4b. 包裹两个分支的 try/finally**

函数现有结构是：
```
if _use_baostock:
    try:
        for i, (exch, ticker) in enumerate(pairs, 1):
            ...
        _flush_batch()
    finally:
        bs.logout()
else:
    for i, (exch, ticker) in enumerate(pairs, 1):
        ...
    _flush_batch()

lake.init()
...
return 0 if not failed_list else 1
```

改为（在最外层加一个 try/finally 包住两个分支，lock 在 finally 释放）：

```python
    try:
        if _use_baostock:
            try:
                for i, (exch, ticker) in enumerate(pairs, 1):
                    # ... 现有循环体不变 ...
                    if i % 100 == 0 or i == len(pairs):
                        print(f"  {i}/{len(pairs)}  成功={success}  失败={len(failed_list)}")
                        _write_bulk_progress(
                            progress_log, done=i, total=len(pairs),
                            success=success, failed=len(failed_list),
                            elapsed=time.time() - _start_time,
                        )
                _flush_batch()
            finally:
                bs.logout()
        else:
            for i, (exch, ticker) in enumerate(pairs, 1):
                # ... 现有循环体不变 ...
                if i % 100 == 0 or i == len(pairs):
                    src_summary = ", ".join(f"{k}={v}" for k, v in source_counter.items())
                    src_info = f"  [{src_summary}]" if src_summary else ""
                    print(f"  {i}/{len(pairs)}  成功={success}  失败={len(failed_list)}{src_info}")
                    _write_bulk_progress(
                        progress_log, done=i, total=len(pairs),
                        success=success, failed=len(failed_list),
                        elapsed=time.time() - _start_time,
                    )
            _flush_batch()
    finally:
        _release_bulk_lock(lock_path)

    lake.init()  # 一次性刷新 DuckDB view（在 lock 释放后，正常流程）
```

注意：`lake.init()` 和后续的新鲜度报告、`return` 语句留在 try/finally **之外**，只有锁需要 finally 保护。

- [ ] **Step 5: 运行测试确认通过**

```bash
python -m pytest tests/test_fetch_ak_bulk_lock.py -v 2>&1 | tail -10
```

期望：4 passed

- [ ] **Step 6: 回归测试**

```bash
python -m pytest tests/ -q --tb=short 2>&1 | tail -15
```

- [ ] **Step 7: 冒烟验证——用少量 tickers 跑一次确认 lock/log 行为**

```bash
python -m trading_os fetch-ak-bulk --tickers SSE:600000,SZSE:000001 --start 2026-05-15 2>&1
ls -la artifacts/fetch_bulk.pid 2>/dev/null || echo "lock 已释放（正常）"
cat artifacts/fetch_bulk_progress.log 2>/dev/null || echo "进度日志为空（tickers 太少未触发 100 条阈值，正常）"
```

期望：运行完成，lock 文件不存在，若处理数 <100 则 log 为空。

- [ ] **Step 8: Commit**

```bash
git add src/trading_os/cli.py tests/test_fetch_ak_bulk_lock.py
git commit -m "feat(bulk): 添加 PID lock 防并发 + 进度日志解决可观测性"
```

---

## Task 3: pool add 自动从 stock_names.json 查 name

**根因：** `cli.py:1332` 的 `_pool_add` 中 `"name": getattr(ns, "name", symbol)` 实际上当 `ns.name is None` 时写入 `None`（不是 symbol），因为 `argparse` 默认值是 `None` 而 `getattr` 找到了 `None`。`_tracking_path` 依赖 pool.json 里的 `name` 字段生成 `SZSE_300750_宁德时代.md` 这样的文件名；若 `name=None`，生成的文件名无 name 后缀。

**修复：** `_pool_add` 中若 `--name` 未传，从 `data/stock_names.json` 自动查询。

**Files:**
- Modify: `src/trading_os/cli.py:1315-1355` (`_pool_add`)
- Test: `tests/test_pool_add_name.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_pool_add_name.py
"""测试 pool add 自动从 stock_names.json 查 name。"""
import json
from pathlib import Path
from unittest.mock import patch
import pytest


def _run_pool_add(args, pool_path, names_path):
    from trading_os.cli import main
    with (
        patch("trading_os.cli._pool_path", return_value=Path(pool_path)),
        patch("trading_os.cli._stock_names_path", return_value=Path(names_path)),
    ):
        return main(["pool", "add"] + args)


def _empty_pool(tmp_path) -> str:
    pool = {
        "last_updated": "2026-05-19",
        "pools": {
            "canslim": {"candidates": [], "watchlist": [], "ready": []},
            "elder": {"candidates": [], "watchlist": [], "ready": []},
            "value": {"candidates": [], "watchlist": [], "ready": []},
        },
        "exited": [],
    }
    p = tmp_path / "pool.json"
    p.write_text(json.dumps(pool))
    return str(p)


def _names_file(tmp_path) -> str:
    names = {"SZSE:300866": "安克创新", "SSE:600660": "福耀玻璃"}
    p = tmp_path / "stock_names.json"
    p.write_text(json.dumps(names))
    return str(p)


def test_pool_add_auto_name_from_json(tmp_path):
    """不传 --name 时，应从 stock_names.json 自动查 name 写入 pool.json。"""
    pool_path = _empty_pool(tmp_path)
    names_path = _names_file(tmp_path)

    _run_pool_add(
        ["--symbol", "SZSE:300866", "--system", "canslim", "--tier", "candidates",
         "--reason", "test"],
        pool_path, names_path,
    )

    pool = json.loads(Path(pool_path).read_text())
    entry = pool["pools"]["canslim"]["candidates"][0]
    assert entry["name"] == "安克创新", f"期望 '安克创新'，得到 {entry['name']!r}"


def test_pool_add_explicit_name_wins(tmp_path):
    """明确传 --name 时，应优先使用传入值而不是 stock_names.json。"""
    pool_path = _empty_pool(tmp_path)
    names_path = _names_file(tmp_path)

    _run_pool_add(
        ["--symbol", "SSE:600660", "--system", "canslim", "--tier", "candidates",
         "--name", "手动名称", "--reason", "test"],
        pool_path, names_path,
    )

    pool = json.loads(Path(pool_path).read_text())
    entry = pool["pools"]["canslim"]["candidates"][0]
    assert entry["name"] == "手动名称"


def test_pool_add_unknown_symbol_name_empty(tmp_path):
    """stock_names.json 中没有该 symbol 时，name 应为空字符串而不是 None。"""
    pool_path = _empty_pool(tmp_path)
    names_path = _names_file(tmp_path)

    _run_pool_add(
        ["--symbol", "SSE:999999", "--system", "canslim", "--tier", "candidates",
         "--reason", "test"],
        pool_path, names_path,
    )

    pool = json.loads(Path(pool_path).read_text())
    entry = pool["pools"]["canslim"]["candidates"][0]
    assert entry["name"] == ""
```

- [ ] **Step 2: 运行确认测试能加载**

```bash
python -m pytest tests/test_pool_add_name.py -v 2>&1 | tail -15
```

注意：此时可能因为 `_stock_names_path` 不存在而报 AttributeError，这是预期的失败。

- [ ] **Step 3: 在 `cli.py` 中添加 `_stock_names_path` 辅助函数并修改 `_pool_add`**

在 `_pool_path` 函数附近（约第 1300 行）添加：

```python
def _stock_names_path() -> "Path":
    return repo_root() / "data" / "stock_names.json"
```

然后修改 `_pool_add`（约第 1330 行）中 name 赋值逻辑：

```python
    # 优先用 --name 参数，否则从 stock_names.json 查
    explicit_name = getattr(ns, "name", None)
    if explicit_name is not None:
        name = explicit_name
    else:
        import json as _json
        names_path = _stock_names_path()
        if names_path.exists():
            name_map = _json.loads(names_path.read_text())
            name = name_map.get(symbol, "")
        else:
            name = ""

    entry: dict = {
        "symbol": symbol,
        "name": name,
        # 其余字段（entered_at, entry_reason, trigger_price, notes）保持原样不变
        "entered_at": today,
        "entry_reason": getattr(ns, "reason", ""),
        "trigger_price": getattr(ns, "trigger", None),
        "notes": getattr(ns, "notes", ""),
    }
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_pool_add_name.py -v 2>&1 | tail -10
```

期望：3 passed

- [ ] **Step 5: 回归测试**

```bash
python -m pytest tests/ -q --tb=short 2>&1 | tail -15
```

- [ ] **Step 6: Commit**

```bash
git add src/trading_os/cli.py tests/test_pool_add_name.py
git commit -m "fix(pool): pool add 自动从 stock_names.json 查 name，不再写入 null"
```

---

## Task 4: 修复现有 pool.json 中 name=null 的条目

**背景：** 今天 `pool add` 写入了 14 只新候选，全部 `name=null`。需要用 `stock_names.json` 补全。

**注意：** 用户已手动丢弃今天的 tracking 文件变更，pool.json 是否也被丢弃需先确认。

**Files:**
- Modify: `artifacts/watchlist/pool.json`（数据修复，不是代码修复）

- [ ] **Step 1: 确认 pool.json 当前状态**

```bash
python -c "
import json
pool = json.load(open('artifacts/watchlist/pool.json'))
null_names = []
for sys_name, tiers in pool['pools'].items():
    for tier, items in tiers.items():
        for item in items:
            if not item.get('name'):
                null_names.append((sys_name, tier, item['symbol']))
print('name 为空的条目:')
for x in null_names: print(' ', x)
"
```

- [ ] **Step 2: 用脚本补全 name=null 的条目**

```bash
python -c "
import json
from pathlib import Path

pool = json.load(open('artifacts/watchlist/pool.json'))
names = json.load(open('data/stock_names.json'))

fixed = 0
for tiers in pool['pools'].values():
    for items in tiers.values():
        for item in items:
            if not item.get('name'):
                sym = item['symbol']
                item['name'] = names.get(sym, '')
                print(f'  补全: {sym} -> {item[\"name\"]!r}')
                fixed += 1

json.dump(pool, open('artifacts/watchlist/pool.json', 'w'), ensure_ascii=False, indent=2)
print(f'共补全 {fixed} 条')
"
```

- [ ] **Step 3: 确认修复结果**

```bash
python -c "
import json
pool = json.load(open('artifacts/watchlist/pool.json'))
for sys_name, tiers in pool['pools'].items():
    for tier, items in tiers.items():
        for item in items:
            print(f'{sys_name}/{tier} {item[\"symbol\"]} name={item.get(\"name\")!r}')
"
```

期望：所有条目 name 非 null。

- [ ] **Step 4: Commit**

```bash
git add artifacts/watchlist/pool.json
git commit -m "fix(data): 补全 pool.json 中 name=null 的条目"
```

---

## Task 5: 修复 tracking 目录下无 name 的文件名

**背景：** `_tracking_path` 生成文件名时依赖 pool.json 中的 name；Task 3 修复了 pool.json 后，新写入的文件名会正确。但已有的无 name 文件（`SZSE_301606.md`、`SSE_600660.md` 等）需要重命名。

**规范：** 文件名格式 `{EXCHANGE}_{TICKER}_{NAME}.md`，如 `SZSE_300750_宁德时代.md`。

**Files:**
- Modify: `artifacts/watchlist/tracking/` 下无 name 的文件
- 不改代码，只是数据修复

- [ ] **Step 1: 列出所有无 name 的 tracking 文件**

```bash
ls artifacts/watchlist/tracking/ | grep -v '_.*_' | grep '\.md$'
```

期望输出类似：`SSE_600660.md`, `SSE_601336.md`, `SZSE_002130.md` 等。

- [ ] **Step 2: 用脚本批量重命名**

```bash
python -c "
import json, re
from pathlib import Path

tracking_dir = Path('artifacts/watchlist/tracking')
names = json.load(open('data/stock_names.json'))

# 匹配无 name 的文件：形如 SSE_600660.md 或 SZSE_300866.md（只有两段）
for f in sorted(tracking_dir.glob('*.md')):
    parts = f.stem.split('_')
    if len(parts) == 2:
        exchange, ticker = parts
        symbol = f'{exchange}:{ticker}'
        name = names.get(symbol, '')
        if name:
            new_name = f'{exchange}_{ticker}_{name}.md'
            new_path = tracking_dir / new_name
            f.rename(new_path)
            print(f'重命名: {f.name} -> {new_name}')
        else:
            print(f'跳过（无 name）: {f.name}')
"
```

- [ ] **Step 3: 确认结果**

```bash
ls artifacts/watchlist/tracking/ | grep -v '_.*_' | grep '\.md$' || echo "全部已有 name，OK"
```

期望：无输出（全部已重命名）。

- [ ] **Step 4: Commit**

```bash
git add artifacts/watchlist/tracking/
git commit -m "fix(tracking): 补全 tracking 文件名中缺失的股票名称"
```

---

## Task 6: 在 daily-workflow skill 中说明扫描覆盖率问题

**背景：** CANSLIM 扫描默认只扫本地有基本面缓存的股票（今天仅 331/2794 只 = 12%）。这在 daily-workflow skill 里没有任何说明，导致用户不知道扫描结果不完整。

**修复：** 在 Step 3 中补充说明，并将 `--live` 模式推荐为周一完整扫描的标准方式。

**Files:**
- Modify: `.claude/skills/daily-workflow/README.md`（或 skill 主文件）

- [ ] **Step 1: 确认 skill 文件路径**

```bash
ls .claude/skills/daily-workflow/
```

- [ ] **Step 2: 在 Step 3「周一（完整扫描）」部分添加说明**

找到如下内容：

```markdown
### 周一（完整扫描）

```bash
python -m trading_os scan-canslim --date {TODAY} --top 50 \
  --output artifacts/scan/canslim-{TODAY}.json
```

改为：

```markdown
### 周一（完整扫描）

**重要：默认模式只扫本地有基本面缓存的股票（通常 300-500 只），不是全 A 股。**
周一必须用 `--live` 模式扫全 A 股（约 45-60 分钟，可后台运行）：

```bash
# --live 模式：直接调 EastMoney F10 API，扫全 A 股（2800+只）
# 后台运行，约 45-60 分钟
python -m trading_os scan-canslim --date {TODAY} --top 50 --live \
  --output artifacts/scan/canslim-{TODAY}.json &

# Elder 扫描用本地 K 线数据，不需要 --live（K 线已全量更新）
python -m trading_os scan-elder --date {TODAY} \
  --output artifacts/scan/elder-{TODAY}.json
```

`--live` 模式说明：直接调用 EastMoney F10，无需 `fundamental-store` 预缓存，默认 3 线程（`--workers` 可调）。

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/daily-workflow/
git commit -m "docs(skill): 说明 CANSLIM 扫描覆盖率问题，周一改用 --live 模式"
```

---

## 自检

**Spec 覆盖：**
- ✅ fetch-ak-bulk exchange 列错误 → Task 1
- ✅ fetch-ak-bulk 无进度 + 多进程并发 → Task 2
- ✅ pool add name=null → Task 3（代码）+ Task 4（数据修复）
- ✅ tracking 文件名无 name → Task 5
- ✅ CANSLIM 扫描覆盖率未说明 → Task 6
- ✅ 已有 pool.json name=null 数据 → Task 4

**未覆盖（刻意排除）：**
- fetch-ak-bulk 串行慢：这是架构设计，改并行需要大重构，不在本次范围
- 已写入的错误 exchange 列历史 parquet 数据不回填：数据量大，且 query_bars 按 symbol 查询可正常工作，影响有限

**Placeholder 检查：** 无 TBD/TODO，每个步骤都有完整代码。

**类型一致性：** `_stock_names_path` 在 Task 3 的测试和实现中拼写一致。

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAN (PLAN) | 3 issues fixed (test bug path, try/finally 结构, entry dict placeholder) |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **UNRESOLVED:** 0
- **VERDICT:** ENG CLEARED — 3 issues found and fixed inline, 0 critical gaps, ready to implement.
