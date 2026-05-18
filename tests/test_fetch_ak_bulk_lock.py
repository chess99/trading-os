# tests/test_fetch_ak_bulk_lock.py
"""测试 fetch-ak-bulk 的 PID lock 和进度日志行为。"""
import os
from pathlib import Path

import pytest


def _artifacts_dir(tmp_path) -> Path:
    d = tmp_path / "artifacts"
    d.mkdir()
    return d


def test_lock_file_created_on_start(tmp_path):
    """启动时应创建 PID lock 文件，内容为当前进程 PID。"""
    from trading_os.cli import _acquire_bulk_lock, _release_bulk_lock
    lock_path = _artifacts_dir(tmp_path) / "fetch_bulk.pid"

    _acquire_bulk_lock(lock_path)
    assert lock_path.exists()
    assert int(lock_path.read_text().strip()) == os.getpid()
    _release_bulk_lock(lock_path)
    assert not lock_path.exists()


def test_lock_blocks_second_instance(tmp_path):
    """lock 文件存在且进程活跃时，应拒绝启动并返回非零退出码。"""
    from trading_os.cli import _acquire_bulk_lock
    lock_path = _artifacts_dir(tmp_path) / "fetch_bulk.pid"
    lock_path.write_text(str(os.getpid()))

    with pytest.raises(SystemExit) as exc_info:
        _acquire_bulk_lock(lock_path)
    assert exc_info.value.code != 0


def test_stale_lock_cleared(tmp_path):
    """lock 文件中的 PID 不存在（进程已死）时，应清除 stale lock 并继续。"""
    from trading_os.cli import _acquire_bulk_lock, _release_bulk_lock
    lock_path = _artifacts_dir(tmp_path) / "fetch_bulk.pid"
    lock_path.write_text("99999999")

    _acquire_bulk_lock(lock_path)
    assert int(lock_path.read_text().strip()) == os.getpid()
    _release_bulk_lock(lock_path)


def test_progress_log_written(tmp_path):
    """_write_bulk_progress 应向日志追加一行，包含进度信息。"""
    from trading_os.cli import _write_bulk_progress
    log_path = _artifacts_dir(tmp_path) / "fetch_bulk_progress.log"

    _write_bulk_progress(log_path, done=100, total=2880, success=98, failed=2, elapsed=40.0)

    content = log_path.read_text()
    assert "100/2880" in content
    assert "success=98" in content
    assert "failed=2" in content
