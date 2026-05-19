"""测试 pool sync-from-scan 子命令。"""
import json, sys
from pathlib import Path
from unittest.mock import patch
import pytest


def _run_pool(args, pool_path):
    """辅助：以 pool_path 为池文件运行 pool 子命令。"""
    from trading_os.cli import main
    with (
        patch("trading_os.cli_internal.commands.pool._pool_path", return_value=Path(pool_path)),
        # Prevent writing to real artifacts/watchlist/tracking/
        patch("trading_os.cli_internal.commands.pool._append_tracking"),
    ):
        return main(["pool"] + args)


def _make_pool(tmp_path):
    pool = {
        "last_updated": "2026-05-06",
        "pools": {
            "canslim": {
                "candidates": [
                    {"symbol": "SSE:601138", "name": "工业富联", "entered_at": "2026-05-01",
                     "entry_reason": "test", "score": 5}
                ],
                "watchlist": [], "ready": []
            },
            "elder": {"candidates": [], "watchlist": [], "ready": []},
            "value": {"candidates": [], "watchlist": [], "ready": []}
        },
        "exited": []
    }
    p = tmp_path / "pool.json"
    p.write_text(json.dumps(pool))
    return str(p)


def _make_scan(tmp_path, candidates):
    scan = {
        "scan_date": "2026-05-06",
        "system": "canslim",
        "total_scanned": 5517,
        "candidates": candidates,
        "filtered_out": 0,
    }
    p = tmp_path / "canslim-20260506.json"
    p.write_text(json.dumps(scan))
    return str(p)


def test_sync_shows_new_candidate(tmp_path, capsys):
    """扫描中出现的高分新标的，且不在池中，应提示'建议入候选池'。"""
    pool_path = _make_pool(tmp_path)
    scan_path = _make_scan(tmp_path, [
        {"symbol": "SZSE:300750", "name": "宁德时代", "rank": 1, "score": 6.0,
         "signals": {"eps_growth_yoy": 0.42, "roe": 0.247, "relative_strength_top20pct": True},
         "next_step": ""}
    ])
    _run_pool(["sync-from-scan", "--scan", scan_path, "--system", "canslim"], pool_path)
    out = capsys.readouterr().out
    assert "SZSE:300750" in out
    assert "宁德时代" in out
    assert "建议入候选" in out or "new" in out.lower()


def test_sync_shows_already_in_pool(tmp_path, capsys):
    """扫描中出现的标的已经在池中，应显示'已在池中'而不是重复建议。"""
    pool_path = _make_pool(tmp_path)
    scan_path = _make_scan(tmp_path, [
        {"symbol": "SSE:601138", "name": "工业富联", "rank": 1, "score": 5.0,
         "signals": {}, "next_step": ""}
    ])
    _run_pool(["sync-from-scan", "--scan", scan_path, "--system", "canslim"], pool_path)
    out = capsys.readouterr().out
    assert "SSE:601138" in out
    assert "已在池" in out or "already" in out.lower()


def test_sync_shows_dropped_from_scan(tmp_path, capsys):
    """池中标的本次扫描未出现（得分不足），应提示'需关注是否移出'。"""
    pool_path = _make_pool(tmp_path)
    scan_path = _make_scan(tmp_path, [])  # 扫描结果为空，601138 消失
    _run_pool(["sync-from-scan", "--scan", scan_path, "--system", "canslim"], pool_path)
    out = capsys.readouterr().out
    assert "SSE:601138" in out
    assert "未出现" in out or "dropped" in out.lower() or "不在" in out
