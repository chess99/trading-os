"""Trading OS CLI compatibility shim."""
from __future__ import annotations

from .cli_impl.app import build_parser
from .cli_impl.app import main as _app_main
from .cli_impl.commands.data import (
    _acquire_bulk_lock,
    _bulk_lock_path,
    _bulk_progress_log_path,
    _release_bulk_lock,
    _resolve_bulk_pairs,
    _write_bulk_progress,
)
from .cli_impl.commands.pool import (
    _append_tracking,
    _cmd_pool,
    _empty_pool,
    _load_pool,
    _pool_add,
    _pool_path,
    _pool_promote,
    _pool_remove,
    _pool_status,
    _pool_sync_from_scan,
    _pool_update,
    _save_pool,
    _stock_names_path,
    _tracking_path,
)


def _sync_compat_overrides() -> None:
    """Propagate patched compatibility exports into implementation modules."""
    from .cli_impl.commands import data as data_commands
    from .cli_impl.commands import pool as pool_commands

    data_commands._acquire_bulk_lock = _acquire_bulk_lock
    data_commands._release_bulk_lock = _release_bulk_lock
    data_commands._write_bulk_progress = _write_bulk_progress
    data_commands._bulk_lock_path = _bulk_lock_path
    data_commands._bulk_progress_log_path = _bulk_progress_log_path
    data_commands._resolve_bulk_pairs = _resolve_bulk_pairs

    pool_commands._pool_path = _pool_path
    pool_commands._stock_names_path = _stock_names_path
    pool_commands._append_tracking = _append_tracking
    pool_commands._tracking_path = _tracking_path
    pool_commands._load_pool = _load_pool
    pool_commands._save_pool = _save_pool
    pool_commands._empty_pool = _empty_pool


def main(argv: list[str] | None = None) -> int:
    _sync_compat_overrides()
    return _app_main(argv)


__all__ = [
    "build_parser",
    "main",
    "_acquire_bulk_lock",
    "_append_tracking",
    "_bulk_lock_path",
    "_bulk_progress_log_path",
    "_cmd_pool",
    "_empty_pool",
    "_load_pool",
    "_pool_add",
    "_pool_path",
    "_pool_promote",
    "_pool_remove",
    "_pool_status",
    "_pool_sync_from_scan",
    "_pool_update",
    "_release_bulk_lock",
    "_resolve_bulk_pairs",
    "_save_pool",
    "_stock_names_path",
    "_tracking_path",
    "_write_bulk_progress",
]
