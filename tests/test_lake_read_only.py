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
    # Trigger a connect() call so lake.duckdb is initialized on disk.
    # (write_bars_parquet skips connect when bars_dir is empty at check time)
    lake.list_symbols()


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


def test_read_only_lake_blocks_duckdb_catalog_writes(tmp_path: Path) -> None:
    """read_only lake 不能对 DuckDB catalog 写入（CREATE TABLE 等）。
    parquet 写入走文件系统，不受 read_only 限制，属于预期行为。
    """
    rw_lake = LocalDataLake(tmp_path)
    _write_test_bars(rw_lake)

    ro_lake = LocalDataLake(tmp_path, read_only=True)
    with pytest.raises(Exception):
        with ro_lake.connect() as con:
            con.execute("CREATE TABLE _test_block (x INT)")
