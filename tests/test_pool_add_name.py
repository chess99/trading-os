"""测试 pool add 自动从 stock_names.json 查 name。"""
import json
from pathlib import Path
from unittest.mock import patch


def _run_pool_add(args, pool_path, names_path):
    from trading_os.cli import main
    with (
        patch("trading_os.cli_internal.commands.pool._pool_path", return_value=Path(pool_path)),
        patch("trading_os.cli_internal.commands.pool._stock_names_path", return_value=Path(names_path)),
        # Prevent writing to real artifacts/watchlist/tracking/
        patch("trading_os.cli_internal.commands.pool._append_tracking"),
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
