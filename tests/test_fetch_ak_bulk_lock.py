# tests/test_fetch_ak_bulk_lock.py
"""测试 fetch-ak-bulk 的 PID lock 和进度日志行为。"""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


def _artifacts_dir(tmp_path) -> Path:
    d = tmp_path / "artifacts"
    d.mkdir()
    return d


def test_lock_file_created_on_start(tmp_path):
    """启动时应创建 PID lock 文件，内容为当前进程 PID。"""
    from trading_os.cli_internal.commands.data import _acquire_bulk_lock, _release_bulk_lock
    lock_path = _artifacts_dir(tmp_path) / "fetch_bulk.pid"

    _acquire_bulk_lock(lock_path)
    assert lock_path.exists()
    assert json.loads(lock_path.read_text())["pid"] == os.getpid()
    _release_bulk_lock(lock_path)
    assert not lock_path.exists()


def test_lock_blocks_second_instance(tmp_path):
    """lock 文件存在且进程活跃时，应拒绝启动并返回非零退出码。"""
    from trading_os.cli_internal.commands.data import _acquire_bulk_lock
    lock_path = _artifacts_dir(tmp_path) / "fetch_bulk.pid"
    lock_path.write_text(str(os.getpid()))

    with pytest.raises(SystemExit) as exc_info:
        _acquire_bulk_lock(lock_path)
    assert exc_info.value.code != 0


def test_stale_lock_cleared(tmp_path):
    """lock 文件中的 PID 不存在（进程已死）时，应清除 stale lock 并继续。"""
    from trading_os.cli_internal.commands.data import _acquire_bulk_lock, _release_bulk_lock
    lock_path = _artifacts_dir(tmp_path) / "fetch_bulk.pid"
    lock_path.write_text("99999999")

    _acquire_bulk_lock(lock_path)
    assert json.loads(lock_path.read_text())["pid"] == os.getpid()
    _release_bulk_lock(lock_path)


def test_progress_log_written(tmp_path):
    """_write_bulk_progress 应向日志追加一行，包含进度信息。"""
    from trading_os.cli_internal.commands.data import _write_bulk_progress
    log_path = _artifacts_dir(tmp_path) / "fetch_bulk_progress.log"

    _write_bulk_progress(log_path, done=100, total=2880, success=98, failed=2, elapsed=40.0)

    content = log_path.read_text()
    assert "100/2880" in content
    assert "success=98" in content
    assert "failed=2" in content
    progress = json.loads((log_path.parent / "jobs" / "current_fetch_bulk.json").read_text())
    assert progress["done"] == 100
    assert progress["total"] == 2880
    assert progress["eta_sec"] == 1112


def test_progress_records_retry_source_counts_and_coverage_path(tmp_path):
    """结构化进度应包含重试轮次、数据源分布和 coverage manifest 路径。"""
    from trading_os.cli_internal.commands.data import _write_bulk_progress

    log_path = _artifacts_dir(tmp_path) / "fetch_bulk_progress.log"

    _write_bulk_progress(
        log_path,
        done=2,
        total=3,
        success=2,
        failed=1,
        elapsed=10.0,
        source_counts={"eastmoney": 1, "sina": 1},
        retry_round=1,
        coverage_path=str(tmp_path / "artifacts" / "jobs" / "bulk_coverage_20260526.json"),
    )

    progress = json.loads((log_path.parent / "jobs" / "current_fetch_bulk.json").read_text())
    assert progress["source_counts"] == {"eastmoney": 1, "sina": 1}
    assert progress["retry_round"] == 1
    assert progress["coverage_path"].endswith("bulk_coverage_20260526.json")


def test_resolve_bulk_pairs_uses_valid_universe_cache_after_baostock_timeout(tmp_path, monkeypatch):
    """BaoStock 股票列表超时后，应使用最近一次有效 universe cache。"""
    import trading_os.cli_internal.commands.data as data_cmd
    from trading_os.data.schema import Exchange

    monkeypatch.setattr(data_cmd, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        data_cmd,
        "_fetch_baostock_universe",
        lambda max_retries=3: (_ for _ in ()).throw(TimeoutError("BaoStock 获取股票列表超时")),
        raising=False,
    )
    pairs = [
        {"exchange": Exchange.SSE.value if i % 2 == 0 else Exchange.SZSE.value, "ticker": f"{i:06d}"}
        for i in range(5000)
    ]
    cache_path = tmp_path / "artifacts" / "jobs" / "stock_universe_cache.json"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(json.dumps({"pairs": pairs}), encoding="utf-8")
    ns = SimpleNamespace(tickers=None, max_retries=2)

    resolved = data_cmd._resolve_bulk_pairs(ns)

    assert len(resolved) == 5000
    assert resolved[0] == (Exchange.SSE, "000000")


def test_resolve_bulk_pairs_fails_when_universe_cache_is_missing(tmp_path, monkeypatch):
    """股票列表和 cache 都不可用时，不能返回空列表导致 skipped。"""
    import trading_os.cli_internal.commands.data as data_cmd

    monkeypatch.setattr(data_cmd, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        data_cmd,
        "_fetch_baostock_universe",
        lambda max_retries=3: (_ for _ in ()).throw(TimeoutError("BaoStock 获取股票列表超时")),
        raising=False,
    )
    ns = SimpleNamespace(tickers=None, max_retries=2)

    assert data_cmd._resolve_bulk_pairs(ns) is None


def test_lock_file_records_job_metadata(tmp_path):
    """job-aware lock 应记录 job_id、命令和 effective_date。"""
    from trading_os.cli_internal.commands.data import _acquire_bulk_lock, _release_bulk_lock
    lock_path = _artifacts_dir(tmp_path) / "fetch_bulk.pid"

    _acquire_bulk_lock(
        lock_path,
        job_id="bulk-1",
        command="python -m trading_os fetch-ak-bulk",
        effective_date="2026-05-19",
    )

    data = json.loads(lock_path.read_text())
    assert data["job_id"] == "bulk-1"
    assert data["pid"] == os.getpid()
    assert data["command"] == "python -m trading_os fetch-ak-bulk"
    assert data["effective_date"] == "2026-05-19"
    _release_bulk_lock(lock_path)


def test_fetch_ak_bulk_failed_resolution_writes_terminal_progress(tmp_path, monkeypatch):
    """股票列表解析失败早退时，结构化进度不能停留在 running。"""
    import trading_os.cli_internal.commands.data as data_cmd

    monkeypatch.setattr(data_cmd, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(data_cmd, "_resolve_bulk_pairs", lambda ns: None)
    ns = SimpleNamespace(
        adjustment="qfq",
        start="2026-05-18",
        end="2026-05-18",
        skip_existing=False,
        verbose=False,
        tickers=None,
    )

    assert data_cmd._cmd_fetch_ak_bulk(ns) == 1

    progress_path = tmp_path / "artifacts" / "jobs" / "current_fetch_bulk.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    assert progress["status"] == "failed"
    assert progress["done"] == 0
    assert progress["total"] == 0
    assert not (tmp_path / "artifacts" / "fetch_bulk.pid").exists()


def test_fetch_ak_bulk_no_pairs_writes_skipped_progress(tmp_path, monkeypatch):
    """没有可拉取股票时也要写终态，避免 stale running 误导 daily。"""
    import trading_os.cli_internal.commands.data as data_cmd

    monkeypatch.setattr(data_cmd, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(data_cmd, "_resolve_bulk_pairs", lambda ns: [])
    ns = SimpleNamespace(
        adjustment="qfq",
        start="2026-05-18",
        end="2026-05-18",
        skip_existing=False,
        verbose=False,
        tickers=None,
    )

    assert data_cmd._cmd_fetch_ak_bulk(ns) == 0

    progress = json.loads(
        (tmp_path / "artifacts" / "jobs" / "current_fetch_bulk.json").read_text(encoding="utf-8")
    )
    assert progress["status"] == "skipped"


def test_fetch_ak_bulk_write_integrity_failure_is_reported_as_failed(tmp_path, monkeypatch):
    """lake 写入拒绝某个 symbol 时，应进入失败/coverage，而不是只扣 success。"""
    import pandas as pd
    import trading_os.cli_internal.commands.data as data_cmd
    from trading_os.data.exceptions import DataIntegrityError
    from trading_os.data.schema import Exchange

    monkeypatch.setattr(data_cmd, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        data_cmd,
        "_resolve_bulk_pairs",
        lambda ns: [(Exchange.SSE, "600000"), (Exchange.SSE, "600001")],
    )
    monkeypatch.setattr(data_cmd, "_load_baostock_exceptions", lambda symbols, effective_date: {})

    class FakeLake:
        def __init__(self, root):
            self.root = root

        def write_bars_parquet(self, df, **kwargs):
            if len(df) > 1:
                raise DataIntegrityError(
                    symbol="batch",
                    expected_range=(1.0, 2.0),
                    actual_value=10.0,
                )
            sym = df["symbol"].iloc[0]
            if sym == "SSE:600001":
                raise DataIntegrityError(
                    symbol=sym,
                    expected_range=(1.0, 2.0),
                    actual_value=10.0,
                )
            return []

        def init(self):
            return None

        def connect(self):
            raise RuntimeError("not used")

        def latest_bar_dates(self, **kwargs):
            return {"SSE:600000": "2026-05-26"}

    monkeypatch.setattr("trading_os.data.lake.LocalDataLake", FakeLake)

    def fake_fetch(ticker, *, exchange, start, end, adjustment):
        return pd.DataFrame(
            {
                "symbol": [f"{exchange.value}:{ticker}"],
                "ts": pd.to_datetime(["2026-05-26"], utc=True),
                "open": [1.0],
                "high": [1.0],
                "low": [1.0],
                "close": [1.0],
                "volume": [1000.0],
                "source": ["sina"],
            }
        ), "sina"

    monkeypatch.setattr(
        "trading_os.data.sources.akshare_source.fetch_daily_bars",
        fake_fetch,
    )
    ns = SimpleNamespace(
        adjustment="qfq",
        start="2026-05-26",
        end="2026-05-26",
        skip_existing=False,
        verbose=False,
        tickers=None,
        source="akshare",
        max_retries=1,
        retry_failed_rounds=0,
        workers=1,
    )

    assert data_cmd._cmd_fetch_ak_bulk(ns) == 1

    progress = json.loads(
        (tmp_path / "artifacts" / "jobs" / "current_fetch_bulk.json").read_text(encoding="utf-8")
    )
    coverage = json.loads(
        (tmp_path / "artifacts" / "jobs" / "bulk_coverage_20260526.json").read_text(encoding="utf-8")
    )
    assert progress["status"] == "failed"
    assert progress["failed"] == 1
    assert coverage["status_counts"]["failed"] == 1
    assert coverage["symbols"][1]["reason"].startswith("DataIntegrityError")
